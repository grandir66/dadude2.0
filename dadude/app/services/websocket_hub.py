"""
DaDude - WebSocket Hub
Gestisce connessioni WebSocket bidirezionali con agent remoti (mTLS)
"""
import asyncio
import json
import ssl
import uuid
from datetime import datetime
from typing import Dict, Optional, Any, Callable, Awaitable, Set
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from .pki_service import get_pki_service


class MessageType(str, Enum):
    """Tipi di messaggio WebSocket"""
    # Agent -> Server
    HEARTBEAT = "heartbeat"
    RESULT = "result"
    LOG = "log"
    METRICS = "metrics"
    
    # Server -> Agent
    COMMAND = "command"
    CONFIG_UPDATE = "config_update"
    ACK = "ack"


class CommandType(str, Enum):
    """Tipi di comandi server -> agent"""
    SCAN_NETWORK = "scan_network"
    PROBE_WMI = "probe_wmi"
    PROBE_SSH = "probe_ssh"
    PROBE_SNMP = "probe_snmp"
    PORT_SCAN = "port_scan"
    SCAN_PORTS = "port_scan"  # Alias per compatibilità
    DNS_REVERSE = "dns_reverse"
    GET_ARP_TABLE = "get_arp_table"  # Query ARP da MikroTik o SNMP
    UPDATE_AGENT = "update_agent"
    RESTART = "restart"
    REBOOT = "reboot"
    GET_STATUS = "get_status"
    EXEC_COMMAND = "exec_command"  # Esegui comando locale sull'agent
    EXEC_SSH = "exec_ssh"  # Esegui comando su host remoto via SSH


@dataclass
class AgentConnection:
    """Rappresenta una connessione agent attiva"""
    agent_id: str
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    ip_address: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    pending_commands: Dict[str, asyncio.Future] = field(default_factory=dict)
    

@dataclass
class Command:
    """Comando da inviare all'agent"""
    id: str
    action: CommandType
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 300.0  # 5 minuti default
    
    def to_dict(self) -> dict:
        return {
            "type": MessageType.COMMAND.value,
            "id": self.id,
            "action": self.action.value if isinstance(self.action, CommandType) else self.action,
            "params": self.params,
        }


