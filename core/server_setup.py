"""
Utilidades para la configuración inicial del servidor Minecraft.
Genera server.properties y ofrece descarga automática de Paper.
"""

import subprocess
from pathlib import Path
from typing import Optional


def generate_server_properties(
    server_dir: Path,
    port: int = 25565,
    motd: str = "MC Server Termux",
    max_players: int = 20,
    gamemode: str = "survival",
    difficulty: str = "normal",
    online_mode: bool = True,
    pvp: bool = True,
    view_distance: int = 10,
    simulation_distance: int = 10,
    allow_flight: bool = False,
    enable_command_block: bool = False,
    spawn_protection: int = 16,
) -> bool:
    """
    Genera un archivo server.properties con valores seguros.

    Args:
        server_dir: Directorio del servidor
        port: Puerto del servidor
        motd: Mensaje del día
        max_players: Máximo de jugadores
        gamemode: Modo de juego por defecto
        difficulty: Dificultad
        online_mode: Autenticación con Mojang
        pvp: Permitir PvP
        view_distance: Distancia de renderizado
        simulation_distance: Distancia de simulación
        allow_flight: Permitir vuelo
        enable_command_block: Habilitar bloques de comando
        spawn_protection: Radio de protección del spawn

    Returns:
        True si se generó correctamente
    """
    props_file = server_dir / "server.properties"

    properties = {
        "server-port": port,
        "motd": motd,
        "max-players": max_players,
        "gamemode": gamemode,
        "difficulty": difficulty,
        "online-mode": online_mode,
        "pvp": pvp,
        "view-distance": view_distance,
        "simulation-distance": simulation_distance,
        "allow-flight": allow_flight,
        "enable-command-block": enable_command_block,
        "spawn-protection": spawn_protection,
        "server-ip": "",
        "enable-rcon": False,
        "rcon.password": "",
        "rcon.port": 25575,
        "level-name": "world",
        "level-type": "minecraft\\:normal",
        "generator-settings": {},
        "level-seed": "",
        "max-world-size": 29999984,
        "allow-nether": True,
        "enable-query": False,
        "query.port": port,
        "network-compression-threshold": 256,
        "max-tick-time": 60000,
        "require-resource-pack": False,
        "resource-pack": "",
        "resource-pack-prompt": "",
        "resource-pack-sha1": "",
        "enforce-secure-profile": True,
        "white-list": False,
        "enforce-whitelist": False,
        "player-idle-timeout": 0,
        "op-permission-level": 4,
        "function-permission-level": 2,
        "rate-limit": 0,
        "hardcore": False,
        "spawn-npcs": True,
        "spawn-animals": True,
        "spawn-monsters": True,
        "generate-structures": True,
        "snooper-enabled": False,
        "prevent-proxy-connections": False,
        "use-native-transport": True,
        "enable-status": True,
        "hide-online-players": False,
        "entity-broadcast-range-percentage": 100,
        "simulation-distance": simulation_distance,
        "player-idle-timeout": 0,
        "debug": False,
        "force-gamemode": False,
        "text-filtering-config": "",
    }

    try:
        lines = [
            "# MC Server Termux - server.properties\n",
            "# Generado automáticamente\n",
            "\n",
        ]
        for key, value in properties.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            elif isinstance(value, dict):
                value = ""
            lines.append(f"{key}={value}\n")

        props_file.write_text("".join(lines), encoding="utf-8")
        return True
    except Exception:
        return False


def download_paper(
    server_dir: Path,
    version: str = "latest",
    build: str = "latest",
) -> Optional[Path]:
    """
    Descarga el servidor Paper más reciente.

    Args:
        server_dir: Directorio donde descargar
        version: Versión de Minecraft (ej: "1.21.4") o "latest"
        build: Build de Paper o "latest"

    Returns:
        Path al archivo descargado, o None si falla
    """
    try:
        import urllib.request
        import json

        # Resolver versión latest
        if version == "latest":
            versions_url = "https://api.papermc.io/v2/projects/paper"
            with urllib.request.urlopen(versions_url, timeout=15) as resp:
                data = json.loads(resp.read())
                version = data["versions"][-1]

        # Resolver build latest
        if build == "latest":
            builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}"
            with urllib.request.urlopen(builds_url, timeout=15) as resp:
                data = json.loads(resp.read())
                build = str(data["builds"][-1])

        # Descargar
        filename = f"paper-{version}-{build}.jar"
        download_url = (
            f"https://api.papermc.io/v2/projects/paper/versions/{version}"
            f"/builds/{build}/downloads/{filename}"
        )

        dest = server_dir / filename
        urllib.request.urlretrieve(download_url, str(dest))

        # Crear symlink server.jar si no existe
        server_jar = server_dir / "server.jar"
        if not server_jar.exists():
            server_jar.symlink_to(dest.name)

        return dest

    except Exception:
        return None


def accept_eula(server_dir: Path) -> bool:
    """
    Acepta el EULA escribiendo eula.txt directamente.

    Args:
        server_dir: Directorio del servidor

    Returns:
        True si se escribió correctamente
    """
    eula_file = server_dir / "eula.txt"
    try:
        eula_file.write_text(
            "# MC Server Termux - EULA aceptado automáticamente\n"
            "eula=true\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False
