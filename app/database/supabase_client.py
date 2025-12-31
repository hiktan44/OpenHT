"""
OpenHT - Supabase Database Client
Database bağlantısı ve CRUD işlemleri
"""

import os
from functools import lru_cache
from typing import Optional

try:
    from supabase import Client, create_client

    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from loguru import logger


class SupabaseClient:
    """Supabase client wrapper with connection management"""

    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._initialize()

    def _initialize(self):
        """Initialize Supabase client"""
        if not SUPABASE_AVAILABLE:
            logger.warning("Supabase package not installed. Running in local mode.")
            return

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            logger.warning("Supabase credentials not found. Running in local mode.")
            return

        try:
            self._client = create_client(url, key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            self._client = None

    @property
    def client(self) -> Optional[Client]:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    # ==================== User Operations ====================

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get user by ID"""
        if not self.is_connected:
            return None

        try:
            response = (
                self._client.table("users")
                .select("*")
                .eq("id", user_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email"""
        if not self.is_connected:
            return None

        try:
            response = (
                self._client.table("users")
                .select("*")
                .eq("email", email)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    async def create_user(self, user_data: dict) -> Optional[dict]:
        """Create new user"""
        if not self.is_connected:
            return None

        try:
            response = self._client.table("users").insert(user_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    # ==================== Conversation Operations ====================

    async def get_conversations(self, user_id: str) -> list:
        """Get all conversations for a user"""
        if not self.is_connected:
            return []

        try:
            response = (
                self._client.table("conversations")
                .select("*")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            return []

    async def get_conversation(
        self, conv_id: str, user_id: str = None
    ) -> Optional[dict]:
        """Get single conversation with messages"""
        if not self.is_connected:
            return None

        try:
            query = self._client.table("conversations").select("*").eq("id", conv_id)
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.single().execute()

            if response.data:
                # Get messages for this conversation
                messages = await self.get_messages(conv_id)
                response.data["messages"] = messages

            return response.data
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None

    async def create_conversation(
        self,
        user_id: str,
        title: str = "Yeni Sohbet",
        model: str = "anthropic/claude-sonnet-4",
    ) -> Optional[dict]:
        """Create new conversation"""
        if not self.is_connected:
            return None

        try:
            data = {
                "user_id": user_id,
                "title": title,
                "model": model,
                "settings": {"temperature": 1.0, "max_tokens": 4096},
            }
            response = self._client.table("conversations").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            return None

    async def update_conversation(self, conv_id: str, data: dict) -> Optional[dict]:
        """Update conversation"""
        if not self.is_connected:
            return None

        try:
            response = (
                self._client.table("conversations")
                .update(data)
                .eq("id", conv_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating conversation: {e}")
            return None

    async def delete_conversation(self, conv_id: str, user_id: str = None) -> bool:
        """Delete conversation and its messages"""
        if not self.is_connected:
            return False

        try:
            # Delete messages first
            self._client.table("messages").delete().eq(
                "conversation_id", conv_id
            ).execute()

            # Delete conversation
            query = self._client.table("conversations").delete().eq("id", conv_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()

            return True
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return False

    # ==================== Message Operations ====================

    async def get_messages(self, conversation_id: str) -> list:
        """Get all messages for a conversation"""
        if not self.is_connected:
            return []

        try:
            response = (
                self._client.table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []

    async def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> Optional[dict]:
        """Add message to conversation"""
        if not self.is_connected:
            return None

        try:
            data = {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            }
            response = self._client.table("messages").insert(data).execute()

            # Update conversation's updated_at
            self._client.table("conversations").update({"updated_at": "now()"}).eq(
                "id", conversation_id
            ).execute()

            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return None

    async def init_db(self):
        """Initialize database tables if they don't exist (Self-Healing)"""
        if not self.is_connected:
            return

        logger.info("Checking database schema...")

        # Check if users table exists by trying to select from it
        try:
            self._client.table("users").select("id").limit(1).execute()
        except Exception as e:
            logger.warning(
                f"Tables not found, attempting to create schema... Error: {e}"
            )

            # If selection fails, try to create tables via raw SQL (using rpc if available or raw query)
            # Since Supabase-py client doesn't support raw SQL execution directly on all versions,
            # we will use the 'postgres' connection string fallback if possible,
            # Or reliance on the user manually running it.
            # However, for this specific request, we will try to use the `setup_db.py` logic internally if possible.

            # Note: The most reliable way in a Python app without direct Postgres connection is usually
            # to depend on prepared migrations. But here we will log a critical instruction.
            logger.critical(
                "DATABASE TABLES MISSING! Please run the following SQL in your database:"
            )
            logger.critical(
                """
                CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email TEXT UNIQUE NOT NULL, name TEXT, avatar_url TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), last_login TIMESTAMPTZ, settings JSONB DEFAULT '{}'::jsonb);
                CREATE TABLE IF NOT EXISTS conversations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE CASCADE, title TEXT DEFAULT 'Yeni Sohbet', model TEXT DEFAULT 'anthropic/claude-sonnet-4', settings JSONB DEFAULT '{"temperature": 1.0, "max_tokens": 4096}'::jsonb, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW());
                CREATE TABLE IF NOT EXISTS messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')), content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW(), metadata JSONB DEFAULT '{}'::jsonb);
                CREATE TABLE IF NOT EXISTS attachments (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), message_id UUID REFERENCES messages(id) ON DELETE CASCADE, user_id UUID REFERENCES users(id) ON DELETE CASCADE, file_name TEXT NOT NULL, file_type TEXT, file_size INTEGER, storage_path TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
            """
            )


# Singleton instance
@lru_cache(maxsize=1)
def get_supabase() -> SupabaseClient:
    """Get Supabase client singleton"""
    return SupabaseClient()


# Convenience function
def get_db() -> SupabaseClient:
    """Alias for get_supabase"""
    return get_supabase()
