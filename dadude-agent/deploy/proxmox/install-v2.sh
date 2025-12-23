#!/bin/bash
#
# DaDude Agent v2 - Installer per Proxmox VE
# Crea un container LXC con Docker e l'agent preconfigurato
# L'agent si auto-registra al server e apparirà nella lista "Pending Approval"
#
# Uso:
#   ./install-v2.sh --server-url http://IP:8000
#
# Opzioni:
#   --server-url URL      URL del server DaDude (richiesto)
#   --agent-name NAME     Nome descrittivo (default: auto)
#   --ctid ID             ID container Proxmox (default: auto)
#   --ip CIDR             IP statico (es: 192.168.1.100/24) o 'dhcp'
#   --gateway IP          Gateway
#   --bridge BRIDGE       Bridge Proxmox (default: vmbr0)
#   --vlan TAG            VLAN tag (opzionale)
#   --storage STORAGE     Storage Proxmox (default: local-lvm)
#   --memory MB           RAM in MB (default: 512)
#   --repo URL            URL repository Git (default: vedi sotto)
#   --branch BRANCH       Branch da usare (default: main)
#   --yes                 Non chiedere conferma
#

# ============================================================
# CONFIGURAZIONE REPOSITORY
# Modifica questa variabile quando il repo dadude2.0 è pronto
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
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Valori default
CTID=""
HOSTNAME=""
BRIDGE="vmbr0"
VLAN=""
STORAGE="local-lvm"
MEMORY=512
DISK=4
IP_CONFIG="dhcp"
GATEWAY=""
SERVER_URL=""
AGENT_NAME=""
AUTO_YES=false

# Parse argomenti
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-url) SERVER_URL="$2"; shift 2 ;;
        --agent-name) AGENT_NAME="$2"; shift 2 ;;
        --ctid) CTID="$2"; shift 2 ;;
        --ip) IP_CONFIG="$2"; shift 2 ;;
        --gateway) GATEWAY="$2"; shift 2 ;;
        --bridge) BRIDGE="$2"; shift 2 ;;
        --vlan) VLAN="$2"; shift 2 ;;
        --storage) STORAGE="$2"; shift 2 ;;
        --memory) MEMORY="$2"; shift 2 ;;
        --repo) DADUDE_REPO="$2"; shift 2 ;;
        --branch) DADUDE_BRANCH="$2"; shift 2 ;;
        --yes|-y) AUTO_YES=true; shift ;;
        --help|-h)
            echo "Uso: $0 --server-url URL [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  --server-url URL    URL del server DaDude (richiesto)"
            echo "  --agent-name NAME   Nome agent (default: auto)"
            echo "  --ctid ID           ID container Proxmox"
            echo "  --ip CIDR           IP statico o 'dhcp'"
            echo "  --gateway IP        Gateway"
            echo "  --bridge BRIDGE     Bridge (default: vmbr0)"
            echo "  --vlan TAG          VLAN tag"
            echo "  --storage NAME      Storage (default: local-lvm)"
            echo "  --memory MB         RAM (default: 512)"
            echo "  --repo URL          Git repository URL"
            echo "  --branch BRANCH     Git branch (default: main)"
            echo "  --yes               Non chiedere conferma"
            exit 0
            ;;
        *) log_error "Opzione sconosciuta: $1"; exit 1 ;;
    esac
done

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     DaDude Agent v2 - Proxmox LXC Installer       ║${NC}"
echo -e "${CYAN}║                                                   ║${NC}"
echo -e "${CYAN}║  L'agent si auto-registrerà al server e dovrà    ║${NC}"
echo -e "${CYAN}║  essere approvato dalla pagina Agents             ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# Verifica siamo su Proxmox
if ! command -v pct &> /dev/null; then
    log_error "Questo script deve essere eseguito su un host Proxmox VE"
    exit 1
fi

# ==========================================
# CONFIGURAZIONE INTERATTIVA
# ==========================================

# Server URL
if [ -z "$SERVER_URL" ]; then
    echo -e "${YELLOW}=== Configurazione Server ===${NC}"
    read -p "URL del server DaDude (es: http://192.168.1.100:8000): " SERVER_URL
    if [ -z "$SERVER_URL" ]; then
        log_error "URL server richiesto"
        exit 1
    fi
fi

# Verifica connettività al server
log_info "Verifico connettività a $SERVER_URL..."
if curl -s --connect-timeout 5 "$SERVER_URL/api/v1/system/health" > /dev/null 2>&1; then
    log_ok "Server raggiungibile"
else
    log_warn "Server non raggiungibile (potrebbe essere normale se su rete diversa)"
