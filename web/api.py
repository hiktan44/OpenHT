"""
OpenHT Web UI - FastAPI Backend
REST API ve WebSocket endpoint'leri
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, EmailStr

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agent.openht import OpenHT
from app.config import config
from web.session import Conversation, Message, session_manager

# Auth modüllerini import et (opsiyonel - yoksa çalışmaya devam eder)
try:
    from app.auth import (
        UserToken,
        auth_handler,
        get_current_user,
        hash_password,
        require_auth,
        verify_password,
    )

    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    logger.warning("Auth modülü yüklenemedi. Authentication devre dışı.")

# Database modülünü import et (opsiyonel)
try:
    from app.database import get_db

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database modülü yüklenemedi. Local mode aktif.")

app = FastAPI(title="OpenHT Web UI", version="1.0.0")

# Static dosyaları serve et
app.mount("/static", StaticFiles(directory="web/static"), name="static")


# ===================== Pydantic Modeller =====================


class ChatRequest(BaseModel):
    """Chat isteği"""

    conversation_id: str
    message: str


class SettingsUpdate(BaseModel):
    """Ayar güncellemesi"""

    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None


class NewConversationRequest(BaseModel):
    """Yeni konuşma isteği"""

    title: Optional[str] = "Yeni Sohbet"


# ===================== Mevcut Modeller =====================

AVAILABLE_MODELS = [
    # ===================== Google (Gemini) =====================
    {"id": "google/gemini-3-pro", "name": "Gemini 3 Pro", "provider": "Google"},
    {"id": "google/gemini-3-flash", "name": "Gemini 3 Flash", "provider": "Google"},
    {
        "id": "google/gemini-2.5-pro-preview",
        "name": "Gemini 2.5 Pro",
        "provider": "Google",
    },
    {
        "id": "google/gemini-2.5-flash-preview",
        "name": "Gemini 2.5 Flash",
        "provider": "Google",
    },
    {
        "id": "google/gemini-2.0-flash-001",
        "name": "Gemini 2.0 Flash",
        "provider": "Google",
    },
    {
        "id": "google/gemini-2.0-flash-thinking-exp",
        "name": "Gemini 2.0 Flash Thinking",
        "provider": "Google",
    },
    # ===================== Anthropic (Claude) =====================
    {
        "id": "anthropic/claude-opus-4.5",
        "name": "Claude Opus 4.5",
        "provider": "Anthropic",
    },
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "provider": "Anthropic",
    },
    {"id": "anthropic/claude-opus-4", "name": "Claude Opus 4", "provider": "Anthropic"},
    {
        "id": "anthropic/claude-sonnet-4",
        "name": "Claude Sonnet 4",
        "provider": "Anthropic",
    },
    {
        "id": "anthropic/claude-3.5-sonnet",
        "name": "Claude 3.5 Sonnet",
        "provider": "Anthropic",
    },
    {
        "id": "anthropic/claude-3.5-haiku",
        "name": "Claude 3.5 Haiku",
        "provider": "Anthropic",
    },
    # ===================== OpenAI =====================
    {"id": "openai/gpt-5-turbo", "name": "GPT-5 Turbo", "provider": "OpenAI"},
    {"id": "openai/gpt-5", "name": "GPT-5", "provider": "OpenAI"},
    {"id": "openai/gpt-5-mini", "name": "GPT-5 Mini", "provider": "OpenAI"},
    {"id": "openai/gpt-4.5-preview", "name": "GPT-4.5 Preview", "provider": "OpenAI"},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    {"id": "openai/o3", "name": "O3", "provider": "OpenAI"},
    {"id": "openai/o3-mini", "name": "O3 Mini", "provider": "OpenAI"},
    {"id": "openai/o1", "name": "O1", "provider": "OpenAI"},
    {"id": "openai/o1-mini", "name": "O1 Mini", "provider": "OpenAI"},
    {"id": "openai/codex-mini-latest", "name": "Codex Mini", "provider": "OpenAI"},
    # ===================== DeepSeek =====================
    {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "provider": "DeepSeek"},
    {"id": "deepseek/deepseek-v3", "name": "DeepSeek V3", "provider": "DeepSeek"},
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "provider": "DeepSeek"},
    # ===================== Mistral =====================
    {
        "id": "mistralai/mistral-large-2411",
        "name": "Mistral Large",
        "provider": "Mistral",
    },
    {"id": "mistralai/codestral-2501", "name": "Codestral", "provider": "Mistral"},
    {
        "id": "mistralai/mistral-medium-3",
        "name": "Mistral Medium 3",
        "provider": "Mistral",
    },
    # ===================== Meta (Llama) =====================
    {
        "id": "meta-llama/llama-4-maverick",
        "name": "Llama 4 Maverick",
        "provider": "Meta",
    },
    {"id": "meta-llama/llama-4-scout", "name": "Llama 4 Scout", "provider": "Meta"},
    {
        "id": "meta-llama/llama-3.3-70b-instruct",
        "name": "Llama 3.3 70B",
        "provider": "Meta",
    },
    # ===================== Qwen =====================
    {"id": "qwen/qwen-3-235b-instruct", "name": "Qwen 3 235B", "provider": "Qwen"},
    {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "provider": "Qwen"},
    {"id": "qwen/qwq-32b", "name": "QwQ 32B", "provider": "Qwen"},
    # ===================== xAI (Grok) =====================
    {"id": "x-ai/grok-3", "name": "Grok 3", "provider": "xAI"},
    {"id": "x-ai/grok-3-mini", "name": "Grok 3 Mini", "provider": "xAI"},
    {"id": "x-ai/grok-2", "name": "Grok 2", "provider": "xAI"},
    # ===================== Zhipu AI (GLM) =====================
    {"id": "zhipu/glm-4.7", "name": "GLM 4.7", "provider": "Zhipu AI"},
    {"id": "zhipu/glm-4-plus", "name": "GLM 4 Plus", "provider": "Zhipu AI"},
    {"id": "zhipu/glm-4-flash", "name": "GLM 4 Flash", "provider": "Zhipu AI"},
    # ===================== Minimax =====================
    {"id": "minimax/minimax-m2", "name": "Minimax M2", "provider": "Minimax"},
    {"id": "minimax/minimax-01", "name": "Minimax 01", "provider": "Minimax"},
    # ===================== Baichuan =====================
    {"id": "baichuan/baichuan-4", "name": "Baichuan 4", "provider": "Baichuan"},
    # ===================== 🎨 IMAGE GENERATION MODELS 🎨 =====================
    {
        "id": "openai/gpt-image-1",
        "name": "GPT Image 1 (DALL-E 4)",
        "provider": "OpenAI",
        "type": "image",
    },
    {
        "id": "openai/dall-e-3",
        "name": "DALL-E 3",
        "provider": "OpenAI",
        "type": "image",
    },
    {
        "id": "stability/stable-diffusion-xl",
        "name": "Stable Diffusion XL",
        "provider": "Stability AI",
        "type": "image",
    },
    {
        "id": "stability/stable-diffusion-3",
        "name": "Stable Diffusion 3",
        "provider": "Stability AI",
        "type": "image",
    },
    {
        "id": "black-forest-labs/flux-1.1-pro",
        "name": "FLUX 1.1 Pro",
        "provider": "Black Forest Labs",
        "type": "image",
    },
    {
        "id": "black-forest-labs/flux-1.1-pro-ultra",
        "name": "FLUX 1.1 Pro Ultra",
        "provider": "Black Forest Labs",
        "type": "image",
    },
    {
        "id": "black-forest-labs/flux-schnell",
        "name": "FLUX Schnell",
        "provider": "Black Forest Labs",
        "type": "image",
    },
    {
        "id": "midjourney/midjourney-v6",
        "name": "Midjourney V6",
        "provider": "Midjourney",
        "type": "image",
    },
    {
        "id": "ideogram/ideogram-v2",
        "name": "Ideogram V2",
        "provider": "Ideogram",
        "type": "image",
    },
    {
        "id": "google/imagen-3",
        "name": "Imagen 3",
        "provider": "Google",
        "type": "image",
    },
    {
        "id": "recraft/recraft-v3",
        "name": "Recraft V3",
        "provider": "Recraft",
        "type": "image",
    },
    {
        "id": "together/banana-nano",
        "name": "Banana Nano",
        "provider": "Together AI",
        "type": "image",
    },
]

# Varsayılan görsel üretim modeli
DEFAULT_IMAGE_MODEL = "openai/gpt-image-1"


# ===================== REST API Endpoints =====================


# ==================== Health Check ====================


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Coolify"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": "connected" if DB_AVAILABLE else "local_mode",
        "auth": "enabled" if AUTH_AVAILABLE else "disabled",
    }


# ==================== Auth Endpoints ====================


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


@app.get("/login")
async def login_page():
    """Login sayfası"""
    return FileResponse("web/static/login.html")


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Kullanıcı girişi"""
    if not AUTH_AVAILABLE:
        # Auth yoksa demo token döndür
        demo_token = str(uuid.uuid4())
        return {
            "access_token": demo_token,
            "token_type": "bearer",
            "user": {
                "id": "demo-user",
                "email": request.email,
                "name": request.email.split("@")[0],
            },
        }

    # Supabase veya local auth ile doğrula
    # Bu basit implementasyon - production'da Supabase Auth kullanılmalı
    token = auth_handler.create_token(
        user_id=str(uuid.uuid4()), email=request.email, name=request.email.split("@")[0]
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(uuid.uuid4()),
            "email": request.email,
            "name": request.email.split("@")[0],
        },
    }


