"""
DaDude - Customers Router
API endpoints per gestione clienti/tenant
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from loguru import logger

from ..models.customer_schemas import (
    Customer, CustomerCreate, CustomerUpdate, CustomerListResponse,
    Network, NetworkCreate, NetworkUpdate, NetworkListResponse,
    CredentialSafe, CredentialCreate, CredentialUpdate, CredentialListResponse,
    DeviceAssignment, DeviceAssignmentCreate, DeviceAssignmentUpdate,
    DeviceAssignmentListResponse,
    AgentAssignment, AgentAssignmentCreate, AgentAssignmentUpdate, AgentAssignmentSafe,
)
from ..services.customer_service import get_customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


# ==========================================
# CUSTOMERS ENDPOINTS
# ==========================================

@router.get("", response_model=CustomerListResponse)
async def list_customers(
    active_only: bool = Query(True, description="Solo clienti attivi"),
    search: Optional[str] = Query(None, description="Cerca per codice o nome"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Lista tutti i clienti.
    
    - **active_only**: Filtra solo clienti attivi
    - **search**: Cerca per codice o nome (case-insensitive)
    """
    try:
        service = get_customer_service()
        customers = service.list_customers(
            active_only=active_only,
            search=search,
            limit=limit,
            offset=offset,
        )
        return CustomerListResponse(total=len(customers), customers=customers)
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Customer, status_code=201)
async def create_customer(data: CustomerCreate):
    """
    Crea un nuovo cliente.
    
    Il codice cliente deve essere univoco e verrà convertito in maiuscolo.
    """
    try:
        service = get_customer_service()
        return service.create_customer(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str):
    """
    Ottiene dettagli di un cliente specifico.
    """
    service = get_customer_service()
    customer = service.get_customer(customer_id)
    
    if not customer:
        raise HTTPException(status_code=404, detail=f"Cliente {customer_id} non trovato")
    
    return customer


@router.get("/code/{code}", response_model=Customer)
async def get_customer_by_code(code: str):
    """
    Ottiene cliente per codice.
    """
    service = get_customer_service()
    customer = service.get_customer_by_code(code)
    
    if not customer:
        raise HTTPException(status_code=404, detail=f"Cliente con codice {code} non trovato")
    
    return customer


@router.put("/{customer_id}", response_model=Customer)
async def update_customer(customer_id: str, data: CustomerUpdate):
    """
    Aggiorna dati di un cliente.
    """
    try:
        service = get_customer_service()
        customer = service.update_customer(customer_id, data)
        
        if not customer:
            raise HTTPException(status_code=404, detail=f"Cliente {customer_id} non trovato")
        
        return customer
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str):
    """
    Disattiva un cliente (soft delete).
    """
    service = get_customer_service()
    
    if not service.delete_customer(customer_id):
        raise HTTPException(status_code=404, detail=f"Cliente {customer_id} non trovato")
    
    return {"status": "success", "message": f"Cliente {customer_id} disattivato"}


# ==========================================
# NETWORKS ENDPOINTS
# ==========================================

@router.get("/{customer_id}/networks", response_model=NetworkListResponse)
async def list_customer_networks(
    customer_id: str,
    network_type: Optional[str] = Query(None, description="Filtra per tipo"),
    vlan_id: Optional[int] = Query(None, description="Filtra per VLAN ID"),
):
    """
    Lista reti di un cliente.
    """
    service = get_customer_service()
    networks = service.list_networks(
        customer_id=customer_id,
        network_type=network_type,
        vlan_id=vlan_id,
    )
    return NetworkListResponse(total=len(networks), networks=networks)


@router.post("/{customer_id}/networks", response_model=Network, status_code=201)
async def create_network(customer_id: str, data: NetworkCreate):
    """
    Crea una nuova rete per il cliente.
    
    Le reti possono sovrapporsi tra clienti diversi.
    """
    # Override customer_id dal path
    data.customer_id = customer_id
    
    try:
        service = get_customer_service()
        return service.create_network(data)
    except Exception as e:
        logger.error(f"Error creating network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/networks/{network_id}", response_model=Network)
async def update_network(network_id: str, data: NetworkUpdate):
    """
    Aggiorna una rete.
    """
    service = get_customer_service()
    network = service.update_network(network_id, data)
    
    if not network:
        raise HTTPException(status_code=404, detail=f"Rete {network_id} non trovata")
    
    return network


@router.delete("/networks/{network_id}")
async def delete_network(network_id: str):
    """
    Elimina una rete.
    """
    service = get_customer_service()
    
    if not service.delete_network(network_id):
        raise HTTPException(status_code=404, detail=f"Rete {network_id} non trovata")
    
    return {"status": "success", "message": "Rete eliminata"}


