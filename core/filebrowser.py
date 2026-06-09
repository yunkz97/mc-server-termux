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
        self.last_error: str = ""

    def start(self) -> bool:
        """
        Inicia Filebrowser.

        Returns:
            True si inició correctamente
        """
        self.last_error = ""

        if self.is_running():
            self._log("Filebrowser ya está corriendo")
            return True

        if not self.binary.exists():
            self.last_error = f"Binary not found: {self.binary}"
            self._log(f"ERROR: {self.last_error}")
            return False

        # Configurar si es primera vez
        if not self.db_file.exists():
            if not self._setup_filebrowser():
                # _setup_filebrowser already set self.last_error
                if not self.last_error:
                    self.last_error = "Setup failed (see log for details)"
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
                # Leer log para dar más información del error
                error_detail = ""
                if self.log_file.exists():
                    log_content = self.log_file.read_text()
                    if log_content.strip():
                        error_detail = log_content.strip()
                        self._log(f"Filebrowser log:\n{error_detail}")
                self.last_error = f"Filebrowser did not start within 10s. {error_detail}"
                return False

        except Exception as e:
            self.last_error = str(e)
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

        Si la DB ya existe, actualiza la contraseña del usuario
        en lugar de fallar.

        Returns:
            True si se configuró correctamente
        """
        try:
            self._log("Configurando Filebrowser...")

            # Inicializar base de datos con noauth desde el inicio
            result = subprocess.run(
                [str(self.binary), "config", "init", "--database", str(self.db_file), "--auth.method", "noauth"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "config init failed"
                self._log(f"ERROR config init: {self.last_error}")
                return False

            # Configurar puerto y root
            result = subprocess.run(
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
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "config set failed"
                self._log(f"ERROR config set: {self.last_error}")
                return False

            # Intentar agregar usuario (no crítico con noauth)
            result = subprocess.run(
                [
                    str(self.binary),
                    "users",
                    "add",
                    self.settings.filebrowser_user or "admin",
                    self.settings.filebrowser_password or "admin12345678",
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
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                add_out = result.stderr.strip() or result.stdout.strip() or "users add failed"
                self._log(f"users add (no crítico con noauth): {add_out}")

            self._log("Filebrowser configurado correctamente (auth: noauth)")
            return True

        except Exception as e:
            self._log(f"ERROR configurando Filebrowser: {e}")
            return False

    def _generate_credentials(self):
        """Genera credenciales aleatorias seguras (mínimo 12 caracteres)."""
        # Generar una contraseña segura: 16 chars alfanuméricos
        # Sin caracteres especiales para evitar problemas de parsing
        # en shell, .env, o validación de filebrowser
        alphabet = string.ascii_letters + string.digits
        password = "".join(random.choices(alphabet, k=16))

        # Guardar en settings
        self.settings.save({"FILEBROWSER_PASSWORD": password})

        # Actualizar instancia local
        self.settings.filebrowser_password = password

        self._log(
            f"Credenciales generadas para usuario: {self.settings.filebrowser_user}"
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

    def manual_setup(self, username: str, password: str) -> bool:
        """
        Configura Filebrowser manualmente con un usuario y contraseña específicos.
        Elimina la DB anterior para garantizar un estado limpio.
        """
        try:
            self._log(f"Iniciando configuración manual para usuario: {username}")

            # 0. Detener Filebrowser si está corriendo
            if self.is_running():
                self._log("Deteniendo Filebrowser antes de reconfigurar...")
                self.stop()
                import time
                time.sleep(1)

            # 1. Eliminar DB anterior (nuclear reset)
            if self.db_file.exists():
                self._log("Eliminando base de datos anterior...")
                self.db_file.unlink()

            # 2. Inicializar DB fresca con noauth desde el inicio
            result = subprocess.run(
                [str(self.binary), "config", "init", "--database", str(self.db_file), "--auth.method", "noauth"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "config init failed"
                self._log(f"ERROR config init: {self.last_error}")
                return False

            # 3. Configurar puerto y root
            result = subprocess.run(
                [
                    str(self.binary),
                    "config",
                    "set",
                    "--port", str(self.settings.filebrowser_port),
                    "--address", "0.0.0.0",
                    "--root", str(self.settings.server_dir),
                    "--database", str(self.db_file),
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "config set failed"
                self._log(f"ERROR config set: {self.last_error}")
                return False

            # 4. Agregar usuario (opcional con noauth, no falla si falla)
            result = subprocess.run(
                [
                    str(self.binary),
                    "users",
                    "add",
                    username,
                    password,
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
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                add_out = result.stderr.strip() or result.stdout.strip() or "users add failed"
                self._log(f"users add (no crítico con noauth): {add_out}")

            # 5. Guardar en settings
            self.settings.save({
                "FILEBROWSER_USER": username,
                "FILEBROWSER_PASSWORD": password
            })
            self.settings.filebrowser_user = username
            self.settings.filebrowser_password = password

            self._log(f"Configuración manual completada con éxito para {username}")
            return True

        except Exception as e:
            self.last_error = str(e)
            self._log(f"ERROR en manual_setup: {e}")
            return False

    def _log(self, message: str):
        """Escribe al log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message)
