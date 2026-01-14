"""
Sistema de configuración centralizado con validación y valores por defecto.
Maneja variables de entorno desde .env de forma segura.
"""

import os
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv


class Settings:
    """Gestor de configuración del sistema."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.home() / "mc-server-termux"
        self.env_file = self.base_dir / ".env"

        # Cargar variables de entorno
        load_dotenv(self.env_file)

        # General
        self.version = self._get_env("VERSION", "1.0.0")
        self.first_run = self._get_bool("FIRST_RUN", True)

        # Minecraft
        self.server_jar = self._get_env("SERVER_JAR", "server.jar")
        self.java_ram = self._get_env("JAVA_RAM", "1G")
        self.use_aikar_flags = self._get_bool("USE_AIKAR_FLAGS", True)
        self.server_port = self._get_int("SERVER_PORT", 25565)

        # Playit.gg
        self.playit_enabled = self._get_bool("PLAYIT_ENABLED", True)
        self.playit_auto_reconnect = self._get_bool("PLAYIT_AUTO_RECONNECT", True)
        self.playit_health_check_interval = self._get_int("PLAYIT_HEALTH_CHECK_INTERVAL", 30)
        self.playit_claim_url = self._get_env("PLAYIT_CLAIM_URL", "")
        self.playit_tunnel_address = self._get_env("PLAYIT_TUNNEL_ADDRESS", "")

        # Filebrowser
        self.filebrowser_enabled = self._get_bool("FILEBROWSER_ENABLED", True)
        self.filebrowser_port = self._get_int("FILEBROWSER_PORT", 8080)
        self.filebrowser_user = self._get_env("FILEBROWSER_USER", "admin")
        self.filebrowser_password = self._get_env("FILEBROWSER_PASSWORD", "")

        # Batería
        self.battery_monitor_enabled = self._get_bool("BATTERY_MONITOR_ENABLED", True)
        self.battery_check_interval = self._get_int("BATTERY_CHECK_INTERVAL", 60)
        self.battery_alert_20 = self._get_bool("BATTERY_ALERT_20", True)
        self.battery_alert_10 = self._get_bool("BATTERY_ALERT_10", True)
        self.battery_alert_5 = self._get_bool("BATTERY_ALERT_5", True)

        # Sistema
        self.log_level = self._get_env("LOG_LEVEL", "INFO")
        self.log_rotation_size = self._get_env("LOG_ROTATION_SIZE", "10M")
        self.log_rotation_count = self._get_int("LOG_ROTATION_COUNT", 5)
        self.auto_backup = self._get_bool("AUTO_BACKUP", False)
        self.backup_interval = self._get_env("BACKUP_INTERVAL", "24h")

        # Rutas
        self.server_dir = self._get_path("SERVER_DIR", self.base_dir / "server")
        self.data_dir = self._get_path("DATA_DIR", self.base_dir / "data")
        self.bin_dir = self._get_path("BIN_DIR", self.base_dir / "bin")
        self.log_dir = self._get_path("LOG_DIR", self.base_dir / "logs")
        self.run_dir = self._get_path("RUN_DIR", self.base_dir / "run")
        self.backup_dir = self._get_path("BACKUP_DIR", self.base_dir / "backups")

        # Crear directorios si no existen
        self._ensure_directories()

    def _get_env(self, key: str, default: str = "") -> str:
        """Obtiene variable de entorno de forma segura."""
        value = os.getenv(key, default).strip()
        # Expandir variables de entorno dentro del valor
        return os.path.expandvars(value) if value else default

    def _get_int(self, key: str, default: int) -> int:
        """Obtiene variable como entero con fallback."""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    def _get_bool(self, key: str, default: bool) -> bool:
        """Obtiene variable como booleano con fallback."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "si", "s")

    def _get_path(self, key: str, default: Path) -> Path:
        """Obtiene variable como Path con expansión."""
        value = self._get_env(key, str(default))
        return Path(os.path.expanduser(value))

    def _ensure_directories(self):
        """Crea todos los directorios necesarios."""
        for directory in [
            self.server_dir,
            self.data_dir,
            self.bin_dir,
            self.log_dir,
            self.run_dir,
            self.backup_dir
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def save(self, updates: dict[str, Any]):
        """
        Actualiza valores en el archivo .env de forma segura.

        Args:
            updates: Diccionario con las actualizaciones {KEY: value}
        """
        # Leer contenido actual
        lines = []
        if self.env_file.exists():
            with open(self.env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        # Actualizar valores existentes
        updated_keys = set()
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if '=' in line:
                key = line.split('=')[0].strip()
                if key in updates:
                    # Formatear valor apropiadamente
                    value = updates[key]
                    if isinstance(value, bool):
                        value = "true" if value else "false"
                    elif isinstance(value, str) and ' ' in value:
                        value = f'"{value}"'

                    lines[i] = f"{key}={value}\n"
                    updated_keys.add(key)

        # Agregar nuevos valores
        for key, value in updates.items():
            if key not in updated_keys:
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, str) and ' ' in value:
                    value = f'"{value}"'

                lines.append(f"{key}={value}\n")

        # Guardar
        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # Recargar configuración
        load_dotenv(self.env_file, override=True)

    def get_server_jar_path(self) -> Path:
        """Obtiene la ruta completa al JAR del servidor."""
        return self.server_dir / self.server_jar

    def get_playit_binary(self) -> Path:
        """Obtiene la ruta al binario de playit."""
        return self.bin_dir / "playit"

    def get_filebrowser_binary(self) -> Path:
        """Obtiene la ruta al binario de filebrowser."""
        return self.bin_dir / "filebrowser"

    def validate(self) -> list[str]:
        """
        Valida la configuración y retorna lista de errores.

        Returns:
            Lista de mensajes de error (vacía si todo está OK)
        """
        errors = []

        # Validar RAM
        if not self.java_ram.endswith(('M', 'G')):
            errors.append(f"JAVA_RAM inválida: {self.java_ram} (debe terminar en M o G)")

        # Validar puertos
        if not (1024 <= self.server_port <= 65535):
            errors.append(f"SERVER_PORT inválido: {self.server_port}")
        if not (1024 <= self.filebrowser_port <= 65535):
            errors.append(f"FILEBROWSER_PORT inválido: {self.filebrowser_port}")

        # Validar intervalos
        if self.battery_check_interval < 10:
            errors.append(f"BATTERY_CHECK_INTERVAL muy bajo: {self.battery_check_interval}s (mínimo 10s)")
        if self.playit_health_check_interval < 15:
            errors.append(f"PLAYIT_HEALTH_CHECK_INTERVAL muy bajo: {self.playit_health_check_interval}s (mínimo 15s)")

        # Validar log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            errors.append(f"LOG_LEVEL inválido: {self.log_level} (debe ser uno de {valid_levels})")

        return errors

    def __repr__(self) -> str:
        """Representación string de la configuración."""
        return (
            f"Settings(version={self.version}, "
            f"server_jar={self.server_jar}, "
            f"java_ram={self.java_ram})"
        )


# Instancia global de configuración
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Obtiene la instancia global de configuración (singleton).

    Returns:
        Instancia de Settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """Recarga la configuración desde el archivo .env."""
    global _settings
    _settings = Settings()
