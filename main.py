#!/usr/bin/env python3
"""
Panel de Escritorio para XFCE/OpenBox usando PyQt
Autor: Asistente AI
Licencia: MIT
"""

import sys
import os
import subprocess
import datetime
import threading
import time
import json
from pathlib import Path

# Variables globales para el sistema de notificaciones
NOTIFY2_AVAILABLE = False
try:
    import notify2
    NOTIFY2_AVAILABLE = True
except ImportError:
    print("Notify2 no disponible. Instala python3-notify2 para las notificaciones.")

class NotificationItem:
    def __init__(self, id, app_name, icon, summary, body):
        self.id = id
        self.app_name = app_name
        self.icon = icon
        self.summary = summary
        self.body = body
        self.timestamp = datetime.datetime.now()

# Intentar importar PyQt6 primero, luego PyQt5
try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    PYQT_VERSION = 6
    print("Usando PyQt6")
except ImportError:
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *
        PYQT_VERSION = 5
        print("Usando PyQt5")
    except ImportError:
        print("Error: PyQt5 o PyQt6 no encontrado. Instala con:")
        print("pip install PyQt6  # o pip install PyQt5")
        sys.exit(1)

# Intentar importar psutil para información del sistema
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Advertencia: psutil no disponible. Información del sistema limitada.")

