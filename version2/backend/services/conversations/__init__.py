"""
Conversations Service Package
=============================
Chat and conversation management services.
"""

from .conversation_service import (
    load_or_create_conversation,
    save_conversation,
    get_user_conversations,
    delete_conversation,
    get_conversation,
    update_title,
    append_message,
    get_conversation_page,
    get_archived_messages,
    get_message_count,
    auto_archive_if_needed,
    archive_old_messages,
)


class ConversationService:
    """
    Conversation service with methods wrapping module-level functions.
    Provides a clean interface for managing conversations.
    """

    async def load_or_create_conversation(self, conv_id, user_id, dataset_id):
        return await load_or_create_conversation(conv_id, user_id, dataset_id)

    async def save_conversation(self, conv_id, messages):
        return await save_conversation(conv_id, messages)

    async def get_user_conversations(self, user_id, **kwargs):
        return await get_user_conversations(user_id)

    async def delete_conversation(self, conversation_id, user_id):
        return await delete_conversation(conversation_id, user_id)

    async def get_conversation(self, conversation_id, user_id):
        return await get_conversation(conversation_id, user_id)

    async def update_title(self, conversation_id, user_id, title):
        return await update_title(conversation_id, user_id, title)

    async def append_message(self, conv_id, message, auto_archive=True):
        return await append_message(conv_id, message, auto_archive)

    async def get_conversation_page(self, conversation_id, user_id, page=1, page_size=None, include_archived=False):
        return await get_conversation_page(conversation_id, user_id, page, page_size or 50, include_archived)

    async def get_archived_messages(self, conv_id, user_id, batch=None):
        return await get_archived_messages(conv_id, user_id, batch)

    async def get_message_count(self, conversation_id):
        return await get_message_count(conversation_id)

    async def auto_archive_if_needed(self, conv_id):
        return await auto_archive_if_needed(conv_id)

    async def archive_old_messages(self, conv_id, keep_recent=None):
        return await archive_old_messages(conv_id, keep_recent or 100)


# Create singleton instance
conversation_service = ConversationService()

__all__ = [
    "conversation_service",
    "ConversationService",
    "load_or_create_conversation",
    "save_conversation",
    "get_user_conversations",
    "delete_conversation",
    "get_conversation",
    "update_title",
]
