"""
DaDude - The Dude MikroTik Connector
Main FastAPI Application

Permette di esporre i dati di The Dude come API REST
per applicazioni esterne di monitoraggio.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import sys
import os
from pathlib import Path

from .config import get_settings
from .services import get_dude_service, get_sync_service
from .services.websocket_hub import get_websocket_hub
from .routers import devices, probes, alerts, webhook, system, customers, import_export, dashboard, discovery, mikrotik, inventory, agents


# Configura logging
def setup_logging():
    settings = get_settings()
    
    # Rimuovi handler default
    logger.remove()
    
    # Console output
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    
    # File output
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        settings.log_file,
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione lifecycle applicazione"""
    setup_logging()
    settings = get_settings()
    
    logger.info("=" * 60)
    logger.info("DaDude - The Dude MikroTik Connector")
    logger.info("=" * 60)
    
    # Crea directory necessarie
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    
    # Avvia WebSocket Hub per agent mTLS
    ws_hub = get_websocket_hub()
    await ws_hub.start()
    logger.info("WebSocket Hub started for agent connections")
    
    # Connetti a Dude Server (opzionale)
    dude = get_dude_service()
    if dude.connect():
        logger.success(f"Connected to Dude Server at {settings.dude_host}")
        
        # Avvia sync service
        sync = get_sync_service()
        
        # Prima sync iniziale
        await sync.full_sync()
        
        # Avvia scheduler
        sync.start()
    else:
        logger.warning("Running in offline mode - Dude Server not available")
    
    yield
    
    # Shutdown
    logger.info("Shutting down DaDude...")
    
    # Ferma WebSocket Hub
    ws_hub = get_websocket_hub()
    await ws_hub.stop()
    logger.info("WebSocket Hub stopped")
    
    sync = get_sync_service()
    sync.stop()
    
    dude = get_dude_service()
    dude.disconnect()
    
    logger.info("DaDude shutdown complete")


# Crea applicazione FastAPI
app = FastAPI(
    title="DaDude",
    description="""
## The Dude MikroTik Connector - Multi-Tenant Edition

DaDude espone i dati di monitoraggio di **The Dude** tramite API REST,
con supporto **multi-tenant** per gestione clienti MSP/MSSP.

### Funzionalità

- 📡 **Dispositivi**: Lista e stato di tutti i dispositivi monitorati
- 🔍 **Probe/Sonde**: Metriche e valori delle sonde configurate
- 🚨 **Alert**: Notifiche e allarmi in tempo reale
- 🔄 **Webhook**: Ricevi notifiche push su cambi di stato
- 👥 **Multi-Tenant**: Gestione clienti con reti e credenziali dedicate
- 🌐 **Reti Sovrapposte**: Supporto reti IP/VLAN indipendenti per cliente
- 🔐 **Credenziali**: Gestione credenziali per device specifici o di default
- 📊 **API REST**: Integrazione semplice con qualsiasi applicazione

### Autenticazione

Usa l'header `X-API-Key` per autenticarti alle API.
    """,
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler globale
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Registra routers
app.include_router(devices.router, prefix="/api/v1")
app.include_router(probes.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(mikrotik.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(import_export.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")

# Dashboard (senza prefisso API)
app.include_router(dashboard.router)


# Monta directory static se esiste
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api", tags=["Root"])
async def api_info():
    """Endpoint info API"""
    return {
        "name": "DaDude API",
        "version": "1.1.0",
        "description": "The Dude MikroTik Connector - Multi-Tenant",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "health": "/api/v1/system/health",
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """Health check rapido"""
    dude = get_dude_service()
    sync = get_sync_service()
    
    return {
        "status": "healthy" if dude.is_connected else "degraded",
        "dude_connected": dude.is_connected,
        "devices_cached": len(sync.devices),
        "probes_cached": len(sync.probes),
        "last_sync": sync.last_sync.isoformat() if sync.last_sync else None,
    }
