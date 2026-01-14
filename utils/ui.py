"""
Utilidades de interfaz de usuario para terminal.
Maneja colores, menús, prompts y formateo.
"""

import os
import sys
from typing import Callable, List, Optional

# =============================================================================
# COLORES ANSI
# =============================================================================


class Colors:
    """Códigos de color ANSI para terminal."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def strip(text: str) -> str:
        """Remueve códigos de color de un texto."""
        import re

        return re.sub(r"\033\[[0-9;]*m", "", text)


# =============================================================================
# FUNCIONES DE IMPRESIÓN
# =============================================================================


def print_header(title: str, version: str = "1.0.0"):
    """Imprime el header principal."""
    clear_screen()
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("════════════════════════════════════════════════════════")
    print(f"     🎮 {title}")
    print(f"              v{version}")
    print("════════════════════════════════════════════════════════")
    print(f"{Colors.RESET}\n")


def print_box(title: str, width: int = 52):
    """
    Imprime un título en una caja decorada.

    Args:
        title: Título a mostrar
        width: Ancho de la caja
    """
    # Limpiar colores para calcular longitud real
    clean_title = Colors.strip(title)
    text_len = len(clean_title)

    # Calcular padding
    total_padding = width - text_len
    padding_left = total_padding // 2
    padding_right = total_padding - padding_left

    print(f"{Colors.CYAN}╔{'═' * width}╗{Colors.RESET}")
    print(
        f"{Colors.CYAN}║{Colors.RESET}{' ' * padding_left}{title}{' ' * padding_right}{Colors.CYAN}║{Colors.RESET}"
    )
    print(f"{Colors.CYAN}╚{'═' * width}╝{Colors.RESET}")


def log_step(message: str):
    """Imprime un paso de proceso."""
    print(f"{Colors.BLUE}[→]{Colors.RESET} {message}")


def log_success(message: str):
    """Imprime un mensaje de éxito."""
    print(f"{Colors.GREEN}[✓]{Colors.RESET} {message}")


def log_error(message: str):
    """Imprime un mensaje de error."""
    print(f"{Colors.RED}[✗]{Colors.RESET} {message}")


def log_warning(message: str):
    """Imprime un mensaje de advertencia."""
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {message}")


def log_info(message: str):
    """Imprime un mensaje informativo."""
    print(f"{Colors.CYAN}[i]{Colors.RESET} {message}")


# =============================================================================
# INPUT Y MENÚS
# =============================================================================


def prompt(message: str, default: str = "") -> str:
    """
    Solicita input del usuario con valor por defecto.

    Args:
        message: Mensaje a mostrar
        default: Valor por defecto

    Returns:
        Respuesta del usuario o default
    """
    if default:
        display = f"{message} [{default}]: "
    else:
        display = f"{message}: "

    try:
        response = input(display).strip()
        return response if response else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """
    Solicita confirmación sí/no.

    Args:
        message: Mensaje a mostrar
        default: Valor por defecto

    Returns:
        True si es sí, False si es no
    """
    default_str = "S/n" if default else "s/N"
    response = prompt(f"{message} ({default_str})", "")

    if not response:
        return default

    return response.lower() in ("s", "si", "sí", "y", "yes")


def prompt_choice(message: str, options: List[str], default: int = 1) -> int:
    """
    Solicita elegir una opción de una lista.

    Args:
        message: Mensaje a mostrar
        options: Lista de opciones
        default: Opción por defecto (1-indexed)

    Returns:
        Índice de la opción elegida (0-indexed)
    """
    print(f"\n{message}")
    for i, option in enumerate(options, 1):
        print(f"  {i}) {option}")
    print()

    while True:
        try:
            response = prompt("Selecciona", str(default))
            choice = int(response)

            if 1 <= choice <= len(options):
                return choice - 1
            else:
                log_error(f"Opción inválida. Elige entre 1 y {len(options)}")
        except ValueError:
            log_error("Ingresa un número válido")


def show_menu(
    title: str,
    options: List[tuple[str, str]],
    status_callback: Optional[Callable] = None,
) -> str:
    """
    Muestra un menú interactivo.

    Args:
        title: Título del menú
        options: Lista de tuplas (key, descripción)
        status_callback: Función opcional para mostrar estado

    Returns:
        Tecla de la opción seleccionada
    """
    print_header(title)

    if status_callback:
        status_callback()

    print(f"{Colors.CYAN}╔{'═' * 52}╗{Colors.RESET}")
    print(f"{Colors.CYAN}║{' ' * 17}📋 MENÚ PRINCIPAL{' ' * 17}║{Colors.RESET}")
    print(f"{Colors.CYAN}╚{'═' * 52}╝{Colors.RESET}")
    print()

    for key, description in options:
        color = Colors.GREEN if key.isdigit() else Colors.CYAN
        print(f"  {color}[{key}]{Colors.RESET}  {description}")

    print()
    print(f"{Colors.DIM}{'─' * 52}{Colors.RESET}")

    return prompt("Opción", "0")


# =============================================================================
# UTILIDADES DE PANTALLA
# =============================================================================


def clear_screen():
    """Limpia la pantalla."""
    os.system("clear" if os.name != "nt" else "cls")


def press_enter(message: str = "Presiona Enter para continuar..."):
    """Espera a que el usuario presione Enter."""
    print()
    print(f"{Colors.DIM}{message}{Colors.RESET}")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print()


def show_loading(message: str, duration: float = 2.0):
    """
    Muestra un mensaje de carga con animación.

    Args:
        message: Mensaje a mostrar
        duration: Duración en segundos
    """
    import time

    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0

    while time.time() < end_time:
        print(
            f"\r{Colors.CYAN}[{spinner[i]}]{Colors.RESET}  {message}",
            end="",
            flush=True,
        )
        i = (i + 1) % len(spinner)
        time.sleep(0.1)

    print(f"\r{Colors.GREEN}[✓]{Colors.RESET}  {message}")


# =============================================================================
# FORMATEO DE DATOS
# =============================================================================


def format_status(label: str, value: str, is_good: bool = True) -> str:
    """
    Formatea un estado con colores.

    Args:
        label: Etiqueta del estado
        value: Valor del estado
        is_good: Si es un estado bueno (verde) o malo (rojo)

    Returns:
        String formateado con colores
    """
    color = Colors.GREEN if is_good else Colors.RED
    return f"  {label:20} {color}{value}{Colors.RESET}"


def format_size(bytes_size: int) -> str:
    """
    Formatea un tamaño en bytes a formato legible.

    Args:
        bytes_size: Tamaño en bytes

    Returns:
        String formateado (ej: "1.5 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def format_duration(seconds: int) -> str:
    """
    Formatea una duración en segundos a formato legible.

    Args:
        seconds: Duración en segundos

    Returns:
        String formateado (ej: "2h 30m")
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


# =============================================================================
# TABLAS
# =============================================================================


class Table:
    """Generador de tablas ASCII."""

    def __init__(self, headers: List[str]):
        self.headers = headers
        self.rows: List[List[str]] = []
        self.column_widths: List[int] = [len(h) for h in headers]

    def add_row(self, row: List[str]):
        """Agrega una fila a la tabla."""
        # Actualizar anchos de columna
        for i, cell in enumerate(row):
            clean_cell = Colors.strip(str(cell))
            self.column_widths[i] = max(self.column_widths[i], len(clean_cell))

        self.rows.append([str(cell) for cell in row])

    def print(self):
        """Imprime la tabla."""
        # Línea superior
        print("┌" + "┬".join("─" * (w + 2) for w in self.column_widths) + "┐")

        # Headers
        header_row = "│"
        for i, header in enumerate(self.headers):
            header_row += f" {header:^{self.column_widths[i]}} │"
        print(header_row)

        # Separador
        print("├" + "┼".join("─" * (w + 2) for w in self.column_widths) + "┤")

        # Filas
        for row in self.rows:
            row_str = "│"
            for i, cell in enumerate(row):
                clean_cell = Colors.strip(cell)
                padding = self.column_widths[i] - len(clean_cell)
                row_str += f" {cell}{' ' * padding} │"
            print(row_str)

        # Línea inferior
        print("└" + "┴".join("─" * (w + 2) for w in self.column_widths) + "┘")


# =============================================================================
# PROGRESS BAR
# =============================================================================


def print_progress_bar(
    current: int, total: int, prefix: str = "", suffix: str = "", length: int = 40
):
    """
    Imprime una barra de progreso.

    Args:
        current: Valor actual
        total: Valor total
        prefix: Texto antes de la barra
        suffix: Texto después de la barra
        length: Longitud de la barra en caracteres
    """
    if total == 0:
        return

    percent = int(100 * current / total)
    filled = int(length * current / total)
    bar = "█" * filled + "░" * (length - filled)

    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end="", flush=True)

    if current >= total:
        print()


# =============================================================================
# UTILIDAD DE RED
# =============================================================================


def get_local_ip() -> str:
    """
    Obtiene la IP local del dispositivo.

    Returns:
        Dirección IP o fallback
    """
    try:
        import subprocess

        # Método 1: ip addr
        result = subprocess.run(
            ["ip", "addr", "show", "wlan0"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            import re

            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)

        # Método 2: ifconfig
        result = subprocess.run(
            ["ifconfig", "wlan0"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            import re

            match = re.search(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)

        # Fallback
        return "192.168.X.X"

    except Exception:
        return "192.168.X.X"
