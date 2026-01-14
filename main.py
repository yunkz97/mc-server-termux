#!/usr/bin/env python3
"""
MC Server Termux - Manager Principal v1.0.0
Sistema completo de gestión de servidores Minecraft en Termux.
"""

import sys
import time
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings, get_settings
from core.battery import BatteryMonitor
from core.filebrowser import FilebrowserManager
from core.minecraft import MinecraftServer
from core.playit import PlayitManager
from utils.logger import LogManager
from utils.process import ProcessManager
from utils.ui import *


class MCServerManager:
    """Gestor principal de MC Server Termux."""

    def __init__(self):
        """Inicializa el gestor."""
        # Cargar configuración
        self.settings = get_settings()

        # Validar configuración
        errors = self.settings.validate()
        if errors:
            log_error("Errores de configuración:")
            for error in errors:
                print(f"  • {error}")
            sys.exit(1)

        # Inicializar logger
        self.log_manager = LogManager(self.settings)
        self.logger = self.log_manager.get("main")

        # Inicializar process manager
        self.pm = ProcessManager()

        # Limpiar PIDs obsoletos
        self.pm.cleanup_stale_pids(self.settings.run_dir)

        # Inicializar componentes
        self.minecraft = MinecraftServer(self.settings, self.pm)
        self.playit = PlayitManager(self.settings)
        self.filebrowser = FilebrowserManager(self.settings, self.pm)
        self.battery = BatteryMonitor(self.settings, self.minecraft)

        self.logger.info("Manager inicializado")

    def run(self):
        """Ejecuta el loop principal."""
        # Verificar primera ejecución
        if self.settings.first_run:
            if not self.first_run_wizard():
                self.logger.error("Setup inicial cancelado")
                return

        # Loop principal del menú
        while True:
            try:
                choice = self.show_main_menu()

                if choice == "0":
                    self.exit_program()
                    break

                self.handle_menu_choice(choice)

                # No pausar si solo es refresh
                if choice != "18":
                    press_enter()

            except KeyboardInterrupt:
                print("\n")
                if prompt_yes_no("¿Salir del programa?", default=False):
                    self.exit_program()
                    break
            except Exception as e:
                log_error(f"Error inesperado: {e}")
                self.logger.exception("Error en loop principal")
                press_enter()

    def show_main_menu(self) -> str:
        """Muestra el menú principal."""
        print_header("MC SERVER TERMUX", self.settings.version)
        self.show_status()

        print(f"{Colors.CYAN}╔{'═' * 52}╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{' ' * 17}📋 MENÚ PRINCIPAL{' ' * 17}║{Colors.RESET}")
        print(f"{Colors.CYAN}╚{'═' * 52}╝{Colors.RESET}")
        print()

        # Control General
        print(f"{Colors.BOLD}CONTROL GENERAL{Colors.RESET}")
        print(f"  {Colors.GREEN}[1]{Colors.RESET}  🚀 Iniciar TODO")
        print(f"  {Colors.RED}[2]{Colors.RESET}  🛑 Detener TODO")
        print(f"  {Colors.YELLOW}[3]{Colors.RESET}  ↻  Reiniciar TODO")
        print()

        # Servidor Minecraft
        print(f"{Colors.BOLD}SERVIDOR MINECRAFT{Colors.RESET}")
        print(f"  {Colors.GREEN}[4]{Colors.RESET}  ▶  Iniciar servidor")
        print(f"  {Colors.RED}[5]{Colors.RESET}  ■  Detener servidor")
        print(f"  {Colors.YELLOW}[6]{Colors.RESET}  ↻  Reiniciar servidor")
        print()

        # Servicios
        print(f"{Colors.BOLD}SERVICIOS{Colors.RESET}")
        print(f"  {Colors.GREEN}[7]{Colors.RESET}  ▶  Iniciar Playit")
        print(f"  {Colors.RED}[8]{Colors.RESET}  ■  Detener Playit")
        print(f"  {Colors.GREEN}[9]{Colors.RESET}  ▶  Iniciar Filebrowser")
        print(f"  {Colors.RED}[10]{Colors.RESET} ■  Detener Filebrowser")
        print(f"  {Colors.YELLOW}[11]{Colors.RESET} 🔧 Resetear Filebrowser")
        print()

        # Monitor
        print(f"{Colors.BOLD}MONITOR{Colors.RESET}")
        print(f"  {Colors.GREEN}[12]{Colors.RESET} ▶  Iniciar Monitor Batería")
        print(f"  {Colors.RED}[13]{Colors.RESET} ■  Detener Monitor Batería")
        print(f"  {Colors.BLUE}[14]{Colors.RESET} 🔋 Ver Estado Batería")
        print()

        # Información
        print(f"{Colors.BOLD}INFORMACIÓN{Colors.RESET}")
        print(f"  {Colors.CYAN}[15]{Colors.RESET} 📋 Ver Logs")
        print(f"  {Colors.CYAN}[16]{Colors.RESET} 🌐 Info Conexión")
        print(f"  {Colors.CYAN}[17]{Colors.RESET} ⚙️  Ver Configuración")
        print(f"  {Colors.CYAN}[18]{Colors.RESET} 🔄 Actualizar Estado")
        print(f"  {Colors.MAGENTA}[19]{Colors.RESET} 🆙 Actualizar Sistema")
        print()

        print(f"  {Colors.MAGENTA}[0]{Colors.RESET}  ✖ Salir")
        print()
        print(f"{Colors.DIM}{'─' * 52}{Colors.RESET}")

        return prompt("Opción", "18")

    def show_status(self):
        """Muestra el estado del sistema."""
        print()
        print_box("📊 ESTADO DEL SISTEMA")
        print()

        # IP Local
        local_ip = get_local_ip()
        print(f"  🌐 IP Local:       {Colors.CYAN}{local_ip}{Colors.RESET}")
        print()

        # Estados de servicios
        mc_status = (
            f"{Colors.GREEN}● CORRIENDO{Colors.RESET}"
            if self.minecraft.is_running()
            else f"{Colors.RED}○ DETENIDO{Colors.RESET}"
        )
        playit_status = (
            f"{Colors.GREEN}● CORRIENDO{Colors.RESET}"
            if self.playit.is_running()
            else f"{Colors.RED}○ DETENIDO{Colors.RESET}"
        )
        fb_status = (
            f"{Colors.GREEN}● CORRIENDO{Colors.RESET}"
            if self.filebrowser.is_running()
            else f"{Colors.RED}○ DETENIDO{Colors.RESET}"
        )
        bat_status = (
            f"{Colors.GREEN}● ACTIVO{Colors.RESET}"
            if self.battery.is_running()
            else f"{Colors.RED}○ INACTIVO{Colors.RESET}"
        )

        print(f"  🎮 Minecraft:      {mc_status}")
        print(f"  🌍 Playit:         {playit_status}")
        print(f"  📁 Filebrowser:    {fb_status}")
        print(f"  🔋 Monitor Bat.:   {bat_status}")

        # Info de batería si está disponible
        try:
            import subprocess

            result = subprocess.run(
                ["termux-battery-status"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                level = data.get("percentage", 0)
                status = data.get("status", "UNKNOWN")

                bat_color = Colors.GREEN
                if level <= 20:
                    bat_color = Colors.YELLOW
                if level <= 10:
                    bat_color = Colors.RED

                print(
                    f"  ⚡ Batería:        {bat_color}{level}%{Colors.RESET} ({status})"
                )
        except:
            pass

        print()

    def handle_menu_choice(self, choice: str):
        """Maneja la selección del menú."""
        handlers = {
            "1": self.start_all,
            "2": self.stop_all,
            "3": self.restart_all,
            "4": self.start_minecraft,
            "5": self.stop_minecraft,
            "6": self.restart_minecraft,
            "7": self.start_playit,
            "8": self.stop_playit,
            "9": self.start_filebrowser,
            "10": self.stop_filebrowser,
            "11": self.reset_filebrowser,
            "12": self.start_battery_monitor,
            "13": self.stop_battery_monitor,
            "14": self.show_battery_info,
            "15": self.show_logs_menu,
            "16": self.show_connection_info,
            "17": self.show_configuration,
            "18": lambda: None,  # Solo refresh
            "19": self.update_system,
        }

        handler = handlers.get(choice)
        if handler:
            handler()
        else:
            log_error("Opción inválida")

    # =============================================================================
    # ACCIONES - Control General
    # =============================================================================

    def start_all(self):
        """Inicia todos los servicios."""
        print_header("🚀 INICIANDO SERVICIOS")
        print()

        log_step("Iniciando servidor Minecraft...")
        if self.minecraft.start():
            log_success("Minecraft iniciado")
        else:
            log_error("Error iniciando Minecraft")
            return

        print()
        log_step("Iniciando Playit.gg...")
        if self.playit.start():
            log_success("Playit iniciado")
            if self.playit.claim_url:
                print()
                print_box("🔗 VINCULACIÓN DE PLAYIT.GG")
                print()
                print(f"  Copia este enlace para vincular:")
                print(f"  {Colors.MAGENTA}{self.playit.claim_url}{Colors.RESET}")
                print()
                log_info("Abre el enlace en tu navegador")
        else:
            log_warning("Error iniciando Playit (opcional)")

        print()
        log_step("Iniciando Filebrowser...")
        if self.filebrowser.start():
            log_success("Filebrowser iniciado")
            self._show_filebrowser_info()
        else:
            log_warning("Error iniciando Filebrowser (opcional)")

        print()
        if self.settings.battery_monitor_enabled:
            if prompt_yes_no("¿Iniciar monitor de batería?"):
                log_step("Iniciando monitor de batería...")
                if self.battery.start():
                    log_success("Monitor de batería iniciado")
                else:
                    log_warning("Error iniciando monitor")

        print()
        log_success("¡Servicios iniciados!")

    def stop_all(self):
        """Detiene todos los servicios."""
        print_header("🛑 DETENIENDO SERVICIOS")
        print()

        if self.battery.is_running():
            log_step("Deteniendo monitor de batería...")
            self.battery.stop()
            log_success("Monitor detenido")
            print()

        log_step("Deteniendo Filebrowser...")
        self.filebrowser.stop()
        log_success("Filebrowser detenido")
        print()

        log_step("Deteniendo Playit...")
        self.playit.stop()
        log_success("Playit detenido")
        print()

        log_step("Deteniendo servidor Minecraft...")
        self.minecraft.stop()
        log_success("Minecraft detenido")
        print()

        log_success("¡Todos los servicios detenidos!")

    def restart_all(self):
        """Reinicia todos los servicios."""
        self.stop_all()
        time.sleep(3)
        self.start_all()

    # =============================================================================
    # ACCIONES - Minecraft
    # =============================================================================

    def start_minecraft(self):
        """Inicia el servidor Minecraft."""
        if self.minecraft.start():
            log_success("Servidor iniciado correctamente")
        else:
            log_error("Error iniciando el servidor")
            log_info("Revisa los logs en [15] para más detalles")

    def stop_minecraft(self):
        """Detiene el servidor Minecraft."""
        if self.minecraft.stop():
            log_success("Servidor detenido correctamente")
        else:
            log_error("Error deteniendo el servidor")

    def restart_minecraft(self):
        """Reinicia el servidor Minecraft."""
        log_step("Reiniciando servidor...")
        if self.minecraft.restart():
            log_success("Servidor reiniciado")
        else:
            log_error("Error reiniciando servidor")

    # =============================================================================
    # ACCIONES - Playit
    # =============================================================================

    def start_playit(self):
        """Inicia Playit.gg."""
        if self.playit.start(timeout=60):
            log_success("Playit iniciado")

            if self.playit.claim_url:
                print()
                print_box("🔗 VINCULACIÓN DE PLAYIT.GG")
                print()
                print("  Copia este enlace para vincular:")
                print(f"  {Colors.MAGENTA}{self.playit.claim_url}{Colors.RESET}")
                print()
                log_info("Abre el enlace en tu navegador para activar")
            elif self.playit.tunnel_address:
                print()
                log_success(f"Túnel activo: {self.playit.tunnel_address}")
        else:
            log_error("Error iniciando Playit")
            log_info("Revisa los logs en [15]")

    def stop_playit(self):
        """Detiene Playit.gg."""
        self.playit.stop()
        log_success("Playit detenido")

    # =============================================================================
    # ACCIONES - Filebrowser
    # =============================================================================

    def start_filebrowser(self):
        """Inicia Filebrowser."""
        if self.filebrowser.start():
            log_success("Filebrowser iniciado")
            self._show_filebrowser_info()
        else:
            log_error("Error iniciando Filebrowser")

    def stop_filebrowser(self):
        """Detiene Filebrowser."""
        self.filebrowser.stop()
        log_success("Filebrowser detenido")

    def reset_filebrowser(self):
        """Resetea credenciales de Filebrowser."""
        log_warning("Esto regenerará las credenciales de Filebrowser")
        if not prompt_yes_no("¿Estás seguro?", default=False):
            log_info("Operación cancelada")
            return

        if self.filebrowser.reset_credentials():
            log_success("Filebrowser reconfigurado")
            print()
            creds = self.filebrowser.get_credentials()
            print(f"  Usuario:    {Colors.YELLOW}{creds['user']}{Colors.RESET}")
            print(f"  Contraseña: {Colors.YELLOW}{creds['password']}{Colors.RESET}")
        else:
            log_error("Error reconfigurando Filebrowser")

    def _show_filebrowser_info(self):
        """Muestra información de acceso a Filebrowser."""
        creds = self.filebrowser.get_credentials()
        local_ip = get_local_ip()

        print()
        print_box("📁 GESTOR DE ARCHIVOS")
        print()
        print(
            f"  🌐 URL:        {Colors.CYAN}http://{local_ip}:{creds['port']}{Colors.RESET}"
        )
        print(f"  👤 Usuario:    {Colors.YELLOW}{creds['user']}{Colors.RESET}")
        print(f"  🔑 Contraseña: {Colors.YELLOW}{creds['password']}{Colors.RESET}")
        print()
        log_warning("¡Guarda estas credenciales!")

    # =============================================================================
    # ACCIONES - Batería
    # =============================================================================

    def start_battery_monitor(self):
        """Inicia el monitor de batería."""
        if self.battery.start():
            log_success("Monitor de batería iniciado")
            log_info(f"Alertas configuradas: 20%, 10%, 5%")
        else:
            log_error("Error iniciando monitor")
            log_info("Verifica que Termux:API esté instalado")

    def stop_battery_monitor(self):
        """Detiene el monitor de batería."""
        self.battery.stop()
        log_success("Monitor detenido")

    def show_battery_info(self):
        """Muestra información de batería."""
        status = self.battery.get_status()

        print()
        print_box("🔋 ESTADO DE LA BATERÍA")
        print()

        if status["battery_info"]:
            info = status["battery_info"]
            level = info["level"]

            color = Colors.GREEN
            if level <= 20:
                color = Colors.YELLOW
            if level <= 10:
                color = Colors.RED

            print(f"  Nivel:       {color}{level}%{Colors.RESET}")
            print(f"  Estado:      {info['status']}")
            print(f"  Temperatura: {info['temperature']}°C")
        else:
            log_error("No se pudo obtener información de batería")
            log_info("Instala Termux:API desde F-Droid")

        print()
        monitor_status = (
            f"{Colors.GREEN}● Activo{Colors.RESET}"
            if status["running"]
            else f"{Colors.RED}○ Inactivo{Colors.RESET}"
        )
        print(f"  Monitor:     {monitor_status}")
        print()

    # =============================================================================
    # ACCIONES - Información
    # =============================================================================

    def show_logs_menu(self):
        """Menú de visualización de logs."""
        print_header("📋 VER LOGS")

        options = [
            "Minecraft (30 líneas)",
            "Playit.gg (30 líneas)",
            "Filebrowser (30 líneas)",
            "Monitor Batería (30 líneas)",
            "Ver todos (resumen)",
            "Volver",
        ]

        choice = prompt_choice("Selecciona log:", options, default=1)

        if choice == 5:  # Volver
            return

        clear_screen()

        if choice == 4:  # Ver todos
            logs = self.log_manager.get_all_recent_logs(lines=10)
            for component, content in logs.items():
                print(f"\n{'=' * 50}")
                print(f"  {component.upper()}")
                print("=" * 50)
                print(content)
        else:
            component = ["minecraft", "playit", "filebrowser", "battery"][choice]
            logger = self.log_manager.get(component)
            print(logger.get_recent_logs(30))

    def show_connection_info(self):
        """Muestra información de conexión."""
        print()
        print_box("🌐 INFORMACIÓN DE CONEXIÓN")
        print()

        local_ip = get_local_ip()

        # Local
        print(f"{Colors.GREEN}📱 CONEXIÓN LOCAL (Red WiFi){Colors.RESET}")
        print("   Para conectarte desde tu red:")
        print(f"   Dirección: {Colors.CYAN}{local_ip}:25565{Colors.RESET}")
        print()

        # Externa
        print(f"{Colors.YELLOW}🌍 CONEXIÓN EXTERNA (Playit.gg){Colors.RESET}")
        if self.playit.is_running():
            playit_status = self.playit.get_status()
            if playit_status["tunnel_address"]:
                print(
                    f"   Túnel: {Colors.CYAN}{playit_status['tunnel_address']}{Colors.RESET}"
                )
            elif playit_status["claim_url"]:
                print(
                    f"   Vincula en: {Colors.MAGENTA}{playit_status['claim_url']}{Colors.RESET}"
                )
            else:
                print("   Revisando información de túnel...")
        else:
            print("   Playit no está corriendo")
        print()

        # Filebrowser
        print(f"{Colors.BLUE}📁 GESTOR DE ARCHIVOS{Colors.RESET}")
        if self.filebrowser.is_running():
            creds = self.filebrowser.get_credentials()
            print(
                f"   URL: {Colors.CYAN}http://{local_ip}:{creds['port']}{Colors.RESET}"
            )
            print(f"   Usuario: {creds['user']}")
            print(f"   Contraseña: {creds['password']}")
        else:
            print("   No está corriendo")
        print()

    def show_configuration(self):
        """Muestra la configuración actual."""
        print()
        print_box("⚙️ CONFIGURACIÓN")
        print()
        print(f"  Archivo:        {self.settings.env_file}")
        print(f"  Servidor Dir:   {self.settings.server_dir}")
        print(f"  JAR:            {self.settings.server_jar}")
        print(f"  RAM:            {self.settings.java_ram}")
        print(f"  Puerto Files:   {self.settings.filebrowser_port}")
        print(f"  Aikar Flags:    {self.settings.use_aikar_flags}")
        print()
        print(
            f"  Para editar: {Colors.YELLOW}nano {self.settings.env_file}{Colors.RESET}"
        )
        print()

    def update_system(self):
        """Actualiza el sistema."""
        print()
        print_box("🆙 ACTUALIZAR SISTEMA")
        print()

        log_info("Esta opción descargará la última versión del sistema")
        log_warning("Se recomienda hacer backup antes")
        print()

        if not prompt_yes_no("¿Continuar con la actualización?"):
            log_info("Actualización cancelada")
            return

        log_step("Descargando actualizaciones...")
        # Aquí iría la lógica de git pull
        # Por ahora solo un placeholder
        log_info("Función de actualización en desarrollo")
        log_info("Por ahora, actualiza manualmente con:")
        print(f"  cd {self.settings.base_dir}")
        print("  git pull")

    # =============================================================================
    # SETUP WIZARD
    # =============================================================================

    def first_run_wizard(self) -> bool:
        """Wizard de configuración inicial."""
        print_header("🎯 CONFIGURACIÓN INICIAL")
        print()

        log_info("¡Bienvenido! Configuremos tu servidor paso a paso")
        print()

        # RAM
        print("¿Cuánta RAM deseas asignar?")
        ram_options = [
            "512M  (Mínimo)",
            "1G    (Recomendado móviles)",
            "2G    (Recomendado tablets)",
            "3G    (Alto rendimiento)",
            "Personalizado",
        ]
        ram_choice = prompt_choice("Selecciona:", ram_options, default=2)

        ram_values = ["512M", "1G", "2G", "3G", ""]
        java_ram = ram_values[ram_choice]

        if ram_choice == 4:  # Personalizado
            java_ram = prompt("Cantidad (ej: 1500M, 2G)", "1G")

        log_success(f"RAM configurada: {java_ram}")

        # Optimizaciones
        print()
        use_aikar = prompt_yes_no("¿Usar Aikar's Flags (optimizaciones)?")
        log_success(
            "Optimizaciones " + ("habilitadas" if use_aikar else "deshabilitadas")
        )

        # Guardar configuración
        self.settings.save(
            {"JAVA_RAM": java_ram, "USE_AIKAR_FLAGS": use_aikar, "FIRST_RUN": False}
        )

        # Subir JAR
        print()
        print_box("📁 SUBIR SERVIDOR JAR")
        print()
        log_info("Necesitas subir el archivo .jar de tu servidor")
        print()

        log_step("Iniciando Filebrowser...")
        if not self.filebrowser.start():
            log_error("Error iniciando Filebrowser")
            return False

        self._show_filebrowser_info()

        print()
        print_box("📋 INSTRUCCIONES")
        print()
        print("  1. Abre la URL en tu navegador")
        print("  2. Inicia sesión con las credenciales")
        print("  3. Sube tu archivo .jar del servidor")
        print("     (Vanilla, Fabric, Paper, etc.)")
        print("  4. Cuando termines, vuelve aquí")
        print()

        press_enter("Presiona Enter cuando hayas subido el JAR")

        # Buscar JARs
        log_step("Buscando archivos JAR...")
        jars = list(self.settings.server_dir.glob("*.jar"))

        if not jars:
            log_error("No se encontró ningún JAR")
            log_info(f"Sube el archivo a: {self.settings.server_dir}")
            return False

        if len(jars) == 1:
            server_jar = jars[0].name
            log_success(f"JAR detectado: {server_jar}")
        else:
            jar_options = [jar.name for jar in jars]
            jar_choice = prompt_choice("Múltiples JARs encontrados:", jar_options)
            server_jar = jar_options[jar_choice]
            log_success(f"JAR seleccionado: {server_jar}")

        self.settings.save({"SERVER_JAR": server_jar})

        # Configurar Playit
        print()
        print_box("🌍 CONFIGURAR PLAYIT.GG")
        print()
        log_info("Configurando conexión externa...")

        if self.playit.start():
            if self.playit.claim_url:
                print()
                print(
                    f"  Vincula en: {Colors.MAGENTA}{self.playit.claim_url}{Colors.RESET}"
                )
                print()
                press_enter("Presiona Enter después de vincular")

        self.filebrowser.stop()

        # Finalizar
        print()
        print_box("✅ CONFIGURACIÓN COMPLETADA")
        print()
        log_success("¡Tu servidor está listo!")
        print()
        print("Configuración guardada:")
        print(f"  • RAM: {java_ram}")
        print(f"  • Optimizado: {use_aikar}")
        print(f"  • JAR: {server_jar}")
        print()
        press_enter()

        return True

    def exit_program(self):
        """Sale del programa."""
        print()
        if prompt_yes_no("¿Detener servicios antes de salir?", default=False):
            self.stop_all()

        print()
        log_success("¡Hasta luego!")
        self.logger.info("Manager finalizado")


def main():
    """Función principal."""
    try:
        manager = MCServerManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n\n¡Hasta luego!")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}ERROR FATAL:{Colors.RESET} {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