# ==========================================
# CREDENTIALS ENDPOINTS
# ==========================================

@router.get("/{customer_id}/credentials", response_model=CredentialListResponse)
async def list_customer_credentials(
    customer_id: str,
    credential_type: Optional[str] = Query(None, description="Filtra per tipo"),
):
    """
    Lista credenziali di un cliente (senza dati sensibili).
    """
    service = get_customer_service()
    credentials = service.list_credentials(
        customer_id=customer_id,
        credential_type=credential_type,
    )
    return CredentialListResponse(total=len(credentials), credentials=credentials)


@router.post("/{customer_id}/credentials", response_model=CredentialSafe, status_code=201)
async def create_credential(customer_id: str, data: CredentialCreate):
    """
    Crea nuove credenziali per il cliente.
    
    - **is_default**: Se True, sarà usata come fallback per device senza credenziali specifiche
    - **device_filter**: Pattern glob per matching device (es: "router-*", "*-fw")
    """
    data.customer_id = customer_id
    
    try:
        service = get_customer_service()
        return service.create_credential(data)
    except Exception as e:
        logger.error(f"Error creating credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/credentials/{credential_id}")
async def get_credential(credential_id: str, include_secrets: bool = False):
    """
    Ottiene credenziali (include_secrets richiede autenticazione).
    """
    service = get_customer_service()
    credential = service.get_credential(credential_id, include_secrets=include_secrets)
    
    if not credential:
        raise HTTPException(status_code=404, detail=f"Credenziali {credential_id} non trovate")
    
    return credential


