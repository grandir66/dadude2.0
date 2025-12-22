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
    - Per scan_type="nmap": usa l'agent remoto via HTTP (richiede dadude-agent con nmap)
    - Per altri tipi: usa il router MikroTik via RouterOS API
    Restituisce i dispositivi trovati direttamente senza salvarli nel database.
    Se scan_ports=True, esegue anche una scansione delle porte TCP comuni.
    """
    from ..services.customer_service import get_customer_service
    from ..services.scanner_service import get_scanner_service
    from ..services.mac_vendor_service import get_mac_vendor_service
    from ..services.device_probe_service import get_probe_service
    from ..services.agent_client import AgentClient, AgentConfig
    import uuid
    import asyncio

    customer_id = data.get("customer_id")
    agent_id = data.get("agent_id")
    network_cidr = data.get("network_cidr")
    scan_type = data.get("scan_type", "ping")
    scan_ports = data.get("scan_ports", False)

    if not customer_id or not agent_id:
        raise HTTPException(status_code=400, detail="customer_id and agent_id required")

    # Get agent details
    customer_service = get_customer_service()
    agent = customer_service.get_agent(agent_id, include_password=True)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trovato")

    logger.info(f"[DISCOVERY] Starting scan: agent={agent.name}, address={agent.address}, network={network_cidr}, type={scan_type}, scan_ports={scan_ports}")

    # Se scan_type è "nmap", usa l'agent remoto via HTTP
    if scan_type == "nmap":
        # Costruisci URL dell'agent
        agent_url = getattr(agent, 'agent_url', None)
        if not agent_url:
            agent_api_port = getattr(agent, 'agent_api_port', 8080)
            agent_url = f"http://{agent.address}:{agent_api_port}"

        agent_token = getattr(agent, 'agent_token', '') or ''

        # Decripta token se necessario
        if agent_token and agent_token.startswith('gAAAAA'):
            try:
                from ..services.encryption import get_encryption_service
                encryption = get_encryption_service()
                agent_token = encryption.decrypt(agent_token)
            except Exception as e:
                logger.warning(f"[DISCOVERY] Could not decrypt agent token: {e}")
                agent_token = ""

        logger.info(f"[DISCOVERY] Using Nmap via agent HTTP: {agent_url}")

        config = AgentConfig(
            agent_id=agent_id,
            agent_url=agent_url,
            agent_token=agent_token,
            timeout=300,  # 5 minuti per scan Nmap
        )

        agent_client = AgentClient(config)
        try:
            scan_results = await agent_client.scan_network(
                network=network_cidr,
                scan_type="nmap",
                timeout=120,
            )
            logger.info(f"[DISCOVERY] Nmap scan results: success={scan_results.get('success')}, devices={len(scan_results.get('results', []))}")
        finally:
            await agent_client.close()
    else:
        # Per altri tipi di scan, usa MikroTik RouterOS API
        scanner = get_scanner_service()
        logger.info(f"[DISCOVERY] Using MikroTik RouterOS: {agent.address}:{agent.port}")
        logger.info(f"[DISCOVERY] Agent credentials: username={agent.username}, password={'SET' if agent.password else 'EMPTY'}")

        scan_results = scanner.scan_network_via_router(
            router_address=agent.address,
            router_port=agent.port or 8728,
            router_username=agent.username or 'admin',
            router_password=agent.password or '',
            network=network_cidr,
            scan_type=scan_type,
            use_ssl=getattr(agent, 'use_ssl', False),
        )
        logger.info(f"[DISCOVERY] Scan results: success={scan_results.get('success')}, devices={len(scan_results.get('devices', []))}")

    # Prepara i dispositivi per la risposta (senza salvarli nel DB)
    try:
        devices_list = scan_results.get("devices") or scan_results.get("results") or []
        devices = []
        mac_vendor_service = get_mac_vendor_service()

        for dev in devices_list:
            hostname = dev.get("hostname") or dev.get("identity") or ""
            mac_address = dev.get("mac_address", "")

            # Lookup vendor from MAC address (solo se non già presente da nmap)
            existing_vendor = dev.get("vendor", "")
            if existing_vendor:
                vendor_info = {"vendor": existing_vendor, "category": "", "device_type": "other"}
            else:
                vendor_info = mac_vendor_service.lookup_vendor_with_type(mac_address)

            devices.append({
                "id": str(uuid.uuid4())[:8],  # ID temporaneo
                "address": dev.get("address", ""),
                "mac_address": mac_address,
                "hostname": hostname,
                "platform": dev.get("platform") or vendor_info.get("category") or "unknown",
                "source": dev.get("source", scan_type),
                "vendor": vendor_info.get("vendor") or "",
                "device_type": vendor_info.get("device_type") or "other",
                "open_ports": dev.get("open_ports", []),  # Nmap può già restituire open_ports
            })

        # Se richiesto, esegui port scanning sui dispositivi trovati
        if scan_ports and devices:
            logger.info(f"[DISCOVERY] Starting port scan for {len(devices)} devices")
            probe_service = get_probe_service()

            async def scan_device_ports(device):
                """Scansiona le porte di un singolo dispositivo"""
                try:
                    address = device.get("address")
                    if not address:
                        return device

                    open_ports = await probe_service.scan_services(address)
                    # Filtra solo le porte aperte
                    device["open_ports"] = [p for p in open_ports if p.get("open")]
                    logger.debug(f"[DISCOVERY] Port scan for {address}: {len(device['open_ports'])} open ports")
                except Exception as e:
                    logger.warning(f"[DISCOVERY] Port scan failed for {device.get('address')}: {e}")
                return device

            # Esegui port scan in parallelo (max 10 alla volta per non sovraccaricare)
            batch_size = 10
            for i in range(0, len(devices), batch_size):
                batch = devices[i:i + batch_size]
                await asyncio.gather(*[scan_device_ports(dev) for dev in batch])

            total_ports = sum(len(d.get("open_ports", [])) for d in devices)
            logger.info(f"[DISCOVERY] Port scan completed: {total_ports} total open ports found")

        return {
            "success": True,
            "message": f"Scan completed: {len(devices)} devices found" + (f", {sum(len(d.get('open_ports', [])) for d in devices)} open ports" if scan_ports else ""),
            "devices_found": len(devices),
            "devices": devices,  # Restituisce i dispositivi direttamente
        }

    except Exception as scan_error:
        logger.error(f"Scan execution error: {scan_error}")
        return {
            "success": False,
            "message": f"Scan failed: {str(scan_error)}",
            "devices_found": 0,
            "devices": [],
        }


@router.post("/devices/{device_id}/import")
async def import_device(device_id: str, data: dict):
    """
    Importa un dispositivo scoperto nell'inventario.
    Accetta i dati del dispositivo direttamente (per scansioni transienti).
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    import uuid
    from datetime import datetime

    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id required")

    # Device data can come directly from the request (transient scans)
    device_data = data.get("device", {})
    address = device_data.get("address") or data.get("address")
    if not address:
        raise HTTPException(status_code=400, detail="Device address is required")

    settings = get_settings()
    db_url = settings.database_url_sync_computed
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        # Check if device already exists in inventory
        existing = session.query(InventoryDevice).filter(
            InventoryDevice.primary_ip == address,
            InventoryDevice.customer_id == customer_id
        ).first()

        if existing:
            return {
                "success": False,
                "device_id": existing.id,
                "message": f"Device {address} already exists in inventory"
            }

        # Create inventory device from request data
        hostname = device_data.get("hostname") or data.get("hostname") or ""
        mac_address = device_data.get("mac_address") or data.get("mac_address") or ""
        vendor = device_data.get("vendor") or data.get("vendor") or ""
        device_type = device_data.get("device_type") or data.get("device_type") or "other"
        platform = device_data.get("platform") or data.get("platform") or ""

        inventory_device = InventoryDevice(
            id=str(uuid.uuid4())[:8],
            customer_id=customer_id,
            name=hostname or address,  # name is required
            hostname=hostname,
            primary_ip=address,
            mac_address=mac_address,
            primary_mac=mac_address,
            manufacturer=vendor,
            device_type=device_type,
            category=platform or None,
            status="unknown",
            identified_by="discovery_scan",
        )
        session.add(inventory_device)
        session.commit()

        logger.info(f"[IMPORT] Device imported: {address} -> customer {customer_id}")

        return {
            "success": True,
            "device_id": inventory_device.id,
            "message": f"Device {address} imported successfully"
        }
    except Exception as e:
        session.rollback()
        logger.error(f"[IMPORT] Error importing device: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
