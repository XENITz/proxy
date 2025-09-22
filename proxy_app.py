import sys
import winreg
import subprocess
import requests
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QDialog,
    QFormLayout, QGroupBox, QFrame, QGraphicsDropShadowEffect, QCheckBox
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtGui import QIcon, QColor, QIntValidator, QFont, QPalette

# Versión actual de la aplicación
APP_VERSION = "1.0.0"
# Debe ser en formato "owner/repo" para usar con la API de GitHub
GITHUB_REPO = "XENITz/proxy"

# Clase para verificar actualizaciones en segundo plano
def compare_versions(version1: str, version2: str) -> int:
    """Compara dos versiones semánticas x.y.z devolviendo 1, 0, -1."""
    try:
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
    except ValueError:
        # Si el formato no es numérico, se considera iguales para no forzar actualización incorrecta
        return 0
    while len(v1_parts) < 3:
        v1_parts.append(0)
    while len(v2_parts) < 3:
        v2_parts.append(0)
    for a, b in zip(v1_parts[:3], v2_parts[:3]):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0


class UpdateChecker(QThread):
    update_available = Signal(str)

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get('tag_name', '').lstrip('v')
                if latest_version and compare_versions(latest_version, APP_VERSION) > 0:
                    self.update_available.emit(latest_version)
            # 404 u otros códigos se ignoran silenciosamente aquí (ya se manejan en verificación manual)
        except (requests.RequestException, ValueError, KeyError):
            pass


class ManualUpdateChecker(QThread):
    finished_check = Signal(object)  # dict con claves: status, latest_version, error(optional)

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get('tag_name', '').lstrip('v')
                if latest_version:
                    self.finished_check.emit({
                        'status': 'ok',
                        'latest_version': latest_version
                    })
                else:
                    self.finished_check.emit({
                        'status': 'error',
                        'error': 'Formato de release inválido'
                    })
            elif response.status_code == 404:
                self.finished_check.emit({'status': 'no_releases'})
            else:
                self.finished_check.emit({
                    'status': 'error',
                    'error': f"Código HTTP {response.status_code}"
                })
        except (requests.RequestException, ValueError, KeyError) as e:
            self.finished_check.emit({'status': 'error', 'error': str(e)})

