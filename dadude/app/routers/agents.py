"""
DaDude - Agents Router
API endpoints per registrazione e gestione dinamica degli agent
"""
from fastapi import APIRouter, HTTPException, Query, Header, Request
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

from ..services.customer_service import get_customer_service
from ..services.encryption_service import get_encryption_service

router = APIRouter(prefix="/agents", tags=["Agents"])


# ==========================================
# SCHEMAS
# ==========================================

class AgentRegistration(BaseModel):
    """Schema per auto-registrazione agent"""
    agent_id: str  # ID univoco dell'agent
    agent_name: str
    agent_type: str = "docker"  # docker, mikrotik
    version: str = "1.0.0"
    
    # Info rete rilevate dall'agent
    detected_ip: Optional[str] = None
    detected_hostname: Optional[str] = None
    
    # Capacità
    capabilities: Optional[List[str]] = None  # ["ssh", "snmp", "wmi", "nmap", "dns"]
    
    # Info sistema
    os_info: Optional[str] = None
    python_version: Optional[str] = None


class AgentHeartbeat(BaseModel):
    """Schema per heartbeat agent"""
    agent_id: str
    status: str = "online"
    version: Optional[str] = None
    detected_ip: Optional[str] = None
    uptime_seconds: Optional[int] = None
    last_scan_count: Optional[int] = None  # Numero scan eseguiti dall'ultimo heartbeat


class AgentConfigResponse(BaseModel):
    """Configurazione inviata dal server all'agent"""
    agent_id: str
    agent_name: str
    
    # Configurazione polling
    poll_interval: int = 60  # Secondi tra un poll e l'altro
    
    # DNS da usare per scansioni
    dns_servers: List[str] = ["8.8.8.8", "1.1.1.1"]
    
    # Range di porte da scansionare
    default_ports: List[int] = [22, 23, 80, 443, 161, 445, 3389, 8728]
    
    # Credenziali (opzionale, per scan automatici)
    # Non inviamo password in chiaro, solo riferimento
    credential_ids: List[str] = []
    
    # Reti assegnate all'agent
    assigned_networks: List[dict] = []
    
    # Ultimo aggiornamento config
    config_version: int = 1
    updated_at: Optional[str] = None


class AgentUpdateRequest(BaseModel):
    """Richiesta di aggiornamento configurazione agent dal server"""
    name: Optional[str] = None
    address: Optional[str] = None
    dns_servers: Optional[List[str]] = None
    poll_interval: Optional[int] = None
    assigned_networks: Optional[List[str]] = None
    active: Optional[bool] = None


# ==========================================
# AGENT SELF-SERVICE ENDPOINTS
# ==========================================