fi

# Agent Name
if [ -z "$AGENT_NAME" ]; then
    default_name="Agent-$(hostname -s)-$(date +%H%M)"
    read -p "Nome dell'agent [$default_name]: " input
    AGENT_NAME="${input:-$default_name}"
fi

# Bridge
echo ""
echo -e "${YELLOW}=== Configurazione Rete ===${NC}"
echo "Bridge disponibili su questo host:"
for br in $(ls /sys/class/net/ | grep -E "^vmbr"); do
    echo "  - $br"
done
echo ""

if [ "$BRIDGE" == "vmbr0" ] && [ "$AUTO_YES" != "true" ]; then
    read -p "Bridge da usare [vmbr0]: " input
    BRIDGE="${input:-vmbr0}"
fi

# VLAN
if [ -z "$VLAN" ] && [ "$AUTO_YES" != "true" ]; then
    read -p "VLAN tag (lascia vuoto se non usato): " VLAN
fi

# IP
if [ "$IP_CONFIG" == "dhcp" ] && [ "$AUTO_YES" != "true" ]; then
    read -p "Indirizzo IP (es: 192.168.1.100/24) o 'dhcp' [dhcp]: " input
    IP_CONFIG="${input:-dhcp}"
fi

# Gateway
if [ "$IP_CONFIG" != "dhcp" ] && [ -z "$GATEWAY" ]; then
    suggested_gw=$(echo "$IP_CONFIG" | sed 's|/.*||' | sed 's|\.[0-9]*$|.1|')
    read -p "Gateway [$suggested_gw]: " input
    GATEWAY="${input:-$suggested_gw}"
fi

# Genera CTID se non specificato
if [ -z "$CTID" ]; then
    CTID=$(pvesh get /cluster/nextid)
fi

# Genera hostname
HOSTNAME="dadude-$(echo $AGENT_NAME | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-12)"

# Genera Agent ID univoco
AGENT_ID="agent-$(hostname -s)-$(date +%s | tail -c 6)"

# Genera token random
AGENT_TOKEN=$(openssl rand -hex 32)

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}              Riepilogo Configurazione              ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo "  Container ID:   $CTID"
echo "  Hostname:       $HOSTNAME"
echo "  Agent Name:     $AGENT_NAME"
echo "  Agent ID:       $AGENT_ID"
echo "  Storage:        $STORAGE"
echo "  Memory:         ${MEMORY}MB"
echo "  Disk:           ${DISK}GB"
echo "  Bridge:         $BRIDGE"
[ -n "$VLAN" ] && echo "  VLAN:           $VLAN"
echo "  IP:             $IP_CONFIG"
[ -n "$GATEWAY" ] && echo "  Gateway:        $GATEWAY"
echo "  Server URL:     $SERVER_URL"
echo "  Repository:     $DADUDE_REPO"
echo "  Branch:         $DADUDE_BRANCH"
echo ""
echo -e "${CYAN}L'agent si registrerà automaticamente al server.${NC}"
echo -e "${CYAN}Dovrai approvarlo dalla pagina Agents del frontend.${NC}"
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
log_info "[1/6] Scarico template Debian..."

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
        exit 1
    fi

    log_info "Scarico $TEMPLATE_NAME..."
    pveam download $TEMPLATE_STORAGE "$TEMPLATE_NAME" > /dev/null
    TEMPLATE_PATH=$(pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -i "debian" | head -1 | awk '{print $1}')
fi

log_ok "Template: $TEMPLATE_PATH"

# Crea container
log_info "[2/6] Creo container LXC $CTID..."

NET_CONFIG="name=eth0,bridge=$BRIDGE"
[ -n "$VLAN" ] && NET_CONFIG="$NET_CONFIG,tag=$VLAN"

if [ "$IP_CONFIG" != "dhcp" ]; then
    NET_CONFIG="$NET_CONFIG,ip=$IP_CONFIG"
    [ -n "$GATEWAY" ] && NET_CONFIG="$NET_CONFIG,gw=$GATEWAY"
else
    NET_CONFIG="$NET_CONFIG,ip=dhcp"
fi

pct create $CTID $TEMPLATE_PATH \
    --hostname $HOSTNAME \
    --storage $STORAGE \
    --rootfs ${STORAGE}:${DISK} \
    --memory $MEMORY \
    --swap 256 \
    --cores 2 \
    --net0 "$NET_CONFIG" \
    --features nesting=1,keyctl=1 \
    --unprivileged 1 \
    --onboot 1 \
    --start 0 > /dev/null

log_ok "Container $CTID creato"