class SystemTray(QSystemTrayIcon):
    """Icono en la bandeja del sistema"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_tray()
    
    def setup_tray(self):
        """Configurar el icono de la bandeja"""
        # Crear un icono simple si no hay uno disponible
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(100, 150, 200))
        icon = QIcon(pixmap)
        self.setIcon(icon)
        
        # Crear menú contextual
        menu = QMenu()
        
        show_action = menu.addAction("Mostrar Panel")
        show_action.triggered.connect(self.parent.show)
        
        hide_action = menu.addAction("Ocultar Panel")
        hide_action.triggered.connect(self.parent.hide)
        
        menu.addSeparator()
        
        settings_action = menu.addAction("Configuración")
        settings_action.triggered.connect(self.parent.show_settings)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.parent.quit_application)
        
        self.setContextMenu(menu)
        self.setToolTip("Panel de Escritorio")

class ApplicationMenu(QWidget):
    """Menú de aplicaciones con soporte de temas"""

    FAVORITES_FILE = os.path.expanduser("~/.config/desktop-panel/favorites.json")
    THEME_FILE = os.path.expanduser("~/.config/desktop-panel/menu_theme.json")
    THEMES = {
        "claro": "theme_light.css",
        "oscuro": "theme_dark.css",
        "sistema": None
    }

    DEFAULT_FAVORITES = [
        ("Firefox", "firefox", "firefox"),
        ("LibreOffice", "libreoffice", "libreoffice"),
        ("GIMP", "gimp", "gimp"),
        ("VLC", "vlc", "vlc"),
    ]

    SHORTCUTS = [
        ("Computador", "system-file-manager", os.path.expanduser("~")),
        ("Documentos", "folder-documents", os.path.expanduser("~/Documentos")),
        ("Descargas", "folder-downloads", os.path.expanduser("~/Descargas")),
        ("Música", "folder-music", os.path.expanduser("~/Música")),
        ("Imágenes", "folder-pictures", os.path.expanduser("~/Imágenes")),
        ("Videos", "folder-videos", os.path.expanduser("~/Videos")),
        ("Escritorio", "user-desktop", os.path.expanduser("~/Escritorio")),
        ("Configuraciones", "preferences-system", "settings"),
        ("Store", "applications-other", "store"),
        ("Terminal", "utilities-terminal", "terminal"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.load_favorites()
        self.theme = self.load_theme()
        self.setup_ui()
        self.load_applications()
        self.show_favorites()
        self.apply_theme(self.theme)

    def setup_ui(self):
        self.resize(600, 480)
        self.setMinimumSize(400, 350)
        self.setWindowTitle("Menú de Aplicaciones")
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        fondo = QWidget(self)
        fondo.setObjectName("MenuFondo")
        fondo_layout = QHBoxLayout(fondo)
        fondo_layout.setContentsMargins(12, 12, 12, 12)
        fondo_layout.setSpacing(8)

        # === IZQUIERDA: Favoritos o todas las apps ===
        left_layout = QVBoxLayout()
        left_layout.setSpacing(6)
        self.left_list = QListWidget()
        self.left_list.setIconSize(QSize(32, 32))
        self.left_list.itemClicked.connect(self.launch_left_item)
        self.left_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.left_list.customContextMenuRequested.connect(self.left_context_menu)
        left_layout.addWidget(self.left_list, 1)

        self.todas_btn = QPushButton("Todas las aplicaciones")
        self.todas_btn.setObjectName("TodasBtn")
        self.todas_btn.clicked.connect(self.toggle_left_list)
        left_layout.addWidget(self.todas_btn)

        # Botón de configuración de tema (solo icono pequeño)
        self.theme_btn = QPushButton()
        self.theme_btn.setIcon(self.get_icon("preferences-desktop-theme"))
        self.theme_btn.setIconSize(QSize(20, 20))
        self.theme_btn.setFixedSize(32, 32)
        self.theme_btn.setToolTip("Configuración del Panel")
        self.theme_btn.setStyleSheet("border: none; background: transparent;")
        self.theme_btn.clicked.connect(self.open_panel_settings)  # <-- Cambia aquí
        left_layout.addWidget(self.theme_btn)

        fondo_layout.addLayout(left_layout, 1)

        # === DERECHA: Accesos directos ===
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        for name, icon, action in self.SHORTCUTS:
            btn = QPushButton(name)
            btn.setIcon(self.get_icon(icon))
            btn.setIconSize(QSize(28, 28))
            btn.setStyleSheet("""
                background: transparent;
                text-align: left;
                padding: 8px;
                font-size: 13px;
                border: none;
            """)
            btn.clicked.connect(lambda checked, act=action: self.launch_shortcut(act))
            right_layout.addWidget(btn)
        right_layout.addStretch()
        fondo_layout.addWidget(right_widget, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(fondo)

        self.showing_favorites = True

    def show_theme_menu(self):
        menu = QMenu(self)
        claro = menu.addAction("Tema claro")
        oscuro = menu.addAction("Tema oscuro")
        sistema = menu.addAction("Tema del sistema")
        claro.triggered.connect(lambda: self.set_theme("claro"))
        oscuro.triggered.connect(lambda: self.set_theme("oscuro"))
        sistema.triggered.connect(lambda: self.set_theme("sistema"))
        menu.exec(self.theme_btn.mapToGlobal(self.theme_btn.rect().bottomLeft()))

    def set_theme(self, theme_name):
        self.theme = theme_name
        self.apply_theme(theme_name)
        self.save_theme(theme_name)

    def apply_theme(self, theme_name):
        css_file = self.THEMES.get(theme_name)
        if css_file:
            css_path = os.path.join(os.path.dirname(__file__), css_file)
            if os.path.exists(css_path):
                with open(css_path, "r") as f:
                    self.setStyleSheet(f.read())
        else:
            # Forzar fondo claro y texto oscuro para evitar transparencia
            self.setStyleSheet("""
                QWidget#MenuFondo {
                    background: #f2f2f2;
                    border-radius: 10px;
                    border: 1px solid #b0b0b0;
                    color: #222;
                }
                QListWidget, QScrollArea, QLineEdit, QPushButton {
                    color: #222;
                }
            """)

    def save_theme(self, theme_name):
        try:
            os.makedirs(os.path.dirname(self.THEME_FILE), exist_ok=True)
            with open(self.THEME_FILE, "w") as f:
                json.dump({"theme": theme_name}, f)
        except Exception as e:
            print("No se pudo guardar el tema:", e)

    def load_theme(self):
        try:
            if os.path.exists(self.THEME_FILE):
                with open(self.THEME_FILE, "r") as f:
                    data = json.load(f)
                    return data.get("theme", "claro")
        except Exception:
            pass
        return "claro"

    def load_favorites(self):
        try:
            if os.path.exists(self.FAVORITES_FILE):
                with open(self.FAVORITES_FILE, "r") as f:
                    self.favorites = json.load(f)
            else:
                self.favorites = self.DEFAULT_FAVORITES.copy()
        except Exception:
            self.favorites = self.DEFAULT_FAVORITES.copy()

    def save_favorites(self):
        try:
            os.makedirs(os.path.dirname(self.FAVORITES_FILE), exist_ok=True)
            with open(self.FAVORITES_FILE, "w") as f:
                json.dump(self.favorites, f)
        except Exception as e:
            print("No se pudo guardar favoritos:", e)

    def load_applications(self):
        """Cargar aplicaciones del sistema desde archivos .desktop"""
        self.applications = []
        import configparser
        desktop_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications")
        ]
        for d in desktop_dirs:
            if os.path.isdir(d):
                for fname in os.listdir(d):
                    if fname.endswith(".desktop"):
                        path = os.path.join(d, fname)
                        config = configparser.ConfigParser(interpolation=None)
                        try:
                            config.read(path, encoding="utf-8")
                            if "Desktop Entry" in config:
                                entry = config["Desktop Entry"]
                                if entry.get("NoDisplay", "false").lower() == "true":
                                    continue
                                name = entry.get("Name")
                                exec_cmd = entry.get("Exec")
                                icon = entry.get("Icon", "")
                                if name and exec_cmd:
                                    exec_cmd_clean = exec_cmd.split()[0]
                                    self.applications.append((name, exec_cmd_clean, icon))
                        except Exception:
                            continue

    def show_favorites(self):
        self.left_list.clear()
        for name, command, icon in self.favorites:
            item = QListWidgetItem(self.get_icon(icon), name)
            item.setData(Qt.ItemDataRole.UserRole, (name, command, icon))
            self.left_list.addItem(item)
        self.showing_favorites = True
        self.todas_btn.setText("Todas las aplicaciones")

    def show_all_apps(self):
        self.left_list.clear()
        for name, command, icon in sorted(self.applications):
            item = QListWidgetItem(self.get_icon(icon), name)
            item.setData(Qt.ItemDataRole.UserRole, (name, command, icon))
            self.left_list.addItem(item)
        self.showing_favorites = False
        self.todas_btn.setText("Favoritos")

    def toggle_left_list(self):
        if self.showing_favorites:
            self.show_all_apps()
        else:
            self.show_favorites()

    def launch_left_item(self, item):
        name, command, icon = item.data(Qt.ItemDataRole.UserRole)
        self.launch_command(command)

    def left_context_menu(self, pos):
        item = self.left_list.itemAt(pos)
        menu = QMenu(self)
        if self.showing_favorites:
            if item:
                remove_action = menu.addAction("Quitar de favoritos")
                remove_action.triggered.connect(lambda: self.remove_favorite(item))
        else:
            if item:
                add_action = menu.addAction("Agregar a favoritos")
                add_action.triggered.connect(lambda: self.add_favorite(item))
        if menu.actions():
            menu.exec(self.left_list.mapToGlobal(pos))

    def add_favorite(self, item):
        fav = item.data(Qt.ItemDataRole.UserRole)
        if fav not in self.favorites:
            self.favorites.append(fav)
            self.save_favorites()
            QMessageBox.information(self, "Favoritos", f"{fav[0]} agregado a favoritos.")

    def remove_favorite(self, item):
        fav = item.data(Qt.ItemDataRole.UserRole)
        self.favorites = [f for f in self.favorites if f != fav]
        self.save_favorites()
        self.show_favorites()

    def launch_command(self, command):
        if command == "settings":
            if self.parent:
                self.parent.show_settings()
        elif command == "store":
            subprocess.Popen(["xdg-open", "https://flathub.org/"])
        elif command == "terminal":
            terminals = ['xfce4-terminal', 'gnome-terminal', 'konsole', 'xterm', 'alacritty']
            for terminal in terminals:
                try:
                    subprocess.Popen([terminal])
                    break
                except FileNotFoundError:
                    continue
        elif os.path.isdir(command):
            subprocess.Popen(['xdg-open', command])
        else:
            try:
                subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo lanzar: {command}\n{e}")
        self.hide()

    def launch_shortcut(self, action):
        self.launch_command(action)

    def get_icon(self, icon_name):
        if hasattr(QIcon, 'fromTheme'):
            icon = QIcon.fromTheme(icon_name)
            if not icon.isNull():
                return icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(180, 200, 230))
        return QIcon(pixmap)

    def open_panel_settings(self):
        """Abrir la ventana de configuración del panel"""
        if self.parent:
            self.parent.show_settings()

class WindowButton(QPushButton):
    """Botón para ventana en la barra de tareas"""
    
    def __init__(self, window_id, window_title, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self.window_title = window_title
        self.setToolTip(window_title)
        self.setText("")
        self.setFixedSize(36, 36)
        self.clicked.connect(self.focus_window)
        # Intentar obtener el icono de la ventana usando xprop y xdg-icon-resource
        icon = self.get_window_icon()
        if icon:
            self.setIcon(icon)
        else:
            self.setIcon(QIcon.fromTheme("application-x-executable"))
        self.setIconSize(QSize(24, 24))
        self.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                border: 1px solid #666;
                border-radius: 5px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
        """)

    def get_window_icon(self):
        # Intenta obtener el icono de la ventana usando xprop y ambos valores de WM_CLASS
        try:
            output = subprocess.check_output([
                'xprop', '-id', self.window_id, 'WM_CLASS'
            ], stderr=subprocess.DEVNULL).decode()
            # WM_CLASS(STRING) = "Navigator", "firefox"
            if 'WM_CLASS' in output:
                parts = output.strip().split('=')[-1].split(',')
                class_names = [p.replace('"', '').strip() for p in parts]
                # Probar ambos valores de WM_CLASS
                for name in reversed(class_names):  # Prioriza el segundo
                    icon = QIcon.fromTheme(name)
                    if not icon.isNull():
                        return icon
        except Exception:
            pass
        return None
    
    def focus_window(self):
        """Alternar minimizar/restaurar ventana"""
        try:
            # Primero intentar obtener el estado de la ventana
            window_state = subprocess.check_output(
                ['xprop', '-id', self.window_id, '_NET_WM_STATE'],
                stderr=subprocess.DEVNULL
            ).decode()
            
            # Convertir el ID de la ventana al formato decimal
            window_id_dec = str(int(self.window_id, 16))
            
            # Verificar si la ventana está minimizada
            is_minimized = '_NET_WM_STATE_HIDDEN' in window_state
            
            if not is_minimized:
                # La ventana está visible, intentar minimizarla
                try:
                    subprocess.run(['xdotool', 'windowminimize', window_id_dec],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    # Si xdotool falla, intentar con wmctrl
                    try:
                        subprocess.run(['wmctrl', '-ir', self.window_id, '-b', 'add,hidden'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"Error minimizando ventana: {e}")
            else:
                # La ventana está minimizada, restaurarla y activarla
                try:
                    # Primero intentar con xdotool
                    subprocess.run(['xdotool', 'windowactivate', window_id_dec],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    # Si falla, intentar con wmctrl
                    try:
                        subprocess.run(['wmctrl', '-i', '-a', self.window_id],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"Error restaurando ventana: {e}")
        
        except Exception as e:
            # Si todo lo anterior falla, intentar simplemente activar la ventana
            try:
                subprocess.run(['wmctrl', '-i', '-a', self.window_id],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                print(f"Error manejando ventana: {e}")

class DesktopPanel(QMainWindow):


    def open_network_settings(self):
        """Abrir la configuración de red del sistema"""
        try:
            # Intentar varios comandos comunes para abrir la configuración de red
            # Obtener el DISPLAY actual
            display = os.environ.get('DISPLAY', ':0')
            
            # Preparar el ambiente para el proceso
            env = os.environ.copy()
            env['DISPLAY'] = display
            
            # Lista de comandos con sus wrappers de privilegios
            commands = [
                ["pkexec", "--user", os.environ.get('USER', 'root'), "env", f"DISPLAY={display}", "nm-connection-editor"],  # NetworkManager con pkexec
                ["nm-connection-editor"],  # NetworkManager sin privilegios
                ["gnome-control-center", "network"],  # GNOME
                ["systemsettings5", "kcm_networkmanagement"],  # KDE
                ["xfce4-network-settings"]  # XFCE
            ]
            
            for cmd in commands:
                try:
                    # Verificar si el comando principal existe
                    main_cmd = cmd[-1] if cmd[0] == "pkexec" else cmd[0]
                    if subprocess.run(["which", main_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                        subprocess.Popen(cmd, env=env)
                        return
                except Exception as e:
                    print(f"Error al ejecutar {cmd}: {str(e)}")
                    continue
            # Si ninguno funciona, mostrar un mensaje
            QMessageBox.warning(self, "Error", "No se pudo abrir la configuración de red")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al abrir la configuración de red: {str(e)}")

    def get_volume_info(self):
        """Obtener información del volumen usando pactl o amixer"""
        try:
            # Intentar primero con PulseAudio (pactl)
            output = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], 
                                          universal_newlines=True)
            volume = int(output.split()[4].rstrip('%'))
            
            # Verificar si está muteado
            mute_output = subprocess.check_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], 
                                                universal_newlines=True)
            muted = "yes" in mute_output.lower()
            
            return volume, muted
        except:
            try:
                # Fallback a ALSA (amixer)
                output = subprocess.check_output(["amixer", "get", "Master"], 
                                              universal_newlines=True)
                volume = int(output.split()[-2].strip('[]%'))
                muted = "off" in output.lower()
                return volume, muted
            except:
                return 0, True

    def get_battery_info(self):
        """Obtener información detallada de la batería"""
        try:
            if not PSUTIL_AVAILABLE:
                return None

            battery = psutil.sensors_battery()
            if battery is None:
                return None

            # Obtener información adicional del sistema
            power_supply_path = "/sys/class/power_supply"
            bat_path = None
            
            # Buscar la batería en el sistema
            for path in os.listdir(power_supply_path):
                if path.startswith("BAT"):
                    bat_path = os.path.join(power_supply_path, path)
                    break
            
            if bat_path:
                # Leer información adicional
                try:
                    with open(os.path.join(bat_path, "manufacturer"), 'r') as f:
                        manufacturer = f.read().strip()
                except:
                    manufacturer = "Desconocido"
                
                try:
                    with open(os.path.join(bat_path, "model_name"), 'r') as f:
                        model = f.read().strip()
                except:
                    model = "Batería"
                
                try:
                    with open(os.path.join(bat_path, "cycle_count"), 'r') as f:
                        cycles = int(f.read().strip())
                except:
                    cycles = 0
            else:
                manufacturer = "Desconocido"
                model = "Batería"
                cycles = 0

            return {
                'percent': battery.percent,
                'power_plugged': battery.power_plugged,
                'time_left': battery.secsleft if battery.secsleft > 0 else None,
                'manufacturer': manufacturer,
                'model': model,
                'cycles': cycles
            }
        except:
            return None

    def format_time(self, seconds):
        """Formatear tiempo en segundos a formato legible"""
        if seconds < 0:
            return "Calculando..."
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def update_battery_status(self):
        """Actualizar el ícono y estado de la batería"""
        info = self.get_battery_info()
        
        if info is None:
            # No hay batería o no se puede detectar
            icon = QIcon.fromTheme("ac-adapter")
            if icon.isNull():
                self.battery_button.setText("🔌")
            else:
                self.battery_button.setIcon(icon)
                self.battery_button.setIconSize(QSize(22, 22))
            self.battery_button.setToolTip("Sin batería detectada")
            return

        # Seleccionar ícono basado en el estado
        icon_name = "battery"
        if info['power_plugged']:
            if info['percent'] >= 99:
                icon_name = "battery-full-charged"
            else:
                icon_name = "battery-full-charging"
        else:
            if info['percent'] <= 20:
                icon_name = "battery-caution"
            elif info['percent'] <= 40:
                icon_name = "battery-low"
            elif info['percent'] <= 80:
                icon_name = "battery-good"
            else:
                icon_name = "battery-full"

        icon = QIcon.fromTheme(icon_name)
        if icon.isNull():
            # Fallback a emojis
            if info['power_plugged']:
                self.battery_button.setText("🔌")
            else:
                battery_icons = ["🪫", "🔋", "🔋", "🔋", "🔋"]  # 0-20, 20-40, 40-60, 60-80, 80-100
                idx = min(4, info['percent'] // 20)
                self.battery_button.setText(battery_icons[idx])
        else:
            self.battery_button.setIcon(icon)
            self.battery_button.setIconSize(QSize(22, 22))

        # Actualizar tooltip
        status = "Cargando" if info['power_plugged'] else "Descargando"
        if info['time_left'] and not info['power_plugged']:
            time_left = self.format_time(info['time_left'])
            tooltip = f"{info['percent']}% - {time_left} restantes"
        else:
            tooltip = f"{info['percent']}% - {status}"
        self.battery_button.setToolTip(tooltip)

    def show_battery_menu(self):
        """Mostrar menú detallado de la batería"""
        info = self.get_battery_info()
        if info is None:
            QMessageBox.information(self, "Estado de la Batería", "No se detectó ninguna batería en el sistema.")
            return

        menu = QMenu(self)
        
        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Encabezado con ícono y porcentaje
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 8)

        # Ícono grande de batería
        icon_label = QLabel()
        icon = QIcon.fromTheme("battery")
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)

        # Información principal
        percent_label = QLabel(f"{info['percent']}%")
        percent_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333333;")
        header_layout.addWidget(percent_label)
        
        status_label = QLabel("Conectado" if info['power_plugged'] else "Usando batería")
        status_label.setStyleSheet("color: #666666;")
        header_layout.addWidget(status_label)
        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        # Contenedor de información con fondo estilizado
        info_container = QWidget()
        info_container.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: #333333;
                padding: 4px;
            }
        """)
        info_layout = QVBoxLayout(info_container)
        
        # Detalles de la batería
        if info['time_left'] and not info['power_plugged']:
            time_left = self.format_time(info['time_left'])
            info_layout.addWidget(QLabel(f"Tiempo restante: {time_left}"))

        info_layout.addWidget(QLabel(f"Fabricante: {info['manufacturer']}"))
        info_layout.addWidget(QLabel(f"Modelo: {info['model']}"))
        if info['cycles'] > 0:
            info_layout.addWidget(QLabel(f"Ciclos de carga: {info['cycles']}"))

        main_layout.addWidget(info_container)

        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.1); margin: 4px 0;")
        main_layout.addWidget(separator)

        # Botón de configuración de energía
        power_button = QPushButton(QIcon.fromTheme("preferences-system-power"), " Configuración de energía")
        power_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px;
                text-align: left;
                color: #333333;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
        """)
        power_button.clicked.connect(self.open_power_settings)
        main_layout.addWidget(power_button)

        # Aplicar el widget al menú
        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        # Estilo del menú
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        # Timer para actualización en tiempo real
        timer = QTimer(menu)
        timer.timeout.connect(lambda: (
            self.update_battery_status(),
            percent_label.setText(f"{self.get_battery_info()['percent']}%"),
            status_label.setText("Conectado" if self.get_battery_info()['power_plugged'] else "Usando batería")
        ))
        timer.start(1000)
        menu.aboutToHide.connect(timer.stop)

        # Mostrar el menú justo fuera del panel, no sobre él
        position = self.settings.get('position', 'top')
        btn_rect = self.battery_button.rect()
        menu_size = menu.sizeHint()
        if position == 'top':
            pos = self.battery_button.mapToGlobal(btn_rect.bottomLeft())
            pos.setY(pos.y() + self.battery_button.height())
        elif position == 'bottom':
            pos = self.battery_button.mapToGlobal(btn_rect.topLeft())
            pos.setY(pos.y() - menu_size.height())
        elif position == 'left':
            pos = self.battery_button.mapToGlobal(btn_rect.topRight())
        elif position == 'right':
            pos = self.battery_button.mapToGlobal(btn_rect.topLeft())
            pos.setX(pos.x() - menu_size.width())
        else:
            pos = self.battery_button.mapToGlobal(btn_rect.bottomLeft())
        menu.exec(pos)

    def get_storage_devices(self):
        """Obtener lista de dispositivos de almacenamiento externos"""
        devices = []
        try:
            # Obtener información de lsblk en formato JSON
            output = subprocess.check_output([
                'lsblk', '-Jpo', 'NAME,LABEL,TYPE,SIZE,MOUNTPOINT,VENDOR,MODEL,HOTPLUG,RM,TRAN'
            ], universal_newlines=True)
            
            data = json.loads(output)
            if 'blockdevices' in data:
                for device in data['blockdevices']:
                    # Verificar si es un dispositivo de almacenamiento externo
                    if (device.get('type') in ['disk', 'part'] and 
                        (device.get('rm') == '1' or  # Removible
                         device.get('hotplug') == '1' or  # Hot-plug
                         device.get('tran') == 'usb') and  # USB
                        device.get('mountpoint')):  # Está montado
                        
                        # Obtener nombre descriptivo
                        name = device.get('label', '')
                        if not name:
                            vendor = device.get('vendor', '').strip()
                            model = device.get('model', '').strip()
                            if vendor or model:
                                name = f"{vendor} {model}".strip()
                            else:
                                name = os.path.basename(device['mountpoint'])
                        
                        # Agregar dispositivo a la lista
                        devices.append({
                            'name': name,
                            'path': device['name'],
                            'size': device.get('size', 'Desconocido'),
                            'mountpoint': device['mountpoint'],
                            'vendor': device.get('vendor', ''),
                            'model': device.get('model', '')
                        })
        except Exception as e:
            print(f"Error al obtener dispositivos de almacenamiento: {str(e)}")
        
        return devices

    def update_storage_status(self):
        """Actualizar el ícono y estado de los dispositivos de almacenamiento"""
        devices = self.get_storage_devices()
        
        if devices:
            # Usar ícono de dispositivo USB si está disponible
            icon = QIcon.fromTheme("drive-removable-media-usb")
            if icon.isNull():
                icon = QIcon.fromTheme("drive-removable-media")
            tooltip = f"{len(devices)} dispositivo{'s' if len(devices) != 1 else ''} conectado{'s' if len(devices) != 1 else ''}"
        else:
            icon = QIcon.fromTheme("drive-removable-media-symbolic")
            tooltip = "No hay dispositivos conectados"

        if icon.isNull():
            # Fallback a emoji si no hay íconos disponibles
            self.storage_button.setText("💾")
        else:
            self.storage_button.setIcon(icon)
            self.storage_button.setIconSize(QSize(22, 22))
        
        self.storage_button.setToolTip(tooltip)

    def show_storage_menu(self):
        """Mostrar menú de dispositivos de almacenamiento"""
        devices = self.get_storage_devices()
        menu = QMenu(self)

        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Título
        header = QLabel("Dispositivos de Almacenamiento")
        header.setStyleSheet("font-weight: bold; color: #333333; font-size: 14px;")
        main_layout.addWidget(header)

        if devices:
            # Contenedor con scroll
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setMaximumHeight(300)

            devices_widget = QWidget()
            devices_layout = QVBoxLayout(devices_widget)
            devices_layout.setSpacing(4)
            devices_layout.setContentsMargins(0, 0, 0, 0)

            for device in devices:
                # Contenedor para cada dispositivo
                device_widget = QWidget()
                device_widget.setStyleSheet("""
                    QWidget {
                        background: rgba(0, 0, 0, 0.05);
                        border-radius: 8px;
                        padding: 8px;
                    }
                    QWidget:hover {
                        background: rgba(0, 0, 0, 0.08);
                    }
                """)
                device_layout = QVBoxLayout(device_widget)
                device_layout.setSpacing(4)
                device_layout.setContentsMargins(8, 8, 8, 8)

                # Nombre y tamaño
                name_label = QLabel(f"<b>{device['name']}</b>")
                name_label.setStyleSheet("color: #333333;")
                device_layout.addWidget(name_label)

                size_label = QLabel(f"Tamaño: {device['size']}")
                size_label.setStyleSheet("color: #666666; font-size: 11px;")
                device_layout.addWidget(size_label)

                # Botones de acción
                buttons_widget = QWidget()
                buttons_layout = QHBoxLayout(buttons_widget)
                buttons_layout.setContentsMargins(0, 4, 0, 0)
                buttons_layout.setSpacing(4)

                # Botón Abrir
                open_btn = QPushButton(QIcon.fromTheme("folder"), "Abrir")
                open_btn.setStyleSheet("""
                    QPushButton {
                        background: #3daee9;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: #2196F3;
                    }
                """)
                open_btn.clicked.connect(
                    lambda checked, path=device['mountpoint']: 
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                )
                buttons_layout.addWidget(open_btn)

                # Botón Expulsar
                eject_btn = QPushButton(QIcon.fromTheme("media-eject"), "Expulsar")
                eject_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #333333;
                        border: 1px solid #cccccc;
                        border-radius: 4px;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(0, 0, 0, 0.05);
                    }
                """)
                eject_btn.clicked.connect(
                    lambda checked, path=device['path']: 
                    self.eject_device(path)
                )
                buttons_layout.addWidget(eject_btn)

                device_layout.addWidget(buttons_widget)
                devices_layout.addWidget(device_widget)

            scroll.setWidget(devices_widget)
            main_layout.addWidget(scroll)
        else:
            # Mensaje cuando no hay dispositivos
            no_devices = QLabel("No hay dispositivos de almacenamiento conectados")
            no_devices.setStyleSheet("color: #666666; padding: 20px;")
            no_devices.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(no_devices)

        # Aplicar el widget al menú
        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        # Estilo del menú
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        # Timer para actualización en tiempo real
        timer = QTimer(menu)
        timer.timeout.connect(self.update_storage_status)
        timer.start(2000)
        menu.aboutToHide.connect(timer.stop)

        # Mostrar el menú justo fuera del panel, no sobre él
        position = self.settings.get('position', 'top')
        btn_rect = self.storage_button.rect()
        menu_size = menu.sizeHint()
        if position == 'top':
            pos = self.storage_button.mapToGlobal(btn_rect.bottomLeft())
            pos.setY(pos.y() + self.storage_button.height())
        elif position == 'bottom':
            pos = self.storage_button.mapToGlobal(btn_rect.topLeft())
            pos.setY(pos.y() - menu_size.height())
        elif position == 'left':
            pos = self.storage_button.mapToGlobal(btn_rect.topRight())
        elif position == 'right':
            pos = self.storage_button.mapToGlobal(btn_rect.topLeft())
            pos.setX(pos.x() - menu_size.width())
        else:
            pos = self.storage_button.mapToGlobal(btn_rect.bottomLeft())
        menu.exec(pos)

    def get_bluetooth_status(self):
        """Obtener el estado del Bluetooth y dispositivos conectados"""
        try:
            # Verificar si bluetoothctl está disponible
            if subprocess.run(['which', 'bluetoothctl'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode != 0:
                return {'error': 'bluetoothctl no está instalado'}

            # Obtener estado del controlador
            controller_info = subprocess.check_output(['bluetoothctl', 'show'], universal_newlines=True)
            powered = 'Powered: yes' in controller_info
            
            if not powered:
                return {'powered': False, 'devices': []}

            # Obtener dispositivos conectados
            devices = []
            paired_devices = subprocess.check_output(['bluetoothctl', 'paired-devices'], universal_newlines=True)
            for line in paired_devices.splitlines():
                if line.strip():
                    try:
                        dev_id = line.split()[1]
                        dev_name = ' '.join(line.split()[2:])
                        
                        # Obtener información adicional del dispositivo
                        info = subprocess.check_output(['bluetoothctl', 'info', dev_id], universal_newlines=True)
                        connected = 'Connected: yes' in info
                        
                        # Determinar el tipo de dispositivo
                        dev_type = 'other'
                        icon_name = 'bluetooth'
                        
                        if any(kw in dev_name.lower() for kw in ['mouse', 'ratón']):
                            dev_type = 'mouse'
                            icon_name = 'input-mouse'
                        elif any(kw in dev_name.lower() for kw in ['keyboard', 'teclado']):
                            dev_type = 'keyboard'
                            icon_name = 'input-keyboard'
                        elif any(kw in dev_name.lower() for kw in ['headset', 'headphone', 'auricular', 'speaker']):
                            dev_type = 'audio'
                            icon_name = 'audio-headset'
                        elif any(kw in dev_name.lower() for kw in ['phone', 'móvil', 'android', 'iphone']):
                            dev_type = 'phone'
                            icon_name = 'phone'
                        
                        devices.append({
                            'id': dev_id,
                            'name': dev_name,
                            'connected': connected,
                            'type': dev_type,
                            'icon': icon_name
                        })
                        
                    except Exception as e:
                        print(f"Error al procesar dispositivo Bluetooth: {str(e)}")

            return {
                'powered': True,
                'devices': devices
            }
            
        except Exception as e:
            return {'error': str(e)}

    def update_bluetooth_status(self):
        """Actualizar el ícono y estado del Bluetooth"""
        status = self.get_bluetooth_status()
        
        if 'error' in status:
            icon = QIcon.fromTheme("bluetooth-disabled")
            tooltip = "Bluetooth no disponible"
        elif not status['powered']:
            icon = QIcon.fromTheme("bluetooth-offline")
            tooltip = "Bluetooth desactivado"
        else:
            connected_devices = [d for d in status['devices'] if d['connected']]
            if connected_devices:
                icon = QIcon.fromTheme("bluetooth-active")
                tooltip = f"{len(connected_devices)} dispositivo{'s' if len(connected_devices) != 1 else ''} conectado{'s' if len(connected_devices) != 1 else ''}"
            else:
                icon = QIcon.fromTheme("bluetooth")
                tooltip = "Bluetooth activado"

        if icon.isNull():
            # Fallback a emoji
            if 'error' in status or not status['powered']:
                self.bluetooth_button.setText("📵")
            else:
                self.bluetooth_button.setText("📶")
        else:
            self.bluetooth_button.setIcon(icon)
            self.bluetooth_button.setIconSize(QSize(22, 22))
        
        self.bluetooth_button.setToolTip(tooltip)

    def toggle_bluetooth(self, enable=None):
        """Activar/desactivar Bluetooth"""
        try:
            if enable is None:
                # Toggle actual state
                current_status = self.get_bluetooth_status()
                enable = not current_status.get('powered', False)

            cmd = 'power on' if enable else 'power off'
            subprocess.run(['bluetoothctl', cmd], check=True)
            self.update_bluetooth_status()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cambiar estado del Bluetooth: {str(e)}")

    def connect_bluetooth_device(self, device_id):
        """Conectar a un dispositivo Bluetooth"""
        try:
            subprocess.run(['bluetoothctl', 'connect', device_id], check=True)
            self.update_bluetooth_status()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al conectar dispositivo: {str(e)}")

    def disconnect_bluetooth_device(self, device_id):
        """Desconectar un dispositivo Bluetooth"""
        try:
            subprocess.run(['bluetoothctl', 'disconnect', device_id], check=True)
            self.update_bluetooth_status()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al desconectar dispositivo: {str(e)}")

    def show_notifications_menu(self):
        """Mostrar menú del centro de notificaciones"""
        print(f"Mostrando menú de notificaciones. Total: {len(self.notifications)}")  # Debug
        menu = QMenu(self)
        self.notification_menu = menu  # Guardar referencia para poder cerrarlo
        
        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Título y botón de limpiar todo
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Centro de Notificaciones")
        title.setStyleSheet("font-weight: bold; color: #333333; font-size: 14px;")
        header_layout.addWidget(title)

        if self.notifications:
            clear_all_btn = QPushButton("Limpiar todo")
            clear_all_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #666;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(0, 0, 0, 0.1);
                    border-radius: 4px;
                }
            """)
            clear_all_btn.clicked.connect(self.clear_all_notifications)
            header_layout.addWidget(clear_all_btn)

        main_layout.addWidget(header_widget)

        # Scroll area para notificaciones
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        if self.notifications:
            for idx, notif in enumerate(self.notifications[:10]):
                # Contenedor para cada notificación
                notif_widget = QWidget()
                notif_widget.setMinimumHeight(50)  # Altura mínima para cada notificación
                notif_widget.setStyleSheet("""
                    QWidget {
                        background: rgba(0, 0, 0, 0.05);
                        border-radius: 8px;
                        padding: 8px;
                        margin: 2px 0;
                    }
                """)
                notif_layout = QVBoxLayout(notif_widget)
                notif_layout.setSpacing(4)

                # Encabezado: App + Timestamp + Botón cerrar
                header_widget = QWidget()
                header_layout = QHBoxLayout(header_widget)
                header_layout.setContentsMargins(0, 0, 0, 0)

                app_label = QLabel(f"<b>{notif.app_name}</b>")
                header_layout.addWidget(app_label)

                time_label = QLabel(notif.timestamp.strftime("%H:%M"))
                time_label.setStyleSheet("color: #666;")
                header_layout.addWidget(time_label)

                close_btn = QPushButton("×")
                close_btn.setFixedSize(24, 24)
                close_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                        font-size: 16px;
                        font-weight: bold;
                        color: #666;
                    }
                    QPushButton:hover {
                        background: rgba(0, 0, 0, 0.1);
                        border-radius: 4px;
                        color: #333;
                    }
                """)
                close_btn.clicked.connect(lambda checked, i=idx: self.remove_notification(i))
                header_layout.addWidget(close_btn)

                notif_layout.addWidget(header_widget)

                # Título
                if notif.summary:
                    summary_label = QLabel(f"<b>{notif.summary}</b>")
                    notif_layout.addWidget(summary_label)

                # Contenido
                if notif.body:
                    body_label = QLabel(notif.body)
                    body_label.setWordWrap(True)
                    notif_layout.addWidget(body_label)

                scroll_layout.addWidget(notif_widget)
        else:
            empty_label = QLabel("No hay notificaciones")
            empty_label.setStyleSheet("color: #666; padding: 20px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(empty_label)

        # Crear scroll area
        # Crear scroll area
        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumWidth(350)  # Un poco más ancho para mejor legibilidad
        
        # Calcular altura basada en el contenido
        screen = QApplication.primaryScreen().geometry()
        content_height = scroll_widget.sizeHint().height()
        max_height = screen.height() * 0.7  # 70% de la altura de la pantalla
        
        # Si el contenido es menor que el máximo, usar el tamaño del contenido
        if content_height < max_height:
            scroll.setMaximumHeight(content_height + 30)  # +30 para margen
        else:
            scroll.setMaximumHeight(int(max_height))
            
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(0, 0, 0, 0.1);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.3);
            }
        """)

        # Configuración
        settings_btn = QPushButton("Configuración de notificaciones")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                color: #333333;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        settings_btn.clicked.connect(self.show_notification_settings)
        main_layout.addWidget(settings_btn)

        # Aplicar el widget al menú
        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        # Estilo del menú
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        # Calcular posición del menú
        button_pos = self.notification_button.mapToGlobal(self.notification_button.rect().topLeft())
        menu_x = button_pos.x() - menu.sizeHint().width() + self.notification_button.width()
        
        # Si el panel está en la parte superior, mostrar abajo
        if self.y() == 0:
            menu_y = self.height()
        else:
            # Si el panel está en la parte inferior, mostrar arriba
            menu_y = button_pos.y() - menu.sizeHint().height()
        
        menu.exec(QPoint(menu_x, menu_y))

    def show_notification_settings(self):
        """Mostrar configuración de notificaciones"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuración de Notificaciones")
        layout = QVBoxLayout(dialog)

        # Opciones
        show_popup = QCheckBox("Mostrar notificaciones emergentes")
        show_popup.setChecked(True)
        layout.addWidget(show_popup)

        play_sound = QCheckBox("Reproducir sonido")
        play_sound.setChecked(True)
        layout.addWidget(play_sound)

        # Duración
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duración:"))
        duration_combo = QComboBox()
        duration_combo.addItems(["3 segundos", "5 segundos", "10 segundos"])
        duration_combo.setCurrentText("5 segundos")
        duration_layout.addWidget(duration_combo)
        layout.addLayout(duration_layout)

        # Botones
        buttons = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        dialog.setStyleSheet("""
            QDialog {
                background: white;
            }
            QPushButton {
                background: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 20px;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
            QCheckBox {
                spacing: 8px;
                color: #333;
            }
            QComboBox {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
            }
        """)

        dialog.exec()

    def show_bluetooth_menu(self):
        """Mostrar menú de Bluetooth"""
        menu = QMenu(self)
        
        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Estado actual
        status = self.get_bluetooth_status()

        # Encabezado con switch de poder
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 8)

        header_label = QLabel("Bluetooth")
        header_label.setStyleSheet("font-weight: bold; color: #333333; font-size: 14px;")
        header_layout.addWidget(header_label)

        power_btn = QPushButton()
        if 'error' in status:
            power_btn.setText("No disponible")
            power_btn.setEnabled(False)
        else:
            power_btn.setText("Activado" if status.get('powered', False) else "Desactivado")
            power_btn.setCheckable(True)
            power_btn.setChecked(status.get('powered', False))
            power_btn.clicked.connect(lambda: self.toggle_bluetooth(power_btn.isChecked()))
        
        power_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px 8px;
                color: #333333;
            }
            QPushButton:checked {
                background: #3daee9;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background: #2196F3;
                color: white;
            }
        """)
        header_layout.addWidget(power_btn)
        main_layout.addWidget(header_widget)

        if not 'error' in status and status.get('powered', False):
            devices = status.get('devices', [])
            if devices:
                # Contenedor con scroll
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setMaximumHeight(300)

                devices_widget = QWidget()
                devices_layout = QVBoxLayout(devices_widget)
                devices_layout.setSpacing(4)
                devices_layout.setContentsMargins(0, 0, 0, 0)

                for device in devices:
                    # Contenedor para cada dispositivo
                    device_widget = QWidget()
                    device_widget.setStyleSheet("""
                        QWidget {
                            background: rgba(0, 0, 0, 0.05);
                            border-radius: 8px;
                            padding: 8px;
                        }
                        QWidget:hover {
                            background: rgba(0, 0, 0, 0.08);
                        }
                    """)
                    device_layout = QHBoxLayout(device_widget)
                    device_layout.setSpacing(8)
                    device_layout.setContentsMargins(8, 8, 8, 8)

                    # Ícono del dispositivo
                    icon_label = QLabel()
                    icon = QIcon.fromTheme(device['icon'])
                    if not icon.isNull():
                        icon_label.setPixmap(icon.pixmap(24, 24))
                    device_layout.addWidget(icon_label)

                    # Información del dispositivo
                    info_widget = QWidget()
                    info_layout = QVBoxLayout(info_widget)
                    info_layout.setSpacing(0)
                    info_layout.setContentsMargins(0, 0, 0, 0)

                    name_label = QLabel(device['name'])
                    name_label.setStyleSheet("font-weight: bold; color: #333333;")
                    info_layout.addWidget(name_label)

                    status_label = QLabel("Conectado" if device['connected'] else "Desconectado")
                    status_label.setStyleSheet("color: #666666; font-size: 11px;")
                    info_layout.addWidget(status_label)

                    device_layout.addWidget(info_widget)
                    device_layout.addStretch()

                    # Botón de conexión/desconexión
                    connect_btn = QPushButton()
                    if device['connected']:
                        connect_btn.setText("Desconectar")
                        connect_btn.clicked.connect(
                            lambda checked, dev_id=device['id']: 
                            self.disconnect_bluetooth_device(dev_id)
                        )
                    else:
                        connect_btn.setText("Conectar")
                        connect_btn.clicked.connect(
                            lambda checked, dev_id=device['id']: 
                            self.connect_bluetooth_device(dev_id)
                        )
                    
                    connect_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                            border: 1px solid #cccccc;
                            border-radius: 4px;
                            padding: 4px 8px;
                            color: #333333;
                        }
                        QPushButton:hover {
                            background: rgba(0, 0, 0, 0.05);
                        }
                    """)
                    device_layout.addWidget(connect_btn)

                    devices_layout.addWidget(device_widget)

                scroll.setWidget(devices_widget)
                main_layout.addWidget(scroll)
            else:
                no_devices = QLabel("No hay dispositivos vinculados")
                no_devices.setStyleSheet("color: #666666; padding: 20px;")
                no_devices.setAlignment(Qt.AlignmentFlag.AlignCenter)
                main_layout.addWidget(no_devices)

        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.1); margin: 4px 0;")
        main_layout.addWidget(separator)

        # Botón de configuración
        settings_btn = QPushButton(QIcon.fromTheme("preferences-system-bluetooth"), " Configuración de Bluetooth")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px;
                text-align: left;
                color: #333333;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
        """)
        settings_btn.clicked.connect(self.open_bluetooth_settings)
        main_layout.addWidget(settings_btn)

        # Aplicar el widget al menú
        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        # Estilo del menú
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        # Timer para actualización en tiempo real
        timer = QTimer(menu)
        timer.timeout.connect(self.update_bluetooth_status)
        timer.start(2000)
        menu.aboutToHide.connect(timer.stop)

        menu.exec(self.bluetooth_button.mapToGlobal(self.bluetooth_button.rect().bottomLeft()))

    def open_bluetooth_settings(self):
        """Abrir la configuración de Bluetooth del sistema"""
        try:
            # Intentar varios comandos comunes para la configuración de Bluetooth
            for cmd in [
                ["gnome-control-center", "bluetooth"],  # GNOME
                ["systemsettings5", "kcm_bluetooth"],  # KDE
                ["blueman-manager"],  # Blueman
                ["blueberry"],  # Cinnamon/MATE
                ["xfce4-settings-manager", "--dialog=bluetooth"]  # XFCE
            ]:
                try:
                    if subprocess.run(["which", cmd[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                        subprocess.Popen(cmd)
                        return
                except:
                    continue
            
            QMessageBox.warning(self, "Error", "No se encontró ningún gestor de Bluetooth instalado")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al abrir la configuración de Bluetooth: {str(e)}")

    def eject_device(self, device_path):
        """Expulsar un dispositivo de forma segura"""
        try:
            # Intentar desmontar usando udisksctl
            subprocess.run(['udisksctl', 'unmount', '-b', device_path], check=True)
            self.update_storage_status()
            QMessageBox.information(self, "Éxito", "El dispositivo se ha expulsado correctamente")
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "Error", f"No se pudo expulsar el dispositivo: {str(e)}")

    def open_power_settings(self):
        """Abrir la configuración de energía del sistema"""
        try:
            # Intentar varios comandos comunes para abrir la configuración de energía
            for cmd in [
                ["gnome-control-center", "power"],  # GNOME
                ["systemsettings5", "kcm_powerdevilprofilesconfig"],  # KDE
                ["xfce4-power-manager-settings"],  # XFCE
                ["mate-power-preferences"],  # MATE
                ["cinnamon-settings", "power"]  # Cinnamon
            ]:
                try:
                    if subprocess.run(["which", cmd[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                        subprocess.Popen(cmd)
                        return
                except:
                    continue
            
            QMessageBox.warning(self, "Error", "No se pudo abrir la configuración de energía")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al abrir la configuración de energía: {str(e)}")

    def update_volume_status(self):
        """Actualizar el ícono de volumen según el estado"""
        volume, muted = self.get_volume_info()
        
        if muted:
            icon = QIcon.fromTheme("audio-volume-muted")
            tooltip = "Audio muteado"
        else:
            if volume > 70:
                icon = QIcon.fromTheme("audio-volume-high")
            elif volume > 30:
                icon = QIcon.fromTheme("audio-volume-medium")
            else:
                icon = QIcon.fromTheme("audio-volume-low")
            tooltip = f"Volumen: {volume}%"

        if icon.isNull():
            # Fallback a emojis si no hay íconos del tema
            if muted:
                self.volume_button.setText("🔇")
            else:
                self.volume_button.setText("🔊")
        else:
            self.volume_button.setIcon(icon)
            self.volume_button.setIconSize(QSize(22, 22))
        
        self.volume_button.setToolTip(tooltip)

    def set_volume(self, volume):
        """Establecer el volumen del sistema"""
        try:
            # Intentar con PulseAudio
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"])
        except:
            try:
                # Fallback a ALSA
                subprocess.run(["amixer", "set", "Master", f"{volume}%"])
            except:
                pass
        self.update_volume_status()

    def toggle_mute(self):
        """Alternar el estado de mute"""
        try:
            # Intentar con PulseAudio
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
        except:
            try:
                # Fallback a ALSA
                subprocess.run(["amixer", "set", "Master", "toggle"])
            except:
                pass
        self.update_volume_status()

    def show_volume_menu(self):
        """Mostrar el menú de control de volumen estilo Cinnamon"""
        menu = QMenu(self)
        volume, muted = self.get_volume_info()

        # Contenedor principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Encabezado con ícono y título
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 8)
        
        volume_icon = QLabel()
        if muted:
            icon = QIcon.fromTheme("audio-volume-muted")
        elif volume > 70:
            icon = QIcon.fromTheme("audio-volume-high")
        elif volume > 30:
            icon = QIcon.fromTheme("audio-volume-medium")
        else:
            icon = QIcon.fromTheme("audio-volume-low")
        volume_icon.setPixmap(icon.pixmap(24, 24))
        header_layout.addWidget(volume_icon)

        volume_label = QLabel(f"Volumen {volume}%")
        volume_label.setStyleSheet("font-weight: bold; color: #333333; font-size: 13px;")
        header_layout.addWidget(volume_label)
        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        # Container para el slider con fondo estilizado
        slider_container = QWidget()
        slider_container.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        slider_layout = QVBoxLayout(slider_container)
        slider_layout.setContentsMargins(8, 8, 8, 8)

        # Slider vertical estilizado
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(volume)
        slider.setFixedHeight(150)
        slider.valueChanged.connect(lambda v: (self.set_volume(v), volume_label.setText(f"Volumen {v}%")))
        slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: #d0d0d0;
                width: 6px;
                border-radius: 3px;
            }
            QSlider::handle:vertical {
                background: #3daee9;
                border: none;
                width: 20px;
                height: 20px;
                margin: 0 -7px;
                border-radius: 10px;
            }
            QSlider::handle:vertical:hover {
                background: #2196F3;
            }
            QSlider::sub-page:vertical {
                background: #3daee9;
                border-radius: 3px;
            }
            QSlider::add-page:vertical {
                background: #d0d0d0;
                border-radius: 3px;
            }
        """)
        slider_layout.addWidget(slider)
        main_layout.addWidget(slider_container)

        # Botón de mute estilizado
        mute_button = QPushButton("🔇 Silenciar" if not muted else "🔊 Activar sonido")
        mute_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px;
                text-align: left;
                color: #333333;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
        """)
        mute_button.clicked.connect(self.toggle_mute)
        main_layout.addWidget(mute_button)

        # Separador estilizado
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.1); margin: 4px 0;")
        main_layout.addWidget(separator)

        # Botón del mezclador estilizado
        mixer_button = QPushButton(QIcon.fromTheme("preferences-system-sound"), " Configuración de sonido")
        mixer_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px;
                text-align: left;
                color: #333333;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
        """)
        mixer_button.clicked.connect(self.open_sound_settings)
        main_layout.addWidget(mixer_button)

        # Aplicar el widget al menú
        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        # Estilo general del menú
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        # Timer para actualizar el estado
        timer = QTimer(menu)
        timer.timeout.connect(self.update_volume_status)
        timer.start(1000)

        menu.aboutToHide.connect(timer.stop)
        # Mostrar el menú justo fuera del panel, no sobre él
        position = self.settings.get('position', 'top')
        btn_rect = self.volume_button.rect()
        menu_size = menu.sizeHint()
        if position == 'top':
            pos = self.volume_button.mapToGlobal(btn_rect.bottomLeft())
            pos.setY(pos.y() + self.volume_button.height())
        elif position == 'bottom':
            pos = self.volume_button.mapToGlobal(btn_rect.topLeft())
            pos.setY(pos.y() - menu_size.height())
        elif position == 'left':
            pos = self.volume_button.mapToGlobal(btn_rect.topRight())
        elif position == 'right':
            pos = self.volume_button.mapToGlobal(btn_rect.topLeft())
            pos.setX(pos.x() - menu_size.width())
        else:
            pos = self.volume_button.mapToGlobal(btn_rect.bottomLeft())
        menu.exec(pos)

    def open_sound_settings(self):
        """Abrir la configuración de sonido del sistema"""
        try:
            # Intentar varios comandos comunes para abrir la configuración de sonido
            for cmd in [
                ["pavucontrol"],  # PulseAudio Volume Control
                ["gnome-control-center", "sound"],  # GNOME
                ["systemsettings5", "kcm_pulseaudio"],  # KDE
                ["xfce4-audio-settings"]  # XFCE
            ]:
                try:
                    if subprocess.run(["which", cmd[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                        subprocess.Popen(cmd)
                        return
                except:
                    continue
            
            # Si ninguno funciona, mostrar mensaje
            QMessageBox.warning(self, "Error", "No se pudo abrir la configuración de sonido")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al abrir la configuración de sonido: {str(e)}")

    def update_network_status(self):
        """Actualizar el estado de la red y el ícono"""
        if not PSUTIL_AVAILABLE:
            self.network_button.setText("📶")  # Emoji fallback
            return

        try:
            # Obtener información de red
            net = psutil.net_if_stats()
            connected = False
            for interface, stats in net.items():
                if interface != 'lo' and stats.isup:  # Ignorar loopback
                    connected = True
                    break

            # Actualizar ícono según estado
            if connected:
                icon = QIcon.fromTheme("network-transmit-receive")
                if not icon.isNull():
                    self.network_button.setIcon(icon)
                    self.network_button.setIconSize(QSize(22, 22))
                else:
                    self.network_button.setText("🌐")
                self.network_button.setToolTip("Red conectada")
            else:
                icon = QIcon.fromTheme("network-offline")
                if not icon.isNull():
                    self.network_button.setIcon(icon)
                    self.network_button.setIconSize(QSize(22, 22))
                else:
                    self.network_button.setText("❌")
                self.network_button.setToolTip("Red desconectada")
        except:
            self.network_button.setText("📶")
            self.network_button.setToolTip("Estado de red desconocido")

    def get_wifi_networks(self):
        """Obtener lista de redes WiFi disponibles usando nmcli"""
        try:
            # Obtener lista de redes WiFi
            output = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"], 
                                          universal_newlines=True)
            networks = []
            for line in output.strip().split('\n'):
                if line:
                    ssid, signal, security, in_use = line.split(':')
                    if ssid:  # Ignorar SSIDs vacíos
                        networks.append({
                            'ssid': ssid,
                            'signal': int(signal) if signal else 0,
                            'security': security if security != '' else 'Abierta',
                            'in_use': in_use == '*'
                        })
            # Ordenar por intensidad de señal
            return sorted(networks, key=lambda x: x['signal'], reverse=True)
        except Exception as e:
            print(f"Error al obtener redes WiFi: {str(e)}")
            return []

    def connect_to_wifi(self, ssid, security):
        """Conectar a una red WiFi"""
        try:
            if security != 'Abierta':
                # Para redes con seguridad, mostrar diálogo de contraseña
                password, ok = QInputDialog.getText(
                    self, 
                    'Conectar a WiFi',
                    f'Ingrese la contraseña para "{ssid}":',
                    QLineEdit.EchoMode.Password
                )
                if ok and password:
                    subprocess.Popen(["nmcli", "device", "wifi", "connect", ssid, "password", password])
            else:
                # Para redes abiertas, conectar directamente
                subprocess.Popen(["nmcli", "device", "wifi", "connect", ssid])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al conectar a {ssid}: {str(e)}")

    def show_network_menu(self):
        """Mostrar menú contextual de red"""
        menu = QMenu(self)
        
        # Sección de WiFi
        wifi_menu = QMenu("Redes WiFi", menu)
        wifi_menu.setIcon(QIcon.fromTheme("network-wireless"))
        
        # Obtener y mostrar redes WiFi disponibles
        networks = self.get_wifi_networks()
        if networks:
            for net in networks:
                # Crear ícono según intensidad de señal
                if net['signal'] >= 75:
                    icon = QIcon.fromTheme("network-wireless-signal-excellent")
                elif net['signal'] >= 50:
                    icon = QIcon.fromTheme("network-wireless-signal-good")
                elif net['signal'] >= 25:
                    icon = QIcon.fromTheme("network-wireless-signal-ok")
                else:
                    icon = QIcon.fromTheme("network-wireless-signal-weak")
                
                # Crear acción para la red
                action = wifi_menu.addAction(icon, f"{net['ssid']} ({net['signal']}%) - {net['security']}")
                if net['in_use']:
                    action.setIcon(QIcon.fromTheme("network-wireless-connected"))
                    font = action.font()
                    font.setBold(True)
                    action.setFont(font)
                else:
                    # Conectar señal solo si no está en uso
                    action.triggered.connect(
                        lambda checked, ssid=net['ssid'], sec=net['security']: 
                        self.connect_to_wifi(ssid, sec)
                    )
        else:
            action = wifi_menu.addAction("No se encontraron redes")
            action.setEnabled(False)

        # Agregar submenú de WiFi al menú principal
        menu.addMenu(wifi_menu)
        menu.addSeparator()

        # Mostrar interfaces de red si psutil está disponible
        if PSUTIL_AVAILABLE:
            try:
                for interface, stats in psutil.net_if_stats().items():
                    if interface != 'lo':  # Ignorar loopback
                        status = "Conectado" if stats.isup else "Desconectado"
                        icon = QIcon.fromTheme("network-wired" if stats.isup else "network-wired-disconnected")
                        action = menu.addAction(icon, f"{interface}: {status}")
                        action.setEnabled(False)
                menu.addSeparator()
            except:
                pass

        # Botón para actualizar redes WiFi
        refresh_action = menu.addAction(QIcon.fromTheme("view-refresh"), "Actualizar redes WiFi")
        refresh_action.triggered.connect(lambda: self.show_network_menu())

        # Botón de configuración
        config_action = menu.addAction(QIcon.fromTheme("preferences-system-network"), "Configuración de red")
        config_action.triggered.connect(self.open_network_settings)
        
        # Mostrar el menú justo fuera del panel, no sobre él
        position = self.settings.get('position', 'top')
        btn_rect = self.network_button.rect()
        menu_size = menu.sizeHint()
        if position == 'top':
            pos = self.network_button.mapToGlobal(btn_rect.bottomLeft())
            pos.setY(pos.y() + self.network_button.height())
        elif position == 'bottom':
            pos = self.network_button.mapToGlobal(btn_rect.topLeft())
            pos.setY(pos.y() - menu_size.height())
        elif position == 'left':
            pos = self.network_button.mapToGlobal(btn_rect.topRight())
        elif position == 'right':
            pos = self.network_button.mapToGlobal(btn_rect.topLeft())
            pos.setX(pos.x() - menu_size.width())
        else:
            pos = self.network_button.mapToGlobal(btn_rect.bottomLeft())
        menu.exec(pos)

    def update_panel_launchers(self):
        # Elimina los lanzadores actuales
        for i in reversed(range(self.left_layout.count())):
            widget = self.left_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # Vuelve a crear los lanzadores según la configuración
        launchers = self.settings.get("panel_launchers", [
            {"name": "Menú", "command": None, "icon": "start-here"},
            {"name": "Terminal", "command": "terminal", "icon": "utilities-terminal"},
            {"name": "Archivos", "command": "file-manager", "icon": "system-file-manager"},
            {"name": "Red", "command": "network-settings", "icon": "network-wired"}
        ])
        self.launcher_buttons = []
        for idx, launcher in enumerate(launchers):
            btn = QPushButton()
            btn.setIcon(self.app_menu.get_icon(launcher["icon"]))
            btn.setIconSize(QSize(24, 24))
            btn.setToolTip(launcher["name"])
            btn.setFixedSize(38, 38)
            if idx == 0:
                self.menu_button = btn  # Guardar referencia al primer botón (Menú)
            if launcher["name"].lower() == "escritorio":
                btn.clicked.connect(self.show_workspace_menu)
            elif launcher["command"] == "terminal":
                btn.clicked.connect(self.open_terminal)
            elif launcher["command"] == "file-manager":
                btn.clicked.connect(self.open_file_manager)
            elif launcher["command"] or launcher["command"] is not None:
                btn.clicked.connect(lambda checked, cmd=launcher["command"]: subprocess.Popen(cmd.split()) if cmd else None)
            else:
                btn.clicked.connect(self.show_application_menu)
            self.left_layout.addWidget(btn)
            self.launcher_buttons.append(btn)

    def show_workspace_menu(self):
        """Mostrar menú para cambiar o crear escritorios virtuales"""
        import subprocess
        menu = QMenu(self)
        # Obtener número de escritorios y escritorio actual
        try:
            num = int(subprocess.check_output(['wmctrl', '-d']).decode().count('\n'))
            lines = subprocess.check_output(['wmctrl', '-d']).decode().splitlines()
            current = next((i for i, l in enumerate(lines) if '*' in l), 0)
        except Exception:
            num = 1
            current = 0
        # Añadir acciones para cambiar de escritorio
        for i in range(num):
            action = menu.addAction(f"Escritorio {i+1}")
            if i == current:
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            action.triggered.connect(lambda checked, idx=i: self.switch_workspace(idx))
        menu.addSeparator()
        # Acción para crear un nuevo escritorio
        add_action = menu.addAction("Crear nuevo escritorio")
        add_action.triggered.connect(self.create_new_workspace)
        # Mostrar menú debajo del botón que lo llamó
        sender = self.sender()
        if isinstance(sender, QPushButton):
            pos = sender.mapToGlobal(sender.rect().bottomLeft())
        else:
            pos = self.mapToGlobal(self.rect().bottomLeft())
        menu.exec(pos)

    def switch_workspace(self, idx):
        import subprocess
        try:
            subprocess.run(['wmctrl', '-s', str(idx)], check=False)
        except Exception:
            pass

    def create_new_workspace(self):
        import subprocess
        try:
            # Obtener número actual de escritorios
            lines = subprocess.check_output(['wmctrl', '-d']).decode().splitlines()
            num = len(lines)
            # Crear uno más
            subprocess.run(['wmctrl', '-n', str(num+1)], check=False)
        except Exception:
            pass
    """Panel principal de escritorio"""
    
    # Señales personalizadas
    update_clock_signal = pyqtSignal()
    update_system_signal = pyqtSignal(str)
    update_windows_signal = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.load_settings()  # <-- Asegura que self.settings exista antes de crear widgets
        self.setup_window()
        self.create_widgets()
        self.setup_system_tray()
        self.setup_timers()
        self.setup_notifications()  # Configurar servicio de notificaciones
        self.connect_signals()
        # Asegura que los struts se apliquen tras mostrar la ventana
        QTimer.singleShot(100, self.apply_position)

    def showEvent(self, event):
        super().showEvent(event)
        # Reaplicar struts al mostrar el panel
        self.apply_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reaplicar struts al cambiar tamaño
        self.apply_position()

    def moveEvent(self, event):
        super().moveEvent(event)
        # Reaplicar struts al mover el panel
        self.apply_position()
    
    def apply_position(self):
        """Aplicar la posición configurada al panel"""
        screen = QApplication.primaryScreen().geometry()
        panel_height = self.settings.get('height', 35)
        position = self.settings.get('position', 'top')
        if position == 'top':
            self.setGeometry(0, 0, screen.width(), panel_height)
        elif position == 'bottom':
            self.setGeometry(0, screen.height() - panel_height, screen.width(), panel_height)
        elif position == 'left':
            self.setGeometry(0, 0, panel_height, screen.height())
        elif position == 'right':
            self.setGeometry(screen.width() - panel_height, 0, panel_height, screen.height())
        
        # Actualizar los struts cuando cambia la posición
        if hasattr(self, 'winId'):
            try:
                import subprocess
                if position == 'top':
                    struts = f"0, 0, {panel_height}, 0"
                    partial_struts = f"0, 0, {panel_height}, 0, 0, 0, 0, 0, 0, {screen.width()}, 0, 0"
                elif position == 'bottom':
                    struts = f"0, 0, 0, {panel_height}"
                    partial_struts = f"0, 0, 0, {panel_height}, 0, 0, 0, 0, 0, {screen.width()}, 0, 0"
                elif position == 'left':
                    struts = f"{panel_height}, 0, 0, 0"
                    partial_struts = f"{panel_height}, 0, 0, 0, 0, {screen.height()}, 0, 0, 0, 0, 0, 0"
                elif position == 'right':
                    struts = f"0, {panel_height}, 0, 0"
                    partial_struts = f"0, {panel_height}, 0, 0, 0, {screen.height()}, 0, 0, 0, 0, 0, 0"
                
                subprocess.run([
                    'xprop', '-id', str(int(self.winId())),
                    '-f', '_NET_WM_STRUT', '32cccc',
                    '-set', '_NET_WM_STRUT', struts
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                subprocess.run([
                    'xprop', '-id', str(int(self.winId())),
                    '-f', '_NET_WM_STRUT_PARTIAL', '32cccccccccccc',
                    '-set', '_NET_WM_STRUT_PARTIAL', partial_struts
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error actualizando struts: {e}")

    def setup_window(self):
        """Configurar ventana principal"""
        # Obtener geometría de la pantalla
        screen = QApplication.primaryScreen().geometry()
        # Configurar tamaño y posición
        self.apply_position()
        # Propiedades de la ventana
        self.setWindowTitle("Panel de Escritorio")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Configurar como panel/dock y reservar espacio en X11
        if hasattr(self, 'winId'):
            try:
                import subprocess
                # Configurar como dock
                subprocess.run([
                    'xprop', '-id', str(int(self.winId())),
                    '-f', '_NET_WM_WINDOW_TYPE', '32a',
                    '-set', '_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DOCK'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Configurar struts para reservar espacio
                panel_height = self.settings.get('height', 35)
                position = self.settings.get('position', 'top')
                screen = QApplication.primaryScreen().geometry()
                
                if position == 'top':
                    struts = f"0, 0, {panel_height}, 0"  # left, right, top, bottom
                elif position == 'bottom':
                    struts = f"0, 0, 0, {panel_height}"
                elif position == 'left':
                    struts = f"{panel_height}, 0, 0, 0"
                elif position == 'right':
                    struts = f"0, {panel_height}, 0, 0"
                
                subprocess.run([
                    'xprop', '-id', str(int(self.winId())),
                    '-f', '_NET_WM_STRUT', '32cccc',
                    '-set', '_NET_WM_STRUT', struts
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Configurar struts parciales (más preciso)
                if position == 'top':
                    partial_struts = f"0, 0, {panel_height}, 0, 0, 0, 0, 0, 0, {screen.width()}, 0, 0"
                elif position == 'bottom':
                    partial_struts = f"0, 0, 0, {panel_height}, 0, 0, 0, 0, 0, {screen.width()}, 0, 0"
                elif position == 'left':
                    partial_struts = f"{panel_height}, 0, 0, 0, 0, {screen.height()}, 0, 0, 0, 0, 0, 0"
                elif position == 'right':
                    partial_struts = f"0, {panel_height}, 0, 0, 0, {screen.height()}, 0, 0, 0, 0, 0, 0"
                
                subprocess.run([
                    'xprop', '-id', str(int(self.winId())),
                    '-f', '_NET_WM_STRUT_PARTIAL', '32cccccccccccc',
                    '-set', '_NET_WM_STRUT_PARTIAL', partial_struts
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error configurando struts: {e}")
        
        # Estilo general
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e2e2e;
                border-bottom: 1px solid #555;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QLabel {
                color: white;
                padding: 5px;
            }
        """)
    
    def create_widgets(self):
        """Crear widgets del panel"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal horizontal
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 2, 5, 2)
        main_layout.setSpacing(5)
        
        # === LADO IZQUIERDO ===
        self.left_layout = QHBoxLayout()
        

    # Crear menú de aplicaciones antes de los lanzadores para poder usar get_icon
        self.app_menu = ApplicationMenu(self)
        self.update_panel_launchers()
        
        main_layout.addLayout(self.left_layout)
        
        # === CENTRO - Lista de ventanas ===
        self.windows_layout = QHBoxLayout()
        self.windows_layout.setSpacing(3)
        main_layout.addLayout(self.windows_layout, 1)  # Stretch factor 1
        
        # === LADO DERECHO ===
        right_layout = QHBoxLayout()
        
        # Monitor del sistema
        self.system_label = QLabel("Sistema: --")
        self.system_label.setStyleSheet("color: #00ff00; font-family: monospace;")
        right_layout.addWidget(self.system_label)
        
        # Reloj
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setStyleSheet("color: white; font-weight: bold; font-family: monospace; font-size: 12px;")
        right_layout.addWidget(self.clock_label)

        # Indicador de Red
        self.network_button = QPushButton()
        self.network_button.setObjectName("NetworkButton")
        self.network_button.setFixedSize(32, 32)
        self.network_button.setToolTip("Estado de la Red")
        self.network_button.setStyleSheet("background: transparent; border: none;")
        self.network_button.clicked.connect(self.show_network_menu)
        self.update_network_status()  # Actualizar estado inicial
        right_layout.addWidget(self.network_button)

        # Control de Volumen
        self.volume_button = QPushButton()
        self.volume_button.setObjectName("VolumeButton")
        self.volume_button.setFixedSize(32, 32)
        self.volume_button.setToolTip("Control de Volumen")
        self.volume_button.setStyleSheet("background: transparent; border: none;")
        self.volume_button.clicked.connect(self.show_volume_menu)
        self.volume_slider = None  # Se creará cuando se necesite
        self.update_volume_status()  # Actualizar estado inicial
        right_layout.addWidget(self.volume_button)

        # Indicador de Batería
        self.battery_button = QPushButton()
        self.battery_button.setObjectName("BatteryButton")
        self.battery_button.setFixedSize(32, 32)
        self.battery_button.setToolTip("Estado de la Batería")
        self.battery_button.setStyleSheet("background: transparent; border: none;")
        self.battery_button.clicked.connect(self.show_battery_menu)
        self.update_battery_status()  # Actualizar estado inicial
        right_layout.addWidget(self.battery_button)

        # Dispositivos de almacenamiento
        self.storage_button = QPushButton()
        self.storage_button.setObjectName("StorageButton")
        self.storage_button.setFixedSize(32, 32)
        self.storage_button.setToolTip("Dispositivos de almacenamiento")
        self.storage_button.setStyleSheet("background: transparent; border: none;")
        self.storage_button.clicked.connect(self.show_storage_menu)
        self.update_storage_status()  # Actualizar estado inicial
        right_layout.addWidget(self.storage_button)

        # Bluetooth
        self.bluetooth_button = QPushButton()
        self.bluetooth_button.setObjectName("BluetoothButton")
        self.bluetooth_button.setFixedSize(32, 32)
        self.bluetooth_button.setToolTip("Bluetooth")
        self.bluetooth_button.setStyleSheet("background: transparent; border: none;")
        self.bluetooth_button.clicked.connect(self.show_bluetooth_menu)
        self.update_bluetooth_status()  # Actualizar estado inicial
        right_layout.addWidget(self.bluetooth_button)

        # Notificaciones
        self.notification_button = QPushButton()
        self.notification_button.setObjectName("NotificationButton")
        self.notification_button.setFixedSize(32, 32)
        bell_icon = QIcon.fromTheme("preferences-desktop-notification")
        if bell_icon.isNull():
            # Si no hay ícono del tema, usar emoji
            self.notification_button.setText("🔔")
            self.notification_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 16px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                }
                QPushButton:pressed {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
        else:
            self.notification_button.setIcon(bell_icon)
            self.notification_button.setIconSize(QSize(22, 22))
            self.notification_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                }
                QPushButton:pressed {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
        self.notification_button.setToolTip("Centro de Notificaciones")
        self.notification_button.clicked.connect(self.show_notifications_menu)
        right_layout.addWidget(self.notification_button)

        # Botón de configuración
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setMaximumWidth(30)
        self.settings_button.clicked.connect(self.show_settings)
        right_layout.addWidget(self.settings_button)

        # Botón de acciones de usuario (bloquear, cambiar usuario, cerrar sesión)
        self.user_button = QPushButton("🔒")
        self.user_button.setMaximumWidth(30)
        self.user_button.setToolTip("Opciones de usuario")
        self.user_button.clicked.connect(self.show_user_menu)
        right_layout.addWidget(self.user_button)
        
        main_layout.addLayout(right_layout)
        
        # Crear menú de aplicaciones
        self.app_menu = ApplicationMenu(self)

    def show_user_menu(self):
        menu = QMenu(self)
        lock_action = menu.addAction("Bloquear Pantalla")
        suspend_action = menu.addAction("Suspender")
        reboot_action = menu.addAction("Reiniciar")
        shutdown_action = menu.addAction("Apagar")
        switch_action = menu.addAction("Cambiar de Usuario")
        logout_action = menu.addAction("Cerrar Sesión")

        lock_action.triggered.connect(self.lock_screen)
        suspend_action.triggered.connect(self.suspend_system)
        reboot_action.triggered.connect(self.reboot_system)
        shutdown_action.triggered.connect(self.shutdown_system)
        switch_action.triggered.connect(self.switch_user)
        logout_action.triggered.connect(self.logout_session)

        menu.exec(self.user_button.mapToGlobal(self.user_button.rect().bottomLeft()))

    def suspend_system(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea suspender el equipo?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["systemctl suspend", "pm-suspend"]:
                try:
                    subprocess.Popen(cmd.split())
                    break
                except Exception:
                    continue

    def reboot_system(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea reiniciar el equipo?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["systemctl reboot", "reboot"]:
                try:
                    subprocess.Popen(cmd.split())
                    break
                except Exception:
                    continue

    def shutdown_system(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea apagar el equipo?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["systemctl poweroff", "shutdown -h now", "poweroff"]:
                try:
                    subprocess.Popen(cmd.split())
                    break
                except Exception:
                    continue

    def lock_screen(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea bloquear la pantalla?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["xdg-screensaver lock", "dm-tool lock", "gnome-screensaver-command -l", "loginctl lock-session"]:
                try:
                    subprocess.Popen(cmd.split())
                    break
                except Exception:
                    continue

    def switch_user(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea cambiar de usuario?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["dm-tool switch-to-greeter", "gdmflexiserver", "lightdm --switch-to-greeter"]:
                try:
                    subprocess.Popen(cmd.split())
                    break
                except Exception:
                    continue

    def logout_session(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirmar")
        box.setText("¿Desea cerrar la sesión?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Aceptar")
        box.button(QMessageBox.Cancel).setText("Cancelar")
        box.setStyleSheet("QLabel{color:#111;} QPushButton{background:white; color:#111; border:1px solid #bbb; border-radius:4px; padding:4px 16px;} QPushButton:hover{background:#f0f0f0;}")
        reply = box.exec()
        if reply == QMessageBox.Yes:
            for cmd in ["xfce4-session-logout --logout", "gnome-session-quit --logout --no-prompt", "openbox --exit", "pkill -KILL -u $USER"]:
                try:
                    subprocess.Popen(cmd.split(), shell=False)
                    break
                except Exception:
                    continue
    
    def setup_system_tray(self):
        """Configurar bandeja del sistema"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = SystemTray(self)
            self.tray.show()
    
    def setup_timers(self):
        """Configurar timers para actualizaciones"""
        # Timer para el reloj (cada segundo)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        # Timer para información del sistema (cada 2 segundos)
        self.system_timer = QTimer()
        self.system_timer.timeout.connect(self.update_system_info_threaded)
        self.system_timer.start(2000)

        # Timer para el estado de la red (cada 5 segundos)
        self.network_timer = QTimer()
        self.network_timer.timeout.connect(self.update_network_status)
        self.network_timer.start(5000)

        # Timer para el estado del volumen (cada segundo)
        self.volume_timer = QTimer()
        self.volume_timer.timeout.connect(self.update_volume_status)
        self.volume_timer.start(1000)

        # Timer para el estado de la batería (cada 5 segundos)
        self.battery_timer = QTimer()
        self.battery_timer.timeout.connect(self.update_battery_status)
        self.battery_timer.start(5000)

        # Timer para el estado de dispositivos de almacenamiento (cada 2 segundos)
        self.storage_timer = QTimer()
        self.storage_timer.timeout.connect(self.update_storage_status)
        self.storage_timer.start(2000)

        # Timer para el estado del Bluetooth (cada 2 segundos)
        self.bluetooth_timer = QTimer()
        self.bluetooth_timer.timeout.connect(self.update_bluetooth_status)
        self.bluetooth_timer.start(2000)
        
        # Timer para lista de ventanas (cada 3 segundos)
        self.windows_timer = QTimer()
        self.windows_timer.timeout.connect(self.update_windows_threaded)
        self.windows_timer.start(3000)
    
    def connect_signals(self):
        """Conectar señales personalizadas"""
        self.update_clock_signal.connect(self.update_clock)
        self.update_system_signal.connect(self.update_system_info_display)
        self.update_windows_signal.connect(self.update_windows_display)
    
    def load_settings(self):
        """Cargar configuración"""
        self.settings_file = Path.home() / ".config" / "desktop-panel" / "config.json"
        self.settings = {
            "auto_hide": False,
            "position": "top",
            "height": 35,
            "show_system_info": True
        }
        
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error cargando configuración: {e}")
    
    def save_settings(self):
        """Guardar configuración"""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error guardando configuración: {e}")
    
    def update_clock(self):
        """Actualizar reloj"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(current_time)
    
    def update_system_info_threaded(self):
        """Actualizar información del sistema en hilo separado"""
        def worker():
            if PSUTIL_AVAILABLE:
                try:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory = psutil.virtual_memory()
                    ram_percent = memory.percent
                    
                    system_text = f"CPU: {cpu_percent:.0f}% | RAM: {ram_percent:.0f}%"
                    self.update_system_signal.emit(system_text)
                except Exception:
                    self.update_system_signal.emit("Sistema: Error")
            else:
                self.update_system_signal.emit("Sistema: N/A")
        
        threading.Thread(target=worker, daemon=True).start()
    
    def update_system_info_display(self, text):
        """Actualizar display de información del sistema"""
        self.system_label.setText(text)
    
    def update_windows_threaded(self):
        """Actualizar lista de ventanas en hilo separado"""
        def worker():
            try:
                result = subprocess.run(['wmctrl', '-l'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    windows = []
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            parts = line.split(None, 3)
                            if len(parts) >= 4:
                                window_id = parts[0]
                                window_title = parts[3]
                                # Filtrar ventanas del propio panel
                                if "Panel de Escritorio" not in window_title:
                                    windows.append((window_id, window_title))
                    
                    self.update_windows_signal.emit(windows)
            except Exception:
                self.update_windows_signal.emit([])
        
        threading.Thread(target=worker, daemon=True).start()
    
    def update_windows_display(self, windows):
        """Actualizar display de ventanas"""
        # Limpiar botones existentes
        for i in reversed(range(self.windows_layout.count())):
            child = self.windows_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
        
        # Crear nuevos botones para las ventanas
        for window_id, window_title in windows[:8]:  # Máximo 8 ventanas
            window_btn = WindowButton(window_id, window_title)
            self.windows_layout.addWidget(window_btn)
        
        # Añadir espaciador si hay pocas ventanas
        if len(windows) < 8:
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.windows_layout.addItem(spacer)
    
    def show_application_menu(self):
        """Mostrar menú de aplicaciones ajustando la dirección según la posición del panel"""
        position = self.settings.get('position', 'top')
        btn_rect = self.menu_button.rect()
        if position == 'top':
            # Menú hacia abajo
            pos = self.menu_button.mapToGlobal(btn_rect.bottomLeft())
        elif position == 'bottom':
            # Menú hacia arriba
            pos = self.menu_button.mapToGlobal(btn_rect.topLeft())
            pos.setY(pos.y() - self.app_menu.height())
        elif position == 'left':
            # Menú hacia la derecha
            pos = self.menu_button.mapToGlobal(btn_rect.topRight())
        elif position == 'right':
            # Menú hacia la izquierda
            pos = self.menu_button.mapToGlobal(btn_rect.topLeft())
            pos.setX(pos.x() - self.app_menu.width())
        else:
            pos = self.menu_button.mapToGlobal(btn_rect.bottomLeft())
        self.app_menu.move(pos)
        self.app_menu.show()
    
    def open_terminal(self):
        """Abrir terminal"""
        terminals = ['xfce4-terminal', 'gnome-terminal', 'konsole', 'xterm', 'alacritty']
        for terminal in terminals:
            try:
                subprocess.Popen([terminal])
                break
            except FileNotFoundError:
                continue
    
    def open_file_manager(self):
        """Abrir gestor de archivos"""
        file_managers = ['thunar', 'nautilus', 'dolphin', 'pcmanfm', 'nemo']
        for fm in file_managers:
            try:
                subprocess.Popen([fm])
                break
            except FileNotFoundError:
                continue
    
    def show_settings(self):
        """Mostrar ventana de configuración"""
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()

    def setup_notifications(self):
        """Configurar el servicio de notificaciones"""
        self.notifications = []  # Inicializar lista de notificaciones
        
        # Crear una notificación de prueba inicial
        test_notification = NotificationItem(
            1,
            "Panel Qt",
            "dialog-information",
            "Sistema de notificaciones",
            "El centro de notificaciones está funcionando correctamente"
        )
        self.notifications.append(test_notification)
        self.update_notification_button()

        if not NOTIFY2_AVAILABLE:
            print("Notify2 no está disponible, las notificaciones no funcionarán")
            return

        try:
            # Inicializar notify2
            notify2.init("Panel Qt")
            print("Servicio de notificaciones iniciado correctamente")
            
            # Iniciar el hilo de monitoreo de notificaciones
            self.start_notification_monitor()
            
        except Exception as e:
            print(f"Error al configurar notificaciones: {e}")
    
    def start_notification_monitor(self):
        """Iniciar el monitor de notificaciones en un hilo separado"""
        def monitor():
            try:
                import subprocess
                proc = subprocess.Popen(['dbus-monitor', 'interface=org.freedesktop.Notifications'],
                                      stdout=subprocess.PIPE, universal_newlines=True)
                for line in proc.stdout:
                    if 'member=Notify' in line:
                        self.on_notification_received()
            except Exception as e:
                print(f"Error en el monitor de notificaciones: {e}")
        
        threading.Thread(target=monitor, daemon=True).start()
            
    def on_notification_received(self, *args):
        """Callback cuando se recibe una notificación"""
        try:
            print("Notificación recibida")  # Debug
            notification = NotificationItem(
                len(self.notifications) + 1,
                "Sistema",
                "dialog-information",
                "Nueva notificación",
                "Se ha recibido una nueva notificación"
            )
            self.add_notification(notification)
            print(f"Notificación agregada. Total: {len(self.notifications)}")  # Debug
        except Exception as e:
            print(f"Error al procesar notificación: {e}")

    def remove_notification(self, index):
        """Eliminar una notificación específica"""
        try:
            if 0 <= index < len(self.notifications):
                del self.notifications[index]
                self.update_notification_button()
                # Refrescar el menú de notificaciones
                if hasattr(self, 'notification_menu'):
                    self.notification_menu.close()
                    self.show_notifications_menu()
        except Exception as e:
            print(f"Error al eliminar notificación: {e}")

    def clear_all_notifications(self):
        """Limpiar todas las notificaciones"""
        try:
            self.notifications.clear()
            self.update_notification_button()
            # Refrescar el menú de notificaciones
            if hasattr(self, 'notification_menu'):
                self.notification_menu.close()
                self.show_notifications_menu()
        except Exception as e:
            print(f"Error al limpiar notificaciones: {e}")

    def add_notification(self, notification):
        """Agregar una nueva notificación"""
        self.notifications.insert(0, notification)  # Agregar al principio
        # Mantener solo las últimas 50 notificaciones
        if len(self.notifications) > 50:
            self.notifications.pop()
        # Actualizar el contador y el ícono
        self.update_notification_button()

    def update_notification_button(self):
        """Actualizar el botón de notificaciones"""
        count = len(self.notifications)
        if count > 0:
            self.notification_button.setText(f"🔔 {count}")
            self.notification_button.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    border-radius: 4px;
                    padding: 4px;
                    color: white;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
        else:
            self.notification_button.setText("🔔")
            self.notification_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                }
            """)

    def remove_notification(self, index):
        """Eliminar una notificación específica"""
        try:
            if 0 <= index < len(self.notifications):
                del self.notifications[index]
                self.update_notification_button()
                # Refrescar el menú de notificaciones
                if hasattr(self, 'notification_menu'):
                    self.notification_menu.close()
                    self.show_notifications_menu()
        except Exception as e:
            print(f"Error al eliminar notificación: {e}")

    def clear_all_notifications(self):
        """Limpiar todas las notificaciones"""
        try:
            self.notifications.clear()
            self.update_notification_button()
            # Refrescar el menú de notificaciones
            if hasattr(self, 'notification_menu'):
                self.notification_menu.close()
                self.show_notifications_menu()
        except Exception as e:
            print(f"Error al limpiar notificaciones: {e}")
    
    def quit_application(self):
        """Salir de la aplicación"""
        self.save_settings()
        QApplication.quit()
    
    def closeEvent(self, event):
        """Manejar evento de cierre"""
        if hasattr(self, 'tray') and self.tray.isVisible():
            # Minimizar a bandeja del sistema
            self.hide()
            event.ignore()
        else:
            self.quit_application()
            event.accept()

