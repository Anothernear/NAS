#!/bin/bash

# --- CONFIGURACIÓN ---
APP_DIR="/srv/app"
HALO_DIR="$APP_DIR/halo_server"
ZIP_SOURCE="HaloCE.zip" # El nombre de tu archivo zip
USER_SYSTEM=$(whoami)

echo "[!] Iniciando configuración automatizada (NAS + Halo CE)..."

# 1. Instalar dependencias del sistema
echo "[1/6] Instalando paquetes (Python, Wine, Unzip)..."
sudo apt update
sudo apt install -y python3-venv python3-pip wine unzip nginx gunicorn

# 2. Crear estructura de directorios
echo "[2/6] Creando estructura de directorios en $APP_DIR..."
sudo mkdir -p $APP_DIR/nas/users
sudo mkdir -p $APP_DIR/nas/public
sudo mkdir -p $HALO_DIR
sudo chown -R $USER_SYSTEM:$USER_SYSTEM $APP_DIR

# 3. Automatización de Halo CE
echo "[3/6] Gestionando archivos de Halo..."
if [ -f "$ZIP_SOURCE" ]; then
    # Copiar a la carpeta pública del NAS para que Flask lo pueda servir
    cp "$ZIP_SOURCE" "$APP_DIR/nas/public/HaloCE.zip"
    
    # Descomprimir en la carpeta del servidor para ejecutarlo con Wine
    echo "[!] Descomprimiendo Halo en $HALO_DIR..."
    unzip -q "$ZIP_SOURCE" -d "$HALO_DIR"
    echo "[OK] Halo descomprimido correctamente."
else
    echo "[ADVERTENCIA] No se encontró $ZIP_SOURCE en la carpeta actual."
    echo "Recuerda colocarlo manualmente en $APP_DIR/nas/public/ y descomprimirlo en $HALO_DIR"
fi

# 4. Configurar entorno de Python y Flask
echo "[4/6] Configurando entorno virtual y dependencias..."
python3 -m venv $APP_DIR/venv
source $APP_DIR/venv/bin/activate
pip install flask flask-login flask-wtf flask-talisman flask-limiter bcrypt werkzeug gunicorn

# 5. Configuración de Servicios (Systemd)
echo "[5/6] Creando servicios del sistema..."

# Servicio para la Web NAS
sudo bash -c "cat > /etc/systemd/system/nas_app.service <<EOF
[Unit]
Description=Servidor NAS Flask
After=network.target

[Service]
User=$USER_SYSTEM
WorkingDirectory=$APP_DIR
Environment=\"PATH=$APP_DIR/venv/bin\"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF"

# Servicio para el Servidor de Halo
sudo bash -c "cat > /etc/systemd/system/halo_server.service <<EOF
[Unit]
Description=Servidor de Halo CE via Wine
After=network.target

[Service]
User=$USER_SYSTEM
WorkingDirectory=$HALO_DIR
# Se asume que el ejecutable es haloceded.exe
ExecStart=/usr/bin/wine haloceded.exe -nogui
Restart=always

[Install]
WantedBy=multi-user.target
EOF"

# 6. Activación
echo "[6/6] Activando servicios..."
sudo systemctl daemon-reload
sudo systemctl enable nas_app
sudo systemctl enable halo_server
sudo systemctl start nas_app

echo "========================================================="
echo "[SISTEMA LISTO]"
echo "1. El NAS ya está corriendo en el puerto 5000."
echo "2. El servidor de Halo se iniciará automáticamente."
echo "3. IMPORTANTE: Ejecuta 'source $APP_DIR/venv/bin/activate && python3 $APP_DIR/app.py'"
echo "   una vez para configurar tu usuario ADMIN por primera vez."
echo "========================================================="
