"""
db/migrations/add_router_fields.py

Database migration: Add router fields to conversation_messages table.

New columns:
- router_score: Raw routing score from RouteLLM
- router_confidence: Confidence level (0.0 to 1.0)
- router_reason: Human-readable explanation for routing decision

Run with: python db/migrations/add_router_fields.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from db.engine import init_db, close_db, get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration():
    """Add router fields to conversation_messages table."""
    logger.info("=" * 60)
    logger.info("Database Migration: Add Router Fields")
    logger.info("=" * 60)
    
    await init_db()
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Check if columns already exist
        logger.info("Checking existing schema...")
        result = await conn.execute(text(
            "PRAGMA table_info(conversation_messages)"
        ))
        existing_columns = {row[1] for row in result.fetchall()}
        
        logger.info(f"Found {len(existing_columns)} existing columns")
        
        # Add router_score column if not exists
        if "router_score" not in existing_columns:
            logger.info("Adding column: router_score")
            await conn.execute(text(
                "ALTER TABLE conversation_messages "
                "ADD COLUMN router_score REAL DEFAULT NULL"
            ))
            logger.info("✓ Added router_score")
        else:
            logger.info("✓ router_score already exists")
        
        # Add router_confidence column if not exists
        if "router_confidence" not in existing_columns:
            logger.info("Adding column: router_confidence")
            await conn.execute(text(
                "ALTER TABLE conversation_messages "
                "ADD COLUMN router_confidence REAL DEFAULT NULL"
            ))
            logger.info("✓ Added router_confidence")
        else:
            logger.info("✓ router_confidence already exists")
        
        # Add router_reason column if not exists
        if "router_reason" not in existing_columns:
            logger.info("Adding column: router_reason")
            await conn.execute(text(
                "ALTER TABLE conversation_messages "
                "ADD COLUMN router_reason TEXT DEFAULT NULL"
            ))
            logger.info("✓ Added router_reason")
        else:
            logger.info("✓ router_reason already exists")
        
        await conn.commit()
    
    # Verify migration
    logger.info("\nVerifying migration...")
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "PRAGMA table_info(conversation_messages)"
        ))
        columns = result.fetchall()
        
        router_columns = [col for col in columns if col[1].startswith("router_")]
        logger.info(f"Found {len(router_columns)} router columns:")
        for col in router_columns:
            logger.info(f"  - {col[1]} ({col[2]})")
    
    await close_db()
    
    logger.info("\n✓ Migration complete!")


async def main():
    try:
        await run_migration()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
