#!/data/data/com.termux/files/usr/bin/bash

# =============================================================================
# MC SERVER TERMUX - INSTALADOR v1.0.0
# Instalación automatizada con manejo robusto de errores
# =============================================================================

set -e  # Salir en cualquier error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuración
REPO_USER="yunkz97"
REPO_NAME="mc-server-termux"
VERSION="1.0.0"
BASE_DIR="$HOME/mc-server-termux"
GITHUB_RAW="https://raw.githubusercontent.com/${REPO_USER}/${REPO_NAME}/main"

# =============================================================================
# FUNCIONES DE UI
# =============================================================================

print_header() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "════════════════════════════════════════════════════════"
    echo "     🎮 MC SERVER TERMUX - INSTALADOR v${VERSION}"
    echo "════════════════════════════════════════════════════════"
    echo -e "${NC}\n"

    if [ "$DEBUG" = "1" ]; then
        echo -e "${YELLOW}[MODO DEBUG ACTIVADO]${NC}"
        echo "  TMP_DIR: $TMP_DIR"
        echo "  BASE_DIR: $BASE_DIR"
        echo ""
    fi
}

log_step() { echo -e "${BLUE}[→]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_info() { echo -e "${CYAN}[i]${NC} $1"; }

# Spinner simple para operaciones largas
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while kill -0 $pid 2>/dev/null; do
        local temp=${spinstr#?}
        printf " ${CYAN}[%c]${NC}  " "$spinstr"
        spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# =============================================================================
# VERIFICACIONES PREVIAS
# =============================================================================

check_termux() {
    log_step "Verificando entorno Termux..."

    if [ ! -d "/data/data/com.termux" ]; then
        log_error "Este script solo funciona en Termux"
        echo ""
        log_info "Descarga Termux desde F-Droid:"
        echo "  https://f-droid.org/packages/com.termux/"
        echo ""
        log_warning "NO uses la versión de Play Store (está desactualizada)"
        exit 1
    fi

    log_success "Entorno Termux OK"
}

check_storage() {
    log_step "Verificando permisos de almacenamiento..."

    if [ ! -d "$HOME/storage" ]; then
        log_warning "Configurando permisos de almacenamiento..."
        termux-setup-storage
        sleep 2

        # Verificar nuevamente
        if [ ! -d "$HOME/storage" ]; then
            log_error "No se pudieron configurar los permisos"
            log_info "Ejecuta manualmente: termux-setup-storage"
            exit 1
        fi
    fi

    log_success "Permisos OK"
}

check_internet() {
    log_step "Verificando conexión a internet..."

    if ! ping -c 1 -W 5 8.8.8.8 &> /dev/null; then
        log_error "No hay conexión a internet"
        log_info "Conecta a WiFi o datos móviles e intenta de nuevo"
        exit 1
    fi

    log_success "Conexión OK"
}

check_space() {
    log_step "Verificando espacio disponible..."

    # Obtener espacio disponible con unidad
    local available_raw=$(df -h "$HOME" | awk 'NR==2 {print $4}')
    debug_log "Espacio raw: '$available_raw'"

    local available_value=$(echo "$available_raw" | sed 's/[^0-9.]//g')
    debug_log "Valor numérico: '$available_value'"

    local available_unit=$(echo "$available_raw" | sed 's/[0-9.]//g' | tr '[:lower:]' '[:upper:]')
    debug_log "Unidad: '$available_unit'"

    # Convertir a MB para comparación (sin usar bc)
    local available_mb=0
    case "$available_unit" in
        G|GB)
            # Convertir GB a MB (multiplicar por 1024)
            if command -v awk &> /dev/null; then
                available_mb=$(awk "BEGIN {printf \"%.0f\", ${available_value} * 1024}")
            else
                # Fallback sin awk (menos preciso)
                available_mb=$(( ${available_value%.*} * 1024 ))
            fi
            debug_log "Conversión GB->MB: ${available_mb}MB"
            ;;
        M|MB)
            available_mb=${available_value%.*}
            debug_log "Ya en MB: ${available_mb}MB"
            ;;
        K|KB)
            # Convertir KB a MB (dividir por 1024)
            if command -v awk &> /dev/null; then
                available_mb=$(awk "BEGIN {printf \"%.0f\", ${available_value} / 1024}")
            else
                available_mb=$(( ${available_value%.*} / 1024 ))
            fi
            debug_log "Conversión KB->MB: ${available_mb}MB"
            ;;
        T|TB)
            # Convertir TB a MB
            if command -v awk &> /dev/null; then
                available_mb=$(awk "BEGIN {printf \"%.0f\", ${available_value} * 1024 * 1024}")
            else
                available_mb=$(( ${available_value%.*} * 1024 * 1024 ))
            fi
            debug_log "Conversión TB->MB: ${available_mb}MB"
            ;;
        *)
            # Si no podemos determinar, asumir que hay suficiente espacio
            debug_log "Unidad desconocida, asumiendo espacio suficiente"
            log_success "Espacio: ${available_raw} disponibles"
            return 0
            ;;
    esac

    local required=500  # MB mínimos requeridos
    debug_log "Espacio disponible: ${available_mb}MB, requerido: ${required}MB"

    if [ "$available_mb" -lt "$required" ]; then
        log_warning "Espacio bajo: ${available_raw} disponibles (${available_mb}MB)"
        log_info "Se recomiendan al menos ${required}MB libres"
        echo ""
        read -p "¿Continuar de todos modos? (s/N): " -r
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            log_info "Instalación cancelada"
            exit 0
        fi
    else
        log_success "Espacio suficiente (${available_raw} disponibles)"
    fi
}

