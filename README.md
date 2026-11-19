# Teti App 🍼

Aplicación web para llevar el registro de las tomas de un bebé: **teti** (con cronómetro) y **leche de fórmula** (por mililitros). Pensada para que mamá y papá la usen desde el celular, con una sola mano y a cualquier hora de la noche.

Es de **código abierto**, de libre distribución y personalización. Se creó como un aporte a la comunidad: podés descargarla, modificarla y adaptarla a tus necesidades.

## Características

**Cargar tomas**
- **Cronómetro de teti** con botones grandes: *Iniciar / Pausar / Reanudar*, *Cambiar de teta* (marca una vuelta, también en pausa), *Guardar* y *Reiniciar*. Al guardar, la app registra sola la hora de inicio, la de fin y el tiempo de cada vuelta.
- **Fórmula en dos toques**: se escribe la cantidad en ml y *Registrar ahora* guarda la toma con la fecha y hora de ese instante. Si fue en otro momento, la fecha y la hora se pueden editar.
- **Carga manual** de tomas de teti pasadas (hora de inicio y minutos de cada vuelta).
- Editar y borrar cualquier toma desde el historial.

**Última toma y próxima toma**
- Indicador grande con *"hace X h Y min"* desde el inicio de la última toma, sea de teti o de fórmula.
- Cambia de color según el tiempo transcurrido: **verde** (primera hora), **naranja** (segunda) y **rojo** (desde las 2 h), con un latido suave al llegar a las 3 h.
- Muestra la hora estimada de la **próxima toma** (inicio de la última + 3 h).

**Resumen**
- Últimas 4 tomas del día elegido y botón para ver el historial completo.
- Selector de fecha que controla tomas, métricas y gráficos.
- Métricas del día: tomas totales, tomas de teti (cada ciclo con todas sus vueltas cuenta como una), tomas de fórmula, minutos de teti, ml de fórmula, promedios y tiempo promedio entre tomas.
- Gráficos de los últimos 7 días: tomas, minutos de teti y ml de fórmula.

**Otros**
- **Un código por bebé:** cada bebé tiene un código secreto. Quien lo ingresa en su celular ve las mismas tomas (por ejemplo, ambos padres); otras familias crean su propio bebé y nunca ven datos ajenos. El código se ve y se copia desde el engranaje de configuración, para pasárselo a quien deba ver las mismas tomas.
- Los datos viven en el servidor: los dispositivos de un mismo bebé se actualizan solos cada 10 segundos.
- Copia de seguridad: descargar e importar un archivo JSON desde la app.
- Ayuda e información del proyecto en ventanas emergentes.
- Diseño en tonos crema, rosa y celeste, optimizado para celular.

## ¿Desde cuándo se cuenta "última toma"?

Siempre desde el **inicio** de la última toma (en teti, el primer toque en *Iniciar*; en fórmula, la hora registrada). Las pausas, los cambios de teta y la duración de la toma no influyen. Por ejemplo: si la toma empezó a las 00:18 y ahora son las 01:22, el indicador marca *hace 1 h 4 min*.

## Tecnologías

