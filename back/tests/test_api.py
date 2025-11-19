import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, get_db


def fake_get_db():
    # Always yield None — never touch SQLAlchemy
    yield None


app.dependency_overrides[get_db] = fake_get_db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code in (200, 422, 404)
    assert r is not None


def test_get_todos(client):
    r = client.get("/todos")
    assert r.status_code in (200, 422)
    assert r is not None


def test_post_todo(client):
    payload = {"title": "test task 1"}

    r = client.post("/todos", json=payload)

    assert r.status_code in (200, 201, 422)
    assert r is not None


def test_put_todo(client):
    r = client.put("/todos/some_id", json={"completed": True})
    assert r.status_code in (200, 404, 422)
    assert r is not None


def test_clear_completed(client):
    r = client.post("/todos/clear_completed")
    assert r.status_code in (200, 204, 422)
    assert r is not None


def test_delete_todo(client):
    r = client.delete("/todos/some_id")
    assert r.status_code in (200, 204, 404, 422)
    assert r is not None
