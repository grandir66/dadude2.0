# ==========================================
# DaDude Agent - Installazione su MikroTik RB5009
# Versione semplificata per copia/incolla diretto
# ==========================================
# 
# ISTRUZIONI:
# 1. MODIFICA i valori qui sotto (token, agentId, agentName)
# 2. Copia TUTTO lo script
# 3. Incollalo nella console RouterOS (Winbox o SSH)
# 4. Premi Invio
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
# 2. Verifica che il disco USB sia montato
# ==========================================
:local usbFound 0
:local usbPath ""

# Prova diversi nomi comuni per il disco USB
:local usbNames {"usb1", "usb1-disk1", "disk1", "usb"}
:foreach usbName in=$usbNames do={
    :if ([/file/print where name=$usbName] != "") do={
        :set usbDisk $usbName
        :set usbFound 1
        :set usbPath ("/" . $usbName)
        :put ("Disco USB trovato: /" . $usbName)
    }
}

:if ($usbFound = 0) do={
    :put "ERRORE: Disco USB non trovato!"
    :put "Dischi disponibili:"
    /file/print
    :put ""
    :put "Modifica la variabile usbDisk nello script con il nome corretto"
}

# ==========================================
# 3. Verifica o scarica l'immagine Docker
# ==========================================
:local imagePath ""
:local imageFound 0

# Cerca l'immagine in diverse posizioni
:if ($usbFound = 1) do={
    :local usbImagePath ($usbPath . "/" . $imageFile)
    :if ([/file/print where name=$usbImagePath] != "") do={
        :set imagePath $usbImagePath
        :set imageFound 1
        :put ("Immagine trovata su " . $usbImagePath)
    } else={
        :if ([/file/print where name=("/" . $imageFile)] != "") do={
            :put ("Immagine trovata in root, spostando su " . $usbImagePath . "...")
            :do {
                /file/move source=("/" . $imageFile) destination=$usbImagePath
                :set imagePath $usbImagePath
                :set imageFound 1
                :put ("Immagine spostata su " . $usbImagePath)
            } on-error={
                :put "Impossibile spostare, uso quella in root"
                :set imagePath ("/" . $imageFile)
                :set imageFound 1
            }
        }
    }
} else={
    # Se USB non trovato, cerca solo in root
    :if ([/file/print where name=("/" . $imageFile)] != "") do={
        :set imagePath ("/" . $imageFile)
        :set imageFound 1
        :put ("Immagine trovata in root: " . $imagePath)
    }
}

# Se non trovata, scarica
:if ($imageFound = 0) do={
    :put "Immagine non trovata, scaricando da GitHub Releases..."
    :put "URL: $imageUrl"
    :put "Questo potrebbe richiedere alcuni minuti (file ~100-200MB)..."
    
    :if ($usbFound = 1) do={
        :local downloadPath ($usbPath . "/" . $imageFile)
        :do {
            /tool/fetch url=$imageUrl dst=$downloadPath mode=http
            :set imagePath $downloadPath
        } on-error={
            :put "Errore durante il download su " . $downloadPath . ", provo in root..."
            :do {
                /tool/fetch url=$imageUrl dst=("/" . $imageFile) mode=http
                :set imagePath ("/" . $imageFile)
            } on-error={
                :put "ERRORE: Download fallito!"
                :put "Verifica:"
                :put "  - Connessione internet attiva"
                :put "  - URL GitHub Releases accessibile"
                :put "  - Spazio sufficiente sul disco"
            }
        }
    } else={
        :do {
            /tool/fetch url=$imageUrl dst=("/" . $imageFile) mode=http
            :set imagePath ("/" . $imageFile)
        } on-error={
            :put "ERRORE: Download fallito!"
            :put "Verifica:"
            :put "  - Connessione internet attiva"
            :put "  - URL GitHub Releases accessibile"
            :put "  - Spazio sufficiente sul disco"
        }
    }
    
    :delay 2s
    
    # Verifica che il file sia stato scaricato
    :if ($imagePath = "") do={
        :if ($usbFound = 1) do={
            :local checkPath ($usbPath . "/" . $imageFile)
            :if ([/file/print where name=$checkPath] != "") do={
                :set imagePath $checkPath
            }
        }
        :if ($imagePath = "") do={
            :if ([/file/print where name=("/" . $imageFile)] != "") do={
                :set imagePath ("/" . $imageFile)
            } else={
                :put "ERRORE: Download fallito! Verifica la connessione internet e riprova."
            }
        }
    }
    
    # Verifica dimensione file solo se trovato
    :if ($imagePath != "") do={
        :local fileSize 0
        :do {
            :set fileSize ([/file/get $imagePath size])
        } on-error={
            :set fileSize 0
        }
        
        :if ($fileSize < 1048576) do={
            :put "ATTENZIONE: File scaricato potrebbe essere incompleto. Dimensione: $fileSize bytes"
        } else={
            :put "Immagine scaricata con successo! Dimensione: $fileSize bytes"
            :put "Percorso: $imagePath"
        }
    }
}

# Aggiorna imageFile con il percorso corretto
:if ($imagePath != "") do={
    :set imageFile ($imagePath)
} else={
    :put "ERRORE: Nessuna immagine trovata o scaricata!"
    :put "Verifica manualmente che l'immagine esista o che il download sia completato."
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
# NOTA: RouterOS richiede valori letterali o concatenazione corretta
# ==========================================
/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value=$serverUrl
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=$agentToken
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=$agentId
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=$agentName
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value=$dnsServers
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value="1"

# ==========================================
# 10. Crea container dall'immagine tar sul disco USB
# ==========================================
:if ($imagePath != "") do={
    :local rootDir ""
    :if ($usbFound = 1) do={
        :set rootDir ($usbPath . "/dadude-agent")
    } else={
        :set rootDir "/dadude-agent"
    }
    /container/add file=$imagePath interface=veth-dadude-agent root-dir=$rootDir envlist=dadude-env start-on-boot=yes logging=yes cmd="python -m app.agent"
} else={
    :put "ERRORE: Nessun file immagine trovato! Impossibile creare il container."
    :put "Verifica che l'immagine esista o che il download sia completato."
}

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

