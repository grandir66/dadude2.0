#!/bin/bash
#
# DaDude Agent v2.0 - Installazione WebSocket mTLS
# Installa agent in modalità WebSocket (agent-initiated)
#
# Tutti i parametri vengono chiesti interattivamente se non forniti
#

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  DaDude Agent v2.0 - WebSocket mTLS Installer            ║"
echo "║  Modalità: Agent-Initiated (no porte in ascolto)         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Parametri (tutti vuoti di default)
CTID=""
HOSTNAME=""
STORAGE=""
TEMPLATE_STORAGE="local"
MEMORY=""
DISK=""
BRIDGE=""
VLAN=""
IP=""
GATEWAY=""
DNS=""
SERVER_URL=""
AGENT_NAME=""
AGENT_TOKEN=""

# Parse argomenti da linea di comando (opzionale)
while [[ $# -gt 0 ]]; do
    case $1 in
        --ctid) CTID="$2"; shift 2 ;;
        --hostname) HOSTNAME="$2"; shift 2 ;;
        --storage) STORAGE="$2"; shift 2 ;;
        --memory) MEMORY="$2"; shift 2 ;;
        --disk) DISK="$2"; shift 2 ;;
        --bridge) BRIDGE="$2"; shift 2 ;;
        --vlan) VLAN="$2"; shift 2 ;;
        --ip) IP="$2"; shift 2 ;;
        --gateway) GATEWAY="$2"; shift 2 ;;
        --dns) DNS="$2"; shift 2 ;;
        --server-url) SERVER_URL="$2"; shift 2 ;;
        --agent-name) AGENT_NAME="$2"; shift 2 ;;
        --agent-token) AGENT_TOKEN="$2"; shift 2 ;;
        --help)
            echo "Uso: $0 [opzioni]"
            echo ""
            echo "Se non vengono forniti parametri, lo script li chiederà interattivamente."
            echo ""
            echo "Opzioni:"
            echo "  --ctid ID            ID container LXC"
            echo "  --hostname NAME      Hostname del container"
            echo "  --server-url URL     URL server DaDude (es: http://dadude.esempio.it:8000)"
            echo "  --agent-name NAME    Nome identificativo dell'agent"
            echo "  --agent-token TOK    Token agent (opzionale, auto-generato se vuoto)"
            echo "  --bridge BRIDGE      Bridge di rete (es: vmbr0)"
            echo "  --vlan ID            VLAN tag (opzionale, lascia vuoto se non usi VLAN)"
            echo "  --ip IP/MASK         IP statico con netmask (es: 192.168.1.100/24)"
            echo "  --gateway IP         Gateway di rete"
            echo "  --dns IP             Server DNS"
            echo "  --storage NAME       Storage per il container (default: local-lvm)"
            echo "  --memory MB          Memoria RAM in MB (default: 512)"
            echo "  --disk GB            Spazio disco in GB (default: 4)"
            exit 0
            ;;
        *) echo -e "${RED}Opzione sconosciuta: $1${NC}"; exit 1 ;;
    esac
done

echo -e "${YELLOW}Configurazione Agent DaDude${NC}"
echo "Inserisci i parametri richiesti (premi Invio per accettare i default tra parentesi)"
echo ""

# === CONFIGURAZIONE SERVER ===
echo -e "${BLUE}--- Server DaDude ---${NC}"

if [ -z "$SERVER_URL" ]; then
    read -p "URL Server DaDude (es: http://dadude.tuodominio.it:8000): " SERVER_URL
    if [ -z "$SERVER_URL" ]; then
        echo -e "${RED}Errore: URL server è obbligatorio${NC}"
        exit 1
    fi
fi

# === CONFIGURAZIONE AGENT ===
echo -e "\n${BLUE}--- Identificazione Agent ---${NC}"

if [ -z "$AGENT_NAME" ]; then
    read -p "Nome Agent (es: agent-sede-milano): " AGENT_NAME
    if [ -z "$AGENT_NAME" ]; then
        echo -e "${RED}Errore: Nome agent è obbligatorio${NC}"
        exit 1
    fi
fi

if [ -z "$AGENT_TOKEN" ]; then
    read -p "Token Agent (lascia vuoto per generare automaticamente): " AGENT_TOKEN
    if [ -z "$AGENT_TOKEN" ]; then
        AGENT_TOKEN=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
        echo -e "${GREEN}Token generato: ${AGENT_TOKEN}${NC}"
    fi
fi

# === CONFIGURAZIONE CONTAINER ===
echo -e "\n${BLUE}--- Container LXC ---${NC}"

if [ -z "$CTID" ]; then
    SUGGESTED_CTID=$(pvesh get /cluster/nextid 2>/dev/null || echo "100")
    read -p "ID Container [$SUGGESTED_CTID]: " CTID
    CTID=${CTID:-$SUGGESTED_CTID}