# Ya no es necesario, se movió arriba

class SettingsDialog(QDialog):
    def edit_selected_launcher_dialog(self):
        row = self.launchers_list.currentRow()
        if row < 0:
            return
        item = self.launchers_list.item(row)
        launcher = item.data(Qt.ItemDataRole.UserRole)
        dlg = QDialog(self)
        dlg.setWindowTitle("Editar Lanzador")
        layout = QVBoxLayout(dlg)
        name_edit = QLineEdit(launcher.get("name", ""))
        name_edit.setPlaceholderText("Nombre")
        cmd_edit = QLineEdit(launcher.get("command") or "")
        cmd_edit.setPlaceholderText("Comando (ej: thunar, firefox, etc)")
        icon_edit = QLineEdit(launcher.get("icon", ""))
        icon_edit.setPlaceholderText("Icono del sistema (ej: firefox, utilities-terminal)")
        layout.addWidget(QLabel("Nombre:"))
        layout.addWidget(name_edit)
        layout.addWidget(QLabel("Comando:"))
        layout.addWidget(cmd_edit)
        layout.addWidget(QLabel("Icono del sistema:"))
        layout.addWidget(icon_edit)
        btns = QHBoxLayout()
        ok_btn = QPushButton("Guardar")
        cancel_btn = QPushButton("Cancelar")
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            cmd = cmd_edit.text().strip()
            icon = icon_edit.text().strip()
            if name and icon:
                new_launcher = {"name": name, "command": cmd if cmd else None, "icon": icon}
                item.setText(name)
                item.setIcon(self.parent.app_menu.get_icon(icon))
                item.setData(Qt.ItemDataRole.UserRole, new_launcher)
    """Diálogo de configuración"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
    
    def setup_ui(self):
        """Configurar interfaz"""
        self.setWindowTitle("Configuración del Panel")
        self.setFixedSize(420, 340)

        main_layout = QVBoxLayout(self)

        # Título
        title = QLabel("Configuración del Panel")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Pestaña de Opciones Generales ---
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        options_group = QGroupBox("Opciones")
        options_layout = QVBoxLayout(options_group)

        # Auto-hide
        self.auto_hide_check = QCheckBox("Ocultar automáticamente")
        self.auto_hide_check.setChecked(self.parent.settings.get("auto_hide", False))
        options_layout.addWidget(self.auto_hide_check)

        # Mostrar info del sistema
        self.show_system_check = QCheckBox("Mostrar información del sistema")
        self.show_system_check.setChecked(self.parent.settings.get("show_system_info", True))
        options_layout.addWidget(self.show_system_check)

        options_group.setLayout(options_layout)
        general_layout.addWidget(options_group)

        # Información del sistema
        info_group = QGroupBox("Información del Sistema")
        info_layout = QVBoxLayout(info_group)
        try:
            import platform
            system_info = f"Sistema: {platform.system()} {platform.release()}"
            python_info = f"Python: {platform.python_version()}"
            pyqt_info = f"PyQt: {PYQT_VERSION}"
            info_layout.addWidget(QLabel(system_info))
            info_layout.addWidget(QLabel(python_info))
            info_layout.addWidget(QLabel(pyqt_info))
            info_layout.addWidget(QLabel(f"psutil: {'Disponible' if PSUTIL_AVAILABLE else 'No disponible'}"))
        except Exception:
            info_layout.addWidget(QLabel("Información no disponible"))
        general_layout.addWidget(info_group)

        self.tabs.addTab(general_tab, "General")

        # --- Pestaña de Posición del Panel ---
        position_tab = QWidget()
        position_layout = QVBoxLayout(position_tab)
        position_group = QGroupBox("Posición del Panel")
        position_group_layout = QVBoxLayout(position_group)
        self.top_radio = QRadioButton("Arriba")
        self.bottom_radio = QRadioButton("Abajo")
        self.left_radio = QRadioButton("Izquierda")
        self.right_radio = QRadioButton("Derecha")
        position_group_layout.addWidget(self.top_radio)
        position_group_layout.addWidget(self.bottom_radio)
        position_group_layout.addWidget(self.left_radio)
        position_group_layout.addWidget(self.right_radio)
        position_group.setLayout(position_group_layout)
        position_layout.addWidget(position_group)
        position_layout.addStretch()
        self.tabs.addTab(position_tab, "Posición")

        # Cargar la posición actual
        position = self.parent.settings.get('position', 'bottom')
        if position == 'top':
            self.top_radio.setChecked(True)
        elif position == 'bottom':
            self.bottom_radio.setChecked(True)
        elif position == 'left':
            self.left_radio.setChecked(True)
        elif position == 'right':
            self.right_radio.setChecked(True)

        # --- Pestaña de Tema del Menú ---
        theme_tab = QWidget()
        theme_layout = QVBoxLayout(theme_tab)
        theme_group = QGroupBox("Tema del Menú de Aplicaciones")
        theme_group_layout = QVBoxLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Claro", "claro")
        self.theme_combo.addItem("Oscuro", "oscuro")
        self.theme_combo.addItem("Sistema", "sistema")
        # Cargar tema actual
        current_theme = self.parent.app_menu.theme if hasattr(self.parent, 'app_menu') else "claro"
        idx = self.theme_combo.findData(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        theme_group_layout.addWidget(QLabel("Selecciona el tema del menú de aplicaciones:"))
        theme_group_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_group_layout)
        theme_layout.addWidget(theme_group)
        theme_layout.addStretch()
        self.tabs.addTab(theme_tab, "Tema del Menú")


        # --- Pestaña de Lanzadores del Panel ---
        panel_tab = QWidget()
        panel_layout = QVBoxLayout(panel_tab)
        self.launchers_list = QListWidget()
        self.launchers_list.setIconSize(QSize(28, 28))
        self.load_launchers_to_list()
        panel_layout.addWidget(QLabel("Lanzadores del Panel:"))
        panel_layout.addWidget(self.launchers_list)


    # Botones para agregar, editar, eliminar y mover
        btns_layout = QHBoxLayout()
        add_btn = QPushButton("Agregar")
        edit_btn = QPushButton("Editar")
        remove_btn = QPushButton("Eliminar")
        up_btn = QPushButton("Subir")
        down_btn = QPushButton("Bajar")
        btns_layout.addWidget(add_btn)
        btns_layout.addWidget(edit_btn)
        btns_layout.addWidget(remove_btn)
        btns_layout.addWidget(up_btn)
        btns_layout.addWidget(down_btn)

        panel_layout.addLayout(btns_layout)
        add_btn.clicked.connect(self.add_launcher_dialog)
        edit_btn.clicked.connect(self.edit_selected_launcher_dialog)
        remove_btn.clicked.connect(self.remove_selected_launcher)
        up_btn.clicked.connect(self.move_launcher_up)
        down_btn.clicked.connect(self.move_launcher_down)
        self.tabs.addTab(panel_tab, "Panel")

        # --- Botones inferiores ---
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Guardar")
        save_button.clicked.connect(self.on_save_clicked)
        buttons_layout.addWidget(save_button)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        restart_button = QPushButton("Reiniciar Panel")
        restart_button.clicked.connect(self.on_restart_clicked)
        buttons_layout.addWidget(restart_button)
        self.layout().addLayout(buttons_layout)

    def on_save_clicked(self):
        # Guardar la posición seleccionada
        if self.top_radio.isChecked():
            self.parent.settings['position'] = 'top'
        elif self.bottom_radio.isChecked():
            self.parent.settings['position'] = 'bottom'
        elif self.left_radio.isChecked():
            self.parent.settings['position'] = 'left'
        elif self.right_radio.isChecked():
            self.parent.settings['position'] = 'right'
        # Guardar otras opciones generales
        self.parent.settings['auto_hide'] = self.auto_hide_check.isChecked()
        self.parent.settings['show_system_info'] = self.show_system_check.isChecked()
        # Guardar y aplicar
        if hasattr(self.parent, 'save_settings'):
            self.parent.save_settings()
        if hasattr(self.parent, 'load_settings'):
            self.parent.load_settings()
        if hasattr(self.parent, 'apply_position'):
            self.parent.apply_position()
        self.accept()

    def on_restart_clicked(self):
        # Guardar antes de reiniciar
        self.on_save_clicked()
        # Reiniciar el panel (cerrar y volver a abrir)
        import sys
        import os
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def load_launchers_to_list(self):
        self.launchers_list.clear()
        launchers = self.parent.settings.get("panel_launchers", [
            {"name": "Menú", "command": None, "icon": "start-here"},
            {"name": "Terminal", "command": "terminal", "icon": "utilities-terminal"},
            {"name": "Archivos", "command": "file-manager", "icon": "system-file-manager"}
        ])
        for launcher in launchers:
            icon = self.parent.app_menu.get_icon(launcher["icon"])
            item = QListWidgetItem(icon, launcher["name"])
            item.setData(Qt.ItemDataRole.UserRole, launcher)
            self.launchers_list.addItem(item)

    def add_launcher_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Agregar Lanzador")
        layout = QVBoxLayout(dlg)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Nombre")
        cmd_edit = QLineEdit()
        cmd_edit.setPlaceholderText("Comando (ej: thunar, firefox, etc)")
        icon_edit = QLineEdit()
        icon_edit.setPlaceholderText("Icono del sistema (ej: firefox, utilities-terminal)")
        layout.addWidget(QLabel("Nombre:"))
        layout.addWidget(name_edit)
        layout.addWidget(QLabel("Comando:"))
        layout.addWidget(cmd_edit)
        layout.addWidget(QLabel("Icono del sistema:"))
        layout.addWidget(icon_edit)
        btns = QHBoxLayout()
        ok_btn = QPushButton("Agregar")
        cancel_btn = QPushButton("Cancelar")
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            cmd = cmd_edit.text().strip()
            icon = icon_edit.text().strip()
            if name and icon:
                launcher = {"name": name, "command": cmd if cmd else None, "icon": icon}
                item = QListWidgetItem(self.parent.app_menu.get_icon(icon), name)
                item.setData(Qt.ItemDataRole.UserRole, launcher)
                self.launchers_list.addItem(item)

    def remove_selected_launcher(self):
        row = self.launchers_list.currentRow()
        if row >= 0:
            self.launchers_list.takeItem(row)

    def move_launcher_up(self):
        row = self.launchers_list.currentRow()
        if row > 0:
            item = self.launchers_list.takeItem(row)
            self.launchers_list.insertItem(row-1, item)
            self.launchers_list.setCurrentRow(row-1)

    def move_launcher_down(self):
        row = self.launchers_list.currentRow()
        if row < self.launchers_list.count()-1 and row >= 0:
            item = self.launchers_list.takeItem(row)
            self.launchers_list.insertItem(row+1, item)
            self.launchers_list.setCurrentRow(row+1)

        # Estilo
        self.setStyleSheet("""
            QDialog {
                background-color: #3e3e3e;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #505050;
                border: 1px solid #666;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #606060;
            }
        """)
    
    def save_settings(self):
        """Guardar configuración"""
        self.parent.settings["auto_hide"] = self.auto_hide_check.isChecked()
        self.parent.settings["show_system_info"] = self.show_system_check.isChecked()

        # Guardar lanzadores del panel
        launchers = []
        for i in range(self.launchers_list.count()):
            launcher = self.launchers_list.item(i).data(Qt.ItemDataRole.UserRole)
            launchers.append(launcher)
        self.parent.settings["panel_launchers"] = launchers

        # Aplicar cambios
        if not self.parent.settings["show_system_info"]:
            self.parent.system_label.hide()
        else:
            self.parent.system_label.show()

        # Guardar y aplicar tema del menú de aplicaciones
        if hasattr(self.parent, 'app_menu'):
            selected_theme = self.theme_combo.currentData()
            self.parent.app_menu.set_theme(selected_theme)

        self.parent.save_settings()
        if hasattr(self.parent, 'update_panel_launchers'):
            self.parent.update_panel_launchers()
        self.accept()
    
    def restart_panel(self):
        """Reiniciar panel"""
        self.accept()
        self.parent.quit_application()
        subprocess.Popen([sys.executable, __file__])



def main():
    """Función principal"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # No salir cuando se cierra la ventana
    
    # Verificar si ya hay una instancia ejecutándose
    app.setApplicationName("DesktopPanel")
    
    # Crear y mostrar panel
    panel = DesktopPanel()
    panel.show()
    
    # Configurar manejo de señales del sistema
    import signal
    signal.signal(signal.SIGINT, lambda sig, frame: panel.quit_application())
    
    # Ejecutar aplicación
    try:
        sys.exit(app.exec() if PYQT_VERSION == 6 else app.exec_())
    except KeyboardInterrupt:
        panel.quit_application()

if __name__ == "__main__":
    main()