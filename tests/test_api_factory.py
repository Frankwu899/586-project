"""Launcher imports never create a database inside a read-only app bundle."""
import os
from pathlib import Path
import subprocess
import sys


def test_factory_import_is_lazy_but_uvicorn_attribute_still_resolves(tmp_path):
    environment = dict(os.environ)
    environment.pop("OPENAI_API_KEY", None)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    environment["VIDEO_ANATOMY_DATA_DIR"] = str(tmp_path / "selected-library")
    script = """
from pathlib import Path
import os
from scripts import local_server
from backend.app import api
target = Path(os.environ['VIDEO_ANATOMY_DATA_DIR'])
assert not target.exists()
assert not Path('.local-data').exists()
assert 'app' not in api.__dict__
application = getattr(api, 'app')
assert application is getattr(api, 'app')
assert target.joinpath('tasks.sqlite3').is_file()
assert not Path('.local-data').exists()
"""
    subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=environment,
                   check=True, capture_output=True, timeout=20)
