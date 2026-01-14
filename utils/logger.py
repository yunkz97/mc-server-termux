"""
Sistema de logging con rotación automática y niveles configurables.
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para terminal."""

    COLORS = {
        "DEBUG": "\033[0;36m",  # Cyan
        "INFO": "\033[0;32m",  # Green
        "WARNING": "\033[1;33m",  # Yellow
        "ERROR": "\033[0;31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record):
        # Aplicar color solo si es para terminal
        if hasattr(record, "use_color") and record.use_color:
            color = self.COLORS.get(record.levelname, self.RESET)
            record.levelname = f"{color}{record.levelname}{self.RESET}"

        return super().format(record)


class AppLogger:
    """Sistema de logging centralizado con rotación."""

    def __init__(
        self,
        name: str,
        log_file: Path,
        level: str = "INFO",
        max_size_mb: int = 10,
        backup_count: int = 5,
        console_output: bool = True,
    ):
        """
        Inicializa el logger.

        Args:
            name: Nombre del logger
            log_file: Ruta al archivo de log
            level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_size_mb: Tamaño máximo del log en MB antes de rotar
            backup_count: Número de archivos de backup a mantener
            console_output: Si debe imprimir también en consola
        """
        self.name = name
        self.log_file = log_file
        self.logger = logging.getLogger(name)

        # Configurar nivel
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(numeric_level)

        # Evitar duplicación de handlers
        if self.logger.handlers:
            return

        # Crear directorio de logs
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Handler de archivo con rotación
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)

        # Formato para archivo (sin colores)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Handler de consola (con colores)
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(numeric_level)

            console_formatter = ColoredFormatter("%(levelname)s: %(message)s")
            console_handler.setFormatter(console_formatter)

            # Marcar records para console con flag de color
            class ColoredFilter(logging.Filter):
                def filter(self, record):
                    record.use_color = True
                    return True

            console_handler.addFilter(ColoredFilter())
            self.logger.addHandler(console_handler)

    def debug(self, message: str):
        """Log nivel DEBUG."""
        self.logger.debug(message)

    def info(self, message: str):
        """Log nivel INFO."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log nivel WARNING."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log nivel ERROR."""
        self.logger.error(message)

    def critical(self, message: str):
        """Log nivel CRITICAL."""
        self.logger.critical(message)

    def exception(self, message: str):
        """Log de excepción con traceback."""
        self.logger.exception(message)

    def get_recent_logs(self, lines: int = 50) -> str:
        """
        Obtiene las últimas líneas del log.

        Args:
            lines: Número de líneas a obtener

        Returns:
            Últimas líneas del log
        """
        if not self.log_file.exists():
            return "No hay logs disponibles"

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent)
        except Exception as e:
            return f"Error leyendo logs: {e}"

    def clear_logs(self):
        """Limpia el archivo de log actual."""
        try:
            if self.log_file.exists():
                self.log_file.write_text("")
                self.info("Logs limpiados")
        except Exception as e:
            self.error(f"Error limpiando logs: {e}")

    def rotate_now(self):
        """Fuerza una rotación de logs."""
        for handler in self.logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.doRollover()
                self.info("Logs rotados manualmente")

    def get_log_size(self) -> int:
        """
        Obtiene el tamaño del log actual en bytes.

        Returns:
            Tamaño en bytes
        """
        if self.log_file.exists():
            return self.log_file.stat().st_size
        return 0

    def get_all_log_files(self) -> list[Path]:
        """
        Obtiene lista de todos los archivos de log (incluyendo rotados).

        Returns:
            Lista de rutas de logs
        """
        log_files = [self.log_file]

        # Buscar logs rotados
        pattern = f"{self.log_file.name}.*"
        for file in self.log_file.parent.glob(pattern):
            if file != self.log_file:
                log_files.append(file)

        return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)


class LogManager:
    """Gestor centralizado de todos los logs de la aplicación."""

    def __init__(self, settings):
        self.settings = settings
        self.loggers = {}

        # Crear loggers para cada componente
        self._create_loggers()

    def _create_loggers(self):
        """Crea loggers para cada componente."""
        # Parsear tamaño de rotación
        size_str = self.settings.log_rotation_size
        if size_str.endswith("M"):
            max_size = int(size_str[:-1])
        elif size_str.endswith("G"):
            max_size = int(size_str[:-1]) * 1024
        else:
            max_size = 10

        components = ["main", "minecraft", "playit", "filebrowser", "battery"]

        for component in components:
            log_file = self.settings.log_dir / f"{component}.log"
            self.loggers[component] = AppLogger(
                name=component,
                log_file=log_file,
                level=self.settings.log_level,
                max_size_mb=max_size,
                backup_count=self.settings.log_rotation_count,
                console_output=False,  # Solo el main logger imprime a consola
            )

        # Logger principal con salida a consola
        self.loggers["main"].logger.handlers[0]  # Ya tiene console output

    def get(self, component: str) -> AppLogger:
        """
        Obtiene el logger de un componente.

        Args:
            component: Nombre del componente

        Returns:
            Logger del componente
        """
        return self.loggers.get(component, self.loggers["main"])

    def get_all_recent_logs(self, lines: int = 20) -> dict[str, str]:
        """
        Obtiene logs recientes de todos los componentes.

        Args:
            lines: Número de líneas por componente

        Returns:
            Diccionario {componente: logs}
        """
        return {
            name: logger.get_recent_logs(lines) for name, logger in self.loggers.items()
        }

    def clear_all_logs(self):
        """Limpia todos los logs."""
        for logger in self.loggers.values():
            logger.clear_logs()

    def rotate_all_logs(self):
        """Rota todos los logs."""
        for logger in self.loggers.values():
            logger.rotate_now()

    def get_total_log_size(self) -> int:
        """
        Obtiene el tamaño total de todos los logs.

        Returns:
            Tamaño total en bytes
        """
        total = 0
        for logger in self.loggers.values():
            for log_file in logger.get_all_log_files():
                if log_file.exists():
                    total += log_file.stat().st_size
        return total

    def cleanup_old_logs(self, days: int = 7):
        """
        Limpia logs más viejos que X días.

        Args:
            days: Días de antigüedad
        """
        import time

        cutoff = time.time() - (days * 86400)

        cleaned = 0
        for logger in self.loggers.values():
            for log_file in logger.get_all_log_files():
                if log_file.stat().st_mtime < cutoff:
                    try:
                        log_file.unlink()
                        cleaned += 1
                    except Exception:
                        pass

        return cleaned
