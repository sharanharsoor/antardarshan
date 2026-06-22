"""
API contract tests for FastAPI endpoints.

Tests response shapes and status codes without requiring
Qdrant or Groq to be running (uses TestClient).
"""

import pytest
from urllib.parse import quote
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "antardarshan"
    assert "version" in data


def test_library_list(client):
    r = client.get("/api/library")
    assert r.status_code == 200
    data = r.json()
    assert "scriptures" in data
    assert len(data["scriptures"]) >= 3
    for s in data["scriptures"]:
        assert "scripture" in s
        assert "tradition" in s
        assert "total_chapters" in s
        assert "total_verses" in s
        assert "license_tier" in s


def test_library_chapter(client):
    r = client.get("/api/library/Dhammapada/1")
    assert r.status_code == 200
    data = r.json()
    assert data["scripture"] == "Dhammapada"
    assert data["chapter"] == 1
    assert len(data["verses"]) == 20  # Dhammapada Ch.1 = 20 verses


def test_library_chapter_not_found(client):
    r = client.get("/api/library/NonExistent/99")
    assert r.status_code == 404


def test_query_endpoint_shape(client):
    r = client.post("/api/query", json={"query": "What is consciousness?", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "mode" in data
    assert "citations" in data
    assert "latency_ms" in data
    assert isinstance(data["citations"], list)
    assert data["mode"] in ("citation", "well_being", "exploration", "comparison")


def test_explain_endpoint_shape(client):
    r = client.post("/api/explain", json={
        "scripture": "Ashtavakra Gita",
        "chapter": 1,
        "verse": 2
    })
    assert r.status_code == 200
    data = r.json()
    assert "verse" in data
    assert "explanation" in data
    assert "context_verses" in data
    assert data["verse"]["chapter"] == 1
    assert data["verse"]["verse"] == 2


def test_explain_not_found(client):
    r = client.post("/api/explain", json={
        "scripture": "Fake Text",
        "chapter": 99,
        "verse": 99
    })
    assert r.status_code == 404


def test_query_log_never_stores_query_text(client, tmp_path, monkeypatch):
    """
    Privacy contract test (Section 13 of COMBINED-PLAN.md).
    Verify that the query text is never written to query_logs.
    """
    import sqlite3
    from pathlib import Path

    # Point the DB to a temp path so we start clean
    db = tmp_path / "test_query_logs.db"
    monkeypatch.setattr("backend.app.DB_PATH", db)

    # Re-init DB with the new path
    from backend.app import _init_db
    _init_db()

    # Make a query
    sensitive_query = "I am suffering from deep grief and suicidal thoughts"
    client.post("/api/query", json={"query": sensitive_query})

    # Check the DB — query_text column must be NULL
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT query_text FROM query_logs").fetchall()
    conn.close()

    assert len(rows) >= 1, "At least one log entry should exist"
    for row in rows:
        assert row[0] is None, f"query_text should be NULL but got: {row[0]!r}"


# --- New endpoint tests (backend sync for frontend) ---

def test_library_returns_slugs(client):
    r = client.get("/api/library")
    assert r.status_code == 200
    for s in r.json()["scriptures"]:
        assert "slug" in s, f"Scripture {s['scripture']} missing slug field"
        assert s["slug"] == s["scripture"].lower().replace(" ", "-").strip("-") or "-" in s["slug"]


def test_scripture_detail(client):
    """GET /api/library/{slug} returns chapters for table of contents."""
    r = client.get("/api/library")
    slug = r.json()["scriptures"][0]["slug"]

    r = client.get(f"/api/library/{slug}")
    assert r.status_code == 200
    data = r.json()
    assert "scripture" in data
    assert "chapters" in data
    assert len(data["chapters"]) >= 1
    ch = data["chapters"][0]
    assert "chapter" in ch
    assert "verse_count" in ch
    assert ch["verse_count"] > 0


def test_scripture_detail_accepts_full_name(client):
    """GET /api/library/{scripture} should accept URL-encoded full scripture names."""
    r = client.get("/api/library")
    scripture_name = r.json()["scriptures"][0]["scripture"]

    encoded = quote(scripture_name, safe="")
    r = client.get(f"/api/library/{encoded}")
    assert r.status_code == 200
    data = r.json()
    assert data["scripture"]["scripture"] == scripture_name
    assert "chapters" in data


def test_scripture_detail_not_found(client):
    r = client.get("/api/library/nonexistent-slug")
    assert r.status_code == 404


def test_verse_detail(client):
    """GET /api/library/{slug}/{chapter}/{verse} returns verse + context."""
    r = client.get("/api/library")
    slug = r.json()["scriptures"][0]["slug"]

    r = client.get(f"/api/library/{slug}/1/1")
    assert r.status_code == 200
    data = r.json()
    assert "verse" in data
    assert "context_verses" in data
    assert data["verse"]["chapter"] == 1
    assert data["verse"]["verse"] == 1
    assert len(data["context_verses"]) >= 1


def test_verse_detail_accepts_full_name(client):
    """GET /api/library/{scripture}/{chapter}/{verse} should accept full names."""
    r = client.get("/api/library")
    scripture_name = r.json()["scriptures"][0]["scripture"]

    encoded = quote(scripture_name, safe="")
    r = client.get(f"/api/library/{encoded}/1/1")
    assert r.status_code == 200
    data = r.json()
    assert data["verse"]["scripture"] == scripture_name
    assert data["verse"]["chapter"] == 1
    assert data["verse"]["verse"] == 1


def test_verse_detail_not_found(client):
    r = client.get("/api/library/ashtavakra-gita/99/99")
    assert r.status_code == 404


def test_quota_status(client):
    """GET /api/quota-status returns availability indicator."""
    r = client.get("/api/quota-status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("available", "limited", "exhausted")
    assert "queries_today" in data
    assert "daily_limit" in data
    assert data["daily_limit"] == 15_400
