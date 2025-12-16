# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Versione ultra-semplice - completamente hardcoded
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori qui sotto se necessario (cerca "MODIFICA")
# 2. Copia TUTTO lo script
# 3. Incollalo nella console RouterOS (Winbox o SSH)
# 4. Premi Invio
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
# 5. Configura NAT per accesso internet
# ==========================================
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 out-interface=bridge-dadude-agent comment="dadude-agent-nat"

# ==========================================
# 6. Crea environment variables
# NOTA: RouterOS potrebbe richiedere valori senza virgolette
# ==========================================
/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value=https://dadude.domarc.it:8000
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=$agentToken
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=$agentId
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=$agentName
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value=192.168.4.1,8.8.8.8
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value=1

# ==========================================
# 7. Crea container dall'immagine tar
# MODIFICA: Cambia il percorso se l'immagine è in una posizione diversa
# ==========================================
# Prova prima con immagine su USB
:do {
    /container/add file=usb1/dadude-agent-mikrotik.tar.gz interface=veth-dadude-agent root-dir=usb1/dadude-agent envlist=dadude-env start-on-boot=yes logging=yes cmd="python -m app.agent"
    :put "Container creato con immagine su USB"
} on-error={
    # Se fallisce, prova con immagine in root
    :do {
        /container/add file=/dadude-agent-mikrotik.tar.gz interface=veth-dadude-agent root-dir=/dadude-agent envlist=dadude-env start-on-boot=yes logging=yes cmd="python -m app.agent"
        :put "Container creato con immagine in root"
    } on-error={
        :put "ERRORE: Impossibile creare container!"
        :put "Verifica che l'immagine esista:"
        :put "  /file/print where name~dadude-agent-mikrotik"
    }
}

# ==========================================
# 8. Avvia container
# ==========================================
:do {
    /container/start 0
    :put "Container avviato con successo!"
} on-error={
    :put "ERRORE: Impossibile avviare il container"
    :put "Verifica i log con: /container/logs 0"
}

# ==========================================
# 9. Verifica installazione
# ==========================================
:delay 3s
:put "=========================================="
:put "Installazione completata!"
:put "=========================================="
/container/print
:put ""
:put "Per vedere i log:"
:put "  /container/logs 0"
:put ""
:put "Per entrare nel container:"
:put "  /container/shell 0"
:put ""
:put "IMPORTANTE:"
:put "L'agent si auto-registrerà al server."
:put "Vai su https://dadude.domarc.it:8001/agents per approvare l'agent."
