"""
db/conversations.py

CRUD operations for conversations and messages.
All functions are async and use SQLAlchemy 2.0+ async API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation, ConversationMessage

logger = logging.getLogger(__name__)


# ── Conversation CRUD ─────────────────────────────────────────────────────────


async def create_conversation(
    session: AsyncSession,
    user_id: str = "anonymous",
    title: str = "New Conversation",
    model_preference: str = "auto",
) -> Conversation:
    """
    Create a new conversation.
    
    Args:
        session: Database session
        user_id: User identifier (default: "anonymous")
        title: Conversation title
        model_preference: Routing preference ("auto" | "local" | "remote-efficient" | "remote-power")
    
    Returns:
        Newly created Conversation object
    """
    conv = Conversation(
        user_id=user_id,
        title=title,
        model_preference=model_preference,
        status="active",
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    
    logger.info(f"Created conversation {conv.id[:8]} for user {user_id}")
    return conv


async def get_conversation(
    session: AsyncSession,
    conversation_id: str,
) -> Optional[Conversation]:
    """
    Retrieve a conversation by ID.
    
    Returns:
        Conversation object or None if not found
    """
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return result.scalar_one_or_none()


async def list_conversations(
    session: AsyncSession,
    user_id: str = "anonymous",
    status: str = "active",
    limit: int = 100,
    offset: int = 0,
) -> list[Conversation]:
    """
    List conversations for a user, ordered by most recent activity.
    
    Args:
        session: Database session
        user_id: Filter by user
        status: Filter by status ("active" | "archived" | "deleted")
        limit: Max results to return
        offset: Pagination offset
    
    Returns:
        List of Conversation objects
    """
    query = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.status == status)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_conversation(
    session: AsyncSession,
    conversation_id: str,
    **kwargs,
) -> Optional[Conversation]:
    """
    Update conversation fields.
    
    Args:
        session: Database session
        conversation_id: Conversation ID
        **kwargs: Fields to update (title, model_preference, status, etc.)
    
    Returns:
        Updated Conversation or None if not found
    """
    conv = await get_conversation(session, conversation_id)
    if not conv:
        return None
    
    for key, value in kwargs.items():
        if hasattr(conv, key):
            setattr(conv, key, value)
    
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conv)
    
    logger.info(f"Updated conversation {conversation_id[:8]}: {kwargs}")
    return conv


async def delete_conversation(
    session: AsyncSession,
    conversation_id: str,
    soft_delete: bool = True,
) -> bool:
    """
    Delete a conversation (soft delete by default).
    
    Args:
        session: Database session
        conversation_id: Conversation ID
        soft_delete: If True, mark as deleted; if False, hard delete from DB
    
    Returns:
        True if deleted, False if not found
    """
    conv = await get_conversation(session, conversation_id)
    if not conv:
        return False
    
    if soft_delete:
        conv.status = "deleted"
        conv.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(f"Soft-deleted conversation {conversation_id[:8]}")
    else:
        await session.delete(conv)
        await session.commit()
        logger.info(f"Hard-deleted conversation {conversation_id[:8]}")
    
    return True


async def search_conversations(
    session: AsyncSession,
    user_id: str,
    query: str,
    limit: int = 20,
) -> list[Conversation]:
    """
    Search conversations by title (case-insensitive).
    
    Args:
        session: Database session
        user_id: User ID to filter
        query: Search string
        limit: Max results
    
    Returns:
        List of matching Conversation objects
    """
    search_pattern = f"%{query}%"
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.status == "active")
        .where(Conversation.title.ilike(search_pattern))
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Message CRUD ──────────────────────────────────────────────────────────────


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    backend: Optional[str] = None,
    model_used: Optional[str] = None,
    complexity: Optional[str] = None,
    route_reason: Optional[str] = None,
    tokens_used: int = 0,
    tokens_saved: int = 0,
    cost_usd: float = 0.0,
    savings_usd: float = 0.0,
    latency_ms: int = 0,
    quality_score: Optional[float] = None,
    quality_passed: Optional[bool] = None,
    router_score: Optional[float] = None,
    router_confidence: Optional[float] = None,
    router_reason: Optional[str] = None,
) -> ConversationMessage:
    """
    Add a message to a conversation and update conversation stats.
    
    Args:
        session: Database session
        conversation_id: Parent conversation ID
        role: Message role ("user" | "assistant" | "system")
        content: Message text
        backend: Routing backend ("local" | "fireworks" | None)
        model_used: Model name
        complexity: Complexity level ("low" | "standard" | "high")
        route_reason: Explanation for routing decision
        tokens_used: Tokens consumed (for remote)
        tokens_saved: Tokens saved (for local)
        cost_usd: USD cost
        savings_usd: USD saved
        latency_ms: Response latency
        quality_score: Quality validation score (0.0-1.0) [LEGACY]
        quality_passed: Whether quality check passed [LEGACY]
        router_score: RouteLLM raw routing score
        router_confidence: Router confidence level (0.0-1.0)
        router_reason: Human-readable routing explanation
    
    Returns:
        Newly created ConversationMessage
    """
    msg = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        backend=backend,
        model_used=model_used,
        complexity=complexity,
        route_reason=route_reason,
        tokens_used=tokens_used,
        tokens_saved=tokens_saved,
        cost_usd=cost_usd,
        savings_usd=savings_usd,
        latency_ms=latency_ms,
        quality_score=quality_score,
        quality_passed=quality_passed,
        router_score=router_score,
        router_confidence=router_confidence,
        router_reason=router_reason,
    )
    session.add(msg)
    
    # Update conversation stats
    conv = await get_conversation(session, conversation_id)
    if conv:
        conv.total_messages += 1
        conv.total_tokens_used += tokens_used
        conv.total_cost_usd += cost_usd
        conv.updated_at = datetime.now(timezone.utc)
        
        # Auto-generate title from first user message
        if conv.total_messages == 1 and role == "user":
            # Use first 60 chars of user message as title
            conv.title = content[:60] + ("..." if len(content) > 60 else "")
    
    await session.commit()
    await session.refresh(msg)
    
    logger.debug(f"Added {role} message to conversation {conversation_id[:8]}")
    return msg


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: str,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[ConversationMessage]:
    """
    Retrieve messages for a conversation, ordered chronologically.
    
    Args:
        session: Database session
        conversation_id: Conversation ID
        limit: Max messages to return (None = all)
        offset: Pagination offset
    
    Returns:
        List of ConversationMessage objects
    """
    query = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
        .offset(offset)
    )
    
    if limit is not None:
        query = query.limit(limit)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_conversation_history_for_llm(
    session: AsyncSession,
    conversation_id: str,
    max_messages: Optional[int] = None,
) -> list[dict[str, str]]:
    """
    Retrieve conversation history in OpenAI message format for LLM API calls.
    
    Args:
        session: Database session
        conversation_id: Conversation ID
        max_messages: Limit to most recent N messages (for context window management)
    
    Returns:
        List of dicts: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    """
    messages = await get_conversation_messages(session, conversation_id)
    
    # Apply limit (keep most recent)
    if max_messages is not None and len(messages) > max_messages:
        messages = messages[-max_messages:]
    
    # Convert to LLM format
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


async def delete_message(
    session: AsyncSession,
    message_id: str,
) -> bool:
    """
    Delete a message from a conversation.
    
    Args:
        session: Database session
        message_id: Message ID
    
    Returns:
        True if deleted, False if not found
    """
    result = await session.execute(
        select(ConversationMessage).where(ConversationMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()
    
    if not msg:
        return False
    
    # Update conversation stats
    conv = await get_conversation(session, msg.conversation_id)
    if conv:
        conv.total_messages = max(0, conv.total_messages - 1)
        conv.total_tokens_used = max(0, conv.total_tokens_used - msg.tokens_used)
        conv.total_cost_usd = max(0.0, conv.total_cost_usd - msg.cost_usd)
        conv.updated_at = datetime.now(timezone.utc)
    
    await session.delete(msg)
    await session.commit()
    
    logger.debug(f"Deleted message {message_id[:8]}")
    return True


# ── Analytics helpers ─────────────────────────────────────────────────────────


async def get_conversation_stats(
    session: AsyncSession,
    user_id: str = "anonymous",
) -> dict:
    """
    Get aggregate statistics for a user's conversations.
    
    Returns:
        Dict with stats: total_conversations, total_messages, avg_messages_per_conv, etc.
    """
    result = await session.execute(
        select(
            func.count(Conversation.id).label("total_conversations"),
            func.sum(Conversation.total_messages).label("total_messages"),
            func.avg(Conversation.total_messages).label("avg_messages_per_conv"),
            func.sum(Conversation.total_cost_usd).label("total_cost"),
            func.avg(Conversation.total_cost_usd).label("avg_cost_per_conv"),
        )
        .where(Conversation.user_id == user_id)
        .where(Conversation.status == "active")
    )
    row = result.one()
    
    return {
        "total_conversations": row.total_conversations or 0,
        "total_messages": int(row.total_messages or 0),
        "avg_messages_per_conversation": round(float(row.avg_messages_per_conv or 0), 1),
        "total_cost_usd": round(float(row.total_cost or 0), 6),
        "avg_cost_per_conversation": round(float(row.avg_cost_per_conv or 0), 6),
    }
