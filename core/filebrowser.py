# =============================================================================
# core/filebrowser.py
# =============================================================================

"""
Gestor de Filebrowser para gestión web de archivos del servidor.
"""

import random
import string
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


class FilebrowserManager:
    """Gestor del servidor de archivos Filebrowser."""

    def __init__(self, settings, process_manager):
        self.settings = settings
        self.pm = process_manager

        self.binary = settings.get_filebrowser_binary()
        self.db_file = settings.data_dir / "filebrowser.db"
        self.log_file = settings.log_dir / "filebrowser.log"
        self.pid_file = settings.run_dir / "filebrowser.pid"

        self.process: Optional[subprocess.Popen] = None

        # Generar contraseña si no existe
        if not self.settings.filebrowser_password:
            self._generate_credentials()

    def start(self) -> bool:
        """
        Inicia Filebrowser.

        Returns:
            True si inició correctamente
        """
        if self.is_running():
            self._log("Filebrowser ya está corriendo")
            return True

        if not self.binary.exists():
            self._log(f"ERROR: Filebrowser binary no encontrado: {self.binary}")
            return False

        # Configurar si es primera vez
        if not self.db_file.exists():
            if not self._setup_filebrowser():
                return False

        self._log("Iniciando Filebrowser...")

        try:
            command = [
                str(self.binary),
                "--port",
                str(self.settings.filebrowser_port),
                "--address",
                "0.0.0.0",
                "--root",
                str(self.settings.server_dir),
                "--database",
                str(self.db_file),
            ]

            self.process = self.pm.start_process(
                command=command, pid_file=self.pid_file, log_file=self.log_file
            )

            # Esperar inicio
            if self.pm.wait_for_process(self.pid_file, timeout=10):
                self._log("Filebrowser iniciado correctamente")
                return True
            else:
                self._log("Filebrowser no inició en el tiempo esperado")
                return False

        except Exception as e:
            self._log(f"ERROR iniciando Filebrowser: {e}")
            return False

    def stop(self) -> bool:
        """
        Detiene Filebrowser.

        Returns:
            True si se detuvo correctamente
        """
        if not self.is_running():
            self._log("Filebrowser no está corriendo")
            return True

        self._log("Deteniendo Filebrowser...")

        if self.pm.stop_process(self.pid_file):
            self._log("Filebrowser detenido")
            self.process = None
            return True
        else:
            self._log("Error deteniendo Filebrowser")
            return False

    def is_running(self) -> bool:
        """Verifica si está corriendo."""
        return self.pm.is_running(self.pid_file)

    def reset_credentials(self) -> bool:
        """
        Regenera las credenciales de acceso.

        Returns:
            True si se regeneraron correctamente
        """
        if self.is_running():
            self.stop()

        self._log("Regenerando credenciales...")

        # Eliminar DB anterior
        if self.db_file.exists():
            self.db_file.unlink()

        # Generar nuevas credenciales
        self._generate_credentials()

        # Reconfigurar
        return self._setup_filebrowser()

    def _setup_filebrowser(self) -> bool:
        """
        Configura Filebrowser inicialmente.

        Returns:
            True si se configuró correctamente
        """
        try:
            self._log("Configurando Filebrowser...")

            # Inicializar base de datos
            subprocess.run(
                [str(self.binary), "config", "init", "--database", str(self.db_file)],
                check=True,
                capture_output=True,
            )

            # Configurar puerto y root
            subprocess.run(
                [
                    str(self.binary),
                    "config",
                    "set",
                    "--port",
                    str(self.settings.filebrowser_port),
                    "--address",
                    "0.0.0.0",
                    "--root",
                    str(self.settings.server_dir),
                    "--database",
                    str(self.db_file),
                ],
                check=True,
                capture_output=True,
            )

            # Agregar usuario
            subprocess.run(
                [
                    str(self.binary),
                    "users",
                    "add",
                    self.settings.filebrowser_user,
                    self.settings.filebrowser_password,
                    "--perm.admin",
                    "--perm.execute",
                    "--perm.create",
                    "--perm.rename",
                    "--perm.modify",
                    "--perm.delete",
                    "--perm.share",
                    "--perm.download",
                    "--database",
                    str(self.db_file),
                ],
                check=True,
                capture_output=True,
            )

            self._log("Filebrowser configurado correctamente")
            return True

        except Exception as e:
            self._log(f"ERROR configurando Filebrowser: {e}")
            return False

    def _generate_credentials(self):
        """Genera credenciales aleatorias pero legibles."""
        adjectives = [
            "Super",
            "Mega",
            "Epic",
            "Fast",
            "Cool",
            "Iron",
            "Gold",
            "Blue",
            "Dark",
            "Neon",
        ]
        nouns = [
            "Creeper",
            "Dragon",
            "Steve",
            "Sword",
            "Block",
            "Mine",
            "Craft",
            "Server",
            "Player",
            "World",
        ]

        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        num = random.randint(100, 999)

        password = f"{adj}{noun}{num}!MC"

        # Guardar en settings
        self.settings.save({"FILEBROWSER_PASSWORD": password})

        # Actualizar instancia local
        self.settings.filebrowser_password = password

        self._log(
            f"Credenciales generadas: {self.settings.filebrowser_user} / {password}"
        )

    def get_credentials(self) -> dict:
        """
        Obtiene las credenciales actuales.

        Returns:
            Diccionario con usuario y contraseña
        """
        return {
            "user": self.settings.filebrowser_user,
            "password": self.settings.filebrowser_password,
            "port": self.settings.filebrowser_port,
            "url": f"http://{{ip}}:{self.settings.filebrowser_port}",
        }

    def get_status(self) -> dict:
        """Obtiene el estado."""
        return {
            "running": self.is_running(),
            "port": self.settings.filebrowser_port,
            "user": self.settings.filebrowser_user,
            "pid": self.pm.get_pid(self.pid_file),
        }

    def _log(self, message: str):
        """Escribe al log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message)