@router.put("/credentials/{credential_id}", response_model=CredentialSafe)
async def update_credential(credential_id: str, data: CredentialUpdate):
    """
    Aggiorna credenziali esistenti.
    """
    service = get_customer_service()
    
    # Verifica esistenza
    existing = service.get_credential(credential_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Credenziali {credential_id} non trovate")
    
    updated = service.update_credential(credential_id, data)
    if not updated:
        raise HTTPException(status_code=500, detail="Errore aggiornamento credenziali")
    
    return updated


@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str):
    """
    Elimina credenziali.
    """
    service = get_customer_service()
    
    # Verifica esistenza
    existing = service.get_credential(credential_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Credenziali {credential_id} non trovate")
    
    success = service.delete_credential(credential_id)
    if not success:
        raise HTTPException(status_code=500, detail="Errore eliminazione credenziali")
    
    return {"success": True, "message": f"Credenziali {credential_id} eliminate"}


# ==========================================
# DEVICE ASSIGNMENTS ENDPOINTS
# ==========================================

@router.get("/{customer_id}/devices", response_model=DeviceAssignmentListResponse)
async def list_customer_devices(
    customer_id: str,
    role: Optional[str] = Query(None, description="Filtra per ruolo"),
):
    """
    Lista device assegnati a un cliente.
    """
    service = get_customer_service()
    assignments = service.list_device_assignments(
        customer_id=customer_id,
        role=role,
    )
    return DeviceAssignmentListResponse(total=len(assignments), assignments=assignments)


@router.post("/{customer_id}/devices", response_model=DeviceAssignment, status_code=201)
async def assign_device_to_customer(customer_id: str, data: DeviceAssignmentCreate):
    """
    Assegna un device dal Dude a questo cliente.
    
    - **dude_device_id**: ID del device nel Dude (obbligatorio)
    - **role**: Ruolo del device (router, switch, firewall, etc.)
    - **primary_network_id**: Rete principale del device
    - **credential_id**: Credenziali specifiche per questo device
    """
    data.customer_id = customer_id
    
    try:
        service = get_customer_service()
        return service.assign_device(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{dude_device_id}", response_model=DeviceAssignment)
async def get_device_assignment(dude_device_id: str):
    """
    Ottiene assegnazione di un device specifico.
    """
    service = get_customer_service()
    assignment = service.get_device_assignment(dude_device_id)
    
    if not assignment:
        raise HTTPException(status_code=404, detail=f"Device {dude_device_id} non assegnato")
    
    return assignment


@router.put("/devices/{dude_device_id}", response_model=DeviceAssignment)
async def update_device_assignment(dude_device_id: str, data: DeviceAssignmentUpdate):
    """
    Aggiorna assegnazione device.
    """
    service = get_customer_service()
    assignment = service.update_device_assignment(dude_device_id, data)
    
    if not assignment:
        raise HTTPException(status_code=404, detail=f"Device {dude_device_id} non assegnato")
    
    return assignment


@router.delete("/devices/{dude_device_id}")
async def unassign_device(dude_device_id: str):
    """
    Rimuove assegnazione device.
    """
    service = get_customer_service()
    
    if not service.unassign_device(dude_device_id):
        raise HTTPException(status_code=404, detail=f"Device {dude_device_id} non assegnato")
    
    return {"status": "success", "message": f"Device {dude_device_id} rimosso"}


# ==========================================
# UTILITY ENDPOINTS
# ==========================================

@router.get("/{customer_id}/summary")
async def get_customer_summary(customer_id: str):
    """
    Ottiene riepilogo completo di un cliente.
    """
    service = get_customer_service()
    
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Cliente {customer_id} non trovato")
    
    networks = service.list_networks(customer_id=customer_id)
    credentials = service.list_credentials(customer_id=customer_id)
    devices = service.list_device_assignments(customer_id=customer_id)
    
    return {
        "customer": customer,
        "summary": {
            "networks": len(networks),
            "credentials": len(credentials),
            "devices": len(devices),
            "devices_by_role": _count_by_field(devices, "role"),
        },
        "networks": networks,
        "credentials": credentials,
        "devices": devices,
    }


def _count_by_field(items: List, field: str) -> dict:
    """Conta elementi per valore di un campo"""
    counts = {}
    for item in items:
        value = getattr(item, field, None) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


# ==========================================
# AGENT ASSIGNMENTS (SONDE)
# ==========================================

@router.get("/{customer_id}/agents", response_model=List[AgentAssignmentSafe])
async def list_customer_agents(
    customer_id: str,
    active_only: bool = Query(True),
):
    """
    Lista le sonde assegnate a un cliente.
    """
    service = get_customer_service()
    
    # Verifica cliente esiste
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Cliente {customer_id} non trovato")
    
    return service.list_agents(customer_id=customer_id, active_only=active_only)


@router.post("/{customer_id}/agents", response_model=AgentAssignment, status_code=201)
async def create_customer_agent(customer_id: str, data: AgentAssignmentCreate):
    """
    Crea una nuova sonda per il cliente.
    """
    data.customer_id = customer_id
    
    # Log dei dati ricevuti per debug
    logger.info(f"Creating agent for customer {customer_id}: name={data.name}, address={data.address}, "
                f"agent_type={data.agent_type}, agent_api_port={data.agent_api_port}, "
                f"agent_token={'***' if data.agent_token else None}")
    
    try:
        service = get_customer_service()
        return service.create_agent(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentAssignment)
async def get_agent(agent_id: str, include_password: bool = Query(False)):
    """
    Ottiene dettagli di una sonda.
    """
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=include_password)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    return agent


@router.put("/agents/{agent_id}", response_model=AgentAssignment)
async def update_agent(agent_id: str, data: AgentAssignmentUpdate):
    """
    Aggiorna una sonda.
    """
    service = get_customer_service()
    agent = service.update_agent(agent_id, data)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """
    Elimina una sonda.
    """
    service = get_customer_service()
    
    if not service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    return {"status": "deleted", "agent_id": agent_id}


@router.post("/agents/{agent_id}/test")
async def test_agent_connection(
    agent_id: str,
    test_type: Optional[str] = Query(None, description="Forza tipo test: api, ssh, docker, o auto (default)")
):
    """
    Testa la connessione a una sonda (API RouterOS, SSH, o Docker Agent).
    """
    import routeros_api
    import paramiko
    import socket
    
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    agent_type = getattr(agent, 'agent_type', 'mikrotik')
    
    # Se è un agent Docker, testa via HTTP
    if agent_type == "docker" or test_type == "docker":
        from ..services.agent_service import get_agent_service
        
        agent_svc = get_agent_service()
        agent_info = agent_svc._agent_to_dict(agent)
        
        try:
            health = await agent_svc.check_agent_health(agent_info)
            
            if health.get("status") == "healthy":
                service.update_agent_status(agent_id, "online", health.get("version", ""))
                return {
                    "success": True,
                    "connection_type": "docker",
                    "status": "online",
                    "results": {"docker": health},
                    "message": f"Docker Agent OK - {health.get('agent_name', agent.name)}"
                }
            else:
                service.update_agent_status(agent_id, "offline", "")
                return {
                    "success": False,
                    "connection_type": "docker",
                    "status": "offline",
                    "results": {"docker": health},
                    "message": f"Docker Agent fallito: {health.get('error', 'Unknown error')}"
                }
        except Exception as e:
            service.update_agent_status(agent_id, "offline", "")
            return {
                "success": False,
                "connection_type": "docker",
                "status": "offline",
                "results": {"docker": {"error": str(e)}},
                "message": f"Docker Agent fallito: {e}"
            }
    
    # MikroTik nativo
    conn_type = test_type or agent.connection_type
    results = {"api": None, "ssh": None}
    
    # Test API RouterOS
    if conn_type in ["api", "both"]:
        try:
            connection = routeros_api.RouterOsApiPool(
                host=agent.address,
                username=agent.username or "admin",
                password=agent.password or "",
                port=agent.port,
                use_ssl=agent.use_ssl,
                ssl_verify=False,
                plaintext_login=True,
            )
            
            api = connection.get_api()
            
            identity = api.get_resource('/system/identity')
            identity_data = identity.get()
            name = identity_data[0].get('name', 'Unknown') if identity_data else 'Unknown'
            
            resource = api.get_resource('/system/resource')
            resource_data = resource.get()
            version = resource_data[0].get('version', '') if resource_data else ''
            
            connection.disconnect()
            
            results["api"] = {
                "success": True,
                "name": name,
                "version": version,
                "message": f"API OK - {name}"
            }
        except Exception as e:
            results["api"] = {
                "success": False,
                "error": str(e),
                "message": f"API fallita: {e}"
            }
    
    # Test SSH
    if conn_type in ["ssh", "both"]:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_params = {
                "hostname": agent.address,
                "port": agent.ssh_port,
                "username": agent.username or "admin",
                "timeout": 10,
                "allow_agent": False,
                "look_for_keys": False,
            }
            
            # Usa chiave SSH se disponibile, altrimenti password
            if agent.ssh_key:
                from io import StringIO
                key = paramiko.RSAKey.from_private_key(StringIO(agent.ssh_key))
                connect_params["pkey"] = key
            else:
                connect_params["password"] = agent.password or ""
            
            ssh.connect(**connect_params)
            
            # Esegui comando per verificare
            stdin, stdout, stderr = ssh.exec_command("/system identity print")
            output = stdout.read().decode().strip()
            
            # Ottieni versione
            stdin, stdout, stderr = ssh.exec_command("/system resource print")
            resource_output = stdout.read().decode()
            
            ssh.close()
            
            # Parse output
            name = "Unknown"
            version = ""
            for line in output.split('\n'):
                if 'name:' in line.lower():
                    name = line.split(':')[-1].strip()
            for line in resource_output.split('\n'):
                if 'version:' in line.lower():
                    version = line.split(':')[-1].strip()
            
            results["ssh"] = {
                "success": True,
                "name": name,
                "version": version,
                "message": f"SSH OK - {name}"
            }
        except Exception as e:
            results["ssh"] = {
                "success": False,
                "error": str(e),
                "message": f"SSH fallita: {e}"
            }
    
    # Determina stato finale
    api_ok = results["api"] and results["api"]["success"] if results["api"] else None
    ssh_ok = results["ssh"] and results["ssh"]["success"] if results["ssh"] else None
    
    if conn_type == "both":
        success = api_ok and ssh_ok
        status = "online" if success else ("partial" if (api_ok or ssh_ok) else "offline")
    elif conn_type == "api":
        success = api_ok
        status = "online" if success else "offline"
    else:  # ssh
        success = ssh_ok
        status = "online" if success else "offline"
    
    # Aggiorna stato
    version = (results["api"] or results["ssh"] or {}).get("version", "")
    service.update_agent_status(agent_id, status, version)
    
    return {
        "success": success,
        "connection_type": conn_type,
        "status": status,
        "results": results,
        "message": f"Test {conn_type}: {'OK' if success else 'Fallito'}"
    }


@router.post("/agents/{agent_id}/ssh-command")
async def execute_ssh_command(
    agent_id: str,
    command: str = Query(..., description="Comando da eseguire"),
):
    """
    Esegue un comando SSH sulla sonda.
    """
    import paramiko
    
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    if agent.connection_type not in ["ssh", "both"]:
        raise HTTPException(status_code=400, detail="Sonda non configurata per SSH")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_params = {
            "hostname": agent.address,
            "port": agent.ssh_port,
            "username": agent.username or "admin",
            "timeout": 30,
            "allow_agent": False,
            "look_for_keys": False,
        }
        
        if agent.ssh_key:
            from io import StringIO
            key = paramiko.RSAKey.from_private_key(StringIO(agent.ssh_key))
            connect_params["pkey"] = key
        else:
            connect_params["password"] = agent.password or ""
        
        ssh.connect(**connect_params)
        
        stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
        output = stdout.read().decode()
        error = stderr.read().decode()
        exit_code = stdout.channel.recv_exit_status()
        
        ssh.close()
        
        return {
            "success": exit_code == 0,
            "command": command,
            "output": output,
            "error": error,
            "exit_code": exit_code
        }
        
    except Exception as e:
        return {
            "success": False,
            "command": command,
            "error": str(e),
            "message": f"Errore SSH: {e}"
        }


@router.post("/agents/{agent_id}/scan")
async def start_agent_scan(
    agent_id: str,
    network_id: Optional[str] = Query(None, description="ID rete da scansionare"),
    scan_type: str = Query("ping", description="Tipo scan: ping, arp, snmp, all"),
    add_devices: bool = Query(False, description="Aggiungi device a Dude"),
):
    """
    Avvia una scansione tramite la sonda.
    """
    from ..services import get_dude_service
    
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    # Determina rete da scansionare
    network_cidr = None
    if network_id:
        networks = service.list_networks(customer_id=agent.customer_id)
        network = next((n for n in networks if n.id == network_id), None)
        if network:
            network_cidr = network.ip_network
    elif agent.assigned_networks:
        # Usa prima rete assegnata
        networks = service.list_networks(customer_id=agent.customer_id)
        for net in networks:
            if net.id in agent.assigned_networks:
                network_cidr = net.ip_network
                break
    
    if not network_cidr:
        raise HTTPException(status_code=400, detail="Nessuna rete specificata o assegnata")
    
    # Avvia discovery via Dude con l'agent specificato
    dude = get_dude_service()
    result = dude.start_discovery(
        network=network_cidr,
        agent_id=agent.dude_agent_id,  # ID agent in Dude
        scan_type=scan_type or agent.default_scan_type,
        add_devices=add_devices or agent.auto_add_devices,
    )
    
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "network": network_cidr,
        "scan_type": scan_type,
        **result
    }



