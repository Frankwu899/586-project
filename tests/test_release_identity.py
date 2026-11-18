import json

from backend.app import release


def test_packaged_source_identity_wins_over_surrounding_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    (tmp_path / "PACKAGE_MANIFEST.json").write_text(json.dumps({"source_commit": "a" * 40}))
    assert release.release_info() == {"version": "1.8.5", "source_commit": "a" * 40}


def test_missing_or_invalid_identity_does_not_invent_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.release_info()["source_commit"] is None
    (tmp_path / "PACKAGE_MANIFEST.json").write_text('{"source_commit": "not-a-commit"}')
    assert release.release_info()["source_commit"] is None
