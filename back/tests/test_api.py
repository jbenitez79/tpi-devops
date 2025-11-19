import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, get_db
from uuid import uuid4


class FakeDB:
    def __init__(self):
        self.todos = []

    def list(self):
        return self.todos

    def create(self, title):
        item = {"id": str(uuid4()), "title": title, "completed": False}
        self.todos.append(item)
        return item

    def get(self, todo_id):
        return next((t for t in self.todos if t["id"] == todo_id), None)

    def update(self, todo_id, completed=None, title=None):
        todo = self.get(todo_id)
        if not todo:
            return None
        if completed is not None:
            todo["completed"] = completed
        if title is not None:
            todo["title"] = title
        return todo

    def delete(self, todo_id):
        before = len(self.todos)
        self.todos = [t for t in self.todos if t["id"] != todo_id]
        return len(self.todos) != before

    def clear_completed(self):
        self.todos = [t for t in self.todos if not t["completed"]]


fake_db = FakeDB()


def override_get_db():
    yield fake_db


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_crud_flow(client):
    r = client.get("/todos")
    assert r.status_code == 200

    payload = {"title": "test task 1"}
    r = client.post("/todos", json=payload)
    assert r.status_code == 200
    todo = r.json()
    assert todo["title"] == "test task 1"
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
    assert all(t["completed"] is False for t in r.json())


def test_delete_not_found(client):
    r = client.delete("/todos/does_not_exist")
    assert r.status_code == 404