@router.post("/agents/{agent_id}/register-in-dude")
async def register_agent_in_dude(agent_id: str):
    """
    Registra una sonda locale come agent in The Dude.
    Questo permette a The Dude di usare il router per eseguire discovery.
    """
    from ..services import get_dude_service
    
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    # Registra in The Dude
    dude = get_dude_service()
    result = dude.add_agent_to_dude(
        name=agent.name,
        address=agent.address,
        port=agent.port,
        username=agent.username or "admin",
        password=agent.password or "",
        use_ssl=agent.use_ssl,
    )
    
    if result.get("success"):
        # Aggiorna la sonda locale con l'ID di The Dude
        dude_agent_id = result.get("agent_id")
        if dude_agent_id:
            service.update_agent(agent_id, AgentAssignmentUpdate(
                dude_agent_id=dude_agent_id
            ))
        
        return {
            "success": True,
            "agent_id": agent_id,
            "dude_agent_id": dude_agent_id,
            "message": result.get("message"),
            "existing": result.get("existing", False)
        }
    else:
        return {
            "success": False,
            "error": result.get("error"),
            "message": result.get("message")
        }


@router.delete("/agents/{agent_id}/unregister-from-dude")
async def unregister_agent_from_dude(agent_id: str):
    """
    Rimuove una sonda da The Dude (ma la mantiene in DaDude).
    """
    from ..services import get_dude_service
    
    service = get_customer_service()
    agent = service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    if not agent.dude_agent_id:
        return {
            "success": False,
            "message": "Sonda non registrata in The Dude"
        }
    
    # Rimuovi da The Dude
    dude = get_dude_service()
    result = dude.remove_agent_from_dude(agent.dude_agent_id)
    
    if result.get("success"):
        # Rimuovi l'ID Dude dalla sonda locale
        service.update_agent(agent_id, AgentAssignmentUpdate(
            dude_agent_id=None
        ))
        
        return {
            "success": True,
            "message": "Sonda rimossa da The Dude"
        }
    else:
        return result


