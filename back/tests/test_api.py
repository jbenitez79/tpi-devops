import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, get_db


class FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def delete(self):
        return 0


class FakeDB:
    def query(self, *args, **kwargs):
        return FakeQuery()

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def delete(self, obj):
        pass


def fake_get_db():
    yield FakeDB()


app.dependency_overrides[get_db] = fake_get_db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_get_todos(client):
    r = client.get("/todos")
    assert r.status_code == 200
    assert r.json() == []


def test_post_todo(client):
    payload = {"title": "test task 1"}
    r = client.post("/todos", json=payload)
    assert r.status_code in (200, 422)


def test_put_todo(client):
    r = client.put("/todos/whatever", json={"completed": True})
    assert r.status_code == 422


def test_clear_completed(client):
    r = client.post("/todos/clear_completed")
    assert r.status_code == 200
    assert r.json() == {"deleted": 0}


def test_delete_todo(client):
    r = client.delete("/todos/whatever")
    assert r.status_code == 404
