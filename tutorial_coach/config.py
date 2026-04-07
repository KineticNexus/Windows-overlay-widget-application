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
Analizas capturas de pantalla con cuadrícula y generas planes concisos en JSON válido.
NUNCA incluyas texto fuera del JSON. NUNCA uses comillas dentro de los valores de string."""

PLAN_USER = """Analiza esta captura. Resolución del monitor: {w}x{h} px.

CUADRÍCULA: líneas rojas cada {grid} px con números de posición.
Eje X: izquierda=0, derecha={w}. Eje Y: arriba=0, abajo={h}.
USA los números visibles en la cuadrícula para coordenadas exactas.

Tarea: {goal}

Responde SOLO con este JSON (sin texto extra antes ni después):
{{"title":"título corto","steps":[{{"n":1,"instruction":"acción simple en máximo 10 palabras","target_x":640,"target_y":360,"region_w":120,"region_h":40,"element":"descripción corta del elemento"}}]}}

Reglas:
- Máximo 6 pasos. Una acción por paso.
- target_x y target_y = centro exacto del elemento usando la cuadrícula.
- Usa presiona en lugar de haz clic. Sin tecnicismos.
- Si la pantalla no muestra la app necesaria, el paso 1 es abrirla.
- Sin comillas dobles dentro de los valores de string."""

VERIFY_PROMPT = """Captura de pantalla. Usuario intentaba: {goal}
Paso {n}: {instruction} (elemento: {element})

Responde SOLO con JSON:
{{"completed":true,"feedback":"mensaje breve de confirmacion o error"}}"""

FREEQ_PROMPT = """Captura de pantalla. El usuario pregunta: {question}
Mouse en ({mx},{my}). Responde en 2 oraciones simples en español, sin tecnicismos."""

WHERE_PROMPT = """Captura de pantalla. Describe en 2 oraciones simples que ve el usuario
y que puede hacer. Lenguaje amable, sin tecnicismos, en español."""
