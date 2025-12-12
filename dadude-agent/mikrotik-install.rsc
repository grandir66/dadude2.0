# RouterOS 7 - DaDude Agent Container Setup
# Eseguire dopo aver abilitato container mode

# 1. Abilita container mode (richiede reboot)
# /system/device-mode/update container=yes

# 2. VETH interface per container
/interface/veth/add name=veth-agent address=172.17.0.2/24 gateway=172.17.0.1

# 3. Bridge per container
/interface/bridge/add name=docker
/interface/bridge/port/add bridge=docker interface=veth-agent
/ip/address/add address=172.17.0.1/24 interface=docker

# 4. NAT per accesso internet dal container
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24

# 5. Mount per config
/container/mounts/add name=agent-config src=/agent dst=/app/config

# 6. Environment variables
/container/envs/add name=agent-env key=DADUDE_SERVER_URL value="https://your-server.com"
/container/envs/add name=agent-env key=DADUDE_AGENT_ID value="mikrotik-agent-01"
/container/envs/add name=agent-env key=DADUDE_AGENT_TOKEN value="your-secure-token"
/container/envs/add name=agent-env key=DADUDE_DNS_SERVERS value="192.168.4.1"

# 7. Container da file tar (upload prima via FTP/SFTP)
/container/add file=dadude-agent-1.0.0.tar interface=veth-agent root-dir=disk1/agent mounts=agent-config envlist=agent-env start-on-boot=yes logging=yes

# 8. Avvia container
/container/start 0

# Verifica
# /container/print
# /container/shell 0

