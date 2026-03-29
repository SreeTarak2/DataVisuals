"""
Privacy Settings Service
=======================
Manages user privacy settings with support for both global defaults
and per-dataset overrides.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class DataRetentionPeriod(Enum):
    """Available data retention periods."""

    THIRTY_DAYS = 30
    SIXTY_DAYS = 60
    NINETY_DAYS = 90
    ONE_YEAR = 365
    FOREVER = -1


@dataclass
class GlobalPrivacySettings:
    """Global privacy settings for a user."""

    pii_auto_detect: bool = True
    pii_auto_redact: bool = True
    share_column_names: bool = True
    share_sample_rows: bool = True
    max_sample_rows: int = 10
    data_retention_days: int = 90
    show_dry_run_first_time: bool = True
    send_retention_warnings: bool = True
    retention_warning_days: int = 7


@dataclass
class DatasetPrivacySettings:
    """Per-dataset privacy settings override."""

    pii_auto_redact: Optional[bool] = None  # None = use global
    private_columns: List[str] = field(default_factory=list)
    share_column_names: Optional[bool] = None  # None = use global
    share_sample_rows: Optional[bool] = None  # None = use global
    max_sample_rows: Optional[int] = None  # None = use global
    dry_run_completed: bool = False  # Track if dry-run was shown
    last_scanned_at: Optional[str] = None  # ISO timestamp of last PII scan


@dataclass
class UserPrivacySettings:
    """Complete privacy settings for a user."""

    user_id: str
    global_defaults: GlobalPrivacySettings = field(
        default_factory=GlobalPrivacySettings
    )
    dataset_overrides: Dict[str, DatasetPrivacySettings] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        return {
            "user_id": self.user_id,
            "global_defaults": asdict(self.global_defaults),
            "dataset_overrides": {
                k: asdict(v) for k, v in self.dataset_overrides.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPrivacySettings":
        """Create from MongoDB document."""
        if not data:
            return None

        global_defaults = GlobalPrivacySettings(**data.get("global_defaults", {}))
        dataset_overrides = {
            k: DatasetPrivacySettings(**v)
            for k, v in data.get("dataset_overrides", {}).items()
        }

        return cls(
            user_id=data.get("user_id", ""),
            global_defaults=global_defaults,
            dataset_overrides=dataset_overrides,
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )


class PrivacySettingsService:
    """
    Service for managing user privacy settings.

    Supports:
    - Global default settings
    - Per-dataset overrides
    - Settings inheritance
    - GDPR data export
    """

    COLLECTION_NAME = "privacy_settings"

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        """Lazy database initialization."""
        if self._db is None:
            from db.database import get_database

            self._db = get_database()
        return self._db

    async def get_user_settings(self, user_id: str) -> UserPrivacySettings:
        """
        Get privacy settings for a user.

        Creates default settings if not exists.
        """
        doc = await self.db[self.COLLECTION_NAME].find_one({"user_id": user_id})

        if not doc:
            # Create default settings
            settings = UserPrivacySettings(user_id=user_id)
            await self.save_user_settings(settings)
            return settings

        return UserPrivacySettings.from_dict(doc)

    async def save_user_settings(self, settings: UserPrivacySettings) -> bool:
        """
        Save privacy settings for a user.

        Returns True on success.
        """
        try:
            settings.updated_at = datetime.utcnow().isoformat()
            await self.db[self.COLLECTION_NAME].update_one(
                {"user_id": settings.user_id}, {"$set": settings.to_dict()}, upsert=True
            )
            logger.info(f"Privacy settings saved for user {settings.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save privacy settings: {e}")
            return False

    async def update_global_settings(
        self, user_id: str, updates: Dict[str, Any]
    ) -> UserPrivacySettings:
        """
        Update global privacy settings.

        Args:
            user_id: User identifier
            updates: Dictionary of settings to update

        Returns:
            Updated UserPrivacySettings
        """
        settings = await self.get_user_settings(user_id)

        # Apply updates to global defaults
        for key, value in updates.items():
            if hasattr(settings.global_defaults, key):
                setattr(settings.global_defaults, key, value)

        await self.save_user_settings(settings)
        return settings

    async def get_dataset_settings(
        self, user_id: str, dataset_id: str
    ) -> DatasetPrivacySettings:
        """
        Get privacy settings for a specific dataset.

        Returns merged settings (dataset override + global defaults).
        """
        settings = await self.get_user_settings(user_id)

        # Get dataset override or create new
        dataset_override = settings.dataset_overrides.get(dataset_id)
        if not dataset_override:
            dataset_override = DatasetPrivacySettings()

        return dataset_override

    async def get_effective_settings(
        self, user_id: str, dataset_id: str
    ) -> Dict[str, Any]:
        """
        Get effective privacy settings for a dataset.

        Merges global defaults with dataset-specific overrides.
        Returns a flat dictionary of effective settings.
        """
        global_settings = await self.get_user_settings(user_id)
        dataset_override = await self.get_dataset_settings(user_id, dataset_id)

        effective = {
            # PII settings
            "pii_auto_detect": global_settings.global_defaults.pii_auto_detect,
            "pii_auto_redact": (
                dataset_override.pii_auto_redact
                if dataset_override.pii_auto_redact is not None
                else global_settings.global_defaults.pii_auto_redact
            ),
            # Column sharing settings
            "share_column_names": (
                dataset_override.share_column_names
                if dataset_override.share_column_names is not None
                else global_settings.global_defaults.share_column_names
            ),
            "share_sample_rows": (
                dataset_override.share_sample_rows
                if dataset_override.share_sample_rows is not None
                else global_settings.global_defaults.share_sample_rows
            ),
            "max_sample_rows": (
                dataset_override.max_sample_rows
                if dataset_override.max_sample_rows is not None
                else global_settings.global_defaults.max_sample_rows
            ),
            # Private columns (only from dataset override)
            "private_columns": dataset_override.private_columns,
            # Data retention
            "data_retention_days": global_settings.global_defaults.data_retention_days,
            "show_dry_run_first_time": global_settings.global_defaults.show_dry_run_first_time,
            "dry_run_completed": dataset_override.dry_run_completed,
            # Settings sources (for UI display)
            "_setting_sources": {
                "pii_auto_redact": "dataset"
                if dataset_override.pii_auto_redact is not None
                else "global",
                "share_column_names": "dataset"
                if dataset_override.share_column_names is not None
                else "global",
                "share_sample_rows": "dataset"
                if dataset_override.share_sample_rows is not None
                else "global",
                "max_sample_rows": "dataset"
                if dataset_override.max_sample_rows is not None
                else "global",
            },
        }

        return effective

    async def update_dataset_settings(
        self, user_id: str, dataset_id: str, updates: Dict[str, Any]
    ) -> DatasetPrivacySettings:
        """
        Update privacy settings for a specific dataset.

        Args:
            user_id: User identifier
            dataset_id: Dataset identifier
            updates: Dictionary of settings to update

        Returns:
            Updated DatasetPrivacySettings
        """
        settings = await self.get_user_settings(user_id)

        # Get or create dataset override
        if dataset_id not in settings.dataset_overrides:
            settings.dataset_overrides[dataset_id] = DatasetPrivacySettings()

        dataset_override = settings.dataset_overrides[dataset_id]

        # Apply updates
        for key, value in updates.items():
            if hasattr(dataset_override, key):
                setattr(dataset_override, key, value)

        await self.save_user_settings(settings)

        logger.info(
            f"Dataset privacy settings updated for user {user_id}, dataset {dataset_id}"
        )
        return dataset_override

    async def add_private_column(
        self, user_id: str, dataset_id: str, column_name: str
    ) -> bool:
        """Add a column to the private columns list."""
        settings = await self.get_user_settings(user_id)

        if dataset_id not in settings.dataset_overrides:
            settings.dataset_overrides[dataset_id] = DatasetPrivacySettings()

        if column_name not in settings.dataset_overrides[dataset_id].private_columns:
            settings.dataset_overrides[dataset_id].private_columns.append(column_name)
            await self.save_user_settings(settings)
            logger.info(
                f"Column '{column_name}' marked private for dataset {dataset_id}"
            )
            return True

        return False

    async def remove_private_column(
        self, user_id: str, dataset_id: str, column_name: str
    ) -> bool:
        """Remove a column from the private columns list."""
        settings = await self.get_user_settings(user_id)

        if dataset_id in settings.dataset_overrides:
            if column_name in settings.dataset_overrides[dataset_id].private_columns:
                settings.dataset_overrides[dataset_id].private_columns.remove(
                    column_name
                )
                await self.save_user_settings(settings)
                logger.info(
                    f"Column '{column_name}' removed from private for dataset {dataset_id}"
                )
                return True

        return False

    async def mark_dry_run_completed(self, user_id: str, dataset_id: str) -> bool:
        """Mark that dry-run preview was shown for a dataset."""
        settings = await self.get_user_settings(user_id)

        if dataset_id not in settings.dataset_overrides:
            settings.dataset_overrides[dataset_id] = DatasetPrivacySettings()

        settings.dataset_overrides[dataset_id].dry_run_completed = True
        await self.save_user_settings(settings)
        return True

    async def get_all_datasets_with_overrides(
        self, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get all datasets that have privacy overrides."""
        settings = await self.get_user_settings(user_id)

        datasets_with_overrides = []
        for dataset_id, override in settings.dataset_overrides.items():
            datasets_with_overrides.append(
                {"dataset_id": dataset_id, "settings": asdict(override)}
            )

        return datasets_with_overrides

    async def delete_dataset_override(self, user_id: str, dataset_id: str) -> bool:
        """Delete privacy override for a dataset (revert to global)."""
        settings = await self.get_user_settings(user_id)

        if dataset_id in settings.dataset_overrides:
            del settings.dataset_overrides[dataset_id]
            await self.save_user_settings(settings)
            logger.info(f"Privacy override deleted for dataset {dataset_id}")
            return True

        return False

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all privacy-related data for a user (GDPR compliance).

        Returns:
            Dictionary with all privacy settings data
        """
        settings = await self.get_user_settings(user_id)

        return {
            "export_date": datetime.utcnow().isoformat(),
            "privacy_settings": settings.to_dict(),
            "note": "This export includes your privacy preferences. "
            "For full GDPR data export, also request your datasets and audit logs.",
        }

    async def delete_user_data(self, user_id: str) -> bool:
        """
        Delete all privacy settings for a user (GDPR - right to be forgotten).

        Returns:
            True on success
        """
        try:
            result = await self.db[self.COLLECTION_NAME].delete_one(
                {"user_id": user_id}
            )
            logger.info(f"Deleted privacy settings for user {user_id}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete privacy settings: {e}")
            return False


# Singleton instance
privacy_settings_service = PrivacySettingsService()