class ModernButton(QPushButton):
    def __init__(self, text, bg_color="#2196F3", hover_color="#1976D2", text_color="white", parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self._apply_style()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.bg_color};
                color: {self.text_color};
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {self.hover_color};
            }}
            QPushButton:pressed {{
                background-color: {self.hover_color};
                padding-top: 10px;
            }}
            QPushButton:disabled {{
                background-color: #CCCCCC;
                color: #888888;
            }}
        """)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, proxy_ip="127.0.0.1", proxy_port="8080"):
        super().__init__(parent)
        
        # Configuración de la ventana
        self.setWindowTitle("Configuración de Proxy")
        self.setMinimumWidth(400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        # Quitar transparencia para evitar fondo invisible en algunos entornos
        # (si se desea translucidez real, se puede reactivar pero puede interferir con eventos)
        # self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(True)
        
        # Atributos
        self._drag_position = None
        self.proxy_ip = proxy_ip
        self.proxy_port = proxy_port
        self.ip_input = None
        self.port_input = None
        self.result_value = QDialog.Rejected
        self.parent_widget = parent
        
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
                border: none;
                border-radius: 10px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #2196F3;
            }
            QLabel {
                font-size: 13px;
            }
        """)
        
        # Construir la interfaz
        self.setup_ui()
    
    def mousePressEvent(self, event):
        # Permitir mover la ventana al hacer clic y arrastrar
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        # Mover la ventana cuando se arrastra
        if event.buttons() == Qt.LeftButton and self._drag_position is not None:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, _):
        # Resetear la posición de arrastre
        self._drag_position = None
    
    def setup_ui(self):
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barra de título personalizada
        title_bar = QFrame()
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #2196F3;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border: none;
            }
        """)
        title_bar.setFixedHeight(35)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        # Título
        title_label = QLabel("Configuración de Proxy")
        title_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
        """)
        
        # Botón de cerrar
        close_button = QPushButton("✕")
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e81123;
                border-radius: 10px;
            }
        """)
        close_button.clicked.connect(self.reject)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)
        
        # Contenedor para el contenido
        content_container = QWidget()
        content_container.setStyleSheet("background: #FFFFFF; border: none;")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # Grupo de configuración de proxy
        group_box = QGroupBox("Configuración de Proxy")
        group_layout = QFormLayout(group_box)
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(15, 15, 15, 15)
        
        # IP address
        self.ip_input = QLineEdit(self.proxy_ip)
        self.ip_input.setPlaceholderText("Ej: 127.0.0.1")
        group_layout.addRow("Dirección IP:", self.ip_input)
        
        # Port
        self.port_input = QLineEdit(self.proxy_port)
        # Para validar solo números entre 1-65535
        validator = QIntValidator(1, 65535)
        self.port_input.setValidator(validator)
        self.port_input.setPlaceholderText("Ej: 8080")
        group_layout.addRow("Puerto:", self.port_input)
        
        content_layout.addWidget(group_box)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        cancel_button = ModernButton("Cancelar", "#e0e0e0", "#bdbdbd", "#222222", self)
        cancel_button.clicked.connect(self.reject)
        save_button = ModernButton("Guardar", "#2196F3", "#1976D2", "white", self)
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        content_layout.addLayout(button_layout)
        
        # Add to main layout
        main_layout.addWidget(title_bar)
        main_layout.addWidget(content_container)
    
    def accept(self):
        self.proxy_ip = self.ip_input.text().strip()
        self.proxy_port = self.port_input.text().strip()
        self.result_value = QDialog.Accepted
        super().accept()

    def reject(self):
        self.result_value = QDialog.Rejected
        super().reject()
    
    def get_result(self):
        return self.result_value, self.proxy_ip, self.proxy_port


class ProxyManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Proxy Manager")
        self.setMinimumSize(450, 300)
        # Quitar el marco estándar de la ventana
        self.setWindowFlags(Qt.FramelessWindowHint)
        # Hacer transparente el fondo para bordes redondeados
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Permitir mover la ventana
        self._drag_position = None
        # Para almacenar el diálogo de configuración
        self.settings_dialog = None
        
        # Inicializar configuraciones
        self.settings = QSettings("ProxyManager", "SimpleProxyApp")

        # Atributos para verificación manual de actualizaciones
        self._manual_update_thread = None
        self._wait_dialog = None
        
        # Intentar establecer el icono de la ventana
        try:
            window_icon_path = str(Path(__file__).parent / "icon.ico")
            self.setWindowIcon(QIcon(window_icon_path))
        except (FileNotFoundError, OSError):
            pass
            
        # Aplicar estilo global a la aplicación
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FAFAFA;
                border: none;
                border-radius: 10px;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #333333;
            }
        """)
        
        # Comprobar actualizaciones
        self.check_for_updates()
        
        # Load settings
        self.proxy_ip = self.settings.value("proxy_ip", "127.0.0.1")
        self.proxy_port = self.settings.value("proxy_port", "8080")
        
        # Check current proxy status
        self.proxy_enabled = self.is_proxy_enabled()
        
        # Create UI
        self.setup_ui()
        
        # Update UI state based on proxy status
        self.update_ui_state()
    
    def check_for_updates(self):
        """Inicia el proceso de verificación de actualizaciones en segundo plano"""
        # Inicializar el objeto de configuración en caso de que aún no se haya hecho
        if not hasattr(self, 'settings'):
            self.settings = QSettings("ProxyManager", "SimpleProxyApp")
            
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.start()
    
    def on_update_available(self, new_version):
        """Procesa una actualización disponible y muestra la notificación si es necesario"""
        # Comprobar si el usuario ha elegido omitir esta versión
        skip_version = self.settings.value("skip_update_version", "")
        
        # Si el usuario no ha elegido omitir esta versión, mostrar la notificación
        if skip_version != new_version:
            self.show_update_notification(new_version)
    
    def show_update_notification(self, new_version):
        """Muestra una notificación cuando hay una actualización disponible"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Actualización Disponible")
        msg.setText(f"Hay una nueva versión disponible: v{new_version}")
        msg.setInformativeText(f"Estás usando la versión v{APP_VERSION}. ¿Deseas visitar el sitio de descarga ahora?\n\nPuedes actualizar más tarde desde el menú principal.")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        # Añadir checkbox para recordar la decisión
        skip_checkbox = QCheckBox("No volver a mostrar para esta versión")
        msg.setCheckBox(skip_checkbox)
        
        # Aplicar estilos al mensaje
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #FAFAFA;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QCheckBox {
                color: #555555;
            }
        """)
        result = msg.exec()

        # Si el usuario marcó la casilla, guardar la preferencia
        if skip_checkbox.isChecked():
            self.settings.setValue("skip_update_version", new_version)

        if result == QMessageBox.Yes:
            # Abrir el navegador en la página de releases del repositorio
            url = f"https://github.com/{GITHUB_REPO}/releases/latest"
            try:
                subprocess.Popen(["start", url], shell=True)

                # Mostrar mensaje de confirmación
                confirm_msg = QMessageBox(self)
                confirm_msg.setWindowTitle("Actualización en Curso")
                confirm_msg.setText("Se ha abierto el navegador para descargar la nueva versión.")
                confirm_msg.setInformativeText("Recuerda cerrar esta aplicación antes de instalar la actualización.")
                confirm_msg.setIcon(QMessageBox.Information)
                confirm_msg.exec()

            except (OSError, subprocess.SubprocessError):
                # Si hay algún error al abrir el navegador, mostrar la URL
                fallback_msg = QMessageBox(self)
                fallback_msg.setWindowTitle("Enlace de Descarga")
                fallback_msg.setText("Visita la siguiente URL para descargar la nueva versión:")
                fallback_msg.setInformativeText(url)
                fallback_msg.setIcon(QMessageBox.Information)
                fallback_msg.exec()
    
    def mousePressEvent(self, event):
        # Permitir mover la ventana al hacer clic y arrastrar
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        # Mover la ventana cuando se arrastra
        if event.buttons() == Qt.LeftButton and self._drag_position is not None:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, _):
        # Resetear la posición de arrastre
        self._drag_position = None
    
    def check_updates_manually(self):
        """Verifica actualizaciones manualmente (asíncrono) evitando congelar la UI"""
        # Evitar lanzar múltiples verificaciones simultáneas
        if self._manual_update_thread and self._manual_update_thread.isRunning():
            return
        # Crear diálogo de progreso cancelable
        from PySide6.QtWidgets import QProgressDialog
        self._wait_dialog = QProgressDialog("Verificando si hay actualizaciones disponibles...", "Cancelar", 0, 0, self)
        self._wait_dialog.setWindowTitle("Verificando Actualizaciones")
        self._wait_dialog.setWindowModality(Qt.WindowModal)
        self._wait_dialog.setCancelButtonText("Cancelar")
        self._wait_dialog.canceled.connect(self._cancel_manual_update)
        self._wait_dialog.show()

        # Lanzar hilo
        self._manual_update_thread = ManualUpdateChecker()
        self._manual_update_thread.finished_check.connect(self._on_manual_update_finished)
        self._manual_update_thread.start()

    def _on_manual_update_finished(self, result: dict):
        # Cerrar cuadro de progreso si existe
        if self._wait_dialog:
            self._wait_dialog.close()
            self._wait_dialog = None

        status = result.get('status')
        if status == 'ok':
            latest = result.get('latest_version')
            if latest and compare_versions(latest, APP_VERSION) > 0:
                self.settings.remove("skip_update_version")
                self.show_update_notification(latest)
            else:
                no_updates_msg = QMessageBox(self)
                no_updates_msg.setWindowTitle("No Hay Actualizaciones")
                no_updates_msg.setText(f"Ya estás utilizando la última versión: v{APP_VERSION}")
                no_updates_msg.setIcon(QMessageBox.Information)
                no_updates_msg.exec()
        elif status == 'no_releases':
            no_rel = QMessageBox(self)
            no_rel.setWindowTitle("Sin Releases")
            no_rel.setText("El repositorio no tiene releases publicadas todavía.")
            no_rel.setInformativeText("Crea una release en GitHub para habilitar la comprobación de versiones.")
            no_rel.setIcon(QMessageBox.Information)
            no_rel.exec()
        else:
            error_msg = QMessageBox(self)
            error_msg.setWindowTitle("Error")
            error_msg.setText("No se pudo verificar si hay actualizaciones disponibles")
            error_msg.setInformativeText(f"Error: {result.get('error', 'Desconocido')}")
            error_msg.setIcon(QMessageBox.Warning)
            error_msg.exec()

        # Liberar referencia del hilo
        self._manual_update_thread = None

    def _cancel_manual_update(self):
        if self._manual_update_thread and self._manual_update_thread.isRunning():
            # No hay una forma directa y segura de matar el hilo de requests; marcamos cancelación lógica.
            # Simplemente ignoraremos el resultado cuando llegue si el usuario canceló.
            self._manual_update_thread.finished_check.disconnect(self._on_manual_update_finished)
        if self._wait_dialog:
            self._wait_dialog.close()
            self._wait_dialog = None
        # Mostrar mensaje de cancelación (opcional)
        cancel_msg = QMessageBox(self)
        cancel_msg.setWindowTitle("Cancelado")
        cancel_msg.setText("La verificación de actualizaciones fue cancelada.")
        cancel_msg.setIcon(QMessageBox.Information)
        cancel_msg.exec()
    
    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Barra de título personalizada
        title_bar = QFrame()
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #2196F3;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border: none;
            }
        """)
        title_bar.setFixedHeight(35)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        # Título
        title_label = QLabel("Simple Proxy Manager")
        title_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
        """)
        
        # Botones de la barra de título
        close_button = QPushButton("✕")
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e81123;
                border-radius: 10px;
            }
        """)
        close_button.clicked.connect(self.close)
        
        minimize_button = QPushButton("−")
        minimize_button.setFixedSize(20, 20)
        minimize_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 10px;
            }
        """)
        minimize_button.clicked.connect(self.showMinimized)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(minimize_button)
        title_bar_layout.addWidget(close_button)
        
        # Crear contenedor con sombra
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #E0E0E0;
            }
        """)
        
        # Aplicar sombra al contenedor
        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)
        
        # Layout para el contenedor
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(25, 25, 25, 25)
        container_layout.setSpacing(15)
        
        # Status label con un estilo más moderno
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        self.status_label.setFont(font)
        
        # Current proxy info con estilo mejorado
        self.proxy_info_label = QLabel()
        self.proxy_info_label.setAlignment(Qt.AlignCenter)
        proxy_font = QFont("Segoe UI", 12)
        self.proxy_info_label.setFont(proxy_font)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #E0E0E0;")
        
        # Buttons con estilos modernos y mejores colores
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.connect_button = ModernButton("CONECTAR", "#4CAF50", "#388E3C")
        self.connect_button.clicked.connect(self.enable_proxy)
        
        self.disconnect_button = ModernButton("DESCONECTAR", "#F44336", "#D32F2F")
        self.disconnect_button.clicked.connect(self.disable_proxy)
        
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        
        settings_button = ModernButton("CONFIGURACIÓN", "#2196F3", "#1976D2")
        settings_button.clicked.connect(self.open_settings)
        
        # Add widgets to container layout
        container_layout.addWidget(self.status_label)
        container_layout.addWidget(self.proxy_info_label)
        container_layout.addWidget(separator)
        container_layout.addLayout(button_layout)
        container_layout.addWidget(settings_button)
        
        # Botón para verificar actualizaciones
        check_updates_button = ModernButton("VERIFICAR ACTUALIZACIONES", "#FF9800", "#F57C00")
        check_updates_button.clicked.connect(self.check_updates_manually)
        container_layout.addWidget(check_updates_button)
        
        # Add title bar and container to main layout
        main_layout.addWidget(title_bar)
        main_layout.addWidget(container)
        
        # Set central widget
        self.setCentralWidget(main_widget)
    
    def update_ui_state(self):
        # Update status label
        if self.proxy_enabled:
            self.status_label.setText("CONECTADO")
            self.status_label.setStyleSheet("""
                color: #4CAF50;
                background-color: #E8F5E9;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            """)
        else:
            self.status_label.setText("DESCONECTADO")
            self.status_label.setStyleSheet("""
                color: #F44336;
                background-color: #FFEBEE;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            """)
        
        # Update proxy info with better styling
        self.proxy_info_label.setText(f"Proxy: {self.proxy_ip}:{self.proxy_port}")
        self.proxy_info_label.setStyleSheet("""
            color: #555555;
            padding: 10px;
            background-color: #F5F5F5;
            border-radius: 5px;
        """)
        
        # Update button states with smooth transition
        self.connect_button.setEnabled(not self.proxy_enabled)
        self.disconnect_button.setEnabled(self.proxy_enabled)
    
    def open_settings(self):
        settings = QSettings("ProxyManager", "SimpleProxyApp")
        current_ip = settings.value("proxy_ip", "127.0.0.1")
        current_port = settings.value("proxy_port", "8080")
        dlg = SettingsDialog(self, current_ip, current_port)
        dlg.adjustSize()
        # Centrar respecto a la ventana principal
        parent_geom = self.frameGeometry()
        g = dlg.frameGeometry()
        dlg.move(parent_geom.center().x() - g.width() // 2, parent_geom.center().y() - g.height() // 2)
        if dlg.exec() == QDialog.Accepted:
            settings.setValue("proxy_ip", dlg.proxy_ip)
            settings.setValue("proxy_port", dlg.proxy_port)
            self.proxy_ip = dlg.proxy_ip
            self.proxy_port = dlg.proxy_port
            self.update_ui_state()
    
    def on_settings_dialog_finished(self, _):
        # Obtener resultados del diálogo
        result_value, proxy_ip, proxy_port = self.settings_dialog.get_result()
        
        if result_value == QDialog.Accepted:
            # Guardar la configuración
            settings = QSettings("ProxyManager", "SimpleProxyApp")
            settings.setValue("proxy_ip", proxy_ip)
            settings.setValue("proxy_port", proxy_port)
            
            # Actualizar variables locales
            self.proxy_ip = proxy_ip
            self.proxy_port = proxy_port
            
            # Actualizar UI
            self.update_ui_state()
    
    def is_proxy_enabled(self):
        try:
            # Open the Internet Settings registry key
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            
            # Check if proxy is enabled
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            
            return bool(proxy_enable)
        except OSError as e:
            print(f"Error checking proxy status: {e}")
            return False
    
    def get_current_proxy(self):
        try:
            # Open the Internet Settings registry key
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            
            # Get proxy server
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            
            return proxy_server
        except OSError as e:
            print(f"Error getting proxy server: {e}")
            return ""
    
    def enable_proxy(self):
        try:
            # Format proxy server string
            proxy_server = f"{self.proxy_ip}:{self.proxy_port}"
            
            # Open the Internet Settings registry key
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            
            # Enable proxy
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            
            # Set proxy server
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
            
            # Refresh system settings
            self.refresh_system_settings()
            
            # Update status
            self.proxy_enabled = True
            self.update_ui_state()
            
            # Mostrar mensaje más elegante
            QMessageBox.information(
                self, 
                "Proxy Habilitado", 
                f"<h3>¡Conexión Exitosa!</h3><p>Proxy configurado a <b>{proxy_server}</b></p>",
                QMessageBox.Ok
            )
        except OSError as e:
            QMessageBox.critical(
                self,
                "Error",
                f"<h3>No se pudo habilitar el proxy</h3><p>{str(e)}</p>",
                QMessageBox.Ok
            )
    
    def disable_proxy(self):
        try:
            # Open the Internet Settings registry key
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            
            # Disable proxy
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            
            # Refresh system settings
            self.refresh_system_settings()
            
            # Update status
            self.proxy_enabled = False
            self.update_ui_state()
            
            # Mostrar mensaje más elegante
            QMessageBox.information(
                self, 
                "Proxy Deshabilitado", 
                "<h3>Proxy Desactivado</h3><p>La configuración de proxy ha sido deshabilitada correctamente.</p>",
                QMessageBox.Ok
            )
            
        except OSError as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"<h3>No se pudo deshabilitar el proxy</h3><p>{str(e)}</p>",
                QMessageBox.Ok
            )
    
    def refresh_system_settings(self):
        # Notify Windows of settings change
        # This is equivalent to the InternetSetOption API call with INTERNET_OPTION_REFRESH
        try:
            # Run a PowerShell command to refresh settings
            subprocess.run(["powershell", "-Command", "& {(New-Object -ComObject WScript.Shell).SendKeys('^{F5}'); Start-Sleep -Milliseconds 500}"], 
                          capture_output=True, text=True, check=True)
        except (OSError, subprocess.SubprocessError) as e:
            print(f"Error refreshing settings: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Cargar el icono de la aplicación
    try:
        # Intentar cargar el icono desde la ruta relativa
        icon_path = str(Path(__file__).parent / "icon.ico")
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    except (FileNotFoundError, OSError) as e:
        print(f"No se pudo cargar el icono: {e}")
    
    # Establecer estilo de aplicación moderno
    app.setStyle("Fusion")
    
    # Crear paleta de colores personalizada
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(250, 250, 250))
    palette.setColor(QPalette.WindowText, QColor(50, 50, 50))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(50, 50, 50))
    palette.setColor(QPalette.Text, QColor(50, 50, 50))
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(50, 50, 50))
    palette.setColor(QPalette.Highlight, QColor(33, 150, 243))  # Material Blue
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    # Establecer estilo global
    app.setStyleSheet("""
        QMessageBox {
            background-color: white;
        }
        QMessageBox QLabel {
            color: #333333;
        }
        QMessageBox QPushButton {
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QMessageBox QPushButton:hover {
            background-color: #1976D2;
        }
        QMessageBox QPushButton:pressed {
            background-color: #0D47A1;
        }
    """)
    
    # Create and show the main window
    window = ProxyManager()
    window.show()
    
    sys.exit(app.exec())