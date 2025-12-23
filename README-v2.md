# DaDude v2.0 - Network Inventory & Monitoring System

Sistema di inventario e monitoraggio reti multi-tenant con:
- **Backend**: FastAPI + PostgreSQL + Redis
- **Frontend**: Vue.js 3 + Vuetify 3
- **Agent**: Python WebSocket distribuiti

## 🏗️ Architettura v2.0

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DaDude Server                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
│  │ Vue.js    │  │ FastAPI   │  │ WebSocket │  │PostgreSQL │        │
│  │ Frontend  │  │ Backend   │  │ Hub       │  │ + Redis   │        │
│  │ (Nginx)   │  │ (Uvicorn) │  │           │  │           │        │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └───────────┘        │
│        │              │              │                               │
│        └──────────────┴──────────────┘                               │
│                       │                                              │
│              Port 80 (HTTP) / 443 (HTTPS)                           │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬───────────────┐
        │               │               │               │
        ▼               ▼               ▼               ▼
  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
  │ Agent A   │   │ Agent B   │   │ Agent C   │   │ Agent D   │
  │ Site Roma │   │ Site Milano   │ Site Napoli   │ Site Torino
  │           │   │           │   │           │   │           │
  │ • Nmap    │   │ • Nmap    │   │ • Nmap    │   │ • Nmap    │
  │ • WMI     │   │ • WMI     │   │ • WMI     │   │ • WMI     │
  │ • SSH     │   │ • SSH     │   │ • SSH     │   │ • SSH     │
  │ • SNMP    │   │ • SNMP    │   │ • SNMP    │   │ • SNMP    │
  └───────────┘   └───────────┘   └───────────┘   └───────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
   Rete Locale     Rete Locale     Rete Locale     Rete Locale
```

---

## 📦 Installazione Server (Backend + Frontend)

### Requisiti
- Proxmox VE 7.x o 8.x
- Storage per container (local-lvm consigliato)
- Rete configurata (bridge vmbr0)

### Installazione Automatica su Proxmox LXC

```bash
# Download script
wget https://raw.githubusercontent.com/grandir66/dadude2.0/main/dadude/deploy/proxmox/install-server-v2.sh
chmod +x install-server-v2.sh

# Esecuzione con IP statico (consigliato)
./install-server-v2.sh \
  --ip 192.168.1.100/24 \
  --gateway 192.168.1.1

# Oppure interattivo
./install-server-v2.sh
```

### Opzioni disponibili

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `--ctid` | ID container Proxmox | auto |
| `--ip` | IP statico (es: 192.168.1.100/24) | richiesto |
| `--gateway` | Gateway | richiesto |
| `--bridge` | Bridge Proxmox | vmbr0 |
| `--storage` | Storage Proxmox | local-lvm |
| `--memory` | RAM in MB | 2048 |
| `--disk` | Disco in GB | 20 |
| `--dns` | Server DNS | 8.8.8.8 |

### Installazione Manuale con Docker Compose

```bash
# Clone repository
git clone https://github.com/grandir66/dadude2.0.git /opt/dadude
cd /opt/dadude/dadude

# Crea file .env
cat > .env << 'EOF'
# Database PostgreSQL
POSTGRES_USER=dadude
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=dadude

# Server
DADUDE_PORT=8000
DADUDE_API_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)

# Optional: MikroTik The Dude
# DUDE_HOST=192.168.1.1
# DUDE_USERNAME=admin
# DUDE_PASSWORD=yourpassword

# Logging
LOG_LEVEL=INFO
EOF

# Avvia tutti i servizi
docker compose -f docker-compose.v2.yml up -d --build

# Verifica
curl http://localhost:8000/api/v1/system/health
```

### Servizi inclusi

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Frontend | 80 | Vue.js UI |
| Backend | 8000 | FastAPI REST + WebSocket |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache / Session store |
| Adminer | 8080 | DB Admin (solo dev) |

---

## 🤖 Installazione Agent

Gli Agent sono componenti distribuiti che eseguono scansioni sulle reti remote. Ogni agent:
- Si connette al server via WebSocket
- Si auto-registra e attende approvazione
- Esegue scansioni Nmap, probe WMI/SSH/SNMP
- Supporta console remota per comandi

### Installazione Automatica su Proxmox LXC

```bash
# Download script di installazione
wget https://raw.githubusercontent.com/grandir66/dadude2.0/main/dadude-agent/deploy/proxmox/install-v2.sh
chmod +x install-v2.sh

