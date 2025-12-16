# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Versione completamente hardcoded - pronta all'uso
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori hardcoded qui sotto se necessario (cerca "MODIFICA")
# 2. Copia TUTTO lo script
# 3. Incollalo nella console RouterOS (Winbox o SSH)
# 4. Premi Invio
#
# ==========================================

# ==========================================
# CONFIGURAZIONE - MODIFICA QUESTI VALORI SE NECESSARIO
# ==========================================
# MODIFICA: Token agent (qualsiasi stringa)
:local agentToken "mio-token-rb5009"
# MODIFICA: ID agent
:local agentId "agent-rb5009-test"
# MODIFICA: Nome agent
:local agentName "RB5009 Test"

# ==========================================
# 1. Verifica che Container Mode sia abilitato
# ==========================================
:local containerMode ""
:do {
    :set containerMode ([/system/device-mode/get container])
} on-error={
    :set containerMode "no"
}

:if ($containerMode = "no") do={
    :put "ERRORE: Container mode non abilitato!"
    :put "Esegui: /system/device-mode/update container=yes"
    :put "Poi riavvia il router"
    :put "Dopo il riavvio, riesegui questo script"
}

# ==========================================
# 2. Trova immagine Docker (usa percorso hardcoded)
# ==========================================
:local imagePath ""

# Prova prima su USB
:if ([/file/print where name="usb1/dadude-agent-mikrotik.tar.gz"] != "") do={
    :set imagePath "usb1/dadude-agent-mikrotik.tar.gz"
    :put "Immagine trovata su USB: usb1/dadude-agent-mikrotik.tar.gz"
} else={
    # Prova in root
    :if ([/file/print where name="/dadude-agent-mikrotik.tar.gz"] != "") do={
        :set imagePath "/dadude-agent-mikrotik.tar.gz"
        :put "Immagine trovata in root: /dadude-agent-mikrotik.tar.gz"
    } else={
        :put "ERRORE: Immagine non trovata!"
        :put "Verifica che il file esista con: /file/print"
        :put "Cerca: usb1/dadude-agent-mikrotik.tar.gz o /dadude-agent-mikrotik.tar.gz"
    }
}

# ==========================================
# 3. Rimuovi container esistente (se presente)
# ==========================================
:do {
    /container/stop 0
    /container/remove 0
} on-error={}

# ==========================================
# 4. Rimuovi configurazioni esistenti (se presenti)
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
# 5. Crea VETH interface per container
# ==========================================
/interface/veth/add name=veth-dadude-agent address=172.17.0.2/24 gateway=172.17.0.1

# ==========================================
# 6. Crea bridge per container
# ==========================================
/interface/bridge/add name=bridge-dadude-agent
/interface/bridge/port/add bridge=bridge-dadude-agent interface=veth-dadude-agent
/ip/address/add address=172.17.0.1/24 interface=bridge-dadude-agent

# ==========================================
# 7. Configura NAT per accesso internet
# ==========================================
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 out-interface=bridge-dadude-agent comment="dadude-agent-nat"

# ==========================================
# 8. Crea environment variables (valori hardcoded)
# ==========================================
/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value="https://dadude.domarc.it:8000"
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=$agentToken
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=$agentId
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=$agentName
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value="192.168.4.1,8.8.8.8"
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value="1"

# ==========================================
# 9. Crea container dall'immagine tar
# ==========================================
:if ($imagePath != "") do={
    :local rootDir ""
    :if ([/file/print where name="usb1" and type="directory"] != "") do={
        :set rootDir "usb1/dadude-agent"
    } else={
        :set rootDir "/dadude-agent"
    }
    
    :put ("Creando container con immagine: " . $imagePath)
    :put ("Root directory: " . $rootDir)
    
    /container/add file=$imagePath interface=veth-dadude-agent root-dir=$rootDir envlist=dadude-env start-on-boot=yes logging=yes cmd="python -m app.agent"
} else={
    :put "ERRORE: Nessun file immagine trovato! Impossibile creare il container."
    :put "Verifica che l'immagine esista con: /file/print"
}

# ==========================================
# 10. Avvia container
# ==========================================
:do {
    /container/start 0
    :put "Container avviato con successo!"
} on-error={
    :put "ERRORE: Impossibile avviare il container"
    :put "Verifica i log con: /container/logs 0"
}

# ==========================================
# 11. Verifica installazione
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
