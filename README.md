# Proxy Personal con AWS EC2

Una aplicación gráfica desarrollada con PySide6 (Qt) para establecer un túnel SSH a una instancia EC2 de AWS y configurar un proxy SOCKS5 local en el puerto 8080.

## Características

- Interfaz gráfica para gestionar conexiones a instancias EC2
- Soporte para autenticación mediante claves SSH
- Configuración de proxy SOCKS5 en localhost:8080
- Verificación de estado de instancias EC2
- Soporte para credenciales AWS desde variables de entorno o la interfaz

## Requisitos

- Python 3.7+
- PySide6
- boto3 (AWS SDK para Python)
- Una instancia EC2 en ejecución con acceso SSH configurado
- Un archivo de clave SSH (.pem) para autenticación

## Instalación

1. Clona este repositorio
2. Instala las dependencias:
   ```
   pip install -r requirements.txt
   ```

## Uso

1. Ejecuta la aplicación:
   ```
   python main.py
   ```
2. Ingresa tus credenciales de AWS (Access Key ID, Secret Access Key y Región) o configura las variables de entorno correspondientes.
3. Proporciona el ID de la instancia EC2 y la ruta a tu archivo de clave SSH.
4. Haz clic en "Conectar" para establecer el túnel SSH.
5. Configura tu navegador para usar un proxy SOCKS5 en localhost:8080.

## Variables de Entorno

- `AWS_ACCESS_KEY_ID`: Tu clave de acceso de AWS
- `AWS_SECRET_ACCESS_KEY`: Tu clave secreta de AWS
- `AWS_REGION`: La región de AWS donde se encuentra tu instancia EC2