@router.post("/register")
async def register_agent(
    data: AgentRegistration,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Auto-registrazione di un nuovo agent.
    
    L'agent chiama questo endpoint al primo avvio per registrarsi.
    Il server crea un record temporaneo che deve essere approvato
    da un amministratore e associato a un cliente.
    """
    service = get_customer_service()
    encryption = get_encryption_service()
    
    # Estrai IP reale dalla request se non fornito
    client_ip = data.detected_ip
    if not client_ip:
        client_ip = request.client.host if request.client else None
    
    logger.info(f"Agent registration request: {data.agent_id} from {client_ip}")
    
    # Verifica se agent già esiste (per ID, nome o indirizzo)
    try:
        existing = service.get_agent_by_unique_id(data.agent_id, address=client_ip)
        if existing:
            # Aggiorna info esistente
            logger.info(f"Agent {data.agent_id} already registered, updating info")
            
            # Aggiorna IP e status
            service.update_agent_status(
                existing.id, 
                status="online",
                version=data.version
            )
            
            # Se IP cambiato, aggiornalo
            if client_ip and client_ip != existing.address:
                logger.info(f"Agent {data.agent_id} IP changed: {existing.address} -> {client_ip}")
                service.update_agent_address(existing.id, client_ip)
            
            return {
                "success": True,
                "registered": False,
                "updated": True,
                "agent_db_id": existing.id,
                "message": "Agent info updated"
            }
    except Exception as e:
        logger.debug(f"Agent not found, will create: {e}")
    
    # Crea nuovo agent (senza customer_id - deve essere approvato)
    try:
        from ..models.database import AgentAssignment, generate_uuid, init_db, get_session
        from ..config import get_settings
        
        settings = get_settings()
        db_url = settings.database_url.replace("+aiosqlite", "")
        engine = init_db(db_url)
        session = get_session(engine)
        
        # Genera token per l'agent
        import secrets
        agent_token = secrets.token_urlsafe(32)
        
        agent = AgentAssignment(
            id=generate_uuid(),
            customer_id=None,  # Da assegnare manualmente
            name=data.agent_name,
            address=client_ip or "pending",
            port=8080,
            agent_type=data.agent_type,
            agent_api_port=8080,
            agent_token=encryption.encrypt(agent_token),
            agent_url=f"http://{client_ip}:8080" if client_ip else None,
            status="pending_approval",
            version=data.version,
            active=False,  # Inattivo finché non approvato
        )
        
        # Salva capabilities come JSON
        if data.capabilities:
            import json
            agent.notes = json.dumps({"capabilities": data.capabilities, "os_info": data.os_info})
        
        session.add(agent)
        session.commit()
        
        logger.success(f"New agent registered: {data.agent_id} ({data.agent_name}) from {client_ip}")
        
        return {
            "success": True,
            "registered": True,
            "agent_db_id": agent.id,
            "agent_token": agent_token,  # Invia token solo alla prima registrazione
            "message": "Agent registered successfully. Awaiting admin approval.",
            "next_steps": [
                "Save the agent_token securely",
                "An admin will approve and assign this agent to a customer",
                "Once approved, the agent will receive its configuration"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat")
async def agent_heartbeat(
    data: AgentHeartbeat,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Heartbeat periodico dall'agent.
    Aggiorna lo stato e restituisce eventuali comandi pendenti.
    """
    service = get_customer_service()
    
    # Estrai IP dalla request
    client_ip = data.detected_ip or (request.client.host if request.client else None)
    
    try:
        # Trova agent
        agent = service.get_agent_by_unique_id(data.agent_id)
        if not agent:
            return {
                "success": False,
                "error": "Agent not registered",
                "action": "register"  # Dice all'agent di registrarsi
            }
        
        # Aggiorna status
        service.update_agent_status(agent.id, status=data.status, version=data.version)
        
        # Se IP cambiato, aggiornalo
        if client_ip and client_ip != agent.address:
            service.update_agent_address(agent.id, client_ip)
        
        # Controlla se ci sono comandi pendenti
        # (future: scan requests, config updates, etc.)
        
        return {
            "success": True,
            "agent_db_id": agent.id,
            "active": agent.active,
            "config_changed": False,  # Future: True se config è cambiata
            "commands": []  # Future: comandi da eseguire
        }
        
    except Exception as e:
        logger.error(f"Heartbeat failed for {data.agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/{agent_id}")
async def get_agent_config(
    agent_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Ottiene la configurazione corrente per un agent.
    L'agent chiama questo endpoint per ottenere/aggiornare la sua config.
    """
    service = get_customer_service()
    
    try:
        agent = service.get_agent_by_unique_id(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if not agent.active:
            return {
                "success": False,
                "error": "Agent not approved yet",
                "status": "pending_approval"
            }
        
        # Costruisci configurazione
        config = AgentConfigResponse(
            agent_id=agent_id,
            agent_name=agent.name,
            poll_interval=60,  # Default, potrebbe essere configurabile
            dns_servers=agent.dns_server.split(",") if agent.dns_server else ["8.8.8.8"],
            default_ports=[22, 23, 80, 443, 161, 445, 3389, 8728],
            config_version=1,
            updated_at=agent.updated_at.isoformat() if agent.updated_at else None,
        )
        
        # Aggiungi reti assegnate se customer_id presente
        if agent.customer_id:
            networks = service.list_networks(customer_id=agent.customer_id)
            config.assigned_networks = [
                {"id": n.id, "name": n.name, "cidr": n.cidr}
                for n in networks
            ]
        
        return {
            "success": True,
            "config": config.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ADMIN ENDPOINTS
# ==========================================

@router.get("/pending")
async def list_pending_agents():
    """
    Lista agent in attesa di approvazione.
    """
    from ..models.database import AgentAssignment, init_db, get_session
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        agents = session.query(AgentAssignment).filter(
            AgentAssignment.customer_id == None,
            AgentAssignment.status == "pending_approval"
        ).all()
        
        return {
            "total": len(agents),
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "address": a.address,
                    "agent_type": a.agent_type,
                    "version": a.version,
                    "status": a.status,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in agents
            ]
        }
    finally:
        session.close()


# ==========================================
# SERVER UPDATE SYSTEM
# (MUST be before routes with path parameters)
# ==========================================

# Versione corrente del server
SERVER_VERSION = "1.1.0"
GITHUB_REPO = "grandir66/dadude"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"


@router.get("/server/version")
async def get_server_version():
    """
    Restituisce la versione corrente del server.
    """
    return {
        "version": SERVER_VERSION,
        "agent_version": AGENT_VERSION,
        "repository": f"https://github.com/{GITHUB_REPO}",
    }


@router.get("/server/check-update")
async def check_server_update():
    """
    Controlla se è disponibile una nuova versione del server su GitHub.
    """
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=15) as client:
            # Controlla l'ultimo tag/release
            response = await client.get(
                f"{GITHUB_API}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code == 200:
                release = response.json()
                latest_version = release.get("tag_name", "").lstrip("v")
                
                needs_update = _compare_versions(SERVER_VERSION, latest_version) < 0
                
                return {
                    "success": True,
                    "current_version": SERVER_VERSION,
                    "latest_version": latest_version,
                    "needs_update": needs_update,
                    "release_name": release.get("name"),
                    "release_date": release.get("published_at"),
                    "release_url": release.get("html_url"),
                    "changelog": release.get("body", "")[:500],
                }
            elif response.status_code == 404:
                # Nessuna release pubblicata, prova con i commit
                commits_resp = await client.get(
                    f"{GITHUB_API}/commits?per_page=1",
                    headers={"Accept": "application/vnd.github.v3+json"}
                )
                
                if commits_resp.status_code == 200:
                    commits = commits_resp.json()
                    if commits:
                        latest_commit = commits[0]
                        return {
                            "success": True,
                            "current_version": SERVER_VERSION,
                            "latest_version": "dev",
                            "needs_update": True,
                            "release_name": "Latest commit",
                            "release_date": latest_commit.get("commit", {}).get("author", {}).get("date"),
                            "release_url": latest_commit.get("html_url"),
                            "changelog": latest_commit.get("commit", {}).get("message", "")[:500],
                            "commit_sha": latest_commit.get("sha", "")[:8],
                        }
                
                return {
                    "success": False,
                    "current_version": SERVER_VERSION,
                    "error": "No releases or commits found",
                }
            else:
                return {
                    "success": False,
                    "current_version": SERVER_VERSION,
                    "error": f"GitHub API error: {response.status_code}",
                }
                
    except Exception as e:
        logger.error(f"Failed to check server update: {e}")
        return {
            "success": False,
            "current_version": SERVER_VERSION,
            "error": str(e),
        }


@router.get("/server/commits")
async def get_recent_commits():
    """
    Ottiene gli ultimi commit dal repository GitHub.
    """
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{GITHUB_API}/commits?per_page=10",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code == 200:
                commits = response.json()
                return {
                    "success": True,
                    "commits": [
                        {
                            "sha": c.get("sha", "")[:8],
                            "message": c.get("commit", {}).get("message", "").split("\n")[0],
                            "author": c.get("commit", {}).get("author", {}).get("name"),
                            "date": c.get("commit", {}).get("author", {}).get("date"),
                            "url": c.get("html_url"),
                        }
                        for c in commits
                    ]
                }
            else:
                return {
                    "success": False,
                    "error": f"GitHub API error: {response.status_code}",
                }
                
    except Exception as e:
        logger.error(f"Failed to get commits: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/server/update")
async def trigger_server_update():
    """
    Avvia l'aggiornamento del server (git pull).
    NOTA: Richiede riavvio manuale del server dopo l'update.
    """
    import subprocess
    import os
    
    # Determina la directory del progetto
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            output = result.stdout
            already_up_to_date = "Already up to date" in output or "Già aggiornato" in output
            
            return {
                "success": True,
                "already_up_to_date": already_up_to_date,
                "message": "Update completed" if not already_up_to_date else "Already up to date",
                "output": output,
                "needs_restart": not already_up_to_date,
            }
        else:
            return {
                "success": False,
                "error": result.stderr or "Git pull failed",
                "output": result.stdout,
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Update timed out",
        }
    except Exception as e:
        logger.error(f"Failed to update server: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/server/restart")
async def trigger_server_restart():
    """
    Riavvia il server.
    Per Docker: restarta il container.
    Per processo diretto: esegue reload.
    """
    import os
    
    try:
        in_docker = os.path.exists("/.dockerenv")
        
        if in_docker:
            return {
                "success": True,
                "message": "Server is running in Docker. Please restart the container manually.",
                "command": "docker restart dadude-server",
            }
        else:
            import signal
            os.kill(os.getpid(), signal.SIGHUP)
            
            return {
                "success": True,
                "message": "Restart signal sent",
            }
            
    except Exception as e:
        logger.error(f"Failed to restart server: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ==========================================
# AGENT-SPECIFIC ROUTES (with path parameters)
# ==========================================

@router.post("/{agent_db_id}/approve")
async def approve_agent(
    agent_db_id: str,
    customer_id: str = Query(..., description="ID cliente a cui assegnare l'agent"),
):
    """
    Approva un agent e lo assegna a un cliente.
    """
    service = get_customer_service()
    
    try:
        agent = service.get_agent(agent_db_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Verifica che il cliente esista
        customer = service.get_customer(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Aggiorna agent
        from ..models.database import AgentAssignment, init_db, get_session
        from ..config import get_settings
        
        settings = get_settings()
        db_url = settings.database_url.replace("+aiosqlite", "")
        engine = init_db(db_url)
        session = get_session(engine)
        
        db_agent = session.query(AgentAssignment).filter(
            AgentAssignment.id == agent_db_id
        ).first()
        
        if db_agent:
            db_agent.customer_id = customer_id
            db_agent.active = True
            db_agent.status = "online"
            session.commit()
        
        session.close()
        
        logger.success(f"Agent {agent.name} approved and assigned to {customer.name}")
        
        return {
            "success": True,
            "message": f"Agent assigned to {customer.name}",
            "agent_id": agent_db_id,
            "customer_id": customer_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_db_id}/update-address")
async def update_agent_address(
    agent_db_id: str,
    new_address: str = Query(..., description="Nuovo indirizzo IP"),
):
    """
    Aggiorna l'indirizzo IP di un agent dal pannello admin.
    """
    service = get_customer_service()
    
    try:
        success = service.update_agent_address(agent_db_id, new_address)
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return {
            "success": True,
            "message": f"Agent address updated to {new_address}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent address: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_db_id}/config")
async def update_agent_config(
    agent_db_id: str,
    data: AgentUpdateRequest,
):
    """
    Aggiorna la configurazione di un agent dal pannello admin.
    La nuova config sarà inviata all'agent al prossimo poll.
    """
    service = get_customer_service()
    
    try:
        agent = service.get_agent(agent_db_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Aggiorna campi
        from ..models.database import AgentAssignment, init_db, get_session
        from ..config import get_settings
        
        settings = get_settings()
        db_url = settings.database_url.replace("+aiosqlite", "")
        engine = init_db(db_url)
        session = get_session(engine)
        
        db_agent = session.query(AgentAssignment).filter(
            AgentAssignment.id == agent_db_id
        ).first()
        
        if db_agent:
            if data.name:
                db_agent.name = data.name
            if data.address:
                db_agent.address = data.address
                db_agent.agent_url = f"http://{data.address}:{db_agent.agent_api_port}"
            if data.dns_servers:
                db_agent.dns_server = ",".join(data.dns_servers)
            if data.active is not None:
                db_agent.active = data.active
            
            session.commit()
        
        session.close()
        
        return {
            "success": True,
            "message": "Agent configuration updated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# AGENT UPDATE/UPGRADE SYSTEM
# ==========================================

# Versione corrente dell'agent (da aggiornare ad ogni release)
AGENT_VERSION = "1.1.0"

@router.get("/version")
async def get_current_agent_version():
    """Restituisce la versione corrente dell'agent disponibile sul server"""
    return {
        "version": AGENT_VERSION,
        "download_url": "/api/v1/agents/download/agent-package.tar.gz",
        "changelog": "https://github.com/grandir66/dadude/releases",
    }


@router.get("/{agent_db_id}/check-update")
async def check_agent_update(agent_db_id: str):
    """
    Controlla se un agent ha bisogno di aggiornamento.
    Legge la versione dal database.
    """
    service = get_customer_service()
    
    agent = service.get_agent(agent_db_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent_version = agent.version or "0.0.0"
    needs_update = _compare_versions(agent_version, AGENT_VERSION) < 0
    
    return {
        "agent_id": agent_db_id,
        "current_version": agent_version,
        "latest_version": AGENT_VERSION,
        "needs_update": needs_update,
    }


@router.get("/{agent_db_id}/verify-version")
async def verify_agent_version(agent_db_id: str):
    """
    Verifica la versione REALE dell'agent contattandolo direttamente.
    Aggiorna il database con la versione rilevata.
    """
    service = get_customer_service()
    encryption = get_encryption_service()
    
    agent = service.get_agent(agent_db_id, include_password=True)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.agent_url:
        raise HTTPException(status_code=400, detail="Agent URL not configured")
    
    # Decripta token
    agent_token = None
    if hasattr(agent, 'agent_token') and agent.agent_token:
        try:
            agent_token = encryption.decrypt(agent.agent_token)
        except:
            agent_token = agent.agent_token
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{agent.agent_url}/health",
                headers={"Authorization": f"Bearer {agent_token}"} if agent_token else {}
            )
            
            if response.status_code == 200:
                data = response.json()
                real_version = data.get("version", "unknown")
                
                # Aggiorna versione nel database
                if real_version != "unknown":
                    service.update_agent_status(agent_db_id, version=real_version)
                
                needs_update = _compare_versions(real_version, AGENT_VERSION) < 0
                
                return {
                    "success": True,
                    "agent_id": agent_db_id,
                    "agent_name": agent.name,
                    "db_version": agent.version or "N/A",
                    "real_version": real_version,
                    "latest_version": AGENT_VERSION,
                    "needs_update": needs_update,
                    "version_match": (agent.version or "") == real_version,
                    "agent_online": True,
                    "agent_info": {
                        "agent_id": data.get("agent_id"),
                        "agent_name": data.get("agent_name"),
                        "uptime": data.get("uptime_seconds"),
                    }
                }
            else:
                return {
                    "success": False,
                    "agent_id": agent_db_id,
                    "agent_online": False,
                    "error": f"Agent returned {response.status_code}",
                }
                
    except Exception as e:
        logger.error(f"Failed to verify version for agent {agent_db_id}: {e}")
        return {
            "success": False,
            "agent_id": agent_db_id,
            "agent_online": False,
            "error": str(e),
        }


@router.post("/{agent_db_id}/trigger-update")
async def trigger_agent_update(agent_db_id: str):
    """
    Invia comando di aggiornamento all'agent.
    L'agent scaricherà la nuova versione e si riavvierà.
    """
    service = get_customer_service()
    encryption = get_encryption_service()
    
    agent = service.get_agent(agent_db_id, include_password=True)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.agent_url:
        raise HTTPException(status_code=400, detail="Agent URL not configured")
    
    # Decripta token
    agent_token = None
    if hasattr(agent, 'agent_token') and agent.agent_token:
        try:
            agent_token = encryption.decrypt(agent.agent_token)
        except:
            agent_token = agent.agent_token
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{agent.agent_url}/admin/update",
                json={
                    "version": AGENT_VERSION,
                    "download_url": f"https://raw.githubusercontent.com/grandir66/dadude/main/dadude-agent/",
                },
                headers={"Authorization": f"Bearer {agent_token}"} if agent_token else {}
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "Update triggered successfully",
                    "agent_response": result,
                }
            else:
                return {
                    "success": False,
                    "error": f"Agent returned {response.status_code}: {response.text}",
                }
                
    except Exception as e:
        logger.error(f"Failed to trigger update for agent {agent_db_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_db_id}/restart")
async def restart_agent(agent_db_id: str):
    """
    Invia comando di riavvio all'agent.
    """
    service = get_customer_service()
    encryption = get_encryption_service()
    
    agent = service.get_agent(agent_db_id, include_password=True)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.agent_url:
        raise HTTPException(status_code=400, detail="Agent URL not configured")
    
    agent_token = None
    if hasattr(agent, 'agent_token') and agent.agent_token:
        try:
            agent_token = encryption.decrypt(agent.agent_token)
        except:
            agent_token = agent.agent_token
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{agent.agent_url}/admin/restart",
                headers={"Authorization": f"Bearer {agent_token}"} if agent_token else {}
            )
            
            return {
                "success": response.status_code == 200,
                "message": "Restart command sent" if response.status_code == 200 else response.text,
            }
                
    except Exception as e:
        # L'agent potrebbe disconnettersi durante il riavvio
        return {
            "success": True,
            "message": "Restart command sent (agent may be restarting)",
        }


