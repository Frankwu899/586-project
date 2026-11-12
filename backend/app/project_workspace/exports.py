"""Version-pinned production documents; browser printing provides PDF output."""
from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import zipfile

from ..workflow_errors import WorkflowError


_DOCUMENTS = (("production_brief", "Production brief"), ("script", "Script"),
              ("storyboard", "Storyboard"), ("shot_list", "Shot list"))


def _selected(project, pack_id, revision):
    matches = [pack for pack in project.packs if pack.id == pack_id]
    if not matches:
        raise WorkflowError("pack_not_found", "This production pack does not belong to the project.", 404)
    latest = max(matches, key=lambda pack: pack.revision)
    chosen = latest if revision is None else next((pack for pack in matches if pack.revision == revision), None)
    if chosen is None:
        raise WorkflowError("pack_revision_not_found", "The requested production revision does not exist.", 404)
    return chosen, chosen.revision != latest.revision


def _source_text(source):
    label = source.resource_id or source.message_id or "Source"
    if source.event_id:
        label += f" / {source.event_id}"
    if source.evidence_revision is not None:
        label += f" / evidence revision {source.evidence_revision}"
    if source.locator:
        label += f" / {source.locator}"
    if source.start_seconds is not None:
        label += f" / {source.start_seconds:g}s"
        if source.end_seconds is not None:
            label += f"–{source.end_seconds:g}s"
    if source.excerpt:
        label += f": {source.excerpt}"
    if _safe_url(source.url):
        label += f" ({source.url})"
    return label


def _safe_url(value):
    if not value:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _metadata(project, pack, historical):
    item = next((entry for entry in project.contents if entry.id == pack.content_id), None)
    title = item.title if item else "Production pack"
    status = "Historical revision" if historical else "Saved production draft"
    if pack.needs_review:
        status += " · Needs review: confirmed inputs have changed"
    missing = [label for field, label in _DOCUMENTS if not getattr(pack, field).strip()]
    if missing:
        status += " · Incomplete: " + ", ".join(missing)
    return title, [f"Project: {project.title}", f"Content: {title}",
                   f"Pack: {pack.id} · Revision {pack.revision}", f"Saved: {pack.created_at}",
                   f"Status: {status}", "Planned timings are estimates; approval does not independently verify product claims."]


