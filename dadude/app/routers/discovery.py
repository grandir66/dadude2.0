"""
DaDude - Discovery Router
API endpoints per network discovery via The Dude
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel, Field
from loguru import logger

from ..services import get_dude_service

router = APIRouter(prefix="/discovery", tags=["Discovery"])


# ============================================
# Schemas
# ============================================

class AgentResponse(BaseModel):
    """Schema risposta agente"""
    id: str
    name: str
    address: str
    status: str
    version: str
    enabled: bool


class DiscoveryRequest(BaseModel):
    """Schema richiesta discovery"""
    network: str = Field(..., description="Rete CIDR, es: 192.168.1.0/24")
    agent_id: Optional[str] = Field(None, description="ID agente (None = locale)")
    scan_type: str = Field("ping", description="Tipo scan: ping, arp, snmp, all")
    add_devices: bool = Field(False, description="Aggiungi dispositivi automaticamente")


class DiscoveryResponse(BaseModel):
    """Schema risposta discovery"""
    id: str
    address_range: str
    status: str
    found: str
    added: str
    progress: str
    agent: str
    type: str


class DiscoveryResultResponse(BaseModel):
    """Schema risultato discovery"""
    id: str
    name: str
    address: str
    mac_address: str
    type: str
    status: str


class AddDeviceRequest(BaseModel):
    """Schema richiesta aggiunta dispositivo"""
    name: str
    address: str
    device_type: str = "generic"
    agent_id: Optional[str] = None
    note: Optional[str] = None
    group: Optional[str] = None


# ============================================
# Agents (Sonde)
# ============================================

@router.get("/agents", response_model=List[AgentResponse])
async def list_agents():
    """
    Lista tutti gli agenti/sonde configurati in The Dude.
    """
    try:
        dude = get_dude_service()
        agents = dude.get_agents()
        return agents
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """
    Ottiene dettagli di un agente specifico.
    """
    try:
        dude = get_dude_service()
        agent = dude.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agente non trovato")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Discovery
# ============================================

@router.post("/start")
async def start_discovery(request: DiscoveryRequest):
    """
    Avvia una network discovery.
    
    Parametri:
    - network: Rete da scansionare in notazione CIDR
    - agent_id: ID dell'agente da usare (opzionale, default: server locale)
    - scan_type: Tipo di scansione (ping, arp, snmp, all)
    - add_devices: Se aggiungere automaticamente i dispositivi trovati
    """
    try:
        dude = get_dude_service()
        result = dude.start_discovery(
            network=request.network,
            agent_id=request.agent_id,
            scan_type=request.scan_type,
            add_devices=request.add_devices,
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Errore sconosciuto"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[DiscoveryResponse])
async def list_discoveries():
    """
    Lista tutte le discovery attive e completate.
    """
    try:
        dude = get_dude_service()
        return dude.get_discoveries()
    except Exception as e:
        logger.error(f"Error listing discoveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{discovery_id}/results", response_model=List[DiscoveryResultResponse])
async def get_discovery_results(discovery_id: str):
    """
    Ottiene i risultati di una discovery specifica.
    """
    try:
        dude = get_dude_service()
        return dude.get_discovery_results(discovery_id)
    except Exception as e:
        logger.error(f"Error getting discovery results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{discovery_id}")
async def stop_discovery(discovery_id: str):
    """
    Ferma una discovery in corso.
    """
    try:
        dude = get_dude_service()
        success = dude.stop_discovery(discovery_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Errore stop discovery")
        
        return {"status": "stopped", "discovery_id": discovery_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Device Management
# ============================================

@router.get("/scans")
async def list_scans(
    customer_id: Optional[str] = None,
    limit: int = 50
):
    """
    Lista tutte le scansioni dal database locale.
    """
    from ..models.database import ScanResult, init_db, get_session
    from ..config import get_settings

    settings = get_settings()
    db_url = settings.database_url_sync_computed
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        query = session.query(ScanResult)
        if customer_id:
            query = query.filter(ScanResult.customer_id == customer_id)
        query = query.order_by(ScanResult.created_at.desc()).limit(limit)

        scans = []
        for s in query.all():
            scans.append({
                "id": s.id,
                "customer_id": s.customer_id,
                "agent_id": s.agent_id,
                "network": s.network_cidr,
                "network_cidr": s.network_cidr,
                "scan_type": s.scan_type,
                "status": s.status,
                "devices_found": s.devices_found or 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
        return {"scans": scans, "total": len(scans)}
    finally:
        session.close()


@router.get("/scans/{scan_id}/devices")
async def get_scan_devices(scan_id: str):
    """
    Lista dispositivi trovati in una scansione.
    """
    from ..models.database import DiscoveredDevice, init_db, get_session
    from ..config import get_settings

    settings = get_settings()
    db_url = settings.database_url_sync_computed
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        devices = session.query(DiscoveredDevice).filter(
            DiscoveredDevice.scan_id == scan_id
        ).all()

        result = []
        for d in devices:
            result.append({
                "id": d.id,
                "scan_id": d.scan_id,
                "address": d.address,
                "mac_address": d.mac_address,
                "hostname": d.hostname,
                "platform": d.platform,
                "source": d.source,
                "imported": d.imported,
                "customer_id": d.customer_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            })
        return {"devices": result, "total": len(result)}
    finally:
        session.close()


@router.post("/scan")
async def start_scan(data: dict):
    """
    Avvia una scansione di rete (endpoint per frontend Vue).
    Esegue la scansione tramite l'agent MikroTik selezionato.
    """
    from ..services.customer_service import get_customer_service
    from ..services.scanner_service import get_scanner_service
    from ..models.database import ScanResult, DiscoveredDevice, init_db, get_session
    from ..config import get_settings
    import uuid
    from datetime import datetime

    customer_id = data.get("customer_id")
    agent_id = data.get("agent_id")
    network_cidr = data.get("network_cidr")
    scan_type = data.get("scan_type", "ping")

    if not customer_id or not agent_id:
        raise HTTPException(status_code=400, detail="customer_id and agent_id required")

    # Get agent details
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trovato")

    settings = get_settings()
    db_url = settings.database_url_sync_computed
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        # Create scan record
        scan_id = str(uuid.uuid4())[:8]
        scan = ScanResult(
            id=scan_id,
            customer_id=customer_id,
            agent_id=agent_id,
            network_cidr=network_cidr,
            scan_type=scan_type,
            status="running",
        )
        session.add(scan)
        session.commit()

        # Execute scan via MikroTik router
        scanner = get_scanner_service()
        try:
            scan_results = scanner.scan_network_via_router(
                router_address=agent.address,
                router_port=agent.port or 8728,
                router_username=agent.username or 'admin',
                router_password=agent.password or '',
                network=network_cidr,
                scan_type=scan_type,
                use_ssl=getattr(agent, 'use_ssl', False),
            )

            # Save discovered devices
            devices_found = 0
            devices_list = scan_results.get("devices") or scan_results.get("results") or []
            if scan_results.get("success") and devices_list:
                for dev in devices_list:
                    # Get hostname from identity or hostname field
                    hostname = dev.get("hostname") or dev.get("identity") or ""
                    device = DiscoveredDevice(
                        id=str(uuid.uuid4())[:8],
                        scan_id=scan_id,
                        customer_id=customer_id,
                        address=dev.get("address", ""),
                        mac_address=dev.get("mac_address", ""),
                        hostname=hostname,
                        platform=dev.get("platform") or "unknown",
                        source=dev.get("source", "scan"),
                    )
                    session.add(device)
                    devices_found += 1

            # Update scan record
            scan.status = "completed" if scan_results.get("success") else "failed"
            scan.devices_found = devices_found
            session.commit()

            return {
                "success": True,
                "scan_id": scan_id,
                "message": f"Scan completed: {devices_found} devices found",
                "devices_found": devices_found,
            }

        except Exception as scan_error:
            # Update scan record with error
            scan.status = "failed"
            scan.completed_at = datetime.utcnow()
            session.commit()
            logger.error(f"Scan execution error: {scan_error}")
            return {
                "success": False,
                "scan_id": scan_id,
                "message": f"Scan failed: {str(scan_error)}",
            }

    except Exception as e:
        logger.error(f"Start scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/devices/{device_id}/import")
async def import_device(device_id: str, data: dict):
    """
    Importa un dispositivo scoperto nell'inventario.
    """
    from ..models.database import DiscoveredDevice, init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    import uuid
    from datetime import datetime

    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id required")

    settings = get_settings()
    db_url = settings.database_url_sync_computed
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        # Find discovered device
        discovered = session.query(DiscoveredDevice).filter(
            DiscoveredDevice.id == device_id
        ).first()

        if not discovered:
            raise HTTPException(status_code=404, detail="Device not found")

        # Create inventory device
        inventory_device = InventoryDevice(
            id=str(uuid.uuid4())[:8],
            customer_id=customer_id,
            address=discovered.address,
            hostname=discovered.hostname,
            mac_address=discovered.mac_address,
            platform=discovered.platform,
            source="discovery",
            discovered_at=datetime.utcnow(),
        )
        session.add(inventory_device)

        # Mark as imported
        discovered.imported = True
        discovered.customer_id = customer_id
        session.commit()

        return {
            "success": True,
            "device_id": inventory_device.id,
            "message": f"Device {discovered.address} imported"
        }
    finally:
        session.close()


@router.post("/devices/add")
async def add_device(request: AddDeviceRequest):
    """
    Aggiunge manualmente un dispositivo a The Dude.
    """
    try:
        dude = get_dude_service()
        
        extra_params = {}
        if request.note:
            extra_params["note"] = request.note
        if request.group:
            extra_params["group"] = request.group
        
        device_id = dude.add_device(
            name=request.name,
            address=request.address,
            device_type=request.device_type,
            agent_id=request.agent_id,
            **extra_params
        )
        
        if not device_id:
            raise HTTPException(status_code=500, detail="Errore aggiunta dispositivo")
        
        return {
            "status": "created",
            "device_id": device_id,
            "name": request.name,
            "address": request.address,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding device: {e}")
        raise HTTPException(status_code=500, detail=str(e))
