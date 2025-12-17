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
# Rimuovi envlist se esiste (non più necessario ma lasciamo per pulizia)
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
# 5b. Container tmpdir su USB (riduce errori di import/layer su storage interno)
# ==========================================
# Nota: RouterOS si aspetta una directory reale come tmpdir.
# La creiamo su USB e la impostiamo come tmpdir.
:do { /file/make-directory name="usb1/container-tmp" } on-error={}
/container/config/set tmpdir=usb1/container-tmp

# ==========================================
# 6. Crea container dall'immagine tar con environment variables nel comando
# NOTA: RouterOS non supporta /container/envs/add, quindi passiamo le env direttamente nel cmd
# MODIFICA: Cambia il percorso se l'immagine è in una posizione diversa
# ==========================================
# Comando breve (evita che il paste “rompa” la riga) + workdir=/ per evitare chdir su /app
# Usiamo PYTHONPATH=/app così Python trova il package `app` anche se workdir non è /app
:local cmdLine "sh -c 'PYTHONPATH=/app DADUDE_SERVER_URL=https://dadude.domarc.it:8000 DADUDE_AGENT_TOKEN=mio-token-rb5009 DADUDE_AGENT_ID=agent-rb5009-test python -m app.agent'"

# Prova prima con immagine su USB
# NOTA: Usiamo 'cd /app &&' nel comando invece di workdir perché RouterOS potrebbe non supportarlo
:do {
    :do { /file/make-directory name="usb1/dadude-agent" } on-error={}
    /container/add file=usb1/dadude-agent-mikrotik.tar interface=veth-dadude-agent root-dir=usb1/dadude-agent workdir=/ start-on-boot=yes logging=yes cmd=$cmdLine
    :put "Container creato con immagine su USB"
} on-error={
    # Se fallisce, prova con immagine in root
    :do {
        :do { /file/make-directory name="dadude-agent" } on-error={}
        /container/add file=/dadude-agent-mikrotik.tar interface=veth-dadude-agent root-dir=/dadude-agent workdir=/ start-on-boot=yes logging=yes cmd=$cmdLine
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
