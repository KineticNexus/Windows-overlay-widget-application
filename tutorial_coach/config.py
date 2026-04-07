"""Configuración, constantes y prompts del sistema."""
import os
import json
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
APP_DIR   = Path(os.environ.get("APPDATA", Path.home())) / "AsistenteTutorial"
DB_PATH   = APP_DIR / "memory.db"
PREFS_PATH = APP_DIR / "preferences.json"
APP_DIR.mkdir(parents=True, exist_ok=True)

# ── Constantes ─────────────────────────────────────────────────────────────────
CLICK_RADIUS    = 90    # px de tolerancia para auto-avance
ANIM_INTERVAL   = 33    # ms entre frames (~30 fps)
GRID_STEP       = 200   # px entre líneas de la cuadrícula
VERIFY_DELAY_MS = 800   # ms de espera antes de verificar un paso
VOICE_RATE      = 160   # palabras por minuto del TTS
MODEL           = "claude-sonnet-4-6"  # modelo Claude a usar

# ── Colores (teal glassmorphism) ───────────────────────────────────────────────
ACCENT      = (56, 220, 180)
ACCENT_HEX  = "#38dcb4"
BG_DARK     = "rgba(8, 12, 28, 215)"
BG_GLASS    = "rgba(255, 255, 255, 18)"
BORDER_GLOW = "rgba(56, 220, 180, 160)"

# ── Perfiles de usuario ───────────────────────────────────────────────────────
DEFAULT_PROFILE = {
    "name": "default",
    "font_size": 14,         # instrucción en overlay
    "panel_font": 13,        # texto del panel
    "voice_enabled": True,   # TTS activo
    "voice_rate": VOICE_RATE,
    "auto_advance": True,    # avanzar al clickear el target
    "auto_verify": True,     # re-analizar pantalla tras avance
    "hotkey_help": "f1",     # tecla global "¿dónde estoy?"
    "language": "es",
    "deepgram_key": "",      # Deepgram API key (TTS+STT de alta calidad)
}


def load_profile() -> dict:
    """Carga preferencias del usuario. Crea el archivo si no existe."""
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
    """Guarda preferencias del usuario."""
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


# ── Prompts ────────────────────────────────────────────────────────────────────
PLAN_SYSTEM = """Eres un asistente experto en usabilidad que ayuda a personas mayores a usar la computadora.
Analizas capturas de pantalla con cuadrícula de coordenadas y generas planes paso a paso muy claros y simples."""

PLAN_USER = """Analiza esta captura de pantalla. La resolución física real del monitor es {w}x{h} px.

CUADRÍCULA DE REFERENCIA: La imagen tiene líneas rojas cada {grid} píxeles con números que indican
la posición exacta. El eje X va de izquierda (0) a derecha ({w}). El eje Y va de arriba (0) a abajo ({h}).
USA los números de la cuadrícula para dar coordenadas exactas.

Crea un plan paso a paso para que una persona mayor pueda: {goal}

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después:
{{
  "title": "Título corto del plan",
  "steps": [
    {{
      "n": 1,
      "instruction": "Instrucción simple de máximo 15 palabras",
      "target_x": 640,
      "target_y": 360,
      "region_w": 120,
      "region_h": 40,
      "element": "descripción visual del elemento (color, texto, forma)"
    }}
  ]
}}

Reglas CRÍTICAS:
- target_x, target_y = centro EXACTO del elemento usando la cuadrícula roja. Interpola entre líneas.
- region_w, region_h = ancho y alto aproximados del elemento clickeable en píxeles.
- Instrucciones en español. Di "presiona" no "haz clic". Di "barra de dirección" no "URL".
- Una sola acción por paso. Máximo 8 pasos.
- Si la pantalla no muestra lo necesario, el primer paso indica cómo abrir la app correcta."""

VERIFY_PROMPT = """Mira esta captura de pantalla. El usuario estaba intentando: {goal}

El paso que acaba de completar era:
Paso {n}: "{instruction}" (presionando en {element})

¿La pantalla muestra que la acción se completó correctamente?

Responde ÚNICAMENTE con JSON:
{{
  "completed": true/false,
  "feedback": "mensaje breve para el usuario (ej: ¡Perfecto! / Parece que no funcionó, intenta de nuevo)"
}}"""

FREEQ_PROMPT = """Mira esta captura de pantalla. Una persona mayor quiere saber:

"{question}"

La posición del mouse está en ({mx}, {my}).

Responde en español, en 2-3 oraciones muy simples y amables. Sin tecnicismos."""

WHERE_PROMPT = """Mira esta captura de pantalla. Explica en 2-3 oraciones muy simples
qué está viendo una persona mayor en su pantalla y qué puede hacer desde ahí.
Lenguaje amable, sin tecnicismos. Español."""
