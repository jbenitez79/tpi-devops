import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Asegura que se pueda importar desde back/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app as app_module, Base, get_db, TodoModel, set_session_override

# 🔧 Crear engine SQLite en memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

set_session_override(TestingSessionLocal)

# 🧱 Crear las tablas en la base de datos de test
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app_module.dependency_overrides[app_module.get_db] = override_get_db


# 🧪 Fixture para inyectar la sesión de test
@pytest.fixture(scope="module")
def client():
    return TestClient(app_module)


# ✅ Test de salud
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_crud_flow(client):
    r = client.get("/todos")
    assert r.status_code == 200
    items = r.json()

    payload = {"title": "test task 1"}
    r = client.post("/todos", json=payload)
    assert r.status_code == 200
    todo = r.json()
    assert todo["title"] == "test task 1"
    tid = todo["id"]

    r = client.get("/todos")
    assert r.status_code == 200
    assert any(t["id"] == tid for t in r.json())

    r = client.put(f"/todos/{tid}", json={"completed": True})
    assert r.status_code == 200
    assert r.json()["completed"] is True

    r = client.post("/todos/clear_completed")
    assert r.status_code == 200

    r = client.get("/todos?filter=completed")
    assert r.status_code == 200
    assert all(t["id"] != tid for t in r.json())


# ❌ Test de borrado de ID inexistente
def test_delete_not_found(client):
    r = client.delete("/todos/nonexistent_id")
    assert r.status_code == 404
