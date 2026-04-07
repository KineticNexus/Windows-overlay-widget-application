"""Orquestador principal: conecta IA, overlay, panel, voz, monitores."""
import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QDialog

from tutorial_coach.config import VERIFY_DELAY_MS, load_profile, save_profile
from tutorial_coach.signals import Signals
from tutorial_coach.ai_coach import AICoach
from tutorial_coach.overlay import AnnotationOverlay
from tutorial_coach.panel import ControlPanel
from tutorial_coach.monitors import ClickMonitor, HotkeyMonitor
from tutorial_coach.recorder import TutorialRecorder
from tutorial_coach.dialogs import APIKeyDialog
from tutorial_coach import voice, memory, capture, calibration


class TutorialApp:
    def __init__(self, api_key: str, deepgram_key: str = "", cal: dict = None):
        self.signals  = Signals()
        self.profile  = load_profile()
        self.coach    = AICoach(api_key, self.signals)
        self.overlay  = AnnotationOverlay()
        self.panel    = ControlPanel()
        self.clicker  = ClickMonitor(on_hit=self._on_target_click)
        self.hotkeys  = HotkeyMonitor(on_hotkey=self._on_hotkey)
        self.recorder = TutorialRecorder(on_step_recorded=self._on_recorded_step)

        # Calibración DPI: escala física→lógica
        self._cal = cal or {"scale_x": 1.0, "scale_y": 1.0}

        # Deepgram
        if deepgram_key:
            voice.set_deepgram_key(deepgram_key)
            self.profile["deepgram_key"] = deepgram_key
            save_profile(self.profile)

        # Ocultar widgets durante capturas de pantalla
        capture.register_widgets(self.overlay, self.panel)

        self._steps:   list = []
        self._current: int  = 0
        self._session_id: int = 0
        self._mic_active = False

        self._connect_signals()
        self._load_history()

    # ── Señales ───────────────────────────────────────────────────────────────
    def _connect_signals(self):
        s = self.signals
        # IA → UI
        s.plan_ready.connect(self._on_plan)
        s.verify_result.connect(self._on_verify)
        s.free_answer.connect(self._on_free_answer)
        s.error_occurred.connect(self._on_error)
        s.status_changed.connect(self.panel.set_status)
        # Voz
        s.voice_text_ready.connect(self._on_voice_text)
        s.voice_status.connect(self._on_voice_status)
        # Panel → lógica
        p = self.panel
        p.goal_submitted.connect(self._on_goal)
        p.prev_clicked.connect(self._go_prev)
        p.next_clicked.connect(self._go_next)
        p.reset_clicked.connect(self._reset)
        p.mic_clicked.connect(self._toggle_mic)
        p.help_clicked.connect(self._on_help)
        p.profile_saved.connect(self._on_profile_saved)
        p.close_clicked.connect(self._quit)

    # ── Arranque ──────────────────────────────────────────────────────────────
    def run(self):
        self.overlay.show()   # geometría ya fijada en __init__, no showFullScreen
        self.panel.show()
        self.clicker.start()
        self.hotkeys.start()
        self._sync_panel_rect()

    def _quit(self):
        self.clicker.stop()
        self.hotkeys.stop()
        QApplication.quit()

    def _sync_panel_rect(self):
        self.clicker.set_panel_rect(*self.panel.get_rect())

    def _load_history(self):
        try:
            sessions = memory.get_recent_sessions(20)
            self.panel.set_history(sessions)
        except Exception:
            pass

    # ── Objetivo del usuario ──────────────────────────────────────────────────
    def _on_goal(self, text: str):
        self._steps   = []
        self._current = 0
        self.overlay.clear()
        self.coach.generate_plan(text)

    # ── Plan recibido ─────────────────────────────────────────────────────────
    def _on_plan(self, plan: dict):
        self._steps   = plan.get("steps", [])
        self._current = 0
        self.panel.set_busy(False)

        if not self._steps:
            self.panel.append_chat("⚠", "No se generaron pasos.", "#f87171")
            return

        title = plan.get("title", "")
        self.panel.append_chat(
            "Asistente",
            f"Plan: «{title}» — {len(self._steps)} pasos.",
            "#00BCD4")

        try:
            self._session_id = memory.save_session(
                self.coach.goal, plan, completed=False)
        except Exception:
            pass

        self._show_step(0)

    # ── Mostrar paso ──────────────────────────────────────────────────────────
    def _show_step(self, idx: int):
        step  = self._steps[idx]
        total = len(self._steps)

        # Las coordenadas ya son lógicas (capture.py redimensiona a lógico
        # antes del grid, Claude devuelve coords en ese espacio).
        # No se necesita conversión.
        display = dict(step,
                       target_x=int(step["target_x"]),
                       target_y=int(step["target_y"]),
                       region_w=int(step.get("region_w", 100)),
                       region_h=int(step.get("region_h", 40)))

        self.overlay.set_step(display, total)
        self.panel.show_guide_mode(step, total)
        self.clicker.set_target(display["target_x"], display["target_y"])
        self._sync_panel_rect()

        if self.profile.get("voice_enabled", True):
            voice.speak(step["instruction"])

    # ── Click en target → verificar y avanzar ─────────────────────────────────
    def _on_target_click(self):
        QTimer.singleShot(0, self._handle_target_click)

    def _handle_target_click(self):
        if not self._steps:
            return

        step = self._steps[self._current]

        if self.profile.get("auto_verify", True):
            self.panel.show_feedback("Verificando…")
            QTimer.singleShot(VERIFY_DELAY_MS,
                              lambda: self.coach.verify_step(step))
        else:
            self._advance()

    def _on_verify(self, result: dict):
        feedback = result.get("feedback", "")
        if feedback:
            self.panel.show_feedback(feedback)
            if self.profile.get("voice_enabled"):
                voice.speak(feedback)

        if result.get("completed", True):
            QTimer.singleShot(600, self._advance)

    def _advance(self):
        if self._current < len(self._steps) - 1:
            self._current += 1
            self._show_step(self._current)
        else:
            self._finish()

    def _finish(self):
        self.overlay.clear()
        self.clicker.clear_target()
        self.panel.show_finished()
        self.panel.set_status("¡Completado!")
        if self.profile.get("voice_enabled"):
            voice.speak("¡Lo lograste! Completaste todos los pasos.")
        try:
            memory.mark_completed(self._session_id)
            self._load_history()
        except Exception:
            pass

    # ── Navegación manual ─────────────────────────────────────────────────────
    def _go_next(self):
        if self._current < len(self._steps) - 1:
            self._current += 1
            self._show_step(self._current)
        else:
            self._finish()

    def _go_prev(self):
        if self._current > 0:
            self._current -= 1
            self._show_step(self._current)

    def _reset(self):
        self._steps   = []
        self._current = 0
        self.overlay.clear()
        self.clicker.clear_target()
        self.panel.show_chat_mode()
        self.panel.set_status("Listo")

    # ── Voz ───────────────────────────────────────────────────────────────────
    def _toggle_mic(self):
        if self._mic_active:
            return
        self._mic_active = True
        self.panel.set_mic_state("recording")
        voice.listen(self.signals)

    def _on_voice_text(self, text: str):
        self._mic_active = False
        self.panel.set_mic_state("idle")
        self.panel.chat_input.setText(text)
        self.panel.append_chat("Tú (voz)", text, "#34a853")
        self.panel.set_busy(True)
        self.coach.generate_plan(text)

    def _on_voice_status(self, status: str):
        if status.startswith("error:"):
            self._mic_active = False
            self.panel.set_mic_state("idle")
            self.panel.set_status(status.replace("error:", ""))
        elif status == "processing":
            self.panel.set_status("Procesando voz…")
        elif status == "idle":
            self._mic_active = False
            self.panel.set_mic_state("idle")
        elif "No escuché" in status:
            self._mic_active = False
            self.panel.set_mic_state("idle")
            self.panel.set_status(status)

    # ── Hotkey (F1 = ¿dónde estoy?) ───────────────────────────────────────────
    def _on_hotkey(self, key: str):
        QTimer.singleShot(0, self._handle_hotkey)

    def _handle_hotkey(self):
        self.coach.where_am_i()

    def _on_help(self):
        self.coach.where_am_i()

    # ── Respuesta libre ───────────────────────────────────────────────────────
    def _on_free_answer(self, text: str):
        self.panel.append_chat("Asistente", text, "#1a73e8")
        if self.profile.get("voice_enabled"):
            voice.speak(text)

    # ── Errores ───────────────────────────────────────────────────────────────
    def _on_error(self, msg: str):
        self.panel.set_busy(False)
        self.panel.append_chat("⚠ Error", msg, "#ea4335")
        self.panel.set_status("Error")

    # ── Recorder ──────────────────────────────────────────────────────────────
    def _on_recorded_step(self, step: dict):
        self.signals.recording_step.emit(step)

    # ── Configuración ─────────────────────────────────────────────────────────
    def _on_profile_saved(self, profile: dict):
        self.profile = profile
        if profile.get("deepgram_key"):
            voice.set_deepgram_key(profile["deepgram_key"])
        if "font_size" in profile:
            from PyQt5.QtGui import QFont
            self.panel.instr_lbl.setFont(QFont("Segoe UI", profile["font_size"], QFont.Bold))


