"""
DaDude - Dashboard Router
Pagine web per dashboard e configurazione
"""
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime, timedelta
from loguru import logger
import os

from ..config import get_settings
from ..services import get_dude_service, get_sync_service, get_alert_service
from ..services.customer_service import get_customer_service
from ..services.settings_service import get_settings_service

router = APIRouter(tags=["Dashboard"])

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)


def get_dashboard_data():
    """Raccoglie dati per la dashboard"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    
    settings = get_settings()
    settings_service = get_settings_service()
    dude = get_dude_service()
    sync = get_sync_service()
    alert_service = get_alert_service()
    customer_service = get_customer_service()
    
    # Configurazione Dude
    dude_config = settings_service.get_dude_config()
    
    # Dati clienti
    customers = customer_service.list_customers(active_only=True, limit=1000)
    
    # Dati inventario locale
    try:
        db_url = settings.database_url.replace("+aiosqlite", "")
        engine = init_db(db_url)
        session = get_session(engine)
        
        # Conta dispositivi in inventario
        inventory_total = session.query(InventoryDevice).filter(InventoryDevice.active == True).count()
        inventory_monitored = session.query(InventoryDevice).filter(
            InventoryDevice.active == True,
            InventoryDevice.monitored == True
        ).count()
        inventory_online = session.query(InventoryDevice).filter(
            InventoryDevice.active == True,
            InventoryDevice.status == 'online'
        ).count()
        inventory_offline = session.query(InventoryDevice).filter(
            InventoryDevice.active == True,
            InventoryDevice.status == 'offline'
        ).count()
        
        # Conta sonde attive
        agents = customer_service.list_agents(active_only=True)
        agents_mikrotik = len([a for a in agents if a.agent_type == 'mikrotik'])
        agents_docker = len([a for a in agents if a.agent_type == 'docker'])
        
        session.close()
    except Exception as e:
        logger.warning(f"Errore lettura inventario: {e}")
        inventory_total = 0
        inventory_monitored = 0
        inventory_online = 0
        inventory_offline = 0
        agents = []
        agents_mikrotik = 0
        agents_docker = 0
    
    # Dati The Dude (opzionali)
    dude_devices = []
    dude_up = 0
    dude_down = 0
    dude_probes_ok = 0
    dude_probes_warning = 0
    dude_probes_critical = 0
    alerts_unack = 0
    
    if dude.is_connected:
        devices = sync.devices
        dude_up = len([d for d in devices if d.status.value == "up"])
        dude_down = len([d for d in devices if d.status.value == "down"])
        dude_devices = devices[:10]
        
        probes = sync.probes
        dude_probes_ok = len([p for p in probes if p.status.value == "ok"])
        dude_probes_warning = len([p for p in probes if p.status.value == "warning"])
        dude_probes_critical = len([p for p in probes if p.status.value == "critical"])
        
        alerts = alert_service.get_alerts(since=datetime.utcnow() - timedelta(hours=24), limit=100)
        alerts_unack = len([a for a in alerts if not a.acknowledged])
    
    return {
        "dude_connected": dude.is_connected,
        "dude_host": settings.dude_host,
        "dude_config": dude_config,
        "last_sync": sync.last_sync,
        # Inventario locale (principale)
        "inventory": {
            "total": inventory_total,
            "monitored": inventory_monitored,
            "online": inventory_online,
            "offline": inventory_offline,
        },
        "agents": {
            "total": len(agents) if agents else 0,
            "mikrotik": agents_mikrotik,
            "docker": agents_docker,
        },
        # The Dude (opzionale)
        "devices": {
            "total": len(dude_devices),
            "up": dude_up,
            "down": dude_down,
            "list": dude_devices,
        },
        "probes": {
            "ok": dude_probes_ok,
            "warning": dude_probes_warning,
            "critical": dude_probes_critical,
        },
        "alerts": {
            "unacknowledged": alerts_unack,
        },
        "customers": {
            "total": len(customers),
            "list": customers[:10],
        },
        "settings": settings,
    }


# ==========================================
# DASHBOARD PAGES
# ==========================================

@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard principale"""
    data = get_dashboard_data()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "page": "dashboard",
        "title": "Dashboard",
        **data
    })


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, status: Optional[str] = None):
    """Pagina dispositivi"""
    sync = get_sync_service()
    devices = sync.devices
    
    if status:
        devices = [d for d in devices if d.status.value == status]
    
    return templates.TemplateResponse("devices.html", {
        "request": request,
        "page": "devices",
        "title": "Dispositivi",
        "devices": devices,
        "status_filter": status,
    })


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    """Pagina alert"""
    alert_service = get_alert_service()
    alerts = alert_service.get_alerts(since=datetime.utcnow() - timedelta(hours=48), limit=200)
    
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "page": "alerts",
        "title": "Alert",
        "alerts": alerts,
    })


