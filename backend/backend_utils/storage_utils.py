from pathlib import Path
from uuid import UUID
import mimetypes

from backend.supabase_client import admin_supabase


# ============================================================
# STORAGE BUCKETS
# ============================================================

HOSPITAL_LOGO_BUCKET = "hospital-logos"
PROFILE_PICTURE_BUCKET = "profile-pictures"


# ============================================================
# FILE SETTINGS
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ============================================================
# HELPERS
# ============================================================

def _validate_image(
    file_bytes: bytes,
    file_name: str,
) -> tuple[bool, str]:
    """
    Validate image file type and size.

    Returns:
        (True, "") when valid.
        (False, error_message) when invalid.
    """

    if not file_bytes:
        return False, "The image file is empty."

    if len(file_bytes) > MAX_FILE_SIZE:
        return False, "Image size must not exceed 5 MB."

    extension = Path(file_name).suffix.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return (
            False,
            "Invalid image format. "
            "Please upload a JPG, PNG, or WEBP image.",
        )

    content_type, _ = mimetypes.guess_type(file_name)

    if content_type not in ALLOWED_IMAGE_TYPES:
        return (
            False,
            "Invalid image format. "
            "Please upload a JPG, PNG, or WEBP image.",
        )

    return True, ""


def _safe_extension(file_name: str) -> str:
    """
    Return a safe lowercase file extension.

    JPEG is normalized to JPG.
    """

    extension = Path(file_name).suffix.lower()

    if extension == ".jpeg":
        return ".jpg"

    return extension


def _content_type(file_name: str) -> str:
    """
    Determine the MIME type of an uploaded image.
    """

    content_type, _ = mimetypes.guess_type(file_name)

    return content_type or "image/png"


def _public_url(
    bucket: str,
    file_path: str,
) -> str:
    """
    Return the public URL of a file
    in a public Supabase Storage bucket.
    """

    result = (
        admin_supabase
        .storage
        .from_(bucket)
        .get_public_url(file_path)
    )

    if isinstance(result, dict):
        return (
            result.get("publicUrl")
            or result.get("public_url")
            or ""
        )

    return str(result)


# ============================================================
# HOSPITAL LOGO
# ============================================================

def upload_hospital_logo(
    hospital_id: str | UUID,
    file_bytes: bytes,
    file_name: str,
) -> dict:
    """
    Upload or replace a hospital logo.

    Storage path:

        hospital-logos/<hospital_id>/logo.<extension>

    The existing logo files are removed first.
    """

    valid, message = _validate_image(
        file_bytes,
        file_name,
    )

    if not valid:
        return {
            "success": False,
            "url": None,
            "path": None,
            "message": message,
        }

    hospital_id = str(hospital_id)
    extension = _safe_extension(file_name)

    file_path = f"{hospital_id}/logo{extension}"

    try:
        storage = admin_supabase.storage.from_(
            HOSPITAL_LOGO_BUCKET
        )

        # ----------------------------------------------------
        # Remove any existing hospital logo files.
        # ----------------------------------------------------

        delete_result = delete_old_hospital_logo(
            hospital_id
        )

        if not delete_result["success"]:
            return {
                "success": False,
                "url": None,
                "path": None,
                "message": delete_result["message"],
            }

        # ----------------------------------------------------
        # Upload / replace logo.
        #
        # upsert=True prevents a 409 Duplicate if an object
        # with the same path still exists.
        # ----------------------------------------------------

        storage.upload(
            file_path,
            file_bytes,
            {
                "content-type": _content_type(file_name),
                "upsert": "true",
            },
        )

        url = _public_url(
            HOSPITAL_LOGO_BUCKET,
            file_path,
        )

        return {
            "success": True,
            "url": url,
            "path": file_path,
            "message": "Hospital logo uploaded successfully.",
        }

    except Exception as exc:
        return {
            "success": False,
            "url": None,
            "path": None,
            "message": (
                "Failed to upload hospital logo: "
                f"{exc}"
            ),
        }


def delete_old_hospital_logo(
    hospital_id: str | UUID,
) -> dict:
    """
    Delete all existing hospital logo files.

    The storage bucket itself is NEVER deleted.
    Only objects belonging to this hospital are removed.
    """

    hospital_id = str(hospital_id)

    try:
        storage = admin_supabase.storage.from_(
            HOSPITAL_LOGO_BUCKET
        )

        files = storage.list(hospital_id)

        if not files:
            return {
                "success": True,
                "message": "No existing hospital logo found.",
            }

        paths_to_delete = []

        for file in files:
            file_name = file.get("name")

            if not file_name:
                continue

            extension = Path(
                file_name
            ).suffix.lower()

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            paths_to_delete.append(
                f"{hospital_id}/{file_name}"
            )

        if paths_to_delete:
            storage.remove(paths_to_delete)

        return {
            "success": True,
            "message": "Existing hospital logo removed.",
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                "Failed to remove old hospital logo: "
                f"{exc}"
            ),
        }


def delete_hospital_logo(
    hospital_id: str | UUID,
) -> dict:
    """
    Public helper for deleting a hospital logo.

    The bucket remains intact.
    """

    return delete_old_hospital_logo(
        hospital_id
    )


