"""
Captura de pantalla — sistema de tres fases.

Fase 1 — pantalla completa con 8 cuadros numerados (4×2):
    capture_for_three_phase() → (raw_img, phase1_b64, lw, lh)
    raw_img: PIL Image en píxeles lógicos, sin overlay; se pasa al hilo bg.

Fase 2 — recorte del cuadro seleccionado con 8 sub-cuadros numerados:
    make_phase2_crop(raw_img, sq1_id) → (sq1_raw, phase2_b64)
    Puede llamarse desde hilo de fondo (solo CPU/PIL, no Qt).

Fase 3 — recorte del sub-cuadro con cuadrícula de porcentajes:
    make_phase3_crop(sq1_raw, sq2_id) → phase3_b64
    Puede llamarse desde hilo de fondo.

Conversión a global (GRID_COLS=4, GRID_ROWS=2):
    global_x = (4·col1 + col2 + lx) / 16
    global_y = (2·row1 + row2 + ly) /  4
    → resolución 16× en X y 4× en Y respecto a la pantalla completa.

capture_screen() — captura simple para verify_step / where_am_i.
"""
import base64
import time
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

# ── Constantes de grilla ───────────────────────────────────────────────────────
GRID_COLS = 4   # columnas por nivel
GRID_ROWS = 2   # filas por nivel

_widgets_to_hide: list = []


# ── Registro de widgets ────────────────────────────────────────────────────────
def register_widgets(*widgets):
    _widgets_to_hide.clear()
    _widgets_to_hide.extend(widgets)


def _hide_widgets():
    """SOLO llamar desde el hilo principal de Qt."""
    from PyQt5.QtWidgets import QApplication
    for w in _widgets_to_hide:
        w.hide()
    QApplication.processEvents()
    time.sleep(0.10)


def _show_widgets():
    for w in _widgets_to_hide:
        w.show()


def _logical_size() -> tuple:
    from PyQt5.QtWidgets import QApplication
    geo = QApplication.primaryScreen().geometry()
    return geo.width(), geo.height()


def _raw_capture() -> Image.Image:
    """Captura física → PIL Image RGB."""
    with mss.mss() as sct:
        mon  = sct.monitors[1]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


# ── Helpers de dibujo ──────────────────────────────────────────────────────────
def _load_fonts():
    try:
        return (ImageFont.truetype("arial.ttf", 88),   # números grandes
                ImageFont.truetype("arial.ttf", 16))   # etiquetas pequeñas
    except OSError:
        f = ImageFont.load_default()
        return f, f


def _draw_squares(img: Image.Image):
    """
    Dibuja GRID_COLS×GRID_ROWS cuadros numerados sobre img (in-place).
    Los números son grandes y se colocan sobre fondo blanco para máxima legibilidad.
    """
    lw, lh = img.size
    draw   = ImageDraw.Draw(img, "RGBA")
    font_n, font_s = _load_fonts()

    cell_w = lw // GRID_COLS
    cell_h = lh // GRID_ROWS

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            sq_id = row * GRID_COLS + col
            x0, y0 = col * cell_w, row * cell_h
            x1, y1 = x0 + cell_w - 1, y0 + cell_h - 1

            # Borde
            draw.rectangle([x0, y0, x1, y1],
                           outline=(210, 35, 35, 190), width=3)

            # Caja de número (esquina superior-izquierda)
            bx0, by0 = x0 + 12, y0 + 12
            bx1, by1 = bx0 + 92, by0 + 105
            draw.rectangle([bx0 - 6, by0 - 6, bx1 + 6, by1 + 6],
                           fill=(255, 255, 255, 215))
            draw.text((bx0, by0), str(sq_id),
                      fill=(195, 25, 25, 255), font=font_n)

            # Coord fila/col debajo del número
            draw.text((bx0, by1 + 4), f"f{row}c{col}",
                      fill=(140, 25, 25, 190), font=font_s)


