import json
from types import SimpleNamespace


def _write_json(path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeCountResult:
    def __init__(self, count):
        self.count = count


class _FakeClient:
    def __init__(self, total_points=0):
        self.total_points = total_points
        self.delete_calls = []

    def count(self, *args, **kwargs):
        return _FakeCountResult(self.total_points)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        return {"status": "ok"}


def test_cmd_status_aggregates_multi_scripture_files(tmp_path, monkeypatch, capsys):
    import ingestion.admin as admin

    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setattr(admin, "CORPUS_PROCESSED", processed)

    # One file contains multiple scriptures; another adds more rows for an existing one.
    _write_json(
        processed / "vivekananda_collected.json",
        [
            {"scripture": "Vivekananda - Raja-Yoga"},
            {"scripture": "Vivekananda - Karma-Yoga"},
            {"scripture": "Vivekananda - Jnana-Yoga"},
        ],
    )
    _write_json(
        processed / "more_karma.json",
        [
            {"scripture": "Vivekananda - Karma-Yoga"},
            {"scripture": "Vivekananda - Karma-Yoga"},
        ],
    )

    fake = _FakeClient(total_points=5)
    monkeypatch.setattr(admin, "_get_client", lambda: fake)

    admin.cmd_status(SimpleNamespace())
    out = capsys.readouterr().out

    assert "Total chunks in JSON: 5" in out
    assert "Qdrant points:        5" in out
    assert "Vivekananda - Raja-Yoga" in out
    assert "Vivekananda - Karma-Yoga" in out
    assert "Vivekananda - Jnana-Yoga" in out
    # Ensure Karma is aggregated across both files.
    assert "Vivekananda - Karma-Yoga" in out and "3" in out


def test_cmd_remove_rewrites_mixed_files_and_deletes_empty_files(tmp_path, monkeypatch):
    import ingestion.admin as admin

    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setattr(admin, "CORPUS_PROCESSED", processed)

    mixed = processed / "mixed.json"
    pure = processed / "pure_target.json"

    _write_json(
        mixed,
        [
            {"scripture": "Vivekananda - Raja-Yoga", "text": "a"},
            {"scripture": "Vivekananda - Karma-Yoga", "text": "b"},
            {"scripture": "Vivekananda - Jnana-Yoga", "text": "c"},
        ],
    )
    _write_json(
        pure,
        [
            {"scripture": "Vivekananda - Karma-Yoga", "text": "d"},
            {"scripture": "Vivekananda - Karma-Yoga", "text": "e"},
        ],
    )

    fake = _FakeClient(total_points=0)
    monkeypatch.setattr(admin, "_get_client", lambda: fake)

    admin.cmd_remove(SimpleNamespace(scripture="Vivekananda - Karma-Yoga"))

    # Qdrant delete was attempted once.
    assert len(fake.delete_calls) == 1

    # Mixed file should remain but without target scripture.
    mixed_rows = json.loads(mixed.read_text(encoding="utf-8"))
    assert {r["scripture"] for r in mixed_rows} == {
        "Vivekananda - Raja-Yoga",
        "Vivekananda - Jnana-Yoga",
    }

    # Pure target file should be deleted after removing all rows.
    assert not pure.exists()