@router.get("/outdated")
async def list_outdated_agents():
    """
    Lista tutti gli agent che hanno bisogno di aggiornamento.
    """
    from ..models.database import AgentAssignment, init_db, get_session
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        agents = session.query(AgentAssignment).filter(
            AgentAssignment.active == True
        ).all()
        
        outdated = []
        for agent in agents:
            agent_version = agent.version or "0.0.0"
            if _compare_versions(agent_version, AGENT_VERSION) < 0:
                outdated.append({
                    "id": agent.id,
                    "name": agent.name,
                    "address": agent.address,
                    "current_version": agent_version,
                    "latest_version": AGENT_VERSION,
                    "customer_id": agent.customer_id,
                })
        
        return {
            "total_agents": len(agents),
            "outdated_count": len(outdated),
            "latest_version": AGENT_VERSION,
            "outdated_agents": outdated,
        }
    finally:
        session.close()


@router.post("/update-all")
async def update_all_agents():
    """
    Invia comando di aggiornamento a tutti gli agent outdated.
    """
    outdated_result = await list_outdated_agents()
    
    results = []
    for agent in outdated_result.get("outdated_agents", []):
        try:
            result = await trigger_agent_update(agent["id"])
            results.append({
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "success": result.get("success", False),
                "message": result.get("message") or result.get("error"),
            })
        except Exception as e:
            results.append({
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "success": False,
                "message": str(e),
            })
    
    return {
        "total_updated": sum(1 for r in results if r["success"]),
        "total_failed": sum(1 for r in results if not r["success"]),
        "results": results,
    }


def _compare_versions(v1: str, v2: str) -> int:
    """
    Confronta due versioni semver.
    Ritorna: -1 se v1 < v2, 0 se v1 == v2, 1 se v1 > v2
    """
    def parse(v):
        parts = v.replace("-", ".").split(".")
        return [int(p) if p.isdigit() else 0 for p in parts[:3]]
    
    p1, p2 = parse(v1), parse(v2)
    
    for a, b in zip(p1, p2):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0

