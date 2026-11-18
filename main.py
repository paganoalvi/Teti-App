import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("TETI_DB", os.path.join(BASE, "data", "teti.db"))
os.makedirs(os.path.dirname(DB), exist_ok=True)
TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


@contextmanager
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


with db() as c:
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS feedings (
        id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL,
        start TEXT NOT NULL, end TEXT, ml INTEGER)""")
    if "laps" not in [r[1] for r in c.execute("PRAGMA table_info(feedings)")]:
        c.execute("ALTER TABLE feedings ADD COLUMN laps TEXT")


class Feeding(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[\w-]+$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    type: Literal["teti", "formula"]
    start: str = Field(pattern=TIME)
    end: Optional[str] = Field(default=None, pattern=TIME)
    ml: Optional[int] = Field(default=None, ge=1, le=1000)
    laps: Optional[list[int]] = Field(default=None, max_length=6)  # segundos por vuelta

    @model_validator(mode="after")
    def check(self):
        if self.type == "teti":
            if not self.end:
                raise ValueError("La teti necesita hora de fin")
            if self.laps and any(x < 0 or x > 43200 for x in self.laps):
                raise ValueError("Duración de vuelta inválida")
            self.ml = None
        else:
            if self.ml is None:
                raise ValueError("La fórmula necesita mililitros")
            self.end = None
            self.laps = None
        return self


COLS = "id, date, type, start, end, ml, laps"
VALS = "(:id, :date, :type, :start, :end, :ml, :laps)"

def row(f):
    d = f.model_dump()
    d["laps"] = json.dumps(d["laps"]) if d["laps"] else None
    return d


def out(r):
    d = dict(r)
    d["laps"] = json.loads(d["laps"]) if d["laps"] else None
    return d


app = FastAPI(title="Teti App")


@app.get("/api/feedings")
def list_feedings():
    with db() as c:
        return [out(r) for r in c.execute(
            f"SELECT {COLS} FROM feedings ORDER BY date DESC, start DESC")]


@app.post("/api/feedings", status_code=201)
def create(f: Feeding):
    with db() as c:
        try:
            c.execute(f"INSERT INTO feedings ({COLS}) VALUES {VALS}", row(f))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Ya existe una toma con ese id")
    return f


@app.post("/api/feedings/bulk")
def bulk(rows: list[Feeding]):
    # Importar / migrar: ignora los ids que ya existen
    with db() as c:
        c.executemany(f"INSERT OR IGNORE INTO feedings ({COLS}) VALUES {VALS}",
                      [row(r) for r in rows])
    return {"received": len(rows)}


@app.put("/api/feedings/{fid}")
def update(fid: str, f: Feeding):
    if f.id != fid:
        raise HTTPException(400, "El id no coincide")
    with db() as c:
        cur = c.execute("UPDATE feedings SET date=:date, type=:type, start=:start, "
                        "end=:end, ml=:ml, laps=:laps WHERE id=:id", row(f))
        if cur.rowcount == 0:
            raise HTTPException(404, "Toma no encontrada")
    return f


@app.delete("/api/feedings/{fid}", status_code=204)
def delete(fid: str):
    with db() as c:
        c.execute("DELETE FROM feedings WHERE id=?", (fid,))
    return Response(status_code=204)


app.mount("/", StaticFiles(directory=os.path.join(BASE, "static"), html=True), name="static")