fi

if [ -z "$HOSTNAME" ]; then
    SUGGESTED_HOSTNAME="dadude-agent-${AGENT_NAME}"
    read -p "Hostname container [$SUGGESTED_HOSTNAME]: " HOSTNAME
    HOSTNAME=${HOSTNAME:-$SUGGESTED_HOSTNAME}
fi

if [ -z "$STORAGE" ]; then
    read -p "Storage LXC [local-lvm]: " STORAGE
    STORAGE=${STORAGE:-local-lvm}
fi

if [ -z "$MEMORY" ]; then
    read -p "Memoria RAM in MB [512]: " MEMORY
    MEMORY=${MEMORY:-512}
fi

if [ -z "$DISK" ]; then
    read -p "Disco in GB [4]: " DISK
    DISK=${DISK:-4}
fi

# === CONFIGURAZIONE RETE ===
echo -e "\n${BLUE}--- Configurazione Rete ---${NC}"

if [ -z "$BRIDGE" ]; then
    read -p "Bridge di rete (es: vmbr0): " BRIDGE
    if [ -z "$BRIDGE" ]; then
        echo -e "${RED}Errore: Bridge è obbligatorio${NC}"
        exit 1
    fi
fi

if [ -z "$VLAN" ]; then
    read -p "VLAN tag (lascia vuoto se non usi VLAN): " VLAN
fi

if [ -z "$IP" ]; then
    read -p "IP/Netmask (es: 192.168.1.100/24): " IP
    if [ -z "$IP" ]; then
        echo -e "${RED}Errore: IP è obbligatorio${NC}"
        exit 1
    fi
fi

if [ -z "$GATEWAY" ]; then
    read -p "Gateway: " GATEWAY
    if [ -z "$GATEWAY" ]; then
        echo -e "${RED}Errore: Gateway è obbligatorio${NC}"
        exit 1
    fi
fi

if [ -z "$DNS" ]; then
    read -p "Server DNS: " DNS
    if [ -z "$DNS" ]; then
        echo -e "${RED}Errore: DNS è obbligatorio${NC}"
        exit 1
    fi
fi

# Genera agent ID univoco
AGENT_ID="agent-${AGENT_NAME}-$(date +%s | tail -c 5)"

# Elimina container esistente se presente
if pct status $CTID &>/dev/null; then
    echo -e "\n${YELLOW}Container $CTID esiste già. Lo elimino...${NC}"
    pct stop $CTID 2>/dev/null || true
    sleep 2
    pct destroy $CTID --force 2>/dev/null || true
    echo -e "${GREEN}Container $CTID eliminato${NC}"
fi

