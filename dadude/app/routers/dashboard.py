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
from ..auth import (
    is_auth_enabled, verify_password, get_admin_username,
    create_session, destroy_session
)

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

# ==========================================
# LOGIN ROUTES
# ==========================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Pagina di login"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "username": get_admin_username(),
    })


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Processa il login"""
    admin_username = get_admin_username()
    
    if username != admin_username:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Username non valido",
            "username": username,
        })
    
    if not verify_password(password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Password non valida",
            "username": username,
        })
    
    # Login riuscito, crea sessione
    session_token = create_session(username)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="dadude_session",
        value=session_token,
        httponly=True,
        max_age=86400 * 7,  # 7 giorni
        samesite="lax"
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    """Logout e distrugge la sessione"""
    session_token = request.cookies.get("dadude_session")
    if session_token:
        destroy_session(session_token)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("dadude_session")
    return response


# ==========================================
# DASHBOARD ROUTES
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
    customers = customer_service.list_customers(active_only=True, limit=500)
    
    return templates.TemplateResponse("customers.html", {
        "request": request,
        "page": "customers",
        "title": "Clienti",
        "customers": customers,
    })


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(request: Request, customer_id: str):
    """Dettaglio cliente"""
    import re
    import httpx
    
    customer_service = get_customer_service()
    
    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    
    networks = customer_service.list_networks(customer_id=customer_id, active_only=False)
    credentials = customer_service.list_credentials(customer_id=customer_id, active_only=False)
    global_credentials = customer_service.list_global_credentials(active_only=True)
    devices = customer_service.list_device_assignments(customer_id=customer_id, active_only=False)
    agents_raw = customer_service.list_agents(customer_id=customer_id, active_only=False)
    
    # Ottieni stato WebSocket via HTTP dall'Agent API (porta 8000)
    ws_connected_names = set()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:8000/api/v1/agents/ws/connected")
            if resp.status_code == 200:
                ws_data = resp.json()
                for ws_agent in ws_data.get("agents", []):
                    agent_id = ws_agent.get("agent_id", "")
                    match = re.match(r'^agent-(.+?)(?:-\d+)?$', agent_id)
                    if match:
                        ws_connected_names.add(match.group(1))
                logger.debug(f"WebSocket connected names: {ws_connected_names}")
    except Exception as e:
        logger.warning(f"Could not fetch WebSocket status: {e}")
    
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
    import os
    settings = get_settings()
    dude = get_dude_service()
    
    # Leggi impostazioni extra da .env
    env_vars = {}
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings",
        "title": "Configurazione",
        "settings": settings,
        "dude_connected": dude.is_connected,
        "ssl_enabled": env_vars.get("SSL_ENABLED", "false").lower() == "true",
        "ssl_cert_path": env_vars.get("SSL_CERT_PATH", "/app/certs/server.crt"),
        "ssl_key_path": env_vars.get("SSL_KEY_PATH", "/app/certs/server.key"),
        "auth_enabled": env_vars.get("AUTH_ENABLED", "false").lower() == "true",
        "admin_username": env_vars.get("ADMIN_USERNAME", "admin"),
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
