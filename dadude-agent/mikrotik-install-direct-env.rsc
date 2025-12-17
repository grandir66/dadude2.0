# ==========================================
# DaDude Agent - Installazione con Environment Variables Dirette
# Versione alternativa che passa le env direttamente al container
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori qui sotto se necessario
# 2. Rimuovi il container esistente
# 3. Crea il nuovo container con questo script
#
# ==========================================

# Rimuovi container esistente
:do {
    /container/stop 0
    /container/remove 0
} on-error={}

# Crea container con environment variables direttamente nel comando
# NOTA: RouterOS potrebbe supportare env= direttamente invece di envlist
:do {
    /container/add file=usb1/dadude-agent-mikrotik.tar interface=veth-dadude-agent root-dir=usb1/dadude-agent start-on-boot=yes logging=yes cmd="python -m app.agent" env=DADUDE_SERVER_URL=https://dadude.domarc.it:8000 env=DADUDE_AGENT_TOKEN=mio-token-rb5009 env=DADUDE_AGENT_ID=agent-rb5009-test env=DADUDE_AGENT_NAME=RB5009\ Test env=DADUDE_DNS_SERVERS=192.168.4.1,8.8.8.8 env=PYTHONUNBUFFERED=1
    :put "Container creato con env dirette"
} on-error={
    :put "ERRORE: Impossibile creare container con env dirette"
    :put "Prova a creare il container senza env e aggiungerle dopo"
}

# Avvia container
:do {
    /container/start 0
    :put "Container avviato!"
} on-error={
    :put "ERRORE: Impossibile avviare il container"
}

# Verifica
:delay 2s
/container/print
/container/logs 0