# Esecuzione (richiede URL server)
./install-v2.sh --server-url http://192.168.1.100:8000

# Con tutte le opzioni
./install-v2.sh \
  --server-url http://192.168.1.100:8000 \
  --agent-name "Agent Sede Milano" \
  --ip 192.168.1.150/24 \
  --gateway 192.168.1.1 \
  --vlan 100
```

### Opzioni Agent

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `--server-url` | URL server DaDude | richiesto |
| `--agent-name` | Nome descrittivo | auto |
| `--ctid` | ID container Proxmox | auto |
| `--ip` | IP statico o 'dhcp' | dhcp |
| `--gateway` | Gateway | - |
| `--bridge` | Bridge Proxmox | vmbr0 |
| `--vlan` | VLAN tag | - |
| `--memory` | RAM in MB | 512 |

### Installazione Manuale Agent

```bash
# Clone repository
git clone https://github.com/grandir66/dadude2.0.git /opt/dadude-agent
cd /opt/dadude-agent/dadude-agent

# Configura
cat > .env << 'EOF'
DADUDE_SERVER_URL=http://192.168.1.100:8000
DADUDE_AGENT_ID=agent-$(hostname)-$(date +%s | tail -c 5)
DADUDE_AGENT_NAME=my-agent
DADUDE_AGENT_TOKEN=$(openssl rand -hex 32)
DADUDE_LOG_LEVEL=INFO
EOF

# Avvia con Docker
docker compose up -d --build

# Verifica logs
docker logs -f dadude-agent
```

### Flusso Registrazione Agent

```
1. Agent avviato → Si connette al server via WebSocket
2. Server riceve → Agent in stato "pending_approval"
3. Admin approva → Dalla UI, assegna agent a un cliente
4. Agent attivo → Pronto per scansioni e comandi
```

---

## 🖥️ Utilizzo Frontend

### Accesso
```
http://<IP_SERVER>/
```

### Pagine Principali

| Pagina | Descrizione |
|--------|-------------|
| Dashboard | Overview sistema, statistiche |
| Customers | Gestione clienti multi-tenant |
| Networks | Reti da monitorare per cliente |
| Devices | Dispositivi scoperti |
| Agents | Gestione agent (approvazione, comandi) |
| Discovery | Avvia scansioni di rete |
| Credentials | Credenziali per probe (WMI, SSH, SNMP) |
| Backups | Backup schedulati database |
| Settings | Configurazione sistema |

### Approvazione Agent

1. Vai su **Agents**
2. Nella sezione **"Pending Approval"** vedrai i nuovi agent
3. Clicca **Approve**
4. Seleziona il **Cliente** a cui assegnare l'agent
5. L'agent diventa operativo

### Avvio Scansione

1. Vai su **Discovery**
2. Seleziona **Cliente** e **Rete**
3. Scegli l'**Agent** (o "Server" per scansione locale)
4. Opzionale: abilita **Nmap** per port scanning
5. Clicca **Start Discovery**

---

## 🔧 Comandi Utili

### Server

```bash
# Logs backend
docker logs -f dadude-backend

# Logs frontend
docker logs -f dadude-frontend

# Riavvio completo
cd /opt/dadude/dadude
docker compose -f docker-compose.v2.yml restart

# Aggiornamento
cd /opt/dadude
git pull
docker compose -f dadude/docker-compose.v2.yml up -d --build

# Backup database
docker exec dadude-postgres pg_dump -U dadude dadude > backup.sql

# Accesso database
docker exec -it dadude-postgres psql -U dadude dadude
```

### Agent (da Proxmox host)

```bash
# Entra nel container LXC
pct enter <CTID>

# Logs agent
docker logs -f dadude-agent

# Riavvio agent
docker restart dadude-agent

# Rebuild agent
cd /opt/dadude-agent
docker compose up -d --build

