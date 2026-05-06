from workers.celery_app import celery_app
from workers.database import init_worker_db, get_db
from workers.helpers import convert_types_for_json, update_progress, extract_sample_rows
from workers.async_helper import run_async
from workers.pipeline.load import load_dataset, coerce_numeric_columns
from workers.pipeline.clean import clean_dataframe, calculate_quality_metrics

import os
import logging
import polars as pl
from datetime import datetime
from typing import Dict, List, Any, Optional

from services.analysis.analysis_service import analysis_service
from services.analysis.insight_interpreter import insight_interpreter
from services.charts.chart_recommender import chart_recommender
from services.datasets.faiss_vector_service import faiss_vector_service
from services.datasets.domain_detector import domain_detector
from services.datasets.data_profiler import data_profiler
from services.pipeline.profiler import profile_dataframe
from services.pipeline.classifier import classify
from services.pipeline.planner import plan
from services.pipeline.compute import compute_all
from services.pipeline.critic import check_all
from services.pipeline.narrator import narrate

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="datasage.process_dataset", max_retries=3)
def process_dataset_task(
    self, dataset_id: str, file_path: str, user_id: str = "unknown"
):
    logger.info(f"╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║ DATASET PROCESSING STARTED: {dataset_id:<30} ║")
    logger.info(f"╚════════════════════════════════════════════════════════════════╝")

    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    datasets_collection = db.uploads

    try:
        update_progress(
            self, datasets_collection, dataset_id, "Loading dataset", 5, "loading"
        )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        df = load_dataset(file_path)

        if df.is_empty():
            raise ValueError("Dataset is empty")

        if len(df.columns) == 0:
            raise ValueError("Dataset has no columns")

        df, coerce_cols = coerce_numeric_columns(df)
        logger.info(f"✓ Numeric coercion: {len(coerce_cols)} columns promoted")

        df_lazy = df.lazy()
        original_rows = len(df)
        schema = df.schema

        logger.info(f"✓ Loaded: {original_rows:,} rows × {len(schema):,} columns")

        update_progress(
            self, datasets_collection, dataset_id, "Cleaning dataset", 15, "cleaning"
        )

        df_clean = clean_dataframe(df_lazy, schema)
        cleaned_rows = len(df_clean)
        duplicates_removed = original_rows - cleaned_rows

        if duplicates_removed > 0:
            logger.info(f"✓ Removed {duplicates_removed:,} duplicate rows")

        parquet_path = None
        try:
            parquet_path = file_path.rsplit(".", 1)[0] + ".parquet"
            df_clean.write_parquet(parquet_path, compression="zstd")
            logger.info(f"✓ Saved Parquet: {parquet_path}")
        except Exception as e:
            logger.warning(f"Parquet save failed: {e}")
            parquet_path = None

        update_progress(
            self, datasets_collection, dataset_id, "Generating metadata", 25, "metadata"
        )

        column_metadata = []
        for col in df_clean.columns:
            col_data = df_clean[col]
            col_meta = {
                "name": col,
                "type": str(col_data.dtype),
                "null_count": col_data.null_count(),
                "null_percentage": round(
                    (col_data.null_count() / len(df_clean)) * 100, 2
                )
                if len(df_clean) > 0
                else 0,
                "unique_count": col_data.n_unique(),
            }

            if col_data.dtype in pl.NUMERIC_DTYPES:
                try:
                    col_meta["numeric_summary"] = {
                        "min": float(col_data.min())
                        if col_data.min() is not None
                        else None,
                        "max": float(col_data.max())
                        if col_data.max() is not None
                        else None,
                        "mean": round(float(col_data.mean()), 2)
                        if col_data.mean() is not None
                        else None,
                    }
                except Exception:
                    pass
            elif col_data.dtype == pl.Boolean or col_data.n_unique() <= 20:
                try:
                    col_meta["top_values"] = [
                        {"value": str(v), "count": int((col_data == v).sum())}
                        for v in col_data.drop_nulls().unique().to_list()[:10]
                    ]
                except Exception:
                    pass
            elif col_data.dtype == pl.Utf8 and col_data.n_unique() < 100:
                try:
                    vc = (
                        df_clean.group_by(col)
                        .len()
                        .sort("len", descending=True)
                        .head(10)
                    )
                    col_meta["top_values"] = [
                        {"value": row[col], "count": row["len"]}
                        for row in vc.to_dicts()
                    ]
                except Exception:
                    pass

            column_metadata.append(col_meta)

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Detecting domain",
            35,
            "domain_detection",
        )

        sample_rows = extract_sample_rows(df_clean, n=5)

        try:
            domain_info = run_async(
                domain_detector.detect_domain_hybrid(
                    df=df_clean,
                    column_metadata=column_metadata,
                    sample_rows=sample_rows,
                )
            )
            logger.info(
                f"✓ Domain: {domain_info['domain']} (confidence: {domain_info['confidence']})"
            )
        except Exception as e:
            logger.warning(f"Domain detection failed: {e}")
            domain_info = {
                "domain": "general",
                "confidence": 0.5,
                "matched_patterns": [],
                "key_metrics": [],
                "dimensions": [],
                "measures": [],
                "time_columns": [],
                "method": "fallback",
            }

        update_progress(
            self, datasets_collection, dataset_id, "Computing KPI primitives", 42, "kpi_pipeline"
        )

        pipeline_profile = None
        pipeline_specs = []
        pipeline_results = []
        pipeline_cards = []
        try:
            pipeline_profile = run_async(
                profile_dataframe(
                    df_clean,
                    domain_signal=domain_info.get("domain", "general"),
                    domain_confidence=float(domain_info.get("confidence", 0.5)),
                )
            )
            pipeline_specs = classify(pipeline_profile)
            pipeline_specs = run_async(plan(pipeline_profile, pipeline_specs))
            pipeline_results = run_async(compute_all(pipeline_specs, df_clean))
            pipeline_results = check_all(pipeline_results)
            pipeline_cards = run_async(narrate(pipeline_results, pipeline_specs))
            logger.info(
                f"✓ Pipeline: {len(pipeline_results)} primitives → {len(pipeline_cards)} cards"
            )
        except Exception as e:
            logger.warning(f"KPI pipeline failed: {e}")

        update_progress(
            self, datasets_collection, dataset_id, "Profiling data", 45, "profiling"
        )

        try:
            profile_info = data_profiler.profile_dataset(df_clean, column_metadata)
            logger.info(f"✓ Profiled: {profile_info['row_count']:,} rows")
        except Exception as e:
            logger.warning(f"Data profiling failed: {e}")
            profile_info = {
                "row_count": len(df_clean),
                "column_count": len(df_clean.columns),
                "cardinality": {},
                "patterns": {},
                "quality_metrics": {},
                "relationships": {},
                "id_columns": [],
                "high_cardinality_dims": [],
                "low_cardinality_dims": [],
            }

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Running deep statistical analysis",
            55,
            "analysis",
        )

        try:
            enhanced_results = analysis_service.run_enhanced_analysis(
                df_clean, depth="standard"
            )
            logger.info(f"✓ Enhanced analysis complete")
        except Exception as e:
            enhanced_results = {
                "depth": "fallback",
                "row_count": len(df_clean),
                "column_count": len(df_clean.columns),
                "distributions": [],
                "correlations": [],
            }

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Running QUIS subspace analysis",
            65,
            "quis_analysis",
        )

        try:
            quis_results = analysis_service.run_enhanced_quis_sync(
                df_clean, dataset_id=dataset_id
            )
            logger.info(f"✓ QUIS complete")
        except Exception as e:
            quis_results = {
                "summary": {"total_questions": 0, "significant_insights": 0},
                "insights": [],
                "top_insights": [],
            }

        try:
            executive_summary = insight_interpreter.generate_summary(enhanced_results)
        except Exception:
            executive_summary = ""

        try:
            statistical_findings = analysis_service.run_all_statistical_checks(df_clean)
        except Exception:
            statistical_findings = {
                "correlations": [],
                "outliers": [],
                "distributions": {},
            }

        deep_analysis = {
            "enhanced_analysis": enhanced_results,
            "quis_insights": quis_results,
            "executive_summary": executive_summary,
            "analysis_version": "2.0",
        }

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Generating chart recommendations",
            70,
            "charts",
        )

        try:
            chart_recommendations = chart_recommender.recommend_charts(
                df=df_clean,
                column_metadata=column_metadata,
                domain=domain_info["domain"],
                cardinality=profile_info.get("cardinality", {}),
                time_columns=domain_info.get("time_columns", []),
            )
            logger.info(
                f"✓ Generated {len(chart_recommendations)} chart recommendations"
            )
        except Exception as e:
            chart_recommendations = []

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Calculating quality metrics",
            80,
            "quality",
        )

        data_quality = calculate_quality_metrics(
            column_metadata, original_rows, duplicates_removed
        )
        logger.info(f"✓ Quality: {data_quality['completeness']:.1f}% complete")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Consolidating metadata",
            85,
            "consolidating",
        )

        final_metadata = {
            "dataset_overview": {
                "total_rows": cleaned_rows,
                "total_columns": len(df_clean.columns),
                "original_rows": original_rows,
                "file_type": file_path.split(".")[-1].lower(),
            },
            "column_metadata": column_metadata,
            "domain_intelligence": domain_info,
            "data_profile": profile_info,
            "statistical_findings": statistical_findings,
            "deep_analysis": deep_analysis,
            "chart_recommendations": chart_recommendations,
            "data_quality": data_quality,
            "pipeline_profile": pipeline_profile.model_dump() if pipeline_profile else None,
            "pipeline_specs": [s.model_dump() for s in pipeline_specs],
            "pipeline_results": [r.model_dump() for r in pipeline_results],
            "pipeline_cards": [c.model_dump() for c in pipeline_cards],
            "sample_data": sample_rows[:3],
            "processing_info": {
                "processed_at": datetime.utcnow(),
                "pipeline_version": "3.0",
                "celery_task_id": self.request.id,
            },
        }

        sanitized_metadata = convert_types_for_json(final_metadata)

        update_progress(
            self, datasets_collection, dataset_id, "Saving to database", 90, "saving"
        )

        update_fields = {
            "metadata": sanitized_metadata,
            "is_processed": True,
            "processing_status": "success",
            "row_count": cleaned_rows,
            "column_count": len(df_clean.columns),
            "domain": domain_info["domain"],
            "domain_confidence": domain_info["confidence"],
            "updated_at": datetime.utcnow(),
        }
        if parquet_path:
            update_fields["parquet_path"] = parquet_path
        datasets_collection.update_one({"_id": dataset_id}, {"$set": update_fields})

        try:
            analytics_collection = db.dataset_analytics
            analytics_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "chart_recommendations": convert_types_for_json(chart_recommendations),
                "statistical_findings": convert_types_for_json(statistical_findings),
                "deep_analysis": convert_types_for_json(deep_analysis),
                "data_profile": convert_types_for_json(profile_info),
                "domain_intelligence": convert_types_for_json(domain_info),
                "data_quality": convert_types_for_json(data_quality),
                "pipeline_results": convert_types_for_json([r.model_dump() for r in pipeline_results]),
                "pipeline_cards": convert_types_for_json([c.model_dump() for c in pipeline_cards]),
                "pipeline_profile": convert_types_for_json(pipeline_profile.model_dump() if pipeline_profile else {}),
                "computed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "pipeline_version": "3.0",
            }
            analytics_collection.update_one(
                {"dataset_id": dataset_id, "user_id": user_id},
                {"$set": analytics_doc},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to save analytics: {e}")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Pre-computing KPIs",
            90,
            "artifact_generation",
        )

        try:
            from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
            from services.cache.dashboard_cache_service import dashboard_cache_service
            from services.datasets.enhanced_dataset_service import (
                enhanced_dataset_service,
            )

            try:
                kpi_df = run_async(
                    enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
                )
                domain_for_kpi = domain_info.get("domain", "general")
                intelligent_kpis = run_async(
                    intelligent_kpi_generator.generate_intelligent_kpis(
                        df=kpi_df,
                        domain=domain_for_kpi,
                        max_kpis=4,
                        dataset_metadata=sanitized_metadata,
                    )
                )
                run_async(
                    dashboard_cache_service.cache_kpis(
                        dataset_id, user_id, intelligent_kpis
                    )
                )
                logger.info(f"✓ Pre-computed {len(intelligent_kpis)} KPIs")
            except Exception as e:
                logger.warning(f"KPI pre-computation failed: {e}")
                logger.debug(f"KPI pre-computation error details: {type(e).__name__}")
        except Exception as e:
            logger.warning(f"KPI pre-computation import/initialization failed: {e}")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Pre-computing charts",
            92,
            "artifact_generation",
        )

        try:
            from services.charts.chart_render_service import chart_render_service
            from services.charts.chart_intelligence_service import (
                chart_intelligence_service,
            )
            from services.cache.dashboard_cache_service import dashboard_cache_service
            from services.datasets.enhanced_dataset_service import (
                enhanced_dataset_service,
            )

            try:
                chart_df = run_async(
                    enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
                )
            except Exception as e:
                logger.warning(f"Chart pre-computation data load failed: {e}")
                logger.debug(f"Chart pre-computation error details: {type(e).__name__}")
                chart_df = None

            if chart_df is not None:
                col_meta = sanitized_metadata.get("column_metadata", [])
                data_profile = sanitized_metadata.get("data_profile", {})
                domain_intel = sanitized_metadata.get("domain_intelligence", {})
                deep_analysis_data = sanitized_metadata.get("deep_analysis", {})

                numeric_cols = chart_df.select(pl.col(pl.NUMERIC_DTYPES)).columns
                categorical_cols = chart_df.select(pl.col(pl.Utf8, pl.Categorical)).columns

                precomputed_charts = {}
                if numeric_cols and categorical_cols:
                    chart_selection = chart_intelligence_service.select_dashboard_charts(
                        df=chart_df,
                        column_metadata=col_meta,
                        domain=domain_intel.get("domain", "general"),
                        domain_confidence=domain_intel.get("confidence", 0.5),
                        statistical_findings=deep_analysis_data.get(
                            "enhanced_analysis", {}
                        ),
                        data_profile=data_profile,
                        context="executive",
                    )
                    for i, chart_spec in enumerate(chart_selection.get("charts", [])[:5]):
                        config = chart_spec.get("config", {})
                        chart_data = run_async(
                            chart_render_service.render_chart(
                                chart_df,
                                {
                                    "chart_type": chart_spec.get("chart_type", "bar"),
                                    "columns": config.get(
                                        "columns", [categorical_cols[0], numeric_cols[0]]
                                    ),
                                    "aggregation": config.get("aggregation", "sum"),
                                },
                            )
                        )
                        precomputed_charts[f"chart_{i}"] = chart_data

                if precomputed_charts:
                    run_async(
                        dashboard_cache_service.cache_charts(
                            dataset_id, user_id, precomputed_charts
                        )
                    )
                    logger.info(f"✓ Pre-computed {len(precomputed_charts)} charts")
                else:
                    logger.debug("No charts were successfully pre-computed")
        except Exception as e:
            logger.warning(f"Chart pre-computation failed: {e}")
            logger.debug(f"Chart pre-computation error details: {type(e).__name__}")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Preparing dashboard design",
            94,
            "artifact_generation",
        )

        try:
            from services.ai.ai_designer_service import AIDesignerService

            designer_service = AIDesignerService(sync_db=db)
            run_async(
                designer_service.design_intelligent_dashboard(
                    dataset_id=dataset_id, user_id=user_id, force_regenerate=True
                )
            )
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "artifact_status.dashboard_design": "ready",
                        "artifact_status.dashboard_generated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as e:
            logger.warning(f"Dashboard design failed: {e}")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Indexing to vector database",
            95,
            "vector_indexing",
        )

        try:
            run_async(
                faiss_vector_service.add_dataset_to_vector_db(
                    dataset_id=dataset_id,
                    dataset_metadata=sanitized_metadata,
                    user_id=user_id,
                )
            )
            logger.info(f"✓ Vector indexing successful")
        except Exception as e:
            logger.error(f"✗ Vector indexing failed: {e}")
            logger.debug(f"Vector indexing error details: {type(e).__name__}")

        update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Processing complete",
            100,
            "completed",
        )

        logger.info(
            f"╔════════════════════════════════════════════════════════════════╗"
        )
        logger.info(f"║ DATASET PROCESSING COMPLETED: {dataset_id:<27} ║")
        logger.info(
            f"╚════════════════════════════════════════════════════════════════╝"
        )

        return {
            "status": "success",
            "progress": 100,
            "dataset_id": dataset_id,
            "rows": cleaned_rows,
            "columns": len(df_clean.columns),
            "domain": domain_info["domain"],
            "quality": data_quality["completeness"],
        }

    except Exception as e:
        logger.error(
            f"╔════════════════════════════════════════════════════════════════╗"
        )
        logger.error(f"║ DATASET PROCESSING FAILED: {dataset_id:<30} ║")
        logger.error(f"║ Error: {str(e)[:50]:<54} ║")
        logger.error(
            f"╚════════════════════════════════════════════════════════════════╝"
        )
        logger.exception(e)

        if db is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "is_processed": True,
                        "processing_status": "failed",
                        "processing_error": str(e)[:1000],
                        "error_type": type(e).__name__,
                        "failed_at": datetime.utcnow(),
                    }
                },
            )

        error_message = str(e)[:1000]
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Processing failed",
                "error": error_message,
                "error_type": type(e).__name__,
                "dataset_id": dataset_id,
            },
        )
        raise