- **Backend:** Python, [FastAPI](https://fastapi.tiangolo.com/) y SQLite.
- **Frontend:** HTML, CSS y JavaScript sin frameworks ni paso de compilación.
- Probado en Ubuntu 24.04 con Python 3.12 (compatible con Python 3.9 o superior).

## Estructura

```
teti-app/
├── main.py              # API REST + servidor de archivos estáticos
├── db.py                # Base SQLite, migraciones y consultas aisladas por bebé
├── requirements.txt     # Dependencias de Python
├── requirements-dev.txt # Dependencias para correr las pruebas
├── tests/               # Pruebas de aislamiento de datos entre bebés
├── teti-app.service     # Unidad de systemd de ejemplo
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── data/                # Se crea sola; contiene teti.db (no se sube al repo)
```

## Instalación

### Probarla en tu computadora

```bash
git clone https://github.com/<tu-usuario>/teti-app.git
cd teti-app
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Abrí `http://localhost:8000`. Para acceder desde el celular, usá la IP de tu computadora en la misma red wifi, por ejemplo `http://192.168.1.50:8000`.

### Dejarla funcionando en un servidor Linux (systemd)

1. Copiá la carpeta al servidor (por ejemplo a `~/teti-app`) y creá el entorno virtual como en el paso anterior. En Ubuntu puede hacer falta `sudo apt install python3-venv`.
2. Editá `teti-app.service` y ajustá `User`, `WorkingDirectory`, `ExecStart` y el puerto (`--port`) a tu caso.
3. Activala:

```bash
sudo cp teti-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now teti-app
```

Para ver los registros: `journalctl -u teti-app -f`. Después de actualizar `main.py` hay que reiniciar el servicio (`sudo systemctl restart teti-app`); los cambios en `static/` se ven con solo recargar la página.

### Actualizar desde una versión sin bebés

Al iniciar, el servidor migra la base de forma automática: todas las tomas existentes pasan a un bebé llamado "Mi bebé" y se imprime su código en el registro (`journalctl -u teti-app`). Para ver los códigos en cualquier momento: `./venv/bin/python db.py`. Hacé una copia de `data/teti.db` antes de actualizar.

## Pruebas

```bash
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest
```

Verifican que un bebé no pueda leer, editar, borrar ni importar tomas de otro, y que la migración desde la base anterior conserve los datos.

## Personalización

- **Umbral de la próxima toma y alerta:** constante `ALERT_MIN` en `static/app.js` (180 minutos por defecto).
- **Colores del indicador:** lista `TINTS` en `static/app.js`; el primer número de cada fila es el minuto en que empieza ese color.
- **Paleta y estilos:** variables CSS al inicio de `static/style.css`.
- **Ubicación de la base de datos:** variable de entorno `TETI_DB` (por defecto `data/teti.db`).

## API

Todas las rutas de tomas y del bebé exigen la cabecera `X-Baby-Code` con el código del bebé; sin ella, o con un código inválido, responden `401` (y `429` tras demasiados intentos fallidos). El servidor solo opera sobre las tomas de ese bebé.

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/babies` | Crea un bebé (`{"name": "..."}`) y devuelve su código |
| `GET` | `/api/baby` | Datos del bebé (sirve para validar un código) |
| `PUT` | `/api/baby` | Cambia el nombre del bebé |
| `GET` | `/api/feedings` | Lista las tomas del bebé |
| `POST` | `/api/feedings` | Crea una toma |
| `PUT` | `/api/feedings/{id}` | Actualiza una toma |
| `DELETE` | `/api/feedings/{id}` | Borra una toma |
| `POST` | `/api/feedings/bulk` | Importa varias tomas (ignora los ids que ya existen) |

Cada toma tiene esta forma:

```json
{
  "id": "m3k9x2ab",
  "date": "2026-11-18",
  "type": "teti",
  "start": "00:18",
  "end": "00:55",
  "ml": null,
  "laps": [600, 900, 300]
}
```

- `type` es `"teti"` o `"formula"`.
- En `teti`, `laps` guarda los segundos de cada vuelta (máximo 6) y `ml` es `null`.
- En `formula`, `ml` es la cantidad en mililitros y `end` y `laps` son `null`.
- Si `end` es menor que `start`, la toma terminó después de medianoche.

## Seguridad y respaldo

- No hay cuentas de usuario: cada bebé se protege con un código secreto de 8 caracteres (los códigos de 16 emitidos antes siguen valiendo), y el servidor solo entrega las tomas del bebé cuyo código recibe. Quien tenga el código ve esos datos, así que compartilo con cuidado.
- Tras 10 intentos fallidos con un código inválido en 10 minutos, el servidor bloquea esa IP temporalmente (respuesta `429`); detrás de un proxy o túnel, definí `TETI_TRUST_PROXY=1` para que cuente por IP real. Cualquiera que conozca la dirección del servidor puede crear un bebé nuevo. Si lo publicás en internet, usá siempre **HTTPS** y no difundas la dirección.
- Para respaldar los datos, copiá `data/teti.db` o usá *Descargar copia* dentro de la app.

## Limitaciones y próximos pasos

- El estado del cronómetro se guarda en el dispositivo donde se inicia; la toma se comparte con el resto cuando se guarda.
- Al servirse por HTTP, el navegador no permite notificaciones push. Está previsto convertirla en una **PWA** y explorar alarmas o avisos cuando pasen 3 horas desde la última toma.
- Las tomas de teti anteriores a las vueltas (cargadas con desde/hasta) cuentan como una toma cada una.

## Contribuir

Las ideas, los reportes de errores y los pull requests son bienvenidos. Podés abrir un *issue* para proponer cambios o hacer un *fork* y adaptar la app a tu familia.

## Licencia

Distribuida bajo la licencia [MIT](LICENSE): podés usarla, copiarla, modificarla y redistribuirla libremente.

## Apoyar el proyecto

Teti App no tiene fines de lucro. Si querés colaborar con una donación, el alias del equipo de desarrollo es **`alva.pagano`**.
