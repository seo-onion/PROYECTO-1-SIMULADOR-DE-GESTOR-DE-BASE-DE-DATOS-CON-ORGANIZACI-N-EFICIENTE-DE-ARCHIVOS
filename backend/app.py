from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from engine import Engine


class SQLRequest(BaseModel):
    sql: str


ROOT_DIR = Path(__file__).resolve().parent.parent / "runtime"
engine = Engine(ROOT_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.close()


app = FastAPI(
    title="Proyecto 1 DB Engine API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_index():
    return FileResponse(ROOT_DIR.parent / "index.html")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "db-engine-backend"}


@app.get("/tables")
def list_tables() -> dict:
    return {"ok": True, "tables": engine.list_tables()}


@app.get("/tables/{table_name}")
def describe_table(table_name: str) -> dict:
    try:
        return {"ok": True, "table": engine.describe_table(table_name)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/query")
def execute_query(payload: SQLRequest) -> dict:
    try:
        return engine.execute(payload.sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