@router.get("/customers", response_class=HTMLResponse)
async def customers_page(request: Request):
    """Pagina clienti"""
    customer_service = get_customer_service()
    customers = customer_service.list_customers(active_only=False, limit=500)
    
    return templates.TemplateResponse("customers.html", {
        "request": request,
        "page": "customers",
        "title": "Clienti",
        "customers": customers,
    })


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(request: Request, customer_id: str):
    """Dettaglio cliente"""
    from ..services.websocket_hub import get_websocket_hub
    import re
    
    customer_service = get_customer_service()
    
    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    
    networks = customer_service.list_networks(customer_id=customer_id, active_only=False)
    credentials = customer_service.list_credentials(customer_id=customer_id, active_only=False)
    global_credentials = customer_service.list_global_credentials(active_only=True)
    devices = customer_service.list_device_assignments(customer_id=customer_id, active_only=False)
    agents_raw = customer_service.list_agents(customer_id=customer_id, active_only=False)
    
    # Arricchisci agents con stato WebSocket real-time
    hub = get_websocket_hub()
    ws_connected_names = set()
    
    if hub and hub._connections:
        for conn_id in hub._connections.keys():
            match = re.match(r'^agent-(.+?)(?:-\d+)?$', conn_id)
            if match:
                ws_connected_names.add(match.group(1))
    
    # Converti e arricchisci
    agents = []
    connected_docker_agents = []
    
    for agent in agents_raw:
        agent_dict = agent.model_dump() if hasattr(agent, 'model_dump') else dict(agent)
        agent_type = agent_dict.get('agent_type', 'mikrotik')
        agent_name = agent_dict.get('name', '')
        
        if agent_type == 'docker':
            if agent_name in ws_connected_names:
                agent_dict['status'] = 'online'
                agent_dict['ws_connected'] = True
                connected_docker_agents.append(agent_dict)
            else:
                agent_dict['ws_connected'] = False
        
        agents.append(agent_dict)
    
    # Per MikroTik, mostra se raggiungibili via Docker agent
    for agent_dict in agents:
        if agent_dict.get('agent_type', 'mikrotik') == 'mikrotik':
            if connected_docker_agents:
                bridge = connected_docker_agents[0]
                agent_dict['status'] = 'reachable'
                agent_dict['reachable_via'] = bridge.get('name', 'Docker Agent')
            else:
                agent_dict['status'] = 'unreachable'
    
    return templates.TemplateResponse("customer_detail.html", {
        "request": request,
        "page": "customers",
        "title": f"Cliente: {customer.name}",
        "customer": customer,
        "networks": networks,
        "credentials": credentials,
        "global_credentials": global_credentials,
        "devices": devices,
        "agents": agents,
    })


# ==========================================
# CREDENTIALS PAGE
# ==========================================

@router.get("/credentials", response_class=HTMLResponse)
async def credentials_page(request: Request):
    """Pagina credenziali globali"""
    customer_service = get_customer_service()
    
    # Ottieni credenziali globali (senza customer_id)
    credentials = customer_service.list_global_credentials()
    
    return templates.TemplateResponse("credentials.html", {
        "request": request,
        "page": "credentials",
        "title": "Credenziali Globali",
        "credentials": credentials,
    })


# ==========================================
# AGENTS PAGE
# ==========================================

@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    """Pagina gestione agent"""
    return templates.TemplateResponse("agents.html", {
        "request": request,
        "page": "agents",
        "title": "Gestione Agent",
    })