# Avvia container
log_info "[3/6] Avvio container..."
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
log_info "[4/6] Installo Docker (questo richiede ~2 minuti)..."

pct exec $CTID -- bash -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg > /dev/null
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

# Configura agent
log_info "[5/6] Configuro DaDude Agent..."

pct exec $CTID -- mkdir -p /opt/dadude-agent/config /opt/dadude-agent/data

# Crea docker-compose.yml (variabili espanse qui, non nel container)
cat << EOF | pct exec $CTID -- tee /opt/dadude-agent/docker-compose.yml > /dev/null
version: '3.8'
services:
  agent:
    build: .
    container_name: dadude-agent
    restart: unless-stopped
    network_mode: host
    environment:
      - DADUDE_SERVER_URL=${SERVER_URL}
      - DADUDE_AGENT_ID=${AGENT_ID}
      - DADUDE_AGENT_NAME=${AGENT_NAME}
      - DADUDE_AGENT_TOKEN=${AGENT_TOKEN}
      - DADUDE_LOG_LEVEL=INFO
    volumes:
      - ./config:/app/config:ro
      - ./data:/var/lib/dadude-agent
EOF

# Crea Dockerfile per build locale (con variabili espanse)
cat << EOF | pct exec $CTID -- tee /opt/dadude-agent/Dockerfile > /dev/null
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc libffi-dev iputils-ping dnsutils net-tools iproute2 nmap procps git \\
    && rm -rf /var/lib/apt/lists/*

# Clone agent code from ${DADUDE_REPO} branch ${DADUDE_BRANCH}
RUN git clone --depth 1 --branch ${DADUDE_BRANCH} ${DADUDE_REPO} /tmp/dadude \\
    && cp -r /tmp/dadude/dadude-agent/app . \\
    && cp /tmp/dadude/dadude-agent/requirements.txt . \\
    && rm -rf /tmp/dadude

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.agent"]
EOF

# Crea systemd service
cat << 'SERVICE' | pct exec $CTID -- tee /etc/systemd/system/dadude-agent.service > /dev/null
[Unit]
Description=DaDude Agent
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/dadude-agent
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE

pct exec $CTID -- systemctl daemon-reload > /dev/null 2>&1
pct exec $CTID -- systemctl enable dadude-agent > /dev/null 2>&1

log_ok "Configurazione completata"

# Avvia agent
log_info "[6/6] Build e avvio agent (questo richiede ~3 minuti)..."

pct exec $CTID -- bash -c 'cd /opt/dadude-agent && docker compose up -d --build' 2>&1 | while read line; do
    echo -ne "\r${BLUE}[BUILD]${NC} $line                    "
done
echo ""

# Attendi che l'agent sia pronto
log_info "Attendo che l'agent sia pronto..."
sleep 10

# Verifica stato
AGENT_STATUS=$(pct exec $CTID -- docker ps --filter "name=dadude-agent" --format "{{.Status}}" 2>/dev/null || echo "")

# Ottieni IP
AGENT_IP=$(pct exec $CTID -- hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Installazione Completata!              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Container ID:   ${CYAN}$CTID${NC}"
echo -e "  Hostname:       ${CYAN}$HOSTNAME${NC}"
echo -e "  Agent Name:     ${CYAN}$AGENT_NAME${NC}"
echo -e "  Agent ID:       ${CYAN}$AGENT_ID${NC}"
if [ -n "$AGENT_IP" ]; then
    echo -e "  Agent IP:       ${CYAN}$AGENT_IP${NC}"
    echo -e "  Health Check:   ${CYAN}http://$AGENT_IP:8080/health${NC}"
fi
echo -e "  Status:         ${CYAN}$AGENT_STATUS${NC}"
echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║                   PROSSIMI PASSI                  ║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  1. Apri il frontend DaDude: ${CYAN}$SERVER_URL${NC}"
echo -e "  2. Vai nella pagina ${CYAN}Agents${NC}"
echo -e "  3. Vedrai l'agent in ${YELLOW}\"Pending Approval\"${NC}"
echo -e "  4. Clicca ${GREEN}Approve${NC} e seleziona il cliente"
echo -e "  5. L'agent è pronto per le scansioni!"
echo ""
echo -e "${YELLOW}Comandi utili:${NC}"
echo "  pct enter $CTID                              # Entra nel container"
echo "  pct exec $CTID -- docker logs -f dadude-agent  # Vedi logs agent"
echo "  pct exec $CTID -- docker restart dadude-agent  # Riavvia agent"
echo "  curl http://$AGENT_IP:8080/health             # Test health"
echo ""
