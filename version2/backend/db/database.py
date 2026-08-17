from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os
from pathlib import Path
from typing import Optional
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database = None


# Create database instance
db = Database()


async def connect_to_mongo():
    """Create database connection"""
    try:
        # MongoDB connection string
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = os.getenv("DATABASE_NAME", "signal_ai")

        # Create async client
        db.client = AsyncIOMotorClient(mongo_url)
        db.database = db.client[database_name]

        # Test the connection
        await db.client.admin.command("ping")
        logger.info(f"Connected to MongoDB")
        logger.info(f"Using database: {database_name}")

        # Create indexes for better performance
        await create_indexes()

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e


async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB")


async def create_indexes():
    """
    Create database indexes for better performance and query optimization.

    Index strategy:
    - Single field indexes for unique constraints (email, username)
    - Compound indexes for common query patterns (user_id + is_active, user_id + created_at)
    - Content hash index for duplicate detection
    """
    try:
        # ============================================================
        # Users Collection
        # ============================================================
        await db.database.users.create_index("email", unique=True)
        await db.database.users.create_index("username", unique=True)

        # ============================================================
        # Uploads Collection (renamed from datasets)
        # ============================================================
        await db.database.uploads.create_index("user_id")
        await db.database.uploads.create_index("created_at")
        await db.database.uploads.create_index("filename")

        # COMPOUND: User's active uploads (most common query pattern)
        await db.database.uploads.create_index(
            [("user_id", 1), ("is_active", 1)], name="idx_user_active_uploads"
        )

        # COMPOUND: Duplicate detection (content_hash + user_id)
        await db.database.uploads.create_index(
            [("content_hash", 1), ("user_id", 1)], name="idx_duplicate_detection"
        )

        # COMPOUND: User's uploads sorted by creation (for listing)
        await db.database.uploads.create_index(
            [("user_id", 1), ("created_at", -1)], name="idx_user_uploads_sorted"
        )

        # ============================================================
        # Tenant Scoping Indexes (workspace_id first)
        # ------------------------------------------------------------
        # Every tenant-scoped collection is indexed with workspace_id leading
        # so workspace-isolated reads/writes never degrade to collection scans.
        # See db/tenant_guard.py for the fail-closed enforcement layer.
        # ============================================================
        await db.database.uploads.create_index(
            [("workspace_id", 1), ("is_active", 1)], name="idx_workspace_active_uploads"
        )
        await db.database.uploads.create_index(
            [("workspace_id", 1), ("upload_date", -1)], name="idx_workspace_uploads_sorted"
        )
        await db.database.uploads.create_index(
            [("workspace_id", 1), ("content_hash", 1)], name="idx_workspace_content_hash"
        )
        await db.database.dataset_profiles.create_index(
            [("workspace_id", 1)], name="idx_dataset_profiles_workspace"
        )
        await db.database.dataset_intelligence.create_index(
            [("workspace_id", 1)], name="idx_dataset_intelligence_workspace"
        )
        await db.database.dataset_analytics.create_index(
            [("workspace_id", 1)], name="idx_dataset_analytics_workspace"
        )
        await db.database.pipeline_stages.create_index(
            [("workspace_id", 1)], name="idx_pipeline_stages_workspace"
        )

        # ============================================================
        # Projects Collection (analysis containers — tenant-scoped)
        # ============================================================
        await db.database.projects.create_index(
            [("workspace_id", 1), ("updated_at", -1)],
            name="idx_projects_workspace_recent",
        )
        await db.database.projects.create_index(
            [("workspace_id", 1), ("owner_id", 1)],
            name="idx_projects_workspace_owner",
        )

        # ============================================================
        # Project Sources Collection (bindings — tenant-scoped)
        # ============================================================
        await db.database.project_sources.create_index(
            [("workspace_id", 1), ("project_id", 1)],
            name="idx_project_sources_workspace_project",
        )

        # ============================================================
        # Project Cells Collection (journey — tenant-scoped)
        # ============================================================
        await db.database.project_cells.create_index(
            [("workspace_id", 1), ("project_id", 1), ("order", 1)],
            name="idx_project_cells_workspace_order",
        )

        # ============================================================
        # Semantic Assumptions Collection (ontology state machine)
        # ============================================================
        await db.database.semantic_assumptions.create_index(
            [("workspace_id", 1), ("dataset_id", 1), ("state", 1)],
            name="idx_assumptions_ws_dataset_state",
        )
        await db.database.semantic_assumptions.create_index(
            [("workspace_id", 1), ("dataset_id", 1), ("type", 1)],
            name="idx_assumptions_ws_dataset_type",
        )

        # ============================================================
        # Dataset Analytics Collection (NEW)
        # ============================================================
        await db.database.dataset_analytics.create_index("dataset_id")
        await db.database.dataset_analytics.create_index("user_id")

        # COMPOUND: User's analytics by dataset
        await db.database.dataset_analytics.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_analytics"
        )

        # COMPOUND: Analytics sorted by computation time
        await db.database.dataset_analytics.create_index(
            [("user_id", 1), ("computed_at", -1)], name="idx_user_analytics_computed"
        )

        # ============================================================
        # Reports Collection (NEW)
        # ============================================================
        await db.database.reports.create_index("dataset_id")
        await db.database.reports.create_index("user_id")
        await db.database.reports.create_index("generated_at")

        # COMPOUND: User's reports by dataset
        await db.database.reports.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_reports"
        )

        # COMPOUND: User's reports sorted by generation time
        await db.database.reports.create_index(
            [("user_id", 1), ("generated_at", -1)], name="idx_user_reports_generated"
        )

        # ============================================================
        # Query Log Collection (async execution history)
        # ============================================================
        await db.database.query_log.create_index(
            "ttl_expire_at",
            expireAfterSeconds=0,
            name="idx_query_log_ttl",
        )
        await db.database.query_log.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_user_query_history",
        )
        await db.database.query_log.create_index(
            [("status", 1)], name="idx_query_status"
        )

        # ============================================================
        # DB Relationships Collection (cross-table FK cache)
        # ============================================================
        # ============================================================
        # User Settings Collection (alpha adaptation, preferences)
        # ============================================================
        await db.database.user_settings.create_index(
            "user_id", unique=True, name="idx_user_settings_user"
        )

        # ============================================================
        # DB Relationships Collection (cross-table FK cache)
        # ============================================================
        await db.database.db_relationships.create_index(
            [("connection_id", 1), ("user_id", 1)],
            unique=True,
            name="idx_connection_user_relationship",
        )
        await db.database.db_relationships.create_index("discovered_at")

        # ============================================================
        # Charts Collection
        # ============================================================
        await db.database.charts.create_index("user_id")
        await db.database.charts.create_index("dataset_id")
        await db.database.charts.create_index("created_at")

        # ============================================================
        # Insights Collection
        # ============================================================
        await db.database.insights.create_index("user_id")
        await db.database.insights.create_index("dataset_id")
        await db.database.insights.create_index("created_at")

        # ============================================================
        # Conversations Collection
        # ============================================================
        await db.database.conversations.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_conversations"
        )

        await db.database.conversations.create_index(
            [("user_id", 1), ("updated_at", -1)], name="idx_user_recent_conversations"
        )

        # ============================================================
        # KPI Configs Collection (Financial Services)
        # ============================================================
        await db.database.kpi_configs.create_index(
            [("user_id", 1), ("dataset_id", 1)],
            unique=True,
            name="idx_user_dataset_kpi_config",
        )
        await db.database.kpi_configs.create_index("updated_at")

        # ============================================================
        # Chunks Collection (RAG — TTL for orphaned chunks)
        # ============================================================
        await db.database.chunks.create_index(
            "expire_at",
            expireAfterSeconds=0,
            name="idx_chunks_ttl",
        )
        await db.database.chunks.create_index(
            [("dataset_id", 1)],
            name="idx_chunks_dataset",
        )
        await db.database.chunks.create_index(
            [("chunk_id", 1)],
            unique=True,
            name="idx_chunks_id",
        )

        # ============================================================
        # Workspaces Collection
        # ============================================================
        await db.database.workspaces.create_index("owner_id")
        await db.database.workspaces.create_index("created_at")

        # COMPOUND: Personal workspace lookup (backfill on login)
        await db.database.workspaces.create_index(
            [("owner_id", 1), ("is_personal", 1)],
            name="idx_owner_personal_workspace",
        )

        # ============================================================
        # User API Keys Collection (BYOK)
        # ============================================================
        await db.database.user_api_keys.create_index(
            [("user_id", 1), ("provider", 1)],
            unique=True,
            name="idx_user_api_key_provider",
            partialFilterExpression={"is_active": True},
        )
        await db.database.user_api_keys.create_index(
            [("user_id", 1), ("is_active", 1)],
            name="idx_user_api_keys_active",
        )
        await db.database.user_api_keys.create_index(
            "user_id",
            name="idx_user_api_keys_user",
        )

        # ============================================================
        # Workspace Members Collection
        # ============================================================
        await db.database.workspace_members.create_index(
            [("workspace_id", 1), ("user_id", 1)],
            unique=True,
            name="idx_workspace_user_member",
        )
        await db.database.workspace_members.create_index("user_id")
        await db.database.workspace_members.create_index("workspace_id")

        # ============================================================
        # User Notifications Collection (job notifications inbox)
        # ============================================================
        # Tenant-scoped inbox: workspace_id leads so workspace-isolated
        # reads never degrade to collection scans (see tenant_guard.py).
        await db.database.user_notifications.create_index(
            [("workspace_id", 1), ("user_id", 1), ("created_at", -1)],
            name="idx_notifications_ws_user_recent",
        )
        # Unread badge queries: workspace + user + read flag
        await db.database.user_notifications.create_index(
            [("workspace_id", 1), ("user_id", 1), ("read", 1)],
            name="idx_notifications_ws_user_read",
        )

        # ============================================================
        # Sessions Collection (per-device auth, refresh-token rotation)
        # ============================================================
        # Active sessions per user (device list in Settings), newest first
        await db.database.sessions.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_sessions_user_recent",
        )
        # Refresh-token lookup must be unique — one token = one session
        await db.database.sessions.create_index(
            "refresh_token_hash",
            unique=True,
            name="idx_sessions_refresh_hash",
        )
        # Expired sessions are auto-purged by MongoDB TTL
        await db.database.sessions.create_index(
            "expires_at",
            expireAfterSeconds=0,
            name="idx_sessions_ttl",
        )

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")


def get_database():
    """Get database instance with safety check"""
    if db.database is None:
        logger.error("Database accessed before connect_to_mongo() was called.")
        raise ConnectionError(
            "Database not initialized. Ensure connect_to_mongo() was awaited at worker startup."
        )
    return db.database


def get_collection(name: str):
    """Get a collection by name"""
    return get_database()[name]