# =============================================================================
# INSTALACIÓN DE DEPENDENCIAS
# =============================================================================

update_packages() {
    log_step "Actualizando repositorios..."

    {
        yes | pkg update 2>&1
    } > "$TMP_DIR/pkg_update.log" &

    spinner $!
    wait $!

    log_success "Repositorios actualizados"
}

install_package() {
    local package="$1"
    local display_name="${2:-$package}"

    # Verificar si ya está instalado
    if pkg list-installed 2>/dev/null | grep -q "^${package}/"; then
        log_success "$display_name ya instalado"
        return 0
    fi

    log_step "Instalando $display_name..."

    {
        yes | pkg install "$package" 2>&1
    } > "$TMP_DIR/pkg_${package}.log" &

    local pid=$!
    spinner $pid

    if wait $pid; then
        log_success "$display_name instalado"
        return 0
    else
        log_error "Error instalando $display_name"
        log_info "Ver detalles en: $TMP_DIR/pkg_${package}.log"
        return 1
    fi
}

install_dependencies() {
    log_step "Instalando dependencias del sistema..."
    echo ""

    local failed=()

    # Dependencias críticas
    install_package "python" "Python 3" || failed+=("Python")
    install_package "proot" "Proot (para playit)" || failed+=("Proot")
    install_package "openjdk-21" "Java 21" || failed+=("Java")
    install_package "wget" "Wget" || failed+=("Wget")
    install_package "git" "Git" || failed+=("Git")

    # Dependencias opcionales (no bloquean instalación)
    install_package "termux-api" "Termux:API" || log_warning "Termux:API no disponible (monitor de batería deshabilitado)"

    echo ""

    if [ ${#failed[@]} -gt 0 ]; then
        log_error "Faltan dependencias críticas: ${failed[*]}"
        log_info "Intenta instalarlas manualmente:"
        for dep in "${failed[@]}"; do
            echo "  pkg install ${dep,,}"
        done
        exit 1
    fi

    log_success "Todas las dependencias instaladas"
}

verify_python() {
    log_step "Verificando Python..."

    if ! command -v python &> /dev/null; then
        log_error "Python no está disponible"
        exit 1
    fi

    local py_version=$(python --version 2>&1 | awk '{print $2}')
    log_success "Python $py_version detectado"

    # Verificar pip
    if ! python -m pip --version &> /dev/null; then
        log_step "Instalando pip..."
        python -m ensurepip --upgrade 2>&1 | grep -v "^$"
    fi

    log_success "Pip disponible"
}

# =============================================================================
# DESCARGA DEL PROYECTO
# =============================================================================

handle_existing_installation() {
    if [ ! -d "$BASE_DIR" ]; then
        return 0
    fi

    log_warning "Se detectó una instalación existente"
    echo ""
    echo "Opciones:"
    echo "  1) Actualizar (mantener datos)"
    echo "  2) Reinstalar (borrar todo)"
    echo "  3) Cancelar"
    echo ""
    read -p "Selecciona [1]: " -r option
    option=${option:-1}

    case $option in
        1)
            log_info "Actualizando instalación..."
            # Hacer backup de configuración
            if [ -f "$BASE_DIR/.env" ]; then
                cp "$BASE_DIR/.env" "$HOME/.mc-server-backup.env"
                log_success "Configuración respaldada"
            fi
            ;;
        2)
            log_warning "Eliminando instalación anterior..."
            rm -rf "$BASE_DIR"
            log_success "Instalación eliminada"
            ;;
        3)
            log_info "Instalación cancelada"
            exit 0
            ;;
        *)
            log_error "Opción inválida"
            exit 1
            ;;
    esac
}

