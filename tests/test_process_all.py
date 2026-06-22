from ingestion.process_all import _deduplicate_verses
from ingestion.schema import ScriptureChunk


def _chunk(scripture: str, translator: str, chapter: int, verse: int) -> ScriptureChunk:
    return ScriptureChunk(
        text="sample text long enough",
        scripture=scripture,
        tradition="hindu_vedanta",
        chapter=chapter,
        verse=verse,
        translator=translator,
        year=1900,
        language="en",
        license_tier="A",
        source_url="https://example.org/source",
    )


def test_deduplicate_verses_scopes_by_scripture_and_translator():
    chunks = [
        _chunk("Text A", "Translator 1", 1, 1),
        _chunk("Text A", "Translator 1", 1, 1),  # duplicate -> should be bumped
        _chunk("Text B", "Translator 1", 1, 1),  # different scripture -> unchanged
        _chunk("Text A", "Translator 2", 1, 1),  # different translator -> unchanged
    ]

    out = _deduplicate_verses(chunks)

    assert out[0].verse == 1
    assert out[1].verse == 2
    assert out[2].verse == 1
    assert out[3].verse == 1


def test_deduplicate_verses_preserves_chapter_boundary():
    chunks = [
        _chunk("Text A", "Translator 1", 1, 1),
        _chunk("Text A", "Translator 1", 2, 1),
    ]

    out = _deduplicate_verses(chunks)
    assert out[0].verse == 1
    assert out[1].verse == 1
