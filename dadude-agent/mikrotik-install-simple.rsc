# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Versione semplificata per copia/incolla diretto
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori qui sotto se necessario (token, agentId, agentName)
# 2. Copia TUTTO lo script
# 3. Incollalo nella console RouterOS (Winbox o SSH)
# 4. Premi Invio
#
# ==========================================

# ==========================================
# CONFIGURAZIONE - VALORI PRECONFIGURATI (pronto all'uso)
# ==========================================
:local serverUrl "https://dadude.domarc.it:8000"
:local agentToken "mio-token-rb5009"
:local agentId "agent-rb5009-test"
:local agentName "RB5009 Test"
:local dnsServers "192.168.4.1,8.8.8.8"
:local imageFile "dadude-agent-mikrotik.tar.gz"

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
# 2. Trova immagine Docker (cerca in diverse posizioni)
# ==========================================
:local imagePath ""

# Cerca prima su USB (senza slash iniziale per RouterOS)
:if ([/file/print where name=("usb1/" . $imageFile)] != "") do={
    :set imagePath ("usb1/" . $imageFile)
    :put ("Immagine trovata su USB: usb1/" . $imageFile)
} else={
    # Cerca in root (con slash iniziale)
    :if ([/file/print where name=("/" . $imageFile)] != "") do={
        :set imagePath ("/" . $imageFile)
        :put ("Immagine trovata in root: /" . $imageFile)
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
# 8. Crea environment variables
# NOTA: RouterOS non accetta variabili nelle value, quindi usiamo valori letterali
# Modifica questi valori se necessario
# ==========================================
/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value="https://dadude.domarc.it:8000"
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value="mio-token-rb5009"
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value="agent-rb5009-test"
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value="RB5009 Test"
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
