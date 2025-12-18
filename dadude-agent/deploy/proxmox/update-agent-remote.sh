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

echo \"[1/7] Verifica connettività internet e DNS...\"
# Verifica connettività internet prima
if ! pct exec $CONTAINER_ID -- ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo \"ERROR: Container non ha connettività internet\"
    echo \"SOLUZIONE: Verifica configurazione rete del container LXC\"
    exit 1
fi
echo \"   Connettività internet: OK\"

# Verifica risoluzione DNS - prova più percorsi per trovare DNS configurato
DNS_SERVERS=\"\"
# Metodo 1: /etc/resolv.conf
if pct exec $CONTAINER_ID -- test -f /etc/resolv.conf 2>/dev/null; then
    DNS_SERVERS=\$(pct exec $CONTAINER_ID -- cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print \$2}' | head -1 || echo '')
fi

# Metodo 2: systemd-resolve
if [ -z \"\$DNS_SERVERS\" ] && pct exec $CONTAINER_ID -- test -f /run/systemd/resolve/resolv.conf 2>/dev/null; then
    DNS_SERVERS=\$(pct exec $CONTAINER_ID -- cat /run/systemd/resolve/resolv.conf 2>/dev/null | grep nameserver | awk '{print \$2}' | head -1 || echo '')
fi

# Metodo 3: Verifica configurazione Proxmox
if [ -z \"\$DNS_SERVERS\" ]; then
    # Prova a leggere dalla configurazione Proxmox
    PROXMOX_DNS=\$(ssh -o StrictHostKeyChecking=no root@$PROXMOX_IP \"pct config $CONTAINER_ID | grep nameserver | awk '{print \\\$2}'\" 2>/dev/null | head -1 || echo '')
    if [ -n \"\$PROXMOX_DNS\" ]; then
        DNS_SERVERS=\"\$PROXMOX_DNS\"
        echo \"   DNS trovato nella configurazione Proxmox: \$DNS_SERVERS\"
    fi
fi

# Se non c'è DNS configurato, prova a configurarlo automaticamente
if [ -z \"\$DNS_SERVERS\" ]; then
    echo \"WARNING: Nessun DNS server configurato, tentativo configurazione automatica...\"
    # Prova a configurare DNS usando il gateway del container o 8.8.8.8
    GATEWAY=\$(pct exec $CONTAINER_ID -- ip route | grep default | awk '{print \$3}' | head -1 || echo '')
    if [ -n \"\$GATEWAY\" ]; then
        echo \"   Configurazione DNS con gateway: \$GATEWAY\"
        ssh -o StrictHostKeyChecking=no root@$PROXMOX_IP \"pct set $CONTAINER_ID --nameserver \$GATEWAY\" 2>/dev/null || true
        sleep 1
        DNS_SERVERS=\"\$GATEWAY\"
    else
        echo \"   Configurazione DNS con 8.8.8.8\"
        ssh -o StrictHostKeyChecking=no root@$PROXMOX_IP \"pct set $CONTAINER_ID --nameserver 8.8.8.8\" 2>/dev/null || true
        sleep 1
        DNS_SERVERS=\"8.8.8.8\"
    fi
    
    # Riavvia il container per applicare DNS (se necessario)
    echo \"   Riavvio container per applicare DNS...\"
    ssh -o StrictHostKeyChecking=no root@$PROXMOX_IP \"pct shutdown $CONTAINER_ID && sleep 2 && pct start $CONTAINER_ID\" 2>/dev/null || true
    sleep 3
    
    # Verifica che il DNS sia configurato
    DNS_CHECK=\$(pct exec $CONTAINER_ID -- cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print \$2}' | head -1 || echo '')
    if [ -n \"\$DNS_CHECK\" ]; then
        echo \"   DNS configurato: \$DNS_CHECK\"
        DNS_SERVERS=\"\$DNS_CHECK\"
    fi
fi

# Verifica risoluzione DNS
if [ -n \"\$DNS_SERVERS\" ]; then
    echo \"   DNS server: \$DNS_SERVERS\"
    if pct exec $CONTAINER_ID -- nslookup github.com >/dev/null 2>&1; then
        echo \"   Risoluzione DNS: OK\"
    else
        echo \"   WARNING: DNS configurato ma risoluzione non funziona\"
        echo \"   Tentativo con IP diretto di GitHub (140.82.121.4)...\"
        # Configura temporaneamente l'IP di GitHub in /etc/hosts
        pct exec $CONTAINER_ID -- bash -c \"echo '140.82.121.4 github.com' >> /etc/hosts\" 2>/dev/null || true
    fi
else
    echo \"   WARNING: Impossibile configurare DNS automaticamente\"
    echo \"   Tentativo con IP diretto di GitHub (140.82.121.4)...\"
    pct exec $CONTAINER_ID -- bash -c \"echo '140.82.121.4 github.com' >> /etc/hosts\" 2>/dev/null || true
fi

echo \"[2/7] Verifica repository git...\"
if ! pct exec $CONTAINER_ID -- test -d \"\${AGENT_DIR}/.git\" 2>/dev/null; then
    echo \"WARNING: Directory non è un repository git, inizializzazione...\"
    pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git init && git remote add origin https://github.com/grandir66/Dadude.git || true\"
fi

echo \"[3/7] Fetch aggiornamenti da GitHub...\"
FETCH_OUTPUT=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git fetch origin main 2>&1\" || echo \"FETCH_FAILED\")
if echo \"\$FETCH_OUTPUT\" | grep -q \"FETCH_FAILED\|fatal\|Could not resolve host\"; then
    echo \"ERROR: Git fetch fallito\"
    echo \"Output: \$FETCH_OUTPUT\"
    echo \"\"
    echo \"SOLUZIONI:\"
    echo \"1. Configura DNS nel container:\"
    echo \"   pct set $CONTAINER_ID --nameserver 8.8.8.8\"
    echo \"\"
    echo \"2. Verifica connettività internet:\"
    echo \"   pct exec $CONTAINER_ID -- ping -c 3 8.8.8.8\"
    echo \"\"
    echo \"3. Verifica gateway del container:\"
    echo \"   pct exec $CONTAINER_ID -- ip route\"
    exit 1
fi

echo \"[4/8] Backup file di configurazione...\"
# Backup file .env principale
ENV_BACKUP_ROOT=\"\"
ENV_BACKUP_SUBDIR=\"\"
if pct exec $CONTAINER_ID -- test -f \"\${AGENT_DIR}/.env\" 2>/dev/null; then
    ENV_BACKUP_ROOT=\$(mktemp)
    pct exec $CONTAINER_ID -- cat \"\${AGENT_DIR}/.env\" > \"\$ENV_BACKUP_ROOT\"
    echo \"   Backup .env principale salvato\"
fi

# Backup file .env nella subdirectory
if pct exec $CONTAINER_ID -- test -f \"\${COMPOSE_DIR}/.env\" 2>/dev/null; then
    ENV_BACKUP_SUBDIR=\$(mktemp)
    pct exec $CONTAINER_ID -- cat \"\${COMPOSE_DIR}/.env\" > \"\$ENV_BACKUP_SUBDIR\"
    echo \"   Backup .env subdirectory salvato\"
fi

# Backup file config personalizzati
CONFIG_BACKUP=\"\"
if pct exec $CONTAINER_ID -- test -d \"\${COMPOSE_DIR}/config\" 2>/dev/null; then
    CONFIG_BACKUP=\$(mktemp -d)
    pct exec $CONTAINER_ID -- bash -c \"cd \${COMPOSE_DIR} && tar czf - config/\" 2>/dev/null | tar xzf - -C \"\$CONFIG_BACKUP\" 2>/dev/null || true
    if [ -d \"\$CONFIG_BACKUP/config\" ]; then
        echo \"   Backup directory config salvato\"
    fi
fi

echo \"[5/8] Verifica versione corrente...\"
CURRENT_COMMIT=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git rev-parse HEAD 2>/dev/null || echo 'unknown'\")
REMOTE_COMMIT=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git rev-parse origin/main 2>/dev/null || echo 'unknown'\")
CURRENT_VERSION=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR}/dadude-agent && grep -oP 'AGENT_VERSION\\s*=\\s*\\\"\\K[^\\\"]+' app/agent.py 2>/dev/null || echo 'unknown'\")

echo \"   Commit corrente: \${CURRENT_COMMIT:0:8}\"
echo \"   Commit remoto:   \${REMOTE_COMMIT:0:8}\"
echo \"   Versione corrente: v\${CURRENT_VERSION}\"

if [ \"\$CURRENT_COMMIT\" = \"\$REMOTE_COMMIT\" ] && [ \"\$CURRENT_COMMIT\" != \"unknown\" ]; then
    echo \"[INFO] Agent già aggiornato all'ultima versione\"
    # Cleanup backup files
    [ -n \"\$ENV_BACKUP_ROOT\" ] && [ -f \"\$ENV_BACKUP_ROOT\" ] && rm -f \"\$ENV_BACKUP_ROOT\"
    [ -n \"\$ENV_BACKUP_SUBDIR\" ] && [ -f \"\$ENV_BACKUP_SUBDIR\" ] && rm -f \"\$ENV_BACKUP_SUBDIR\"
    [ -n \"\$CONFIG_BACKUP\" ] && [ -d \"\$CONFIG_BACKUP\" ] && rm -rf \"\$CONFIG_BACKUP\"
    exit 0
fi

echo \"[6/8] Applicazione aggiornamenti...\"
pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR} && git reset --hard origin/main 2>&1\" || {
    echo \"ERROR: Git reset fallito\"
    # Ripristina backup in caso di errore
    if [ -n \"\$ENV_BACKUP_ROOT\" ] && [ -f \"\$ENV_BACKUP_ROOT\" ]; then
        pct exec $CONTAINER_ID -- bash -c \"cat > \${AGENT_DIR}/.env\" < \"\$ENV_BACKUP_ROOT\"
        echo \"   .env ripristinato dopo errore\"
    fi
    exit 1
}

NEW_VERSION=\$(pct exec $CONTAINER_ID -- bash -c \"cd \${AGENT_DIR}/dadude-agent && grep -oP 'AGENT_VERSION\\s*=\\s*\\\"\\K[^\\\"]+' app/agent.py 2>/dev/null || echo 'unknown'\")
echo \"   Nuova versione: v\${NEW_VERSION}\"

echo \"[7/8] Ripristino file di configurazione...\"
# Ripristina .env principale
if [ -n \"\$ENV_BACKUP_ROOT\" ] && [ -f \"\$ENV_BACKUP_ROOT\" ]; then
    pct exec $CONTAINER_ID -- bash -c \"cat > \${AGENT_DIR}/.env\" < \"\$ENV_BACKUP_ROOT\"
    echo \"   .env principale ripristinato\"
fi

# Ripristina .env subdirectory
if [ -n \"\$ENV_BACKUP_SUBDIR\" ] && [ -f \"\$ENV_BACKUP_SUBDIR\" ]; then
    pct exec $CONTAINER_ID -- mkdir -p \"\${COMPOSE_DIR}\" 2>/dev/null || true
    pct exec $CONTAINER_ID -- bash -c \"cat > \${COMPOSE_DIR}/.env\" < \"\$ENV_BACKUP_SUBDIR\"
    echo \"   .env subdirectory ripristinato\"
elif [ -n \"\$ENV_BACKUP_ROOT\" ] && [ -f \"\$ENV_BACKUP_ROOT\" ]; then
    # Se non esiste backup subdirectory, copia dalla root
    pct exec $CONTAINER_ID -- mkdir -p \"\${COMPOSE_DIR}\" 2>/dev/null || true
    pct exec $CONTAINER_ID -- cp \"\${AGENT_DIR}/.env\" \"\${COMPOSE_DIR}/.env\" 2>/dev/null || true
    echo \"   .env copiato in subdirectory\"
fi

# Ripristina config personalizzati (solo se esistevano)
if [ -n \"\$CONFIG_BACKUP\" ] && [ -d \"\$CONFIG_BACKUP/config\" ]; then
    pct exec $CONTAINER_ID -- mkdir -p \"\${COMPOSE_DIR}/config\" 2>/dev/null || true
    cd \"\$CONFIG_BACKUP\" && tar czf - config/ | pct exec $CONTAINER_ID -- bash -c \"cd \${COMPOSE_DIR} && tar xzf -\" 2>/dev/null || true
    echo \"   Directory config ripristinata\"
fi

echo \"[8/8] Rebuild immagine Docker...\"
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

echo \"[9/9] Riavvio container con force-recreate...\"
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

# Cleanup backup files
[ -n \"\$ENV_BACKUP_ROOT\" ] && [ -f \"\$ENV_BACKUP_ROOT\" ] && rm -f \"\$ENV_BACKUP_ROOT\"
[ -n \"\$ENV_BACKUP_SUBDIR\" ] && [ -f \"\$ENV_BACKUP_SUBDIR\" ] && rm -f \"\$ENV_BACKUP_SUBDIR\"
[ -n \"\$CONFIG_BACKUP\" ] && [ -d \"\$CONFIG_BACKUP\" ] && rm -rf \"\$CONFIG_BACKUP\"
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

