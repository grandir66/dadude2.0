"""
DaDude - Inventory Router
API per gestione inventario dispositivi
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from loguru import logger
from datetime import datetime


router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ==========================================
# SCHEMAS
# ==========================================

class DeviceImport(BaseModel):
    """Schema per importare un dispositivo nell'inventario"""
    address: Optional[str] = None
    mac_address: Optional[str] = None
    name: Optional[str] = None
    identity: Optional[str] = None
    hostname: Optional[str] = None  # Hostname risolto via DNS o rilevato
    platform: Optional[str] = None
    board: Optional[str] = None
    device_type: str = "other"  # windows, linux, mikrotik, network, printer, etc
    category: Optional[str] = None  # server, workstation, router, switch, etc
    credential_id: Optional[str] = None  # Credenziale associata per accesso
    open_ports: Optional[List[dict]] = None  # Porte TCP/UDP aperte
    os_family: Optional[str] = None
    os_version: Optional[str] = None
    identified_by: Optional[str] = None
    credential_used: Optional[str] = None


class BulkImport(BaseModel):
    """Schema per importare più dispositivi"""
    devices: List[DeviceImport]


class DeviceProbeRequest(BaseModel):
    """Schema per probe dispositivo"""
    address: str
    mac_address: Optional[str] = None
    credential_ids: Optional[List[str]] = None  # ID credenziali da usare


class BulkProbeRequest(BaseModel):
    """Schema per probe multipli dispositivi"""
    devices: List[DeviceProbeRequest]
    credential_ids: Optional[List[str]] = None  # Credenziali comuni


class EnrichRequest(BaseModel):
    """Schema per arricchire device con vendor info"""
    devices: List[dict]  # Lista di device con almeno mac_address


class AutoDetectRequest(BaseModel):
    """Schema per auto-detect dispositivo con credenziali di default"""
    address: str
    mac_address: Optional[str] = None
    device_id: Optional[str] = None  # ID device inventario (se presente, usa sua credenziale e salva risultati)
    use_default_credentials: bool = True  # Usa credenziali default del cliente
    use_assigned_credential: bool = True  # Usa credenziale assegnata al device (prioritaria)
    use_agent: bool = True  # Usa agent remoto se disponibile
    agent_id: Optional[str] = None  # ID agent specifico (se None, usa default)
    save_results: bool = True  # Salva i risultati nel device


class BulkAutoDetectRequest(BaseModel):
    """Schema per auto-detect multipli dispositivi"""
    devices: List[AutoDetectRequest]
    use_agent: bool = True  # Usa agent remoto per tutti i device


# ==========================================
# MAC VENDOR & DEVICE PROBE
# ==========================================

@router.post("/enrich-devices")
async def enrich_devices_with_vendor(data: EnrichRequest):
    """
    Arricchisce una lista di dispositivi con info vendor dal MAC address.
    Ritorna i device con vendor, suggested_type, suggested_category.
    """
    from ..services.mac_lookup_service import get_mac_lookup_service
    
    mac_service = get_mac_lookup_service()
    
    # Arricchisci ogni dispositivo con lookup MAC
    enriched = []
    found_count = 0
    for device in data.devices:
        mac = device.get("mac_address", "") or device.get("mac", "")
        if mac and mac.strip():
            mac = mac.strip()
            vendor_info = mac_service.lookup(mac)
            if vendor_info:
                device["vendor"] = vendor_info.get("vendor")
                device["suggested_type"] = vendor_info.get("device_type", "other")
                device["suggested_category"] = vendor_info.get("category")
                device["os_family"] = vendor_info.get("os_family")
                found_count += 1
                logger.info(f"Enriched device {device.get('address', 'unknown')} MAC {mac}: {vendor_info.get('vendor')}")
            else:
                # Fallback se non trovato
                device["vendor"] = device.get("vendor")
                device["suggested_type"] = device.get("suggested_type", "other")
                device["suggested_category"] = device.get("suggested_category")
                logger.debug(f"No vendor found for MAC {mac} (device {device.get('address', 'unknown')})")
        else:
            logger.debug(f"Device {device.get('address', 'unknown')} has no MAC address")
        enriched.append(device)
    
    logger.info(f"Enriched {found_count}/{len(data.devices)} devices with vendor info")
    
    return {
        "success": True,
        "devices": enriched,
    }


