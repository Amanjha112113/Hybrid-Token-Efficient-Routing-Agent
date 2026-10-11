"""
db/migrations.py

Database migration and initialization utilities.

Run this script to create/update database tables when models change.
For production, use Alembic for proper migration management.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import text

from db.engine import get_engine, init_db
from db.models import Base, Conversation, ConversationMessage, RequestLog

logger = logging.getLogger(__name__)


async def create_tables():
    """
    Create all tables defined in models.py.
    This is safe to run multiple times (idempotent).
    """
    logger.info("Creating database tables...")
    
    engine = get_engine()
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Database tables created successfully")
    logger.info(f"   - conversations")
    logger.info(f"   - conversation_messages")
    logger.info(f"   - request_logs")


async def drop_tables():
    """
    Drop all tables. USE WITH CAUTION - deletes all data!
    """
    logger.warning("⚠️  Dropping all database tables...")
    
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("✅ All tables dropped")


async def reset_database():
    """
    Drop and recreate all tables (clean slate).
    """
    await drop_tables()
    await create_tables()


async def check_tables():
    """
    Check if required tables exist.
    """
    logger.info("Checking database schema...")
    
    engine = get_engine()
    async with engine.connect() as conn:
        # SQLite table check
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = [row[0] for row in result]
    
    logger.info(f"Found {len(tables)} tables:")
    for table in sorted(tables):
        logger.info(f"  - {table}")
    
    required_tables = {"conversations", "conversation_messages", "request_logs"}
    missing = required_tables - set(tables)
    
    if missing:
        logger.warning(f"⚠️  Missing tables: {missing}")
        logger.info("Run with --create to initialize the database")
        return False
    else:
        logger.info("✅ All required tables present")
        return True


async def add_sample_conversation():
    """
    Add a sample conversation for testing the UI.
    """
    from db.engine import get_db_session
    from datetime import datetime, timezone
    
    logger.info("Creating sample conversation...")
    
    async with get_db_session() as session:
        # Create conversation
        conv = Conversation(
            user_id="anonymous",
            title="Getting Started with the Router",
            total_messages=4,
            total_tokens_used=150,
            total_cost_usd=0.0003,
            model_preference="auto",
            status="active",
        )
        session.add(conv)
        await session.flush()  # Get the ID
        
        # Add messages
        messages = [
            ConversationMessage(
                conversation_id=conv.id,
                role="user",
                content="How does the hybrid router work?",
                backend=None,
                created_at=datetime.now(timezone.utc),
            ),
            ConversationMessage(
                conversation_id=conv.id,
                role="assistant",
                content="The hybrid router intelligently routes queries between a local on-device model (Ollama Qwen 2.5 3B) and remote cloud models (Fireworks AI). It classifies each query's complexity and sends simple tasks to the local model at zero cost, while escalating complex tasks to powerful cloud models only when necessary.",
                backend="local",
                model_used="qwen2.5:3b",
                complexity="standard",
                route_reason="Standard conversational query - resolved locally",
                tokens_used=0,
                tokens_saved=120,
                cost_usd=0.0,
                savings_usd=0.000024,
                latency_ms=450,
                created_at=datetime.now(timezone.utc),
            ),
            ConversationMessage(
                conversation_id=conv.id,
                role="user",
                content="What's the token savings rate?",
                backend=None,
                created_at=datetime.now(timezone.utc),
            ),
            ConversationMessage(
                conversation_id=conv.id,
                role="assistant",
                content="The system typically achieves 67-78% token savings by routing simple queries locally. For example, sentiment analysis, named entity recognition, and basic Q&A are handled on-device at $0 cost, while only complex code generation or mathematical reasoning tasks escalate to the cloud API.",
                backend="local",
                model_used="qwen2.5:3b",
                complexity="standard",
                route_reason="Factual follow-up question - local capable",
                tokens_used=0,
                tokens_saved=95,
                cost_usd=0.0,
                savings_usd=0.000019,
                latency_ms=380,
                created_at=datetime.now(timezone.utc),
            ),
        ]
        
        for msg in messages:
            session.add(msg)
        
        await session.commit()
    
    logger.info("✅ Sample conversation created")


async def main():
    """
    CLI entry point for database operations.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration utilities")
    parser.add_argument(
        "action",
        choices=["check", "create", "reset", "sample"],
        help="Action to perform: check=verify schema, create=create tables, reset=drop+create, sample=add test data",
    )
    
    args = parser.parse_args()
    
    # Initialize database connection
    await init_db()
    
    try:
        if args.action == "check":
            await check_tables()
        elif args.action == "create":
            await create_tables()
        elif args.action == "reset":
            confirm = input("⚠️  This will DELETE all data. Type 'yes' to confirm: ")
            if confirm.lower() == "yes":
                await reset_database()
            else:
                logger.info("Reset cancelled")
        elif args.action == "sample":
            await add_sample_conversation()
    finally:
        # Clean up engine
        from db.engine import close_db
        await close_db()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