@dataclass
class CommandResult:
    """Risultato di un comando"""
    command_id: str
    status: str  # success, error, timeout
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentWebSocketHub:
    """
    Hub centrale per gestire connessioni WebSocket con agent.
    Supporta mTLS per autenticazione.
    """
    
    def __init__(self):
        self._connections: Dict[str, AgentConnection] = {}
        self._command_handlers: Dict[str, Callable] = {}
        self._heartbeat_timeout = 60  # secondi
        self._cleanup_task: Optional[asyncio.Task] = None
        self._event_handlers: Dict[str, Set[Callable]] = {}
    
    async def start(self):
        """Avvia task di background"""
        self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
        logger.info("WebSocket Hub started")
    
    async def stop(self):
        """Ferma hub e disconnette tutti gli agent"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Chiudi tutte le connessioni
        for agent_id in list(self._connections.keys()):
            await self.disconnect(agent_id)
        
        logger.info("WebSocket Hub stopped")
    
    async def handle_connection(self, websocket: WebSocket, agent_id: str):
        """
        Gestisce una nuova connessione WebSocket da un agent.
        
        Args:
            websocket: Connessione WebSocket FastAPI
            agent_id: ID agent (estratto dal certificato client o header)
        """
        # Verifica se c'è già una connessione per questo agent
        if agent_id in self._connections:
            old_conn = self._connections[agent_id]
            logger.warning(f"Agent {agent_id} reconnecting, closing old connection")
            try:
                await old_conn.websocket.close(code=1000, reason="New connection")
            except Exception:
                pass
        
        # Accetta connessione
        await websocket.accept()
        
        # Estrai info client
        client_ip = None
        if hasattr(websocket, 'client') and websocket.client:
            client_ip = websocket.client.host
        
        # Crea record connessione
        connection = AgentConnection(
            agent_id=agent_id,
            websocket=websocket,
            ip_address=client_ip,
        )
        self._connections[agent_id] = connection
        
        logger.info(f"Agent connected: {agent_id} from {client_ip}")
        await self._emit_event("agent_connected", agent_id, connection)
        
        try:
            # Loop ricezione messaggi
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_message(connection, message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from {agent_id}: {e}")
                    await self._send_error(connection, "Invalid JSON")
        
        except WebSocketDisconnect:
            logger.info(f"Agent disconnected: {agent_id}")
        except Exception as e:
            logger.error(f"Error handling agent {agent_id}: {e}")
        finally:
            await self._handle_disconnect(agent_id)
    
    async def _handle_message(self, connection: AgentConnection, message: dict):
        """Gestisce messaggio ricevuto da agent"""
        msg_type = message.get("type")
        
        if msg_type == MessageType.HEARTBEAT.value:
            await self._handle_heartbeat(connection, message)
        
        elif msg_type == MessageType.RESULT.value:
            await self._handle_result(connection, message)
        
        elif msg_type == MessageType.LOG.value:
            await self._handle_log(connection, message)
        
        elif msg_type == MessageType.METRICS.value:
            await self._handle_metrics(connection, message)
        
        else:
            logger.warning(f"Unknown message type from {connection.agent_id}: {msg_type}")
    
    async def _handle_heartbeat(self, connection: AgentConnection, message: dict):
        """Gestisce heartbeat da agent"""
        connection.last_heartbeat = datetime.utcnow()
        connection.version = message.get("version")
        connection.metrics = message.get("metrics", {})
        
        # Invia ACK
        await self._send(connection, {
            "type": MessageType.ACK.value,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        await self._emit_event("heartbeat", connection.agent_id, message)
    
    async def _handle_result(self, connection: AgentConnection, message: dict):
        """Gestisce risultato comando da agent"""
        command_id = message.get("task_id") or message.get("command_id")
        
        if command_id in connection.pending_commands:
            future = connection.pending_commands.pop(command_id)
            result = CommandResult(
                command_id=command_id,
                status=message.get("status", "unknown"),
                data=message.get("data"),
                error=message.get("error"),
            )
            if not future.done():
                future.set_result(result)
        else:
            logger.warning(f"Received result for unknown command: {command_id}")
        
        await self._emit_event("result", connection.agent_id, message)
    
    async def _handle_log(self, connection: AgentConnection, message: dict):
        """Gestisce log da agent"""
        level = message.get("level", "INFO")
        log_message = message.get("message", "")
        logger.log(level, f"[Agent {connection.agent_id}] {log_message}")
        
        await self._emit_event("log", connection.agent_id, message)
    
    async def _handle_metrics(self, connection: AgentConnection, message: dict):
        """Gestisce metriche da agent"""
        connection.metrics = message.get("metrics", {})
        await self._emit_event("metrics", connection.agent_id, message)
    
    async def _handle_disconnect(self, agent_id: str):
        """Gestisce disconnessione agent"""
        if agent_id in self._connections:
            connection = self._connections.pop(agent_id)
            
            # Cancella comandi pendenti
            for command_id, future in connection.pending_commands.items():
                if not future.done():
                    future.set_exception(ConnectionError("Agent disconnected"))
            
            await self._emit_event("agent_disconnected", agent_id, None)
    
    async def disconnect(self, agent_id: str):
        """Disconnette un agent"""
        if agent_id in self._connections:
            connection = self._connections[agent_id]
            try:
                await connection.websocket.close(code=1000)
            except Exception:
                pass
            await self._handle_disconnect(agent_id)
    
    async def send_command(
        self,
        agent_id: str,
        action: CommandType,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 300.0
    ) -> CommandResult:
        """
        Invia comando a un agent e attende risposta.
        
        Args:
            agent_id: ID dell'agent destinatario
            action: Tipo di comando
            params: Parametri del comando
            timeout: Timeout in secondi
            
        Returns:
            CommandResult con stato e dati risposta
            
        Raises:
            ConnectionError: Se agent non connesso
            asyncio.TimeoutError: Se timeout scade
        """
        if agent_id not in self._connections:
            raise ConnectionError(f"Agent {agent_id} not connected")
        
        connection = self._connections[agent_id]
        
        # Crea comando
        command = Command(
            id=str(uuid.uuid4()),
            action=action,
            params=params or {},
            timeout=timeout,
        )
        
        # Crea future per risposta
        future: asyncio.Future[CommandResult] = asyncio.Future()
        connection.pending_commands[command.id] = future
        
        try:
            # Invia comando
            await self._send(connection, command.to_dict())
            
            # Attendi risposta
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            connection.pending_commands.pop(command.id, None)
            return CommandResult(
                command_id=command.id,
                status="timeout",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            connection.pending_commands.pop(command.id, None)
            return CommandResult(
                command_id=command.id,
                status="error",
                error=str(e),
            )
    
    async def broadcast_command(
        self,
        action: CommandType,
        params: Optional[Dict[str, Any]] = None,
        agent_ids: Optional[list] = None
    ) -> Dict[str, CommandResult]:
        """
        Invia comando a più agent in parallelo.
        
        Args:
            action: Tipo di comando
            params: Parametri
            agent_ids: Lista agent (None = tutti)
            
        Returns:
            Dict agent_id -> CommandResult
        """
        targets = agent_ids or list(self._connections.keys())
        
        tasks = [
            self.send_command(aid, action, params)
            for aid in targets
            if aid in self._connections
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            aid: (r if isinstance(r, CommandResult) else CommandResult(
                command_id="",
                status="error",
                error=str(r)
            ))
            for aid, r in zip(targets, results)
        }
    
    async def _send(self, connection: AgentConnection, message: dict):
        """Invia messaggio a agent"""
        try:
            await connection.websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending to {connection.agent_id}: {e}")
            raise
    
    async def _send_error(self, connection: AgentConnection, error: str):
        """Invia messaggio di errore"""
        await self._send(connection, {
            "type": "error",
            "message": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    async def _cleanup_stale_connections(self):
        """Task background per cleanup connessioni stale"""
        while True:
            try:
                await asyncio.sleep(30)  # Check ogni 30 secondi
                
                now = datetime.utcnow()
                stale_agents = []
                
                for agent_id, conn in self._connections.items():
                    elapsed = (now - conn.last_heartbeat).total_seconds()
                    if elapsed > self._heartbeat_timeout * 2:
                        stale_agents.append(agent_id)
                
                for agent_id in stale_agents:
                    logger.warning(f"Removing stale agent: {agent_id}")
                    await self.disconnect(agent_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    # Event system
    def on_event(self, event: str, handler: Callable[[str, Any], Awaitable[None]]):
        """Registra handler per evento"""
        if event not in self._event_handlers:
            self._event_handlers[event] = set()
        self._event_handlers[event].add(handler)
    
    def off_event(self, event: str, handler: Callable):
        """Rimuove handler per evento"""
        if event in self._event_handlers:
            self._event_handlers[event].discard(handler)
    
    async def _emit_event(self, event: str, agent_id: str, data: Any):
        """Emette evento agli handler registrati"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    await handler(agent_id, data)
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")
    
    # Query methods
    def get_connected_agents(self) -> list:
        """Lista agent connessi"""
        return [
            {
                "agent_id": conn.agent_id,
                "connected_at": conn.connected_at.isoformat(),
                "last_heartbeat": conn.last_heartbeat.isoformat(),
                "version": conn.version,
                "ip_address": conn.ip_address,
                "metrics": conn.metrics,
            }
            for conn in self._connections.values()
        ]
    
    def is_connected(self, agent_id: str) -> bool:
        """Verifica se agent è connesso"""
        return agent_id in self._connections
    
    def get_connection(self, agent_id: str) -> Optional[AgentConnection]:
        """Ottiene connessione agent"""
        return self._connections.get(agent_id)
    
    @property
    def connected_count(self) -> int:
        """Numero agent connessi"""
        return len(self._connections)


# Singleton
_hub: Optional[AgentWebSocketHub] = None


def get_websocket_hub() -> AgentWebSocketHub:
    """Ottiene istanza singleton del WebSocket Hub"""
    global _hub
    if _hub is None:
        _hub = AgentWebSocketHub()
    return _hub


def create_ssl_context_for_mtls(
    server_cert_path: str,
    server_key_path: str,
    ca_cert_path: str
) -> ssl.SSLContext:
    """
    Crea SSL context per server con mTLS.
    
    Args:
        server_cert_path: Path certificato server
        server_key_path: Path chiave privata server  
        ca_cert_path: Path certificato CA per verifica client
        
    Returns:
        ssl.SSLContext configurato per mTLS
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(server_cert_path, server_key_path)
    context.load_verify_locations(ca_cert_path)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False  # Client non ha hostname
    return context