@router.post("/probe-device")
async def probe_single_device(
    data: DeviceProbeRequest,
    customer_id: str = Query(...),
):
    """
    Esegue probe su un singolo dispositivo per identificarlo.
    Usa le credenziali del cliente specificate.
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    
    # Recupera credenziali
    credentials_list = []
    if data.credential_ids:
        for cred_id in data.credential_ids:
            cred = customer_service.get_credential(cred_id, include_secrets=True)
            if cred:
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
    
    # Esegui probe
    result = await probe_service.auto_identify_device(
        address=data.address,
        mac_address=data.mac_address,
        credentials_list=credentials_list
    )
    
    return {
        "success": True,
        "result": result,
    }


@router.post("/auto-detect")
async def auto_detect_device(
    data: AutoDetectRequest,
    customer_id: str = Query(...),
):
    """
    Esegue auto-detect su un dispositivo:
    1. Cerca agent remoto (Docker o MikroTik) per il cliente
    2. Scansiona le porte aperte (via agent se disponibile)
    3. Determina quali protocolli provare (SSH, SNMP, WMI) in base alle porte
    4. Cerca le credenziali di default del cliente per quei protocolli
    5. Esegue il probe con le credenziali appropriate (via agent Docker se disponibile)
    
    Logica porte → protocolli:
    - SSH (22, 23) → credenziali ssh
    - SNMP (161) → credenziali snmp  
    - RDP/SMB/LDAP/WMI (3389, 445, 139, 389, 135, 5985) → credenziali wmi
    - MikroTik API (8728, 8729, 8291) → credenziali mikrotik
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    from ..services.agent_service import get_agent_service
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    agent_service = get_agent_service()
    
    result = {
        "address": data.address,
        "mac_address": data.mac_address,
        "success": False,
        "scan_result": None,
        "credentials_tested": [],
        "identified": False,
        "agent_used": None,
    }
    
    try:
        # 0. Cerca agent remoto
        agent_info = None
        if data.use_agent:
            if data.agent_id:
                # Agent specifico
                agent = customer_service.get_agent(data.agent_id, include_password=True)
                if agent:
                    agent_info = agent_service._agent_to_dict(agent)
            else:
                # Agent default del cliente
                agent_info = agent_service.get_agent_for_customer(customer_id)
            
            if agent_info:
                result["agent_used"] = {
                    "id": agent_info["id"],
                    "name": agent_info["name"],
                    "type": agent_info["agent_type"],
                }
                logger.info(f"Auto-detect: Using agent {agent_info['name']} ({agent_info['agent_type']})")
        
        # 1. Scansiona le porte
        logger.info(f"Auto-detect: Scanning ports on {data.address}...")
        
        if agent_info and agent_info.get("agent_type") == "docker":
            # Usa agent Docker per port scan
            port_result = await agent_service.scan_ports(agent_info, data.address)
            open_ports = port_result.get("open_ports", [])
        else:
            # Scansione diretta (o via MikroTik per porte limitate)
            open_ports = await probe_service.scan_services(data.address)
        
        result["open_ports"] = open_ports
        open_count = len([p for p in open_ports if p.get("open")])
        logger.info(f"Auto-detect: Found {open_count} open ports on {data.address}")
        
        if not open_ports or open_count == 0:
            result["error"] = "No open ports found"
            return result
        
        # 2. Determina credenziali da provare
        credentials_list = []
        device_record = None
        
        # 2a. Prima controlla se c'è una credenziale assegnata al device specifico
        if data.device_id and data.use_assigned_credential:
            from ..models.inventory import InventoryDevice
            from ..models.database import Credential as CredentialDB
            
            session = customer_service._get_session()
            try:
                device_record = session.query(InventoryDevice).filter(
                    InventoryDevice.id == data.device_id
                ).first()
                
                if device_record and device_record.credential_id:
                    cred = session.query(CredentialDB).filter(
                        CredentialDB.id == device_record.credential_id
                    ).first()
                    
                    if cred:
                        # Decripta la password
                        encryption = customer_service._encryption
                        password = encryption.decrypt(cred.password) if cred.password else None
                        
                        credentials_list.append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "username": cred.username,
                            "password": password,
                            "ssh_port": cred.ssh_port or 22,
                            "ssh_private_key": encryption.decrypt(cred.ssh_private_key) if cred.ssh_private_key else None,
                            "snmp_community": cred.snmp_community,
                            "snmp_version": cred.snmp_version or '2c',
                            "snmp_port": cred.snmp_port or 161,
                            "wmi_domain": cred.wmi_domain,
                            "mikrotik_api_port": cred.mikrotik_api_port or 8728,
                        })
                        result["credentials_tested"].append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "source": "device_assigned",
                        })
                        logger.info(f"Auto-detect: Using device-assigned credential '{cred.name}' ({cred.credential_type})")
            finally:
                session.close()
        
        # 2b. Poi aggiungi credenziali di default se richiesto
        if data.use_default_credentials:
            # Ottieni credenziali di default in base alle porte aperte
            creds = customer_service.get_credentials_for_auto_detect(
                customer_id=customer_id,
                open_ports=open_ports
            )
            
            for cred in creds:
                # Skip se già presente (stessa credenziale assegnata)
                if any(c["id"] == cred.id for c in credentials_list):
                    continue
                    
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
                result["credentials_tested"].append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "source": "default",
                })
        
        logger.info(f"Auto-detect: Testing {len(credentials_list)} credentials on {data.address}")
        
        # 3. Esegui probe con credenziali
        # Se abbiamo un agent Docker, usalo per i probe
        if agent_info and agent_info.get("agent_type") == "docker":
            # Probe via agent Docker
            probe_result = await agent_service.auto_probe(
                agent_info=agent_info,
                target=data.address,
                open_ports=open_ports,
                credentials=credentials_list,
            )
            
            # Converti risultato agent in formato compatibile
            if probe_result.get("best_result"):
                scan_result = {
                    "address": data.address,
                    "mac_address": data.mac_address,
                    "device_type": "unknown",
                    "category": None,
                    "identified_by": f"agent_{probe_result['best_result']['type']}",
                    **probe_result["best_result"].get("data", {}),
                }
            else:
                scan_result = {
                    "address": data.address,
                    "mac_address": data.mac_address,
                    "device_type": "unknown",
                    "identified_by": None,
                    "probes": probe_result.get("probes", []),
                }
        else:
            # Probe diretto (senza agent o con agent MikroTik)
            scan_result = await probe_service.auto_identify_device(
                address=data.address,
                mac_address=data.mac_address,
                credentials_list=credentials_list
            )
        
        result["scan_result"] = scan_result
        result["success"] = True
        result["identified"] = scan_result.get("identified_by") is not None
        
        logger.info(f"Auto-detect complete for {data.address}: identified={result['identified']}, method={scan_result.get('identified_by')}")
        
        # 4. Salva i risultati nel device se richiesto
        if data.save_results and data.device_id and result["identified"]:
            from ..models.inventory import InventoryDevice
            import json
            
            session = customer_service._get_session()
            try:
                device = session.query(InventoryDevice).filter(
                    InventoryDevice.id == data.device_id
                ).first()
                
                if device:
                    # Aggiorna campi dal risultato
                    if scan_result.get("hostname"):
                        device.hostname = scan_result["hostname"]
                    if scan_result.get("os_family"):
                        device.os_family = scan_result["os_family"]
                    if scan_result.get("os_version"):
                        device.os_version = scan_result["os_version"]
                    if scan_result.get("manufacturer") or scan_result.get("vendor"):
                        device.manufacturer = scan_result.get("manufacturer") or scan_result.get("vendor")
                    if scan_result.get("model"):
                        device.model = scan_result["model"]
                    if scan_result.get("serial_number"):
                        device.serial_number = scan_result["serial_number"]
                    if scan_result.get("cpu_model"):
                        device.cpu_model = scan_result["cpu_model"]
                    if scan_result.get("cpu_cores"):
                        device.cpu_cores = int(scan_result["cpu_cores"])
                    if scan_result.get("ram_total_gb"):
                        device.ram_total_gb = float(scan_result["ram_total_gb"])
                    if scan_result.get("disk_total_gb"):
                        device.disk_total_gb = float(scan_result["disk_total_gb"])
                    if scan_result.get("firmware_version"):
                        device.firmware_version = scan_result["firmware_version"]
                    if scan_result.get("category"):
                        device.category = scan_result["category"]
                    
                    # Metodo di identificazione
                    device.identified_by = scan_result.get("identified_by")
                    
                    # Credenziale usata
                    if result["credentials_tested"]:
                        device.credential_used = result["credentials_tested"][0].get("type")
                    
                    # Porte aperte
                    if open_ports:
                        device.open_ports = json.dumps(open_ports) if isinstance(open_ports, list) else open_ports
                    
                    # Timestamp
                    from datetime import datetime
                    device.last_scan = datetime.utcnow()
                    
                    session.commit()
                    logger.info(f"Auto-detect: Saved results to device {data.device_id}")
                    result["saved"] = True
            except Exception as save_err:
                logger.error(f"Failed to save auto-detect results: {save_err}")
                session.rollback()
                result["save_error"] = str(save_err)
            finally:
                session.close()
        
    except Exception as e:
        logger.error(f"Auto-detect failed for {data.address}: {e}")
        result["error"] = str(e)
    
    return result


