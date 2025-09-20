# -*- coding: utf-8 -*-
"""
Interfaz reescrita con PySide6 (Qt). Mantiene la lógica de lanzado de ssh en un QThread
y comunica el log y el estado mediante señales.
"""
from __future__ import annotations

import sys
import subprocess
import os
import boto3
from typing import Optional

from PySide6 import QtCore, QtWidgets


class AWSCredentialsManager:
    """Gestor de credenciales de AWS."""
    
    def __init__(self):
        self.aws_access_key_id = ""
        self.aws_secret_access_key = ""
        self.region_name = ""
        self.initialized = False
        
    def init_from_env(self) -> bool:
        """Inicializa credenciales desde variables de entorno."""
        try:
            self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
            self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
            self.region_name = os.environ.get("AWS_REGION", "")
            self.initialized = bool(self.aws_access_key_id and self.aws_secret_access_key)
            return self.initialized
        except Exception:
            return False
            
    def init_from_values(self, access_key: str, secret_key: str, region: str) -> bool:
        """Inicializa credenciales con valores proporcionados."""
        self.aws_access_key_id = access_key
        self.aws_secret_access_key = secret_key
        self.region_name = region
        self.initialized = bool(self.aws_access_key_id and self.aws_secret_access_key)
        return self.initialized
        
    def get_client(self, service_name: str):
        """Retorna un cliente de boto3 para el servicio especificado."""
        if not self.initialized:
            raise ValueError("AWS credentials not initialized")
        return boto3.client(
            service_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        
    def get_ec2_client(self):
        """Retorna un cliente de EC2."""
        return self.get_client("ec2")


class SSHWorker(QtCore.QThread):
    """Worker que ejecuta el comando ssh y emite logs y estado."""
    log = QtCore.Signal(str)
    connected = QtCore.Signal(bool)

    def __init__(self, region: str, instance_id: str, key_path: str, username: str = "ec2-user"):
        super().__init__()
        self.region = region
        self.instance_id = instance_id
        self.key_path = key_path
        self.username = username
        self._proc: Optional[subprocess.Popen] = None
        self._stop_requested = False
        self.aws_creds = AWSCredentialsManager()
        
    def get_instance_public_dns(self) -> Optional[str]:
        """Obtiene el DNS público de la instancia."""
        try:
            if not self.aws_creds.initialized:
                self.aws_creds.init_from_env()
                
            ec2 = self.aws_creds.get_ec2_client()
            response = ec2.describe_instances(InstanceIds=[self.instance_id])
            
            reservations = response.get('Reservations', [])
            if not reservations:
                self.log.emit(f"No se encontró la instancia {self.instance_id}")
                return None
                
            instances = reservations[0].get('Instances', [])
            if not instances:
                self.log.emit(f"No se encontró la instancia {self.instance_id}")
                return None
                
            instance = instances[0]
            public_dns = instance.get('PublicDnsName')
            
            if not public_dns:
                self.log.emit(f"La instancia {self.instance_id} no tiene un DNS público")
                return None
                
            return public_dns
        except Exception as e:
            self.log.emit(f"Error al obtener DNS público: {e}")
            return None

    def run(self) -> None:
        try:
            # Obtener el DNS público de la instancia
            public_dns = self.get_instance_public_dns()
            if not public_dns:
                self.connected.emit(False)
                return
                
            self.log.emit(f"Conectando a {public_dns}...")
            
            # Crear el comando SSH
            cmd = [
                "ssh",
                "-i", self.key_path,
                "-D", "8080",
                "-N",
                f"{self.username}@{public_dns}"
            ]

            self.log.emit("Iniciando proceso SSH...")
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

            # Leer stderr en tiempo real
            assert self._proc.stderr is not None
            for line in self._proc.stderr:
                if self._stop_requested:
                    break
                text = line.rstrip()
                self.log.emit(f"SSH: {text}")
                # heurística para detectar que la conexión se estableció
                if "Warning" in text or "authorized_keys" in text or "Connecting" in text:
                    self.connected.emit(True)
            # si salimos del bucle sin haber pedido stop, verificar el returncode
            if not self._stop_requested:
                rc = self._proc.poll()
                if rc is None:
                    # proceso sigue vivo -> lo consideramos conectado (fallback)
                    self.connected.emit(True)
                else:
                    # terminó con error
                    err = self._proc.stderr.read() if self._proc.stderr is not None else ""
                    self.log.emit(f"SSH finalizó (rc={rc}): {err.strip()}")
                    self.connected.emit(False)

        except FileNotFoundError:
            self.log.emit("Error: 'ssh' no se encuentra en PATH. Verifica que SSH esté instalado.")
            self.connected.emit(False)
        except Exception as e:
            self.log.emit(f"Error inesperado en SSHWorker: {e}")
            self.connected.emit(False)

    def stop(self) -> None:
        self._stop_requested = True
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        # esperar al hilo que termine
        self.wait(2000)


class MainWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Proxy Personal con AWS EC2")
        self.resize(520, 480)

        self.worker: Optional[SSHWorker] = None
        self.aws_creds = AWSCredentialsManager()

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # Credenciales AWS
        creds_group = QtWidgets.QGroupBox("Credenciales AWS")
        creds_layout = QtWidgets.QFormLayout()
        
        self.access_key_input = QtWidgets.QLineEdit()
        self.access_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.secret_key_input = QtWidgets.QLineEdit()
        self.secret_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.region_input = QtWidgets.QLineEdit()
        
        creds_layout.addRow("Access Key ID:", self.access_key_input)
        creds_layout.addRow("Secret Access Key:", self.secret_key_input)
        creds_layout.addRow("Región:", self.region_input)
        
        creds_group.setLayout(creds_layout)
        layout.addWidget(creds_group)

        # Detalles de la instancia
        instance_group = QtWidgets.QGroupBox("Instancia EC2")
        instance_layout = QtWidgets.QFormLayout()
        
        self.instance_id_input = QtWidgets.QLineEdit()
        self.key_path_input = QtWidgets.QLineEdit()
        self.browse_btn = QtWidgets.QPushButton("Buscar...")
        self.username_input = QtWidgets.QLineEdit("ec2-user")
        
        browse_layout = QtWidgets.QHBoxLayout()
        browse_layout.addWidget(self.key_path_input)
        browse_layout.addWidget(self.browse_btn)
        
        instance_layout.addRow("ID de Instancia:", self.instance_id_input)
        instance_layout.addRow("Ruta a clave SSH:", browse_layout)
        instance_layout.addRow("Usuario:", self.username_input)
        
        instance_group.setLayout(instance_layout)
        layout.addWidget(instance_group)

        # Botones de conexión
        btn_layout = QtWidgets.QHBoxLayout()
        self.connect_btn = QtWidgets.QPushButton("Conectar")
        self.disconnect_btn = QtWidgets.QPushButton("Desconectar")
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.appendPlainText("Estado: Desconectado")
        layout.addWidget(self.log_view)

        # Conectar señales
        self.connect_btn.clicked.connect(self.start_connection)
        self.disconnect_btn.clicked.connect(self.stop_connection)
        self.browse_btn.clicked.connect(self.browse_key_file)

    def browse_key_file(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Seleccionar clave SSH", "", "Archivos de clave (*.pem *.key);;Todos los archivos (*)"
        )
        if file_path:
            self.key_path_input.setText(file_path)
            
    def append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def test_aws_connection(self, region: str, instance_id: str) -> bool:
        """Prueba la conexión a AWS y verifica que la instancia existe."""
        try:
            if not self.aws_creds.initialized:
                return False
                
            self.append_log("Verificando conexión a AWS...")
            ec2 = self.aws_creds.get_ec2_client()
            
            # Intentar describir la instancia
            response = ec2.describe_instances(InstanceIds=[instance_id])
            
            if not response.get('Reservations'):
                self.append_log(f"No se encontró la instancia {instance_id}")
                return False
                
            instance = response['Reservations'][0]['Instances'][0]
            state = instance.get('State', {}).get('Name')
            
            if state != 'running':
                self.append_log(f"La instancia {instance_id} no está en ejecución (estado: {state})")
                return False
                
            self.append_log(f"Instancia {instance_id} encontrada y en ejecución")
            return True
            
        except Exception as e:
            self.append_log(f"Error al verificar instancia: {e}")
            return False
    
    def start_connection(self) -> None:
        if self.worker is not None:
            QtWidgets.QMessageBox.information(self, "Info", "Ya hay una conexión en curso.")
            return

        # Inicializar credenciales AWS
        access_key = self.access_key_input.text().strip()
        secret_key = self.secret_key_input.text().strip()
        region = self.region_input.text().strip()
        
        # Verificar credenciales
        if not access_key or not secret_key or not region:
            # Intentar usar variables de entorno si no se proporcionan
            if not self.aws_creds.init_from_env():
                QtWidgets.QMessageBox.critical(
                    self, "Error", 
                    "Debes proporcionar las credenciales de AWS o configurar las variables de entorno."
                )
                return
        else:
            self.aws_creds.init_from_values(access_key, secret_key, region)
            
        # Verificar detalles de la instancia
        instance_id = self.instance_id_input.text().strip()
        key_path = self.key_path_input.text().strip()
        username = self.username_input.text().strip()
        
        if not instance_id or not key_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Se requiere ID de instancia y ruta a la clave SSH.")
            return
            
        # Verificar que la clave existe
        if not os.path.isfile(key_path):
            QtWidgets.QMessageBox.critical(self, "Error", f"La clave SSH no existe: {key_path}")
            return
            
        # Probar la conexión a AWS
        if not self.test_aws_connection(region, instance_id):
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                "No se pudo verificar la instancia. Verifica tus credenciales y el ID de instancia."
            )
            return

        self.connect_btn.setEnabled(False)
        self.append_log("Intentando conectar...")

        # Iniciar la conexión
        self.worker = SSHWorker(region, instance_id, key_path, username)
        self.worker.log.connect(self.append_log)
        self.worker.connected.connect(self.on_connected)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_connected(self, ok: bool) -> None:
        if ok:
            self.append_log("Conexión SSH a EC2 establecida. Configura tu navegador para usar SOCKS5 localhost:8080")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.append_log("No se pudo establecer la conexión SSH a EC2.")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            # limpiar worker si terminó con fallo
            if self.worker is not None and not self.worker.isRunning():
                self.worker = None

    def on_finished(self) -> None:
        # llamado cuando el thread termina
        if self.worker is not None and not self.worker.isRunning():
            self.append_log("Worker finalizado.")
            self.worker = None
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

    def stop_connection(self) -> None:
        if self.worker is None:
            return
        self.append_log("Terminando conexión...")
        self.worker.stop()
        # on_finished limpiará el estado


def main() -> int:
    # en Windows mantenemos chcp para evitar problemas de encoding en consola
    if sys.platform.startswith("win"):
        try:
            subprocess.run(["chcp", "65001"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
