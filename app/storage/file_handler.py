"""
OpenHT - File Storage Handler
Supabase Storage entegrasyonu veya local dosya depolama
"""

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, List, Optional

from loguru import logger

# Supabase storage (opsiyonel)
try:
    from supabase import create_client

    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class StorageHandler:
    """File storage handler - Supabase Storage veya local filesystem"""

    ALLOWED_EXTENSIONS = {
        # Images
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp",
        "svg",
        "bmp",
        # Videos
        "mp4",
        "webm",
        "mov",
        "avi",
        # Documents
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "txt",
        "md",
        "csv",
        "json",
        "xml",
        # Code
        "py",
        "js",
        "ts",
        "html",
        "css",
        "sql",
        "yaml",
        "yml",
        # Archives
        "zip",
        "tar",
        "gz",
        "rar",
    }

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self):
        self.local_storage_path = Path(os.getenv("STORAGE_PATH", "uploads"))
        self.supabase_client = None
        self.bucket_name = os.getenv("STORAGE_BUCKET", "attachments")

        self._initialize()

    def _initialize(self):
        """Initialize storage backend"""
        # Try Supabase first
        if SUPABASE_AVAILABLE:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

            if url and key:
                try:
                    self.supabase_client = create_client(url, key)
                    logger.info("Supabase Storage initialized")
                    return
                except Exception as e:
                    logger.warning(f"Supabase Storage init failed: {e}")

        # Fall back to local storage
        self.local_storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using local storage at: {self.local_storage_path}")

    @property
    def is_supabase(self) -> bool:
        return self.supabase_client is not None

    def _generate_file_path(self, user_id: str, filename: str) -> str:
        """Generate unique file path"""
        ext = Path(filename).suffix.lower()
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d")
        safe_name = hashlib.md5(filename.encode()).hexdigest()[:8]
        return f"{user_id}/{timestamp}/{safe_name}_{unique_id}{ext}"

    def _validate_file(self, filename: str, file_size: int) -> None:
        """Validate file before upload"""
        # Check extension
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Dosya türü desteklenmiyor: .{ext}")

        # Check size
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE // (1024 * 1024)
            raise ValueError(f"Dosya çok büyük. Maksimum: {max_mb}MB")

    async def upload_file(
        self, file_content: bytes, filename: str, user_id: str, content_type: str = None
    ) -> dict:
        """
        Upload file to storage
        Returns: {id, path, url, size, content_type}
        """
        self._validate_file(filename, len(file_content))

        file_path = self._generate_file_path(user_id, filename)
        file_id = str(uuid.uuid4())

        if self.is_supabase:
            return await self._upload_to_supabase(
                file_content, file_path, file_id, filename, content_type
            )
        else:
            return await self._upload_to_local(
                file_content, file_path, file_id, filename, content_type
            )

    async def _upload_to_supabase(
        self, content: bytes, path: str, file_id: str, filename: str, content_type: str
    ) -> dict:
        """Upload to Supabase Storage"""
        try:
            response = self.supabase_client.storage.from_(self.bucket_name).upload(
                path=path,
                file=content,
                file_options={
                    "content-type": content_type or "application/octet-stream"
                },
            )

            # Get public URL
            url = self.supabase_client.storage.from_(self.bucket_name).get_public_url(
                path
            )

            return {
                "id": file_id,
                "path": path,
                "url": url,
                "filename": filename,
                "size": len(content),
                "content_type": content_type,
                "storage": "supabase",
            }
        except Exception as e:
            logger.error(f"Supabase upload failed: {e}")
            # Fallback to local
            return await self._upload_to_local(
                content, path, file_id, filename, content_type
            )

    async def _upload_to_local(
        self, content: bytes, path: str, file_id: str, filename: str, content_type: str
    ) -> dict:
        """Upload to local filesystem"""
        full_path = self.local_storage_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_bytes(content)

        return {
            "id": file_id,
            "path": path,
            "url": f"/api/files/{file_id}",
            "filename": filename,
            "size": len(content),
            "content_type": content_type,
            "storage": "local",
        }

    async def get_file(self, file_path: str) -> Optional[bytes]:
        """Get file content"""
        if self.is_supabase:
            try:
                response = self.supabase_client.storage.from_(
                    self.bucket_name
                ).download(file_path)
                return response
            except Exception as e:
                logger.error(f"Supabase download failed: {e}")
                return None
        else:
            full_path = self.local_storage_path / file_path
            if full_path.exists():
                return full_path.read_bytes()
            return None

    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        if self.is_supabase:
            try:
                self.supabase_client.storage.from_(self.bucket_name).remove([file_path])
                return True
            except Exception as e:
                logger.error(f"Supabase delete failed: {e}")
                return False
        else:
            full_path = self.local_storage_path / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False

    async def list_user_files(self, user_id: str) -> List[dict]:
        """List all files for a user"""
        if self.is_supabase:
            try:
                response = self.supabase_client.storage.from_(self.bucket_name).list(
                    user_id
                )
                return response
            except Exception as e:
                logger.error(f"Supabase list failed: {e}")
                return []
        else:
            user_path = self.local_storage_path / user_id
            if not user_path.exists():
                return []

            files = []
            for file in user_path.rglob("*"):
                if file.is_file():
                    files.append(
                        {
                            "name": file.name,
                            "path": str(file.relative_to(self.local_storage_path)),
                            "size": file.stat().st_size,
                            "modified": datetime.fromtimestamp(
                                file.stat().st_mtime
                            ).isoformat(),
                        }
                    )
            return files


# Singleton instance
_storage_handler = None


def get_storage() -> StorageHandler:
    """Get storage handler singleton"""
    global _storage_handler
    if _storage_handler is None:
        _storage_handler = StorageHandler()
    return _storage_handler
