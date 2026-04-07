"""
Calibración de pantalla usando múltiples fuentes de datos:
  1. Qt devicePixelRatio()       — razón DPI del sistema
  2. mss                         — resolución física real
  3. ctypes Win32 API            — DPI del sistema Windows
  4. Verificación de consistencia entre fuentes

Con la nueva arquitectura (capture.py redimensiona a lógico antes del grid),
scale_x / scale_y = 1.0 — no se necesita conversión de coordenadas.
La calibración verifica que el sistema esté configurado correctamente.
"""
import mss


def calibrate(qt_app) -> dict:
    """
    Obtiene características reales de pantalla y verifica consistencia.
    Retorna dict con info de pantalla y campo 'ok'.
    """
    # ── Fuente 1: Qt ─────────────────────────────────────────────────────────
    screen    = qt_app.primaryScreen()
    dpr       = screen.devicePixelRatio()         # 1.0 / 1.25 / 1.5 / 2.0
    logical_w = screen.geometry().width()
    logical_h = screen.geometry().height()
    phys_dpi  = screen.physicalDotsPerInch()
    logic_dpi = screen.logicalDotsPerInch()

    # ── Fuente 2: mss (píxeles físicos reales del hardware) ──────────────────
    with mss.mss() as sct:
        mon    = sct.monitors[1]
        phys_w = mon["width"]
        phys_h = mon["height"]

    # ── Fuente 3: Windows ctypes (DPI del sistema) ───────────────────────────
    win_dpi   = None
    win_scale = None
    try:
        import ctypes
        # SetProcessDpiAwareness — asegura que obtenemos el DPI real
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        win_dpi   = ctypes.windll.user32.GetDpiForSystem()
        win_scale = win_dpi / 96.0   # 96 DPI = escala 1.0 en Windows
    except Exception:
        pass

    # ── Verificación de consistencia ─────────────────────────────────────────
    # Las tres fuentes deben coincidir para coordenadas correctas
    mss_scale_x = phys_w / logical_w if logical_w > 0 else 1.0
    mss_scale_y = phys_h / logical_h if logical_h > 0 else 1.0

    issues = []
    if abs(mss_scale_x - dpr) > 0.15:
        issues.append(f"mss/Qt X: {mss_scale_x:.3f} vs devicePixelRatio {dpr:.3f}")
    if abs(mss_scale_y - dpr) > 0.15:
        issues.append(f"mss/Qt Y: {mss_scale_y:.3f} vs devicePixelRatio {dpr:.3f}")
    if win_scale is not None and abs(win_scale - dpr) > 0.15:
        issues.append(f"Win32 DPI: {win_scale:.3f} vs Qt {dpr:.3f}")

    ok = len(issues) == 0

    return {
        # Con la nueva arquitectura las imágenes se redimensionan a lógico
        # antes de dibujar el grid → Claude siempre devuelve coords lógicas
        "scale_x":    1.0,
        "scale_y":    1.0,
        # Info informativa
        "dpr":        dpr,
        "physical_w": phys_w,
        "physical_h": phys_h,
        "logical_w":  logical_w,
        "logical_h":  logical_h,
        "phys_dpi":   phys_dpi,
        "logic_dpi":  logic_dpi,
        "win_dpi":    win_dpi,
        "win_scale":  win_scale,
        "mss_scale_x": round(mss_scale_x, 4),
        "mss_scale_y": round(mss_scale_y, 4),
        "ok":         ok,
        "issues":     issues,
    }