@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Yeni kullanıcı kaydı"""
    if not AUTH_AVAILABLE:
        return {"success": True, "message": "Kayıt başarılı (demo mode)"}

    # Supabase'e kullanıcı kaydet
    # Production'da Supabase Auth kullanılmalı
    return {"success": True, "message": "Kayıt başarılı"}


@app.get("/api/auth/me")
async def get_current_user_info():
    """Mevcut kullanıcı bilgisi"""
    # Token doğrulaması yapılmalı
    # Şimdilik basit bir response
    return {"id": "demo-user", "email": "demo@openht.local", "name": "Demo User"}


# ==================== Main Endpoints ====================


@app.get("/")
async def root():
    """Ana sayfa"""
    return FileResponse("web/static/index.html")


@app.get("/api/models")
async def get_models():
    """Mevcut modelleri listele"""
    return {"models": AVAILABLE_MODELS}


@app.get("/api/conversations")
async def list_conversations():
    """Tüm konuşmaları listele"""
    conversations = session_manager.list_conversations()
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "updated_at": c.updated_at,
                "model": c.model,
                "message_count": len(c.messages),
            }
            for c in conversations
        ]
    }


@app.post("/api/conversations")
async def create_conversation(request: NewConversationRequest):
    """Yeni konuşma oluştur"""
    conv = session_manager.create_conversation(request.title)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Konuşma detaylarını getir"""
    conv = session_manager.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Konuşma bulunamadı")

    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [m.model_dump() for m in conv.messages],
        "model": conv.model,
        "settings": conv.settings,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Konuşmayı sil"""
    if session_manager.delete_conversation(conv_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Konuşma bulunamadı")


@app.put("/api/conversations/{conv_id}/settings")
async def update_settings(conv_id: str, settings: SettingsUpdate):
    """Konuşma ayarlarını güncelle"""
    updates = {k: v for k, v in settings.model_dump().items() if v is not None}
    if session_manager.update_settings(conv_id, updates):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Konuşma bulunamadı")


# ===================== WebSocket Chat =====================


class ConnectionManager:
    """WebSocket bağlantı yöneticisi"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/chat/{client_id}")
