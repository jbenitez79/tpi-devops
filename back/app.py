import os
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base

Base = declarative_base()

# Prefer DATABASE_URL (e.g. mysql+pymysql://user:pass@host:3306/dbname)
env_db = os.getenv("DATABASE_URL")
if env_db:
    DATABASE_URL = env_db
else:
    # fallback to SQLite stored under the repo's db/ folder
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "db"), exist_ok=True)
    DATABASE_URL = "sqlite:///./db/todos.db"

# Create engine, enabling sqlite-specific connect_args when needed
engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def set_engine_override(new_engine):
    global engine, SessionLocal
    engine = new_engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
    Base.metadata.create_all(bind=new_engine)


class TodoModel(Base):
    __tablename__ = "todos"
    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(1024), nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


class TodoCreate(BaseModel):
    id: Optional[str]
    title: str
    completed: Optional[bool] = False


class TodoUpdate(BaseModel):
    title: Optional[str]
    completed: Optional[bool]


class TodoOut(BaseModel):
    id: str
    title: str
    completed: bool
    createdAt: datetime

    class Config:
        orm_mode = True
        fields = {"createdAt": "created_at"}


app = FastAPI(title="ToDo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_session_override(sessionmaker_override):
    global SessionLocal
    SessionLocal = sessionmaker_override
    engine = SessionLocal.kw["bind"]
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/todos", response_model=List[TodoOut])
def list_todos(
    filter: str = Query("all", regex="^(all|active|completed)$"),
    db: Session = Depends(get_db),
):
    q = db.query(TodoModel)
    if filter == "active":
        q = q.filter(TodoModel.completed == False)
    elif filter == "completed":
        q = q.filter(TodoModel.completed == True)
    items = q.order_by(TodoModel.created_at.desc()).all()
    # Map created_at -> createdAt in response using Pydantic config
    return [
        {
            "id": t.id,
            "title": t.title,
            "completed": t.completed,
            "createdAt": t.created_at,
        }
        for t in items
    ]


@app.post("/todos", response_model=TodoOut)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    todo_id = payload.id or (
        datetime.utcnow().timestamp().__str__() + "-" + payload.title[:8]
    )
    todo = TodoModel(
        id=todo_id,
        title=payload.title.strip(),
        completed=bool(payload.completed),
        created_at=datetime.utcnow(),
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return {
        "id": todo.id,
        "title": todo.title,
        "completed": todo.completed,
        "createdAt": todo.created_at,
    }


@app.put("/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: str, payload: TodoUpdate, db: Session = Depends(get_db)):
    todo = db.query(TodoModel).filter(TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="not found")
    if payload.title is not None:
        todo.title = payload.title.strip()
    if payload.completed is not None:
        todo.completed = bool(payload.completed)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return {
        "id": todo.id,
        "title": todo.title,
        "completed": todo.completed,
        "createdAt": todo.created_at,
    }


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: str, db: Session = Depends(get_db)):
    todo = db.query(TodoModel).filter(TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(todo)
    db.commit()
    return {"ok": True}


@app.post("/todos/clear_completed")
def clear_completed(db: Session = Depends(get_db)):
    deleted = db.query(TodoModel).filter(TodoModel.completed == True).delete()
    db.commit()
    return {"deleted": deleted}


if __name__ == "__main__":
    init_db()
