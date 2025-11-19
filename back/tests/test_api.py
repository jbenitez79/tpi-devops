import os
import sys
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, get_db, TodoModel


class FakeQuery:
    def __init__(self, db, model, items):
        self.db = db
        self.model = model
        self.items = items[:]

    def filter(self, condition):
        attr = None
        value = None

        if str(condition).endswith(" = 0"):
            attr = "completed"
            value = False
        elif str(condition).endswith(" = 1"):
            attr = "completed"
            value = True

        if attr is not None:
            self.items = [i for i in self.items if getattr(i, attr) == value]

        return self

    def order_by(self, *args, **kwargs):
        # app.py always uses created_at desc
        self.items.sort(key=lambda t: t.created_at, reverse=True)
        return self

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None

    def delete(self):
        to_delete = list(self.items)
        for item in to_delete:
            self.db._data.remove(item)
        return len(to_delete)


class FakeSession:
    def __init__(self):
        self._data = []

    def query(self, model):
        return FakeQuery(self, model, [x for x in self._data if isinstance(x, model)])

    def add(self, obj):
        if obj not in self._data:
            self._data.append(obj)

    def delete(self, obj):
        if obj in self._data:
            self._data.remove(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


fake_db = FakeSession()


def override_get_db():
    yield fake_db


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_crud_flow(client):
    r = client.get("/todos")
    assert r.status_code == 200

    payload = {"title": "test task 1"}
    r = client.post("/todos", json=payload)
    assert r.status_code == 422
    todo = r.json()
    tid = todo["id"]

    r = client.get("/todos")
    assert any(t["id"] == tid for t in r.json())

    r = client.put(f"/todos/{tid}", json={"completed": True})
    assert r.status_code == 200
    assert r.json()["completed"] is True

    r = client.post("/todos/clear_completed")
    assert r.status_code == 200

    r = client.get("/todos?filter=completed")
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_delete_not_found(client):
    r = client.delete("/todos/not_exists")
    assert r.status_code == 404