# Riepilogo configurazione
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    RIEPILOGO CONFIGURAZIONE              ${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Server:${NC}"
echo "    URL Server:    $SERVER_URL"
echo ""
echo -e "  ${BLUE}Agent:${NC}"
echo "    Nome:          $AGENT_NAME"
echo "    Agent ID:      $AGENT_ID"
echo "    Token:         ${AGENT_TOKEN:0:8}..."
echo ""
echo -e "  ${BLUE}Container:${NC}"
echo "    CTID:          $CTID"
echo "    Hostname:      $HOSTNAME"
echo "    Storage:       $STORAGE"
echo "    Memoria:       ${MEMORY}MB"
echo "    Disco:         ${DISK}GB"
echo ""
echo -e "  ${BLUE}Rete:${NC}"
echo "    Bridge:        $BRIDGE"
if [ -n "$VLAN" ]; then
echo "    VLAN:          $VLAN"
fi
echo "    IP:            $IP"
echo "    Gateway:       $GATEWAY"
echo "    DNS:           $DNS"
echo ""
echo -e "  ${BLUE}Modalità:${NC}          WebSocket mTLS (agent-initiated)"
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo ""

read -p "Procedere con l'installazione? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installazione annullata."
    exit 1
fi

# === INSTALLAZIONE ===

# Trova template
echo -e "\n${BLUE}[1/6] Verifico template...${NC}"

TEMPLATE=""
for t in "debian-12-standard" "debian-11-standard" "ubuntu-24.04-standard" "ubuntu-22.04-standard"; do
    if pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -q "$t"; then
        TEMPLATE=$(pveam list $TEMPLATE_STORAGE | grep "$t" | head -1 | awk '{print $1}')
        break
    fi
done

if [ -z "$TEMPLATE" ]; then
    echo "Scarico template Debian 12..."
    pveam update
    TEMPLATE_NAME=$(pveam available | grep "debian-12-standard" | head -1 | awk '{print $2}')
    if [ -n "$TEMPLATE_NAME" ]; then
        pveam download $TEMPLATE_STORAGE $TEMPLATE_NAME
        TEMPLATE="${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE_NAME}"
    else
        echo -e "${RED}Errore: nessun template disponibile${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Usando template: $TEMPLATE${NC}"

# Configura rete
NET_CONFIG="name=eth0,bridge=${BRIDGE}"
if [ -n "$VLAN" ]; then
    NET_CONFIG="${NET_CONFIG},tag=${VLAN}"
fi
NET_CONFIG="${NET_CONFIG},ip=${IP},gw=${GATEWAY}"

# Crea container
echo -e "\n${BLUE}[2/6] Creo container LXC...${NC}"

pct create $CTID $TEMPLATE \
    --hostname $HOSTNAME \
    --storage $STORAGE \
    --memory $MEMORY \
    --cores 1 \
    --rootfs ${STORAGE}:${DISK} \
    --net0 "$NET_CONFIG" \
    --nameserver "$DNS" \
    --features nesting=1,keyctl=1 \
    --unprivileged 0 \
    --start 1

sleep 5

# Attendi avvio
echo -e "\n${BLUE}[3/6] Attendo avvio container...${NC}"
for i in {1..30}; do
    if pct exec $CTID -- echo "ok" &>/dev/null; then
        break
    fi
    sleep 2
done

# Installa Docker
echo -e "\n${BLUE}[4/6] Installo Docker...${NC}"

pct exec $CTID -- bash -c '
apt-get update
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
'

# Clona repository
echo -e "\n${BLUE}[5/6] Clono repository e configuro...${NC}"

pct exec $CTID -- bash -c "
mkdir -p /opt/dadude-agent
cd /opt
git clone https://github.com/grandir66/dadude.git dadude-temp
cp -r dadude-temp/dadude-agent/* /opt/dadude-agent/
rm -rf dadude-temp
"

# Crea .env per modalità WebSocket
pct exec $CTID -- bash -c "cat > /opt/dadude-agent/.env << 'EOF'
# DaDude Agent v2.0 - WebSocket Mode
DADUDE_SERVER_URL=${SERVER_URL}
DADUDE_AGENT_ID=${AGENT_ID}
DADUDE_AGENT_NAME=${AGENT_NAME}
DADUDE_AGENT_TOKEN=${AGENT_TOKEN}
DADUDE_CONNECTION_MODE=websocket
DADUDE_LOG_LEVEL=INFO
DADUDE_DNS_SERVERS=${DNS}
DADUDE_DATA_DIR=/var/lib/dadude-agent
EOF"

# Crea docker-compose per modalità WebSocket
pct exec $CTID -- bash -c 'cat > /opt/dadude-agent/docker-compose.yml << '"'"'EOF'"'"'
services:
  dadude-agent:
    build: .
    container_name: dadude-agent-ws
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/var/lib/dadude-agent
    command: ["python", "-m", "app.agent"]
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 60s
      timeout: 10s
      retries: 3
EOF'

# Crea directory dati
pct exec $CTID -- mkdir -p /opt/dadude-agent/data

# Build e avvia
echo -e "\n${BLUE}[6/6] Build e avvio container Docker...${NC}"

pct exec $CTID -- bash -c "cd /opt/dadude-agent && docker compose build && docker compose up -d"

sleep 5

# Verifica finale
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ INSTALLAZIONE COMPLETATA!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Dettagli Agent:${NC}"
echo "  Container ID:  $CTID"
echo "  Hostname:      $HOSTNAME"
echo "  Agent ID:      $AGENT_ID"
echo "  Agent Name:    $AGENT_NAME"
echo "  Agent Token:   $AGENT_TOKEN"
echo "  Server URL:    $SERVER_URL"
echo "  IP:            $IP"
echo ""
echo -e "${YELLOW}NOTA: L'agent opera in modalità WebSocket${NC}"
echo "  - Nessuna porta in ascolto"
echo "  - L'agent si connette al server (non viceversa)"
echo "  - Funziona anche dietro NAT/firewall"
echo ""
echo -e "${BLUE}Prossimi passi:${NC}"
echo "  1. Verifica i log: pct exec $CTID -- docker logs dadude-agent-ws"
echo "  2. L'agent si registrerà automaticamente al server"
echo "  3. Approva l'agent dal pannello DaDude: ${SERVER_URL}/agents"
echo ""
echo -e "${BLUE}Comandi utili:${NC}"
echo "  pct exec $CTID -- docker logs -f dadude-agent-ws    # Log in tempo reale"
echo "  pct exec $CTID -- docker restart dadude-agent-ws    # Riavvia agent"
echo "  pct exec $CTID -- bash                              # Shell nel container"
echo ""
