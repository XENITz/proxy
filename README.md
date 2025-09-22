# Simple Proxy Manager

Una aplicación sencilla y elegante para gestionar la configuración del proxy de Windows.

## Características

- Interfaz de usuario moderna y atractiva
- Activar/desactivar rápidamente la configuración del proxy del sistema
- Configurar la dirección IP y el puerto del proxy
- Verificación automática de actualizaciones
- Diseño minimalista y fácil de usar

## Requisitos

- Windows (ya que modifica el registro de Windows)
- Conexión a Internet (opcional, para verificar actualizaciones)
- Permisos de administrador (para modificar la configuración del proxy)

## Instalación

### Método 1: Ejecutable

1. Descargue el archivo `Simple Proxy Manager.exe` de la sección de releases
2. Ejecute la aplicación directamente, no requiere instalación

### Método 2: Desde el código fuente

1. Clone o descargue este repositorio
2. Cree un entorno virtual: `python -m venv .venv`
3. Active el entorno virtual: `.\.venv\Scripts\activate`
4. Instale las dependencias: `pip install PySide6 requests`

## Uso

Para ejecutar la aplicación:

```bash
python proxy_app.py
```

O simplemente haga doble clic en `iniciar_proxy_manager.bat` o en el ejecutable si utilizó ese método.

### Instrucciones de uso

1. **Conectar**: Activa la configuración de proxy del sistema con la IP y puerto especificados
2. **Desconectar**: Desactiva la configuración de proxy del sistema
3. **Configuración**: Abre un diálogo para cambiar la IP y puerto del proxy

## Actualizaciones

La aplicación verificará automáticamente si hay nuevas versiones disponibles al iniciar. Si hay una actualización disponible, se le notificará y podrá elegir si desea descargarla.

## Empaquetado (para desarrolladores)

Para crear un ejecutable independiente:

1. Ejecute el script `empaquetar.bat`
2. El ejecutable se generará en la carpeta `dist`

## Cómo funciona

La aplicación modifica la configuración del proxy en el registro de Windows (bajo `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings`), que es donde Windows almacena la configuración del proxy del sistema.

## Notas

- Esta aplicación requiere permisos para modificar el registro de Windows
- Los cambios en la configuración del proxy afectan a todo el sistema
- La configuración se guarda entre sesiones