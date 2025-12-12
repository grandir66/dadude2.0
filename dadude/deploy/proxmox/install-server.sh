#!/bin/bash
#
# DaDude Server - Installer per Proxmox VE
# Crea un container LXC con il server DaDude
#
# Uso: curl -sSL https://raw.githubusercontent.com/grandir66/Dadude/main/dadude/deploy/proxmox/install-server.sh | bash -s -- [OPZIONI]
#
# Opzioni:
#   --ctid ID             ID container Proxmox (default: prossimo disponibile)
#   --hostname NAME       Hostname container (default: dadude-server)
#   --ip CIDR             IP statico (es: 192.168.1.100/24)
#   --gateway IP          Gateway
#   --storage STORAGE     Storage Proxmox (default: local-lvm)
#   --memory MB           RAM in MB (default: 1024)
#   --disk GB             Disco in GB (default: 8)
#   --dude-host IP        IP del Dude Server MikroTik
#   --dude-user USER      Username Dude (default: admin)
#   --dude-pass PASS      Password Dude
#

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Valori default
CTID=""
HOSTNAME="dadude-server"
BRIDGE="vmbr0"
STORAGE="local-lvm"
TEMPLATE_STORAGE="local"
MEMORY=1024
DISK=8
IP_CONFIG="dhcp"
GATEWAY=""
DUDE_HOST=""
DUDE_USER="admin"
DUDE_PASS=""
TEMPLATE="debian-12-standard"

# Parse argomenti
while [[ $# -gt 0 ]]; do
    case $1 in
        --ctid) CTID="$2"; shift 2 ;;
        --hostname) HOSTNAME="$2"; shift 2 ;;
        --ip) IP_CONFIG="$2"; shift 2 ;;
        --gateway) GATEWAY="$2"; shift 2 ;;
        --bridge) BRIDGE="$2"; shift 2 ;;
        --storage) STORAGE="$2"; shift 2 ;;
        --memory) MEMORY="$2"; shift 2 ;;
        --disk) DISK="$2"; shift 2 ;;
        --dude-host) DUDE_HOST="$2"; shift 2 ;;
        --dude-user) DUDE_USER="$2"; shift 2 ;;
        --dude-pass) DUDE_PASS="$2"; shift 2 ;;
        *) echo -e "${RED}Opzione sconosciuta: $1${NC}"; exit 1 ;;
    esac
done

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║    DaDude Server - Proxmox Installer     ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Genera CTID se non specificato
if [ -z "$CTID" ]; then
    CTID=$(pvesh get /cluster/nextid)
fi

echo "Configurazione:"
echo "  CTID:        $CTID"
echo "  Hostname:    $HOSTNAME"
echo "  Storage:     $STORAGE"
echo "  Memory:      ${MEMORY}MB"
echo "  Disk:        ${DISK}GB"
if [ "$IP_CONFIG" != "dhcp" ]; then
    echo "  Network:     $BRIDGE ($IP_CONFIG)"
    echo "  Gateway:     $GATEWAY"
else
    echo "  Network:     $BRIDGE (DHCP)"
fi
echo ""

read -p "Procedere con l'installazione? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installazione annullata"
    exit 0
fi

# Scarica template se non esiste
echo -e "${BLUE}[1/6] Verifico template...${NC}"
TEMPLATE_NAME=""
for t_name in "debian-12-standard" "debian-11-standard" "ubuntu-22.04-standard"; do
    TEMPLATE_PATH=$(pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -i "$t_name" | head -1 | awk '{print $1}' || true)
    if [ -n "$TEMPLATE_PATH" ]; then
        TEMPLATE_NAME="$TEMPLATE_PATH"
        break
    fi
done

if [ -z "$TEMPLATE_NAME" ]; then
    echo "Nessun template trovato. Scarico Debian 12..."
    pveam update > /dev/null 2>&1
    AVAILABLE=$(pveam available | grep -i "debian-12-standard" | head -1 | awk '{print $2}' || true)
    if [ -n "$AVAILABLE" ]; then
        pveam download $TEMPLATE_STORAGE "$AVAILABLE"
        TEMPLATE_NAME="$TEMPLATE_STORAGE:vztmpl/$AVAILABLE"
    else
        echo -e "${RED}Errore: impossibile trovare template Debian${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Template: $TEMPLATE_NAME${NC}"

# Crea container
echo -e "${BLUE}[2/6] Creo container LXC...${NC}"

NET_CONFIG="name=eth0,bridge=$BRIDGE"
if [ "$IP_CONFIG" != "dhcp" ]; then
    NET_CONFIG="$NET_CONFIG,ip=$IP_CONFIG"
    if [ -n "$GATEWAY" ]; then
        NET_CONFIG="$NET_CONFIG,gw=$GATEWAY"
    fi
else
    NET_CONFIG="$NET_CONFIG,ip=dhcp"
fi

pct create $CTID "$TEMPLATE_NAME" \
    --hostname "$HOSTNAME" \
    --storage "$STORAGE" \
    --rootfs "$STORAGE:$DISK" \
    --memory "$MEMORY" \
    --swap 512 \
    --cores 2 \
    --net0 "$NET_CONFIG" \
    --unprivileged 1 \
    --features nesting=1 \
    --start 1

# Attendi avvio
echo -e "${BLUE}[3/6] Attendo avvio container...${NC}"
sleep 10

# Installa dipendenze
echo -e "${BLUE}[4/6] Installo dipendenze...${NC}"
pct exec $CTID -- bash -c "
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git curl
"

# Clona repository e configura
echo -e "${BLUE}[5/6] Installo DaDude Server...${NC}"
pct exec $CTID -- bash -c "
    cd /opt
    git clone https://github.com/grandir66/Dadude.git dadude
    cd dadude/dadude
    
    # Crea virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Crea directory dati
    mkdir -p data
    
    # Crea file .env
    cat > .env << EOF
# DaDude Server Configuration
DATABASE_URL=sqlite:///./data/dadude.db

# Dude Server Connection
DUDE_HOST=${DUDE_HOST:-192.168.30.250}
DUDE_PORT=8728
DUDE_USERNAME=${DUDE_USER:-admin}
DUDE_PASSWORD=${DUDE_PASS:-}
DUDE_USE_SSL=false

# Server Settings
HOST=0.0.0.0
PORT=8000
DEBUG=false
EOF
"

# Crea systemd service
echo -e "${BLUE}[6/6] Configuro servizio systemd...${NC}"
pct exec $CTID -- bash -c '
cat > /etc/systemd/system/dadude.service << "EOF"
[Unit]
Description=DaDude Inventory Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dadude/dadude
Environment=PATH=/opt/dadude/dadude/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/dadude/dadude/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dadude
systemctl start dadude
'

# Ottieni IP
if [ "$IP_CONFIG" != "dhcp" ]; then
    SERVER_IP=$(echo "$IP_CONFIG" | cut -d'/' -f1)
else
    SERVER_IP=$(pct exec $CTID -- hostname -I | awk '{print $1}')
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    ✅ Installazione Completata!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "Container ID:  $CTID"
echo "Hostname:      $HOSTNAME"
echo "Server IP:     $SERVER_IP"
echo "Web UI:        http://$SERVER_IP:8000"
echo ""
echo "Comandi utili:"
echo "  pct enter $CTID                    # Entra nel container"
echo "  pct exec $CTID -- systemctl status dadude"
echo "  pct exec $CTID -- journalctl -u dadude -f"
echo ""