@router.post("/auto-detect-batch")
async def auto_detect_batch(
    data: BulkAutoDetectRequest,
    customer_id: str = Query(...),
):
    """
    Esegue auto-detect su più dispositivi in parallelo.
    """
    import asyncio
    
    results = []
    
    async def detect_one(device: AutoDetectRequest):
        return await auto_detect_device(device, customer_id)
    
    # Esegui in parallelo (max 5 alla volta per evitare sovraccarico)
    semaphore = asyncio.Semaphore(5)
    
    async def detect_with_semaphore(device):
        async with semaphore:
            return await detect_one(device)
    
    tasks = [detect_with_semaphore(d) for d in data.devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Processa risultati
    processed = []
    success_count = 0
    identified_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append({
                "address": data.devices[i].address,
                "success": False,
                "error": str(result),
            })
        else:
            processed.append(result)
            if result.get("success"):
                success_count += 1
            if result.get("identified"):
                identified_count += 1
    
    return {
        "success": True,
        "total": len(data.devices),
        "scanned": success_count,
        "identified": identified_count,
        "results": processed,
    }


@router.post("/probe-devices")
async def probe_multiple_devices(
    data: BulkProbeRequest,
    customer_id: str = Query(...),
):
    """
    Esegue probe su più dispositivi in parallelo.
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    import asyncio
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    
    # Recupera credenziali comuni
    credentials_list = []
    credential_ids = data.credential_ids or []
    
    if credential_ids:
        for cred_id in credential_ids:
            cred = customer_service.get_credential(cred_id, include_secrets=True)
            if cred:
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
    
    # Probe paralleli
    async def probe_one(device):
        device_creds = credentials_list.copy()
        if device.credential_ids:
            # Aggiungi credenziali specifiche per questo device
            for cred_id in device.credential_ids:
                if cred_id not in credential_ids:
                    cred = customer_service.get_credential(cred_id, include_secrets=True)
                    if cred:
                        device_creds.append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "username": cred.username,
                            "password": cred.password,
                            "ssh_port": getattr(cred, 'ssh_port', 22),
                            "snmp_community": getattr(cred, 'snmp_community', None),
                        })
        
        return await probe_service.auto_identify_device(
            address=device.address,
            mac_address=device.mac_address,
            credentials_list=device_creds
        )
    
    tasks = [probe_one(d) for d in data.devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Formatta risultati
    formatted = []
    for device, result in zip(data.devices, results):
        if isinstance(result, Exception):
            formatted.append({
                "address": device.address,
                "mac_address": device.mac_address,
                "error": str(result),
            })
        else:
            formatted.append(result)
    
    return {
        "success": True,
        "results": formatted,
        "probed": len([r for r in formatted if not r.get("error")]),
        "errors": len([r for r in formatted if r.get("error")]),
    }


@router.get("/detect-protocols/{address}")
async def detect_protocols(address: str):
    """Rileva quali protocolli sono disponibili su un host"""
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    protocols = await probe_service.detect_available_protocols(address)

    return {
        "success": True,
        "address": address,
        "protocols": protocols,
    }


@router.get("/scan-ports/{address}")
async def scan_ports_for_address(address: str):
    """
    Scansiona le porte TCP/UDP di un indirizzo IP.
    Restituisce l'elenco delle porte aperte con relativi servizi.
    """
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    
    try:
        open_ports = await probe_service.scan_services(address)
        
        # Filtra solo porte aperte
        active_ports = [p for p in open_ports if p.get("open")]
        
        return {
            "success": True,
            "address": address,
            "open_ports": open_ports,
            "active_count": len(active_ports),
            "services": [p["service"] for p in active_ports if p.get("service")],
        }
    except Exception as e:
        logger.error(f"Error scanning ports for {address}: {e}")
        return {
            "success": False,
            "address": address,
            "error": str(e),
            "open_ports": [],
        }


@router.get("/suggest-credential-type/{address}")
async def suggest_credential_type(address: str):
    """
    Suggerisce il tipo di credenziali da usare in base alle porte aperte.

    Regole:
    - Se risponde a 389 (LDAP), 445 (SMB), o 3389 (RDP) -> wmi (Windows)
    - Se risponde a 161 (SNMP) -> snmp
    - Se risponde a 22 (SSH) ma non SNMP e non WMI -> ssh (Linux)
    - Se risponde a 8728 (RouterOS API) -> mikrotik
    """
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    suggested_type = await probe_service.suggest_credential_type(address)

    return {
        "success": True,
        "address": address,
        "suggested_type": suggested_type,
    }


@router.get("/reverse-dns/{address}")
async def reverse_dns_lookup(address: str):
    """Esegue reverse DNS lookup per ottenere hostname da IP"""
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    hostname = await probe_service.reverse_dns_lookup(address)

    return {
        "success": True,
        "address": address,
        "hostname": hostname,
    }


# ==========================================
# INVENTORY CRUD
# ==========================================

@router.get("/devices")
async def list_inventory_devices(
    customer_id: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Lista dispositivi inventariati"""
    from ..models.database import init_db, get_session, Credential
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice)
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        if device_type:
            query = query.filter(InventoryDevice.device_type == device_type)
        if status:
            query = query.filter(InventoryDevice.status == status)
        
        total = query.count()
        devices = query.order_by(InventoryDevice.name).offset(offset).limit(limit).all()
        
        # Prepara dict delle credenziali per lookup veloce
        cred_ids = [d.credential_id for d in devices if d.credential_id]
        credentials_map = {}
        if cred_ids:
            creds = session.query(Credential).filter(Credential.id.in_(cred_ids)).all()
            credentials_map = {c.id: {"name": c.name, "type": c.credential_type} for c in creds}
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "devices": [
                {
                    "id": d.id,
                    "customer_id": d.customer_id,
                    "name": d.name,
                    "hostname": d.hostname,
                    "domain": d.domain,
                    "device_type": d.device_type,
                    "category": d.category,
                    "manufacturer": d.manufacturer,
                    "model": d.model,
                    "primary_ip": d.primary_ip,
                    "primary_mac": d.primary_mac,
                    "mac_address": d.mac_address or d.primary_mac,  # Usa mac_address se disponibile, altrimenti primary_mac
                    "status": d.status,
                    "os_family": d.os_family,
                    "os_version": d.os_version,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                    "dude_device_id": d.dude_device_id,
                    "tags": d.tags,
                    "credential_id": d.credential_id,
                    "credential_name": credentials_map.get(d.credential_id, {}).get("name") if d.credential_id else None,
                    "credential_type": credentials_map.get(d.credential_id, {}).get("type") if d.credential_id else None,
                    "open_ports": d.open_ports,  # Porte aperte
                    "identified_by": d.identified_by,  # Metodo identificazione
                    "serial_number": d.serial_number,
                    "cpu_model": d.cpu_model,
                    "cpu_cores": d.cpu_cores,
                    "ram_total_gb": d.ram_total_gb,
                }
                for d in devices
            ]
        }
    finally:
        session.close()