# Health check
curl http://localhost:8080/health
```

---

## 🌐 Configurazione Reverse Proxy (Traefik)

Per esporre il server su internet con HTTPS:

```yaml
# /etc/traefik/conf.d/dadude.yaml
http:
  routers:
    dadude-frontend:
      rule: "Host(`dadude.tuodominio.it`)"
      entryPoints:
        - websecure
      service: dadude-frontend
      tls:
        certResolver: letsencrypt

    dadude-api:
      rule: "Host(`dadude.tuodominio.it`) && PathPrefix(`/api`)"
      entryPoints:
        - websecure
      service: dadude-backend
      tls:
        certResolver: letsencrypt

    dadude-ws:
      rule: "Host(`dadude.tuodominio.it`) && PathPrefix(`/ws`)"
      entryPoints:
        - websecure
      service: dadude-backend
      tls:
        certResolver: letsencrypt

  services:
    dadude-frontend:
      loadBalancer:
        servers:
          - url: "http://192.168.1.100:80"

    dadude-backend:
      loadBalancer:
        servers:
          - url: "http://192.168.1.100:8000"
```

---

## 📊 Variabili Ambiente

### Server (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `POSTGRES_USER` | Utente database | dadude |
| `POSTGRES_PASSWORD` | Password database | dadude_secret |
| `POSTGRES_DB` | Nome database | dadude |
| `DATABASE_URL` | URL completo PostgreSQL | auto |
| `REDIS_URL` | URL Redis | redis://redis:6379/0 |
| `DADUDE_PORT` | Porta API | 8000 |
| `DADUDE_API_KEY` | API key (opzionale) | - |
| `ENCRYPTION_KEY` | Chiave crittografia credenziali | richiesto |
| `LOG_LEVEL` | Livello log | INFO |
| `DUDE_HOST` | Host MikroTik The Dude | - |
| `DUDE_USERNAME` | Username The Dude | - |
| `DUDE_PASSWORD` | Password The Dude | - |

### Agent (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `DADUDE_SERVER_URL` | URL server DaDude | richiesto |
| `DADUDE_AGENT_ID` | ID univoco agent | auto |
| `DADUDE_AGENT_NAME` | Nome agent | hostname |
| `DADUDE_AGENT_TOKEN` | Token autenticazione | auto |
| `DADUDE_LOG_LEVEL` | Livello log | INFO |

---

## 🔒 Sicurezza

### Best Practices

1. **Cambia le password di default** nel file .env
2. **Usa HTTPS** con reverse proxy in produzione
3. **Limita accesso** al backend (firewall)
4. **Backup regolari** del database PostgreSQL
5. **Aggiorna regolarmente** i container

### Firewall Rules (esempio iptables)

```bash
# Solo frontend pubblico
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Backend solo da rete interna
iptables -A INPUT -p tcp --dport 8000 -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

---

## 📋 Funzionalità v2.0

### Nuove rispetto a v1.x

- ✅ **PostgreSQL** invece di SQLite
- ✅ **Redis** per cache e sessioni
- ✅ **Vue.js 3 + Vuetify 3** frontend moderno
- ✅ **Agent auto-registration** con approvazione
- ✅ **Nmap integration** per port scanning
- ✅ **Multi-tenant** completo con clienti separati
- ✅ **Backup scheduler** integrato
- ✅ **Console remota** su agent

### Funzionalità Core

- ✅ Scansione reti (ARP, Nmap, Ping)
- ✅ Port scanning TCP/UDP
- ✅ Riconoscimento vendor MAC
- ✅ Reverse DNS lookup
- ✅ OS fingerprinting
- ✅ Probe WMI (Windows)
- ✅ Probe SSH (Linux)
- ✅ Probe SNMP (Network devices)
- ✅ Gestione credenziali cifrate
- ✅ WebSocket real-time
- ✅ Agent distribuiti
- ✅ Multi-customer

---

## 🆘 Troubleshooting

### Agent non si connette

```bash
# Verifica logs
docker logs dadude-agent

# Verifica connettività
curl -v http://SERVER_URL:8000/api/v1/system/health

# Verifica DNS
nslookup SERVER_HOSTNAME
```

### Database connection error

```bash
# Verifica PostgreSQL
docker exec dadude-postgres pg_isready -U dadude

# Verifica logs
docker logs dadude-postgres
```

### Frontend non carica

```bash
# Verifica nginx
docker logs dadude-frontend

# Verifica build
docker exec dadude-frontend ls -la /usr/share/nginx/html
```

---

## 📄 Licenza

MIT License

## 🤝 Contributi

Contributi benvenuti! Apri una issue o pull request su [GitHub](https://github.com/grandir66/dadude2.0).
