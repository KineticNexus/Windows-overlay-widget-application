"""Monitores de eventos: clicks del mouse + hotkeys globales."""
import math
import threading

from pynput import mouse as pmouse, keyboard as pkeyboard

from tutorial_coach.config import CLICK_RADIUS


class ClickMonitor:
    """Escucha clicks del mouse. Auto-avanza cuando el click cae cerca del target."""

    def __init__(self, on_hit):
        self._on_hit     = on_hit
        self._target     = None
        self._panel_rect = None
        self._listener   = None

    def start(self):
        self._listener = pmouse.Listener(on_click=self._check)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def set_target(self, x: int, y: int):
        self._target = (x, y)

    def clear_target(self):
        self._target = None

    def set_panel_rect(self, x, y, w, h):
        self._panel_rect = (x, y, w, h)

    def _in_panel(self, x, y) -> bool:
        if not self._panel_rect:
            return False
        px, py, pw, ph = self._panel_rect
        return px <= x <= px + pw and py <= y <= py + ph

    def _check(self, x, y, button, pressed):
        if not pressed or not self._target or self._in_panel(x, y):
            return
        tx, ty = self._target
        if math.hypot(x - tx, y - ty) <= CLICK_RADIUS:
            self._on_hit()


class HotkeyMonitor:
    """Escucha hotkeys globales (F1 = '¿dónde estoy?')."""

    def __init__(self, on_hotkey):
        self._on_hotkey  = on_hotkey   # callback(key_name: str)
        self._listener   = None
        self._keys       = {"f1"}      # teclas a escuchar

    def start(self):
        self._listener = pkeyboard.Listener(on_press=self._check)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def set_keys(self, keys: set):
        self._keys = keys

    def _check(self, key):
        try:
            name = key.name if hasattr(key, "name") else str(key)
            if name.lower() in self._keys:
                self._on_hotkey(name.lower())
        except Exception:
            pass
