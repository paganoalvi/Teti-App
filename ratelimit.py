"""Límite de intentos fallidos con código inválido, por IP, en memoria."""
import time

MAX_FAILS = 10      # intentos fallidos permitidos...
WINDOW = 600        # ...en esta cantidad de segundos
_fails = {}


def blocked(ip, now=None):
    now = time.time() if now is None else now
    _fails[ip] = [t for t in _fails.get(ip, []) if now - t < WINDOW]
    if not _fails[ip]:
        _fails.pop(ip, None)
    return len(_fails.get(ip, [])) >= MAX_FAILS


def fail(ip, now=None):
    _fails.setdefault(ip, []).append(time.time() if now is None else now)


def reset():
    _fails.clear()
