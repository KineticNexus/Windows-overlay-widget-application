"""Configuración, constantes y prompts del sistema."""
import os
import json
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
APP_DIR    = Path(os.environ.get("APPDATA", Path.home())) / "Tortuga"
DB_PATH    = APP_DIR / "memory.db"
PREFS_PATH = APP_DIR / "preferences.json"
APP_DIR.mkdir(parents=True, exist_ok=True)

# ── Constantes ─────────────────────────────────────────────────────────────────
CLICK_RADIUS    = 90    # px de tolerancia para auto-avance
ANIM_INTERVAL   = 33    # ms entre frames (~30 fps)
GRID_STEP       = 200   # px entre líneas de la cuadrícula
VERIFY_DELAY_MS = 800   # ms de espera antes de verificar un paso
VOICE_RATE      = 160   # palabras por minuto del TTS
MODEL           = "claude-sonnet-4-6"

# ── Colores ────────────────────────────────────────────────────────────────────
ACCENT      = (56, 220, 180)
ACCENT_HEX  = "#38dcb4"
BG_DARK     = "rgba(8, 12, 28, 215)"
BG_GLASS    = "rgba(255, 255, 255, 18)"
BORDER_GLOW = "rgba(56, 220, 180, 160)"

# ── Perfiles de usuario ────────────────────────────────────────────────────────
DEFAULT_PROFILE = {
    "name": "default",
    "font_size": 14,
    "panel_font": 13,
    "voice_enabled": True,
    "voice_rate": VOICE_RATE,
    "auto_advance": True,
    "auto_verify": True,
    "hotkey_help": "f1",
    "language": "es",
    "anthropic_key": "",
    "deepgram_key": "",
}


def load_profile() -> dict:
    if PREFS_PATH.exists():
        try:
            with open(PREFS_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            return {**DEFAULT_PROFILE, **saved}
        except Exception:
            pass
    save_profile(DEFAULT_PROFILE)
    return dict(DEFAULT_PROFILE)


def save_profile(profile: dict):
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


# ── Prompts ────────────────────────────────────────────────────────────────────
PLAN_SYSTEM = """Eres Tortuga, un asistente visual que guía a personas mayores paso a paso en la computadora.
Analizas capturas de pantalla y generas respuestas JSON válidas.
NUNCA incluyas texto fuera del JSON. NUNCA uses comillas dentro de los valores de string."""

# ── Dos-fase de coordenadas ────────────────────────────────────────────────────
# Fase 1: pantalla completa dividida en 8 cuadros (4 cols × 2 filas).
#   Cuadros: fila superior 0 1 2 3 | fila inferior 4 5 6 7
# Fase 2: imagen del cuadro seleccionado → coordenadas exactas dentro de él.
# Las coordenadas globales se calculan en app.py / ai_coach.py.

PHASE1_PLAN_USER = """Analiza esta captura de pantalla.
La pantalla está dividida en 8 cuadros numerados (fila superior: 0 1 2 3 | fila inferior: 4 5 6 7).

Tarea del usuario: {goal}

Para cada paso indica en qué cuadro (0-7) se encuentra el elemento objetivo.
Responde SOLO con este JSON (sin texto extra):
{{"title":"título corto","steps":[{{"n":1,"instruction":"acción en máximo 10 palabras","square":0,"element":"descripción precisa del elemento UI"}}]}}

Reglas:
- Máximo 6 pasos. square = cuadro (0-7) donde está el elemento a usar.
- element = descripción corta y precisa: botón, icono, campo, menú, etc.
- Usa presiona en lugar de haz clic. Sin tecnicismos.
- Si la app no está visible, el primer paso es abrirla (square=0).
- Sin comillas dobles dentro de los valores de string."""

PHASE2_COORDS_USER = """Esta imagen es el recorte ampliado de UN cuadro de la pantalla.
Encuentra exactamente: {element}

Responde SOLO con este JSON:
{{"x":0.500,"y":0.500}}

x = fracción horizontal (0.000=izquierda, 0.500=centro, 1.000=derecha)
y = fracción vertical (0.000=arriba, 0.500=centro, 1.000=abajo)
El punto debe estar en el CENTRO EXACTO del elemento objetivo."""

LOCATE_PHASE1_USER = """La pantalla está dividida en 8 cuadros (fila sup: 0 1 2 3 | fila inf: 4 5 6 7).
¿En qué cuadro está: {element}?
Responde SOLO con: {{"square":0}}"""

LOCATE_PHASE2_USER = """Recorte ampliado de UN cuadro de la pantalla.
¿Dónde está exactamente: {element}?
Responde SOLO con: {{"x":0.500,"y":0.500}}
x = izquierda→derecha (0.0 a 1.0), y = arriba→abajo (0.0 a 1.0)."""

VERIFY_PROMPT = """Captura de pantalla. Usuario intentaba: {goal}
Paso {n}: {instruction} (elemento: {element})

Responde SOLO con JSON:
{{"completed":true,"feedback":"mensaje breve de confirmacion o error"}}"""

FREEQ_PROMPT = """Captura de pantalla. El usuario pregunta: {question}
Mouse en ({mx},{my}). Responde en 2 oraciones simples en español, sin tecnicismos."""

WHERE_PROMPT = """Captura de pantalla. Describe en 2 oraciones simples que ve el usuario
y que puede hacer. Lenguaje amable, sin tecnicismos, en español."""
