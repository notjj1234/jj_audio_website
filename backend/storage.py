"""Local filesystem or S3/MinIO object storage."""

from __future__ import annotations

import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from backend.config import settings


class Storage(ABC):
    @abstractmethod
    def put_file(self, key: str, path: Path) -> str:
        """Store a local file under key; return the key."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> str:
        """Store bytes under key; return the key."""

    @abstractmethod
    def get_file(self, key: str, dest: Path) -> Path:
        """Download object to dest; return dest."""

    @abstractmethod
    def open_temp(self, key: str, suffix: str = "") -> Path:
        """Download to a temp file and return its path (caller may delete)."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_file(self, key: str, path: Path) -> str:
        dest = self._path(key)
        shutil.copy2(path, dest)
        return key

    def put_bytes(self, key: str, data: bytes) -> str:
        self._path(key).write_bytes(data)
        return key

    def get_file(self, key: str, dest: Path) -> Path:
        src = self.root / key
        if not src.exists():
            raise FileNotFoundError(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    def open_temp(self, key: str, suffix: str = "") -> Path:
        src = self.root / key
        if not src.exists():
            raise FileNotFoundError(key)
        fd, name = tempfile.mkstemp(suffix=suffix or src.suffix)
        Path(name).write_bytes(src.read_bytes())
        import os

        os.close(fd)
        return Path(name)

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()

    def local_path(self, key: str) -> Path:
        """Direct path for local backend (no copy)."""
        return self.root / key


class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def put_file(self, key: str, path: Path) -> str:
        self._client.upload_file(str(path), self.bucket, key)
        return key

    def put_bytes(self, key: str, data: bytes) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get_file(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, key, str(dest))
        return dest

    def open_temp(self, key: str, suffix: str = "") -> Path:
        fd, name = tempfile.mkstemp(suffix=suffix)
        import os

        os.close(fd)
        path = Path(name)
        self.get_file(key, path)
        return path

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            pass


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.storage_backend == "s3":
            _storage = S3Storage()
        else:
            _storage = LocalStorage(Path(settings.data_dir) / "storage")
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