def markdown(project, pack, historical=False):
    title, metadata = _metadata(project, pack, historical)
    sections = [f"# {title}", "\n".join(metadata)]
    for field, label in _DOCUMENTS:
        sections.append(f"## {label}\n\n{getattr(pack, field)}")
    if pack.sources:
        sections.append("## Supporting references\n\n" + "\n".join(f"- {_source_text(source)}" for source in pack.sources))
    sections.append("## Input manifest\n\n```json\n" + json.dumps(pack.inputs.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n```")
    return "\n\n".join(sections) + "\n"


def printable_html(project, pack, historical=False):
    title, metadata = _metadata(project, pack, historical)
    blocks = [f"<h1>{html.escape(title)}</h1>", "<div class='metadata'>" + "".join(f"<p>{html.escape(line)}</p>" for line in metadata) + "</div>"]
    for field, label in _DOCUMENTS:
        blocks.append(f"<section><h2>{label}</h2><pre>{html.escape(getattr(pack, field))}</pre></section>")
    if pack.sources:
        blocks.append("<section><h2>Supporting references</h2><ul>" + "".join(f"<li>{html.escape(_source_text(source))}</li>" for source in pack.sources) + "</ul></section>")
    blocks.append("<section><h2>Input manifest</h2><pre class='manifest'>" + html.escape(json.dumps(pack.inputs.model_dump(mode="json"), indent=2, ensure_ascii=False)) + "</pre></section>")
    return "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>" + html.escape(title) + "</title><style>" + (
        "body{font:15px/1.55 system-ui,sans-serif;color:#172033;background:white;max-width:960px;margin:36px auto;padding:0 24px}"
        "h1{font-size:30px}h2{font-size:21px;margin-top:32px}.metadata{font-size:12px;color:#475569}.metadata p{margin:3px 0}"
        "pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}.manifest{font:11px/1.5 monospace}li{margin:10px 0}"
        "@media print{body{margin:0;max-width:none;font-size:11pt}h2{break-after:avoid}pre{font-size:10pt}section{break-inside:auto}}"
    ) + "</style></head><body>" + "".join(blocks) + "</body></html>"


def _spreadsheet_cell(value):
    value = str(value)
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def csv_document(project, pack, historical=False):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    _, metadata = _metadata(project, pack, historical)
    writer.writerow(["Production pack", "\n".join(metadata)])
    shots = getattr(pack, "shots", [])
    if shots:
        writer.writerow(["Shot", "Start (seconds)", "End (seconds)", "Visual", "Dialogue", "On-screen text", "Sound", "Notes"])
        for shot in shots:
            values = shot.model_dump() if hasattr(shot, "model_dump") else shot
            writer.writerow([_spreadsheet_cell(values.get(key, "")) for key in ("id", "start_seconds", "end_seconds", "visual", "dialogue", "on_screen_text", "sound", "notes")])
    else:
        writer.writerow(["Document", "Saved text (no synchronized structured shots in this revision)"])
        for field, label in _DOCUMENTS:
            writer.writerow([label, _spreadsheet_cell(getattr(pack, field))])
    writer.writerow([])
    writer.writerow(["Input manifest", json.dumps(pack.inputs.model_dump(mode="json"), ensure_ascii=False)])
    for source in pack.sources:
        writer.writerow(["Supporting reference", _spreadsheet_cell(_source_text(source))])
    return stream.getvalue()


def docx_document(project, pack, historical=False):
    """Minimal standards-based editable DOCX with no macros or external relationships."""
    title, metadata = _metadata(project, pack, historical)
    def paragraph(text, bold=False):
        runs = []
        for index, line in enumerate(text.splitlines() or [""]):
            if index:
                runs.append("<w:r><w:br/></w:r>")
            runs.append("<w:r>" + ("<w:rPr><w:b/></w:rPr>" if bold else "") + "<w:t xml:space='preserve'>" + html.escape(line) + "</w:t></w:r>")
        return "<w:p>" + "".join(runs) + "</w:p>"
    body = [paragraph(title, True)] + [paragraph(line) for line in metadata]
    for field, label in _DOCUMENTS:
        body.extend([paragraph(label, True), paragraph(getattr(pack, field))])
    if pack.sources:
        body.append(paragraph("Supporting references", True))
        body.extend(paragraph(_source_text(source)) for source in pack.sources)
    body.extend([paragraph("Input manifest", True), paragraph(json.dumps(pack.inputs.model_dump(mode="json"), indent=2, ensure_ascii=False))])
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + "".join(body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def export_pack(store, project_id, pack_id, revision=None, format="md"):
    project = store.get(project_id)
    pack, historical = _selected(project, pack_id, revision)
    if all(not getattr(pack, field).strip() for field, _label in _DOCUMENTS):
        raise WorkflowError("production_empty", "Write or generate production content before exporting this empty pack.", 422)
    if not historical:
        from .planning import require_pack_draft_clear
        require_pack_draft_clear(project, pack)
    if format == "markdown":
        format = "md"
    if format == "pdf":
        raise WorkflowError("pdf_print_required", "Open the print preview and use the browser's Save as PDF option.", 422)
    if format == "md":
        data, mime = markdown(project, pack, historical).encode(), "text/markdown; charset=utf-8"
    elif format == "html":
        data, mime = printable_html(project, pack, historical).encode(), "text/html; charset=utf-8"
    elif format == "csv":
        data, mime = csv_document(project, pack, historical).encode("utf-8-sig"), "text/csv; charset=utf-8"
    elif format == "docx":
        data, mime = docx_document(project, pack, historical), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise WorkflowError("unsupported_export", "Choose Markdown, CSV, DOCX, or print preview.", 422)
    if not all(re.fullmatch(r"[A-Za-z0-9_-]+", identity) for identity in (pack.id, pack.content_id)):
        raise WorkflowError("invalid_pack_identity", "This production pack has an invalid storage identity.", 422)
    folder = store.resolve_path(project_id, f"outputs/{pack.content_id}/{pack.id}")
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"revision-{pack.revision}.{format}"
    with tempfile.NamedTemporaryFile(dir=folder, prefix=".export-", delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return data, mime, f"production-pack-r{pack.revision}.{format}"
