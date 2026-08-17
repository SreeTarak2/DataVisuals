import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import patch, MagicMock, AsyncMock
import pytest


class TestQUISCacheServiceIntegration:
    @pytest.mark.asyncio
    async def test_load_dataset_cached_cache_hit(self):
        mock_cache = AsyncMock()
        mock_cache.get_dataframe.return_value = MagicMock()

        with patch("services.cache.cache_service.CacheService", return_value=mock_cache):
            with patch("db.database.get_database") as mock_get_db:
                from agents.quis.quis_graph import _load_dataset_cached

                df = await _load_dataset_cached(dataset_id="d1", user_id="u1", tenant_id="t1")
                assert df is not None
                mock_cache.get_dataframe.assert_called_once_with("quis:df:t1:d1")

    @pytest.mark.asyncio
    async def test_load_dataset_cached_cache_miss_loads_from_db(self):
        mock_cache = AsyncMock()
        mock_cache.get_dataframe.return_value = None

        mock_db = MagicMock()
        mock_db.uploads.find_one = AsyncMock(
            return_value={
                "_id": "d1",
                "user_id": "u1",
                "parquet_path": "/nonexistent/test.parquet",
                "file_path": "/nonexistent/test.csv",
            }
        )

        with patch("services.cache.cache_service.CacheService", return_value=mock_cache):
            with patch("db.database.get_database", return_value=mock_db):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("agents.quis.quis_graph.pl.read_parquet") as mock_read:
                        mock_df = MagicMock()
                        mock_read.return_value = mock_df
                        mock_df.__len__.return_value = 10

                        from agents.quis.quis_graph import _load_dataset_cached

                        df = await _load_dataset_cached(
                            dataset_id="d1", user_id="u1", tenant_id="t1"
                        )
                        assert df is not None
                        mock_cache.set_dataframe.assert_called_once_with("quis:df:t1:d1", mock_df)

    @pytest.mark.asyncio
    async def test_load_dataset_cached_returns_none_for_missing(self):
        mock_cache = AsyncMock()
        mock_cache.get_dataframe.return_value = None

        mock_db = MagicMock()
        mock_db.uploads.find_one = AsyncMock(return_value=None)

        with patch("services.cache.cache_service.CacheService", return_value=mock_cache):
            with patch("db.database.get_database", return_value=mock_db):
                from agents.quis.quis_graph import _load_dataset_cached

                df = await _load_dataset_cached(dataset_id="nonexistent", user_id="u1")
                assert df is None

    @pytest.mark.asyncio
    async def test_load_dataset_cached_samples_large_datasets(self):
        mock_cache = AsyncMock()
        mock_cache.get_dataframe.return_value = None

        mock_db = MagicMock()
        mock_db.uploads.find_one = AsyncMock(
            return_value={
                "_id": "d1",
                "user_id": "u1",
                "parquet_path": "/nonexistent/test.parquet",
                "file_path": "/nonexistent/test.csv",
            }
        )

        with patch("services.cache.cache_service.CacheService", return_value=mock_cache):
            with patch("db.database.get_database", return_value=mock_db):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("agents.quis.quis_graph.pl.read_parquet") as mock_read:
                        mock_df = MagicMock()
                        mock_df.__len__.return_value = 200_000
                        mock_read.return_value = mock_df

                        from agents.quis.quis_graph import _load_dataset_cached

                        df = await _load_dataset_cached(
                            dataset_id="d1", user_id="u1", tenant_id="t1"
                        )
                        assert df is not None
                        mock_df.sample.assert_called_once()
