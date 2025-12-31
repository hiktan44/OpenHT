"""
OpenHT Web UI - Session Manager
Konuşma ve mesaj yönetimi
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Tek bir mesaj"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" veya "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class Conversation(BaseModel):
    """Bir konuşma oturumu"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Yeni Sohbet"
    messages: List[Message] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    model: str = "anthropic/claude-sonnet-4"
    settings: Dict = Field(
        default_factory=lambda: {
            "temperature": 1.0,
            "max_tokens": 4096,
            "system_prompt": "",
        }
    )


class SessionManager:
    """Konuşma oturumlarını yönetir"""

    def __init__(self, storage_path: str = "web/conversations.json"):
        self.storage_path = Path(storage_path)
        self.conversations: Dict[str, Conversation] = {}
        self._load()

    def _load(self):
        """Konuşmaları dosyadan yükle"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for conv_id, conv_data in data.items():
                    self.conversations[conv_id] = Conversation(**conv_data)
            except Exception:
                self.conversations = {}

    def _save(self):
        """Konuşmaları dosyaya kaydet"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            conv_id: conv.model_dump() for conv_id, conv in self.conversations.items()
        }
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def create_conversation(self, title: str = "Yeni Sohbet") -> Conversation:
        """Yeni konuşma oluştur"""
        conv = Conversation(title=title)
        self.conversations[conv.id] = conv
        self._save()
        return conv

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Konuşmayı getir"""
        return self.conversations.get(conv_id)

    def list_conversations(self) -> List[Conversation]:
        """Tüm konuşmaları listele (en son güncellenen önce)"""
        return sorted(
            self.conversations.values(), key=lambda c: c.updated_at, reverse=True
        )

    def add_message(self, conv_id: str, role: str, content: str) -> Optional[Message]:
        """Konuşmaya mesaj ekle"""
        conv = self.conversations.get(conv_id)
        if not conv:
            return None

        message = Message(role=role, content=content)
        conv.messages.append(message)
        conv.updated_at = datetime.now().isoformat()

        # İlk kullanıcı mesajından başlık oluştur
        if len(conv.messages) == 1 and role == "user":
            conv.title = content[:50] + ("..." if len(content) > 50 else "")

        self._save()
        return message

    def update_settings(self, conv_id: str, settings: Dict) -> bool:
        """Konuşma ayarlarını güncelle"""
        conv = self.conversations.get(conv_id)
        if not conv:
            return False

        conv.settings.update(settings)
        if "model" in settings:
            conv.model = settings["model"]
        self._save()
        return True

    def delete_conversation(self, conv_id: str) -> bool:
        """Konuşmayı sil"""
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            self._save()
            return True
        return False


# Singleton instance
session_manager = SessionManager()