async def websocket_chat(websocket: WebSocket, client_id: str):
    """WebSocket chat endpoint"""
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_json()

            conv_id = data.get("conversation_id")
            message = data.get("message", "")

            if not conv_id or not message:
                await manager.send_message(
                    client_id,
                    {"type": "error", "message": "conversation_id ve message gerekli"},
                )
                continue

            # Konuşmayı kontrol et
            conv = session_manager.get_conversation(conv_id)
            if not conv:
                await manager.send_message(
                    client_id, {"type": "error", "message": "Konuşma bulunamadı"}
                )
                continue

            # Kullanıcı mesajını kaydet
            session_manager.add_message(conv_id, "user", message)

            # Başladığını bildir
            await manager.send_message(
                client_id, {"type": "start", "conversation_id": conv_id}
            )

            try:
                # OpenHT agent'ı oluştur ve çalıştır
                agent = await OpenHT.create()

                # Geçmiş mesajları prompt'a ekle
                history = "\n".join(
                    [
                        f"{'Kullanıcı' if m.role == 'user' else 'Asistan'}: {m.content}"
                        for m in conv.messages[:-1]  # Son mesaj hariç (yeni eklenen)
                    ]
                )

                full_prompt = message
                if history:
                    full_prompt = f"Önceki konuşma:\n{history}\n\nKullanıcı: {message}"

                # Agent'ı çalıştır
                response = await agent.run(full_prompt)

                # Yanıtı kaydet
                if response:
                    session_manager.add_message(conv_id, "assistant", str(response))

                    # Yanıtı gönder
                    await manager.send_message(
                        client_id,
                        {
                            "type": "message",
                            "content": str(response),
                            "conversation_id": conv_id,
                        },
                    )

                # Agent'ı temizle
                await agent.cleanup()

            except Exception as e:
                await manager.send_message(
                    client_id, {"type": "error", "message": f"Hata: {str(e)}"}
                )

            # Bittiğini bildir
            await manager.send_message(
                client_id, {"type": "end", "conversation_id": conv_id}
            )

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# ===================== Basit Chat Endpoint (WebSocket olmadan) =====================


@app.post("/api/chat")
async def simple_chat(request: ChatRequest):
    """Basit chat endpoint (WebSocket kullanmadan)"""
    conv = session_manager.get_conversation(request.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Konuşma bulunamadı")

    # Kullanıcı mesajını kaydet
    session_manager.add_message(request.conversation_id, "user", request.message)

    try:
        # OpenHT agent'ı oluştur ve çalıştır
        agent = await OpenHT.create()

        # Agent'ı çalıştır
        response = await agent.run(request.message)

        # Yanıtı kaydet
        if response:
            session_manager.add_message(
                request.conversation_id, "assistant", str(response)
            )

        # Agent'ı temizle
        await agent.cleanup()

        return {
            "response": str(response) if response else "",
            "conversation_id": request.conversation_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
