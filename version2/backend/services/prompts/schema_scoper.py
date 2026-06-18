# TODO: REMOVE after Phase 9 — re-export shim
from prompts.schema_scoper import (  # noqa: F401
    scope_schema_to_query, extract_column_names_from_schema,
    extract_column_metadata, estimate_schema_tokens,
)
