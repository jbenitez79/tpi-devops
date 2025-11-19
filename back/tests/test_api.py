import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Asegura que se pueda importar desde back/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module
from app import app, Base, get_db, TodoModel, set_session_override

# 🔧 Crear engine SQLite en memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

set_session_override(TestingSessionLocal)

# 🧱 Crear las tablas en la base de datos de test
Base.metadata.create_all(bind=TestingSessionLocal.kw["bind"])


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# --- debug block ---

import importlib
from sqlalchemy import inspect

print("=== DEBUG: module & paths ===")
print("app module file:", app_module.__file__)
print("sys.path[0]:", sys.path[0])
print("app module repr:", repr(app_module))

print("\n=== DEBUG: engine & session objects ===")
print("test engine object:", engine)
print("app_module.engine attribute exists?:", hasattr(app_module, "engine"))
if hasattr(app_module, "engine"):
    print("app_module.engine:", app_module.engine)

print("TestingSessionLocal (test):", TestingSessionLocal)
print("app_module.SessionLocal (app):", getattr(app_module, "SessionLocal", None))

try:
    app_sess = (
        app_module.SessionLocal() if getattr(app_module, "SessionLocal", None) else None
    )
    if app_sess:
        print("app_session.get_bind():", app_sess.get_bind())
        app_sess.close()
except Exception as e:
    print("app_session creation ERROR:", type(e).__name__, e)

try:
    test_sess = TestingSessionLocal()
    print("test_session.get_bind():", test_sess.get_bind())
    test_sess.close()
except Exception as e:
    print("test_session creation ERROR:", type(e).__name__, e)

print("\n=== DEBUG: Base/metadata/tables ===")
print("Base object id:", id(Base))
print("Base.metadata.tables keys:", list(Base.metadata.tables.keys()))

try:
    print("tables on test engine:", inspect(engine).get_table_names())
except Exception as e:
    print("inspect(test engine) ERROR:", type(e).__name__, e)

if hasattr(app_module, "Base"):
    print("app_module.Base id:", id(app_module.Base))
    print(
        "app_module.Base.metadata.tables:", list(app_module.Base.metadata.tables.keys())
    )
else:
    print("app_module has no Base attribute")


# 🧪 Fixture para inyectar la sesión de test
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


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
