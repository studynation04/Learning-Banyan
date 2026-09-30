"""View-only media: block forced downloads of office files and prefer inline display."""

from django.http import HttpResponse


class InlineMediaMiddleware:
    """
    - Prefer Content-Disposition: inline for media (view, not Save As attachment)
    - Block direct browser navigation to Office files (.ppt/.pptx/etc.) which
      would otherwise auto-download because browsers cannot display them.
    - For /media/resources/: also block top-level PDF/file opens so users
      cannot download by opening the raw media URL in a new tab.
    """

    PROTECTED_PREFIXES = (
        "/media/blog_images/",
        "/media/blog_media/",
        "/media/resources/",
        "/media/resource_previews/",
        "/media/course_thumbnails/",
        "/media/course_content/",
        "/media/discussion_images/",
        "/media/question_equations/",
    )

    # Opening these as a top-level document forces a download in browsers.
    OFFICE_EXTS = (".ppt", ".pptx", ".pps", ".ppsx", ".doc", ".docx", ".xls", ".xlsx")

    # Resource files that must only be embedded (iframe), never top-level download.
    RESOURCE_BLOCK_EXTS = OFFICE_EXTS + (".pdf", ".zip", ".rar", ".7z", ".epub")

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_top_level_navigation(self, request):
        fetch_dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
        fetch_mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
        # iframe / embed / object / empty (range requests from PDF viewer) = allow
        if fetch_dest in ("iframe", "embed", "object", "image", "video", "audio", "empty"):
            return False
        if fetch_mode in ("no-cors", "cors", "same-origin") and fetch_dest == "":
            # Subresource / PDF stream from embedded viewer
            return False
        is_navigation = fetch_dest in ("document",) or fetch_mode == "navigate"
        if not fetch_dest and not fetch_mode and request.method == "GET":
            accept = (request.headers.get("Accept") or "").lower()
            if "text/html" in accept:
                is_navigation = True
        return is_navigation

    # Blog media that must only be embedded (not opened as a top-level download tab).
    BLOG_BLOCK_EXTS = OFFICE_EXTS + (
        ".pdf",
        ".mp4",
        ".webm",
        ".ogg",
        ".ogv",
        ".mov",
        ".m4v",
        ".zip",
        ".rar",
        ".7z",
    )

    def _blocked_course_media(self, request):
        """Course files stay on disk, but only an enrolled student or an admin may read them."""
        from urllib.parse import unquote

        from courses.models import (
            CourseContent,
            StudyMaterial,
            user_can_view_course_materials,
        )

        raw = unquote(request.path or "")
        lower = raw.lower()
        if not (
            lower.startswith("/media/course_content/")
            or lower.startswith("/media/study_materials/")
        ):
            return None
        try:
            rel = raw[len("/media/") :] if lower.startswith("/media/") else raw
            if lower.startswith("/media/course_content/"):
                item = (
                    CourseContent.objects.select_related("course").filter(file=rel).first()
                )
            else:
                item = (
                    StudyMaterial.objects.select_related("course").filter(file=rel).first()
                )
            if item is not None and user_can_view_course_materials(
                request.user, item.course
            ):
                return None
        except Exception:
            pass
        return HttpResponse(
            "Enroll in the course to view this file.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )

    def __call__(self, request):
        blocked = self._blocked_course_media(request)
        if blocked is not None:
            return blocked
        path = (request.path or "").lower()

        try:
            if any(path.startswith(p) for p in self.PROTECTED_PREFIXES):
                # Resources: block top-level open of raw media files
                if path.startswith("/media/resource_previews/"):
                    return HttpResponse(
                        "Downloading this file is not allowed. "
                        "Open the Resources page to view content online only.",
                        status=403,
                        content_type="text/plain; charset=utf-8",
                    )

                if path.startswith("/media/resources/"):
                    if self._is_top_level_navigation(request):
                        return HttpResponse(
                            "Downloading this file is not allowed. "
                            "Open the Resources page to view content online only.",
                            status=403,
                            content_type="text/plain; charset=utf-8",
                        )
                    fetch_dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
                    if fetch_dest in ("document",):
                        return HttpResponse(
                            "Downloading this file is not allowed.",
                            status=403,
                            content_type="text/plain; charset=utf-8",
                        )

                # Blog media/images: block top-level open of PDF/video/office
                # (images still load for <img>; PDF loads inside iframe).
                if path.startswith("/media/blog_media/") or path.startswith(
                    "/media/blog_images/"
                ):
                    if path.endswith(self.BLOG_BLOCK_EXTS) and self._is_top_level_navigation(
                        request
                    ):
                        return HttpResponse(
                            "Downloading this file is not allowed. "
                            "Open the Blog page to view content online only.",
                            status=403,
                            content_type="text/plain; charset=utf-8",
                        )

                if path.endswith(self.OFFICE_EXTS) and not path.startswith(
                    "/media/resources/"
                ):
                    if self._is_top_level_navigation(request):
                        return HttpResponse(
                            "Downloading this file is not allowed. "
                            "Open the page to view content online only.",
                            status=403,
                            content_type="text/plain; charset=utf-8",
                        )
        except Exception:
            pass  # fall through to normal response

        response = self.get_response(request)

        try:
            if any((request.path or "").startswith(p) for p in self.PROTECTED_PREFIXES):
                response["Content-Disposition"] = "inline"
                response["X-Content-Type-Options"] = "nosniff"
                response["X-Frame-Options"] = "SAMEORIGIN"
                if "Cache-Control" not in response:
                    response["Cache-Control"] = "private, max-age=3600"
                low = (request.path or "").lower()
                if (
                    low.startswith("/media/resources/")
                    or low.startswith("/media/resource_previews/")
                    or low.startswith("/media/blog_media/")
                ):
                    response["X-Robots-Tag"] = "noindex, noarchive, nosnippet"
                    response["Cache-Control"] = "private, no-store"
        except Exception:
            pass

        return response
