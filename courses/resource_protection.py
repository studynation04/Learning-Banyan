"""Helpers for view-only Resources (PDF / Word / images) without download links."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import time
from html import escape
from pathlib import Path

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse

logger = logging.getLogger(__name__)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
DOC_EXTS = {".doc"}
TEXT_EXTS = {".txt", ".md", ".csv"}


def resource_file_ext(resource) -> str:
    name = ""
    if getattr(resource, "file", None) and resource.file:
        name = getattr(resource.file, "name", "") or ""
    return Path(name).suffix.lower()


def resource_preview_kind(resource) -> str:
    """Return: pdf | docx | doc | image | text | none | unknown"""
    if not getattr(resource, "file", None) or not resource.file:
        return "none"
    ext = resource_file_ext(resource)
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in DOC_EXTS:
        return "doc"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in TEXT_EXTS:
        return "text"
    return "unknown"


def guess_content_type(path_or_name: str) -> str:
    ctype, _ = mimetypes.guess_type(path_or_name)
    return ctype or "application/octet-stream"


def is_top_level_file_navigation(request) -> bool:
    """True when the browser is opening the file as a document (download/tab)."""
    fetch_dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
    fetch_mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()

    # Embedded viewers / range streams
    if fetch_dest in (
        "iframe",
        "embed",
        "object",
        "image",
        "video",
        "audio",
        "empty",
    ):
        return False
    if fetch_mode in ("cors", "same-origin", "no-cors") and fetch_dest in ("", "empty"):
        return False

    if fetch_dest == "document" or fetch_mode == "navigate":
        return True

    if not fetch_dest and not fetch_mode and request.method == "GET":
        accept = (request.headers.get("Accept") or "").lower()
        if "text/html" in accept and "application/pdf" not in accept:
            return True
        # Explicit download intent
        if "attachment" in (request.headers.get("Content-Disposition") or "").lower():
            return True

    return False


def forbidden_download_response():
    return HttpResponse(
        "Downloading this resource is not allowed. "
        "Open it from the Resources page to view online only.",
        status=403,
        content_type="text/plain; charset=utf-8",
    )


_PLACEHOLDER_RE = re.compile(
    r"\x02(?:OMATH(omatheq\d+)|IMGRID(rId[^\x02]+))\x02"
)
_ONLY_MATH_RE = re.compile(r"\x02OMATHomatheq\d+\x02")
_BROWSER_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


def _publish_resource_image(blob: bytes, ext: str) -> str:
    """Store an equation/image once, keyed by content, and return its URL."""
    ext = (ext or "png").lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in _BROWSER_IMAGE_EXTS or not blob or len(blob) > 6_000_000:
        return ""
    digest = hashlib.md5(blob).hexdigest()
    fname = f"resource_equations/{digest}.{ext}"
    if not default_storage.exists(fname):
        default_storage.save(fname, ContentFile(blob))
    try:
        return default_storage.url(fname)
    except Exception:
        return ""


def _docx_image_urls(document, work_dir: str) -> dict:
    """Map Word image relationship ids to browser URLs (WMF/EMF converted to PNG)."""
    from admin_panel.docx_question_parser import (
        _batch_convert_images,
        _enhance_equation_pngs_parallel,
    )

    image_dir = os.path.join(work_dir, "equations")
    os.makedirs(image_dir, exist_ok=True)
    rid_to_src = {}
    rid_to_ext = {}
    need_convert = []
    blob_hash_to_path = {}

    for rel_id, rel in document.part.rels.items():
        if "image" not in (getattr(rel, "reltype", "") or ""):
            continue
        try:
            target = rel.target_part
            ext = (target.partname.ext or "").lower().lstrip(".")
            blob = target.blob
        except Exception:
            continue
        if not blob:
            continue
        digest = hashlib.md5(blob).hexdigest()
        if digest in blob_hash_to_path:
            src = blob_hash_to_path[digest]
        else:
            src = os.path.join(image_dir, f"{digest}.{ext or 'bin'}")
            with open(src, "wb") as handle:
                handle.write(blob)
            blob_hash_to_path[digest] = src
            if ext in ("wmf", "emf"):
                need_convert.append(src)
        rid_to_src[rel_id] = src
        rid_to_ext[rel_id] = ext or "bin"

    converted = _batch_convert_images(need_convert, "png", image_dir)
    try:
        _enhance_equation_pngs_parallel(list(converted.values()))
    except Exception:
        logger.exception("Could not resize resource equation images")

    rid_to_url = {}
    for rid, src in rid_to_src.items():
        path = converted.get(src)
        ext = "png"
        if not path:
            ext = rid_to_ext.get(rid) or ""
            if ext in _BROWSER_IMAGE_EXTS and os.path.exists(src):
                path = src
            else:
                continue
        if not path or not os.path.exists(path):
            continue
        with open(path, "rb") as handle:
            blob = handle.read()
        url = _publish_resource_image(blob, ext if path == src else "png")
        if url:
            rid_to_url[rid] = url
    return rid_to_url


def _placeholders_to_html(text: str, latex_by_key: dict, rid_to_url: dict) -> str:
    """Escape document text and turn equation placeholders into KaTeX or images."""
    from admin_panel.docx_question_parser import _drop_images_next_to_omath, _eq_img_html
    from admin_panel.omml_to_latex import clean_latex

    if not text:
        return ""
    text = _drop_images_next_to_omath(text, latex_by_key)
    display = bool(_ONLY_MATH_RE.fullmatch(text.strip()))
    parts = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        parts.append(escape(text[cursor:match.start()]))
        math_key = match.group(1)
        image_rid = match.group(2)
        if math_key:
            latex = clean_latex(latex_by_key.get(math_key) or "")
            if latex:
                latex = latex.replace("$", "")
                wrapped = f"$${escape(latex)}$$" if display else f"${escape(latex)}$"
                parts.append(wrapped)
        elif image_rid:
            url = rid_to_url.get(image_rid) or ""
            if url and '"' not in url and "<" not in url:
                parts.append(_eq_img_html(url))
        cursor = match.end()
    parts.append(escape(text[cursor:]))
    html = "".join(parts).replace("\n", "<br>")
    return html.strip()


def _open_docx(file_field):
    from docx import Document

    path = getattr(file_field, "path", None)
    cleanup = None
    if not (path and os.path.exists(path)):
        cleanup = tempfile.mkdtemp(prefix="resource_docx_src_")
        path = os.path.join(cleanup, "source.docx")
        _copy_file_field(file_field, path)
    try:
        try:
            return Document(path)
        except Exception as first_error:
            # Older Word/LibreOffice files use purl.oclc.org relationship ids.
            # python-docx only accepts the standard officeDocument relationship.
            from admin_panel.docx_question_parser import normalize_ooxml_namespaces

            fixed_dir = tempfile.mkdtemp(prefix="resource_docx_norm_")
            fixed = os.path.join(fixed_dir, "fixed.docx")
            try:
                normalize_ooxml_namespaces(path, fixed)
                return Document(fixed)
            except Exception:
                raise first_error
            finally:
                shutil.rmtree(fixed_dir, ignore_errors=True)
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)


def _docx_cache_key(file_field) -> str:
    name = getattr(file_field, "name", "") or ""
    try:
        size = int(getattr(file_field, "size", 0) or 0)
    except Exception:
        size = 0
    mtime = 0
    path = getattr(file_field, "path", None)
    if path and os.path.exists(path):
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
    return f"resource-docx-html-v2:{name}:{size}:{mtime}"


def _render_docx_html(document) -> str:
    from admin_panel.docx_question_parser import (
        _paragraph_text_with_placeholders,
        _render_omath_batch_to_latex,
        _has_numbering,
    )

    body = document.element.body
    para_by_el = {paragraph._p: paragraph for paragraph in document.paragraphs}
    table_by_el = {table._tbl: table for table in document.tables}
    omath_registry = []
    blocks = []

    for child in list(body):
        tag = child.tag or ""
        if tag.endswith("}p"):
            para = para_by_el.get(child)
            if para is None:
                continue
            blocks.append(
                ("p", para, _paragraph_text_with_placeholders(para, omath_registry))
            )
        elif tag.endswith("}tbl"):
            table = table_by_el.get(child)
            if table is None:
                continue
            rows = []
            for row in table.rows:
                cells = []
                seen = set()
                for cell in row.cells:
                    # Merged cells are repeated by python-docx; keep the first.
                    cell_id = id(cell._tc)
                    if cell_id in seen:
                        continue
                    seen.add(cell_id)
                    bits = [
                        _paragraph_text_with_placeholders(para, omath_registry)
                        for para in cell.paragraphs
                    ]
                    cells.append(bits)
                rows.append(cells)
            blocks.append(("table", rows))

    work_dir = tempfile.mkdtemp(prefix="resource_docx_")
    try:
        latex_by_key = _render_omath_batch_to_latex(omath_registry, work_dir)
        try:
            rid_to_url = _docx_image_urls(document, work_dir)
        except Exception:
            logger.exception("Resource Word image extraction failed")
            rid_to_url = {}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    parts = []
    for kind, payload, *rest in (
        (block[0], block[1], *block[2:]) for block in blocks
    ):
        if kind == "p":
            para = payload
            raw = rest[0] if rest else ""
            inner = _placeholders_to_html(raw, latex_by_key, rid_to_url)
            if not inner:
                parts.append("<div class='rd-para-spacer'></div>")
                continue
            style = (para.style.name if para.style else "") or ""
            tag = "p"
            cls = "rd-para"
            if style.startswith("Heading"):
                level = "".join(ch for ch in style if ch.isdigit()) or "2"
                try:
                    tag = f"h{min(int(level), 4)}"
                except ValueError:
                    tag = "h2"
                cls = "rd-heading"
            elif _has_numbering(para):
                inner = "• " + inner
            parts.append(f"<{tag} class='{cls}'>{inner}</{tag}>")
        else:
            rows = payload
            parts.append("<table class='rd-table'>")
            for cells in rows:
                parts.append("<tr>")
                for bits in cells:
                    inner = "<br>".join(
                        html
                        for html in (
                            _placeholders_to_html(bit, latex_by_key, rid_to_url)
                            for bit in bits
                        )
                        if html
                    )
                    parts.append(f"<td>{inner}</td>")
                parts.append("</tr>")
            parts.append("</table>")

    if not any("rd-para-spacer" not in part for part in parts):
        return "<p class='rd-preview-error'>This document has no readable text.</p>"
    return "\n".join(parts)


def docx_to_protected_html(file_field) -> str:
    """Convert a .docx FileField to HTML, keeping equations as KaTeX or images."""
    try:
        import docx  # noqa: F401
    except ImportError:
        return (
            "<p class='rd-preview-error'>Word preview is unavailable "
            "(python-docx not installed).</p>"
        )

    cache_key = _docx_cache_key(file_field)
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        document = _open_docx(file_field)
    except Exception as exc:
        return (
            f"<p class='rd-preview-error'>Could not open this Word document "
            f"for protected preview ({escape(str(exc)[:120])}).</p>"
        )

    try:
        html = _render_docx_html(document)
    except Exception as exc:
        logger.exception("Resource Word preview failed")
        return (
            f"<p class='rd-preview-error'>Could not preview this Word document "
            f"({escape(str(exc)[:120])}).</p>"
        )

    if html and "rd-preview-error" not in html:
        cache.set(cache_key, html, 60 * 60 * 12)
    return html


def _copy_file_field(file_field, dest_path: str) -> None:
    path = getattr(file_field, "path", None)
    if path and os.path.isfile(path):
        shutil.copyfile(path, dest_path)
        return
    file_field.open("rb")
    try:
        with open(dest_path, "wb") as handle:
            shutil.copyfileobj(file_field, handle)
    finally:
        try:
            file_field.close()
        except Exception:
            pass


def _file_identity(file_field):
    name = getattr(file_field, "name", "") or ""
    try:
        size = int(getattr(file_field, "size", 0) or 0)
    except Exception:
        size = 0
    mtime = 0
    path = getattr(file_field, "path", None)
    if path and os.path.exists(path):
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
    return name, size, mtime


def word_preview_storage_name(file_field) -> str:
    name, size, mtime = _file_identity(file_field)
    digest = hashlib.sha1(f"{name}:{size}:{mtime}".encode("utf-8")).hexdigest()
    # v2 is Word's own PDF export. An earlier LibreOffice export dropped equations.
    return f"resource_previews/v2/{digest}.pdf"


def _convert_word_source_to_pdf(src_path: str, outdir: str) -> str:
    """Export a .doc/.docx to PDF so the reader shows the original layout."""
    from admin_panel.docx_question_parser import (
        _soffice_convert_document,
        _word_com_convert_document,
    )

    # Word keeps equations and the original page. LibreOffice is the headless fallback.
    if sys.platform == "win32":
        pdf_path = _word_com_convert_document(src_path, "pdf", outdir)
        if pdf_path:
            return pdf_path
    pdf_path = _soffice_convert_document(src_path, "pdf", outdir)
    return pdf_path or ""


def ensure_word_preview_pdf(file_field) -> str:
    """
    Return the storage name of a cached PDF of this Word file, or ''.

    The PDF is the document as Word laid it out (text, equations, images).
    """
    ext = Path(getattr(file_field, "name", "") or "").suffix.lower()
    if ext not in (".doc", ".docx"):
        return ""

    storage_name = word_preview_storage_name(file_field)
    if default_storage.exists(storage_name):
        return storage_name

    lock_key = "lock:" + storage_name
    if not cache.add(lock_key, "1", 200):
        for _ in range(90):
            if default_storage.exists(storage_name):
                return storage_name
            time.sleep(1)
        return storage_name if default_storage.exists(storage_name) else ""

    work_dir = tempfile.mkdtemp(prefix="resource_wordpdf_")
    try:
        src = os.path.join(work_dir, "source" + ext)
        _copy_file_field(file_field, src)
        pdf_path = _convert_word_source_to_pdf(src, work_dir)
        if not pdf_path or not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 8:
            logger.warning("Word preview PDF was not created for %s", getattr(file_field, "name", ""))
            return ""
        if default_storage.exists(storage_name):
            return storage_name
        with open(pdf_path, "rb") as handle:
            default_storage.save(storage_name, ContentFile(handle.read()))
        return storage_name
    except Exception:
        logger.exception("Word preview PDF failed for %s", getattr(file_field, "name", ""))
        return ""
    finally:
        cache.delete(lock_key)
        shutil.rmtree(work_dir, ignore_errors=True)


def open_word_preview_pdf(file_field):
    """Open the cached Word-as-PDF, creating it on first view. None if it cannot."""
    storage_name = ensure_word_preview_pdf(file_field)
    if not storage_name:
        return None
    try:
        return default_storage.open(storage_name, "rb")
    except Exception:
        logger.exception("Could not open cached Word preview %s", storage_name)
        return None


def legacy_doc_to_protected_html(file_field) -> str:
    """Fallback when PDF export is unavailable: convert .doc and show its text."""
    from admin_panel.docx_question_parser import _convert_document_to_docx

    work_dir = tempfile.mkdtemp(prefix="resource_doc_")
    try:
        src = os.path.join(work_dir, "source.doc")
        _copy_file_field(file_field, src)
        docx_path = _convert_document_to_docx(src, work_dir)
        if not docx_path:
            return (
                "<p class='rd-preview-error'>Could not open this Word file. "
                "Save it as .docx and upload it again.</p>"
            )

        class _Converted:
            def __init__(self, path):
                self.path = path
                self.name = os.path.basename(path)
                self.size = os.path.getsize(path)

        return docx_to_protected_html(_Converted(docx_path))
    except Exception as exc:
        logger.exception("Legacy .doc HTML preview failed")
        return (
            f"<p class='rd-preview-error'>Could not open this Word file "
            f"({escape(str(exc)[:120])}).</p>"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def text_file_to_protected_html(file_field) -> str:
    try:
        file_field.open("rb")
        try:
            raw = file_field.read()
        finally:
            file_field.close()
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return f"<p class='rd-preview-error'>Could not read file ({escape(str(exc)[:100])}).</p>"
    # Cap huge files
    if len(text) > 200_000:
        text = text[:200_000] + "\n\n… (preview truncated)"
    return f"<pre class='rd-pre'>{escape(text)}</pre>"
