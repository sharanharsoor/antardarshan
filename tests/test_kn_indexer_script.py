import json
from pathlib import Path

from ingestion.schema import ScriptureChunk


def _mk_chunk(text: str, chapter: int, verse: int) -> ScriptureChunk:
    return ScriptureChunk(
        text=text,
        scripture="Sutta Nipata",
        tradition="buddhist",
        chapter=chapter,
        verse=verse,
        translator="Bhikkhu Sujato",
        year=2021,
        language="en",
        license_tier="A",
        source_url="https://suttacentral.net/snp1.1",
    )


def test_kn_indexer_uses_saved_output_for_upsert_and_display_count(tmp_path, monkeypatch, capsys):
    """
    Main flow should:
    1) parse chunks
    2) call _save()
    3) reload saved JSON
    4) upsert/reported count based on reloaded JSON (post-cap/dedupe), not raw parse count
    """
    import ingestion.index_kn_subcollections as idx
    import ingestion.parsers.pali_canon_sujato as pcs
    import ingestion.embed_and_load as eal
    import ingestion.process_all as pa

    # Arrange: minimal KN directory exists
    kn_dir = tmp_path / "sc-data" / "translation" / "en" / "sujato" / "sutta" / "kn" / "snp"
    kn_dir.mkdir(parents=True)

    monkeypatch.setattr(idx, "SC_DATA", tmp_path / "sc-data")
    monkeypatch.setattr(idx, "CORPUS_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(idx, "KN_TARGETS", [("snp", "sutta_nipata.json")])

    # Fake parser returns 2 chunks (pre-save count)
    parsed_chunks = [
        _mk_chunk("word " * 100, chapter=1, verse=1),
        _mk_chunk("word " * 100, chapter=1, verse=2),
    ]
    monkeypatch.setattr(pcs, "parse_nikaya", lambda _dir, _code: parsed_chunks)
    monkeypatch.setattr(pcs, "NIKAYA_META", {"snp": ("Sutta Nipata", "The Sutta Nipata")})

    # Fake _save writes only 1 chunk to mimic post-processing change (cap/dedupe)
    def fake_save(chunks, filename):
        out_file = idx.CORPUS_PROCESSED / filename
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps([chunks[0].to_dict()]), encoding="utf-8")
        return 1

    monkeypatch.setattr(pa, "_save", fake_save)

    # Embedding helpers
    monkeypatch.setattr(eal, "build_parent_text", lambda _chunk, _all_chunks: "")
    monkeypatch.setattr(eal, "build_embedding_text", lambda c: c["text"])
    monkeypatch.setattr(eal, "embed_prod", lambda texts: ([[0.0] * 4 for _ in texts], [{} for _ in texts], 4))

    captured = {}

    def fake_upsert(_client, chunk_dicts, _dense_vectors, _sparse_dicts, has_sparse):
        captured["count"] = len(chunk_dicts)
        captured["has_sparse"] = has_sparse

    monkeypatch.setattr(eal, "upsert_chunks", fake_upsert)
    monkeypatch.setattr(idx, "QdrantClient", lambda url: object())

    # Act
    idx.main()
    out = capsys.readouterr().out

    # Assert: uses saved JSON length, not raw parsed length
    assert captured["count"] == 1
    assert captured["has_sparse"] is True
    assert "Parsed 2 chunks" in out
    assert "✅ Sutta Nipata: 1 chunks indexed" in out


def test_kn_indexer_skips_missing_directories_without_upsert(tmp_path, monkeypatch):
    import ingestion.index_kn_subcollections as idx
    import ingestion.embed_and_load as eal

    # No KN dirs created -> should skip cleanly.
    monkeypatch.setattr(idx, "SC_DATA", tmp_path / "sc-data")
    monkeypatch.setattr(idx, "CORPUS_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(idx, "KN_TARGETS", [("snp", "sutta_nipata.json")])
    monkeypatch.setattr(idx, "QDRANT_URL", "http://example")
    monkeypatch.setattr(idx, "QdrantClient", lambda url: object())

    upsert_calls = {"n": 0}
    monkeypatch.setattr(eal, "upsert_chunks", lambda *args, **kwargs: upsert_calls.__setitem__("n", upsert_calls["n"] + 1))

    idx.main()
    assert upsert_calls["n"] == 0
