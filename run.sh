#!/bin/bash

# =============================================================================
# Script de instalación y ejecución del Panel de Escritorio
# Compatible con XFCE, OpenBox y otros gestores de ventanas
# =============================================================================

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANEL_SCRIPT="$SCRIPT_DIR/main.py"
LOG_FILE="$SCRIPT_DIR/panel.log"

# Función para imprimir mensajes con colores
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%H:%M:%S')] ${message}${NC}"
}

# Función para detectar el gestor de paquetes
detect_package_manager() {
    if command -v apt &> /dev/null; then
        echo "apt"
    elif command -v yum &> /dev/null; then
        echo "yum"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

# Función para instalar paquetes según el sistema
install_system_package() {
    local package=$1
    local pm=$(detect_package_manager)
    
    print_message $BLUE "Instalando $package usando $pm..."
    
    case $pm in
        "apt")
            sudo apt update && sudo apt install -y $package
            ;;
        "yum")
            sudo yum install -y $package
            ;;
        "dnf")
            sudo dnf install -y $package
            ;;
        "pacman")
            sudo pacman -S --noconfirm $package
            ;;
        "zypper")
            sudo zypper install -y $package
            ;;
        *)
            print_message $RED "Gestor de paquetes no soportado. Instala manualmente: $package"
            return 1
            ;;
    esac
}

# Función para verificar si Python está instalado
check_python() {
    print_message $CYAN "Verificando Python..."
    
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_message $GREEN "Python3 encontrado: v$python_version"
        return 0
    elif command -v python &> /dev/null; then
        local python_version=$(python --version 2>&1 | cut -d' ' -f2)
        if [[ $python_version == 3.* ]]; then
            print_message $GREEN "Python encontrado: v$python_version"
            return 0
        else
            print_message $YELLOW "Python 2 detectado. Se necesita Python 3."
        fi
    fi
    
    print_message $RED "Python 3 no encontrado."
    read -p "¿Instalar Python 3? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_system_package python3
        return $?
    else
        print_message $RED "Python 3 es requerido para ejecutar el panel."
        return 1
    fi
}

# Función para verificar e instalar pip
check_pip() {
    print_message $CYAN "Verificando pip..."
    
    if command -v pip3 &> /dev/null; then
        print_message $GREEN "pip3 encontrado"
        return 0
    elif command -v pip &> /dev/null; then
        print_message $GREEN "pip encontrado"
        return 0
    fi
    
    print_message $YELLOW "pip no encontrado. Intentando instalar..."
    
    # Intentar instalar pip según el sistema
    local pm=$(detect_package_manager)
    case $pm in
        "apt")
            install_system_package python3-pip
            ;;
        "yum"|"dnf")
            install_system_package python3-pip
            ;;
        "pacman")
            install_system_package python-pip
            ;;
        "zypper")
            install_system_package python3-pip
            ;;
        *)
            print_message $RED "No se pudo instalar pip automáticamente"
            return 1
            ;;
    esac
}


# Función para instalar dependencias Python
install_python_dependencies() {
    print_message $CYAN "Verificando dependencias de Python..."
    # Lista de dependencias Python
    local python_deps=("psutil" "notify2")
    local pyqt_deps=("PyQt6" "PyQt5")
    local missing_deps=()
    local pyqt_found=false

    # Verificar PyQt (PyQt6 o PyQt5)
    for dep in "${pyqt_deps[@]}"; do
        python3 -c "import $dep" 2>/dev/null
        if [ $? -eq 0 ]; then
            print_message $GREEN "✓ $dep disponible"
            pyqt_found=true
            break
        fi
    done
    if [ "$pyqt_found" = false ]; then
        print_message $YELLOW "PyQt no encontrado. Se instalará PyQt6"
        missing_deps+=("PyQt6")
    fi

    # Verificar otras dependencias Python
    for dep in "${python_deps[@]}"; do
        python3 -c "import $dep" 2>/dev/null
        if [ $? -ne 0 ]; then
            missing_deps+=("$dep")
        else
            print_message $GREEN "✓ $dep disponible"
        fi
    done

    # Instalar dependencias faltantes
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_message $YELLOW "Dependencias faltantes: ${missing_deps[*]}"
        for dep in "${missing_deps[@]}"; do
            print_message $BLUE "Instalando $dep con pip..."
            if command -v pip3 &> /dev/null; then
                pip3 install --user $dep
            elif command -v pip &> /dev/null; then
                pip install --user $dep
            else
                print_message $RED "pip no disponible para instalar $dep"
            fi
        done
    else
        print_message $GREEN "Todas las dependencias Python están disponibles"
    fi
}

# Función para instalar dependencias del sistema
install_system_dependencies() {
    print_message $CYAN "Verificando dependencias del sistema..."
    # Lista de dependencias del sistema
    local system_deps=("wmctrl" "xdotool" "amixer" "pactl" "dbus-monitor" "lsblk" "bluetoothctl" "udisksctl" "xprop" "xdg-open" "xdg-utils")
    local missing_deps=()
    for dep in "${system_deps[@]}"; do
        if command -v $dep &> /dev/null; then
            print_message $GREEN "✓ $dep disponible"
        else
            missing_deps+=($dep)
        fi
    done
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_message $YELLOW "Dependencias del sistema faltantes: ${missing_deps[*]}"
        for dep in "${missing_deps[@]}"; do
            install_system_package $dep
        done
    else
        print_message $GREEN "Todas las dependencias del sistema están disponibles"
    fi
}