@router.post("/agents/{agent_id}/scan-customer-networks")
async def scan_customer_networks(
    agent_id: str,
    scan_type: str = Query("arp", description="Tipo scan: arp, ping, all"),
    network_ids: Optional[List[str]] = Query(None, description="IDs reti da scansionare (tutte se vuoto)"),
):
    """
    Scansiona le reti del cliente usando la sonda con connessione diretta.
    Salva i risultati nel database per visualizzazione successiva.
    """
    from ..services.scanner_service import get_scanner_service
    from ..models.database import ScanResult, DiscoveredDevice, init_db, get_session
    from ..config import get_settings
    
    service = get_customer_service()
    agent = service.get_agent(agent_id, include_password=True)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    # Ottieni reti del cliente
    networks = service.list_networks(customer_id=agent.customer_id, active_only=True)
    
    if not networks:
        raise HTTPException(status_code=400, detail="Nessuna rete configurata per il cliente")
    
    # Filtra reti se specificato
    if network_ids:
        networks = [n for n in networks if n.id in network_ids]
    
    if not networks:
        raise HTTPException(status_code=400, detail="Nessuna rete valida selezionata")
    
    # Esegui scansione diretta tramite il router o Docker agent
    scanner = get_scanner_service()
    network = networks[0]  # Prima rete
    
    # Verifica tipo agent
    agent_type = getattr(agent, 'agent_type', 'mikrotik') or 'mikrotik'
    
    logger.info(f"Scan request: agent_type={agent_type}, agent_id={agent.id}, address={agent.address}")
    
    if agent_type == "docker":
        # Scansione tramite Docker Agent
        # Strategia: se c'è un MikroTik nel cliente, usalo per ARP scan
        from ..services.agent_client import AgentClient, AgentConfig
        
        agent_url = agent.agent_url or f"http://{agent.address}:{agent.agent_api_port or 8080}"
        agent_token = agent.agent_token or ""
        
        logger.info(f"Docker agent config: url={agent_url}, token={'***' if agent_token else 'MISSING'}")
        
        # Cerca un MikroTik agent per questo cliente (per ARP scan)
        # Nota: list_agents non restituisce password, dobbiamo usare get_agent per ogni MikroTik
        all_agents = service.list_agents(customer_id=agent.customer_id, active_only=True)
        mikrotik_agent = None
        for ag in all_agents:
            ag_type = getattr(ag, 'agent_type', 'mikrotik') or 'mikrotik'
            if ag_type == 'mikrotik' and ag.id != agent_id:
                # Ottieni l'agent con password
                mikrotik_agent = service.get_agent(ag.id, include_password=True)
                break
        
        scan_result = None
        
        if mikrotik_agent:
            # OPZIONE B: Usa MikroTik per ARP scan (ottiene MAC address)
            logger.info(f"[SCAN VIA MIKROTIK] Using {mikrotik_agent.name} ({mikrotik_agent.address}) for ARP scan on {network.ip_network}")
            try:
                if mikrotik_agent.connection_type in ["api", "both"]:
                    scan_result = scanner.scan_network_via_router(
                        router_address=mikrotik_agent.address,
                        router_port=mikrotik_agent.port or 8728,
                        router_username=mikrotik_agent.username or "admin",
                        router_password=mikrotik_agent.password or "",
                        network=network.ip_network,
                        scan_type="arp",  # Forza ARP per ottenere MAC
                        use_ssl=mikrotik_agent.use_ssl or False,
                    )
                elif mikrotik_agent.connection_type == "ssh":
                    scan_result = scanner.scan_network_via_ssh(
                        router_address=mikrotik_agent.address,
                        ssh_port=mikrotik_agent.ssh_port or 22,
                        username=mikrotik_agent.username or "admin",
                        password=mikrotik_agent.password or "",
                        network=network.ip_network,
                        ssh_key=mikrotik_agent.ssh_key,
                    )
                logger.info(f"[SCAN VIA MIKROTIK] ARP scan completed: {scan_result.get('devices_found', 0)} devices found")
            except Exception as e:
                logger.warning(f"[SCAN VIA MIKROTIK] ARP scan FAILED, falling back to Docker agent: {e}")
                scan_result = None
        
        if not scan_result or not scan_result.get("success"):
            # OPZIONE C: Nessun MikroTik o fallback - usa Docker agent con ARP attivo
            logger.info(f"[SCAN VIA DOCKER AGENT] Using {agent.address}:{agent.agent_api_port} for network scan on {network.ip_network}")
            agent_config = AgentConfig(
                agent_id=agent.id,
                agent_url=agent_url,
                agent_token=agent_token,
            )
            
            agent_client = AgentClient(agent_config)
            try:
                logger.info(f"Starting network scan via Docker agent: network={network.ip_network}")
                scan_result = await agent_client.scan_network(network.ip_network, scan_type=scan_type)
                logger.info(f"[SCAN VIA DOCKER AGENT] Scan completed: {scan_result.get('devices_found', 0)} devices found")
            except Exception as e:
                logger.error(f"Docker agent scan failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Errore scansione Docker agent: {e}")
            finally:
                await agent_client.close()
    
    # MikroTik agent - Usa API o SSH in base al tipo di connessione
    elif agent.connection_type in ["api", "both"]:
        logger.info(f"[SCAN VIA MIKROTIK API] Using {agent.name} ({agent.address}:{agent.port}) for scan on {network.ip_network}")
        scan_result = scanner.scan_network_via_router(
            router_address=agent.address,
            router_port=agent.port,
            router_username=agent.username or "admin",
            router_password=agent.password or "",
            network=network.ip_network,
            scan_type=scan_type,
            use_ssl=agent.use_ssl,
        )
    elif agent.connection_type == "ssh":
        logger.info(f"[SCAN VIA MIKROTIK SSH] Using {agent.name} ({agent.address}:{agent.ssh_port}) for scan on {network.ip_network}")
        scan_result = scanner.scan_network_via_ssh(
            router_address=agent.address,
            ssh_port=agent.ssh_port,
            username=agent.username or "admin",
            password=agent.password or "",
            network=network.ip_network,
            ssh_key=agent.ssh_key,
        )
    else:
        raise HTTPException(status_code=400, detail="Tipo connessione non valido")
    
    # Salva risultati nel database
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Crea record scansione
        scan_record = ScanResult(
            customer_id=agent.customer_id,
            agent_id=agent_id,
            network_id=network.id,
            network_cidr=network.ip_network,
            scan_type=scan_type,
            devices_found=scan_result.get("devices_found", 0),
            status="completed" if scan_result.get("success") else "failed",
            error_message=scan_result.get("error"),
        )
        session.add(scan_record)
        session.flush()  # Per ottenere l'ID
        
        # Salva dispositivi trovati
        if scan_result.get("success") and scan_result.get("results"):
            from ..services.device_probe_service import get_device_probe_service, MikroTikAgent
            from ..services.mikrotik_service import get_mikrotik_service
            
            probe_service = get_device_probe_service()
            mikrotik_service = get_mikrotik_service()
            
            # Prepara lista DNS servers dalla rete
            dns_servers = []
            if network.dns_primary:
                dns_servers.append(network.dns_primary)
            if network.dns_secondary:
                dns_servers.append(network.dns_secondary)
            
            # Crea oggetto MikroTikAgent per operazioni remote (solo per agent MikroTik)
            mikrotik_agent = None
            if agent_type == "mikrotik" and agent and agent.address and agent.username:
                mikrotik_agent = MikroTikAgent(
                    address=agent.address,
                    username=agent.username,
                    password=agent.password or "",
                    port=agent.ssh_port or 22,
                    api_port=agent.port or 8728,
                    use_ssl=agent.use_ssl or False,
                    dns_server=dns_servers[0] if dns_servers else None,
                )
            
            logger.info(f"Processing {len(scan_result['results'])} devices, DNS servers: {dns_servers}, agent: {mikrotik_agent.address if mikrotik_agent else 'local'}")
            
            # Prova batch reverse DNS tramite MikroTik se abbiamo un agente
            mikrotik_dns_results = {}
            if mikrotik_agent:
                try:
                    target_ips = [d.get("address", "") for d in scan_result["results"] if d.get("address")]
                    
                    mikrotik_dns_results = mikrotik_service.batch_reverse_dns_lookup(
                        address=mikrotik_agent.address,
                        port=mikrotik_agent.api_port,
                        username=mikrotik_agent.username,
                        password=mikrotik_agent.password,
                        target_ips=target_ips,
                        dns_server=mikrotik_agent.dns_server,
                    )
                    logger.info(f"MikroTik batch DNS resolved {len(mikrotik_dns_results)}/{len(target_ips)} hostnames")
                except Exception as e:
                    logger.warning(f"MikroTik batch DNS lookup failed: {e}")
            
            for device in scan_result["results"]:
                device_ip = device.get("address", "")
                device_mac = device.get("mac_address", "")
                
                # Reverse DNS lookup per ottenere hostname
                hostname = ""
                
                # Prima prova con risultati batch MikroTik
                if device_ip and device_ip in mikrotik_dns_results:
                    hostname = mikrotik_dns_results[device_ip]
                    logger.debug(f"Hostname from MikroTik DNS: {device_ip} -> {hostname}")
                
                # Fallback a lookup diretto/tramite agente se non trovato
                if not hostname and device_ip:
                    try:
                        hostname = await probe_service.reverse_dns_lookup(
                            device_ip, 
                            dns_servers=dns_servers if dns_servers else None,
                            agent=mikrotik_agent,
                            use_agent=True
                        )
                        if hostname:
                            logger.info(f"Reverse DNS for {device_ip}: {hostname}")
                    except Exception as e:
                        logger.debug(f"Reverse DNS lookup failed for {device_ip}: {e}")
                
                # Usa hostname da DNS se non c'è identity
                identity = device.get("identity", "")
                if not identity and hostname:
                    identity = hostname.split('.')[0]  # Prendi solo la parte prima del punto
                
                # Scansiona porte aperte tramite agente MikroTik
                open_ports_data = []
                if device_ip:
                    try:
                        # Usa agente MikroTik se disponibile per la scansione porte
                        ports_result = await probe_service.scan_services(
                            device_ip, 
                            agent=mikrotik_agent, 
                            use_agent=True
                        )
                        open_ports_data = ports_result
                        open_count = len([p for p in ports_result if p.get('open')])
                        scan_method = "via agent" if mikrotik_agent else "direct"
                        logger.debug(f"Port scan for {device_ip} ({scan_method}): {open_count} ports open")
                    except Exception as e:
                        logger.warning(f"Port scan failed for {device_ip}: {e}")
                
                dev_record = DiscoveredDevice(
                    scan_id=scan_record.id,
                    customer_id=agent.customer_id,
                    address=device_ip,
                    mac_address=device_mac,
                    identity=identity or hostname,  # Usa identity o hostname DNS
                    hostname=hostname,  # Salva anche hostname completo
                    platform=device.get("platform", ""),
                    board=device.get("board", ""),
                    interface=device.get("interface", ""),
                    source=device.get("source", ""),
                    open_ports=open_ports_data if open_ports_data else None,
                )
                session.add(dev_record)
        
        session.commit()
        scan_id = scan_record.id
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving scan results: {e}")
        scan_id = None
    finally:
        session.close()
    
    # Prepara risposta con formato compatibile con la UI
    return {
        "scan_id": scan_id,
        "agent_id": agent_id,
        "agent_name": agent.name,
        "customer_id": agent.customer_id,
        "scan_type": scan_type,
        "networks_scanned": 1,
        "results": [{
            "network_id": network.id,
            "network_name": network.name,
            "network_cidr": network.ip_network,
            "success": scan_result.get("success", False),
            "devices_found": scan_result.get("devices_found", 0),
            "devices": scan_result.get("results", []),  # Includi i dispositivi!
            "error": scan_result.get("error"),
        }],
        "message": scan_result.get("message", ""),
        "view_url": f"/customers/{agent.customer_id}/scans/{scan_id}" if scan_id else None
    }


