#!/bin/bash
#
# DaDude v2.0 Server - Installazione Proxmox LXC
# Installa: PostgreSQL + Redis + Backend FastAPI + Frontend Vue.js
#
# Uso:
#   ./install-server-v2.sh --ip 192.168.1.100/24 --gateway 192.168.1.1
#
# Opzioni:
#   --ip CIDR             IP statico (es: 192.168.1.100/24) - richiesto
#   --gateway IP          Gateway - richiesto
#   --ctid ID             ID container Proxmox (default: auto)
#   --hostname NAME       Hostname (default: dadude-server)
#   --bridge BRIDGE       Bridge Proxmox (default: vmbr0)
#   --storage STORAGE     Storage Proxmox (default: local-lvm)
#   --memory MB           RAM in MB (default: 2048)
#   --disk GB             Disco in GB (default: 20)
#   --dns IP              Server DNS (default: 8.8.8.8)
#   --repo URL            Repository Git (default: github.com/grandir66/dadude2.0)
#   --branch BRANCH       Branch Git (default: main)
#   --yes                 Non chiedere conferma
#

# ============================================================
# CONFIGURAZIONE REPOSITORY
# ============================================================
DADUDE_REPO="https://github.com/grandir66/dadude2.0.git"
DADUDE_BRANCH="main"
# ============================================================

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Defaults
CTID=""
HOSTNAME="dadude-server"
BRIDGE="vmbr0"
STORAGE="local-lvm"
MEMORY=2048
DISK=20
IP_ADDRESS=""
GATEWAY=""
DNS="8.8.8.8"
AUTO_YES=false

# Parse argomenti
while [[ $# -gt 0 ]]; do
    case $1 in
        --ip) IP_ADDRESS="$2"; shift 2 ;;
        --gateway) GATEWAY="$2"; shift 2 ;;
        --ctid) CTID="$2"; shift 2 ;;
        --hostname) HOSTNAME="$2"; shift 2 ;;
        --bridge) BRIDGE="$2"; shift 2 ;;
        --storage) STORAGE="$2"; shift 2 ;;
        --memory) MEMORY="$2"; shift 2 ;;
        --disk) DISK="$2"; shift 2 ;;
        --dns) DNS="$2"; shift 2 ;;
        --repo) DADUDE_REPO="$2"; shift 2 ;;
        --branch) DADUDE_BRANCH="$2"; shift 2 ;;
        --yes|-y) AUTO_YES=true; shift ;;
        --help|-h)
            echo "Uso: $0 --ip IP/MASK --gateway GW [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  --ip CIDR           IP statico (es: 192.168.1.100/24) - richiesto"
            echo "  --gateway IP        Gateway - richiesto"
            echo "  --ctid ID           ID container Proxmox"
            echo "  --hostname NAME     Hostname (default: dadude-server)"
            echo "  --bridge BRIDGE     Bridge (default: vmbr0)"
            echo "  --storage NAME      Storage (default: local-lvm)"
            echo "  --memory MB         RAM (default: 2048)"
            echo "  --disk GB           Disco (default: 20)"
            echo "  --dns IP            DNS (default: 8.8.8.8)"
            echo "  --repo URL          Repository Git"
            echo "  --branch BRANCH     Branch Git (default: main)"
            echo "  --yes               Non chiedere conferma"
            exit 0
            ;;
        *) log_error "Opzione sconosciuta: $1" ;;
    esac
done

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      DaDude v2.0 Server - Proxmox LXC Installer           ║${NC}"
echo -e "${CYAN}║                                                           ║${NC}"
echo -e "${CYAN}║  PostgreSQL + Redis + FastAPI Backend + Vue.js Frontend   ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verifica siamo su Proxmox
if ! command -v pct &> /dev/null; then
    log_error "Questo script deve essere eseguito su un host Proxmox VE"
fi

# ==========================================
# CONFIGURAZIONE INTERATTIVA
# ==========================================

# IP Address
if [ -z "$IP_ADDRESS" ]; then
    echo -e "${YELLOW}=== Configurazione Rete ===${NC}"
    read -p "IP Address (es: 192.168.1.100/24): " IP_ADDRESS
    if [ -z "$IP_ADDRESS" ]; then
        log_error "IP Address richiesto"
    fi
fi

# Gateway
if [ -z "$GATEWAY" ]; then
    suggested_gw=$(echo "$IP_ADDRESS" | sed 's|/.*||' | sed 's|\.[0-9]*$|.1|')
    read -p "Gateway [$suggested_gw]: " input
    GATEWAY="${input:-$suggested_gw}"
