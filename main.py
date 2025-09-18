# -*- coding: utf-8 -*-
"""
Interfaz reescrita con PySide6 (Qt). Mantiene la lógica de lanzado de gcloud/ssh en un QThread
y comunica el log y el estado mediante señales.
"""
from __future__ import annotations

import sys
import subprocess
from typing import Optional

from PySide6 import QtCore, QtWidgets


class SSHWorker(QtCore.QThread):
    """Worker que ejecuta el comando gcloud compute ssh y emite logs y estado."""
    log = QtCore.Signal(str)
    connected = QtCore.Signal(bool)

    def __init__(self, project_id: str, zone: str, vm_name: str):
        super().__init__()
        self.project_id = project_id
        self.zone = zone
        self.vm_name = vm_name
        self._proc: Optional[subprocess.Popen] = None
        self._stop_requested = False

    def run(self) -> None:
        try:
            cmd = [
                "gcloud",
                "compute",
                "ssh",
                f"--project={self.project_id}",
                f"--zone={self.zone}",
                self.vm_name,
                "--",
                "-D",
                "8080",
                "-N",
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
            self.log.emit("Error: 'gcloud' no se encuentra en PATH. Instala Google Cloud SDK.")
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
        self.setWindowTitle("Proxy Personal con Google Cloud")
        self.resize(480, 420)

        self.worker: Optional[SSHWorker] = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.project_input = QtWidgets.QLineEdit()
        self.zone_input = QtWidgets.QLineEdit()
        self.vm_input = QtWidgets.QLineEdit()
        form.addRow("ID de Proyecto:", self.project_input)
        form.addRow("Zona:", self.zone_input)
        form.addRow("Nombre de Instancia:", self.vm_input)
        layout.addLayout(form)

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

        self.connect_btn.clicked.connect(self.start_connection)
        self.disconnect_btn.clicked.connect(self.stop_connection)

    def append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def start_connection(self) -> None:
        if self.worker is not None:
            QtWidgets.QMessageBox.information(self, "Info", "Ya hay una conexión en curso.")
            return

        pid = self.project_input.text().strip()
        zone = self.zone_input.text().strip()
        vm = self.vm_input.text().strip()
        if not pid or not zone or not vm:
            QtWidgets.QMessageBox.critical(self, "Error", "Todos los campos son obligatorios.")
            return

        self.connect_btn.setEnabled(False)
        self.append_log("Intentando conectar...")

        self.worker = SSHWorker(pid, zone, vm)
        self.worker.log.connect(self.append_log)
        self.worker.connected.connect(self.on_connected)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_connected(self, ok: bool) -> None:
        if ok:
            self.append_log("Conexión SSH establecida. Configura tu navegador para usar SOCKS5 localhost:8080")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.append_log("No se pudo establecer la conexión SSH.")
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
