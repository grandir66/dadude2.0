"""
DaDude - Dual Port Application
Main FastAPI Application with separated Agent API (8000) and Admin UI (8001)

Separazione per sicurezza:
- Porta 8000: Agent API (esposta su Internet, solo endpoint agent)
- Porta 8001: Admin UI + Management API (solo rete interna)
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
from .routers import (
    devices, probes, alerts, webhook, system, customers,
    import_export, dashboard, discovery, mikrotik, inventory, agents
)


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


# Shared lifespan context for both apps
_services_started = False

@asynccontextmanager
async def agent_lifespan(app: FastAPI):
    """Gestione lifecycle per Agent API"""
    global _services_started

    setup_logging()
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("DaDude Agent API - Starting on port 8000")
    logger.info("=" * 60)

    # Crea directory necessarie
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)

    # Avvia WebSocket Hub per agent mTLS (solo una volta)
    if not _services_started:
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

        _services_started = True

    yield

    # Shutdown
    logger.info("Shutting down Agent API...")


@asynccontextmanager
async def admin_lifespan(app: FastAPI):
    """Gestione lifecycle per Admin UI"""
    global _services_started

    setup_logging()

    logger.info("=" * 60)
    logger.info("DaDude Admin UI - Starting on port 8001")
    logger.info("=" * 60)

    # Crea directory necessarie
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)

    # Se i servizi non sono ancora partiti, avviali
    # (caso in cui si avvii solo admin senza agent)
    if not _services_started:
        settings = get_settings()
        ws_hub = get_websocket_hub()
        await ws_hub.start()
        logger.info("WebSocket Hub started")

        dude = get_dude_service()
        if dude.connect():
            logger.success(f"Connected to Dude Server at {settings.dude_host}")
            sync = get_sync_service()
            await sync.full_sync()
            sync.start()
        else:
            logger.warning("Running in offline mode - Dude Server not available")

        _services_started = True

    yield

    # Shutdown
    logger.info("Shutting down Admin UI...")

    # Ferma servizi solo se questa è l'ultima app a chiudere
    ws_hub = get_websocket_hub()
    await ws_hub.stop()
    logger.info("WebSocket Hub stopped")

    sync = get_sync_service()
    sync.stop()

    dude = get_dude_service()
    dude.disconnect()

    logger.info("DaDude shutdown complete")


# ==========================================
# AGENT API APPLICATION (Porta 8000)
# ==========================================

agent_app = FastAPI(
    title="DaDude Agent API",
    description="""
## Agent API - Network Inventory Agent Communication

**SOLO PER AGENT - Esposto su Internet**

Endpoint per comunicazione con agent distribuiti:
- Registrazione e enrollment agent
- WebSocket connessioni bidirezionali
- Heartbeat e health check
- Comandi remoti

**Autenticazione**: Token + mTLS certificati
    """,
    version="1.1.0",
    lifespan=agent_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS per Agent API
agent_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Gli agent possono venire da qualsiasi IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@agent_app.exception_handler(Exception)
async def agent_exception_handler(request: Request, exc: Exception):
    logger.error(f"Agent API unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

# Registra SOLO router agents (con tutti i suoi endpoint)
agent_app.include_router(agents.router, prefix="/api/v1")

# Health check per agent
@agent_app.get("/health", tags=["Health"])
async def agent_health_check():
    """Health check per Agent API"""
    ws_hub = get_websocket_hub()
    return {
        "status": "healthy",
        "service": "agent-api",
        "port": 8000,
        "websocket_hub": {
            "active": True,
            "connected_agents": ws_hub.connected_count if ws_hub else 0,
        }
    }

@agent_app.get("/", tags=["Root"])
async def agent_root():
    """Root endpoint Agent API"""
    return {
        "service": "DaDude Agent API",
        "version": "1.1.0",
        "port": 8000,
        "description": "Agent communication endpoint",
        "docs": "/docs",
        "health": "/health",
    }


# ==========================================
# ADMIN UI APPLICATION (Porta 8001)
# ==========================================

admin_app = FastAPI(
    title="DaDude Admin UI",
    description="""
## DaDude Admin - Management Interface

**SOLO RETE INTERNA - NON esporre su Internet**

Dashboard e API per gestione sistema:
- Dashboard web UI
- Gestione clienti multi-tenant
- Inventario dispositivi
- Configurazione reti e credenziali
- Import/Export dati
- Monitoraggio alert

**Autenticazione**: Da implementare (Basic Auth / API Key)
    """,
    version="1.1.0",
    lifespan=admin_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS per Admin UI
admin_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@admin_app.exception_handler(Exception)
async def admin_exception_handler(request: Request, exc: Exception):
    logger.error(f"Admin UI unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

# Registra tutti gli altri router (ESCLUSO agents)
admin_app.include_router(devices.router, prefix="/api/v1")
admin_app.include_router(probes.router, prefix="/api/v1")
admin_app.include_router(alerts.router, prefix="/api/v1")
admin_app.include_router(webhook.router, prefix="/api/v1")
admin_app.include_router(system.router, prefix="/api/v1")
admin_app.include_router(customers.router, prefix="/api/v1")
admin_app.include_router(mikrotik.router, prefix="/api/v1")
admin_app.include_router(inventory.router, prefix="/api/v1")
admin_app.include_router(import_export.router, prefix="/api/v1")
admin_app.include_router(discovery.router, prefix="/api/v1")

# Dashboard (senza prefisso API)
admin_app.include_router(dashboard.router)

# Monta directory static se esiste
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    admin_app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Health check per admin
@admin_app.get("/health", tags=["Health"])
async def admin_health_check():
    """Health check per Admin UI"""
    dude = get_dude_service()
    sync = get_sync_service()

    return {
        "status": "healthy" if dude.is_connected else "degraded",
        "service": "admin-ui",
        "port": 8001,
        "dude_connected": dude.is_connected,
        "devices_cached": len(sync.devices),
        "probes_cached": len(sync.probes),
        "last_sync": sync.last_sync.isoformat() if sync.last_sync else None,
    }

@admin_app.get("/api", tags=["Root"])
async def admin_api_info():
    """Endpoint info API"""
    return {
        "name": "DaDude Admin API",
        "version": "1.1.0",
        "description": "Management and Administration Interface",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "health": "/health",
    }
