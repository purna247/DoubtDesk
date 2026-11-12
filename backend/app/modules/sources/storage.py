import hashlib
import os
import uuid
import tempfile
from pathlib import Path
from typing import Tuple
from app.config import get_settings
from app.common.exceptions import AppException

settings = get_settings()

ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

ALLOWED_EXTENSIONS = set(ALLOWED_FILE_TYPES)


class StorageService:
    """Local-first storage service with opaque keys and strict directory isolation."""

    @staticmethod
    def get_file_extension(filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return ext

    @staticmethod
    def validate_file(filename: str, size_bytes: int, max_limit_mb: int = 50) -> Tuple[str, str]:
        ext = StorageService.get_file_extension(filename)
        if ext not in ALLOWED_EXTENSIONS:
            raise AppException(
                code="UNSUPPORTED_FILE_TYPE",
                message=f"File extension '{ext}' is not supported. Allowed formats: PDF, DOCX, PPTX, TXT, MD.",
                status_code=400,
            )

        max_bytes = max_limit_mb * 1024 * 1024
        if size_bytes > max_bytes:
            raise AppException(
                code="FILE_SIZE_EXCEEDED",
                message=f"File size exceeds the configured limit of {max_limit_mb}MB.",
                status_code=400,
            )

        mime_type = ALLOWED_FILE_TYPES[ext]
        return ext, mime_type

    @staticmethod
    def _resolve_storage_path(storage_key: str) -> Path:
        """Resolve a key and reject paths outside the configured storage root."""
        base_path = settings.LOCAL_STORAGE_DIR.resolve()
        file_path = (base_path / storage_key).resolve()
        try:
            file_path.relative_to(base_path)
        except ValueError as exc:
            raise AppException(
                code="STORAGE_SECURITY_VIOLATION",
                message="Path traversal detected.",
                status_code=400,
            ) from exc
        return file_path

    @staticmethod
    async def store_file(
        content: bytes, original_filename: str, institution_id: uuid.UUID, max_limit_mb: int = 50
    ) -> Tuple[str, str, int, str]:
        """
        Store uploaded bytes under an institution-scoped content-addressed key.
        Never use the original filename as a filesystem path.
        Returns (storage_key, mime_type, size_bytes, sha256_checksum).
        """
        size_bytes = len(content)
        ext, mime_type = StorageService.validate_file(original_filename, size_bytes, max_limit_mb)
        checksum = hashlib.sha256(content).hexdigest()

        # Content-addressed keys make repeat uploads reuse the same stored object.
        # Institution scope prevents cross-tenant existence or storage sharing.
        storage_key = f"{institution_id}/sha256/{checksum}"

        # Resolve destination path
        dest_path = StorageService._resolve_storage_path(storage_key)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            # Stage a complete object, then atomically link it into the content address.
            # Concurrent identical uploads race safely: only one link can be created.
            with tempfile.NamedTemporaryFile(dir=dest_path.parent, prefix=".upload-", delete=False) as staged:
                temp_path = Path(staged.name)
                staged.write(content)
                staged.flush()
                os.fsync(staged.fileno())
            try:
                os.link(temp_path, dest_path)
            except FileExistsError:
                if dest_path.read_bytes() != content:
                    raise AppException(
                        code="STORAGE_CHECKSUM_COLLISION",
                        message="Stored object failed checksum verification.",
                        status_code=500,
                    )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        return storage_key, mime_type, size_bytes, checksum

    @staticmethod
    async def retrieve_file(storage_key: str) -> bytes:
        """Retrieve stored bytes after access verification."""
        file_path = StorageService._resolve_storage_path(storage_key)

        if not file_path.exists():
            raise AppException(
                code="FILE_NOT_FOUND",
                message="The requested file was not found in storage.",
                status_code=404,
            )

        return file_path.read_bytes()

    @staticmethod
    async def delete_file(storage_key: str) -> None:
        file_path = StorageService._resolve_storage_path(storage_key)
        if file_path.exists():
            file_path.unlink()
