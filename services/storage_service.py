import os

from flask import current_app

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # pragma: no cover - optional dependency at runtime
    cloudinary = None


_CLOUDINARY_CONFIGURED = False


def _cloudinary_ready():
    return bool(
        current_app.config.get("CLOUDINARY_CLOUD_NAME")
        and current_app.config.get("CLOUDINARY_API_KEY")
        and current_app.config.get("CLOUDINARY_API_SECRET")
        and cloudinary is not None
    )


def _configure_cloudinary_once():
    global _CLOUDINARY_CONFIGURED
    if _CLOUDINARY_CONFIGURED:
        return
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    _CLOUDINARY_CONFIGURED = True


def upload_capture(file_path, folder, public_id):
    if not file_path or not os.path.exists(file_path):
        return ""

    if not _cloudinary_ready():
        return ""

    try:
        _configure_cloudinary_once()
        result = cloudinary.uploader.upload(
            file_path,
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=True,
        )
        return result.get("secure_url", "")
    except Exception as exc:  # pragma: no cover - external API errors
        current_app.logger.warning("Cloudinary upload failed: %s", exc)
        return ""
