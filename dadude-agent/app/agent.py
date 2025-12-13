"""
DaDude Agent v2.0 - WebSocket mTLS Client
Entry point principale per l'agent con architettura agent-initiated
"""
import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from .connection.ws_client import AgentWebSocketClient, ConnectionState, ReconnectionPolicy
from .connection.state_machine import ConnectionStateMachine, ConnectionEvent, ConnectionManager
from .commands.handler import CommandHandler
from .storage.local_queue import LocalQueue
from .workers.queue_worker import QueueWorker, StoreForwardManager
from .fallback.sftp_uploader import SFTPFallbackUploader, SFTPConfig
from .updater.self_update import SelfUpdater
from .scheduler.local_scheduler import LocalScheduler
from .config import get_settings


# Version
AGENT_VERSION = "2.0.0"


class DaDudeAgent:
    """
    Agent principale DaDude v2.0
    
    Architettura:
    - Connessione WebSocket bidirezionale al server (agent-initiated)
    - mTLS per autenticazione reciproca
    - Coda locale persistente per offline mode
    - Fallback SFTP quando server irraggiungibile
    - Scheduler locale per task periodici
    - Self-update automatico
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Info agent
        self.agent_id = self.settings.agent_id
        self.agent_name = self.settings.agent_name or self.agent_id
        self.server_url = self.settings.server_url
        
        # Paths
        self.data_dir = Path(self.settings.data_dir or "/var/lib/dadude-agent")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Certificati mTLS
        self.certs_dir = self.data_dir / "certs"
        self.certs_dir.mkdir(exist_ok=True)
        
        # Componenti
        self._ws_client: Optional[AgentWebSocketClient] = None
        self._command_handler: Optional[CommandHandler] = None
        self._local_queue: Optional[LocalQueue] = None
        self._queue_worker: Optional[QueueWorker] = None
        self._sftp_uploader: Optional[SFTPFallbackUploader] = None
        self._store_forward: Optional[StoreForwardManager] = None
        self._connection_manager: Optional[ConnectionManager] = None
        self._scheduler: Optional[LocalScheduler] = None
        self._updater: Optional[SelfUpdater] = None
        
        # State
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    def _setup_logging(self):
        """Configura logging"""
        logger.remove()
        
        # Console
        logger.add(
            sys.stderr,
            level=self.settings.log_level or "INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        )
        
        # File
        log_file = self.data_dir / "logs" / "agent.log"
        log_file.parent.mkdir(exist_ok=True)
        
        logger.add(
            str(log_file),
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            compression="gz",
        )
    
    def _setup_signal_handlers(self):
        """Configura handler per segnali"""
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )
    
    async def _initialize_components(self):
        """Inizializza tutti i componenti"""
        logger.info(f"Initializing DaDude Agent v{AGENT_VERSION}")
        logger.info(f"Agent ID: {self.agent_id}")
        logger.info(f"Server URL: {self.server_url}")
        
        # Command Handler
        self._command_handler = CommandHandler()
        
        # Local Queue (SQLite)
        queue_path = self.data_dir / "queue.db"
        self._local_queue = LocalQueue(db_path=str(queue_path))
        
        # WebSocket Client
        self._ws_client = AgentWebSocketClient(
            server_url=self.server_url,
            agent_id=self.agent_id,
            agent_token=self.settings.agent_token,
            client_cert_path=str(self.certs_dir / "agent.crt") if (self.certs_dir / "agent.crt").exists() else None,
            client_key_path=str(self.certs_dir / "agent.key") if (self.certs_dir / "agent.key").exists() else None,
            ca_cert_path=str(self.certs_dir / "ca.crt") if (self.certs_dir / "ca.crt").exists() else None,
            reconnect_policy=ReconnectionPolicy(
                initial_delay=1.0,
                max_delay=300.0,
                multiplier=2.0,
            ),
        )
        
        # Registra command handler
        self._ws_client.set_command_handler(self._command_handler.handle)
        self._ws_client.set_state_change_handler(self._on_connection_state_change)
        
        # Queue Worker (Store & Forward)
        self._store_forward = StoreForwardManager(
            ws_client=self._ws_client,
            db_path=str(queue_path),
        )
        
        # SFTP Fallback
        sftp_config = SFTPConfig.from_env()
        if sftp_config.enabled:
            self._sftp_uploader = SFTPFallbackUploader(
                agent_id=self.agent_id,
                config=sftp_config,
            )
        
        # Connection Manager (state machine + SFTP fallback)
        if self._sftp_uploader:
            self._connection_manager = ConnectionManager(
                ws_client=self._ws_client,
                sftp_uploader=self._sftp_uploader,
                local_queue=self._local_queue,
                sftp_timeout_minutes=int(os.getenv("SFTP_FALLBACK_TIMEOUT_MINUTES", "30")),
            )
        
        # Self-Updater
        self._updater = SelfUpdater(
            current_version=AGENT_VERSION,
            agent_dir=os.getenv("AGENT_DIR", "/opt/dadude-agent"),
            is_docker=os.path.exists("/.dockerenv"),
        )
        
        # Registra update callback nel command handler
        self._command_handler.set_update_callback(self._handle_update_command)
        
        # Scheduler
        self._scheduler = LocalScheduler(
            command_handler=self._command_handler,
            local_queue=self._local_queue,
            state_file=str(self.data_dir / "scheduler_state.json"),
        )
        
        logger.info("All components initialized")
    
    async def _on_connection_state_change(self, state: ConnectionState):
        """Handler per cambi stato connessione"""
        logger.info(f"Connection state changed: {state.value}")
        
        if state == ConnectionState.CONNECTED:
            # Flush coda pendente
            pending = await self._local_queue.get_pending_count()
            if pending > 0:
                logger.info(f"Flushing {pending} pending items")
                await self._ws_client.flush_pending_queue()
    
    async def _handle_update_command(self, download_url: str, checksum: str) -> bool:
        """Handler per comando update"""
        result = await self._updater.update(
            download_url=download_url if download_url else None,
            expected_checksum=checksum if checksum else None,
        )
        return result.success
    
    async def _enrollment_if_needed(self):
        """Esegue enrollment certificato se necessario"""
        cert_file = self.certs_dir / "agent.crt"
        key_file = self.certs_dir / "agent.key"
        ca_file = self.certs_dir / "ca.crt"
        
        if cert_file.exists() and key_file.exists() and ca_file.exists():
            logger.info("Certificates already present")
            return True
        
        logger.info("Certificates not found, requesting enrollment...")
        
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/api/v1/agents/enroll",
                    json={
                        "agent_id": self.agent_id,
                        "agent_name": self.agent_name,
                    },
                    headers={"Authorization": f"Bearer {self.settings.agent_token}"},
                    timeout=30.0,
                )
                
                if response.status_code == 403:
                    logger.warning("Agent not approved yet - waiting for admin approval")
                    return False
                
                if response.status_code != 200:
                    logger.error(f"Enrollment failed: {response.status_code} {response.text}")
                    return False
                
                data = response.json()
                
                # Salva certificati
                with open(cert_file, "w") as f:
                    f.write(data["certificate"])
                
                with open(key_file, "w") as f:
                    f.write(data["private_key"])
                os.chmod(key_file, 0o600)
                
                with open(ca_file, "w") as f:
                    f.write(data["ca_certificate"])
                
                logger.success("Certificate enrollment successful")
                
                # Aggiorna paths nel ws_client
                self._ws_client.client_cert_path = str(cert_file)
                self._ws_client.client_key_path = str(key_file)
                self._ws_client.ca_cert_path = str(ca_file)
                
                return True
                
        except Exception as e:
            logger.error(f"Enrollment error: {e}")
            return False
    
    async def run(self):
        """Loop principale dell'agent"""
        self._setup_logging()
        
        logger.info("=" * 60)
        logger.info(f"DaDude Agent v{AGENT_VERSION}")
        logger.info("=" * 60)
        
        try:
            self._setup_signal_handlers()
        except Exception:
            # Signal handlers non disponibili (es. Windows)
            pass
        
        await self._initialize_components()
        
        self._running = True
        
        # Prova enrollment certificati
        enrolled = await self._enrollment_if_needed()
        if not enrolled:
            logger.warning("Running without mTLS certificates (token auth only)")
        
        # Avvia componenti background
        await self._store_forward.start()
        await self._scheduler.start()
        
        logger.info("Agent running - waiting for server connection...")
        
        # Loop principale
        try:
            if self._connection_manager:
                await self._connection_manager.start()
            else:
                await self._ws_client.run()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Agent error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown pulito dell'agent"""
        if not self._running:
            return
        
        logger.info("Shutting down agent...")
        self._running = False
        
        # Ferma scheduler
        if self._scheduler:
            await self._scheduler.stop()
        
        # Ferma store & forward
        if self._store_forward:
            await self._store_forward.stop()
        
        # Disconnetti
        if self._connection_manager:
            await self._connection_manager.stop()
        elif self._ws_client:
            await self._ws_client.disconnect()
        
        logger.info("Agent shutdown complete")
        self._shutdown_event.set()
    
    async def get_status(self) -> dict:
        """Ottiene stato corrente dell'agent"""
        import platform
        
        queue_stats = await self._local_queue.get_stats() if self._local_queue else {}
        scheduler_stats = self._scheduler.get_stats() if self._scheduler else {}
        
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "version": AGENT_VERSION,
            "connected": self._ws_client.is_connected if self._ws_client else False,
            "connection_state": self._ws_client.state.value if self._ws_client else "unknown",
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "queue": queue_stats,
            "scheduler": scheduler_stats,
        }


def main():
    """Entry point"""
    agent = DaDudeAgent()
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