# ==========================================
# SCAN RESULTS
# ==========================================

@router.get("/{customer_id}/scans")
async def list_customer_scans(
    customer_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Lista scansioni di un cliente"""
    from ..models.database import ScanResult, init_db, get_session
    from ..config import get_settings
    
    service = get_customer_service()
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        scans = session.query(ScanResult).filter(
            ScanResult.customer_id == customer_id
        ).order_by(ScanResult.created_at.desc()).limit(limit).all()
        
        return {
            "customer_id": customer_id,
            "total": len(scans),
            "scans": [
                {
                    "id": s.id,
                    "network_cidr": s.network_cidr,
                    "scan_type": s.scan_type,
                    "devices_found": s.devices_found,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in scans
            ]
        }
    finally:
        session.close()


@router.get("/{customer_id}/scans/{scan_id}")
async def get_scan_details(customer_id: str, scan_id: str):
    """Dettagli di una scansione con dispositivi trovati"""
    from ..models.database import ScanResult, DiscoveredDevice, init_db, get_session
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        scan = session.query(ScanResult).filter(
            ScanResult.id == scan_id,
            ScanResult.customer_id == customer_id
        ).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scansione non trovata")
        
        devices = session.query(DiscoveredDevice).filter(
            DiscoveredDevice.scan_id == scan_id
        ).order_by(DiscoveredDevice.identity, DiscoveredDevice.address).all()
        
        return {
            "scan": {
                "id": scan.id,
                "network_cidr": scan.network_cidr,
                "scan_type": scan.scan_type,
                "devices_found": scan.devices_found,
                "status": scan.status,
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
            },
            "devices": [
                {
                    "id": d.id,
                    "address": d.address,
                    "mac_address": d.mac_address,
                    "identity": d.identity,
                    "hostname": d.hostname,  # Hostname da reverse DNS
                    "platform": d.platform,
                    "board": d.board,
                    "interface": d.interface,
                    "source": d.source,
                    "imported": d.imported,
                    "open_ports": d.open_ports,
                    "os_family": d.os_family,
                    "os_version": d.os_version,
                    "vendor": d.vendor,
                    "model": d.model,
                    "category": d.category,
                    "cpu_cores": d.cpu_cores,
                    "ram_total_mb": d.ram_total_mb,
                    "disk_total_gb": d.disk_total_gb,
                    "serial_number": d.serial_number,
                }
                for d in devices
            ]
        }
    finally:
        session.close()


@router.delete("/{customer_id}/scans/{scan_id}")
async def delete_scan(customer_id: str, scan_id: str):
    """Elimina una scansione e i suoi dispositivi"""
    from ..models.database import ScanResult, init_db, get_session
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url.replace("+aiosqlite", "")
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        scan = session.query(ScanResult).filter(
            ScanResult.id == scan_id,
            ScanResult.customer_id == customer_id
        ).first()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scansione non trovata")
        
        session.delete(scan)  # Cascade elimina anche i devices
        session.commit()
        
        return {"status": "deleted", "scan_id": scan_id}
    finally:
        session.close()
