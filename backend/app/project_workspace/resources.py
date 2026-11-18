"""Bounded local resource intake. Imported bytes are data, never executable instructions."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import posixpath
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

from ..media import MediaSettings, probe_frame_timing, validate_frame_correspondence
from ..storage import WorkflowError
from .models import ExtractedBlock, Project, Resource, ResourceFolder, invalidate, now, resource_is_trashed, uid

DOCUMENTS = {".docx", ".pdf", ".xlsx", ".csv", ".pptx", ".txt", ".md", ".tsv", ".rtf"}
VIDEOS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
AUDIOS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
LEGACY = {".doc", ".xls", ".ppt"}
MAX_TEXT = 1_000_000
MAX_BLOCKS = 4000
MAX_XML = 16 * 1024 * 1024
MAX_ARCHIVE = 80 * 1024 * 1024
MAX_PAGES = 100
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _resource(project: Project, resource_id: str, *, include_trashed=False) -> Resource:
    result = next((item for item in project.resources if item.id == resource_id), None)
    if result is None:
        raise WorkflowError("resource_not_found", "This resource does not belong to this project.", 404)
    if not include_trashed and resource_is_trashed(project, result):
        raise WorkflowError("resource_trashed", "This source is in Trash. Restore the file or its containing folder to use it; saved evidence and history are retained.", 410)
    return result


def _logical_name(value, *, folder=False):
    if not isinstance(value, str):
        raise WorkflowError("invalid_resource_name", "Use a readable file or folder name.", 422)
    value = value.strip()
    if not value or value in {".", ".."} or len(value) > (200 if folder else 250) or re.search(r"[/\\\x00-\x1f]", value):
        raise WorkflowError("invalid_resource_name", "Use a name without path separators or control characters.", 422)
    return value


def _folder(project, folder_id, *, active=True):
    folder = next((item for item in project.resource_folders if item.id == folder_id), None)
    if folder is None:
        raise WorkflowError("folder_not_found", "This folder does not belong to the project.", 404)
    if active:
        folders, current, seen = {item.id: item for item in project.resource_folders}, folder, set()
        while current and current.id not in seen:
            seen.add(current.id)
            if current.trashed_at:
                raise WorkflowError("folder_trashed", "This folder is in Trash. Restore it or choose another destination.", 410)
            current = folders.get(current.parent_id)
    return folder


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _safe_path(root: Path, relative: str, *, create_parent: bool = False) -> Path:
    """A persisted path is still untrusted; never follow a project symlink."""
    part = PurePosixPath(relative)
    if part.is_absolute() or not part.parts or any(item in {"", ".", ".."} for item in part.parts) or "\\" in relative:
        raise WorkflowError("unsafe_resource_path", "This resource has an invalid project location.", 422)
    root = root.resolve()
    result = root.joinpath(*part.parts)
    if any(path.is_symlink() for path in [result, *result.parents] if path != root and root in path.parents):
        raise WorkflowError("unsafe_resource_path", "Linked files cannot replace project-owned resources.", 422)
    if root not in result.resolve().parents:
        raise WorkflowError("unsafe_resource_path", "Resource location must stay inside the project.", 422)
    if create_parent:
        result.parent.mkdir(parents=True, exist_ok=True)
    return result


def _source_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise WorkflowError("invalid_source_url", "Use a valid HTTP or HTTPS source URL.", 422) from exc
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
        raise WorkflowError("invalid_source_url", "Use an HTTP or HTTPS source URL without credentials.", 422)
    return value


def _filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(" .")
    if not name:
        name = "uploaded-file"
    return name[:180]


def _kind(suffix: str) -> str:
    return ("video" if suffix in VIDEOS else "audio" if suffix in AUDIOS else
            "image" if suffix in IMAGES else "document" if suffix in DOCUMENTS | LEGACY else "other")


def _run(command: list[str], timeout: float = 60) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ValueError(f"Required local tool is unavailable: {Path(command[0]).name}.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Local extraction exceeded its time limit. The original file is retained.") from exc
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} could not process this file. The original is retained; check its format and encryption.")
    return result.stdout


def _xml(archive: zipfile.ZipFile, name: str):
    info = archive.getinfo(name)
    if info.file_size > MAX_XML:
        raise ValueError("An Office XML part exceeds the extraction limit.")
    raw = archive.read(name)
    # OOXML may declare UTF-16; strip NUL bytes only for declaration detection,
    # then let the XML parser handle the untouched document encoding.
    declarations = raw.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
        raise ValueError("Document XML entity declarations are unsupported.")
    return ET.fromstring(raw)


def _office(path: Path):
    archive = zipfile.ZipFile(path)
    if len(archive.infolist()) > 10000 or sum(item.file_size for item in archive.infolist()) > MAX_ARCHIVE:
        archive.close()
        raise ValueError("Expanded Office contents exceed the extraction limit.")
    if any(item.flag_bits & 1 for item in archive.infolist()):
        archive.close()
        raise ValueError("Encrypted Office files need an unprotected working copy.")
    return archive


def _plain_text(path: Path) -> tuple[str, list[str]]:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), []
    try:
        return raw.decode("utf-8-sig"), []
    except UnicodeDecodeError:
        return raw.decode("cp1252"), ["Decoded as Windows-1252 after UTF-8 failed; review accented and non-Latin text."]


def extract_office(path: Path) -> tuple[list[ExtractedBlock], list[str]]:
    """Read text and cached cell values only; never execute Office macros/formulas."""
    blocks, warnings = [], []
    with _office(path) as archive:
        if path.suffix.lower() == ".docx":
            document = _xml(archive, "word/document.xml")
            for index, paragraph in enumerate(document.iter(NS_W + "p"), 1):
                text = "".join(item.text or "" for item in paragraph.iter(NS_W + "t")).strip()
                if text:
                    blocks.append(ExtractedBlock(locator=f"Paragraph {index}", text=text))
                if len(blocks) >= MAX_BLOCKS:
                    warnings.append("Only the first 4000 text blocks were extracted.")
                    break
            warnings.append("DOCX text includes table paragraphs. Embedded images, tracked-change meaning, headers and complex layout require review in the original.")
        elif path.suffix.lower() == ".pptx":
            slides = sorted((name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)), key=lambda name: int(re.search(r"slide(\d+)", name)[1]))
            if "ppt/presentation.xml" in archive.namelist() and "ppt/_rels/presentation.xml.rels" in archive.namelist():
                relations = {item.attrib.get("Id"): posixpath.normpath(posixpath.join("ppt", item.attrib.get("Target", "")))
                             for item in _xml(archive, "ppt/_rels/presentation.xml.rels") if item.attrib.get("TargetMode") != "External"}
                ordered = [relations.get(item.attrib.get(NS_R + "id")) for item in _xml(archive, "ppt/presentation.xml").iter()
                           if item.tag.endswith("}sldId")]
                if ordered and all(name in slides for name in ordered):
                    slides = ordered
                else:
                    warnings.append("Presentation ordering could not be resolved; slides are shown in file order.")
            for number, slide in enumerate(slides[:MAX_PAGES], 1):
                texts = [item.text for item in _xml(archive, slide).iter(NS_A + "t") if item.text]
                if texts:
                    blocks.append(ExtractedBlock(locator=f"Slide {number}", text="\n".join(texts)))
                relationships_name = f"ppt/slides/_rels/{PurePosixPath(slide).name}.rels"
                if relationships_name in archive.namelist():
                    for relation in _xml(archive, relationships_name):
                        if relation.attrib.get("TargetMode") == "External" or not relation.attrib.get("Type", "").endswith("/notesSlide"):
                            continue
                        notes_name = posixpath.normpath(posixpath.join("ppt/slides", relation.attrib.get("Target", "")))
                        if not notes_name.startswith("ppt/notesSlides/") or notes_name not in archive.namelist():
                            warnings.append(f"Slide {number} has an unsupported notes relationship.")
                            continue
                        notes = [item.text for item in _xml(archive, notes_name).iter(NS_A + "t") if item.text]
                        if notes:
                            blocks.append(ExtractedBlock(locator=f"Slide {number} notes", text="\n".join(notes)))
            warnings.append("Slide text and notes are extracted; image-only text, charts, animations and layout are not interpreted.")
            if len(slides) > MAX_PAGES:
                warnings.append(f"Only the first {MAX_PAGES} slides were extracted.")
        else:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = ["".join(item.text or "" for item in row.iter(NS_S + "t")) for row in _xml(archive, "xl/sharedStrings.xml").iter(NS_S + "si")]
            relationships = _xml(archive, "xl/_rels/workbook.xml.rels")
            targets = {row.attrib.get("Id"): row.attrib.get("Target", "") for row in relationships if row.attrib.get("TargetMode") != "External"}
            for sheet in _xml(archive, "xl/workbook.xml").iter(NS_S + "sheet"):
                target = targets.get(sheet.attrib.get(NS_R + "id"), "")
                sheet_path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
                if ".." in PurePosixPath(sheet_path).parts or sheet_path not in archive.namelist():
                    warnings.append(f"Sheet {sheet.attrib.get('name', '?')} has an unsupported relationship.")
                    continue
                sheet_name = sheet.attrib.get("name", "Sheet")
                if sheet.attrib.get("state", "visible") != "visible":
                    warnings.append(f"Included hidden sheet: {sheet_name}.")
                tree = _xml(archive, sheet_path)
                for cell in tree.iter(NS_S + "c"):
                    reference = cell.attrib.get("r", "?")
                    kind = cell.attrib.get("t")
                    value = cell.findtext(NS_S + "v", "")
                    if kind == "s":
                        value = shared[int(value)] if value else ""
                    elif kind == "inlineStr":
                        value = "".join(item.text or "" for item in cell.iter(NS_S + "t"))
                    formula = cell.findtext(NS_S + "f")
                    if formula is not None:
                        value = f"Cached value: {value or '[not available]'}; formula: ={formula}"
                    if value:
                        blocks.append(ExtractedBlock(locator=f"{sheet_name}!{reference}", text=value))
                    if len(blocks) >= MAX_BLOCKS:
                        warnings.append("Only the first 4000 populated cells were extracted.")
                        break
                if any(True for _ in tree.iter(NS_S + "mergeCell")):
                    warnings.append(f"Merged cells in {sheet_name}: only their stored values are extracted.")
                if len(blocks) >= MAX_BLOCKS:
                    break
            warnings.append("Spreadsheet formulas are not calculated. Cached values may be stale; number/date formatting, charts and external links require review.")
    return blocks, warnings


def _ocr(path: Path) -> str:
    if shutil.which("tesseract") is None:
        raise ValueError("OCR is unavailable. Install Tesseract locally or supply a text-based copy.")
    return _run(["tesseract", str(path), "stdout", "-l", os.getenv("VIDEO_OCR_LANGUAGES", "eng")], 45).strip()


def extract_pdf(path: Path, cache: Path) -> tuple[list[ExtractedBlock], list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF extraction requires the installed pypdf dependency.") from exc
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        raise ValueError("This PDF is encrypted. Supply an unprotected working copy.")
    blocks, warnings = [], []
    ocr_count = 0
    for index, page in enumerate(reader.pages[:MAX_PAGES], 1):
        text = page.extract_text() or ""
        if not text.strip():
            if shutil.which("pdftoppm") and shutil.which("tesseract") and ocr_count < 10:
                cache.mkdir(parents=True, exist_ok=True)
                prefix = cache / f"page-{index}"
                try:
                    _run(["pdftoppm", "-f", str(index), "-l", str(index), "-singlefile", "-scale-to", "1800", "-png", str(path), str(prefix)], 45)
                    text = _ocr(prefix.with_suffix(".png"))
                    ocr_count += 1
                    warnings.append(f"Page {index} uses OCR; review recognition errors and reading order.")
                except ValueError:
                    warnings.append(f"Page {index}: OCR failed; the original page is retained.")
            else:
                warnings.append(f"Page {index}: no extractable text. OCR requires Tesseract and Poppler; at most 10 image-only pages are processed per import.")
        if text.strip():
            blocks.append(ExtractedBlock(locator=f"Page {index}", text=text.strip()))
    if len(reader.pages) > MAX_PAGES:
        warnings.append(f"Only the first {MAX_PAGES} pages were extracted.")
    return blocks, warnings


class ResourceService:
    def __init__(self, store, settings_provider=None):
        self.store = store
        self.settings_provider = settings_provider
        self.media_settings = MediaSettings.from_env()
        self._verified_playback: dict[str, tuple] = {}

    def create_folder(self, project_id, expected_version, name, parent_id=None):
        folder = ResourceFolder(name=_logical_name(name, folder=True), parent_id=parent_id)
        def change(project):
            if parent_id is not None:
                _folder(project, parent_id)
            project.resource_folders.append(folder)
        return self.store.update(project_id, expected_version, change)

    def edit_folder(self, project_id, expected_version, folder_id, fields):
        if not fields or set(fields) - {"name", "parent_id"}:
            raise WorkflowError("invalid_folder_fields", "Edit only this folder's name and parent folder.", 422)
        def change(project):
            folder = _folder(project, folder_id)
            if "name" in fields:
                folder.name = _logical_name(fields["name"], folder=True)
            if "parent_id" in fields:
                parent_id = fields["parent_id"]
                parent = _folder(project, parent_id) if parent_id is not None else None
                seen = {folder_id}
                while parent is not None:
                    if parent.id in seen:
                        raise WorkflowError("folder_cycle", "A folder cannot be moved into itself or one of its children.", 422)
                    seen.add(parent.id)
                    parent = _folder(project, parent.parent_id) if parent.parent_id is not None else None
                folder.parent_id = parent_id
        return self.store.update(project_id, expected_version, change)

    @staticmethod
    def _require_idle(project, resource_ids):
        if any(resource.id in resource_ids and resource.status == "processing" for resource in project.resources):
            raise WorkflowError("resource_busy", "Wait for this source's processing before moving it to Trash.", 409)
        for job in project.jobs:
            if job.status not in {"queued", "running"}:
                continue
            if job.resource_id in resource_ids:
                raise WorkflowError("resource_busy", "Wait for this source's processing before moving it to Trash.", 409)
            if job.kind == "analyze":
                content = next((item for item in project.contents if item.id == job.content_id), None)
                selected = content.selection if content is not None else project.selection
                if set(selected.resource_ids) & resource_ids:
                    raise WorkflowError("resource_busy", "Wait for the analysis using this source before moving it to Trash.", 409)

    def folder_trash(self, project_id, expected_version, folder_id, *, restore=False):
        def change(project):
            folder = _folder(project, folder_id, active=False)
            if restore:
                if folder.trashed_at is None:
                    return False
                if folder.parent_id:
                    _folder(project, folder.parent_id)
                folder.trashed_at = None
                return
            if folder.trashed_at:
                return False
            affected = {folder_id}
            while True:
                descendants = {item.id for item in project.resource_folders if item.parent_id in affected}
                if descendants.issubset(affected):
                    break
                affected |= descendants
            self._require_idle(project, {resource.id for resource in project.resources if resource.folder_id in affected})
            folder.trashed_at = now()
        return self.store.update(project_id, expected_version, change)

    def edit_resource(self, project_id, expected_version, resource_id, fields):
        if not fields or set(fields) - {"name", "folder_id"}:
            raise WorkflowError("invalid_resource_fields", "Edit only this file's display name and logical folder.", 422)
        def change(project):
            resource = _resource(project, resource_id)
            if "name" in fields:
                resource.name = _logical_name(fields["name"])
            if "folder_id" in fields:
                folder_id = fields["folder_id"] or "folder_inbox"
                _folder(project, folder_id)
                resource.folder_id = folder_id
        return self.store.update(project_id, expected_version, change)

    def move_resources(self, project_id, expected_version, resource_ids, folder_id=None):
        if not resource_ids or len(set(resource_ids)) != len(resource_ids):
            raise WorkflowError("invalid_resource_selection", "Choose each file once for this move.", 422)
        folder_id = folder_id or "folder_inbox"
        def change(project):
            _folder(project, folder_id)
            resources = [_resource(project, resource_id) for resource_id in resource_ids]
            for resource in resources:
                resource.folder_id = folder_id
        return self.store.update(project_id, expected_version, change)

    def resource_trash(self, project_id, expected_version, resource_id, *, restore=False):
        def change(project):
            resource = _resource(project, resource_id, include_trashed=True)
            if restore:
                if resource.folder_id:
                    _folder(project, resource.folder_id)
                if resource.trashed_at is None:
                    return False
                resource.trashed_at = None
                return
            if resource.trashed_at:
                return False
            self._require_idle(project, {resource_id})
            resource.trashed_at = now()
        return self.store.update(project_id, expected_version, change)

    def import_file(self, project_id, expected_version, name, stream, role="reference", origin="upload", source_url=None, provenance="", folder_id=None) -> Project:
        project = self.store.get(project_id)
        if expected_version is not None and project.version != expected_version:
            raise WorkflowError("version_conflict", "This project changed. Reload before importing.", 409)
        name = _filename(name)
        kind = _kind(Path(name).suffix.lower())
        if role not in {"reference", "document", "asset"} or origin not in {"upload", "discovery"}:
            raise WorkflowError("invalid_resource_origin", "Choose a supported resource role and origin.", 422)
        folder_id = folder_id or ("folder_references" if origin == "discovery" else "folder_documents" if role == "document" else "folder_inbox")
        _folder(project, folder_id)
        resource_id = uid("resource")
        category = "documents" if role == "document" else "assets" if role == "asset" else "media"
        relative = f"sources/{category}/{resource_id}/{name}"
        root = self.store.project_dir(project_id)
        destination = _safe_path(root, relative, create_parent=True)
        stage = _safe_path(root, f"staging/{resource_id}.part", create_parent=True)
        digest, size = hashlib.sha256(), 0
        try:
            with stage.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.media_settings.max_bytes:
                        raise WorkflowError("resource_too_large", f"This file exceeds the configured {self.media_settings.max_bytes // (1024 * 1024)} MiB limit.", 422)
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if not size:
                raise WorkflowError("empty_resource", "The uploaded file is empty.", 422)
            resource = Resource(id=resource_id, name=name, kind=kind, role=role, origin=origin,
                                folder_id=folder_id,
                                source_url=_source_url(source_url), provenance=provenance,
                                original_path=relative, sha256=digest.hexdigest(), size_bytes=size,
                                mime_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
            stage.replace(destination)
            try:
                def append(current):
                    _folder(current, folder_id)
                    current.resources.append(resource)
                return self.store.update(project_id, expected_version, append)
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        finally:
            stage.unlink(missing_ok=True)

    def path(self, project_id, resource_id, representation="original") -> Path:
        resource = _resource(self.store.get(project_id), resource_id)
        if representation not in {"original", "playback", "thumbnail"}:
            raise WorkflowError("invalid_representation", "Choose original, playback or thumbnail.", 422)
        relative = resource.original_path if representation == "original" else resource.playback_path if representation == "playback" else resource.thumbnail_path
        if representation == "playback" and relative is None:
            relative = resource.original_path
        if not relative:
            raise WorkflowError("preview_unavailable", "This preview is not available. Retry extraction to rebuild it.", 404)
        path = _safe_path(self.store.project_dir(project_id), relative)
        if not path.is_file():
            if representation == "original":
                def missing(project):
                    item = _resource(project, resource_id)
                    item.status, item.error = "missing", "The project-owned original is missing. Relink the exact original file."
                self.store.update(project_id, None, missing)
            raise WorkflowError("missing_resource", "The saved file is missing. Relink the original or rebuild its preview.", 404)
        if relative == resource.original_path:
            stat = path.stat()
            fingerprint = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, resource.sha256)
            # Analysis/download requests verify every byte. Repeated browser range
            # requests can reuse a verification only while file metadata is unchanged.
            cached = representation != "original" and self._verified_playback.get(str(path)) == fingerprint
            if not cached and _digest(path) != resource.sha256:
                def changed(project):
                    item = _resource(project, resource_id)
                    message = "The project-owned original changed. Relink the exact original; existing evidence is preserved."
                    if item.status == "failed" and item.error == message:
                        return False
                    item.status, item.error = "failed", message
                self.store.update(project_id, None, changed)
                raise WorkflowError("resource_hash_mismatch", "The saved original has changed. Relink the exact original; existing evidence is preserved.", 409)
            after = path.stat()
            if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint[:3]:
                raise WorkflowError("resource_changed", "The original changed while it was being read. Retry after restoring the exact file.", 409)
            self._verified_playback[str(path)] = fingerprint
        return path

    def _media(self, root: Path, resource: Resource, path: Path, *, rebuild_preview=False):
        settings = self.media_settings
        data = json.loads(_run([settings.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format", "-of", "json", str(path)], settings.probe_timeout_seconds))
        streams = data.get("streams", [])
        videos = [item for item in streams if item.get("codec_type") == "video" and not item.get("disposition", {}).get("attached_pic")]
        audios = [item for item in streams if item.get("codec_type") == "audio"]
        duration = float(data.get("format", {}).get("duration", "nan"))
        if not math.isfinite(duration) or not 0 < duration <= settings.max_duration_seconds:
            raise ValueError(f"Use media with a measurable duration up to {settings.max_duration_seconds:g} seconds.")
        if len(audios) > 1:
            raise ValueError("Multiple audio streams are unsupported. Export one intended audio track.")
        metadata = {"duration_seconds": duration, "format_name": data.get("format", {}).get("format_name"),
                    "audio_codec": audios[0].get("codec_name") if audios else None, "has_audio": bool(audios),
                    "audio_track_count": len(audios)}
        if resource.kind == "video":
            if len(videos) != 1:
                raise ValueError("Video intake requires exactly one video stream.")
            video = videos[0]
            width, height = int(video.get("width", 0)), int(video.get("height", 0))
            if not 0 < width <= settings.max_width or not 0 < height <= settings.max_height:
                raise ValueError(f"Video dimensions must be at most {settings.max_width} × {settings.max_height}.")
            if video.get("color_transfer") in {"smpte2084", "arib-std-b67"} or "10" in video.get("pix_fmt", ""):
                raise ValueError("HDR/10-bit video requires a reviewed SDR export before analysis; the original remains stored.")
            timing = probe_frame_timing(path, settings)
            duration = timing.frame_boundaries_seconds[-1]
            metadata.update({"width": width, "height": height, "video_codec": video.get("codec_name"),
                             "pixel_format": video.get("pix_fmt"), "video_profile": video.get("profile"),
                             "duration_seconds": duration, "frame_timing": timing.model_dump(mode="json")})
            _run([settings.ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"], settings.decode_timeout_seconds)
            browser_native = (path.suffix.lower() == ".mp4" and video.get("codec_name") == "h264"
                              and "mp4" in str(metadata["format_name"]).split(",")
                              and video.get("pix_fmt") == "yuv420p"
                              and (not audios or audios[0].get("codec_name") == "aac"))
            if browser_native:
                resource.playback_path = resource.original_path
            else:
                relative = f"cache/playback/{resource.id}-{resource.sha256[:12]}.mp4"
                playback = _safe_path(root, relative, create_parent=True)
                def validated_preview(candidate):
                    probe = json.loads(_run([settings.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format", "-of", "json", str(candidate)], settings.probe_timeout_seconds))
                    candidate_videos = [item for item in probe.get("streams", []) if item.get("codec_type") == "video"]
                    candidate_audios = [item for item in probe.get("streams", []) if item.get("codec_type") == "audio"]
                    if ("mp4" not in probe.get("format", {}).get("format_name", "").split(",")
                            or len(candidate_videos) != 1 or candidate_videos[0].get("codec_name") != "h264"
                            or candidate_videos[0].get("pix_fmt") != "yuv420p"
                            or len(candidate_audios) != len(audios)
                            or any(item.get("codec_name") != "aac" for item in candidate_audios)):
                        raise ValueError("The cached preview is not compatible H.264/AAC MP4.")
                    _run([settings.ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(candidate), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"], settings.decode_timeout_seconds)
                    derivative_timing = probe_frame_timing(candidate, settings)
                    validate_frame_correspondence(path, candidate, timing, derivative_timing, settings)
                    return derivative_timing
                derivative_timing = None
                if playback.is_file() and not rebuild_preview:
                    try:
                        derivative_timing = validated_preview(playback)
                    except (ValueError, KeyError, TypeError):
                        # Disposable bytes are reusable only after compatibility,
                        # full decode and source correspondence have been checked.
                        pass
                if derivative_timing is None:
                    temporary = playback.with_name(playback.stem + ".pending.mp4")
                    try:
                        _run([settings.ffmpeg, "-hide_banner", "-v", "error", "-y", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-c:a", "aac", "-movflags", "+faststart", str(temporary)], settings.transcode_timeout_seconds)
                        derivative_timing = validated_preview(temporary)
                        temporary.replace(playback)
                    finally:
                        temporary.unlink(missing_ok=True)
                resource.playback_path = relative
                metadata["playback_frame_timing"] = derivative_timing.model_dump(mode="json")
                metadata.update({"playback_video_codec": "h264", "playback_pixel_format": "yuv420p",
                                 "playback_audio_codec": "aac" if audios else None, "playback_format_name": "mp4"})
            thumbnail_relative = f"cache/thumbnails/{resource.id}-{resource.sha256[:12]}.jpg"
            thumbnail = _safe_path(root, thumbnail_relative, create_parent=True)
            if not thumbnail.is_file():
                temporary = thumbnail.with_name(thumbnail.stem + ".pending.jpg")
                try:
                    _run([settings.ffmpeg, "-hide_banner", "-v", "error", "-y", "-protocol_whitelist", "file,pipe", "-i", str(path), "-frames:v", "1", "-vf", "scale=480:-2", str(temporary)], settings.decode_timeout_seconds)
                    temporary.replace(thumbnail)
                finally:
                    temporary.unlink(missing_ok=True)
            resource.thumbnail_path = thumbnail_relative
        else:
            if videos or not audios:
                raise ValueError("Audio intake requires an audio track without a video stream.")
            metadata.update({"sample_rate": audios[0].get("sample_rate"), "channels": audios[0].get("channels")})
            origin = float(data.get("format", {}).get("start_time", 0))
            if not math.isfinite(origin):
                raise ValueError("Audio intake could not establish a finite source start time.")
            metadata["media_start_seconds"] = origin
            _run([settings.ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0", "-f", "null", "-"], settings.decode_timeout_seconds)
            resource.playback_path = resource.original_path
        resource.duration_seconds, resource.media_metadata = duration, metadata

    def extract(self, project_id, resource_id, *, rebuild_preview=False) -> Project:
        resource = _resource(self.store.get(project_id), resource_id).model_copy(deep=True)
        def start(project):
            item = _resource(project, resource_id)
            if item.status == "processing":
                raise WorkflowError("resource_busy", "This resource is already being processed.", 409)
            item.status, item.error = "processing", None
        self.store.update(project_id, None, start)
        try:
            path = self.path(project_id, resource_id)
            root = self.store.project_dir(project_id)
            suffix = path.suffix.lower()
            blocks, warnings = [], []
            if resource.kind in {"video", "audio"}:
                self._media(root, resource, path, rebuild_preview=rebuild_preview)
            elif suffix in {".docx", ".pptx", ".xlsx"}:
                blocks, warnings = extract_office(path)
            elif suffix == ".pdf":
                blocks, warnings = extract_pdf(path, _safe_path(root, f"cache/previews/{resource.id}", create_parent=True))
            elif suffix in {".txt", ".md", ".csv", ".tsv"}:
                text, warnings = _plain_text(path)
                if len(text) > MAX_TEXT:
                    text = text[:MAX_TEXT]
                    warnings.append("Only the first 1,000,000 text characters were extracted.")
                if suffix in {".csv", ".tsv"}:
                    try:
                        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
                    except csv.Error:
                        dialect = csv.excel_tab if suffix == ".tsv" else csv.excel
                    for index, row in enumerate(csv.reader(io.StringIO(text), dialect), 1):
                        if row:
                            blocks.append(ExtractedBlock(locator=f"Row {index}", text=" | ".join(f"Column {column}: {value}" for column, value in enumerate(row, 1))))
                        if len(blocks) >= MAX_BLOCKS:
                            warnings.append("Only the first 4000 rows were extracted.")
                            break
                else:
                    for index, line in enumerate(text.splitlines(), 1):
                        if line.strip():
                            blocks.append(ExtractedBlock(locator=f"Line {index}", text=line))
                        if len(blocks) >= MAX_BLOCKS:
                            warnings.append("Only the first 4000 nonempty lines were extracted.")
                            break
            elif resource.kind == "image":
                resource.thumbnail_path = resource.original_path
                text = _ocr(path)
                if text:
                    blocks = [ExtractedBlock(locator="Image OCR", text=text)]
                warnings.append("OCR is machine extraction; review wording and reading order. No visual meaning is inferred from OCR alone.")
            else:
                resource.status = "unsupported"
                resource.error = ("Convert this legacy Office file to DOCX, XLSX or PPTX. The original remains stored." if suffix in LEGACY else "This format is stored locally but has no supported extractor. Supply a PDF, DOCX, XLSX, CSV, PPTX, text, image or supported media copy.")
            if resource.status != "unsupported":
                total, retained = 0, []
                for block in blocks:
                    if total + len(block.text) > MAX_TEXT or len(retained) >= MAX_BLOCKS:
                        if total < MAX_TEXT and len(retained) < MAX_BLOCKS:
                            retained.append(block.model_copy(update={"text": block.text[:MAX_TEXT - total]}))
                        warnings.append("Extraction reached the text limit; remaining content stays in the original file.")
                        break
                    retained.append(block)
                    total += len(block.text)
                resource.blocks, resource.warnings = retained, warnings
                resource.status = "partial" if warnings else "ready"
                if resource.kind == "document" and not retained:
                    resource.status = "partial"
                    resource.error = "No readable text was extracted. Review the original, retry OCR or provide a text-based copy."
                else:
                    resource.error = None
        except Exception as error:
            resource.status = "missing" if getattr(error, "code", None) == "missing_resource" else "failed"
            resource.error = (getattr(error, "message", str(error))[:1000] or
                              "Extraction failed. The original file and prior corrections are retained.")
        def finish(project):
            item = _resource(project, resource_id)
            # Re-extraction must never erase user-corrected document content.
            if item.extraction_revision > 1:
                resource.blocks = item.blocks
                resource.extraction_revision = item.extraction_revision
                resource.extraction_history = item.extraction_history
                resource.warnings.append("Saved extraction corrections were retained while previews were rebuilt.")
            elif item.blocks:
                old_content = [(block.locator, block.text) for block in item.blocks]
                new_content = [(block.locator, block.text) for block in resource.blocks]
                if old_content == new_content:
                    resource.blocks = item.blocks
                elif resource.status not in {"failed", "missing", "unsupported"}:
                    resource.extraction_history = [*item.extraction_history, {"revision": item.extraction_revision,
                                                                          "blocks": [block.model_dump() for block in item.blocks]}]
                    resource.extraction_revision = item.extraction_revision + 1
                    invalidate(project, resource_id=resource_id)
                else:
                    resource.blocks = item.blocks
            resource.evidence = item.evidence
            project.resources[project.resources.index(item)] = resource
        return self.store.update(project_id, None, finish)

    def correct_blocks(self, project_id, expected_version, resource_id, blocks, *, base_revision=None, expected_editor_version=None) -> Project:
        edits = [(ExtractedBlock.model_validate(item) if isinstance(item, dict) else item).model_copy(deep=True) for item in blocks]
        if len(edits) > MAX_BLOCKS or sum(len(item.text) for item in edits) > MAX_TEXT:
            raise WorkflowError("extraction_edit_too_large", "The extraction correction exceeds the supported text limit.", 422)
        def change(project):
            resource = _resource(project, resource_id)
            scope = f"blocks-{resource_id}"
            if base_revision is not None and resource.extraction_revision != base_revision:
                raise WorkflowError("extraction_revision_conflict", "This document extraction has a newer revision. Your correction draft is retained; review the current extraction before applying it.", 409)
            if expected_editor_version is not None and project.editor_draft_versions.get(scope, 0) != expected_editor_version:
                raise WorkflowError("editor_draft_conflict", "This extraction draft changed elsewhere. Your text is retained; review the newer draft before applying corrections.", 409)
            draft = project.editor_drafts.get(scope)
            submitted = [item.model_dump(mode="json") for item in edits]
            matching_draft = (isinstance(draft, dict) and draft.get("blocks") == submitted
                              and draft.get("base_revision", resource.extraction_revision) == resource.extraction_revision)
            def checkpoint():
                if not matching_draft:
                    return False
                normalized = {**draft, "blocks": [item.model_dump(mode="json") for item in resource.blocks],
                              "base_revision": resource.extraction_revision}
                if normalized == draft:
                    return False
                project.editor_drafts[scope] = normalized
                return True
            old = {item.id: item for item in resource.blocks}
            if len(edits) != len(old) or {item.id for item in edits} != set(old):
                raise WorkflowError("invalid_extraction_edit", "Corrections must preserve source block identities.", 422)
            for item in edits:
                if item.locator != old[item.id].locator:
                    raise WorkflowError("invalid_extraction_edit", "Corrections cannot change original source locations.", 422)
                item.original_text = old[item.id].original_text if old[item.id].original_text is not None else old[item.id].text
            if all(item.text == old[item.id].text for item in edits):
                return checkpoint()
            resource.extraction_history.append({"revision": resource.extraction_revision,
                                                "blocks": [item.model_dump() for item in resource.blocks]})
            resource.blocks = edits
            resource.extraction_revision += 1
            changed_locators = {item.locator for item in edits if item.text != old[item.id].text}
            if project.briefs:
                affected = [fact.key for fact in project.briefs[-1].facts
                            if any(source.resource_id == resource_id and source.locator in changed_locators for source in fact.sources)]
                if affected:
                    note = f"Extraction corrected in {resource.name}; review the adopted {', '.join(dict.fromkeys(affected))} context. Confirmed context remains unchanged until you adopt a correction."
                    if note not in project.unresolved:
                        project.unresolved.append(note)
            invalidate(project, resource_id=resource_id)
            checkpoint()
        return self.store.update(project_id, expected_version, change)

    def relink(self, project_id, expected_version, resource_id, stream) -> Project:
        resource = _resource(self.store.get(project_id), resource_id)
        if not re.fullmatch(r"[a-f0-9]{64}", resource.sha256):
            raise WorkflowError("relink_unavailable", "This older resource has no verifiable original fingerprint. Import the file as a new resource; historical evidence remains intact.", 422)
        # Legacy VideoAsset records did not store byte counts. A missing original
        # therefore migrates with size zero, which means unknown only for legacy
        # resources. Its retained checksum still establishes exact identity.
        unknown_legacy_size = resource.origin == "legacy" and resource.size_bytes == 0
        size_limit = self.media_settings.max_bytes if unknown_legacy_size else resource.size_bytes
        root = self.store.project_dir(project_id)
        destination = _safe_path(root, resource.original_path, create_parent=True)
        stage = _safe_path(root, f"staging/{uid('relink')}.part", create_parent=True)
        digest, size = hashlib.sha256(), 0
        try:
            with stage.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > size_limit:
                        raise WorkflowError("relink_mismatch", "This is not the exact original file.", 422)
                    digest.update(chunk)
                    output.write(chunk)
            if not size or (not unknown_legacy_size and size != resource.size_bytes) or digest.hexdigest() != resource.sha256:
                raise WorkflowError("relink_mismatch", "This is not the exact original file. Existing evidence is unchanged.", 422)
            def change(project):
                item = _resource(project, resource_id)
                if destination.is_file() and _digest(destination) == resource.sha256:
                    if item.status != "missing" and not unknown_legacy_size:
                        return False
                    if unknown_legacy_size:
                        item.size_bytes = size
                    item.status, item.error = "stored", None
                    return None
                stage.replace(destination)
                if unknown_legacy_size:
                    item.size_bytes = size
                item.status, item.error = "stored", None
            return self.store.update(project_id, expected_version, change)
        finally:
            stage.unlink(missing_ok=True)
