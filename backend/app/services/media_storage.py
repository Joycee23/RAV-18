from functools import lru_cache

from supabase import create_client

from app.config import get_settings


class StorageNotConfigured(RuntimeError):
    pass


class MediaStorage:
    def __init__(self, client=None, bucket: str | None = None):
        settings = get_settings()
        if client is None:
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise StorageNotConfigured("Private media storage is not configured")
            client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        self.client = client
        self.bucket = bucket or settings.supabase_media_bucket

    def upload(self, incident_id, file_bytes: bytes, object_path: str, content_type: str) -> None:
        self.client.storage.from_(self.bucket).upload(object_path, file_bytes, {"content-type": content_type, "upsert": "false"})

    def download(self, object_path: str) -> bytes:
        return self.client.storage.from_(self.bucket).download(object_path)

    def signed_url(self, object_path: str, expires_in: int) -> str:
        result = self.client.storage.from_(self.bucket).create_signed_url(object_path, expires_in)
        return result.get("signedURL") or result.get("signedUrl")

    def delete(self, object_path: str) -> None:
        self.client.storage.from_(self.bucket).remove([object_path])


@lru_cache
def get_media_storage() -> MediaStorage:
    return MediaStorage()


def optional_media_storage() -> MediaStorage | None:
    try:
        return get_media_storage()
    except StorageNotConfigured:
        return None
