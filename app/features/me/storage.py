from functools import lru_cache
from typing import Any

from app.config import get_settings


@lru_cache(maxsize=1)
def get_s3_client() -> Any:
    import boto3

    settings = get_settings()
    return boto3.client("s3", region_name=settings.MEDIA_BUCKET_REGION)


def make_upload_post(key: str, content_type: str) -> dict[str, Any]:
    settings = get_settings()
    return get_s3_client().generate_presigned_post(
        Bucket=settings.MEDIA_BUCKET_NAME,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"key": key},
            {"Content-Type": content_type},
            ["content-length-range", 1, settings.MAX_UPLOAD_BYTES],
        ],
        ExpiresIn=600,
    )


def head_recording(key: str) -> dict[str, Any]:
    settings = get_settings()
    response = get_s3_client().head_object(Bucket=settings.MEDIA_BUCKET_NAME, Key=key)
    return {
        "size_bytes": int(response.get("ContentLength", 0)),
        "content_type": response.get("ContentType"),
    }


def make_download_url(key: str) -> str:
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MEDIA_BUCKET_NAME, "Key": key},
        ExpiresIn=3600,
    )
