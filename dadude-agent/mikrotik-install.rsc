# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Disco USB: /usb1
# Server: dadude.domarc.it
# Download automatico dell'immagine Docker da GitHub Releases
# ==========================================
# 
# ISTRUZIONI:
# 1. Assicurati che il disco USB sia formattato e montato come /usb1
# 2. Modifica agentToken e agentId qui sotto (il token può essere qualsiasi stringa)
# 3. L'immagine verrà scaricata automaticamente da GitHub Releases
# 4. Esegui questo script su RouterOS
#
# NOTA: Questo script viene generato ed eseguito automaticamente da deploy-mikrotik.sh
#       Non è necessario caricarlo manualmente su MikroTik
#
# ==========================================

# ==========================================
# CONFIGURAZIONE - MODIFICA QUESTI VALORI
# ==========================================
:local serverUrl "https://dadude.domarc.it:8000"
:local agentToken "INSERISCI_IL_TUO_TOKEN_QUI"
:local agentId "agent-rb5009-test"
:local agentName "RB5009 Test"
:local dnsServers "192.168.4.1,8.8.8.8"
:local imageFile "dadude-agent-mikrotik.tar.gz"
:local usbDisk "usb1"
# URL GitHub Releases - usa /latest/ per l'ultima release o /tag/vX.X.X/ per una versione specifica
:local imageUrl "https://github.com/grandir66/Dadude/releases/latest/download/dadude-agent-mikrotik.tar.gz"

# ==========================================
# 1. Verifica che Container Mode sia abilitato
# ==========================================
:if ([/system/device-mode/print] = "") do={
    :error "Container mode non abilitato! Esegui: /system/device-mode/update container=yes"
}

# ==========================================
# 2. Verifica che il disco USB sia montato
# ==========================================
:if ([/file/print where name=$usbDisk] = "") do={
    :error "Disco USB non trovato! Verifica che sia montato come /$usbDisk"
    :put "Per verificare i dischi disponibili: /file/print"
}

# ==========================================
# 3. Verifica o scarica l'immagine Docker
# ==========================================
:local imagePath ""
:local imageFound false

# Cerca l'immagine in diverse posizioni
:if ([/file/print where name=("/$usbDisk/$imageFile")] != "") do={
    :set imagePath ("/$usbDisk/$imageFile")
    :set imageFound true
    :put "✅ Immagine trovata su /$usbDisk/"
} else={
    :if ([/file/print where name=("/$imageFile")] != "") do={
        :put "Immagine trovata in root, spostando su /$usbDisk/..."
        :do {
            /file/move source=("/$imageFile") destination=("/$usbDisk/$imageFile")
            :set imagePath ("/$usbDisk/$imageFile")
            :set imageFound true
            :put "✅ Immagine spostata su /$usbDisk/"
        } on-error={
            :put "⚠️  Impossibile spostare, uso quella in root"
            :set imagePath ("/$imageFile")
            :set imageFound true
        }
    }
}

# Se non trovata, scarica
:if (not $imageFound) do={
    :put "Immagine non trovata, scaricando da GitHub Releases..."
    :put "URL: $imageUrl"
    :put "Questo potrebbe richiedere alcuni minuti (file ~100-200MB)..."
    
    :do {
        /tool/fetch url=$imageUrl dst=("/$usbDisk/$imageFile") mode=http
    } on-error={
        :put "⚠️  Errore durante il download su /$usbDisk/, provo in root..."
        :do {
            /tool/fetch url=$imageUrl dst=("/$imageFile") mode=http
            :set imagePath ("/$imageFile")
        } on-error={
            :error "Errore durante il download dell'immagine!"
            :put "Verifica:"
            :put "  - Connessione internet attiva"
            :put "  - URL GitHub Releases accessibile"
            :put "  - Spazio sufficiente sul disco"
        }
    }
    
    :delay 2s
    
    # Verifica che il file sia stato scaricato
    :if ($imagePath = "") do={
        :if ([/file/print where name=("/$usbDisk/$imageFile")] != "") do={
            :set imagePath ("/$usbDisk/$imageFile")
        } else={
            :if ([/file/print where name=("/$imageFile")] != "") do={
                :set imagePath ("/$imageFile")
            } else={
                :error "Download fallito! Verifica la connessione internet e riprova."
            }
        }
    }
    
    # Verifica dimensione file (deve essere > 1MB)
    :local fileSize 0
    :do {
        :set fileSize ([/file/get $imagePath size])
    } on-error={}
    
    :if ($fileSize < 1048576) do={
        :error "File scaricato troppo piccolo! Potrebbe essere un errore. Dimensione: $fileSize bytes"
    }
    
    :put "✅ Immagine scaricata con successo! Dimensione: $fileSize bytes"
    :put "   Percorso: $imagePath"
}

# Aggiorna imageFile con il percorso corretto
:if ($imagePath != "") do={
    :set imageFile ($imagePath)
}

# ==========================================
# 4. Rimuovi container esistente (se presente)
# ==========================================
:do {
    /container/stop 0
    /container/remove 0
} on-error={}

# ==========================================
# 5. Rimuovi configurazioni esistenti (se presenti)
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
# 6. Crea VETH interface per container
# ==========================================
/interface/veth/add name=veth-dadude-agent address=172.17.0.2/24 gateway=172.17.0.1

# ==========================================
# 7. Crea bridge per container
# ==========================================
/interface/bridge/add name=bridge-dadude-agent
/interface/bridge/port/add bridge=bridge-dadude-agent interface=veth-dadude-agent
/ip/address/add address=172.17.0.1/24 interface=bridge-dadude-agent

# ==========================================
# 8. Configura NAT per accesso internet
# ==========================================
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 out-interface=bridge-dadude-agent comment="dadude-agent-nat"

# ==========================================
# 9. Crea environment variables
# ==========================================
/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value=$serverUrl
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=$agentToken
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=$agentId
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=$agentName
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value=$dnsServers
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value="1"

# ==========================================
# 10. Crea container dall'immagine tar sul disco USB
# IMPORTANTE: root-dir punta a /usb1/dadude-agent
# ==========================================
/container/add \
    file=$imageFile \
    interface=veth-dadude-agent \
    root-dir=("/$usbDisk/dadude-agent") \
    envlist=dadude-env \
    start-on-boot=yes \
    logging=yes \
    cmd="python -m app.agent"

# ==========================================
# 11. Avvia container
# ==========================================
/container/start 0

# ==========================================
# 12. Verifica installazione
# ==========================================
:delay 3s
:put "=========================================="
:put "Installazione completata!"
:put "=========================================="
:put ""
:put "Disco USB: /$usbDisk"
:put "Container ID: 0"
:put "Stato:"
/container/print
:put ""
:put "Log (ultimi 20 righe):"
/container/logs 0 lines=20
:put ""
:put "Per vedere i log in tempo reale:"
:put "  /container/logs 0"
:put ""
:put "Per entrare nel container:"
:put "  /container/shell 0"
:put ""
:put "Per riavviare il container:"
:put "  /container/restart 0"
:put ""
:put "Per verificare spazio disco USB:"
:put "  /file/print where name=$usbDisk"
:put ""
:put "IMPORTANTE:"
:put "L'agent si auto-registrerà al server."
:put "Vai su https://dadude.domarc.it:8001/agents per approvare l'agent."
