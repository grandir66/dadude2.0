"""
DaDude - MikroTik Router Endpoints
API per gestione MikroTik remoti e Dude Agent
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from loguru import logger


router = APIRouter(prefix="/mikrotik", tags=["MikroTik"])


# ==========================================
# SCHEMAS
# ==========================================

class NetwatchCreate(BaseModel):
    host: str
    port: Optional[int] = None
    interval: str = "30s"
    timeout: str = "3s"
    up_script: Optional[str] = None
    down_script: Optional[str] = None
    comment: Optional[str] = None


# ==========================================
# DUDE AGENTS
# ==========================================

@router.post("/dude-agents/sync")
async def sync_dude_agents():
    """Sincronizza agent dal server The Dude"""
    from ..services.dude_agent_sync import get_dude_agent_sync_service
    
    sync_service = get_dude_agent_sync_service()
    result = sync_service.sync_agents()
    
    return result


@router.get("/dude-agents")
async def list_dude_agents(
    customer_id: Optional[str] = Query(None, description="Filtra per cliente"),
):
    """Lista agent Dude sincronizzati"""
    from ..services.dude_agent_sync import get_dude_agent_sync_service
    
    sync_service = get_dude_agent_sync_service()
    agents = sync_service.list_agents(customer_id=customer_id)
    
    return {
        "count": len(agents),
        "agents": agents,
    }


@router.get("/dude-agents/available")
async def list_available_agents():
    """Lista agent non ancora associati a clienti"""
    from ..services.dude_agent_sync import get_dude_agent_sync_service
    
    sync_service = get_dude_agent_sync_service()
    agents = sync_service.get_available_agents()
    
    return {
        "count": len(agents),
        "agents": agents,
    }


@router.post("/dude-agents/{agent_id}/assign/{customer_id}")
async def assign_agent_to_customer(agent_id: str, customer_id: str):
    """Associa agent Dude a un cliente"""
    from ..services.dude_agent_sync import get_dude_agent_sync_service
    
    sync_service = get_dude_agent_sync_service()
    result = sync_service.assign_to_customer(agent_id, customer_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.delete("/dude-agents/{agent_id}/unassign")
async def unassign_agent_from_customer(agent_id: str):
    """Rimuove associazione agent-cliente"""
    from ..services.dude_agent_sync import get_dude_agent_sync_service
    
    sync_service = get_dude_agent_sync_service()
    result = sync_service.unassign_from_customer(agent_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


# ==========================================
# ROUTER OPERATIONS (via Credentials - Direct)
# ==========================================

@router.get("/credentials/{credential_id}/system-info")
async def get_router_system_info_by_credential(credential_id: str):
    """Ottiene informazioni sistema del router tramite credenziale"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    credential = customer_service.get_credential(credential_id, include_password=True)
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credenziale non trovata")
    
    if credential.credential_type not in ["mikrotik", "ssh", "device"]:
        raise HTTPException(status_code=400, detail="Credenziale non supporta MikroTik")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_system_info(
        address=credential.address or "",
        port=credential.port or 8728,
        username=credential.username or "admin",
        password=credential.password or "",
        use_ssl=credential.use_ssl if hasattr(credential, 'use_ssl') else False,
    )
    
    return result


@router.post("/credentials/{credential_id}/backup")
async def backup_router_by_credential(
    credential_id: str,
    backup_type: str = Query("export", description="Tipo backup: export, binary, both"),
):
    """Esegue backup configurazione router tramite credenziale"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_backup_collector import MikroTikBackupCollector
    import os
    
    customer_service = get_customer_service()
    credential = customer_service.get_credential(credential_id, include_password=True)
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credenziale non trovata")
    
    # Determina customer per path backup
    customer = None
    if credential.customer_id:
        customer = customer_service.get_customer(credential.customer_id)
    
    backup_path = None
    if customer:
        backup_base = os.getenv('BACKUP_PATH', './backups')
        backup_path = os.path.join(backup_base, customer.code or "default")
    
    collector = MikroTikBackupCollector()
    result = collector.backup_configuration(
        host=credential.address or "",
        username=credential.username or "admin",
        password=credential.password or "",
        port=credential.ssh_port or 22,
        backup_path=backup_path,
        backup_type=backup_type,
    )
    
    return result


# ==========================================
# ROUTER OPERATIONS (via Agent Assignment)
# ==========================================

@router.get("/agents/{agent_id}/system-info")
async def get_router_system_info(agent_id: str):
    """Ottiene informazioni sistema del router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    if agent.connection_type not in ["api", "both"]:
        raise HTTPException(status_code=400, detail="Sonda non supporta API RouterOS")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_system_info(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.get("/agents/{agent_id}/interfaces")
async def get_router_interfaces(agent_id: str):
    """Ottiene interfacce del router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_interfaces(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.get("/agents/{agent_id}/ip-addresses")
async def get_router_ip_addresses(agent_id: str):
    """Ottiene indirizzi IP configurati"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_ip_addresses(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.get("/agents/{agent_id}/routes")
async def get_router_routes(agent_id: str):
    """Ottiene tabella routing"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_routes(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.get("/agents/{agent_id}/firewall-stats")
async def get_router_firewall_stats(agent_id: str):
    """Ottiene statistiche firewall"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_firewall_stats(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.get("/agents/{agent_id}/dude-agent-status")
async def get_router_dude_agent_status(agent_id: str):
    """Verifica stato Dude Agent sul router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_dude_agent_status(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.post("/agents/{agent_id}/configure-dude-agent")
async def configure_router_dude_agent(
    agent_id: str,
    dude_server: str = Query(..., description="Indirizzo server The Dude"),
    enabled: bool = Query(True, description="Abilita agent"),
):
    """Configura Dude Agent sul router remoto"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.configure_dude_agent(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        dude_server=dude_server,
        enabled=enabled,
        use_ssl=agent.use_ssl,
    )
    
    return result


# ==========================================
# NETWATCH MANAGEMENT
# ==========================================

@router.get("/agents/{agent_id}/netwatch")
async def list_router_netwatch(agent_id: str):
    """Lista netwatch configurati sul router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.get_netwatch_list(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.post("/agents/{agent_id}/netwatch")
async def add_router_netwatch(agent_id: str, netwatch: NetwatchCreate):
    """Aggiunge netwatch sul router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.add_netwatch(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        host=netwatch.host,
        target_port=netwatch.port,
        interval=netwatch.interval,
        timeout=netwatch.timeout,
        up_script=netwatch.up_script,
        down_script=netwatch.down_script,
        comment=netwatch.comment,
        use_ssl=agent.use_ssl,
    )
    
    return result


@router.delete("/agents/{agent_id}/netwatch/{netwatch_id}")
async def remove_router_netwatch(agent_id: str, netwatch_id: str):
    """Rimuove netwatch dal router"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.remove_netwatch(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        netwatch_id=netwatch_id,
        use_ssl=agent.use_ssl,
    )
    
    return result


# ==========================================
# IP SCAN / DISCOVERY
# ==========================================

@router.post("/agents/{agent_id}/ip-scan")
async def run_router_ip_scan(
    agent_id: str,
    network: str = Query(..., description="Rete da scansionare (CIDR)"),
    interface: Optional[str] = Query(None, description="Interfaccia da usare"),
    duration: int = Query(30, description="Durata scansione in secondi"),
):
    """Esegue IP scan dal router remoto"""
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    mikrotik = get_mikrotik_service()
    result = mikrotik.run_ip_scan(
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        network=network,
        interface=interface,
        duration=duration,
        use_ssl=agent.use_ssl,
    )
    
    return result
