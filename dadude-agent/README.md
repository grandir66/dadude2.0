# DaDude Agent

Agent Docker per scansioni di rete remote, progettato per essere deployato su MikroTik RouterOS 7 (container) o qualsiasi host Docker nella rete del cliente.

## Funzionalità

- **WMI Probe**: Scansione dispositivi Windows (CPU, RAM, disco, OS, seriale)
- **SSH Probe**: Scansione dispositivi Linux/Unix
- **SNMP Probe**: Scansione dispositivi di rete (switch, router, AP, NAS)
- **Port Scan**: Scansione porte TCP/UDP
- **Reverse DNS**: Risoluzione nomi tramite DNS locale
- **Ping Check**: Verifica raggiungibilità host

## Architettura

```
┌─────────────────┐         ┌──────────────────┐
│  DaDude Server  │◄───────►│  DaDude Agent    │
│  (Central)      │  HTTPS  │  (Docker/MikroTik)│
└─────────────────┘         └──────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ Rete Cliente  │
                            │ - Windows     │
                            │ - Linux       │
                            │ - Switch/AP   │
                            └───────────────┘
```

## Requisiti MikroTik

- RouterOS 7.x con supporto Container
- Almeno 256MB RAM libera
- Storage per immagine Docker (~100MB)

## Installazione su MikroTik

### 1. Abilita Container

```routeros
/system/device-mode/update container=yes
```

Riavvia il router.

### 2. Configura Container

```routeros
# Crea VETH interface
/interface/veth/add name=veth-agent address=172.17.0.2/24 gateway=172.17.0.1

# Crea bridge per container
/interface/bridge/add name=docker
/interface/bridge/port/add bridge=docker interface=veth-agent

# Configura NAT per container
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24

# Crea mount per config
/container/mounts/add name=agent-config src=/agent dst=/app/config

# Aggiungi registry
/container/config/set registry-url=https://ghcr.io tmpdir=disk1/docker

# Pull e crea container
/container/add remote-image=ghcr.io/dadude/agent:latest interface=veth-agent root-dir=disk1/agent mounts=agent-config start-on-boot=yes
```

### 3. Configura Agent

Crea file `/agent/config.json` sul router:

```json
{
  "server_url": "https://your-dadude-server.com",
  "agent_token": "your-secure-token",
  "agent_id": "agent-cliente-xyz",
  "poll_interval": 60,
  "dns_servers": ["192.168.4.1", "8.8.8.8"]
}
```

## Installazione Docker Standalone

```bash
docker run -d \
  --name dadude-agent \
  --network host \
  -e DADUDE_SERVER_URL=https://your-server.com \
  -e DADUDE_AGENT_TOKEN=your-token \
  -e DADUDE_AGENT_ID=agent-001 \
  ghcr.io/dadude/agent:latest
```

## API Agent

L'agent espone una API REST sulla porta 8080:

### Health Check
```
GET /health
```

### Probe WMI
```
POST /probe/wmi
{
  "target": "192.168.4.4",
  "username": "admin",
  "password": "secret",
  "domain": "DOMAIN"
}
```

### Probe SSH
```
POST /probe/ssh
{
  "target": "192.168.1.100",
  "username": "root",
  "password": "secret",
  "port": 22
}
```

### Probe SNMP
```
POST /probe/snmp
{
  "target": "192.168.1.1",
  "community": "public",
  "version": "2c",
  "port": 161
}
```

### Port Scan
```
POST /scan/ports
{
  "target": "192.168.1.100",
  "ports": [22, 80, 443, 3389]
}
```

### Reverse DNS
```
POST /dns/reverse
{
  "targets": ["192.168.1.1", "192.168.1.2"],
  "dns_server": "192.168.4.1"
}
```

## Sicurezza

- Comunicazione HTTPS con il server centrale
- Autenticazione via token JWT
- Rate limiting per prevenire abusi
- Credenziali mai salvate su disco (solo in memoria durante l'esecuzione)

## Build

```bash
cd dadude-agent
docker build -t dadude-agent .
```

## Licenza

MIT

