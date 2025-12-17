# ============================================================================
# DaDude Agent - Installazione MikroTik Container
# ============================================================================
#
# ISTRUZIONI:
# 1. Sostituisci solo USB_DISK_QUI con il tuo disco USB (es: usb1)
# 2. Agent ID e Token vengono generati automaticamente
# 3. Copia TUTTO e incolla su RouterOS
#
# ============================================================================

# Ottieni nome device RouterOS
:local deviceName [/system/identity/get name]
:local agentId ("agent-" . $deviceName)

:put ("Device: " . $deviceName)
:put ("Agent ID: " . $agentId)

# Genera token casuale sicuro (basato su MAC + timestamp)
:local routerMac ""
:do {
    :set routerMac [/interface/ethernet/get [find default-name~"ether"] mac-address]
} on-error={
    :set routerMac $deviceName
}

# Pulisci MAC
:local macClean ""
:local i 0
:while ($i < [:len $routerMac]) do={
    :local char [:pick $routerMac $i ($i + 1)]
    :if (($char != ":") && ($char != "-")) do={
        :set macClean ($macClean . $char)
    }
    :set i ($i + 1)
}

# Genera token: timestamp + ultimi 8 caratteri MAC
:local timestamp [/system/clock/get time]
:local timestampClean ""
:set i 0
:while ($i < [:len $timestamp]) do={
    :local char [:pick $timestamp $i ($i + 1)]
    :if (($char != ":") && ($char != "-") && ($char != " ")) do={
        :set timestampClean ($timestampClean . $char)
    }
    :set i ($i + 1)
}

:local macSuffix [:pick $macClean ([:len $macClean] - 8) [:len $macClean]]
:local agentToken ($timestampClean . "-" . $macSuffix)

:put ("Token generato: " . $agentToken)

# Pulizia completa
:do { /container/stop 0 } on-error={}
:do { /container/remove 0 } on-error={}
:do { /interface/veth/remove [find name="veth-dadude"] } on-error={}
:do { /interface/bridge/port/remove [find interface="veth-dadude"] } on-error={}
:do { /interface/bridge/remove [find name="br-dadude"] } on-error={}
:do { /ip/address/remove [find comment="dadude"] } on-error={}
:do { /ip/firewall/nat/remove [find comment="dadude"] } on-error={}

# Rete container
/interface/veth/add name=veth-dadude address=172.17.0.2/24 gateway=172.17.0.1
/interface/bridge/add name=br-dadude
/interface/bridge/port/add bridge=br-dadude interface=veth-dadude
/ip/address/add address=172.17.0.1/24 interface=br-dadude comment="dadude"
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 comment="dadude"

# Directory container
:do { /file/make-directory name="USB_DISK_QUI/container-tmp" } on-error={}
:do { /file/make-directory name="USB_DISK_QUI/dadude-agent" } on-error={}
/container/config/set tmpdir=USB_DISK_QUI/container-tmp registry-url=https://ghcr.io

# Costruisci comando container con agent_id e token generati
:local cmdBase "sh -c 'PYTHONPATH=/app DADUDE_SERVER_URL=https://dadude.domarc.it:8000 DADUDE_AGENT_TOKEN="
:local cmdMiddle " DADUDE_AGENT_ID="
:local cmdEnd " python -m app.agent'"
:local containerCmd ($cmdBase . $agentToken . $cmdMiddle . $agentId . $cmdEnd)

# Crea container
/container/add remote-image=ghcr.io/grandir66/dadude-agent-mikrotik:latest interface=veth-dadude root-dir=USB_DISK_QUI/dadude-agent workdir=/ dns=8.8.8.8 start-on-boot=yes logging=yes cmd=$containerCmd

:put ""
:put "=========================================="
:put "Container creato!"
:put "=========================================="
:put ("Agent ID: " . $agentId)
:put ("Token: " . $agentToken)
:put ""
:put "Attendi download immagine..."
:delay 10s
/container/print

:put ""
:put "Quando status=stopped, avvia con: /container/start 0"
:put "Log: /container/logs 0"
:put ""
:put "IMPORTANTE: Salva il token per riferimento futuro!"
