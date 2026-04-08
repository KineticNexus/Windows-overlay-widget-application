"""Motor de IA: genera planes (dos fases), verifica pasos, mueve mouse por voz.

Threading:
  - capture_screen / capture_screen_and_squares corren en el hilo principal (Qt).
  - Solo las llamadas a Claude van al hilo de fondo.
  - Signals PyQt5 cross-thread son thread-safe (queued connections).

Dos-fase de coordenadas:
  Fase 1 → Claude elige el cuadro (0-7) donde está el elemento.
  Fase 2 → Claude da (x,y) normalizado dentro del recorte de ese cuadro.
  global_x = (col + local_x) / GRID_COLS
  global_y = (row + local_y) / GRID_ROWS
"""
import json
import threading

import anthropic

from tutorial_coach.config import (
    MODEL, PLAN_SYSTEM,
    PHASE1_PLAN_USER, PHASE2_COORDS_USER,
    LOCATE_PHASE1_USER, LOCATE_PHASE2_USER,
    VERIFY_PROMPT, FREEQ_PROMPT, WHERE_PROMPT,
)
from tutorial_coach.capture import (
    capture_screen, capture_screen_and_squares,
    GRID_COLS, GRID_ROWS,
)
from tutorial_coach.signals import Signals

_COLS = GRID_COLS
_ROWS = GRID_ROWS


class AICoach:
    def __init__(self, api_key: str, signals: Signals):
        self.client  = anthropic.Anthropic(api_key=api_key)
        self.signals = signals
        self.goal    = ""
        self._busy   = False
        self._lock   = threading.Lock()

    # ── Utilidades ─────────────────────────────────────────────────────────────
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
        """Libera el lock para permitir nuevas operaciones (hilo bg sigue corriendo)."""
        self._release()

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
        """Extrae JSON robusto con tres estrategias antes de fallar."""
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
            depth, in_str, escaped = 0, False, False
            for i, c in enumerate(raw[start:], start):
                if escaped:
                    escaped = False; continue
                if c == "\\" and in_str:
                    escaped = True; continue
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

        raise ValueError(f"Respuesta de IA no contiene JSON válido: {raw[:200]}")

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── Conversión de cuadro a coordenadas globales ─────────────────────────
    def _square_to_global(self, square_id: int,
                          local_x: float, local_y: float) -> tuple:
        """Convierte (square_id, local x/y) a coordenadas globales normalizadas."""
        col = square_id % _COLS
        row = square_id // _COLS
        gx = (col + local_x) / _COLS
        gy = (row + local_y) / _ROWS
        return gx, gy

    def _phase2_coords(self, squares: list, square_id: int,
                       element: str) -> tuple:
        """
        Fase 2: pide a Claude las coordenadas dentro del cuadro.
        Devuelve (global_x, global_y) normalizadas 0.0-1.0.
        En caso de error devuelve el centro del cuadro.
        """
        sq = max(0, min(_COLS * _ROWS - 1, square_id))
        try:
            prompt = PHASE2_COORDS_USER.format(element=element)
            raw    = self._call_claude(PLAN_SYSTEM, prompt,
                                       squares[sq], max_tokens=64)
            data   = self._parse_json(raw)
            lx = float(data.get("x", 0.5))
            ly = float(data.get("y", 0.5))
        except Exception:
            lx, ly = 0.5, 0.5
        return self._square_to_global(sq, lx, ly)

    # ── Generar plan (dos fases) ───────────────────────────────────────────────
    def generate_plan(self, goal: str):
        if self._is_busy():
            return
        self.goal = goal

        # Fase 0: captura en hilo principal
        try:
            self.signals.status_changed.emit("Capturando pantalla…")
            phase1_b64, squares, lw, lh = capture_screen_and_squares()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando pantalla: {e}")
            return

        def _run():
            try:
                # Fase 1: qué pasos y en qué cuadro está cada elemento
                self.signals.status_changed.emit("Tortuga está pensando…")
                prompt1 = PHASE1_PLAN_USER.format(goal=goal)
                raw1    = self._call_claude(PLAN_SYSTEM, prompt1,
                                            phase1_b64, max_tokens=1500)
                plan    = self._parse_json(raw1)

                if "steps" not in plan or not plan["steps"]:
                    raise ValueError("El plan no tiene pasos.")

                # Fase 2: coordenadas precisas para cada paso
                total = len(plan["steps"])
                for i, s in enumerate(plan["steps"]):
                    self.signals.status_changed.emit(
                        f"Ubicando paso {i + 1}/{total}…")
                    sq      = int(s.get("square", 0))
                    element = s.get("element", "el elemento")
                    gx, gy  = self._phase2_coords(squares, sq, element)
                    s["target_x"] = gx
                    s["target_y"] = gy
                    s.setdefault("region_w", 0.08)
                    s.setdefault("region_h", 0.04)
                    s.setdefault("element",  element)

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

    # ── Mover mouse por voz (dos fases) ───────────────────────────────────────
    def find_and_move(self, description: str):
        """
        Captura pantalla, ubica el elemento mediante dos fases y mueve el mouse.
        Emite mouse_moved(x, y) cuando termina.
        """
        if self._is_busy():
            return

        try:
            self.signals.status_changed.emit("Buscando elemento…")
            phase1_b64, squares, lw, lh = capture_screen_and_squares()
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                # Fase 1: ¿en qué cuadro?
                prompt1 = LOCATE_PHASE1_USER.format(element=description)
                raw1    = self._call_claude(PLAN_SYSTEM, prompt1,
                                            phase1_b64, max_tokens=32)
                data1   = self._parse_json(raw1)
                sq      = max(0, min(_COLS * _ROWS - 1,
                                     int(data1.get("square", 0))))

                # Fase 2: coords exactas en el cuadro
                prompt2 = LOCATE_PHASE2_USER.format(element=description)
                raw2    = self._call_claude(PLAN_SYSTEM, prompt2,
                                            squares[sq], max_tokens=32)
                data2   = self._parse_json(raw2)
                lx = float(data2.get("x", 0.5))
                ly = float(data2.get("y", 0.5))

                gx, gy = self._square_to_global(sq, lx, ly)

                # Convertir a píxeles lógicos
                from PyQt5.QtWidgets import QApplication
                geo    = QApplication.primaryScreen().geometry()
                px, py = int(gx * geo.width()), int(gy * geo.height())

                # Mover mouse
                from pynput.mouse import Controller
                Controller().position = (px, py)

                self.signals.mouse_moved.emit(px, py)
                self.signals.status_changed.emit(
                    f"Mouse movido a {description}")

            except Exception as e:
                self.signals.error_occurred.emit(
                    f"No encontré el elemento: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── Verificar paso ─────────────────────────────────────────────────────────
    def verify_step(self, step: dict):
        if self._is_busy():
            return

        try:
            img, pw, ph = capture_screen()
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
                raw    = self._call_claude(PLAN_SYSTEM, prompt,
                                           img, max_tokens=256)
                result = self._parse_json(raw)
                result.setdefault("completed", False)
                result.setdefault("feedback", "")
                self.signals.verify_result.emit(result)
            except Exception:
                self.signals.verify_result.emit(
                    {"completed": True, "feedback": ""})
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
                prompt = FREEQ_PROMPT.format(
                    question=question, mx=mouse_x, my=mouse_y)
                answer = self._call_claude(PLAN_SYSTEM, prompt,
                                           img, max_tokens=300)
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