@router.get("/devices/{device_id}")
async def get_inventory_device(device_id: str):
    """Dettagli singolo dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import (
        InventoryDevice, NetworkInterface, DiskInfo, 
        InstalledSoftware, ServiceInfo,
        WindowsDetails, LinuxDetails, MikroTikDetails, NetworkDeviceDetails
    )
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # Base info
        result = {
            "id": device.id,
            "customer_id": device.customer_id,
            "name": device.name,
            "hostname": device.hostname,
            "domain": device.domain,
            "device_type": device.device_type,
            "category": device.category,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "serial_number": device.serial_number,
            "asset_tag": device.asset_tag,
            "primary_ip": device.primary_ip,
            "primary_mac": device.primary_mac,
            "mac_address": device.mac_address or device.primary_mac,
            "site_name": device.site_name,
            "location": device.location,
            "status": device.status,
            "monitor_source": device.monitor_source,
            "dude_device_id": device.dude_device_id,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "last_scan": device.last_scan.isoformat() if device.last_scan else None,
            "os_family": device.os_family,
            "os_version": device.os_version,
            "os_build": device.os_build,
            "architecture": device.architecture,
            "cpu_model": device.cpu_model,
            "cpu_cores": device.cpu_cores,
            "cpu_threads": device.cpu_threads,
            "ram_total_gb": device.ram_total_gb,
            "description": device.description,
            "notes": device.notes,
            "tags": device.tags,
            "custom_fields": device.custom_fields,
            "open_ports": device.open_ports,
            "identified_by": device.identified_by,
            "credential_used": device.credential_used,
            "credential_id": device.credential_id,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None,
        }
        
        # Network interfaces
        result["network_interfaces"] = [
            {
                "name": n.name,
                "mac_address": n.mac_address,
                "ip_addresses": n.ip_addresses,
                "speed_mbps": n.speed_mbps,
                "admin_status": n.admin_status,
            }
            for n in device.network_interfaces
        ]
        
        # Disks
        result["disks"] = [
            {
                "name": d.name,
                "mount_point": d.mount_point,
                "size_gb": d.size_gb,
                "used_gb": d.used_gb,
                "filesystem": d.filesystem,
            }
            for d in device.disks
        ]
        
        # Type-specific details
        if device.device_type == "windows" and device.windows_details:
            wd = device.windows_details
            result["windows_details"] = {
                "edition": wd.edition,
                "domain_role": wd.domain_role,
                "domain_name": wd.domain_name,
                "last_update_check": wd.last_update_check.isoformat() if wd.last_update_check else None,
                "antivirus_name": wd.antivirus_name,
                "antivirus_status": wd.antivirus_status,
            }
        
        if device.device_type == "linux" and device.linux_details:
            ld = device.linux_details
            result["linux_details"] = {
                "distro_name": ld.distro_name,
                "distro_version": ld.distro_version,
                "kernel_version": ld.kernel_version,
                "docker_installed": ld.docker_installed,
                "containers_running": ld.containers_running,
            }
        
        if device.device_type == "mikrotik" and device.mikrotik_details:
            md = device.mikrotik_details
            result["mikrotik_details"] = {
                "routeros_version": md.routeros_version,
                "board_name": md.board_name,
                "license_level": md.license_level,
                "cpu_load": md.cpu_load,
                "memory_free_mb": md.memory_free_mb,
                "uptime": md.uptime,
            }
        
        return result
        
    finally:
        session.close()


@router.post("/devices")
async def create_inventory_device(
    customer_id: str,
    device: DeviceImport,
):
    """Crea nuovo dispositivo inventariato"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Determina nome
        name = device.name or device.identity or device.address or "Unknown"
        
        # Controlla duplicati per IP
        if device.address:
            existing = session.query(InventoryDevice).filter(
                InventoryDevice.customer_id == customer_id,
                InventoryDevice.primary_ip == device.address
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "error": "duplicate",
                    "message": f"Dispositivo con IP {device.address} già presente",
                    "existing_id": existing.id,
                }
        
        # Crea dispositivo
        new_device = InventoryDevice(
            customer_id=customer_id,
            name=name,
            hostname=device.identity,
            device_type=device.device_type,
            category=device.category,
            primary_ip=device.address,
            primary_mac=device.mac_address,
            mac_address=device.mac_address,  # Alias per retrocompatibilità
            manufacturer=device.platform if device.platform else None,
            model=device.board,
            os_family=device.os_family if hasattr(device, 'os_family') else None,
            os_version=device.os_version if hasattr(device, 'os_version') else None,
            identified_by=device.identified_by if hasattr(device, 'identified_by') else None,
            credential_used=device.credential_used if hasattr(device, 'credential_used') else None,
            open_ports=device.open_ports if hasattr(device, 'open_ports') else None,
            status="unknown",
            last_seen=datetime.now(),
        )
        
        session.add(new_device)
        session.commit()
        
        return {
            "success": True,
            "device_id": new_device.id,
            "name": new_device.name,
            "message": f"Dispositivo {name} creato",
        }
        
    finally:
        session.close()