def _draw_percent_grid(img: Image.Image):
    """
    Dibuja cuadrícula de porcentajes (25 %, 50 %, 75 %) sobre img (in-place).
    Líneas finas con etiquetas para orientar a Claude en Fase 3.
    """
    lw, lh = img.size
    draw   = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    RED = (210, 35, 35, 170)
    BG  = (255, 255, 255, 210)

    for pct in (25, 50, 75):
        x   = int(pct * lw / 100)
        y   = int(pct * lh / 100)
        lbl = f"{pct}%"
        tw  = len(lbl) * 11

        draw.line([(x, 0), (x, lh)], fill=RED, width=2)
        draw.line([(0, y), (lw, y)], fill=RED, width=2)

        # Etiqueta vertical
        draw.rectangle([x + 3, 2, x + 3 + tw, 24], fill=BG)
        draw.text((x + 5, 3), lbl, fill=(185, 20, 20, 255), font=font)

        # Etiqueta horizontal
        draw.rectangle([2, y + 3, 2 + tw, y + 25], fill=BG)
        draw.text((4, y + 4), lbl, fill=(185, 20, 20, 255), font=font)

    # Marcas de 0% y 100% en bordes
    for pct, x in ((0, 2), (100, lw - 30)):
        draw.rectangle([x, 2, x + 32, 24], fill=BG)
        draw.text((x + 2, 3), f"{pct}%", fill=(140, 20, 20, 200), font=font)
    for pct, y in ((0, 2), (100, lh - 26)):
        draw.rectangle([2, y, 34, y + 22], fill=BG)
        draw.text((4, y + 2), f"{pct}%", fill=(140, 20, 20, 200), font=font)


def _to_b64_jpeg(img: Image.Image, quality: int = 85,
                 max_width: int = 1920) -> str:
    if img.width > max_width:
        scale = max_width / img.width
        img   = img.resize((max_width, int(img.height * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


# ── API de tres fases ──────────────────────────────────────────────────────────

def capture_for_three_phase() -> tuple:
    """
    Captura UNA sola vez. Devuelve:
      raw_img    — PIL Image en píxeles lógicos (sin overlay); para Fases 2-3 en bg.
      phase1_b64 — pantalla completa con 8 cuadros numerados.
      lw, lh     — dimensiones lógicas.

    SOLO llamar desde el hilo principal de Qt.
    """
    lw, lh = _logical_size()

    _hide_widgets()
    try:
        raw = _raw_capture()
    finally:
        _show_widgets()

    if raw.size != (lw, lh):
        raw = raw.resize((lw, lh), Image.LANCZOS)

    phase1_img = raw.copy()
    _draw_squares(phase1_img)
    phase1_b64 = _to_b64_jpeg(phase1_img, quality=85, max_width=1920)

    return raw, phase1_b64, lw, lh


def make_phase2_crop(raw_img: Image.Image, sq1_id: int) -> tuple:
    """
    Recorta el cuadro sq1_id del raw completo y le dibuja 8 sub-cuadros.
    Amplía 2× para que Claude vea el detalle.

    Puede llamarse desde hilo de fondo.
    Returns: (sq1_raw, phase2_b64)
      sq1_raw   — PIL Image del cuadro SIN overlay; se pasa a make_phase3_crop.
      phase2_b64 — JPEG con sub-cuadros numerados para Claude.
    """
    lw, lh   = raw_img.size
    cell_w   = lw // GRID_COLS
    cell_h   = lh // GRID_ROWS
    col1     = sq1_id % GRID_COLS
    row1     = sq1_id // GRID_COLS
    x0, y0   = col1 * cell_w, row1 * cell_h

    sq1_raw  = raw_img.crop((x0, y0, x0 + cell_w, y0 + cell_h))

    # Ampliar 2× antes de dibujar los sub-cuadros
    phase2_img = sq1_raw.resize((cell_w * 2, cell_h * 2), Image.LANCZOS)
    _draw_squares(phase2_img)
    phase2_b64 = _to_b64_jpeg(phase2_img, quality=88, max_width=1920)

    return sq1_raw, phase2_b64


def make_phase3_crop(sq1_raw: Image.Image, sq2_id: int) -> str:
    """
    Recorta el sub-cuadro sq2_id del recorte de Fase 2 y le dibuja % grid.
    Amplía 4× para máximo detalle en Fase 3.

    Puede llamarse desde hilo de fondo.
    Returns: phase3_b64
    """
    lw, lh = sq1_raw.size
    cell_w = lw // GRID_COLS
    cell_h = lh // GRID_ROWS
    col2   = sq2_id % GRID_COLS
    row2   = sq2_id // GRID_COLS
    x0, y0 = col2 * cell_w, row2 * cell_h

    sq2_raw    = sq1_raw.crop((x0, y0, x0 + cell_w, y0 + cell_h))
    phase3_img = sq2_raw.resize((sq2_raw.width * 4, sq2_raw.height * 4),
                                Image.LANCZOS)
    _draw_percent_grid(phase3_img)
    return _to_b64_jpeg(phase3_img, quality=92, max_width=1920)


# ── Captura simple (verify / where_am_i / ask_free) ───────────────────────────

def capture_screen(with_grid: bool = False) -> tuple:
    """
    Captura sin overlay. Para verify_step, where_am_i, ask_free.
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

    return _to_b64_jpeg(raw, quality=85, max_width=1920), lw, lh
