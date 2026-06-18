"""
conftest.py — Mock heavy dependencies for test collection.
=========================================================
The services/ai/__init__.py triggers ai_service import chain (→ faiss → langchain → ...).
We mock the problematic modules in sys.modules BEFORE Python processes __init__.py
so that from .ai_service import ai_service resolves to a mock instead of the real module.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Step 1: Mock top-level third-party libraries
_THIRD_PARTY_MOCKS = [
    "faiss",
    "tiktoken",
    "magic",
    "celery",
    "celery.result",
    "langchain_huggingface",
    "langchain",
    "langchain.chains",
    "langchain.memory",
    "langchain.schema",
    "langchain_core",
    "langchain_community",
    "langchain_community.embeddings",
    "langchain_community.vectorstores",
    "huggingface_hub",
    "sentence_transformers",
    "chromadb",
    "chromadb.config",
    "pymongo",
    "motor",
    "motor.motor_asyncio",
    "boto3",
    "botocore",
    "botocore.exceptions",
    "redis",
    "PIL",
    "docx",
    "openpyxl",
    "plotly",
    "plotly.graph_objects",
    "plotly.subplots",
]

for mod_name in _THIRD_PARTY_MOCKS:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Step 2: Mock services.ai.ai_service and ai_designer_service so that
# services/ai/__init__.py can import from them without triggering their
# heavy dependency chains.
# The __init__.py does: from .ai_service import ai_service
#                      from .ai_designer_service import ai_designer_service
# We pre-seed sys.modules so Python uses our mock instead of loading the real file.

_AI_MODULE_MOCKS = {
    "services.ai.ai_service": {"ai_service": MagicMock()},
    "services.ai.ai_designer_service": {"ai_designer_service": MagicMock()},
    # Also mock the services that the ai_service chain would import
    "services.datasets.faiss_vector_service": {},
    "services.datasets.dataset_loader": {},
    "services.datasets.enhanced_dataset_service": {},
    "services.llm.router": {},
    "services.prompts.token_budget": {},
    "services.charts.hydrate": {},
    "services.charts.chart_render_service": {},
    "services.charts.chart_recommender": {},
    "services.cache.dashboard_cache_service": {},
}

for mod_path, attrs in _AI_MODULE_MOCKS.items():
    if mod_path not in sys.modules:
        mock_mod = MagicMock(__name__=mod_path, __file__=f"/mock/{mod_path.replace('.', '/')}.py")
        # Set attributes
        for attr_name, attr_val in attrs.items():
            setattr(mock_mod, attr_name, attr_val)
        sys.modules[mod_path] = mock_mod
