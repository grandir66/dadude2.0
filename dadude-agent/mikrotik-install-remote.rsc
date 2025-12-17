# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Versione REMOTE-IMAGE (pull da GHCR)
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori qui sotto se necessario (cerca "MODIFICA")
# 2. Copia TUTTO lo script
# 3. Incollalo nella console RouterOS (Winbox o SSH)
# 4. Premi Invio
#
# NOTA: Questa versione scarica l'immagine da GitHub Container Registry
#       invece di importare da file tar (più affidabile)
#
# ==========================================

# ==========================================
# CONFIGURAZIONE - MODIFICA QUESTI VALORI SE NECESSARIO
# ==========================================
# MODIFICA: Token agent
:local agentToken "mio-token-rb5009"
# MODIFICA: ID agent
:local agentId "agent-rb5009-test"
# MODIFICA: Nome agent
:local agentName "RB5009 Test"

# Immagine Docker da GHCR (non modificare a meno che non cambi il registry)
:local remoteImage "ghcr.io/grandir66/dadude-agent-mikrotik:latest"

# ==========================================
# 1. Rimuovi container esistente (se presente)
# ==========================================
:do {
    /container/stop 0
    /container/remove 0
} on-error={}

# ==========================================
# 2. Rimuovi configurazioni esistenti (se presenti)
# ==========================================
:do {
    /interface/veth/remove [find name="veth-dadude-agent"]
} on-error={}
:do {
    /interface/bridge/port/remove [find bridge="bridge-dadude-agent"]
} on-error={}
:do {
    /interface/bridge/remove [find name="bridge-dadude-agent"]
} on-error={}
:do {
    /ip/firewall/nat/remove [find comment="dadude-agent-nat"]
} on-error={}
:do {
    /container/envs/remove [find name="dadude-env"]
} on-error={}

# ==========================================
# 3. Crea VETH interface per container
# ==========================================
/interface/veth/add name=veth-dadude-agent address=172.17.0.2/24 gateway=172.17.0.1

# ==========================================
# 4. Crea bridge per container
# ==========================================
/interface/bridge/add name=bridge-dadude-agent
/interface/bridge/port/add bridge=bridge-dadude-agent interface=veth-dadude-agent
/ip/address/add address=172.17.0.1/24 interface=bridge-dadude-agent

# ==========================================
# 5. Configura NAT per accesso internet (senza out-interface!)
# ==========================================
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 comment="dadude-agent-nat"

# ==========================================
# 5b. Container config su USB
# ==========================================
:do { /file/make-directory name="usb1/container-tmp" } on-error={}
:do { /file/make-directory name="usb1/dadude-agent" } on-error={}
/container/config/set tmpdir=usb1/container-tmp registry-url=https://ghcr.io

# ==========================================
# 6. Crea container da remote-image (GHCR)
# ==========================================
:local cmdLine "sh -c 'PYTHONPATH=/app DADUDE_SERVER_URL=https://dadude.domarc.it:8000 DADUDE_AGENT_TOKEN=mio-token-rb5009 DADUDE_AGENT_ID=agent-rb5009-test python -m app.agent'"

:put "Creazione container con remote-image..."
:put "Immagine: $remoteImage"
:put "NOTA: Il download potrebbe richiedere alcuni minuti..."

/container/add remote-image=$remoteImage interface=veth-dadude-agent root-dir=usb1/dadude-agent workdir=/ start-on-boot=yes logging=yes cmd=$cmdLine

# ==========================================
# 7. Attendi download immagine
# ==========================================
:put "Attendere il download dell'immagine..."
:put "Verifica stato con: /container/print"
:put ""
:put "Quando lo stato passa da 'extracting' a 'stopped', avvia con:"
:put "  /container/start 0"
:put ""

# Attendi un po' per il download
:delay 10s

# ==========================================
# 8. Verifica stato
# ==========================================
:put "=========================================="
:put "Stato attuale:"
:put "=========================================="
/container/print
:put ""
:put "Se lo stato è 'extracting', attendi che diventi 'stopped'"
:put "Poi avvia manualmente con: /container/start 0"
:put ""
:put "Per vedere i log:"
:put "  /container/logs 0"
:put ""
:put "IMPORTANTE:"
:put "L'agent si auto-registrerà al server."
:put "Vai su https://dadude.domarc.it:8001/agents per approvare l'agent."

