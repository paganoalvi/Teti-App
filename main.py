import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

import db
import ratelimit

db.init_db()
TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


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


class NewBaby(BaseModel):
    name: str = Field(default="", max_length=60)


def client_ip(request: Request):
    # Detrás de un proxy/túnel todos llegan con la misma IP: con TETI_TRUST_PROXY=1 se usa X-Forwarded-For.
    if os.environ.get("TETI_TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def current_baby(request: Request, x_baby_code: str = Header(default="")):
    """Identifica al bebé por el código que manda el dispositivo (cabecera X-Baby-Code)."""
    ip = client_ip(request)
    if ratelimit.blocked(ip):
        raise HTTPException(429, "Demasiados intentos. Esperá unos minutos.")
    baby = db.find_baby(x_baby_code)
    if baby is None:
        ratelimit.fail(ip)
        raise HTTPException(401, "Código de bebé inválido")
    return baby


app = FastAPI(title="Teti App")


@app.post("/api/babies", status_code=201)
def create_baby(b: NewBaby):
    baby = db.create_baby(b.name)
    return {"name": baby["name"], "code": baby["code"]}


@app.get("/api/baby")
def get_baby(baby=Depends(current_baby)):
    return {"name": baby["name"], "code": baby["code"]}


@app.put("/api/baby")
def rename_baby(b: NewBaby, baby=Depends(current_baby)):
    db.rename_baby(baby["id"], b.name)
    return {"name": b.name.strip()[:60] or baby["name"], "code": baby["code"]}


@app.get("/api/feedings")
def list_feedings(baby=Depends(current_baby)):
    return db.list_feedings(baby["id"])


@app.post("/api/feedings", status_code=201)
def create(f: Feeding, baby=Depends(current_baby)):
    if not db.add_feeding(baby["id"], f.model_dump()):
        raise HTTPException(409, "Ya existe una toma con ese id")
    return f


@app.post("/api/feedings/bulk")
def bulk(rows: list[Feeding], baby=Depends(current_baby)):
    db.add_many(baby["id"], [r.model_dump() for r in rows])
    return {"received": len(rows)}


@app.put("/api/feedings/{fid}")
def update(fid: str, f: Feeding, baby=Depends(current_baby)):
    if f.id != fid:
        raise HTTPException(400, "El id no coincide")
    if not db.update_feeding(baby["id"], f.model_dump()):
        raise HTTPException(404, "Toma no encontrada")
    return f


@app.delete("/api/feedings/{fid}", status_code=204)
def delete(fid: str, baby=Depends(current_baby)):
    db.delete_feeding(baby["id"], fid)
    return Response(status_code=204)


app.mount("/", StaticFiles(directory=os.path.join(db.BASE, "static"), html=True), name="static")
