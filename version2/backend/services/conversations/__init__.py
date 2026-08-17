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
    auto_name_conversation,
)

from .message_tree_service import (
    regenerate_message,
    switch_branch,
    get_branches,
    get_messages_with_active_branch,
    append_message_to_tree,
    start_streaming_message,
    complete_streaming_message,
    migrate_flat_to_tree,
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

    async def auto_name_conversation(self, conv_id, user_id, first_message):
        return await auto_name_conversation(conv_id, user_id, first_message)

    # ── Message Tree Methods ──
    async def regenerate_message(self, conv_id, message_id, user_id, new_content=None, metadata=None):
        return await regenerate_message(conv_id, message_id, user_id, new_content, metadata)

    async def switch_branch(self, conv_id, branch_id, user_id):
        return await switch_branch(conv_id, branch_id, user_id)

    async def get_branches(self, conv_id, user_id):
        return await get_branches(conv_id, user_id)

    async def get_messages_with_active_branch(self, conv_id, user_id):
        return await get_messages_with_active_branch(conv_id, user_id)

    async def append_message_to_tree(self, conv_id, user_id, role, content, parent_id=None, metadata=None):
        return await append_message_to_tree(conv_id, user_id, role, content, parent_id, metadata)

    async def start_streaming_message(self, conv_id, user_id, role, parent_id=None, metadata=None):
        return await start_streaming_message(conv_id, user_id, role, parent_id, metadata)

    async def complete_streaming_message(self, conv_id, user_id, message_id, content, status="completed", metadata=None):
        return await complete_streaming_message(conv_id, user_id, message_id, content, status, metadata)

    async def migrate_flat_to_tree(self, conv_id, user_id):
        return await migrate_flat_to_tree(conv_id, user_id)


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
    "auto_name_conversation",
    "regenerate_message",
    "switch_branch",
    "get_branches",
    "get_messages_with_active_branch",
    "append_message_to_tree",
    "start_streaming_message",
    "complete_streaming_message",
    "migrate_flat_to_tree",
]