download_project() {
    log_step "Descargando proyecto desde GitHub..."

    if [ -d "$BASE_DIR/.git" ]; then
        cd "$BASE_DIR"
        git pull origin main 2>&1 | grep -v "^$"
    else
        git clone "https://github.com/${REPO_USER}/${REPO_NAME}.git" "$BASE_DIR" 2>&1 | grep -v "^$"
    fi

    if [ ! -f "$BASE_DIR/main.py" ]; then
        log_error "Error al descargar el proyecto"
        log_info "Verifica tu conexión y que el repositorio exista"
        exit 1
    fi

    log_success "Proyecto descargado"
}

install_python_deps() {
    log_step "Instalando dependencias Python..."

    cd "$BASE_DIR"

    if [ ! -f "requirements.txt" ]; then
        log_error "No se encontró requirements.txt"
        exit 1
    fi

    {
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
    } > "$TMP_DIR/pip_install.log" 2>&1 &

    spinner $!

    if wait $!; then
        log_success "Dependencias Python instaladas"
    else
        log_error "Error instalando dependencias Python"
        log_info "Ver detalles en: $TMP_DIR/pip_install.log"
        exit 1
    fi
}

# =============================================================================
# DESCARGA DE BINARIOS
# =============================================================================

download_binaries() {
    log_step "Descargando herramientas adicionales..."

    mkdir -p "$BASE_DIR/bin"
    cd "$BASE_DIR/bin"

    local arch=$(uname -m)
    local playit_url=""

    case "$arch" in
        aarch64|arm64)
            playit_url="https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-aarch64"
            ;;
        armv7l|armv8l)
            playit_url="https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-armv7"
            ;;
        x86_64)
            playit_url="https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-x86_64"
            ;;
        *)
            log_warning "Arquitectura no soportada: $arch"
            log_warning "Playit.gg puede no funcionar"
            return 1
            ;;
    esac

    echo ""

    # Playit
    if [ -f "playit" ]; then
        log_success "Playit ya descargado"
    else
        log_step "Descargando Playit.gg..."
        if wget -q --show-progress "$playit_url" -O playit 2>&1; then
            chmod +x playit
            log_success "Playit descargado"
        else
            log_error "Error descargando Playit"
            return 1
        fi
    fi

    # Filebrowser
    if [ -f "filebrowser" ]; then
        log_success "Filebrowser ya descargado"
    else
        log_step "Descargando Filebrowser..."
        local fb_url="https://github.com/filebrowser/filebrowser/releases/latest/download/linux-arm64-filebrowser.tar.gz"

        if wget -q --show-progress "$fb_url" -O fb.tar.gz 2>&1; then
            tar -xzf fb.tar.gz filebrowser 2>/dev/null
            rm fb.tar.gz
            chmod +x filebrowser
            log_success "Filebrowser descargado"
        else
            log_error "Error descargando Filebrowser"
            return 1
        fi
    fi

    echo ""
    log_success "Herramientas descargadas"
}

# =============================================================================
# CONFIGURACIÓN INICIAL
# =============================================================================

create_directory_structure() {
    log_step "Creando estructura de directorios..."

    cd "$BASE_DIR"
    mkdir -p data logs run server backups bin

    log_success "Estructura creada"
}

