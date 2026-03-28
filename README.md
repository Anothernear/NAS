---

# 🚀 NanoNAS + Halo CE Server 🛡️

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0+-black?style=for-the-badge&logo=flask)
![Debian](https://img.shields.io/badge/Debian-Server-red?style=for-the-badge&logo=debian)
![Wine](https://img.shields.io/badge/Wine-Emulator-722131?style=for-the-badge&logo=wine)

Una solución integral de **NAS (Network Attached Storage)** y servidor de juegos privada, diseñada específicamente para hardware de bajos recursos (Intel Atom / 2GB RAM). 

Este proyecto transforma una laptop antigua en un servidor funcional con gestión de archivos segura, cuotas de disco y un servidor de **Halo Custom Edition** automatizado.

---

## ✨ Características Principales

* **Autogestión de Infraestructura:** El script inicializa carpetas, base de datos y logs automáticamente.
* **Seguridad Nivel Producción:** * Cifrado de contraseñas con **Bcrypt**.
    * Protección contra ataques de fuerza bruta (**Flask-Limiter**).
    * Cabeceras de seguridad y políticas CSP con **Talisman**.
    * Protección **CSRF** en todas las peticiones.
* **Servidor Halo CE:** Ejecución automática mediante Wine con servicio de rescate en caso de caídas.
* **Optimización de Recursos:** Logs rotativos para evitar el llenado del almacenamiento y configuración de procesos ligera para CPUs de un solo núcleo.

---

## 🛠️ Requisitos del Sistema

1.  **Hardware:** Recomendado para laptops tipo Netbook (ej. Acer Aspire One) o Single Board Computers.
2.  **SISTEMA:** Debian 12 / Ubuntu 22.04 / Parrot OS.
3.  **Archivos:** Debes tener el archivo `HaloCE.zip` en la raíz del proyecto antes de instalar.

---

## 🚀 Guía de Instalación Paso a Paso

### 1. Clonar y Preparar
Clona el repositorio en tu servidor:
```bash
git clone [https://github.com/Anothernear/NAS.git](https://github.com/Anothernear/NAS.git)
cd NAS


### 2. Ejecutar el Instalador Automático
El archivo `setup.sh` se encargará de instalar Wine, Python, crear el entorno virtual, configurar los servicios de sistema (`systemd`) y descomprimir Halo:
```bash
chmod +x setup.sh
./setup.sh
```

### 3. Configuración del Administrador (Modo Setup)
Por seguridad, el primer usuario (Admin) debe crearse manualmente desde la terminal. Esto evita credenciales por defecto:
```bash
source /srv/app/venv/bin/activate
python3 app.py
```
> **Sigue las instrucciones:** Ingresa el nombre de usuario y contraseña cuando se te solicite. Al finalizar, presiona `Ctrl+C`.

### 4. Lanzamiento Final
Inicia el servicio del NAS:
```bash
sudo systemctl start nas_app
```

---

## 📂 Estructura del Servidor

```text
/srv/app/
├── app.py              # Backend del NAS (Flask)
├── users.db            # Base de datos SQLite (Usuarios y Roles)
├── nas_app.log         # Historial de acciones y seguridad
├── nas/
│   ├── users/          # Carpetas privadas de cada usuario
│   └── public/         # Contiene el HaloCE.zip para descarga web
└── halo_server/        # Archivos del juego ejecutados por Wine
```

---

## ⚙️ Gestión de Servicios (Systemd)

El sistema utiliza servicios para asegurar que el NAS y Halo siempre estén activos, incluso tras un reinicio:

| Comando | Descripción |
| :--- | :--- |
| `sudo systemctl status nas_app` | Verifica si la web del NAS está en línea. |
| `sudo systemctl restart halo_server` | Reinicia el servidor de Halo CE. |
| `journalctl -u nas_app -f` | Ver intentos de login y subidas en tiempo real. |

---

file:///home/fabian/Im%C3%A1genes/Capturas%20de%20pantalla/Captura%20desde%202026-03-27%2016-51-41.png

Ejemplo de server.

## Puedes descargar el HALOCE desde https://halocustomedition.github.io/Halo/
