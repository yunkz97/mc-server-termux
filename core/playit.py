"""
Gestor robusto de Playit.gg con state machine, health checks y auto-reconnect.
Diseñado para ser extremadamente confiable.
"""

import re
import time
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class PlayitState(Enum):
    """Estados del túnel Playit."""
    STOPPED = "stopped"
    STARTING = "starting"
    WAITING_CLAIM = "waiting_claim"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class PlayitManager:
    """Gestor del túnel Playit.gg con manejo robusto de errores."""

    def __init__(self, settings):
        self.settings = settings
        self.binary = settings.get_playit_binary()
        self.log_file = settings.log_dir / "playit.log"
        self.pid_file = settings.run_dir / "playit.pid"
        self.state_file = settings.run_dir / "playit_state.json"

        self.state = PlayitState.STOPPED
        self.process: Optional[subprocess.Popen] = None
        self.claim_url: Optional[str] = None
        self.tunnel_address: Optional[str] = None

        # Health check
        self.health_thread: Optional[threading.Thread] = None
        self.health_running = False

        # Reconnect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.last_reconnect_time: Optional[datetime] = None

        # Cargar estado persistente si existe
        self._load_state()

    def start(self, timeout: int = 120) -> bool:
        """
        Inicia el túnel Playit.gg con detección robusta.

        Args:
            timeout: Tiempo máximo de espera en segundos

        Returns:
            True si inició correctamente
        """
        if self.is_running():
            return True

        if not self.binary.exists():
            raise FileNotFoundError(f"Playit binary no encontrado: {self.binary}")

        self.state = PlayitState.STARTING
        self._log("Iniciando Playit.gg...")

        try:
            # Limpiar log anterior
            self.log_file.write_text("")

            # Iniciar proceso con proot
            self.process = subprocess.Popen(
                ["termux-chroot", str(self.binary)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Guardar PID
            self.pid_file.write_text(str(self.process.pid))

            # Detectar claim URL o conexión
            start_time = time.time()
            self.state = PlayitState.WAITING_CLAIM

            while time.time() - start_time < timeout:
                # Verificar que el proceso sigue vivo
                if self.process.poll() is not None:
                    self.state = PlayitState.ERROR
                    self._log("El proceso terminó inesperadamente")
                    return False

                # Intentar múltiples métodos de detección
                if self._detect_claim_url():
                    self.state = PlayitState.WAITING_CLAIM
                    self._log(f"Claim URL detectada: {self.claim_url}")
                    self._save_state()
                    return True

                if self._detect_tunnel_address():
                    self.state = PlayitState.CONNECTED
                    self._log(f"Túnel conectado: {self.tunnel_address}")
                    self._start_health_monitor()
                    self._save_state()
                    return True

                time.sleep(1)

            # Timeout alcanzado
            self.state = PlayitState.ERROR
            self._log("Timeout esperando respuesta de Playit")
            self.stop()
            return False

        except Exception as e:
            self.state = PlayitState.ERROR
            self._log(f"Error iniciando Playit: {e}")
            self.stop()
            return False

    def _detect_claim_url(self) -> bool:
        """
        Detecta la URL de claim usando múltiples métodos.

        Returns:
            True si se detectó la URL
        """
        if not self.log_file.exists():
            return False

        try:
            # Leer log completo
            log_content = self.log_file.read_text(errors='ignore')

            # Método 1: Regex directo
            pattern = r'https://playit\.gg/claim/[a-zA-Z0-9]+'
            matches = re.findall(pattern, log_content)
            if matches:
                self.claim_url = matches[0]
                return True

            # Método 2: Buscar líneas con "claim"
            for line in log_content.split('\n'):
                if 'claim' in line.lower() and 'playit.gg' in line:
                    matches = re.findall(pattern, line)
                    if matches:
                        self.claim_url = matches[0]
                        return True

            # Método 3: Leer directamente del proceso si está disponible
            if self.process and self.process.stdout:
                try:
                    # Non-blocking read
                    import select
                    if select.select([self.process.stdout], [], [], 0)[0]:
                        output = self.process.stdout.readline()
                        if output:
                            # Escribir a log
                            with open(self.log_file, 'a') as f:
                                f.write(output)

                            matches = re.findall(pattern, output)
                            if matches:
                                self.claim_url = matches[0]
                                return True
                except:
                    pass

            return False

        except Exception as e:
            self._log(f"Error detectando claim URL: {e}")
            return False

    def _detect_tunnel_address(self) -> bool:
        """
        Detecta si el túnel ya está conectado (sin necesidad de claim).

        Returns:
            True si el túnel está activo
        """
        if not self.log_file.exists():
            return False

        try:
            log_content = self.log_file.read_text(errors='ignore')

            # Buscar indicadores de conexión exitosa
            success_indicators = [
                "agent connected",
                "tunnel established",
                "tcp://",
                "connected to playit",
            ]

            for indicator in success_indicators:
                if indicator in log_content.lower():
                    # Intentar extraer dirección del túnel
                    tunnel_pattern = r'tcp://[^\s]+'
                    matches = re.findall(tunnel_pattern, log_content)
                    if matches:
                        self.tunnel_address = matches[0]
                    return True

            return False

        except Exception as e:
            self._log(f"Error detectando túnel: {e}")
            return False

    def _start_health_monitor(self):
        """Inicia el monitor de salud del túnel."""
        if self.health_running:
            return

        self.health_running = True
        self.health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_thread.start()
        self._log("Health monitor iniciado")

    def _health_check_loop(self):
        """Loop de verificación de salud del túnel."""
        interval = self.settings.playit_health_check_interval
        consecutive_failures = 0
        max_failures = 3

        while self.health_running:
            time.sleep(interval)

            if not self.is_running():
                self._log("Health check: proceso no está corriendo")
                consecutive_failures += 1
            elif not self._verify_tunnel_health():
                self._log("Health check: túnel no responde")
                consecutive_failures += 1
            else:
                consecutive_failures = 0
                continue

            # Si hay muchas fallas consecutivas, intentar reconectar
            if consecutive_failures >= max_failures:
                self._log(f"Health check falló {consecutive_failures} veces, intentando reconectar...")

                if self.settings.playit_auto_reconnect:
                    self.reconnect()
                else:
                    self.state = PlayitState.ERROR
                    self.health_running = False
                    break

                consecutive_failures = 0

    def _verify_tunnel_health(self) -> bool:
        """
        Verifica que el túnel esté funcionando correctamente.

        Returns:
            True si el túnel está saludable
        """
        # Verificar que el proceso esté vivo
        if not self.process or self.process.poll() is not None:
            return False

        # Verificar log reciente
        try:
            if self.log_file.exists():
                # Verificar que el log se haya modificado recientemente
                mtime = datetime.fromtimestamp(self.log_file.stat().st_mtime)
                if datetime.now() - mtime > timedelta(minutes=5):
                    return False

            return True

        except Exception:
            return False

    def reconnect(self) -> bool:
        """
        Reconecta el túnel con exponential backoff.

        Returns:
            True si la reconexión fue exitosa
        """
        self.reconnect_attempts += 1

        if self.reconnect_attempts > self.max_reconnect_attempts:
            self._log(f"Máximo de intentos de reconexión alcanzado ({self.max_reconnect_attempts})")
            self.state = PlayitState.ERROR
            return False

        # Exponential backoff
        wait_time = min(2 ** self.reconnect_attempts, 60)

        # Evitar reconexión muy frecuente
        if self.last_reconnect_time:
            elapsed = (datetime.now() - self.last_reconnect_time).total_seconds()
            if elapsed < wait_time:
                time.sleep(wait_time - elapsed)

        self._log(f"Intento de reconexión #{self.reconnect_attempts} (esperando {wait_time}s)")
        self.state = PlayitState.RECONNECTING
        self.last_reconnect_time = datetime.now()

        # Detener proceso actual
        self.stop()
        time.sleep(2)

        # Reintentar
        if self.start():
            self._log("Reconexión exitosa")
            self.reconnect_attempts = 0
            return True
        else:
            self._log("Reconexión falló")
            return False

    def stop(self):
        """Detiene el túnel de forma limpia."""
        self._log("Deteniendo Playit.gg...")

        # Detener health monitor
        self.health_running = False
        if self.health_thread:
            self.health_thread.join(timeout=5)

        # Terminar proceso
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception as e:
                self._log(f"Error deteniendo proceso: {e}")
            finally:
                self.process = None

        # Limpiar PID
        if self.pid_file.exists():
            self.pid_file.unlink()

        self.state = PlayitState.STOPPED
        self._save_state()
        self._log("Playit.gg detenido")

    def is_running(self) -> bool:
        """
        Verifica si el proceso está corriendo.

        Returns:
            True si está corriendo
        """
        if self.process and self.process.poll() is None:
            return True

        # Verificar PID file
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text())
                # Verificar si el proceso existe
                import os
                import signal
                os.kill(pid, 0)
                return True
            except (ValueError, ProcessLookupError, OSError):
                self.pid_file.unlink()
                return False

        return False

    def get_status(self) -> dict:
        """
        Obtiene el estado completo del túnel.

        Returns:
            Diccionario con información del estado
        """
        return {
            'state': self.state.value,
            'running': self.is_running(),
            'claim_url': self.claim_url,
            'tunnel_address': self.tunnel_address,
            'reconnect_attempts': self.reconnect_attempts,
            'health_monitor_active': self.health_running,
            'pid': self.process.pid if self.process else None
        }

    def _save_state(self):
        """Guarda el estado actual a disco."""
        import json

        state_data = {
            'claim_url': self.claim_url,
            'tunnel_address': self.tunnel_address,
            'state': self.state.value,
            'last_update': datetime.now().isoformat()
        }

        self.state_file.write_text(json.dumps(state_data, indent=2))

    def _load_state(self):
        """Carga el estado previo desde disco."""
        if not self.state_file.exists():
            return

        try:
            import json
            state_data = json.loads(self.state_file.read_text())

            self.claim_url = state_data.get('claim_url')
            self.tunnel_address = state_data.get('tunnel_address')

            # Actualizar .env si hay datos nuevos
            if self.claim_url or self.tunnel_address:
                updates = {}
                if self.claim_url:
                    updates['PLAYIT_CLAIM_URL'] = self.claim_url
                if self.tunnel_address:
                    updates['PLAYIT_TUNNEL_ADDRESS'] = self.tunnel_address

                if updates:
                    self.settings.save(updates)

        except Exception as e:
            self._log(f"Error cargando estado: {e}")

    def _log(self, message: str):
        """
        Escribe mensaje al log con timestamp.

        Args:
            message: Mensaje a escribir
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)

    def __del__(self):
        """Cleanup al destruir el objeto."""
        try:
            self.stop()
        except:
            pass