setup_env() {
    log_step "Configurando variables de entorno..."

    cd "$BASE_DIR"

    if [ -f "$HOME/.mc-server-backup.env" ]; then
        cp "$HOME/.mc-server-backup.env" .env
        rm "$HOME/.mc-server-backup.env"
        log_success "Configuración anterior restaurada"
    elif [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_success "Archivo .env creado"
        else
            log_warning "No se encontró .env.example"
        fi
    else
        log_success "Archivo .env ya existe"
    fi
}

create_launcher() {
    log_step "Configurando acceso rápido..."

    # Eliminar alias antiguo si existe
    if grep -q "alias mcserver" "$HOME/.bashrc" 2>/dev/null; then
        sed -i '/alias mcserver/d' "$HOME/.bashrc"
    fi

    # Agregar nuevo alias
    cat >> "$HOME/.bashrc" << EOF

# MC Server Termux v${VERSION}
alias mcserver='cd ${BASE_DIR} && python main.py'
EOF

    log_success "Comando 'mcserver' configurado"
}

# =============================================================================
# RESUMEN FINAL
# =============================================================================

show_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "════════════════════════════════════════════════════════"
    echo "          ✓ INSTALACIÓN COMPLETADA ✓"
    echo "════════════════════════════════════════════════════════"
    echo -e "${NC}"
    echo ""

    echo -e "${CYAN}📁 Instalación en:${NC} $BASE_DIR"
    echo ""

    echo -e "${YELLOW}🚀 Para iniciar:${NC}"
    echo "  1. Reinicia Termux o ejecuta: ${CYAN}source ~/.bashrc${NC}"
    echo "  2. Ejecuta: ${CYAN}mcserver${NC}"
    echo ""

    echo -e "${YELLOW}📝 Necesitarás:${NC}"
    echo "  • Archivo .jar del servidor Minecraft"
    echo "    Descarga de: ${BLUE}https://papermc.io/downloads${NC}"
    echo ""
    echo "  • Cuenta en Playit.gg (gratis)"
    echo "    Regístrate en: ${BLUE}https://playit.gg${NC}"
    echo ""

    echo -e "${YELLOW}💡 Próximos pasos:${NC}"
    echo "  El Setup Wizard te guiará en la configuración inicial"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    print_header

    echo -e "${CYAN}Este instalador configurará automáticamente:${NC}"
    echo "  • Python + dependencias necesarias"
    echo "  • Java 21 para Minecraft"
    echo "  • Playit.gg para conexión externa"
    echo "  • Filebrowser para gestión de archivos"
    echo "  • Sistema completo de administración"
    echo ""
    echo -e "${YELLOW}Tiempo estimado: 3-7 minutos${NC}"
    echo ""
    echo -e "${GREEN}Iniciando en 3 segundos...${NC}"
    echo -e "${CYAN}(Ctrl+C para cancelar)${NC}"
    sleep 3

    echo ""

    # Verificaciones
    check_termux
    check_storage
    check_internet
    check_space
    echo ""

    # Instalación
    update_packages
    install_dependencies
    verify_python
    echo ""

    # Proyecto
    handle_existing_installation
    download_project
    install_python_deps
    echo ""

    # Binarios
    download_binaries
    echo ""

    # Configuración
    create_directory_structure
    setup_env
    create_launcher

    # Resumen
    show_summary

    # Iniciar
    read -p "¿Iniciar el administrador ahora? (S/n): " -r
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        log_info "Iniciando MC Server Manager..."
        sleep 1

        # Auto-eliminar el instalador
        INSTALLER_PATH=$(realpath "$0" 2>/dev/null || echo "$0")
        rm -f "$INSTALLER_PATH"

        cd "$BASE_DIR"
        exec python main.py
    else
        echo ""
        log_success "Instalación completa"
        log_info "Inicia cuando quieras con: ${CYAN}mcserver${NC}"

        # Auto-eliminar el instalador
        INSTALLER_PATH=$(realpath "$0" 2>/dev/null || echo "$0")
        rm -f "$INSTALLER_PATH"
    fi
}

# Trap para interrupciones
trap 'echo ""; log_error "Instalación interrumpida"; exit 1' INT TERM

# Ejecutar
main "$@"

# wow
