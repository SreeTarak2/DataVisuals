import logging
from pathlib import Path

import s3fs

from core.config import settings

logger = logging.getLogger(__name__)


class S3StorageService:
    """Minimal S3-compatible object storage wrapper (Supabase S3 / any S3).

    Uses ``s3fs.S3FileSystem`` under the hood.  All operations are
    synchronous because ``s3fs`` already handles connection pooling
    and the GIL is released during I/O.

    Path-style addressing is used because Supabase S3 does not
    support virtual-hosted-style buckets.
    """

    def __init__(self) -> None:
        self._fs: s3fs.S3FileSystem | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def fs(self) -> s3fs.S3FileSystem:
        if self._fs is not None:
            return self._fs
        if not settings.SUPABASE_S3_URL:
            raise RuntimeError(
                "SUPABASE_S3_URL is not configured — cannot initialise S3 filesystem"
            )
        self._fs = s3fs.S3FileSystem(
            key=settings.SUPABASE_S3_ACCESS_KEY,
            secret=settings.SUPABASE_S3_SECRET_KEY,
            endpoint_url=settings.SUPABASE_S3_URL,
            client_kwargs={
                "endpoint_url": settings.SUPABASE_S3_URL,
                "region_name": settings.SUPABASE_S3_REGION,
            },
        )
        logger.info("S3FileSystem initialised (endpoint=%s)", settings.SUPABASE_S3_URL)
        return self._fs

    def _s3_path(self, key: str) -> str:
        """Return ``s3://bucket/key`` for a given object key."""
        return f"s3://{settings.SUPABASE_BUCKET_NAME}/{key}"

    def _key_from_s3_path(self, s3_path: str) -> str:
        """Strip ``s3://bucket/`` prefix, returning the object key."""
        prefix = f"s3://{settings.SUPABASE_BUCKET_NAME}/"
        if s3_path.startswith(prefix):
            return s3_path[len(prefix) :]
        return s3_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_file(self, local_path: str | Path, s3_key: str) -> str:
        """Upload *local_path* to S3 at *s3_key*.

        Returns the ``s3://bucket/key`` URL for direct use with Polars.
        """
        s3_path = self._s3_path(s3_key)
        self.fs.put(str(local_path), s3_path)
        logger.info("Uploaded %s -> %s", local_path, s3_path)
        return s3_path

    def download_file(self, s3_key: str, local_path: str | Path) -> str:
        """Download *s3_key* to *local_path*.

        Returns the local path.
        """
        s3_path = self._s3_path(s3_key)
        self.fs.get(s3_path, str(local_path))
        logger.info("Downloaded %s -> %s", s3_path, local_path)
        return str(local_path)

    def delete_file(self, s3_key: str) -> bool:
        """Delete *s3_key* from the bucket.  Returns True on success.

        Uses the single-object ``delete_object`` API (via ``fs.rm_file``)
        rather than the bulk ``DeleteObjects`` endpoint, because Supabase
        S3 does not support the bulk variant.
        """
        s3_path = self._s3_path(s3_key)
        try:
            self.fs.rm_file(s3_path)
            logger.info("Deleted %s", s3_path)
            return True
        except Exception:
            logger.warning("Failed to delete %s", s3_path, exc_info=True)
            return False

    def exists(self, s3_key: str) -> bool:
        """Return True if *s3_key* exists in the bucket."""
        s3_path = self._s3_path(s3_key)
        return self.fs.exists(s3_path)

    def s3_url(self, s3_key: str) -> str:
        """Return the ``s3://bucket/key`` URL for direct Polars reads."""
        return self._s3_path(s3_key)

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all object keys under *prefix*."""
        s3_path = self._s3_path(prefix)
        raw = self.fs.ls(s3_path)
        prefix_strip = f"{settings.SUPABASE_BUCKET_NAME}/"
        keys = []
        for p in raw:
            key = p
            if key.startswith(prefix_strip):
                key = key[len(prefix_strip) :]
            keys.append(key)
        return keys

    def generate_parquet_key(self, user_id: str, file_id: str) -> str:
        """Standard key pattern for processed parquet files."""
        return f"datasets/{user_id}/{file_id}.parquet"


s3_storage = S3StorageService()