# ==========================================
# CONFIGURATION PAGES
# ==========================================

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Pagina configurazione"""
    settings = get_settings()
    dude = get_dude_service()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings",
        "title": "Configurazione",
        "settings": settings,
        "dude_connected": dude.is_connected,
    })


@router.get("/settings/webhooks", response_class=HTMLResponse)
async def webhooks_settings_page(request: Request):
    """Pagina configurazione webhook"""
    from ..services.webhook_service import get_webhook_service
    webhook_service = get_webhook_service()
    
    return templates.TemplateResponse("settings_webhooks.html", {
        "request": request,
        "page": "settings",
        "title": "Configurazione Webhook",
        "destinations": webhook_service.get_destinations(),
    })


@router.get("/settings/import-export", response_class=HTMLResponse)
async def import_export_page(request: Request):
    """Pagina import/export"""
    customer_service = get_customer_service()
    customers = customer_service.list_customers(active_only=True, limit=500)
    
    return templates.TemplateResponse("settings_import_export.html", {
        "request": request,
        "page": "settings",
        "title": "Import/Export",
        "customers": customers,
    })


# ==========================================
# DISCOVERY PAGES
# ==========================================

@router.get("/discovery", response_class=HTMLResponse)
async def discovery_page(request: Request):
    """Pagina discovery generale"""
    dude = get_dude_service()
    customer_service = get_customer_service()
    
    # Ottieni agenti disponibili
    agents = []
    if dude.is_connected:
        try:
            agents = dude.get_agents()
        except Exception as e:
            logger.warning(f"Error getting agents: {e}")
    
    # Ottieni clienti con le loro reti
    customers = customer_service.list_customers(active_only=True, limit=500)
    
    # Per ogni cliente, ottieni le reti (convertite in dict per JSON)
    customers_with_networks = []
    for customer in customers:
        networks = customer_service.list_networks(customer_id=customer.id, active_only=True)
        # Converti networks in lista di dict per serializzazione JSON
        networks_dict = [
            {"id": n.id, "name": n.name, "ip_network": n.ip_network, "network_type": n.network_type.value if hasattr(n.network_type, 'value') else n.network_type}
            for n in networks
        ]
        customers_with_networks.append({
            "customer": customer,
            "networks": networks_dict,
        })
    
    return templates.TemplateResponse("discovery.html", {
        "request": request,
        "page": "discovery",
        "title": "Network Discovery",
        "dude_connected": dude.is_connected,
        "agents": agents,
        "customers_with_networks": customers_with_networks,
    })


@router.get("/customers/{customer_id}/discovery", response_class=HTMLResponse)
async def customer_discovery_page(request: Request, customer_id: str):
    """Pagina discovery per cliente specifico"""
    dude = get_dude_service()
    customer_service = get_customer_service()
    
    # Ottieni cliente
    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    
    # Ottieni reti del cliente (convertite in dict per JSON)
    networks_db = customer_service.list_networks(customer_id=customer_id, active_only=True)
    networks = [
        {"id": n.id, "name": n.name, "ip_network": n.ip_network, "network_type": n.network_type.value if hasattr(n.network_type, 'value') else n.network_type}
        for n in networks_db
    ]
    
    # Ottieni agenti disponibili
    agents = []
    if dude.is_connected:
        try:
            agents = dude.get_agents()
        except Exception as e:
            logger.warning(f"Error getting agents: {e}")
    
    return templates.TemplateResponse("customer_discovery.html", {
        "request": request,
        "page": "customers",
        "title": f"Discovery - {customer.name}",
        "customer": customer,
        "networks": networks,
        "agents": agents,
        "dude_connected": dude.is_connected,
    })



@router.get("/customers/{customer_id}/agents/{agent_id}/mikrotik", response_class=HTMLResponse)
async def mikrotik_management(request: Request, customer_id: str, agent_id: str):
    """Pagina gestione MikroTik per una sonda"""
    from ..services.customer_service import get_customer_service
    
    customer_service = get_customer_service()
    
    # Ottieni cliente
    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    
    # Ottieni sonda
    agent = customer_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Sonda non trovata")
    
    if agent.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Sonda non appartiene a questo cliente")
    
    return templates.TemplateResponse("router_detail.html", {
        "request": request,
        "page": "customers",
        "title": f"{agent.name} - MikroTik",
        "customer": customer,
        "agent": agent,
    })
