"""Motor de IA — sistema de tres fases para coordenadas.

Threading:
  capture_for_three_phase() corre en el hilo principal (Qt).
  make_phase2_crop / make_phase3_crop / llamadas a Claude → hilo de fondo.

Conversión a coordenadas globales (GRID_COLS=4, GRID_ROWS=2):
  col1,row1 = sq1 % 4, sq1 // 4
  col2,row2 = sq2 % 4, sq2 // 4
  global_x  = (4·col1 + col2 + lx) / 16    ← resolución 16× en X
  global_y  = (2·row1 + row2 + ly) /  4    ← resolución  4× en Y
"""
import json
import threading

import anthropic

from tutorial_coach.config import (
    MODEL, PLAN_SYSTEM,
    PHASE1_PLAN_USER, LOCATE_PHASE1_USER,
    PHASE2_SELECT_USER, PHASE3_COORDS_USER,
    VERIFY_PROMPT, FREEQ_PROMPT, WHERE_PROMPT,
)
from tutorial_coach.capture import (
    capture_screen, capture_for_three_phase,
    make_phase2_crop, make_phase3_crop,
    GRID_COLS, GRID_ROWS,
)
from tutorial_coach.signals import Signals

_COLS = GRID_COLS   # 4
_ROWS = GRID_ROWS   # 2


