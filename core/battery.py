# =============================================================================
# core/battery.py
# =============================================================================

"""
Monitor de batería con alertas al servidor Minecraft.
"""

import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class BatteryMonitor:
    """Monitor de batería con alertas en juego."""

    def __init__(self, settings, minecraft_server):
        self.settings = settings
        self.minecraft = minecraft_server

        self.log_file = settings.log_dir / "battery.log"
        self.pid_file = settings.run_dir / "battery.pid"
        self.state_file = settings.run_dir / "battery_state.json"

        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Estado de alertas
        self.alert_state = {"alert_20": False, "alert_10": False, "alert_5": False}

        self._load_state()

    def start(self) -> bool:
        """
        Inicia el monitor de batería.

        Returns:
            True si inició correctamente
        """
        if self.running:
            self._log("Monitor de batería ya está corriendo")
            return True

        # Verificar que termux-battery-status esté disponible
        if not self._check_termux_api():
            self._log("ERROR: termux-battery-status no disponible")
            return False

        if not self.minecraft.is_running():
            self._log(
                "ADVERTENCIA: Minecraft no está corriendo, alertas no funcionarán"
            )

        self._log("Iniciando monitor de batería...")

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

        # Guardar "PID" (thread ID)
        self.pid_file.write_text("running")

        self._log("Monitor de batería iniciado")
        return True

    def stop(self):
        """Detiene el monitor."""
        if not self.running:
            return

        self._log("Deteniendo monitor de batería...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=5)

        self.pid_file.unlink(missing_ok=True)
        self._log("Monitor de batería detenido")

    def is_running(self) -> bool:
        """Verifica si está corriendo."""
        return self.running and self.thread and self.thread.is_alive()

    def _monitor_loop(self):
        """Loop principal del monitor."""
        interval = self.settings.battery_check_interval

        self._log(f"Loop iniciado (intervalo: {interval}s)")

        while self.running:
            time.sleep(interval)

            # Solo monitorear si Minecraft está corriendo
            if not self.minecraft.is_running():
                continue

            battery_info = self._get_battery_info()
            if not battery_info:
                continue

            level = battery_info["level"]
            status = battery_info["status"]

            # Si está cargando, resetear alertas
            if status in ["CHARGING", "FULL"]:
                if any(self.alert_state.values()):
                    self._reset_alerts()
                continue

            # Verificar y enviar alertas
            self._check_and_alert(level)

    def _check_and_alert(self, level: int):
        """
        Verifica el nivel de batería y envía alertas si es necesario.

        Args:
            level: Nivel de batería actual
        """
        # Alerta 20%
        if (
            level <= 20
            and not self.alert_state["alert_20"]
            and self.settings.battery_alert_20
        ):
            self._send_alert(level, "§e⚠  ALERTA: Batería del servidor al {level}%")
            self.alert_state["alert_20"] = True
            self._save_state()

        # Alerta 10%
        if (
            level <= 10
            and not self.alert_state["alert_10"]
            and self.settings.battery_alert_10
        ):
            self._send_alert(level, "§c⚠ ⚠  ADVERTENCIA: Batería BAJA {level}%")
            self.alert_state["alert_10"] = True
            self._save_state()

        # Alerta 5%
        if (
            level <= 5
            and not self.alert_state["alert_5"]
            and self.settings.battery_alert_5
        ):
            self._send_alert(
                level, "§4⚠ ⚠ ⚠  CRÍTICO: Batería {level}% - ¡Apagado inminente!"
            )
            self.alert_state["alert_5"] = True
            self._save_state()

    def _send_alert(self, level: int, message_template: str):
        """
        Envía alerta al servidor Minecraft.

        Args:
            level: Nivel de batería
            message_template: Template del mensaje con {level}
        """
        message = message_template.format(level=level)
        command = f"say {message}"

        if self.minecraft.send_command(command):
            self._log(f"Alerta enviada: {message}")
        else:
            self._log(f"ERROR enviando alerta: {message}")

    def _reset_alerts(self):
        """Resetea todas las alertas."""
        self.alert_state = {"alert_20": False, "alert_10": False, "alert_5": False}
        self._save_state()
        self._log("Alertas reseteadas (dispositivo cargando)")

    def _get_battery_info(self) -> Optional[dict]:
        """
        Obtiene información de batería usando termux-api.

        Returns:
            Diccionario con info o None si falla
        """
        try:
            result = subprocess.run(
                ["termux-battery-status"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)

            return {
                "level": data.get("percentage", 0),
                "status": data.get("status", "UNKNOWN"),
                "temperature": data.get("temperature", 0),
            }

        except Exception as e:
            self._log(f"Error obteniendo info de batería: {e}")
            return None

    def _check_termux_api(self) -> bool:
        """
        Verifica que termux-battery-status funcione.

        Returns:
            True si está disponible
        """
        try:
            result = subprocess.run(
                ["termux-battery-status"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_status(self) -> dict:
        """Obtiene el estado completo."""
        battery_info = self._get_battery_info()

        return {
            "running": self.is_running(),
            "battery_info": battery_info,
            "alert_state": self.alert_state.copy(),
            "interval": self.settings.battery_check_interval,
        }

    def _save_state(self):
        """Guarda el estado de alertas a disco."""
        with open(self.state_file, "w") as f:
            json.dump(self.alert_state, f)

    def _load_state(self):
        """Carga el estado previo."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self.alert_state = json.load(f)
            except Exception:
                pass

    def _log(self, message: str):
        """Escribe al log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message)
