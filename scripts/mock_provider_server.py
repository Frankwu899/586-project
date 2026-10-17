"""Test-only browser server. Never use this entry point to recognize real media."""
import os
from pathlib import Path

from backend.app.api import create_app
from scripts.offline_provider_fixtures import fixture_service

app = create_app(service=fixture_service(Path(os.environ["VIDEO_ANATOMY_DATA_DIR"])))
