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
:local imageUrl "https://github.com/grandir66/Dadude/releases/latest/download/dadude-agent-mikrotik.tar.gz"

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
# 2. Trova disco USB (prova diversi nomi)
# ==========================================
:local usbPath ""
:local usbFound 0

:if ([/file/print where name="usb1"] != "") do={
    :set usbPath "usb1"
    :set usbFound 1
    :put "Disco USB trovato: usb1"
} else={
    :if ([/file/print where name="usb1-disk1"] != "") do={
        :set usbPath "usb1-disk1"
        :set usbFound 1
        :put "Disco USB trovato: usb1-disk1"
    } else={
        :if ([/file/print where name="disk1"] != "") do={
            :set usbPath "disk1"
            :set usbFound 1
            :put "Disco USB trovato: disk1"
        } else={
            :put "ERRORE: Disco USB non trovato!"
            :put "Dischi disponibili:"
            /file/print
            :put ""
            :put "Modifica manualmente la variabile usbPath nello script"
        }
    }
}

# ==========================================
# 3. Verifica o scarica l'immagine Docker
# ==========================================
:local imagePath ""
:local imageFound 0

# Cerca l'immagine sul disco USB
:if ($usbFound = 1) do={
    :local usbImagePath ""
    :set usbImagePath ($usbPath . "/" . $imageFile)
    :if ([/file/print where name=$usbImagePath] != "") do={
        :set imagePath $usbImagePath
        :set imageFound 1
        :put ("Immagine trovata su " . $usbImagePath)
    }
}

# Se non trovata su USB, cerca in root
:if ($imageFound = 0) do={
    :local rootImagePath ""
    :set rootImagePath ("/" . $imageFile)
    :if ([/file/print where name=$rootImagePath] != "") do={
        :set imagePath $rootImagePath
        :set imageFound 1
        :put ("Immagine trovata in root: " . $imagePath)
    }
}

# Se ancora non trovata, scarica
:if ($imageFound = 0) do={
    :put "Immagine non trovata, scaricando da GitHub Releases..."
    :put ("URL: " . $imageUrl)
    :put "Questo potrebbe richiedere alcuni minuti (file ~100-200MB)..."
    
    :if ($usbFound = 1) do={
        :local downloadPath ""
        :set downloadPath ($usbPath . "/" . $imageFile)
        :do {
            /tool/fetch url=$imageUrl dst=$downloadPath mode=http
            :set imagePath $downloadPath
            :put ("Download completato su " . $downloadPath)
        } on-error={
            :put "Errore download su USB, provo in root..."
            :local rootDownload ""
            :set rootDownload ("/" . $imageFile)
            :do {
                /tool/fetch url=$imageUrl dst=$rootDownload mode=http
                :set imagePath $rootDownload
                :put ("Download completato in root: " . $imagePath)
            } on-error={
                :put "ERRORE: Download fallito!"
                :put "Verifica connessione internet e riprova"
            }
        }
    } else={
        :local rootDownload ""
        :set rootDownload ("/" . $imageFile)
        :do {
            /tool/fetch url=$imageUrl dst=$rootDownload mode=http
            :set imagePath $rootDownload
            :put ("Download completato in root: " . $imagePath)
        } on-error={
            :put "ERRORE: Download fallito!"
            :put "Verifica connessione internet e riprova"
        }
    }
    
    :delay 3s
    
    # Verifica che il file sia stato scaricato
    :if ($imagePath != "") do={
        :local fileSize 0
        :do {
            :set fileSize ([/file/get $imagePath size])
        } on-error={
            :set fileSize 0
        }
        
        :if ($fileSize < 1048576) do={
            :put ("ATTENZIONE: File potrebbe essere incompleto. Dimensione: " . $fileSize . " bytes")
        } else={
            :put ("Immagine scaricata con successo! Dimensione: " . $fileSize . " bytes")
        }
    }
}

:if ($imagePath = "") do={
    :put "ERRORE: Nessuna immagine trovata o scaricata!"
    :put "Impossibile continuare senza immagine Docker"
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
# NOTA: RouterOS richiede valori letterali, quindi costruiamo le stringhe
# ==========================================
:local envServerUrl ""
:set envServerUrl $serverUrl
:local envToken ""
:set envToken $agentToken
:local envId ""
:set envId $agentId
:local envName ""
:set envName $agentName
:local envDns ""
:set envDns $dnsServers

/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value=$envServerUrl
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=$envToken
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=$envId
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=$envName
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value=$envDns
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value="1"

# ==========================================
# 10. Crea container dall'immagine tar
# ==========================================
:if ($imagePath != "") do={
    :local rootDir ""
    :if ($usbFound = 1) do={
        :set rootDir ($usbPath . "/dadude-agent")
    } else={
        :set rootDir "/dadude-agent"
    }
    
    :put ("Creando container con immagine: " . $imagePath)
    :put ("Root directory: " . $rootDir)
    
    /container/add file=$imagePath interface=veth-dadude-agent root-dir=$rootDir envlist=dadude-env start-on-boot=yes logging=yes cmd="python -m app.agent"
} else={
    :put "ERRORE: Nessun file immagine trovato! Impossibile creare il container."
}

# ==========================================
# 11. Avvia container
# ==========================================
:do {
    /container/start 0
    :put "Container avviato con successo!"
} on-error={
    :put "ERRORE: Impossibile avviare il container"
    :put "Verifica i log con: /container/logs 0"
}

# ==========================================
# 12. Verifica installazione
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
