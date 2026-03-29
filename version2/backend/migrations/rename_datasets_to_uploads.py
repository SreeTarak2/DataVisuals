"""
Migration Script: Rename datasets to uploads and create analytics collection
=========================================================================

This migration:
1. Renames the 'datasets' collection to 'uploads'
2. Extracts analytical data from metadata into a new 'dataset_analytics' collection
3. Creates indexes for the new collections

Run this script BEFORE starting the application with the new code.
The script will backup your data before making changes.

Usage:
    python -m migrations.rename_datasets_to_uploads

Author: DataSage AI Team
Version: 1.0
"""

import sys
import os
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_mongo_client():
    """Get MongoDB client."""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "datasage_ai")

    client = MongoClient(mongo_url)
    db = client[database_name]
    return client, db, database_name


def create_indexes(db):
    """Create indexes for the uploads and dataset_analytics collections."""
    logger.info("Creating indexes...")

    # Uploads collection indexes
    db.uploads.create_index("user_id")
    db.uploads.create_index("created_at")
    db.uploads.create_index("filename")
    db.uploads.create_index(
        [("user_id", 1), ("is_active", 1)], name="idx_user_active_uploads"
    )
    db.uploads.create_index(
        [("content_hash", 1), ("user_id", 1)], name="idx_duplicate_detection"
    )
    db.uploads.create_index(
        [("user_id", 1), ("created_at", -1)], name="idx_user_uploads_sorted"
    )

    # Dataset analytics indexes
    db.dataset_analytics.create_index("dataset_id")
    db.dataset_analytics.create_index("user_id")
    db.dataset_analytics.create_index(
        [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_analytics"
    )
    db.dataset_analytics.create_index(
        [("user_id", 1), ("computed_at", -1)], name="idx_user_analytics_computed"
    )

    # Reports collection indexes
    db.reports.create_index("dataset_id")
    db.reports.create_index("user_id")
    db.reports.create_index("generated_at")
    db.reports.create_index(
        [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_reports"
    )
    db.reports.create_index(
        [("user_id", 1), ("generated_at", -1)], name="idx_user_reports_generated"
    )

    logger.info("Indexes created successfully")


def migrate_analytics_to_separate_collection(db):
    """
    Extract analytical data from datasets.metadata into a new dataset_analytics collection.

    This preserves backward compatibility - datasets.metadata still contains analytics,
    but new processing will write to the separate collection.
    """
    logger.info("Migrating analytics data to dataset_analytics collection...")

    migrated_count = 0
    skipped_count = 0

    # Get all datasets with metadata
    cursor = db.datasets.find(
        {
            "metadata": {"$exists": True},
            "$or": [
                {"metadata.chart_recommendations": {"$exists": True, "$ne": []}},
                {"metadata.statistical_findings": {"$exists": True, "$ne": []}},
                {"metadata.deep_analysis": {"$exists": True}},
                {"metadata.data_profile": {"$exists": True}},
                {"metadata.domain_intelligence": {"$exists": True}},
                {"metadata.data_quality": {"$exists": True}},
            ],
        }
    )

    for dataset in cursor:
        dataset_id = str(dataset["_id"])
        user_id = dataset.get("user_id", "unknown")
        metadata = dataset.get("metadata", {})

        # Check if analytics already exist for this dataset
        existing = db.dataset_analytics.find_one({"dataset_id": dataset_id})
        if existing:
            skipped_count += 1
            continue

        # Create analytics document
        analytics_doc = {
            "dataset_id": dataset_id,
            "user_id": user_id,
            "chart_recommendations": metadata.get("chart_recommendations", []),
            "statistical_findings": metadata.get("statistical_findings", []),
            "deep_analysis": metadata.get("deep_analysis", {}),
            "data_profile": metadata.get("data_profile", {}),
            "domain_intelligence": metadata.get("domain_intelligence", {}),
            "data_quality": metadata.get("data_quality", {}),
            "computed_at": metadata.get("processing_info", {}).get(
                "processed_at", datetime.utcnow()
            ),
            "updated_at": datetime.utcnow(),
            "pipeline_version": metadata.get("processing_info", {}).get(
                "pipeline_version", "2.0"
            ),
            "migrated_from": "datasets.metadata",
            "migrated_at": datetime.utcnow(),
        }

        db.dataset_analytics.insert_one(analytics_doc)
        migrated_count += 1

    logger.info(
        f"Migration complete: {migrated_count} datasets migrated, {skipped_count} skipped (already have analytics)"
    )


def rename_datasets_to_uploads(db):
    """Rename datasets collection to uploads."""
    logger.info("Renaming 'datasets' collection to 'uploads'...")

    # Check if uploads collection already exists
    if "uploads" in db.list_collection_names():
        logger.warning("'uploads' collection already exists. Skipping rename.")
        return False

    # Check if datasets collection exists
    if "datasets" not in db.list_collection_names():
        logger.error("'datasets' collection not found. Nothing to rename.")
        return False

    # Rename the collection
    db.datasets.rename("uploads")
    logger.info("Successfully renamed 'datasets' to 'uploads'")
    return True


def backup_collection(db, collection_name):
    """Create a backup of a collection."""
    backup_name = (
        f"{collection_name}_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    )

    # Copy all documents to backup collection
    backup_docs = list(db[collection_name].find({}))
    if backup_docs:
        db[backup_name].insert_many(backup_docs)
        logger.info(f"Backed up {len(backup_docs)} documents to '{backup_name}'")
    else:
        logger.info(f"No documents to backup in '{collection_name}'")

    return backup_name


def run_migration(dry_run=False):
    """
    Run the full migration.

    Args:
        dry_run: If True, only show what would be done without making changes
    """
    logger.info("=" * 60)
    logger.info("DATASET MIGRATION: datasets -> uploads + dataset_analytics")
    logger.info("=" * 60)

    if dry_run:
        logger.warning("DRY RUN MODE - No changes will be made")

    try:
        client, db, db_name = get_mongo_client()
        logger.info(f"Connected to database: {db_name}")

        # Check current state
        collections = db.list_collection_names()
        logger.info(f"Current collections: {collections}")

        # Step 1: Backup datasets collection
        if "datasets" in collections and not dry_run:
            backup_name = backup_collection(db, "datasets")
            logger.info(f"Backup created: {backup_name}")

        # Step 2: Create indexes (for both uploads and new collections)
        if not dry_run:
            create_indexes(db)

        # Step 3: Migrate analytics to separate collection
        if "datasets" in collections:
            if not dry_run:
                migrate_analytics_to_separate_collection(db)

        # Step 4: Rename datasets to uploads
        if not dry_run:
            rename_datasets_to_uploads(db)

        # Verify final state
        final_collections = db.list_collection_names()
        logger.info(f"Final collections: {final_collections}")

        # Verify analytics collection
        analytics_count = db.dataset_analytics.count_documents({})
        logger.info(f"Documents in dataset_analytics: {analytics_count}")

        # Verify uploads collection
        uploads_count = db.uploads.count_documents({})
        logger.info(f"Documents in uploads: {uploads_count}")

        client.close()

        logger.info("=" * 60)
        logger.info("MIGRATION COMPLETE!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def rollback():
    """Rollback the migration."""
    logger.info("=" * 60)
    logger.info("ROLLBACK: Restoring 'uploads' to 'datasets'")
    logger.info("=" * 60)

    try:
        client, db, db_name = get_mongo_client()

        # Check if uploads exists
        if "uploads" not in db.list_collection_names():
            logger.error("'uploads' collection not found. Nothing to rollback.")
            return False

        # Rename back
        db.uploads.rename("datasets")
        logger.info("Successfully renamed 'uploads' back to 'datasets'")

        # Drop dataset_analytics if it was created
        if "dataset_analytics" in db.list_collection_names():
            db.dataset_analytics.drop()
            logger.info("Dropped 'dataset_analytics' collection")

        client.close()
        return True

    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate datasets to uploads collection"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback the migration"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if args.rollback:
        rollback()
    elif args.dry_run:
        run_migration(dry_run=True)
    else:
        if args.yes:
            run_migration(dry_run=False)
        else:
            confirm = input(
                "This migration will rename 'datasets' to 'uploads'. Continue? (yes/no): "
            )
            if confirm.lower() == "yes":
                run_migration(dry_run=False)
            else:
                logger.info("Migration cancelled")
