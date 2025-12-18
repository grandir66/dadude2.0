#!/bin/bash
# Script completo per aggiornare agent DaDude su Proxmox LXC
# Esegue git pull, rebuild Docker e force-recreate del container
# Uso: ./update-agent-remote.sh <proxmox_ip> <container_id> [ssh_user] [ssh_password]

set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROXMOX_IP="${1:-}"
CONTAINER_ID="${2:-}"
SSH_USER="${3:-root}"
SSH_PASSWORD="${4:-}"

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

if [ -z "$PROXMOX_IP" ] || [ -z "$CONTAINER_ID" ]; then
    error "Uso: $0 <proxmox_ip> <container_id> [ssh_user] [ssh_password]"
    echo ""
    echo "Esempi:"
    echo "  $0 192.168.40.15 600 root"
    echo "  $0 192.168.40.15 610 root mypassword"
    exit 1
fi

log "=========================================="
log "Aggiornamento Agent DaDude"
log "Server Proxmox: $PROXMOX_IP"
log "Container LXC: $CONTAINER_ID"
log "=========================================="

# Comando completo da eseguire sul Proxmox
UPDATE_COMMAND="
set -e
AGENT_DIR=\"/opt/dadude-agent\"
COMPOSE_DIR=\"\${AGENT_DIR}/dadude-agent\"

# Verifica che il container esista
if ! pct status $CONTAINER_ID &>/dev/null; then
    echo \"ERROR: Container $CONTAINER_ID non trovato\"
    exit 1
fi

# Verifica directory agent
if ! pct exec $CONTAINER_ID -- test -d \"\${AGENT_DIR}\" 2>/dev/null; then
    echo \"ERROR: Directory \${AGENT_DIR} non trovata nel container\"
    exit 1
fi

echo \"[1/6] Verifica repository git...\"
if ! pct exec $CONTAINER_ID -- test -d \"\${AGENT_DIR}/.git\" 2>/dev/null; then
    echo \"WARNING: Directory non è un repository git, inizializzazione...\"
    pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git init && git remote add origin https://github.com/grandir66/Dadude.git || true\"
fi

echo \"[2/6] Fetch aggiornamenti da GitHub...\"
pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git fetch origin main 2>&1\" || {
    echo \"ERROR: Git fetch fallito\"
    exit 1
}

echo \"[3/6] Verifica versione corrente...\"
CURRENT_COMMIT=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git rev-parse HEAD 2>/dev/null || echo 'unknown'\")
REMOTE_COMMIT=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git rev-parse origin/main 2>/dev/null || echo 'unknown'\")
CURRENT_VERSION=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR}/dadude-agent && grep -oP 'AGENT_VERSION\\s*=\\s*\\\"\\K[^\\\"]+' app/agent.py 2>/dev/null || echo 'unknown'\")

echo \"   Commit corrente: \${CURRENT_COMMIT:0:8}\"
echo \"   Commit remoto:   \${REMOTE_COMMIT:0:8}\"
echo \"   Versione corrente: v\${CURRENT_VERSION}\"

if [ \"\$CURRENT_COMMIT\" = \"\$REMOTE_COMMIT\" ] && [ \"\$CURRENT_COMMIT\" != \"unknown\" ]; then
    echo \"[INFO] Agent già aggiornato all'ultima versione\"
    exit 0
fi

echo \"[4/6] Applicazione aggiornamenti...\"
pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git reset --hard origin/main 2>&1\" || {
    echo \"ERROR: Git reset fallito\"
    exit 1
}

NEW_VERSION=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR}/dadude-agent && grep -oP 'AGENT_VERSION\\s*=\\s*\\\"\\K[^\\\"]+' app/agent.py 2>/dev/null || echo 'unknown'\")
echo \"   Nuova versione: v\${NEW_VERSION}\"

echo \"[5/6] Rebuild immagine Docker...\"
if ! pct exec $CONTAINER_ID -- test -d \"\${COMPOSE_DIR}\" 2>/dev/null; then
    echo \"WARNING: Directory \${COMPOSE_DIR} non trovata, creazione...\"
    pct exec $CONTAINER_ID -- mkdir -p \"\${COMPOSE_DIR}\"
fi

# Verifica docker-compose.yml
if ! pct exec $CONTAINER_ID -- test -f \"\${COMPOSE_DIR}/docker-compose.yml\" 2>/dev/null; then
    echo \"WARNING: docker-compose.yml non trovato, copia da template...\"
    pct exec $CONTAINER_ID -- bash -c \"cp -r \${AGENT_DIR}/dadude-agent/* \${COMPOSE_DIR}/ 2>/dev/null || true\"
fi

# Rebuild immagine
pct exec $CONTAINER_ID -- bash -c \"cd \${COMPOSE_DIR} && docker compose build --quiet 2>&1\" || {
    echo \"ERROR: Docker build fallito\"
    exit 1
}

echo \"[6/6] Riavvio container con force-recreate...\"
# Stop container esistente
pct exec $CONTAINER_ID -- docker stop dadude-agent 2>/dev/null || true
sleep 2

# Force recreate
pct exec $CONTAINER_ID -- bash -c \"cd \${COMPOSE_DIR} && docker compose up -d --force-recreate 2>&1\" || {
    echo \"ERROR: Avvio container fallito\"
    exit 1
}

# Attendi avvio
sleep 5

# Verifica stato
CONTAINER_STATUS=\$(pct exec $CONTAINER_ID -- docker ps --filter name=dadude-agent --format '{{.Status}}' 2>/dev/null || echo '')
if echo \"\$CONTAINER_STATUS\" | grep -q \"Up\"; then
    echo \"SUCCESS: Container avviato correttamente\"
    
    # Verifica versione nei log
    sleep 3
    LOG_VERSION=\$(pct exec $CONTAINER_ID -- docker logs dadude-agent --tail 20 2>&1 | grep -oP 'DaDude Agent v\\K[0-9.]+' | head -1 || echo '')
    if [ -n \"\$LOG_VERSION\" ]; then
        echo \"   Versione nei log: v\$LOG_VERSION\"
    fi
else
    echo \"ERROR: Container non avviato correttamente\"
    pct exec $CONTAINER_ID -- docker ps -a --filter name=dadude-agent
    exit 1
fi

echo \"==========================================\"
echo \"Update completato con successo!\"
echo \"Versione: v\${NEW_VERSION}\"
echo \"==========================================\"
"

# Esegui comando via SSH
if [ -n "$SSH_PASSWORD" ]; then
    if ! command -v sshpass &> /dev/null; then
        error "sshpass non installato. Installa con: apt-get install sshpass"
        exit 1
    fi
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$SSH_USER@$PROXMOX_IP" "$UPDATE_COMMAND"
else
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$SSH_USER@$PROXMOX_IP" "$UPDATE_COMMAND"
fi

success "Script completato!"

