"""File validation utilities."""

from fastapi import HTTPException, UploadFile

from app.config import settings

# Document types enum
DOCUMENT_TYPES = ["consent", "id_scan", "insurance", "report", "referral", "other"]

# Modern image formats not in the default config allowlist but commonly
# uploaded from clinical phones / tablets. The base allowlist covers
# JPEG / PNG / PDF; we extend for HEIC (iOS), WebP and GIF so the photo
# gallery accepts them without per-clinic config changes.
_PHOTO_MIME_EXTRA = frozenset(
    {
        "image/heic",
        "image/heif",
        "image/webp",
        "image/gif",
    }
)

# DICOM radiology uploads for the imaging_viewer module (study index +
# viewer proxy). Same rationale as above: accepted without per-clinic
# config changes once the module is installed.
_DICOM_MIME_EXTRA = frozenset({"application/dicom"})


def validate_file_size(file: UploadFile, content_length: int | None = None) -> None:
    """Validate file size against limit.

    Args:
        file: Uploaded file
        content_length: Content-Length header value (if available)

    Raises:
        HTTPException: If file exceeds size limit
    """
    max_size = settings.STORAGE_MAX_FILE_SIZE

    if content_length and content_length > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds limit of {max_size // (1024 * 1024)}MB",
        )


def validate_mime_type(file: UploadFile) -> str:
    """Validate and return MIME type.

    Args:
        file: Uploaded file

    Returns:
        Validated MIME type

    Raises:
        HTTPException: If MIME type not allowed
    """
    allowed = set(settings.storage_allowed_mime_types_list) | _PHOTO_MIME_EXTRA | _DICOM_MIME_EXTRA
    content_type = file.content_type or "application/octet-stream"

    if content_type not in allowed:
        # Browsers upload `.dcm` as octet-stream: accept by extension so the
        # viewer's DICM magic-byte sniff (not the mime) decides radiology.
        # Anything else stays rejected — the allowlist is not widened.
        filename = (file.filename or "").lower()
        if content_type != "application/octet-stream" or not filename.endswith(".dcm"):
            raise HTTPException(
                status_code=400,
                detail=f"File type '{content_type}' not allowed. Allowed: {', '.join(sorted(allowed))}",
            )

    return content_type


def validate_document_type(document_type: str) -> None:
    """Validate document type.

    Args:
        document_type: Document type to validate

    Raises:
        HTTPException: If document type invalid
    """
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Allowed: {', '.join(DOCUMENT_TYPES)}",
        )


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename.

    Args:
        filename: Original filename

    Returns:
        Extension without dot (e.g., "pdf")
    """
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""
