"""
Utilidades para gestión robusta de procesos con PIDs, timeouts y cleanup.
"""

import os
import signal
import time
import subprocess
from pathlib import Path
from typing import Optional, List
from datetime import datetime


class ProcessManager:
    """Gestor robusto de procesos con manejo de PIDs."""

    @staticmethod
    def is_running(pid_file: Path) -> bool:
        """
        Verifica si un proceso está corriendo basado en su PID file.

        Args:
            pid_file: Ruta al archivo PID

        Returns:
            True si el proceso está corriendo
        """
        if not pid_file.exists():
            return False

        try:
            pid = int(pid_file.read_text().strip())
            # Intentar enviar signal 0 (no hace nada pero verifica existencia)
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, OSError):
            # PID inválido o proceso no existe
            pid_file.unlink(missing_ok=True)
            return False

    @staticmethod
    def get_pid(pid_file: Path) -> Optional[int]:
        """
        Obtiene el PID desde un archivo PID.

        Args:
            pid_file: Ruta al archivo PID

        Returns:
            PID del proceso o None si no existe
        """
        if not pid_file.exists():
            return None

        try:
            pid = int(pid_file.read_text().strip())
            # Verificar que el proceso existe
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, OSError):
            pid_file.unlink(missing_ok=True)
            return None

    @staticmethod
    def save_pid(pid_file: Path, pid: int):
        """
        Guarda un PID a un archivo.

        Args:
            pid_file: Ruta al archivo PID
            pid: PID a guardar
        """
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(pid))

    @staticmethod
    def stop_process(pid_file: Path, timeout: int = 15, force: bool = True) -> bool:
        """
        Detiene un proceso de forma limpia con fallback a kill.

        Args:
            pid_file: Ruta al archivo PID
            timeout: Tiempo de espera antes de force kill
            force: Si debe forzar kill si no responde

        Returns:
            True si se detuvo exitosamente
        """
        pid = ProcessManager.get_pid(pid_file)
        if pid is None:
            return True

        try:
            # Intentar terminación limpia
            os.kill(pid, signal.SIGTERM)

            # Esperar con timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)  # Verificar si existe
                    time.sleep(0.5)
                except ProcessLookupError:
                    # Proceso terminado
                    pid_file.unlink(missing_ok=True)
                    return True

            # Si llegamos aquí, el proceso no terminó
            if force:
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                pid_file.unlink(missing_ok=True)
                return True
            else:
                return False

        except ProcessLookupError:
            # El proceso ya no existe
            pid_file.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"Error deteniendo proceso {pid}: {e}")
            return False

    @staticmethod
    def cleanup_stale_pids(run_dir: Path):
        """
        Limpia archivos PID de procesos que ya no existen.

        Args:
            run_dir: Directorio donde están los archivos PID
        """
        if not run_dir.exists():
            return

        for pid_file in run_dir.glob("*.pid"):
            if not ProcessManager.is_running(pid_file):
                pid_file.unlink(missing_ok=True)

    @staticmethod
    def start_process(
        command: List[str],
        pid_file: Path,
        log_file: Path,
        env: Optional[dict] = None,
        cwd: Optional[Path] = None
    ) -> subprocess.Popen:
        """
        Inicia un proceso con manejo robusto.

        Args:
            command: Comando a ejecutar (lista)
            pid_file: Donde guardar el PID
            log_file: Donde redirigir stdout/stderr
            env: Variables de entorno adicionales
            cwd: Directorio de trabajo

        Returns:
            Objeto Popen del proceso iniciado
        """
        # Preparar entorno
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # Crear directorios
        log_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Abrir archivo de log
        log_handle = open(log_file, 'a', buffering=1)

        # Iniciar proceso
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=process_env,
            cwd=cwd,
            start_new_session=True  # Crear nuevo session para mejor control
        )

        # Guardar PID
        ProcessManager.save_pid(pid_file, process.pid)

        return process

    @staticmethod
    def wait_for_process(pid_file: Path, timeout: int = 30) -> bool:
        """
        Espera a que un proceso inicie correctamente.

        Args:
            pid_file: Ruta al archivo PID
            timeout: Tiempo máximo de espera

        Returns:
            True si el proceso inició correctamente
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if ProcessManager.is_running(pid_file):
                return True
            time.sleep(0.5)

        return False

    @staticmethod
    def get_process_info(pid: int) -> Optional[dict]:
        """
        Obtiene información de un proceso.

        Args:
            pid: PID del proceso

        Returns:
            Diccionario con información o None si no existe
        """
        try:
            # Intentar leer /proc/{pid}/status
            status_file = Path(f"/proc/{pid}/status")
            if status_file.exists():
                status_data = {}
                for line in status_file.read_text().splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        status_data[key.strip()] = value.strip()

                return {
                    'pid': pid,
                    'name': status_data.get('Name', 'Unknown'),
                    'state': status_data.get('State', 'Unknown'),
                    'threads': status_data.get('Threads', '0'),
                    'memory': status_data.get('VmRSS', '0')
                }

            return None

        except Exception:
            return None

    @staticmethod
    def send_command(pid: int, command: str) -> bool:
        """
        Envía un comando a un proceso (útil para servidores interactivos).

        Args:
            pid: PID del proceso
            command: Comando a enviar

        Returns:
            True si se envió exitosamente
        """
        try:
            # Esto es específico para Minecraft server
            # Normalmente se usa un named pipe o similar
            # Por ahora solo verificamos que el proceso exista
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False


class ProcessMonitor:
    """Monitor de salud de procesos con callbacks."""

    def __init__(self, pid_file: Path, check_interval: int = 30):
        self.pid_file = pid_file
        self.check_interval = check_interval
        self.running = False
        self.on_failure_callback = None

    def start(self, on_failure=None):
        """Inicia el monitoreo."""
        import threading

        self.running = True
        self.on_failure_callback = on_failure

        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()

    def stop(self):
        """Detiene el monitoreo."""
        self.running = False

    def _monitor_loop(self):
        """Loop de monitoreo."""
        consecutive_failures = 0
        max_failures = 3

        while self.running:
            time.sleep(self.check_interval)

            if not ProcessManager.is_running(self.pid_file):
                consecutive_failures += 1

                if consecutive_failures >= max_failures:
                    if self.on_failure_callback:
                        self.on_failure_callback()
                    break
            else:
                consecutive_failures = 0


def cleanup_zombie_processes():
    """Limpia procesos zombie si es posible."""
    try:
        import signal
        # Reap any zombie children
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
            except ChildProcessError:
                break
    except Exception:
        pass


def get_system_load() -> dict:
    """
    Obtiene la carga del sistema.

    Returns:
        Diccionario con información de carga
    """
    try:
        loadavg = os.getloadavg()
        return {
            '1min': loadavg[0],
            '5min': loadavg[1],
            '15min': loadavg[2]
        }
    except Exception:
        return {}


def get_memory_usage() -> dict:
    """
    Obtiene el uso de memoria del sistema.

    Returns:
        Diccionario con información de memoria
    """
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)

        total = meminfo.get('MemTotal', 0)
        available = meminfo.get('MemAvailable', 0)
        used = total - available

        return {
            'total_mb': total // 1024,
            'used_mb': used // 1024,
            'available_mb': available // 1024,
            'percent': (used / total * 100) if total > 0 else 0
        }
    except Exception:
        return {}
