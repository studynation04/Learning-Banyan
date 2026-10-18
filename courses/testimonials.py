"""Validation for student and parent testimonial uploads."""

from __future__ import annotations

import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import Testimonial

MIN_MESSAGE_LENGTH = 20
MAX_MESSAGE_LENGTH = 3000
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 30 * 1024 * 1024
MAX_SUBMISSIONS_PER_EMAIL_PER_DAY = 5

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ATTACHMENT_EXTENSIONS = PHOTO_EXTENSIONS | {
    "pdf",
    "mp4",
    "webm",
    "mov",
    "mp3",
    "m4a",
    "wav",
}
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ATTACHMENT_TYPES = PHOTO_TYPES | {
    "application/pdf",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
}
GENERIC_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
PHONE_RE = re.compile(r"^[0-9+\-().\s]{7,40}$")


def published_testimonials():
    return Testimonial.objects.filter(status=Testimonial.STATUS_APPROVED).order_by(
        "-is_featured", "display_order", "-published_at", "-created_at"
    )


def _extension(filename: str) -> str:
    base = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if "." not in base or base.startswith("."):
        return ""
    return base.rsplit(".", 1)[-1]


def _content_type(uploaded) -> str:
    return (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()


def _looks_like_image(uploaded) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return True
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as image:
            image.verify()
        return True
    except Exception:
        return False
    finally:
        try:
            uploaded.seek(0)
        except Exception:
            pass


def upload_error(uploaded, *, kind: str) -> str:
    """Return an error message, or an empty string when the file is acceptable."""
    if not uploaded:
        return ""
    if kind == "photo":
        allowed_ext = PHOTO_EXTENSIONS
        allowed_types = PHOTO_TYPES
        max_bytes = MAX_PHOTO_BYTES
        label = "Photo"
    else:
        allowed_ext = ATTACHMENT_EXTENSIONS
        allowed_types = ATTACHMENT_TYPES
        max_bytes = MAX_ATTACHMENT_BYTES
        label = "File"

    ext = _extension(getattr(uploaded, "name", ""))
    if ext not in allowed_ext:
        return f"{label} must be one of: {', '.join(sorted(allowed_ext))}."

    size = getattr(uploaded, "size", 0) or 0
    if size <= 0:
        return f"{label} is empty."
    if size > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        return f"{label} must be {limit_mb} MB or smaller."

    content_type = _content_type(uploaded)
    if content_type not in GENERIC_TYPES and content_type not in allowed_types:
        return f"{label} type is not allowed."

    if ext in PHOTO_EXTENSIONS and not _looks_like_image(uploaded):
        return f"{label} is not a valid image."
    return ""


def submission_errors(data, files, *, email_for_limit: str = "") -> list[str]:
    """Validate a public testimonial submission. `data` is a dict of cleaned strings."""
    errors = []
    role = data.get("role") or ""
    name = data.get("name") or ""
    email = data.get("email") or ""
    phone = data.get("phone") or ""
    message = data.get("message") or ""
    rating = data.get("rating")
    consent = bool(data.get("consent"))

    if role not in {Testimonial.ROLE_STUDENT, Testimonial.ROLE_PARENT}:
        errors.append("Choose Student or Parent.")
    if not name:
        errors.append("Name is required.")
    elif len(name) > 150:
        errors.append("Name is too long.")
    if not email:
        errors.append("Email is required.")
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors.append("Enter a valid email address.")
        if len(email) > 254:
            errors.append("Email is too long.")
    if phone and not PHONE_RE.match(phone):
        errors.append("Enter a valid phone number, or leave it blank.")
    if len(data.get("student_name") or "") > 150:
        errors.append("Student name is too long.")
    if len(data.get("class_or_course") or "") > 200:
        errors.append("Class or course is too long.")
    if rating is not None and rating not in {1, 2, 3, 4, 5}:
        errors.append("Rating must be from 1 to 5.")
    if len(message) < MIN_MESSAGE_LENGTH:
        errors.append(
            f"Testimonial must be at least {MIN_MESSAGE_LENGTH} characters."
        )
    elif len(message) > MAX_MESSAGE_LENGTH:
        errors.append("Testimonial is too long.")
    if not consent:
        errors.append("Please allow Learning Banyan to publish this testimonial.")

    photo_error = upload_error(files.get("photo"), kind="photo")
    if photo_error:
        errors.append(photo_error)
    attachment_error = upload_error(files.get("attachment"), kind="attachment")
    if attachment_error:
        errors.append(attachment_error)

    if email and email_for_limit and not any(
        err.startswith("Enter a valid email") or err == "Email is required."
        for err in errors
    ):
        since = timezone.now() - timedelta(hours=24)
        recent = Testimonial.objects.filter(
            email__iexact=email_for_limit, created_at__gte=since
        ).count()
        if recent >= MAX_SUBMISSIONS_PER_EMAIL_PER_DAY:
            errors.append(
                "You have already sent several testimonials today. Please try again tomorrow."
            )
    return errors