# ═══════════════════════════════════════════════════════════════════════════════
#  Punto de entrada
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tortuga")

    # Inicializar base de datos
    try:
        memory.init_db()
    except Exception:
        pass

    # Verificar características de pantalla
    try:
        cal = calibration.calibrate(app)
        if not cal.get("ok", True):
            from PyQt5.QtWidgets import QMessageBox
            issues = "\n".join(f"• {i}" for i in cal.get("issues", []))
            msg = QMessageBox()
            msg.setWindowTitle("Tortuga — Aviso de pantalla")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(
                f"⚠  Se detectó inconsistencia en la configuración de pantalla.\n\n"
                f"{issues}\n\n"
                f"Pantalla: {cal.get('logical_w')}×{cal.get('logical_h')} lógico  |  "
                f"{cal.get('physical_w')}×{cal.get('physical_h')} físico  |  "
                f"DPI ratio: {cal.get('dpr')}\n\n"
                f"Las anotaciones podrían no estar perfectamente alineadas.\n"
                f"Recomendado: ajustar DPI de Windows a un valor entero (100%, 150%, 200%)."
            )
            msg.exec_()
    except Exception:
        cal = {"scale_x": 1.0, "scale_y": 1.0, "ok": False}

    # Pedir API keys
    dialog = APIKeyDialog()
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(0)

    api_key      = dialog.get_key()
    deepgram_key = dialog.get_deepgram_key()

    # Lanzar
    tutorial = TutorialApp(api_key, deepgram_key=deepgram_key, cal=cal)
    tutorial.run()

    sys.exit(app.exec_())