def get_hospital_logo_url(
    hospital_id: str | UUID,
) -> str | None:
    """
    Get the public URL of a hospital logo.

    Returns None when no logo exists.
    """

    hospital_id = str(hospital_id)

    try:
        storage = admin_supabase.storage.from_(
            HOSPITAL_LOGO_BUCKET
        )

        files = storage.list(hospital_id)

        if not files:
            return None

        for file in files:
            file_name = file.get("name")

            if not file_name:
                continue

            extension = Path(
                file_name
            ).suffix.lower()

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            file_path = (
                f"{hospital_id}/{file_name}"
            )

            return _public_url(
                HOSPITAL_LOGO_BUCKET,
                file_path,
            )

        return None

    except Exception:
        return None


# ============================================================
# PROFILE PICTURE
# ============================================================

def upload_profile_picture(
    user_id: str | UUID,
    file_bytes: bytes,
    file_name: str,
) -> dict:
    """
    Upload or replace a user's profile picture.

    Storage path:

        profile-pictures/<user_id>/profile.<extension>

    Only one current profile picture is kept.

    The storage bucket itself is NEVER deleted.
    Existing profile-picture objects belonging to the user
    are removed before the new picture is uploaded.

    The upload also uses upsert=True as a final safeguard
    against Supabase returning a 409 Duplicate.
    """

    valid, message = _validate_image(
        file_bytes,
        file_name,
    )

    if not valid:
        return {
            "success": False,
            "url": None,
            "path": None,
            "message": message,
        }

    user_id = str(user_id)
    extension = _safe_extension(file_name)

    file_path = f"{user_id}/profile{extension}"

    try:
        storage = admin_supabase.storage.from_(
            PROFILE_PICTURE_BUCKET
        )

        # ----------------------------------------------------
        # Remove ALL existing profile-picture objects for
        # this user.
        # ----------------------------------------------------

        delete_result = delete_old_profile_picture(
            user_id
        )

        if not delete_result["success"]:
            return {
                "success": False,
                "url": None,
                "path": None,
                "message": delete_result["message"],
            }

        # ----------------------------------------------------
        # Upload the new profile picture.
        #
        # IMPORTANT:
        # upsert=True means that even if Supabase still sees
        # the same object path, it will replace the object
        # instead of returning:
        #
        # 409 Duplicate
        # The resource already exists
        # ----------------------------------------------------

        storage.upload(
            file_path,
            file_bytes,
            {
                "content-type": _content_type(file_name),
                "upsert": "true",
            },
        )

        # ----------------------------------------------------
        # Generate public URL.
        # ----------------------------------------------------

        url = _public_url(
            PROFILE_PICTURE_BUCKET,
            file_path,
        )

        return {
            "success": True,
            "url": url,
            "path": file_path,
            "message": (
                "Profile picture uploaded successfully."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "url": None,
            "path": None,
            "message": (
                "Failed to upload profile picture: "
                f"{exc}"
            ),
        }


def delete_old_profile_picture(
    user_id: str | UUID,
) -> dict:
    """
    Delete all existing profile-picture objects
    belonging to a user.

    IMPORTANT:
        This does NOT delete the profile-pictures bucket.

    It only deletes files inside:

        profile-pictures/<user_id>/

    This handles old JPG, PNG, WEBP, and any other image
    object that may have been left behind.
    """

    user_id = str(user_id)

    try:
        storage = admin_supabase.storage.from_(
            PROFILE_PICTURE_BUCKET
        )

        files = storage.list(user_id)

        # ----------------------------------------------------
        # Nothing exists.
        # ----------------------------------------------------

        if not files:
            return {
                "success": True,
                "message": (
                    "No existing profile picture found."
                ),
            }

        paths_to_delete = []

        for file in files:
            file_name = file.get("name")

            if not file_name:
                continue

            extension = Path(
                file_name
            ).suffix.lower()

            # ------------------------------------------------
            # Only delete image files.
            # ------------------------------------------------

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            paths_to_delete.append(
                f"{user_id}/{file_name}"
            )

        # ----------------------------------------------------
        # Delete all image objects found.
        # ----------------------------------------------------

        if paths_to_delete:
            storage.remove(paths_to_delete)

        return {
            "success": True,
            "message": (
                "Existing profile picture removed."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                "Failed to remove old profile picture: "
                f"{exc}"
            ),
        }


def delete_profile_picture(
    user_id: str | UUID,
) -> dict:
    """
    Public helper for deleting a user's profile picture.

    The bucket remains intact.
    Only the user's stored image objects are removed.
    """

    return delete_old_profile_picture(
        user_id
    )


def get_profile_picture_url(
    user_id: str | UUID,
) -> str | None:
    """
    Get the public URL of a user's current profile picture.

    Returns None when no profile picture exists.
    """

    user_id = str(user_id)

    try:
        storage = admin_supabase.storage.from_(
            PROFILE_PICTURE_BUCKET
        )

        files = storage.list(user_id)

        if not files:
            return None

        for file in files:
            file_name = file.get("name")

            if not file_name:
                continue

            extension = Path(
                file_name
            ).suffix.lower()

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            file_path = (
                f"{user_id}/{file_name}"
            )

            return _public_url(
                PROFILE_PICTURE_BUCKET,
                file_path,
            )

        return None

    except Exception:
        return None