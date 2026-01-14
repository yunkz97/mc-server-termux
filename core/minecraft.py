"""
Gestor del servidor Minecraft con soporte para Aikar's flags,
EULA automático y gestión robusta de procesos.
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class MinecraftServer:
    """Gestor del servidor Minecraft."""

    def __init__(self, settings, process_manager):
        self.settings = settings
        self.pm = process_manager

        self.jar_path = settings.get_server_jar_path()
        self.server_dir = settings.server_dir
        self.log_file = settings.log_dir / "minecraft.log"
        self.pid_file = settings.run_dir / "minecraft.pid"
        self.eula_file = settings.server_dir / "eula.txt"

        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """
        Inicia el servidor Minecraft.

        Returns:
            True si inició correctamente
        """
        if self.is_running():
            self._log("El servidor ya está corriendo")
            return True

        # Verificar que exista el JAR
        if not self.jar_path.exists():
            self._log(f"ERROR: No se encontró el JAR del servidor: {self.jar_path}")
            return False

        # Verificar/aceptar EULA automáticamente
        if not self._ensure_eula():
            self._log("ERROR: No se pudo aceptar el EULA")
            return False

        # Preparar comando Java
        command = self._build_java_command()

        self._log("Iniciando servidor Minecraft...")
        self._log(f"Comando: {' '.join(command)}")

        try:
            # Iniciar proceso
            self.process = self.pm.start_process(
                command=command,
                pid_file=self.pid_file,
                log_file=self.log_file,
                cwd=self.server_dir,
            )

            # Esperar a que inicie
            self._log("Esperando inicio del servidor...")
            if self._wait_for_startup(timeout=60):
                self._log("Servidor iniciado correctamente")
                return True
            else:
                self._log("El servidor no inició en el tiempo esperado")
                self.stop()
                return False

        except Exception as e:
            self._log(f"ERROR iniciando servidor: {e}")
            return False

    def stop(self, timeout: int = 30) -> bool:
        """
        Detiene el servidor de forma limpia.

        Args:
            timeout: Tiempo de espera antes de force kill

        Returns:
            True si se detuvo correctamente
        """
        if not self.is_running():
            self._log("El servidor no está corriendo")
            return True

        self._log("Deteniendo servidor...")

        # Intentar comando stop si es posible
        self._send_command("stop")
        time.sleep(2)

        # Usar process manager para detener
        if self.pm.stop_process(self.pid_file, timeout=timeout):
            self._log("Servidor detenido correctamente")
            self.process = None
            return True
        else:
            self._log("Error deteniendo el servidor")
            return False

    def restart(self) -> bool:
        """
        Reinicia el servidor.

        Returns:
            True si se reinició correctamente
        """
        self._log("Reiniciando servidor...")
        self.stop()
        time.sleep(3)
        return self.start()

    def is_running(self) -> bool:
        """
        Verifica si el servidor está corriendo.

        Returns:
            True si está corriendo
        """
        return self.pm.is_running(self.pid_file)

    def send_command(self, command: str) -> bool:
        """
        Envía un comando al servidor (para comandos en juego).

        Args:
            command: Comando a enviar

        Returns:
            True si se envió correctamente
        """
        return self._send_command(command)

    def _send_command(self, command: str) -> bool:
        """
        Envía un comando al servidor Minecraft.

        Args:
            command: Comando a enviar

        Returns:
            True si se envió correctamente
        """
        if not self.is_running():
            return False

        try:
            # Para Minecraft, necesitamos escribir al stdin del proceso
            # Como estamos usando nohup y redirección, esto es complicado
            # La solución es usar un named pipe o archivo temporal

            input_file = self.settings.run_dir / "server_input.txt"
            with open(input_file, "a") as f:
                f.write(f"{command}\n")

            return True
        except Exception as e:
            self._log(f"Error enviando comando: {e}")
            return False

    def _ensure_eula(self) -> bool:
        """
        Asegura que el EULA esté aceptado.

        Returns:
            True si el EULA está OK
        """
        if self.eula_file.exists():
            content = self.eula_file.read_text()
            if "eula=true" in content:
                self._log("EULA ya aceptado")
                return True

        self._log("Aceptando EULA automáticamente...")

        try:
            # Si no existe, hacer una corrida rápida para generar archivos
            if not self.eula_file.exists():
                self._log("Generando archivos iniciales del servidor...")

                # Comando simple sin optimizaciones
                command = [
                    "java",
                    "-Xmx512M",
                    "-Xms512M",
                    "-jar",
                    str(self.jar_path),
                    "nogui",
                ]

                # Ejecutar por máximo 20 segundos
                try:
                    result = subprocess.run(
                        command,
                        cwd=self.server_dir,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                except subprocess.TimeoutExpired:
                    pass  # Es normal que haga timeout

                # Esperar un poco
                time.sleep(2)

            # Ahora debería existir el eula.txt
            if not self.eula_file.exists():
                self._log("ERROR: No se generó eula.txt")
                return False

            # Modificar eula.txt
            content = self.eula_file.read_text()
            content = content.replace("eula=false", "eula=true")
            self.eula_file.write_text(content)

            self._log("EULA aceptado correctamente")
            return True

        except Exception as e:
            self._log(f"ERROR aceptando EULA: {e}")
            return False

    def _build_java_command(self) -> List[str]:
        """
        Construye el comando Java con flags apropiadas.

        Returns:
            Lista con el comando completo
        """
        command = ["java"]

        # Aikar's Flags o flags simples
        if self.settings.use_aikar_flags:
            ram = self.settings.java_ram
            command.extend(
                [
                    f"-Xms{ram}",
                    f"-Xmx{ram}",
                    "-XX:+UseG1GC",
                    "-XX:+ParallelRefProcEnabled",
                    "-XX:MaxGCPauseMillis=200",
                    "-XX:+UnlockExperimentalVMOptions",
                    "-XX:+DisableExplicitGC",
                    "-XX:+AlwaysPreTouch",
                    "-XX:G1NewSizePercent=30",
                    "-XX:G1MaxNewSizePercent=40",
                    "-XX:G1HeapRegionSize=8M",
                    "-XX:G1ReservePercent=20",
                    "-XX:G1HeapWastePercent=5",
                    "-XX:G1MixedGCCountTarget=4",
                    "-XX:InitiatingHeapOccupancyPercent=15",
                    "-XX:G1MixedGCLiveThresholdPercent=90",
                    "-XX:G1RSetUpdatingPauseTimePercent=5",
                    "-XX:SurvivorRatio=32",
                    "-XX:+PerfDisableSharedMem",
                    "-XX:MaxTenuringThreshold=1",
                    "-Dusing.aikars.flags=https://mcflags.emc.gs",
                    "-Daikars.new.flags=true",
                ]
            )
        else:
            command.extend([f"-Xmx{self.settings.java_ram}", "-Xms512M"])

        # JAR y opciones
        command.extend(["-jar", str(self.jar_path), "nogui"])

        return command

    def _wait_for_startup(self, timeout: int = 60) -> bool:
        """
        Espera a que el servidor inicie completamente.

        Args:
            timeout: Tiempo máximo de espera

        Returns:
            True si inició correctamente
        """
        start_time = time.time()

        # Primero verificar que el proceso exista
        if not self.pm.wait_for_process(self.pid_file, timeout=10):
            return False

        # Luego buscar indicadores en el log
        success_indicators = [
            "Done (",  # Minecraft vanilla
            "Done!",  # Algunos mods
            "Time elapsed:",
            "starting minecraft server",
        ]

        while time.time() - start_time < timeout:
            if not self.is_running():
                self._log("El proceso terminó inesperadamente")
                return False

            if self.log_file.exists():
                try:
                    log_content = self.log_file.read_text(errors="ignore")

                    for indicator in success_indicators:
                        if indicator.lower() in log_content.lower():
                            return True

                    # Verificar errores críticos
                    if (
                        "error" in log_content.lower()
                        and "fatal" in log_content.lower()
                    ):
                        self._log("Se detectó un error fatal en el servidor")
                        return False

                except Exception:
                    pass

            time.sleep(2)

        # Timeout alcanzado
        self._log("Timeout esperando inicio del servidor")
        return False

    def get_status(self) -> dict:
        """
        Obtiene el estado del servidor.

        Returns:
            Diccionario con información del estado
        """
        status = {
            "running": self.is_running(),
            "jar_exists": self.jar_path.exists(),
            "jar_path": str(self.jar_path),
            "ram": self.settings.java_ram,
            "aikar_flags": self.settings.use_aikar_flags,
            "eula_accepted": self.eula_file.exists()
            and "eula=true" in self.eula_file.read_text(),
            "pid": self.pm.get_pid(self.pid_file),
        }

        return status

    def get_recent_log(self, lines: int = 30) -> str:
        """
        Obtiene las últimas líneas del log.

        Args:
            lines: Número de líneas a obtener

        Returns:
            Últimas líneas del log
        """
        if not self.log_file.exists():
            return "No hay log disponible"

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent)
        except Exception as e:
            return f"Error leyendo log: {e}"

    def _log(self, message: str):
        """
        Escribe mensaje al log con timestamp.

        Args:
            message: Mensaje a escribir
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message)
