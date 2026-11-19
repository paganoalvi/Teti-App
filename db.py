"""Base de datos de Teti App: SQLite, migraciones y consultas aisladas por bebé."""
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("TETI_DB", os.path.join(BASE, "data", "teti.db"))
os.makedirs(os.path.dirname(DB), exist_ok=True)

ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"   # sin 0/O ni 1/I/L, para evitar confusiones
CODE_LEN = 8                                   # códigos nuevos: 30^8 ≈ 6,5e11 combinaciones
LEGACY_LEN = 16                                # códigos de 16 que ya se entregaron siguen valiendo

BABIES_SQL = """CREATE TABLE IF NOT EXISTS babies (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
FEEDINGS_SQL = """CREATE TABLE IF NOT EXISTS feedings (
    baby_id TEXT NOT NULL, id TEXT NOT NULL, date TEXT NOT NULL, type TEXT NOT NULL,
    start TEXT NOT NULL, end TEXT, ml INTEGER, laps TEXT,
    PRIMARY KEY (baby_id, id))"""
INSERT = ("INSERT INTO feedings (baby_id, id, date, type, start, end, ml, laps) "
          "VALUES (:baby_id, :id, :date, :type, :start, :end, :ml, :laps)")


@contextmanager
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def norm(code):
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def pretty(code):
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def new_baby(c, name):
    name = (name or "").strip()[:60] or "Mi bebé"
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
        bid = secrets.token_hex(8)
        try:
            c.execute("INSERT INTO babies (id, name, code) VALUES (?, ?, ?)", (bid, name, code))
            return {"id": bid, "name": name, "code": pretty(code)}
        except sqlite3.IntegrityError:
            continue


def init_db():
    """Crea las tablas. Si la base es de la versión anterior (sin bebés), la migra
    de forma atómica: todas las tomas existentes pasan a un bebé nuevo."""
    con = sqlite3.connect(DB, isolation_level=None)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("BEGIN IMMEDIATE")
        con.execute(BABIES_SQL)
        cols = [r[1] for r in con.execute("PRAGMA table_info(feedings)")]
        if cols and "baby_id" not in cols:
            con.execute("ALTER TABLE feedings RENAME TO feedings_old")
            con.execute(FEEDINGS_SQL)
            if con.execute("SELECT 1 FROM feedings_old LIMIT 1").fetchone():
                baby = new_baby(con, "Mi bebé")
                laps = "laps" if "laps" in cols else "NULL"
                con.execute("INSERT INTO feedings (baby_id, id, date, type, start, end, ml, laps) "
                            f"SELECT ?, id, date, type, start, end, ml, {laps} FROM feedings_old",
                            (baby["id"],))
                print(f"[Teti App] Tomas anteriores asignadas a '{baby['name']}'. "
                      f"Código: {baby['code']}", flush=True)
            con.execute("DROP TABLE feedings_old")
        else:
            con.execute(FEEDINGS_SQL)
        con.execute("COMMIT")
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def create_baby(name):
    with db() as c:
        return new_baby(c, name)


def find_baby(code):
    code = norm(code)
    if len(code) not in (CODE_LEN, LEGACY_LEN):
        return None
    with db() as c:
        r = c.execute("SELECT id, name, code FROM babies WHERE code = ?", (code,)).fetchone()
    return {"id": r["id"], "name": r["name"], "code": pretty(r["code"])} if r else None


def rename_baby(baby_id, name):
    name = (name or "").strip()[:60]
    if name:
        with db() as c:
            c.execute("UPDATE babies SET name = ? WHERE id = ?", (name, baby_id))


# Todas las consultas de tomas exigen baby_id: no hay forma de leer o tocar tomas de otro bebé.
def _in(baby_id, f):
    d = dict(f)
    d["baby_id"] = baby_id
    d["laps"] = json.dumps(d["laps"]) if d.get("laps") else None
    return d


def list_feedings(baby_id):
    with db() as c:
        rows = c.execute("SELECT id, date, type, start, end, ml, laps FROM feedings "
                         "WHERE baby_id = ? ORDER BY date DESC, start DESC", (baby_id,))
        out = []
        for r in rows:
            d = dict(r)
            d["laps"] = json.loads(d["laps"]) if d["laps"] else None
            out.append(d)
        return out


def add_feeding(baby_id, f):
    with db() as c:
        try:
            c.execute(INSERT, _in(baby_id, f))
        except sqlite3.IntegrityError:
            return False
    return True


def add_many(baby_id, rows):
    with db() as c:
        c.executemany(INSERT.replace("INSERT", "INSERT OR IGNORE", 1), [_in(baby_id, f) for f in rows])


def update_feeding(baby_id, f):
    with db() as c:
        cur = c.execute("UPDATE feedings SET date=:date, type=:type, start=:start, end=:end, "
                        "ml=:ml, laps=:laps WHERE baby_id=:baby_id AND id=:id", _in(baby_id, f))
        return cur.rowcount > 0


def delete_feeding(baby_id, fid):
    with db() as c:
        c.execute("DELETE FROM feedings WHERE baby_id = ? AND id = ?", (baby_id, fid))


if __name__ == "__main__":      # python db.py → lista los bebés y sus códigos
    init_db()
    with db() as c:
        rows = c.execute("SELECT b.name, b.code, (SELECT COUNT(*) FROM feedings f WHERE f.baby_id = b.id) AS n "
                         "FROM babies b ORDER BY b.created_at").fetchall()
    for r in rows:
        print(f"{r['name']:<20} {pretty(r['code'])}   {r['n']} tomas")
    if not rows:
        print("Todavía no hay bebés.")