fi

# CTID
if [ -z "$CTID" ]; then
    CTID=$(pvesh get /cluster/nextid)
fi

# Genera chiavi
POSTGRES_PASSWORD=$(openssl rand -hex 16)
ENCRYPTION_KEY=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -hex 32)

# Estrai IP senza maschera per output
IP_ONLY=$(echo "$IP_ADDRESS" | sed 's|/.*||')

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}              Riepilogo Configurazione                      ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo "  Container ID:   $CTID"
echo "  Hostname:       $HOSTNAME"
echo "  IP:             $IP_ADDRESS"
echo "  Gateway:        $GATEWAY"
echo "  DNS:            $DNS"
echo "  Bridge:         $BRIDGE"
echo "  Storage:        $STORAGE"
echo "  Memory:         ${MEMORY}MB"
echo "  Disk:           ${DISK}GB"
echo "  Repository:     $DADUDE_REPO"
echo "  Branch:         $DADUDE_BRANCH"
echo ""
echo -e "${CYAN}Servizi che verranno installati:${NC}"
echo "  - PostgreSQL 16 (database)"
echo "  - Redis 7 (cache)"
echo "  - DaDude Backend (FastAPI)"
echo "  - DaDude Frontend (Vue.js + Nginx)"
echo ""

# Conferma
if [ "$AUTO_YES" != "true" ]; then
    read -p "Procedere con l'installazione? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installazione annullata"
        exit 0
    fi
fi

# ==========================================
# INSTALLAZIONE
# ==========================================

echo ""
log_info "[1/7] Scarico template Debian..."

# Trova storage per template
TEMPLATE_STORAGE="local"
if ! pvesm status | grep -q "^local "; then
    TEMPLATE_STORAGE=$(pvesm status 2>/dev/null | grep -E "dir|nfs" | head -1 | awk '{print $1}')
fi

# Cerca template esistente
TEMPLATE_PATH=$(pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -iE "debian-12|debian-11" | head -1 | awk '{print $1}' || true)

if [ -z "$TEMPLATE_PATH" ]; then
    pveam update > /dev/null 2>&1
    TEMPLATE_NAME=$(pveam available 2>/dev/null | grep -i "debian-12-standard" | head -1 | awk '{print $2}')

    if [ -z "$TEMPLATE_NAME" ]; then
        TEMPLATE_NAME=$(pveam available 2>/dev/null | grep -i "debian-11-standard" | head -1 | awk '{print $2}')
    fi

    if [ -z "$TEMPLATE_NAME" ]; then
        log_error "Nessun template Debian trovato"
    fi

    log_info "Scarico $TEMPLATE_NAME..."
    pveam download $TEMPLATE_STORAGE "$TEMPLATE_NAME" > /dev/null
    TEMPLATE_PATH=$(pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -i "debian" | head -1 | awk '{print $1}')
fi

log_ok "Template: $TEMPLATE_PATH"

# Crea container
log_info "[2/7] Creo container LXC $CTID..."

pct create $CTID $TEMPLATE_PATH \
    --hostname $HOSTNAME \
    --storage $STORAGE \
    --rootfs ${STORAGE}:${DISK} \
    --memory $MEMORY \
    --swap 512 \
    --cores 4 \
    --net0 "name=eth0,bridge=$BRIDGE,ip=$IP_ADDRESS,gw=$GATEWAY" \
    --nameserver "$DNS" \
    --features nesting=1,keyctl=1 \
    --unprivileged 1 \
    --onboot 1 \
    --start 0 > /dev/null

log_ok "Container $CTID creato"

# Avvia container
log_info "[3/7] Avvio container..."
pct start $CTID
sleep 5

# Attendi che il container sia pronto
for i in {1..30}; do
    if pct exec $CTID -- test -f /etc/os-release 2>/dev/null; then
        break
    fi
    sleep 1
done

log_ok "Container avviato"

# Installa Docker
log_info "[4/7] Installo Docker (questo richiede ~2 minuti)..."

pct exec $CTID -- bash -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg git > /dev/null
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker
' 2>/dev/null

log_ok "Docker installato"

# Clone repository
log_info "[5/7] Clono repository DaDude..."

pct exec $CTID -- bash -c "git clone --depth 1 --branch $DADUDE_BRANCH $DADUDE_REPO /opt/dadude" 2>&1 | while read line; do
    echo -ne "\r${BLUE}[GIT]${NC} $line                    "
done
echo ""

log_ok "Repository clonato in /opt/dadude"

