"""
Sistema de actualización automática desde GitHub.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


class Updater:
    """Gestor de actualizaciones del sistema."""

    def __init__(self, settings):
        self.settings = settings
        self.base_dir = settings.base_dir
        self.repo_user = "yunkz97"
        self.repo_name = "mc-server-termux"
        self.current_version = settings.version

        self.github_api = (
            f"https://api.github.com/repos/{self.repo_user}/{self.repo_name}"
        )
        self.github_raw = (
            f"https://raw.githubusercontent.com/{self.repo_user}/{self.repo_name}/main"
        )

    def check_for_updates(self) -> Tuple[bool, Optional[str]]:
        """
        Verifica si hay actualizaciones disponibles.

        Returns:
            Tupla (hay_actualización, versión_nueva)
        """
        try:
            import requests

            # Obtener última release desde GitHub API
            response = requests.get(f"{self.github_api}/releases/latest", timeout=10)

            if response.status_code == 200:
                data = response.json()
                latest_version = data["tag_name"].lstrip("v")

                if self._compare_versions(latest_version, self.current_version) > 0:
                    return True, latest_version
                else:
                    return False, self.current_version
            else:
                # Fallback: verificar VERSION en el repo
                response = requests.get(f"{self.github_raw}/.env.example", timeout=10)

                if response.status_code == 200:
                    for line in response.text.split("\n"):
                        if line.startswith("VERSION="):
                            latest_version = line.split("=")[1].strip()

                            if (
                                self._compare_versions(
                                    latest_version, self.current_version
                                )
                                > 0
                            ):
                                return True, latest_version

                return False, self.current_version

        except Exception as e:
            print(f"Error verificando actualizaciones: {e}")
            return False, None

    def update(self, backup: bool = True) -> bool:
        """
        Actualiza el sistema completo.

        Args:
            backup: Si debe hacer backup antes de actualizar

        Returns:
            True si se actualizó correctamente
        """
        try:
            # Verificar que estemos en un repo git
            if not (self.base_dir / ".git").exists():
                print("Error: No es un repositorio Git")
                print(
                    "Instala desde el instalador oficial para habilitar actualizaciones"
                )
                return False

            # Hacer backup si se solicita
            if backup:
                if not self._backup_config():
                    print("Advertencia: No se pudo hacer backup")

            # Actualizar usando git
            print("Descargando actualizaciones...")
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"Error al actualizar: {result.stderr}")
                return False

            # Actualizar dependencias Python
            print("Actualizando dependencias Python...")
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                    "--upgrade",
                ],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"Advertencia: Error actualizando dependencias: {result.stderr}")

            # Restaurar backup si existe
            if backup:
                self._restore_config_backup()

            print("¡Actualización completada!")
            print("Reinicia el programa para aplicar los cambios")
            return True

        except Exception as e:
            print(f"Error durante la actualización: {e}")
            return False

    def quick_update(self) -> bool:
        """
        Actualización rápida solo del script principal.

        Returns:
            True si se actualizó correctamente
        """
        try:
            import requests

            # Descargar main.py actualizado
            print("Descargando main.py actualizado...")
            response = requests.get(f"{self.github_raw}/main.py", timeout=30)

            if response.status_code != 200:
                print("Error descargando archivo")
                return False

            # Hacer backup
            main_file = self.base_dir / "main.py"
            backup_file = (
                self.base_dir
                / f"main.py.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )

            if main_file.exists():
                main_file.rename(backup_file)
                print(f"Backup creado: {backup_file.name}")

            # Guardar nuevo archivo
            main_file.write_text(response.content.decode("utf-8"))

            # Hacer ejecutable
            import os

            os.chmod(main_file, 0o755)

            print("¡Actualización completada!")
            print("Reinicia el programa para aplicar los cambios")
            return True

        except Exception as e:
            print(f"Error durante la actualización: {e}")
            return False

    def _backup_config(self) -> bool:
        """Hace backup de la configuración."""
        try:
            env_file = self.settings.env_file
            if env_file.exists():
                backup_file = (
                    self.base_dir
                    / f".env.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                )
                env_file.copy(backup_file)
                return True
            return False
        except Exception:
            return False

    def _restore_config_backup(self):
        """Restaura el backup de configuración si existe."""
        try:
            # Buscar backups
            backups = sorted(
                self.base_dir.glob(".env.backup-*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )

            if backups:
                latest_backup = backups[0]
                # No sobrescribir, solo informar
                print(f"Backup disponible en: {latest_backup.name}")
        except Exception:
            pass

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compara dos versiones.

        Args:
            v1: Primera versión
            v2: Segunda versión

        Returns:
            1 si v1 > v2, -1 si v1 < v2, 0 si son iguales
        """
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            # Igualar longitudes
            while len(parts1) < len(parts2):
                parts1.append(0)
            while len(parts2) < len(parts1):
                parts2.append(0)

            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1

            return 0

        except Exception:
            return 0

    def get_changelog(self) -> Optional[str]:
        """
        Obtiene el changelog de la última versión.

        Returns:
            Texto del changelog o None
        """
        try:
            import requests

            response = requests.get(f"{self.github_api}/releases/latest", timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("body", "Sin información de cambios")

            return None

        except Exception:
            return None
