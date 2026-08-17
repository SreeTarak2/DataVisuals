"""
dlt Service Module
==================

Provides a thin integration layer around the dlt (data load tool) library
for extracting data from SaaS APIs and databases into Parquet files.

Uses the same encryption, audit, and circuit breaker infrastructure as the
rest of the DataSage backend. Outputs Parquet files to the standard
``data/uploads/db_extracts/`` directory so the existing pipeline
(profiling → KPI → dashboard) picks them up automatically.

Architecture:
    API Route → dlt_service.run_sync()
                ├── decrypt credentials (Fernet)
                ├── check circuit breaker
                ├── dlt.pipeline().run(source)
                ├── copy Parquet → db_extracts/
                ├── fire process_dataset()
                ├── audit_service.log_agent_execution()
                └── circuit breaker record_success/failure

Usage:
    from services.dlt import dlt_runner

    result = await dlt_runner.run_sync(
        user_id="...",
        conn_id="...",
        source_type="salesforce",
        credentials={"client_id": "...", ...},
        dataset_name="My Salesforce Data",
    )
"""

from services.dlt.runner import DltRunner, DltRunResult, DltRunError

dlt_runner = DltRunner()

__all__ = [
    "dlt_runner",
    "DltRunner",
    "DltRunResult",
]