# Configura ambiente
log_info "[6/7] Configuro ambiente..."

# Crea file .env
cat << EOF | pct exec $CTID -- tee /opt/dadude/dadude/.env > /dev/null
# DaDude v2.0 Configuration
# Generated: $(date)

# PostgreSQL
POSTGRES_USER=dadude
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=dadude
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Backend
DADUDE_HOST=0.0.0.0
DADUDE_PORT=8000
DADUDE_API_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
LOG_LEVEL=INFO

# Frontend
FRONTEND_PORT=80

# DNS for container
DNS_PRIMARY=8.8.8.8
DNS_SECONDARY=8.8.4.4

# Optional: MikroTik The Dude integration
# DUDE_HOST=192.168.1.1
# DUDE_API_PORT=8728
# DUDE_USE_SSL=false
# DUDE_USERNAME=admin
# DUDE_PASSWORD=

# Polling intervals (seconds)
POLL_INTERVAL=60
FULL_SYNC_INTERVAL=300
CONNECTION_TIMEOUT=30
EOF

log_ok "File .env creato"

# Avvia servizi
log_info "[7/7] Build e avvio servizi (questo richiede ~5 minuti)..."

pct exec $CTID -- bash -c 'cd /opt/dadude/dadude && docker compose -f docker-compose.v2.yml up -d --build' 2>&1 | while read line; do
    echo -ne "\r${BLUE}[BUILD]${NC} ${line:0:60}...                    "
done
echo ""

# Attendi che i servizi siano pronti
log_info "Attendo che i servizi siano pronti..."
sleep 30

# Verifica salute servizi
for i in {1..30}; do
    if pct exec $CTID -- curl -s http://localhost:8000/api/v1/system/health > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Verifica stato finale
BACKEND_STATUS=$(pct exec $CTID -- docker ps --filter "name=dadude-backend" --format "{{.Status}}" 2>/dev/null || echo "Unknown")
FRONTEND_STATUS=$(pct exec $CTID -- docker ps --filter "name=dadude-frontend" --format "{{.Status}}" 2>/dev/null || echo "Unknown")
POSTGRES_STATUS=$(pct exec $CTID -- docker ps --filter "name=dadude-postgres" --format "{{.Status}}" 2>/dev/null || echo "Unknown")
REDIS_STATUS=$(pct exec $CTID -- docker ps --filter "name=dadude-redis" --format "{{.Status}}" 2>/dev/null || echo "Unknown")

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Installazione Completata!                      ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Container ID:   ${CYAN}$CTID${NC}"
echo -e "  Hostname:       ${CYAN}$HOSTNAME${NC}"
echo -e "  IP:             ${CYAN}$IP_ONLY${NC}"
echo ""
echo -e "${YELLOW}Stato Servizi:${NC}"
echo -e "  PostgreSQL:     ${CYAN}$POSTGRES_STATUS${NC}"
echo -e "  Redis:          ${CYAN}$REDIS_STATUS${NC}"
echo -e "  Backend:        ${CYAN}$BACKEND_STATUS${NC}"
echo -e "  Frontend:       ${CYAN}$FRONTEND_STATUS${NC}"
echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║                    ACCESSO                                 ║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Frontend UI:    ${CYAN}http://$IP_ONLY/${NC}"
echo -e "  Backend API:    ${CYAN}http://$IP_ONLY:8000/api/v1/${NC}"
echo -e "  API Docs:       ${CYAN}http://$IP_ONLY:8000/docs${NC}"
echo -e "  Health Check:   ${CYAN}http://$IP_ONLY:8000/api/v1/system/health${NC}"
echo ""
echo -e "${YELLOW}Credenziali Database (salvale!):${NC}"
echo -e "  Host:           postgres (interno) / $IP_ONLY:5432 (esterno)"
echo -e "  User:           dadude"
echo -e "  Password:       ${CYAN}$POSTGRES_PASSWORD${NC}"
echo -e "  Database:       dadude"
echo ""
echo -e "${YELLOW}Comandi utili:${NC}"
echo "  pct enter $CTID                                    # Entra nel container"
echo "  pct exec $CTID -- docker logs -f dadude-backend    # Logs backend"
echo "  pct exec $CTID -- docker logs -f dadude-frontend   # Logs frontend"
echo "  pct exec $CTID -- docker compose -f /opt/dadude/dadude/docker-compose.v2.yml restart"
echo ""
echo -e "${GREEN}Prossimo passo: installa gli Agent sulle reti remote${NC}"
echo ""
