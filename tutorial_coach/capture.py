"""
Captura de pantalla.

Arquitectura de dos fases para máxima precisión de coordenadas:
  Fase 1: pantalla completa dividida en 8 cuadros (4×2) con números grandes.
           Claude elige el cuadro donde está el elemento objetivo.
  Fase 2: ese cuadro se recorta y amplía → Claude da coords dentro del cuadro.
  Conversión: global_x = (col + local_x) / COLS   (fracción 0.0-1.0)
              global_y = (row + local_y) / ROWS
  app.py multiplica por dimensiones lógicas de pantalla.
"""
import base64
import time
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

# Dimensiones del grid de dos fases
GRID_COLS = 4
GRID_ROWS = 2

_widgets_to_hide = []


def register_widgets(*widgets):
    _widgets_to_hide.clear()
    _widgets_to_hide.extend(widgets)


def _hide_widgets():
    """SOLO llamar desde el hilo principal."""
    from PyQt5.QtWidgets import QApplication
    for w in _widgets_to_hide:
        w.hide()
    QApplication.processEvents()
    time.sleep(0.10)


def _show_widgets():
    """SOLO llamar desde el hilo principal."""
    for w in _widgets_to_hide:
        w.show()


def _logical_size():
    """Devuelve (width, height) en píxeles lógicos de Qt."""
    from PyQt5.QtWidgets import QApplication
    geo = QApplication.primaryScreen().geometry()
    return geo.width(), geo.height()


def _raw_capture() -> Image.Image:
    """Captura la pantalla física y la devuelve como PIL Image (sin resize)."""
    with mss.mss() as sct:
        mon  = sct.monitors[1]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _draw_squares(img: Image.Image, lw: int, lh: int):
    """
    Dibuja 8 cuadros numerados (4×2) sobre img.
    Los números son grandes y muy visibles para que Claude los lea sin error.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font_num = ImageFont.truetype("arial.ttf", 96)
        font_lbl = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font_num = ImageFont.load_default()
        font_lbl = font_num

    cell_w = lw // GRID_COLS
    cell_h = lh // GRID_ROWS

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            sq_id = row * GRID_COLS + col
            x0 = col * cell_w
            y0 = row * cell_h
            x1 = x0 + cell_w - 1
            y1 = y0 + cell_h - 1

            # Borde del cuadro (rojo semitransparente)
            draw.rectangle([x0, y0, x1, y1],
                           outline=(220, 40, 40, 180), width=3)

            # Fondo para el número (esquina superior izquierda del cuadro)
            num_str = str(sq_id)
            bg_pad = 10
            bg_x0  = x0 + 12
            bg_y0  = y0 + 12
            bg_x1  = bg_x0 + 80
            bg_y1  = bg_y0 + 100
            draw.rectangle([bg_x0 - bg_pad, bg_y0 - bg_pad,
                            bg_x1 + bg_pad, bg_y1 + bg_pad],
                           fill=(255, 255, 255, 210))

            # Número grande
            draw.text((bg_x0, bg_y0), num_str,
                      fill=(200, 30, 30, 255), font=font_num)

            # Etiqueta fila/col pequeña debajo del número
            coord_lbl = f"fila {row} col {col}"
            draw.text((bg_x0, bg_y1 + 2), coord_lbl,
                      fill=(150, 30, 30, 200), font=font_lbl)


def _to_b64_jpeg(img: Image.Image, quality: int = 85,
                 max_width: int = 1920) -> str:
    if img.width > max_width:
        scale = max_width / img.width
        img = img.resize((max_width, int(img.height * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


# ── API pública ────────────────────────────────────────────────────────────────

def capture_screen_and_squares() -> tuple:
    """
    Captura la pantalla UNA SOLA VEZ y genera:
      - phase1_b64: imagen completa con 8 cuadros numerados (para Claude Fase 1)
      - squares:    lista de 8 b64, cada una es el recorte ampliado del cuadro
      - lw, lh:     dimensiones lógicas de la pantalla

    Solo llamar desde el hilo principal de Qt.
    """
    lw, lh = _logical_size()
    cell_w = lw // GRID_COLS
    cell_h = lh // GRID_ROWS

    _hide_widgets()
    try:
        raw = _raw_capture()
    finally:
        _show_widgets()

    # Redimensionar a lógico
    if raw.size != (lw, lh):
        raw = raw.resize((lw, lh), Image.LANCZOS)

    # Recortes por cuadro ANTES de agregar overlay (imagen limpia)
    squares = []
    for sq_id in range(GRID_COLS * GRID_ROWS):
        col = sq_id % GRID_COLS
        row = sq_id // GRID_COLS
        x0, y0 = col * cell_w, row * cell_h
        crop = raw.crop((x0, y0, x0 + cell_w, y0 + cell_h))
        # Ampliar 2× para mejor visión del LLM (más detalle del elemento)
        crop = crop.resize((cell_w * 2, cell_h * 2), Image.LANCZOS)
        squares.append(_to_b64_jpeg(crop, quality=92, max_width=1920))

    # Fase 1: imagen con cuadros numerados
    phase1_img = raw.copy()
    _draw_squares(phase1_img, lw, lh)
    phase1_b64 = _to_b64_jpeg(phase1_img, quality=85, max_width=1920)

    return phase1_b64, squares, lw, lh


def capture_screen(with_grid: bool = False) -> tuple:
    """
    Captura simple para verify_step, where_am_i, ask_free.
    Returns: (base64_jpeg, logical_width, logical_height)
    """
    lw, lh = _logical_size()

    _hide_widgets()
    try:
        raw = _raw_capture()
    finally:
        _show_widgets()

    if raw.size != (lw, lh):
        raw = raw.resize((lw, lh), Image.LANCZOS)

    b64 = _to_b64_jpeg(raw, quality=85, max_width=1920)
    return b64, lw, lh
