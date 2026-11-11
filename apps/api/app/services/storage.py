import uuid
from pathlib import Path
from typing import Protocol

from app.config import settings


class FileStorage(Protocol):
    """Abstract interface for storing uploaded raw datasets."""

    def save(self, filename: str, content: bytes) -> str:
        """Save raw bytes byte-for-byte and return the stored path."""
        ...

    def read(self, path: str) -> bytes:
        """Read original raw bytes."""
        ...

    def delete(self, path: str) -> None:
        """Delete stored file if exists."""
        ...


class LocalFileStorage:
    """Local disk implementation of FileStorage."""

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        safe_name = Path(filename.replace("\\", "/")).name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("Invalid filename for storage")
        base_resolved = self.base_path.resolve()
        unique_prefix = uuid.uuid4().hex[:8]
        target_path = (base_resolved / f"{unique_prefix}_{safe_name}").resolve()
        if not target_path.is_relative_to(base_resolved):
            raise ValueError("Resolved storage path escapes storage root")
        target_path.write_bytes(content)
        return str(target_path)

    def read(self, path: str) -> bytes:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_bytes()

    def delete(self, path: str) -> None:
        file_path = Path(path)
        if file_path.is_file():
            file_path.unlink()


def get_storage() -> FileStorage:
    """Factory returning the configured storage backend."""
    return LocalFileStorage()
