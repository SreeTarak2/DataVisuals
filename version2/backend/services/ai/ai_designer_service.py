# backend/services/ai/ai_designer_service.py

import logging
import json
import inspect
import concurrent.futures
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from bson import ObjectId

from db.database import get_database
from llm.router import llm_router
from prompts.dashboard import get_dashboard_designer_prompt
from .kpi_profiler import get_business_category
from .kpi_families import assign_families, detect_family_from_name, format_family_block_for_prompt

logger = logging.getLogger(__name__)


class AIDesignerService:
    """
    AI Designer Service: Produces intelligent, context-aware dashboard blueprints.

    Architecture:
    - Reads dataset metadata and sample data rows from MongoDB
    - Builds a rich context string (metadata stats + actual data sample rows)
    - Sends a single prompt to the best LLM (DeepSeek V4 Flash via layout_designer role)
    - LLM returns a JSON blueprint with KPIs, charts, and layout
    - Validates blueprint (column resolution, cardinality enforcement)
    - Persists to MongoDB
    """

    def __init__(self, sync_db=None):
        self._db = sync_db
        # Empty — no hardcoded pattern templates. The LLM generates from scratch.

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    @property
    def _is_async_db(self) -> bool:
        db = self._db if self._db is not None else get_database()
        if db is None:
            return True
        db_type = type(db).__name__
        return (
            "Async" in db_type
            or hasattr(db, "find_one")
            and inspect.iscoroutinefunction(db.find_one)
        )

    async def _db_op(self, operation, *args, **kwargs):
        if self._is_async_db:
            return await operation(*args, **kwargs)
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(operation, *args, **kwargs)
                return future.result()

    # ---------------------------------------------------------
    # UTILITY: GET EXISTING DASHBOARD
    # ---------------------------------------------------------
    async def get_existing_dashboard(
        self, dataset_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch existing dashboard without regenerating."""
        try:
            dashboard = await self._db_op(
                self.db.dashboards.find_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
            )

            if dashboard:
                return {
                    "dashboard_blueprint": dashboard.get("blueprint"),
                    "reasoning": "Loaded from cache",
                    "cached": True,
                    "created_at": dashboard.get("created_at"),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching existing dashboard: {e}")
            return None

    # ---------------------------------------------------------
    # UTILITY: UPDATE COMPONENT CONFIG
    # ---------------------------------------------------------
    async def update_dashboard_component(
        self,
        dataset_id: str,
        user_id: str,
        component_title: str,
        updated_config: Dict[str, Any],
    ) -> bool:
        """Update a single component's config in an existing dashboard."""
        try:
            dashboard = await self._db_op(
                self.db.dashboards.find_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
            )

            if not dashboard or "blueprint" not in dashboard:
                logger.warning(
                    f"Cannot update component: No dashboard found for dataset {dataset_id}"
                )
                return False

            blueprint = dashboard["blueprint"]
            components = blueprint.get("components", [])
            updated = False
            for comp in components:
                if comp.get("title") == component_title:
                    comp["config"] = updated_config
                    updated = True
                    break

            if not updated:
                logger.warning(
                    f"Component '{component_title}' not found in dashboard for dataset {dataset_id}"
                )
                return False

            await self._db_op(
                self.db.dashboards.update_one,
                {"_id": dashboard["_id"]},
                {"$set": {"blueprint": blueprint, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
            )

            logger.info(f"Updated component '{component_title}' in dashboard for dataset {dataset_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating component '{component_title}': {e}")
            return False

    # ---------------------------------------------------------
    # MAIN ENTRY: DESIGN DASHBOARD
    # ---------------------------------------------------------
    async def design_intelligent_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        design_preference: Optional[str] = None,
        force_regenerate: bool = False,
        conversation_summary: Optional[str] = None,
        redesign_mode: str = "layout",
        selected_columns: Optional[List[str]] = None,
        user_intent: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Design an intelligent dashboard for a dataset.

        Flow:
        1. Load dataset metadata + sample data rows from MongoDB (workspace-scoped)
        2. Build rich context string (statistics + actual data rows)
        3. Call single LLM (DeepSeek V4 Flash) for the full blueprint
        4. Validate blueprint (column resolution, cardinality enforcement)
        5. Persist to DB

        Args:
            workspace_id: Optional tenant scope. When omitted, resolves the
                user's personal workspace (canonical post-backfill tag).
        """
        try:
            # Resolve tenant scope (explicit workspace → personal workspace)
            wid = workspace_id
            if wid is None:
                try:
                    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

                    wid = await enhanced_dataset_service._effective_workspace(None, user_id)
                except Exception:
                    from db.tenant_guard import resolve_workspace_id

                    wid = resolve_workspace_id(None, user_id)

            from db.tenant_guard import tenant_scope_query

            # Safe ObjectId handling + strict workspace pin
            try:
                dataset_oid = ObjectId(dataset_id)
                query = tenant_scope_query(
                    "uploads", {"_id": dataset_oid}, wid, user_id
                )
            except Exception:
                query = tenant_scope_query(
                    "uploads", {"_id": dataset_id}, wid, user_id
                )

            dataset_doc = await self._db_op(self.db.uploads.find_one, query)

            if not dataset_doc or not dataset_doc.get("metadata"):
                raise RuntimeError("Dataset metadata missing — cannot design dashboard.")

            # CHECK FOR EXISTING DASHBOARD (unless force_regenerate)
            if not force_regenerate:
                existing_dashboard = await self._db_op(
                    self.db.dashboards.find_one,
                    {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                )
                if existing_dashboard:
                    logger.info(f"Found existing dashboard for dataset {dataset_id}, returning cached version")
                    return {
                        "dashboard_blueprint": existing_dashboard.get("blueprint"),
                        "reasoning": "Loaded from cache (previously generated)",
                        "cached": True,
                        "created_at": existing_dashboard.get("created_at"),
                    }
                else:
                    logger.info(f"No existing dashboard found for dataset {dataset_id}, generating new one")

            metadata = dataset_doc["metadata"]

            # ── FILTER to selected columns (if provided) ──
            if selected_columns:
                metadata = self._filter_metadata_to_columns(metadata, selected_columns)
                logger.info(f"Filtered metadata to {len(selected_columns)} user-selected columns: {selected_columns}")

            # Inject user_intent into metadata for context building
            if user_intent:
                metadata["_user_intent"] = user_intent
                logger.info(f"User intent injected: {user_intent[:80]}...")

            # ── LAYOUT-ONLY REDESIGN: Re-generate with existing components as context ──
            if force_regenerate and redesign_mode == "layout":
                return await self._redesign_layout_only(
                    dataset_id, user_id, metadata, dataset_doc, workspace_id=wid
                )

            # ── Build dataset context for AI (with sample data rows) ──
            sample_data = dataset_doc.get("metadata", {}).get("sample_data", [])
            dataset_context = self._create_dataset_context_string(metadata, sample_data)

            # ── Generate dashboard using single best LLM ──
            logger.info("🤖 Using single LLM (DeepSeek V4 Flash) for dashboard design")

            prompt = self._create_designer_prompt(metadata, dataset_context)

            # ── Max-1 retry loop for critical structural failures ──
            retry_attempt = 0
            blueprint = None
            retry_reason = None

            while retry_attempt <= 1:
                try:
                    if retry_attempt == 0:
                        current_prompt = prompt
                    else:
                        # Build targeted correction prompt with specific failure details
                        current_prompt = prompt + "\n\n" + self._build_correction_prompt(retry_reason)
                        logger.info(f"🔄 Retry attempt {retry_attempt}: {retry_reason[:100]}...")

                    ai_output = await llm_router.call(
                        current_prompt, model_role="layout_designer", expect_json=True
                    )
                    full_response = json.dumps(ai_output, indent=2)[:800]
                    logger.info(f"AI Designer LLM Response (first 800 chars): {full_response}")
                except Exception as e:
                    logger.exception(f"LLM call failed on attempt {retry_attempt}: {e}")
                    if retry_attempt == 1:
                        raise RuntimeError(f"AI generation failed after retry: {e}")
                    retry_attempt += 1
                    retry_reason = f"LLM call failed with error: {e}"
                    continue

                # ── Validate and repair (deterministic — fixes column names, cardinality, etc.) ──
                extracted = ai_output.get("dashboard", {})
                blueprint = self._validate_and_enhance_design(extracted, metadata)

                # ── Check if retry is needed (critical structural failures only) ──
                retry_reason = self._needs_retry(blueprint, metadata)
                if retry_reason and retry_attempt == 0:
                    logger.warning(f"🔄 Dashboard needs retry: {retry_reason}")
                    retry_attempt += 1
                    continue

                # Success — exit the loop
                break

            if retry_reason:
                logger.warning(f"⚠️ Dashboard used fallback components after retry: {retry_reason}")

            # ── Persist ──
            design_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "design_pattern": "ai_generated",
                "blueprint": blueprint,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "is_default": True,
            }

            await self._db_op(
                self.db.dashboards.update_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                {"$set": design_doc},
                upsert=True,
            )

            # Update artifact_status
            try:
                await self._db_op(
                    self.db.uploads.update_one,
                    query,
                    {
                        "$set": {
                            "artifact_status.dashboard_design": "ready",
                            "artifact_status.dashboard_generated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                        }
                    },
                )
            except Exception as status_err:
                logger.warning(f"Failed to update artifact_status (non-fatal): {status_err}")

            logger.info(f"{'Regenerated' if force_regenerate else 'Created'} dashboard for dataset {dataset_id}")

            return {
                "dashboard_blueprint": blueprint,
                "reasoning": "Single LLM generated blueprint (DeepSeek V4 Flash)",
                "cached": False,
                "created_at": design_doc["created_at"],
            }

        except Exception as e:
            logger.exception("AI Designer error")
            raise RuntimeError(f"Failed to design dashboard: {e}") from e

    # ---------------------------------------------------------
    # Layout-only redesign (regenerate with existing context)
    # ---------------------------------------------------------
    async def _redesign_layout_only(
        self,
        dataset_id: str,
        user_id: str,
        metadata: Dict,
        dataset_doc: Dict,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Regenerate dashboard with existing components as context.
        Pulls the existing cache, provides it to the LLM, and asks for a fresh layout.
        """
        existing_dashboard = await self._db_op(
            self.db.dashboards.find_one,
            {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
        )

        if not existing_dashboard or not existing_dashboard.get("blueprint"):
            logger.info(f"[Layout redesign] No cached blueprint for {dataset_id}, falling back to fresh generation")
            return await self.design_intelligent_dashboard(
                dataset_id=dataset_id,
                user_id=user_id,
                force_regenerate=True,
                redesign_mode="full",
                workspace_id=workspace_id,
            )

        existing_components = existing_dashboard["blueprint"].get("components", [])
        logger.info(f"[Layout redesign] Using {len(existing_components)} existing components as context for regeneration")

        # Attach existing components as context for the LLM
        metadata["_existing_components"] = json.dumps(existing_components, indent=2)[:2000]

        sample_data = dataset_doc.get("metadata", {}).get("sample_data", [])
        dataset_context = self._create_dataset_context_string(metadata, sample_data)
        prompt = self._create_designer_prompt(metadata, dataset_context)

        try:
            ai_output = await llm_router.call(
                prompt, model_role="layout_designer", expect_json=True
            )
        except Exception as e:
            logger.error(f"[Layout redesign] LLM call failed: {e}")
            return {
                "dashboard_blueprint": existing_dashboard["blueprint"],
                "reasoning": "Layout redesign failed, kept previous version",
                "cached": True,
            }

        blueprint = self._validate_and_enhance_design(
            ai_output.get("dashboard", {}), metadata
        )

        design_doc = {
            "dataset_id": dataset_id,
            "user_id": user_id,
            "design_pattern": "ai_generated",
            "blueprint": blueprint,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "is_default": True,
        }

        await self._db_op(
            self.db.dashboards.update_one,
            {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
            {"$set": design_doc},
            upsert=True,
        )

        return {
            "dashboard_blueprint": blueprint,
            "reasoning": "Layout redesigned with LLM (used existing components as context)",
            "cached": False,
            "created_at": design_doc["created_at"],
        }

    # ---------------------------------------------------------
    # Prompt generation
    # ---------------------------------------------------------
    def _create_designer_prompt(self, metadata: Dict, dataset_context: str) -> str:
        colmeta = metadata.get("column_metadata", [])
        valid_columns = [c["name"] for c in colmeta if isinstance(c.get("name"), str)]

        # ── Compute metric family coverage ──
        domain = metadata.get("domain_intelligence", {}).get("domain", "general")
        column_metadata_for_families = []
        for c in colmeta:
            col_name = c.get("name", "")
            col_type = c.get("type", "")
            # Detect business_category from name patterns for better family assignment
            biz_cat, _ = get_business_category(col_name)
            column_metadata_for_families.append({
                "name": col_name,
                "type": col_type,
                "business_category": biz_cat if biz_cat != "unknown" else None,
            })

        family_report = assign_families(
            column_metadata_for_families,
            domain=domain if domain != "general" else None,
        )
        family_block = format_family_block_for_prompt(family_report)

        # Inject family block into dataset context
        augmented_context = f"{family_block}\n\n{dataset_context}"

        design_strategy = None
        if "analytical_strategy" in metadata or "priority_signals" in metadata:
            design_strategy = {
                "analytical_strategy": metadata.get("analytical_strategy", ""),
                "priority_signals": metadata.get("priority_signals", []),
            }

        return get_dashboard_designer_prompt(
            augmented_context, valid_columns=valid_columns, design_strategy=design_strategy
        )

    # ---------------------------------------------------------
    # Retry decision logic — critical structural failures only
    # ---------------------------------------------------------
    def _needs_retry(self, blueprint: Dict, metadata: Dict) -> Optional[str]:
        """
        Determine if the dashboard blueprint has CRITICAL structural failures
        that require a full LLM retry. Returns None (no retry needed) or a
        string describing the reason for retry.

        Only retries on failures the deterministic _validate_and_enhance_design
        CANNOT fix:
        - Completely empty components array
        - All components were rejected as hallucinated
        - Blueprint is missing entirely (not a dict)
        - Zero valid KPIs AND zero valid charts after validation
        - No components at all (fallback was also empty)

        Minor issues like column name resolution, cardinality enforcement, or
        missing layout_grid are handled deterministically and do NOT trigger retry.
        """
        if not isinstance(blueprint, dict):
            return "Blueprint is not a valid dict"

        components = blueprint.get("components", [])
        if not components:
            return "All components were empty after validation — LLM generated nothing usable"

        # Check for valid components (not all were rejected)
        valid_kpis = [c for c in components if c.get("type") == "kpi"]
        valid_charts = [c for c in components if c.get("type") == "chart"]

        if not valid_kpis and not valid_charts:
            return "Zero valid KPIs and zero valid charts — blueprint has no usable components"

        # Check for the "Total Records" fallback KPI — if ALL KPIs are the generic fallback,
        # the LLM likely didn't understand the data. Only retry if there's more than 1 column
        # and no real KPI was generated.
        colmeta = metadata.get("column_metadata", [])
        if len(colmeta) > 3 and len(valid_kpis) == 1:
            only_kpi = valid_kpis[0]
            title = (only_kpi.get("title") or "").lower()
            fallback_col = only_kpi.get("config", {}).get("column", "")
            has_fallback_title = "total records" in title or "data overview" in title
            has_fallback_col = fallback_col in ("id", "count") or not fallback_col
            if has_fallback_title and has_fallback_col:
                return f"Only generic fallback KPI '{only_kpi.get('title')}' generated — no data-specific KPIs"

        # Everything looks structurally sound — no retry
        return None

    def _build_correction_prompt(self, retry_reason: Optional[str]) -> str:
        """
        Build a targeted correction message for the LLM retry.
        Attaches the specific failure details so the LLM knows exactly what went wrong.
        Uses a terse, actionable format to minimize token waste.
        """
        if not retry_reason:
            return ""

        return (
            "\n════════════════════════════════════════════════\n"
            "⚠️  PREVIOUS ATTEMPT FEEDBACK\n"
            "════════════════════════════════════════════════\n"
            f"Your previous dashboard generation had a critical issue:\n"
            f"{retry_reason}\n\n"
            "Please regenerate the dashboard following ALL the design rules above.\n"
            "Specifically:\n"
            "1. Focus on the SAMPLE DATA ROWS to understand real patterns in the data.\n"
            "2. Generate meaningful, data-specific KPIs — not generic placeholders.\n"
            "3. Review the dataset columns carefully and choose columns that tell a story.\n"
            "4. Include at least one KPI with a real numeric column and appropriate aggregation.\n"
            "5. Include at least one chart that shows a meaningful comparison or trend.\n"
            "════════════════════════════════════════════════"
        )

    # ---------------------------------------------------------
    # Blueprint validation / repair
    # ---------------------------------------------------------
    def _validate_and_enhance_design(self, blueprint: Dict, metadata: Dict) -> Dict:
        """
        Validates the structure of the blueprint and passes it through
        data-aware validation to remove hallucinated columns and enforce cardinality limits.
        """
        # Handle nested structure
        if blueprint and "dashboard" in blueprint and isinstance(blueprint["dashboard"], dict):
            logger.info("Detected nested 'dashboard' key, extracting inner blueprint")
            blueprint = blueprint["dashboard"]

        if not blueprint or "components" not in blueprint:
            logger.warning(f"Invalid AI blueprint. Keys: {list(blueprint.keys()) if blueprint else 'None'}. Creating minimal dashboard.")
            blueprint = {
                "components": [
                    {"type": "kpi", "title": "Total Records", "span": 1, "config": {"column": "id", "aggregation": "count"}},
                    {"type": "chart", "title": "Data Overview", "span": 4, "config": {"chart_type": "bar", "columns": [], "aggregation": "count"}},
                ]
            }

        components = blueprint.get("components", [])

        # Data-Aware Validation Pass
        valid_components = []
        for comp in components:
            validated_comp = self._validate_blueprint_component_with_data_stats(comp, metadata)
            if validated_comp:
                valid_components.append(validated_comp)

        blueprint["components"] = valid_components

        types = [c.get("type") for c in valid_components]

        # Ensure at least one KPI (with family-aware fallback)
        if "kpi" not in types:
            colmeta = metadata.get("column_metadata", [])
            first_numeric = next((c["name"] for c in colmeta if c.get("type") in ("numeric", "integer", "float", "int") and "id" not in c.get("name", "").lower()), None)
            blueprint["components"].insert(
                0,
                {
                    "type": "kpi",
                    "title": "Total Records",
                    "span": 1,
                    "config": {"column": first_numeric or "id", "aggregation": "count"},
                    "_fallbackReason": "Added fallback KPI because none were found.",
                    "_metric_family": "volume",
                },
            )

        # Ensure at least one chart
        if "chart" not in types:
            first_col = (metadata.get("column_metadata") or [{}])[0].get("name", "value")
            blueprint["components"].insert(
                1,
                {
                    "type": "chart",
                    "title": "Data Overview",
                    "span": 2,
                    "config": {"chart_type": "bar", "columns": [first_col], "aggregation": "count"},
                    "_fallbackReason": "Added fallback Chart because none were found.",
                },
            )

        # Ensure layout_grid
        if "layout_grid" not in blueprint:
            blueprint["layout_grid"] = "repeat(4, 1fr)"

        # ── Family-aware enrichment: tag each KPI with its metric family ──
        colmeta = metadata.get("column_metadata", [])
        col_type_map = {c.get("name", ""): c.get("type", "numeric") for c in colmeta}
        for comp in blueprint["components"]:
            if comp.get("type") == "kpi":
                col = comp.get("config", {}).get("column", "")
                if col:
                    col_type = col_type_map.get(col, "numeric")
                    biz_cat, _ = get_business_category(col)
                    family, _ = detect_family_from_name(col, col_type, biz_cat if biz_cat != "unknown" else None)
                    if family:
                        comp["_metric_family"] = family.value

        return blueprint

    def _validate_blueprint_component_with_data_stats(
        self, comp: Dict, metadata: Dict
    ) -> Optional[Dict]:
        """
        Deep validation for a single dashboard component.
        - Resolves fuzzy/hallucinated column names to EXACT dataset column names.
        - Handles group_by as string OR array of strings.
        - Enforces cardinality restrictions.
        """
        colmeta = metadata.get("column_metadata", [])
        valid_col_names = [c["name"] for c in colmeta if c.get("name")]
        valid_col_names_lower = {name.lower().strip(): name for name in valid_col_names}

        def resolve_column(requested_col: str) -> Optional[str]:
            if not requested_col:
                return None
            req_lower = str(requested_col).lower().strip()
            if req_lower in valid_col_names_lower:
                return valid_col_names_lower[req_lower]
            for valid_lower, actual_name in valid_col_names_lower.items():
                if req_lower in valid_lower or valid_lower in req_lower:
                    return actual_name
            return None

        ctype = comp.get("type", "")
        cfg = comp.get("config", {})
        fallback_reasons = []

        if ctype == "kpi":
            req_col = cfg.get("column")
            actual_col = resolve_column(req_col)
            if not actual_col:
                return None
            if actual_col != req_col:
                fallback_reasons.append(f"Mapped hallucinated column '{req_col}' to '{actual_col}'.")
            cfg["column"] = actual_col

        elif ctype == "chart":
            chart_type = cfg.get("chart_type", "bar")
            requested_cols = cfg.get("columns", [])

            actual_cols = []
            for c in requested_cols:
                resolved = resolve_column(c)
                if resolved:
                    actual_cols.append(resolved)
                else:
                    fallback_reasons.append(f"Dropped hallucinated column '{c}'.")

            if not actual_cols:
                return None

            cfg["columns"] = actual_cols
            cfg["x"] = resolve_column(cfg.get("x")) or (actual_cols[0] if len(actual_cols) > 0 else None)
            cfg["y"] = resolve_column(cfg.get("y")) or (actual_cols[1] if len(actual_cols) > 1 else None)

            # group_by: support null | "string" | ["str1", "str2"]
            group_val = cfg.get("group_by")
            if group_val:
                if isinstance(group_val, list):
                    resolved_group = [resolve_column(g) for g in group_val if isinstance(g, str)]
                    cfg["group_by"] = [g for g in resolved_group if g]
                elif isinstance(group_val, str):
                    resolved = resolve_column(group_val)
                    cfg["group_by"] = resolved if resolved else None
                else:
                    cfg["group_by"] = None

            # Enforce Cardinality for Pie
            if chart_type in ["pie", "pie_chart", "donut"]:
                data_profile = metadata.get("data_profile", {})
                cardinality_map = data_profile.get("cardinality", {})
                group_col = cfg.get("x") or (cfg.get("columns", [""])[0] if cfg.get("columns") else "")
                if group_col in cardinality_map:
                    unique_count = cardinality_map[group_col].get("unique_count", 0)
                    if unique_count > 15:
                        cfg["chart_type"] = "bar"
                        fallback_reasons.append(
                            f"Pie chart changed to Bar because '{group_col}' has high cardinality ({unique_count} > 15)."
                        )

        elif ctype in ["pivot_table", "anomaly_feed"]:
            requested_cols = cfg.get("columns", [])
            actual_cols = []
            for c in requested_cols:
                resolved = resolve_column(c)
                if resolved:
                    actual_cols.append(resolved)
                else:
                    fallback_reasons.append(f"Dropped hallucinated column '{c}'.")
            if not actual_cols:
                return None
            cfg["columns"] = actual_cols

        comp["config"] = cfg
        if fallback_reasons:
            comp["_fallbackReason"] = " | ".join(fallback_reasons)

        return comp

    # ---------------------------------------------------------
    # Metadata filtering
    # ---------------------------------------------------------
    def _filter_metadata_to_columns(self, metadata: Dict, selected_columns: List[str]) -> Dict:
        """Filter metadata to only include user-selected columns."""
        selected_set = set(selected_columns)

        colmeta = metadata.get("column_metadata", [])
        metadata["column_metadata"] = [c for c in colmeta if c.get("name") in selected_set]

        domain = metadata.get("domain_intelligence", {})
        if domain:
            for key in ("measures", "dimensions", "time_columns", "key_metrics"):
                if key in domain and isinstance(domain[key], list):
                    domain[key] = [v for v in domain[key] if v in selected_set]
            metadata["domain_intelligence"] = domain

        profile = metadata.get("data_profile", {})
        if profile:
            if "cardinality" in profile:
                profile["cardinality"] = {k: v for k, v in profile["cardinality"].items() if k in selected_set}
            if "id_columns" in profile:
                profile["id_columns"] = [c for c in profile["id_columns"] if c in selected_set]
            if "low_cardinality_dims" in profile:
                profile["low_cardinality_dims"] = [c for c in profile["low_cardinality_dims"] if c in selected_set]
            metadata["data_profile"] = profile

        deep = metadata.get("deep_analysis", {})
        enhanced = deep.get("enhanced_analysis", {})
        if enhanced:
            if "correlations" in enhanced:
                enhanced["correlations"] = [
                    c for c in enhanced["correlations"]
                    if c.get("column1") in selected_set and c.get("column2") in selected_set
                ]
            if "distributions" in enhanced:
                enhanced["distributions"] = [
                    d for d in enhanced["distributions"] if d.get("column") in selected_set
                ]
            deep["enhanced_analysis"] = enhanced
            metadata["deep_analysis"] = deep

        recs = metadata.get("chart_recommendations", [])
        if recs:
            metadata["chart_recommendations"] = [
                r for r in recs if any(c in selected_set for c in (r.get("columns", []) or []))
            ]

        overview = metadata.get("dataset_overview", {})
        if overview:
            overview["total_columns"] = len(metadata["column_metadata"])
            metadata["dataset_overview"] = overview

        # Also filter sample_data rows
        sample_data = metadata.get("sample_data", [])
        if sample_data and selected_columns:
            metadata["sample_data"] = [
                {k: v for k, v in row.items() if k in selected_set}
                for row in sample_data
            ]

        return metadata

    # ---------------------------------------------------------
    # Context builder — THE KEY FUNCTION (now with sample data rows)
    # ---------------------------------------------------------
    def _create_dataset_context_string(self, metadata: Dict, sample_data: Optional[List[Dict]] = None) -> str:
        """
        Build a rich dataset context string for LLM prompts.

        NOW INCLUDES: actual sample data rows so the LLM can see real patterns.
        Previously this only sent metadata statistics — which is why the LLM
        couldn't make good chart choices.
        """
        sections = []

        # ── Inject user intent ──
        user_intent = metadata.get("_user_intent", None)
        if user_intent:
            sections.append(
                f"USER REQUEST: {user_intent}\n\n"
                f"IMPORTANT: Every chart, KPI, and insight must directly relate to this request."
            )
            sections.append("")

        # ── Existing components for layout redesign ──
        existing_components = metadata.get("_existing_components", None)
        if existing_components:
            sections.append(f"EXISTING COMPONENTS (rearrange these into a better layout):\n{existing_components}")
            sections.append("")

        overview = metadata.get("dataset_overview", {})
        colmeta = metadata.get("column_metadata", [])
        domain_intel = metadata.get("domain_intelligence", {})
        data_profile = metadata.get("data_profile", {})
        deep_analysis = metadata.get("deep_analysis", {})
        statistical_findings = metadata.get("statistical_findings", {})
        if isinstance(statistical_findings, list):
            statistical_findings = {"findings": statistical_findings}
        cardinality = data_profile.get("cardinality", {})

        # --- Section 1: Overview ---
        sections.append(
            f"OVERVIEW: {overview.get('total_rows', 'N/A'):,} rows × "
            f"{overview.get('total_columns', 'N/A')} columns"
        )

        # --- Section 2: Domain Intelligence ---
        if domain_intel and domain_intel.get("domain", "general") != "general":
            domain_parts = [
                f"DOMAIN: {domain_intel['domain']} (confidence: {domain_intel.get('confidence', 0):.0%})"
            ]
            if domain_intel.get("key_metrics"):
                domain_parts.append(f"  Key metrics: {', '.join(domain_intel['key_metrics'][:6])}")
            if domain_intel.get("measures"):
                domain_parts.append(f"  Measures (numeric): {', '.join(domain_intel['measures'][:8])}")
            if domain_intel.get("dimensions"):
                domain_parts.append(f"  Dimensions (categorical): {', '.join(domain_intel['dimensions'][:8])}")
            if domain_intel.get("time_columns"):
                domain_parts.append(f"  Time columns: {', '.join(domain_intel['time_columns'][:4])}")
            sections.append("\n".join(domain_parts))

        # --- Section 3: Columns with cardinality context ---
        def _fmt_num(v):
            if v is None:
                return "?"
            return str(int(v)) if float(v) == int(float(v)) else f"{v:.1f}"

        col_lines = []
        for c in colmeta[:30]:
            col_name = c.get("name", "")
            col_type = c.get("type", "")
            card_info = cardinality.get(col_name, {})
            card_level = card_info.get("cardinality_level", "")
            unique_count = card_info.get("unique_count", c.get("unique_count", ""))

            card_tag = ""
            if card_level == "low":
                card_tag = f" [LOW-CARD: {unique_count} uniques — good for grouping/pie]"
            elif card_level == "very_high":
                card_tag = f" [HIGH-CARD: {unique_count} uniques — skip for charts]"
            elif card_level == "high":
                card_tag = f" [HIGH-CARD: {unique_count} uniques — bad for pie/bar]"
            elif card_level == "medium":
                card_tag = f" [MED-CARD: {unique_count} uniques]"

            num_summary = c.get("numeric_summary", {})
            if num_summary:
                lo = num_summary.get("min")
                hi = num_summary.get("max")
                mean = num_summary.get("mean")
                range_str = f" range={_fmt_num(lo)}–{_fmt_num(hi)}, mean={_fmt_num(mean)}"
                n_uniq = unique_count if isinstance(unique_count, int) else 0
                if n_uniq > 15:
                    range_str += " [CONTINUOUS]"
                col_lines.append(f"  • {col_name} ({col_type}){card_tag}{range_str}")
                continue

            top_values = c.get("top_values", [])
            if top_values and (card_level in ("low", "") or (isinstance(unique_count, int) and unique_count <= 15)):
                vals = [str(v["value"]) for v in top_values[:8]]
                col_lines.append(f"  • {col_name} ({col_type}){card_tag} values: {', '.join(vals)}")
                continue

            col_lines.append(f"  • {col_name} ({col_type}){card_tag}")

        sections.append("COLUMNS:\n" + "\n".join(col_lines))
        if len(colmeta) > 30:
            sections.append(f"  ... +{len(colmeta) - 30} more columns")

        # --- Section 4: SAMPLE DATA ROWS (NEW — this is the highest-impact change) ---
        if sample_data and len(sample_data) > 0:
            sample_rows = sample_data[:8]  # Max 8 rows
            columns_in_sample = list(sample_rows[0].keys()) if sample_rows else []

            # Build a clean table
            table_lines = ["SAMPLE DATA ROWS (actual values — look here to understand patterns):"]
            # Header
            header = " | ".join(str(c)[:30] for c in columns_in_sample[:12])
            table_lines.append(f"  {header}")
            table_lines.append(f"  {'-' * min(len(header), 80)}")
            # Data rows
            for row in sample_rows:
                vals = []
                for c in columns_in_sample[:12]:
                    v = row.get(c, "")
                    v_str = str(v)[:25] if v is not None else ""
                    vals.append(v_str)
                table_lines.append(f"  {' | '.join(vals)}")

            sections.append("\n".join(table_lines))

        # --- Section 5: ID columns to skip ---
        id_cols = data_profile.get("id_columns", [])
        if id_cols:
            sections.append(f"SKIP COLUMNS (IDs): {', '.join(id_cols[:10])}")

        # --- Section 6: Top correlations ---
        enhanced = deep_analysis.get("enhanced_analysis", {})
        correlations = enhanced.get("correlations", [])
        if correlations:
            corr_lines = ["KEY CORRELATIONS (for scatter plots or related KPIs):"]
            for c in correlations[:5]:
                col1 = c.get("column1", "")
                col2 = c.get("column2", "")
                r = c.get("correlation", 0)
                strength = c.get("strength", "")
                corr_lines.append(f"  • {col1} ↔ {col2}: r={r:.3f} ({strength})")
            sections.append("\n".join(corr_lines))

        # --- Section 7: Distribution highlights ---
        distributions = enhanced.get("distributions", [])
        if distributions:
            skewed = [d for d in distributions if d.get("skewness") is not None and abs(d["skewness"]) > 1.5]
            if skewed:
                skew_names = [f"{d.get('column', '')} (skew={d.get('skewness', 0):.1f})" for d in skewed[:5]]
                sections.append(f"SKEWED COLUMNS (use median instead of mean): {', '.join(skew_names)}")

        # --- Section 8: Executive summary ---
        exec_summary = deep_analysis.get("executive_summary", "")
        if exec_summary and isinstance(exec_summary, str) and len(exec_summary) > 20:
            truncated = exec_summary[:300].rsplit(".", 1)[0] + "." if len(exec_summary) > 300 else exec_summary
            sections.append(f"EXECUTIVE SUMMARY: {truncated}")

        return "\n\n".join(sections)

    # ---------------------------------------------------------
    async def get_available_patterns(self) -> Dict[str, Any]:
        return {"patterns": []}


# Singleton instance
ai_designer_service = AIDesignerService()
