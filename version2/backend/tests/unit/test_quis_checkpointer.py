import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import patch, MagicMock
import pytest


class TestQUISCheckpointer:
    def test_compile_uses_memory_saver_when_no_db_uri(self):
        import agents.quis.quis_graph as qg

        qg._CHECKPOINT_DB_URI = None
        qg._PERSISTENT_CHECKPOINT = False

        with patch("agents.quis.quis_graph.MemorySaver") as mock_memory:
            with patch("agents.quis.quis_graph.StateGraph") as mock_graph:
                mock_instance = MagicMock()
                mock_graph.return_value = mock_instance
                mock_instance.compile.return_value = MagicMock()

                from agents.quis.quis_graph import create_quis_graph

                create_quis_graph()
                mock_instance.compile.assert_called_once()
                call_kwargs = mock_instance.compile.call_args[1]
                assert "checkpointer" in call_kwargs

    def test_memory_saver_import_works(self):
        from langgraph.checkpoint.memory import MemorySaver

        saver = MemorySaver()
        assert saver is not None

    def test_persistent_checkpoint_flag_parses_env(self):
        original = os.environ.pop("POSTGRES_CHECKPOINT_URL", None)
        os.environ["POSTGRES_CHECKPOINT_URL"] = "postgresql://user:pass@host/db"
        try:
            import importlib
            import agents.quis.quis_graph as qg

            importlib.reload(qg)
            assert qg._PERSISTENT_CHECKPOINT is True
            assert "postgresql" in qg._CHECKPOINT_DB_URI
        finally:
            if original:
                os.environ["POSTGRES_CHECKPOINT_URL"] = original
            else:
                os.environ.pop("POSTGRES_CHECKPOINT_URL", None)

    def test_persistent_checkpoint_false_without_env(self):
        os.environ.pop("POSTGRES_CHECKPOINT_URL", None)
        os.environ.pop("DATABASE_URL", None)
        import importlib
        import agents.quis.quis_graph as qg

        importlib.reload(qg)
        assert qg._PERSISTENT_CHECKPOINT is False
