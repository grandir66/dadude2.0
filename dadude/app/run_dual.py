#!/usr/bin/env python3
"""
DaDude - Dual Server Runner
Avvia entrambe le applicazioni FastAPI su porte separate

Porta 8000: Agent API (pubblico)
Porta 8001: Admin UI (privato)
"""
import asyncio
import signal
import sys
from multiprocessing import Process
import uvicorn
from loguru import logger


def run_agent_api():
    """Avvia Agent API su porta 8000"""
    uvicorn.run(
        "app.main_dual:agent_app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
        reload=False,
    )


def run_admin_ui():
    """Avvia Admin UI su porta 8001"""
    uvicorn.run(
        "app.main_dual:admin_app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        access_log=True,
        reload=False,
    )


def main():
    """Avvia entrambi i server in processi separati"""
    logger.info("=" * 70)
    logger.info("DaDude - Starting Dual Port Configuration")
    logger.info("=" * 70)
    logger.info("Agent API (public):  http://0.0.0.0:8000")
    logger.info("Admin UI (private):  http://0.0.0.0:8001")
    logger.info("=" * 70)

    # Crea processi per entrambi i server
    agent_process = Process(target=run_agent_api, name="agent-api-8000")
    admin_process = Process(target=run_admin_ui, name="admin-ui-8001")

    # Avvia processi
    agent_process.start()
    admin_process.start()

    # Handler per shutdown graceful
    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received, stopping servers...")
        agent_process.terminate()
        admin_process.terminate()
        agent_process.join(timeout=10)
        admin_process.join(timeout=10)
        logger.info("All servers stopped")
        sys.exit(0)

    # Registra handler per SIGINT e SIGTERM
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("Both servers started successfully")
    logger.info("Press Ctrl+C to stop")

    # Mantieni processo principale attivo
    try:
        agent_process.join()
        admin_process.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