@router.post("/devices/bulk-import")
async def bulk_import_devices(
    customer_id: str,
    data: BulkImport,
    skip_duplicates: bool = Query(True),
):
    """Importa più dispositivi nell'inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Ottieni IP esistenti
        existing_ips = set()
        if skip_duplicates:
            existing = session.query(InventoryDevice.primary_ip).filter(
                InventoryDevice.customer_id == customer_id,
                InventoryDevice.primary_ip.isnot(None)
            ).all()
            existing_ips = {e[0] for e in existing}
        
        imported = 0
        skipped = 0
        skipped_no_mac = 0
        errors = []
        
        for device in data.devices:
            try:
                # Skip se non ha MAC address
                if not device.mac_address or device.mac_address.strip() == '':
                    skipped_no_mac += 1
                    continue
                
                # Skip se IP già presente
                if device.address and device.address in existing_ips:
                    skipped += 1
                    continue
                
                # Determina il nome: priorità a name, poi hostname, poi identity, poi address
                name = device.name or device.hostname or device.identity or device.address or "Unknown"
                
                # Determina hostname: priorità a hostname, poi identity
                hostname = device.hostname or device.identity or None

                new_device = InventoryDevice(
                    customer_id=customer_id,
                    name=name,
                    hostname=hostname,
                    device_type=device.device_type,
                    category=device.category,
                    primary_ip=device.address,
                    primary_mac=device.mac_address,
                    mac_address=device.mac_address,  # Alias per retrocompatibilità
                    manufacturer=device.platform if device.platform else None,
                    model=device.board,
                    os_family=device.os_family if hasattr(device, 'os_family') else None,
                    os_version=device.os_version if hasattr(device, 'os_version') else None,
                    identified_by=device.identified_by if hasattr(device, 'identified_by') else None,
                    credential_used=device.credential_used if hasattr(device, 'credential_used') else None,
                    open_ports=device.open_ports if hasattr(device, 'open_ports') else None,
                    status="unknown",
                    last_seen=datetime.now(),
                )
                
                logger.debug(f"Importing device: {name} ({device.address}) - hostname: {hostname}, ports: {len(device.open_ports or [])}")
                
                session.add(new_device)
                imported += 1
                
                if device.address:
                    existing_ips.add(device.address)
                    
            except Exception as e:
                errors.append(f"{device.address}: {str(e)}")
        
        session.commit()
        
        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "skipped_no_mac": skipped_no_mac,
            "errors": errors,
            "message": f"Importati {imported} dispositivi, {skipped} duplicati, {skipped_no_mac} senza MAC",
        }
        
    finally:
        session.close()


@router.delete("/devices/clear")
async def clear_inventory(customer_id: Optional[str] = Query(None)):
    """Elimina tutti i dispositivi dall'inventario di un cliente"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings

    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        # Costruisci query
        query = session.query(InventoryDevice)

        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        else:
            raise HTTPException(status_code=400, detail="customer_id è richiesto")

        # Conta e elimina
        count = query.count()
        query.delete(synchronize_session=False)
        session.commit()

        logger.info(f"Cleared {count} devices from inventory for customer {customer_id}")

        return {
            "success": True,
            "deleted": count,
            "message": f"Eliminati {count} dispositivi"
        }

    except Exception as e:
        session.rollback()
        logger.error(f"Error clearing inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ==========================================
# PORT SCANNING
# ==========================================

@router.post("/devices/{device_id}/scan-ports")
async def scan_device_ports(device_id: str):
    """
    Riesegue la scansione delle porte per un dispositivo inventariato.
    Aggiorna il campo open_ports nel database.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.device_probe_service import get_device_probe_service
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        if not device.primary_ip:
            raise HTTPException(status_code=400, detail="Dispositivo senza IP")
        
        # Esegui scansione porte
        probe_service = get_device_probe_service()
        open_ports = await probe_service.scan_services(device.primary_ip)
        
        # Aggiorna dispositivo
        device.open_ports = open_ports
        device.last_seen = datetime.now()
        session.commit()
        
        logger.info(f"Port scan completed for device {device_id} ({device.primary_ip}): {len([p for p in open_ports if p.get('open')])} ports open")
        
        return {
            "success": True,
            "device_id": device_id,
            "address": device.primary_ip,
            "open_ports": open_ports,
            "open_count": len([p for p in open_ports if p.get('open')]),
            "message": f"Scansione completata: {len([p for p in open_ports if p.get('open')])} porte aperte"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error scanning ports for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class BatchPortScanRequest(BaseModel):
    """Schema per scansione porte batch"""
    device_ids: List[str]


@router.post("/devices/batch-scan-ports")
async def batch_scan_device_ports(
    customer_id: Optional[str] = Query(None),
    data: Optional[BatchPortScanRequest] = None,
):
    """
    Riesegue la scansione delle porte per più dispositivi inventariati.
    Se customer_id è specificato, scansiona tutti i device del cliente.
    Se data.device_ids è specificato, scansiona solo quei device.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.device_probe_service import get_device_probe_service
    from ..config import get_settings
    import asyncio
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Determina quali device scansionare
        query = session.query(InventoryDevice).filter(
            InventoryDevice.primary_ip.isnot(None)
        )
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        if data and data.device_ids:
            query = query.filter(InventoryDevice.id.in_(data.device_ids))
        
        devices = query.all()
        
        if not devices:
            return {
                "success": True,
                "scanned": 0,
                "errors": [],
                "message": "Nessun dispositivo da scansionare"
            }
        
        # Esegui scansione in parallelo
        probe_service = get_device_probe_service()
        
        async def scan_one_device(device):
            """Scansiona un singolo device"""
            try:
                open_ports = await probe_service.scan_services(device.primary_ip)
                device.open_ports = open_ports
                device.last_seen = datetime.now()
                return {
                    "device_id": device.id,
                    "address": device.primary_ip,
                    "success": True,
                    "open_count": len([p for p in open_ports if p.get('open')]),
                }
            except Exception as e:
                logger.error(f"Error scanning {device.primary_ip}: {e}")
                return {
                    "device_id": device.id,
                    "address": device.primary_ip,
                    "success": False,
                    "error": str(e),
                }
        
        # Esegui scansioni in parallelo (max 10 alla volta)
        tasks = [scan_one_device(d) for d in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processa risultati
        scanned = 0
        errors = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result.get("success"):
                scanned += 1
            else:
                errors.append(f"{result.get('address', 'unknown')}: {result.get('error', 'unknown error')}")
        
        session.commit()
        
        logger.info(f"Batch port scan completed: {scanned}/{len(devices)} devices scanned")
        
        return {
            "success": True,
            "scanned": scanned,
            "total": len(devices),
            "errors": errors,
            "message": f"Scansione completata: {scanned}/{len(devices)} dispositivi"
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error in batch port scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/devices/{device_id}")
async def delete_inventory_device(device_id: str):
    """Elimina dispositivo dall'inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        name = device.name
        session.delete(device)
        session.commit()
        
        return {
            "success": True,
            "message": f"Dispositivo {name} eliminato",
        }
        
    finally:
        session.close()


@router.put("/devices/{device_id}")
async def update_inventory_device(device_id: str, updates: dict):
    """Aggiorna dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # Campi aggiornabili
        allowed_fields = [
            'name', 'hostname', 'device_type', 'category', 'manufacturer',
            'model', 'serial_number', 'asset_tag', 'site_name', 'location',
            'description', 'notes', 'tags', 'status', 'credential_id',
            'os_family', 'os_version', 'domain'
        ]
        
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(device, field, value)
        
        session.commit()
        
        return {
            "success": True,
            "message": f"Dispositivo {device.name} aggiornato",
        }
        
    finally:
        session.close()


@router.post("/devices/{device_id}/monitoring")
async def configure_device_monitoring(device_id: str, config: dict):
    """
    Configura il monitoraggio per un dispositivo.
    
    monitoring_type: none, netwatch, agent
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        monitoring_type = config.get("monitoring_type", "none")
        customer_id = config.get("customer_id", device.customer_id)
        
        # Risultato operazione
        result = {
            "success": True,
            "device_id": device_id,
            "device_ip": device.primary_ip,
            "monitoring_type": monitoring_type,
            "netwatch_configured": False,
            "agent_configured": False,
        }
        
        # Ottieni servizio clienti per sonde
        customer_service = get_customer_service()
        
        # Se disabilito il monitoraggio, rimuovi eventuali configurazioni
        if monitoring_type == "none":
            # Rimuovi Netwatch se configurato
            if device.netwatch_id and device.monitoring_agent_id:
                try:
                    agent = customer_service.get_agent(device.monitoring_agent_id, include_password=True)
                    if agent and agent.agent_type == "mikrotik":
                        mikrotik_service = get_mikrotik_service()
                        mikrotik_service.remove_netwatch(
                            address=agent.address,
                            port=agent.port or 8728,
                            username=agent.username or "admin",
                            password=agent.password or "",
                            netwatch_id=device.netwatch_id,
                            use_ssl=agent.use_ssl or False,
                        )
                        logger.info(f"Rimosso Netwatch {device.netwatch_id} da {agent.name}")
                except Exception as e:
                    logger.warning(f"Errore rimozione Netwatch: {e}")
            
            device.monitored = False
            device.monitoring_type = "none"
            device.monitoring_agent_id = None
            device.netwatch_id = None
            
        elif monitoring_type == "netwatch":
            # Configura Netwatch su MikroTik
            # Cerca una sonda MikroTik per questo cliente
            agents = customer_service.list_agents(customer_id=customer_id, active_only=True)
            mikrotik_agent = None
            for ag in agents:
                if ag.agent_type == "mikrotik":
                    mikrotik_agent = customer_service.get_agent(ag.id, include_password=True)
                    break
            
            if not mikrotik_agent:
                return {
                    "success": False,
                    "error": "Nessuna sonda MikroTik configurata per questo cliente"
                }
            
            mikrotik_service = get_mikrotik_service()
            
            try:
                # Aggiungi o aggiorna Netwatch
                netwatch_result = mikrotik_service.add_netwatch(
                    address=mikrotik_agent.address,
                    port=mikrotik_agent.port or 8728,
                    username=mikrotik_agent.username or "admin",
                    password=mikrotik_agent.password or "",
                    target_ip=device.primary_ip,
                    target_name=device.name or device.hostname or device.primary_ip,
                    interval="30s",
                    use_ssl=mikrotik_agent.use_ssl or False,
                )
                
                if netwatch_result.get("success"):
                    device.monitored = True
                    device.monitoring_type = "netwatch"
                    device.monitoring_agent_id = mikrotik_agent.id
                    device.netwatch_id = netwatch_result.get("netwatch_id")
                    result["netwatch_configured"] = True
                    result["mikrotik_name"] = mikrotik_agent.name
                    logger.info(f"Netwatch configurato per {device.primary_ip} su {mikrotik_agent.name}")
                else:
                    result["success"] = False
                    result["error"] = netwatch_result.get("error", "Errore configurazione Netwatch")
                    
            except Exception as e:
                logger.error(f"Errore configurazione Netwatch: {e}")
                result["success"] = False
                result["error"] = str(e)
                
        elif monitoring_type == "agent":
            # Configura monitoring via Docker agent
            agents = customer_service.list_agents(customer_id=customer_id, active_only=True)
            docker_agent = None
            for ag in agents:
                if ag.agent_type == "docker":
                    docker_agent = customer_service.get_agent(ag.id, include_password=True)
                    break
            
            if not docker_agent:
                # Fallback a MikroTik se non c'è Docker
                for ag in agents:
                    if ag.agent_type == "mikrotik":
                        docker_agent = customer_service.get_agent(ag.id, include_password=True)
                        break
            
            if not docker_agent:
                return {
                    "success": False,
                    "error": "Nessuna sonda configurata per questo cliente"
                }
            
            device.monitored = True
            device.monitoring_type = "agent"
            device.monitoring_agent_id = docker_agent.id
            result["agent_configured"] = True
            result["agent_name"] = docker_agent.name
            logger.info(f"Agent monitoring configurato per {device.primary_ip} via {docker_agent.name}")
        
        session.commit()
        return result
        
    except Exception as e:
        session.rollback()
        logger.error(f"Errore configurazione monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        session.close()


@router.post("/devices/{device_id}/identify")
async def identify_inventory_device(
    device_id: str,
    credential_ids: List[str] = Query(default=[]),
):
    """
    Ri-identifica un dispositivo esistente e aggiorna automaticamente le info.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # Prepara credenziali
        credentials_list = []
        if credential_ids:
            customer_service = get_customer_service()
            for cred_id in credential_ids:
                cred = customer_service.get_credential(cred_id, include_secrets=True)
                if cred:
                    credentials_list.append({
                        "id": cred.id,
                        "name": cred.name,
                        "type": cred.credential_type,
                        "username": cred.username,
                        "password": cred.password,
                        "ssh_port": getattr(cred, 'ssh_port', 22),
                        "snmp_community": getattr(cred, 'snmp_community', None),
                        "snmp_version": getattr(cred, 'snmp_version', '2c'),
                        "snmp_port": getattr(cred, 'snmp_port', 161),
                        "wmi_domain": getattr(cred, 'wmi_domain', None),
                        "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                    })
        
        # Esegui probe
        probe_service = get_device_probe_service()
        result = await probe_service.auto_identify_device(
            address=device.primary_ip,
            mac_address=device.primary_mac,
            credentials_list=credentials_list
        )
        
        # Aggiorna dispositivo con info identificate
        updates_applied = []
        
        if result.get("hostname") and not device.hostname:
            device.hostname = result["hostname"]
            updates_applied.append("hostname")
        
        if result.get("device_type") and result["device_type"] != "other":
            device.device_type = result["device_type"]
            updates_applied.append("device_type")
        
        if result.get("category"):
            device.category = result["category"]
            updates_applied.append("category")
        
        if result.get("os_family"):
            device.os_family = result["os_family"]
            updates_applied.append("os_family")
        
        if result.get("model"):
            device.model = result["model"]
            updates_applied.append("model")
        
        if result.get("vendor"):
            device.manufacturer = result["vendor"]
            updates_applied.append("manufacturer")
        
        # Hardware Info
        if result.get("cpu_model"):
            device.cpu_model = result["cpu_model"]
            updates_applied.append("cpu_model")
            
        if result.get("cpu_cores"):
            device.cpu_cores = result["cpu_cores"]
            updates_applied.append("cpu_cores")
            
        if result.get("memory_total_mb"):
            device.ram_total_gb = round(result["memory_total_mb"] / 1024, 2)
            updates_applied.append("ram_total_gb")
            
        if result.get("serial_number"):
            device.serial_number = result["serial_number"]
            updates_applied.append("serial_number")
            
        # OS Version - può venire da "version" (WMI) o altri campi
        if result.get("version") and not device.os_version:
            device.os_version = result["version"]
            updates_applied.append("os_version")
        elif result.get("os_version") and not device.os_version:
            device.os_version = result["os_version"]
            updates_applied.append("os_version")

        # Disk info
        if result.get("disk_total_gb"):
            # Salva in custom_fields o in un campo specifico se disponibile
            if not device.custom_fields:
                device.custom_fields = {}
            device.custom_fields["disk_total_gb"] = result["disk_total_gb"]
            device.custom_fields["disk_free_gb"] = result.get("disk_free_gb")
            updates_applied.append("disk_info")
            
        # Manufacturer - può venire da "manufacturer" (WMI) o "vendor" (MAC)
        if result.get("manufacturer") and not device.manufacturer:
            device.manufacturer = result["manufacturer"]
            updates_applied.append("manufacturer")
            
        # Domain - può venire direttamente da WMI
        if result.get("domain") and not device.domain:
            device.domain = result["domain"]
            updates_applied.append("domain")
            
        # Architecture
        if result.get("architecture"):
            device.architecture = result["architecture"]
            updates_applied.append("architecture")

        # Salva porte aperte rilevate
        if result.get("open_ports"):
            device.open_ports = result["open_ports"]
            updates_applied.append("open_ports")

        # Estrai dominio da hostname se non già impostato
        if not device.domain and result.get("hostname") and "." in result["hostname"]:
            parts = result["hostname"].split(".", 1)
            if len(parts) > 1:
                device.domain = parts[1]
                updates_applied.append("domain_from_hostname")
        
        # Nome OS completo (da WMI: "Windows 10 Pro", etc.)
        if result.get("name") and "Windows" in result.get("name", ""):
            # Salva il nome OS completo in description o custom_fields
            if not device.description:
                device.description = result["name"]
                updates_applied.append("os_description")
                
        # Aggiorna identificato_by e credential_used
        if result.get("identified_by"):
            device.identified_by = result["identified_by"]
            updates_applied.append("identified_by")
            
        if result.get("credential_used"):
            device.credential_used = result["credential_used"]
            updates_applied.append("credential_used")
        
        # Aggiorna last_seen
        device.last_seen = datetime.now()
        device.last_scan = datetime.now()
        
        logger.info(f"Device {device_id} identification complete. Updates: {updates_applied}")
        
        session.commit()
        
        return {
            "success": True,
            "device_id": device_id,
            "probe_result": result,
            "updates_applied": updates_applied,
            "message": f"Dispositivo aggiornato: {', '.join(updates_applied)}" if updates_applied else "Nessun aggiornamento necessario"
        }
        
    finally:
        session.close()


# ==========================================
# STATISTICS
# ==========================================

@router.get("/stats")
async def get_inventory_stats(customer_id: Optional[str] = None):
    """Statistiche inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import func
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice)
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        total = query.count()
        
        # Per tipo
        by_type = session.query(
            InventoryDevice.device_type,
            func.count(InventoryDevice.id)
        )
        if customer_id:
            by_type = by_type.filter(InventoryDevice.customer_id == customer_id)
        by_type = dict(by_type.group_by(InventoryDevice.device_type).all())
        
        # Per stato
        by_status = session.query(
            InventoryDevice.status,
            func.count(InventoryDevice.id)
        )
        if customer_id:
            by_status = by_status.filter(InventoryDevice.customer_id == customer_id)
        by_status = dict(by_status.group_by(InventoryDevice.status).all())
        
        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
        }
        
    finally:
        session.close()


# ==========================================
# SYNC WITH THE DUDE
# ==========================================

@router.post("/devices/{device_id}/add-to-dude")
async def add_device_to_dude(device_id: str):
    """Aggiunge dispositivo a The Dude per monitoraggio"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.dude_service import get_dude_service
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        if not device.primary_ip:
            raise HTTPException(status_code=400, detail="Dispositivo senza IP")
        
        if device.dude_device_id:
            return {
                "success": True,
                "already_exists": True,
                "dude_device_id": device.dude_device_id,
                "message": "Dispositivo già in The Dude",
            }
        
        # Aggiungi a The Dude
        dude = get_dude_service()
        
        # Determina tipo dispositivo per Dude
        dude_type = "Generic Device"
        if device.device_type == "mikrotik":
            dude_type = "RouterOS"
        elif device.device_type == "windows":
            dude_type = "Windows"
        elif device.device_type == "linux":
            dude_type = "Linux"
        elif device.device_type in ["network", "switch"]:
            dude_type = "SNMP Device"
        
        result = dude.add_device(
            name=device.name,
            address=device.primary_ip,
            device_type=dude_type,
        )
        
        if result:
            # Aggiorna riferimento
            device.dude_device_id = result
            device.monitor_source = "dude"
            session.commit()
            
            return {
                "success": True,
                "dude_device_id": result,
                "message": f"Dispositivo {device.name} aggiunto a The Dude",
            }
        else:
            return {
                "success": False,
                "message": "Errore aggiunta a The Dude",
            }
        
    finally:
        session.close()
