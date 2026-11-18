"""Synthetic saved sheets exercise export fidelity, never generated-output quality."""
import csv
from html.parser import HTMLParser
import html
import io

import pytest

from backend.app.project_workspace.exports import export_pack
from backend.app.project_workspace.models import InputManifest, ProductionPack, ProductionShot, SourceRef
from backend.app.project_workspace.store import ProjectStore


class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"th", "td"}:
            self.cell = ""
        elif tag == "br" and self.cell is not None:
            self.cell += "\n"

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self.row is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def sheet(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Synthetic export project")
    source = SourceRef(resource_id="video_a", evidence_revision=3, event_id="event_a",
                       start_seconds=1.25, end_seconds=2.5, excerpt="Observed <card>")
    shot = ProductionShot(id="shot_a", start_seconds=0, end_seconds=4,
                          framing_camera="Wide", visual="First <scene>\n第二行 | detail",
                          dialogue="A proposed voiceover", on_screen_text="<script>alert(1)</script>",
                          sound="New music suggestion", notes="  Keep the qualifier.\nDo not strip this line.\n", sources=[source])
    pack = ProductionPack(id="pack_saved", content_id="content_a", inputs=InputManifest(),
                          production_brief="Synthetic brief", script="obsolete script",
                          storyboard="obsolete mirrored storyboard", shot_list="obsolete shot list",
                          sheet_format="storyboard_sheet", shots=[shot])
    project = store.update(project.id, project.version, lambda state: state.packs.append(pack))
    return store, project, pack


def test_html_uses_saved_shots_with_escaped_multiline_cells_and_exact_shot_citations(tmp_path):
    store, project, pack = sheet(tmp_path)
    page, _, _ = export_pack(store, project.id, pack.id, 1, "html")
    text = page.decode()
    parsed = Table()
    parsed.feed(text)
    assert len(parsed.rows) == 2
    assert parsed.rows[0] == ["Shot", "Timecode", "Framing / Camera", "Visual / Action", "Dialogue / VO", "On-screen Text", "Music / SFX", "Production Notes"]
    assert parsed.rows[1][:7] == ["01", "0–4s", "Wide", "First <scene>\n第二行 | detail", "A proposed voiceover", "<script>alert(1)</script>", "New music suggestion"]
    assert "video_a / event_a / evidence revision 3 / 1.25s–2.5s" in parsed.rows[1][7]
    assert "<script>" not in text and "obsolete mirrored storyboard" not in text
    assert "Keep the qualifier." in parsed.rows[1][7]
    assert parsed.rows[1][7].startswith("  Keep the qualifier.\nDo not strip this line.\n")


def test_markdown_and_csv_read_same_authoritative_shots_while_history_stays_pinned(tmp_path):
    store, project, pack = sheet(tmp_path)
    revised = pack.model_copy(deep=True, update={"revision": 2})
    revised.shots[0].dialogue = "Human-edited r2, not evidence of r1 quality"
    project = store.update(project.id, project.version, lambda state: state.packs.append(revised))
    md, _, _ = export_pack(store, project.id, pack.id, 1, "markdown")
    text = md.decode()
    assert "Historical revision" in text and "Revision 1" in text
    assert "A proposed voiceover" in text and "Human-edited r2" not in text
    assert "obsolete mirrored storyboard" not in text
    assert "第二行 &#124; detail" in text and "<br>" in text
    assert "video_a / event_a / evidence revision 3 / 1.25s–2.5s" in html.unescape(text)
    data, _, _ = export_pack(store, project.id, pack.id, 1, "csv")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[1][4:6] == ["First <scene>\n第二行 | detail", "A proposed voiceover"]
    reopened = ProjectStore(store.root).get(project.id)
    assert reopened.packs[0].shots[0].dialogue == "A proposed voiceover"
    assert reopened.packs[-1].shots[0].dialogue.startswith("Human-edited r2")


def test_legacy_documents_export_original_text_without_inventing_a_sheet(tmp_path):
    store, project, pack = sheet(tmp_path)
    project = store.update(project.id, project.version, lambda state: setattr(state.packs[0], "sheet_format", "legacy_documents"))
    page, _, _ = export_pack(store, project.id, pack.id, 1, "html")
    assert b"obsolete mirrored storyboard" in page and b"<table" not in page


@pytest.mark.parametrize("literal,visible", [
    (r"Literal \| pipe and **asterisks** [not a link](https://example.test)", r"Literal \| pipe and **asterisks** [not a link](https://example.test)"),
    ("First\r\nSecond", "First\nSecond"),
    ("First\rSecond", "First\nSecond"),
])
def test_markdown_keeps_literal_copy_and_platform_line_breaks_in_original_cells(tmp_path, literal, visible):
    store, project, pack = sheet(tmp_path)
    project = store.update(project.id, project.version, lambda state: setattr(state.packs[0].shots[0], "visual", literal))
    data, _, _ = export_pack(store, project.id, pack.id, 1, "markdown")
    row = next(line for line in data.decode().splitlines() if line.startswith("| 01 |"))
    cells = [value.strip() for value in row.split("|")[1:-1]]
    assert len(cells) == 8
    assert html.unescape(cells[3]).replace("<br>", "\n") == visible
    assert cells[4] == "A proposed voiceover"
    assert "**" not in cells[3] and "[" not in cells[3] and "\\" not in cells[3]