class AICoach:
    def __init__(self, api_key: str, signals: Signals):
        self.client  = anthropic.Anthropic(api_key=api_key)
        self.signals = signals
        self.goal    = ""
        self._busy   = False
        self._lock   = threading.Lock()

    # ── Concurrencia ───────────────────────────────────────────────────────────
    def _is_busy(self) -> bool:
        with self._lock:
            if self._busy:
                return True
            self._busy = True
            return False

    def _release(self):
        with self._lock:
            self._busy = False

    def cancel(self):
        """Libera el lock (el hilo bg sigue hasta completar su llamada actual)."""
        self._release()

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── Claude ─────────────────────────────────────────────────────────────────
    def _call_claude(self, system: str, user_text: str,
                     image_b64: str | None = None,
                     max_tokens: int = 256) -> str:
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64",
                           "media_type": "image/jpeg",
                           "data": image_b64},
            })
        content.append({"type": "text", "text": user_text})
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text.strip()

    def _parse_json(self, raw: str) -> dict:
        """3 estrategias para extraer JSON de la respuesta."""
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        if start != -1:
            depth, in_str, esc = 0, False, False
            for i, c in enumerate(raw[start:], start):
                if esc:
                    esc = False; continue
                if c == "\\" and in_str:
                    esc = True; continue
                if c == '"':
                    in_str = not in_str; continue
                if not in_str:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(raw[start:i + 1])
                            except json.JSONDecodeError:
                                break
        raise ValueError(f"JSON no encontrado: {raw[:200]}")

    # ── Conversión de tres fases a global ──────────────────────────────────────
    @staticmethod
    def _to_global(sq1: int, sq2: int, lx: float, ly: float) -> tuple:
        """
        (sq1, sq2) ∈ [0,7], (lx, ly) ∈ [0.0, 1.0] → (gx, gy) globales.

        Ejemplo con sq1=0, sq2=0, lx=ly=0.5:
          col1=0 row1=0, col2=0 row2=0
          gx = (0 + 0 + 0.5) / 16 = 0.03125  (centro del primer sub-cuadro)
          gy = (0 + 0 + 0.5) /  4 = 0.125
        """
        col1, row1 = sq1 % _COLS, sq1 // _COLS
        col2, row2 = sq2 % _COLS, sq2 // _COLS
        gx = (_COLS * col1 + col2 + lx) / (_COLS ** 2)   # / 16
        gy = (_ROWS * row1 + row2 + ly) / (_ROWS ** 2)   # /  4
        return gx, gy

    # ── Tres fases para un elemento ────────────────────────────────────────────
    def _three_phase_coords(self, raw_img, phase1_b64: str,
                            element: str, phase1_prompt: str) -> tuple:
        """
        Ejecuta las 3 fases y devuelve (gx, gy) globales normalizadas.
        Llama a Claude 3 veces. Devuelve centro del área como fallback si falla.

        phase1_prompt ya formateado (incluye el objetivo).
        """
        # Fase 1: cuadro en la pantalla completa
        raw1 = self._call_claude(PLAN_SYSTEM, phase1_prompt,
                                 phase1_b64, max_tokens=32)
        sq1  = max(0, min(_COLS * _ROWS - 1,
                          int(self._parse_json(raw1).get("square", 0))))

        # Fase 2: sub-cuadro dentro del cuadro seleccionado
        sq1_raw, phase2_b64 = make_phase2_crop(raw_img, sq1)
        prompt2 = PHASE2_SELECT_USER.format(element=element)
        raw2    = self._call_claude(PLAN_SYSTEM, prompt2,
                                    phase2_b64, max_tokens=32)
        sq2     = max(0, min(_COLS * _ROWS - 1,
                             int(self._parse_json(raw2).get("square", 0))))

        # Fase 3: coords exactas dentro del sub-cuadro con % grid
        phase3_b64 = make_phase3_crop(sq1_raw, sq2)
        prompt3    = PHASE3_COORDS_USER.format(element=element)
        raw3       = self._call_claude(PLAN_SYSTEM, prompt3,
                                       phase3_b64, max_tokens=32)
        data3 = self._parse_json(raw3)
        lx = float(data3.get("x", 0.5))
        ly = float(data3.get("y", 0.5))
        lx = max(0.0, min(1.0, lx))
        ly = max(0.0, min(1.0, ly))

        return self._to_global(sq1, sq2, lx, ly)

    # ── Generar plan ───────────────────────────────────────────────────────────
    def generate_plan(self, goal: str):
        if self._is_busy():
            return
        self.goal = goal

        # Captura en hilo principal
        try:
            self.signals.status_changed.emit("Capturando pantalla…")
            raw_img, phase1_b64, lw, lh = capture_for_three_phase()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando pantalla: {e}")
            return

        def _run():
            try:
                # Fase 1A: obtener el plan completo con cuadros aproximados
                self.signals.status_changed.emit("Tortuga está pensando…")
                prompt1 = PHASE1_PLAN_USER.format(goal=goal)
                raw1    = self._call_claude(PLAN_SYSTEM, prompt1,
                                            phase1_b64, max_tokens=1500)
                plan    = self._parse_json(raw1)

                if "steps" not in plan or not plan["steps"]:
                    raise ValueError("El plan no tiene pasos.")

                total = len(plan["steps"])

                # Fases 2-3: afinar coordenadas para cada paso
                for i, step in enumerate(plan["steps"]):
                    element = step.get("element", "el elemento")
                    self.signals.status_changed.emit(
                        f"Localizando paso {i + 1}/{total}…")

                    # El sq1 del plan ya es una buena pista para Fase 1 de coords.
                    # Re-usamos la Fase 1 del plan: ya tenemos sq1 = step["square"].
                    # Saltamos directamente a Fase 2 (usando sq1 del plan).
                    sq1 = max(0, min(_COLS * _ROWS - 1,
                                     int(step.get("square", 0))))

                    sq1_raw, phase2_b64 = make_phase2_crop(raw_img, sq1)
                    prompt2 = PHASE2_SELECT_USER.format(element=element)
                    raw2    = self._call_claude(PLAN_SYSTEM, prompt2,
                                               phase2_b64, max_tokens=32)
                    sq2 = max(0, min(_COLS * _ROWS - 1,
                                     int(self._parse_json(raw2).get("square", 0))))

                    phase3_b64 = make_phase3_crop(sq1_raw, sq2)
                    prompt3    = PHASE3_COORDS_USER.format(element=element)
                    raw3       = self._call_claude(PLAN_SYSTEM, prompt3,
                                                   phase3_b64, max_tokens=32)
                    data3 = self._parse_json(raw3)
                    lx = max(0.0, min(1.0, float(data3.get("x", 0.5))))
                    ly = max(0.0, min(1.0, float(data3.get("y", 0.5))))

                    gx, gy = self._to_global(sq1, sq2, lx, ly)
                    step["target_x"] = gx
                    step["target_y"] = gy
                    step.setdefault("region_w", 0.06)
                    step.setdefault("region_h", 0.03)
                    step.setdefault("element",  element)

                self.signals.plan_ready.emit(plan)
                self.signals.status_changed.emit("Listo")

            except anthropic.AuthenticationError:
                self.signals.error_occurred.emit(
                    "API key inválida. Reinicia Tortuga con la clave correcta.")
            except json.JSONDecodeError as e:
                self.signals.error_occurred.emit(f"Error de formato IA: {e}")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── Mover mouse por voz ────────────────────────────────────────────────────
    def find_and_move(self, description: str):
        """Tres fases → mueve el mouse al elemento descripto."""
        if self._is_busy():
            return

        try:
            self.signals.status_changed.emit("Capturando pantalla…")
            raw_img, phase1_b64, lw, lh = capture_for_three_phase()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Buscando elemento (fase 1)…")
                prompt1 = LOCATE_PHASE1_USER.format(element=description)
                raw1    = self._call_claude(PLAN_SYSTEM, prompt1,
                                            phase1_b64, max_tokens=32)
                sq1     = max(0, min(_COLS * _ROWS - 1,
                                     int(self._parse_json(raw1).get("square", 0))))

                self.signals.status_changed.emit("Acercando (fase 2)…")
                sq1_raw, phase2_b64 = make_phase2_crop(raw_img, sq1)
                prompt2 = PHASE2_SELECT_USER.format(element=description)
                raw2    = self._call_claude(PLAN_SYSTEM, prompt2,
                                            phase2_b64, max_tokens=32)
                sq2     = max(0, min(_COLS * _ROWS - 1,
                                     int(self._parse_json(raw2).get("square", 0))))

                self.signals.status_changed.emit("Ajustando posición (fase 3)…")
                phase3_b64 = make_phase3_crop(sq1_raw, sq2)
                prompt3    = PHASE3_COORDS_USER.format(element=description)
                raw3       = self._call_claude(PLAN_SYSTEM, prompt3,
                                               phase3_b64, max_tokens=32)
                data3 = self._parse_json(raw3)
                lx = max(0.0, min(1.0, float(data3.get("x", 0.5))))
                ly = max(0.0, min(1.0, float(data3.get("y", 0.5))))

                gx, gy = self._to_global(sq1, sq2, lx, ly)

                from PyQt5.QtWidgets import QApplication
                geo    = QApplication.primaryScreen().geometry()
                px, py = int(gx * geo.width()), int(gy * geo.height())

                from pynput.mouse import Controller
                Controller().position = (px, py)

                self.signals.mouse_moved.emit(px, py)
                self.signals.status_changed.emit(f"Mouse en {description}")

            except Exception as e:
                self.signals.error_occurred.emit(f"No encontré el elemento: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── Verificar paso ─────────────────────────────────────────────────────────
    def verify_step(self, step: dict):
        if self._is_busy():
            return

        try:
            img, _, _ = capture_screen()
        except Exception:
            self._release()
            self.signals.verify_result.emit({"completed": True, "feedback": ""})
            return

        def _run():
            try:
                self.signals.status_changed.emit("Verificando…")
                prompt = VERIFY_PROMPT.format(
                    goal=self.goal,
                    n=step["n"],
                    instruction=step["instruction"],
                    element=step.get("element", ""),
                )
                raw    = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=256)
                result = self._parse_json(raw)
                result.setdefault("completed", False)
                result.setdefault("feedback", "")
                self.signals.verify_result.emit(result)
            except Exception:
                self.signals.verify_result.emit({"completed": True, "feedback": ""})
            finally:
                self._release()

        self._bg(_run)

    # ── Pregunta libre ─────────────────────────────────────────────────────────
    def ask_free(self, question: str, mouse_x: int = 0, mouse_y: int = 0):
        if self._is_busy():
            return

        try:
            img, _, _ = capture_screen()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Pensando…")
                prompt = FREEQ_PROMPT.format(question=question,
                                             mx=mouse_x, my=mouse_y)
                answer = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=300)
                self.signals.free_answer.emit(answer)
                self.signals.status_changed.emit("Listo")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── ¿Dónde estoy? ─────────────────────────────────────────────────────────
    def where_am_i(self):
        if self._is_busy():
            return

        try:
            img, _, _ = capture_screen()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Mirando tu pantalla…")
                answer = self._call_claude(PLAN_SYSTEM, WHERE_PROMPT,
                                           img, max_tokens=300)
                self.signals.free_answer.emit(answer)
                self.signals.status_changed.emit("Listo")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)