# Función para verificar el entorno gráfico
check_display() {
    print_message $CYAN "Verificando entorno gráfico..."
    
    if [ -z "$DISPLAY" ]; then
        print_message $RED "No se detectó un entorno gráfico (DISPLAY no está configurado)"
        print_message $YELLOW "Asegúrate de ejecutar este script en una sesión gráfica"
        return 1
    else
        print_message $GREEN "Entorno gráfico detectado: $DISPLAY"
    fi
    
    # Verificar si es una sesión SSH con X11 forwarding
    if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
        print_message $YELLOW "Sesión SSH detectada. Verifica que X11 forwarding esté habilitado"
    fi
    
    return 0
}

# Función para crear el script del panel si no existe
create_panel_script() {
    if [ ! -f "$PANEL_SCRIPT" ]; then
        print_message $RED "main.py no encontrado en $SCRIPT_DIR"
        print_message $BLUE "Por favor, asegúrate de que el archivo main.py esté en el mismo directorio que run.sh"
        return 1
    else
        print_message $GREEN "Script del panel encontrado: $PANEL_SCRIPT"
        # Hacer ejecutable
        chmod +x "$PANEL_SCRIPT"
    fi
    
    return 0
}

# Función para crear un .desktop file para autostart
create_autostart() {
    local autostart_dir="$HOME/.config/autostart"
    local desktop_file="$autostart_dir/desktop-panel.desktop"
    
    read -p "¿Crear entrada de autostart para iniciar el panel automáticamente? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Crear directorio si no existe
        mkdir -p "$autostart_dir"
        
        # Crear archivo .desktop
        cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Name=Panel de Escritorio
Comment=Panel personalizado para XFCE/OpenBox
Exec=$SCRIPT_DIR/run.sh --silent
Icon=preferences-desktop
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
        
        print_message $GREEN "Entrada de autostart creada en: $desktop_file"
    fi
}

# Función para mostrar ayuda
show_help() {
    echo "Panel de Escritorio - Script de instalación y ejecución"
    echo
    echo "Uso: $0 [opciones]"
    echo
    echo "Opciones:"
    echo "  -h, --help       Mostrar esta ayuda"
    echo "  -s, --silent     Ejecutar en modo silencioso (sin preguntas interactivas)"
    echo "  -i, --install    Solo instalar dependencias, no ejecutar panel"
    echo "  -r, --run        Solo ejecutar panel (asumir dependencias instaladas)"
    echo "  -c, --check      Solo verificar dependencias"
    echo "  --autostart      Crear entrada de autostart"
    echo "  --log            Mostrar log del panel"
    echo
}

# Función para mostrar log
show_log() {
    if [ -f "$LOG_FILE" ]; then
        print_message $CYAN "Mostrando últimas 50 líneas del log:"
        tail -n 50 "$LOG_FILE"
    else
        print_message $YELLOW "No se encontró archivo de log"
    fi
}

# Función principal de instalación
install_dependencies() {
    print_message $BLUE "=== Instalando dependencias del Panel de Escritorio ==="
    
    # Verificaciones y instalaciones
    check_python || exit 1
    check_pip
    install_python_dependencies
    install_system_dependencies
    print_message $GREEN "=== Instalación de dependencias completada ==="
}

# Función para ejecutar el panel
run_panel() {
    print_message $BLUE "=== Iniciando Panel de Escritorio ==="
    
    # Verificar que el script existe
    create_panel_script || exit 1
    
    # Verificar entorno gráfico
    check_display || exit 1
    
    # Ejecutar el panel
    print_message $GREEN "Iniciando panel..."
    if [[ "$1" == "--silent" ]]; then
        python3 "$PANEL_SCRIPT" >> "$LOG_FILE" 2>&1 &
        echo $! > "$SCRIPT_DIR/panel.pid"
        print_message $GREEN "Panel iniciado en background (PID: $!)"
    else
        python3 "$PANEL_SCRIPT"
    fi
}

# Función principal
main() {
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--install)
            install_dependencies
            exit 0
            ;;
        -r|--run)
            run_panel "$2"
            exit 0
            ;;
        -c|--check)
            check_python
            check_pip
            install_python_dependencies
            install_system_dependencies
            exit 0
            ;;
        --autostart)
            create_autostart
            exit 0
            ;;
        --log)
            show_log
            exit 0
            ;;
        -s|--silent)
            # Verificar dependencias críticas silenciosamente
            command -v python3 &> /dev/null || exit 1
            run_panel --silent
            exit 0
            ;;
        "")
            # Ejecución normal
            print_message $BLUE "=== Panel de Escritorio - Instalación y Ejecución ==="
            print_message $CYAN "Detectando sistema..."
            print_message $YELLOW "Sistema: $(uname -s) $(uname -r)"
            print_message $YELLOW "Gestor de paquetes: $(detect_package_manager)"
            echo
            
            install_dependencies
            echo
            run_panel
            ;;
        *)
            print_message $RED "Opción desconocida: $1"
            show_help
            exit 1
            ;;
    esac
}

# Trap para limpieza al salir
cleanup() {
    if [ -f "$SCRIPT_DIR/panel.pid" ]; then
        local pid=$(cat "$SCRIPT_DIR/panel.pid")
        if kill -0 $pid 2>/dev/null; then
            print_message $YELLOW "Cerrando panel..."
            kill $pid
        fi
        rm -f "$SCRIPT_DIR/panel.pid"
    fi
}

trap cleanup EXIT

# Ejecutar función principal
main "$@"