"""
DaDude - Agent Service
Servizio unificato per gestire agent MikroTik e Docker
Supporta sia agent HTTP legacy che WebSocket
"""
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from loguru import logger

from .agent_client import AgentClient, AgentConfig, get_agent_manager
from .mikrotik_service import get_mikrotik_service
from .device_probe_service import MikroTikAgent
from .customer_service import get_customer_service
from .encryption_service import get_encryption_service
from .websocket_hub import get_websocket_hub, CommandType


@dataclass
class AgentProbeResult:
    """Risultato di un probe via agent"""
    success: bool
    target: str
    protocol: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    agent_id: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentService:
    """
    Servizio unificato per gestire probe via agent.
    Supporta sia MikroTik nativo che DaDude Agent Docker.
    """
    
    def __init__(self):
        self._customer_service = get_customer_service()
        self._mikrotik_service = get_mikrotik_service()
        self._agent_manager = get_agent_manager()
        self._encryption = get_encryption_service()
    
    def get_agent_for_customer(
        self,
        customer_id: str,
        network_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Ottiene l'agent appropriato per un cliente/rete.
        Ritorna dict con info agent o None se non trovato.
        """
        agents = self._customer_service.list_agents(customer_id=customer_id)
        
        if not agents:
            return None
        
        # Se network_id specificato, cerca agent assegnato a quella rete
        if network_id:
            for agent in agents:
                if agent.assigned_networks and network_id in agent.assigned_networks:
                    # Ottieni agent completo con password
                    full_agent = self._customer_service.get_agent(agent.id, include_password=True)
                    if full_agent:
                        return self._agent_to_dict(full_agent)
        
        # Altrimenti prendi il primo agent attivo
        for agent in agents:
            if agent.active:
                # Ottieni agent completo con password
                full_agent = self._customer_service.get_agent(agent.id, include_password=True)
                if full_agent:
                    return self._agent_to_dict(full_agent)
        
        return None
    
    def _agent_to_dict(self, agent) -> Dict[str, Any]:
        """Converte agent in dict con password decriptate"""
        result = {
            "id": agent.id,
            "name": agent.name,
            "address": agent.address,
            "port": getattr(agent, 'port', 8728),
            "agent_type": getattr(agent, 'agent_type', 'mikrotik'),
            "username": getattr(agent, 'username', None),
            "use_ssl": getattr(agent, 'use_ssl', False),
            "ssh_port": getattr(agent, 'ssh_port', 22),
            "agent_api_port": getattr(agent, 'agent_api_port', 8080),
            "agent_url": getattr(agent, 'agent_url', None),
            "dns_server": getattr(agent, 'dns_server', None),
            "status": getattr(agent, 'status', 'unknown'),
        }
        
        # Decripta password (potrebbe non esistere in AgentAssignmentSafe)
        password = getattr(agent, 'password', None)
        if password:
            try:
                result["password"] = self._encryption.decrypt(password)
            except:
                result["password"] = password
        else:
            result["password"] = None
        
        # Decripta token agent
        agent_token = getattr(agent, 'agent_token', None)
        if agent_token:
            try:
                result["agent_token"] = self._encryption.decrypt(agent_token)
            except:
                result["agent_token"] = agent_token
        else:
            result["agent_token"] = None
        
        return result
    
    def _get_ws_agent_id(self, agent_info: Dict[str, Any]) -> Optional[str]:
        """
        Cerca l'agent_id WebSocket per un agent.
        Ritorna l'ID se l'agent è connesso via WebSocket, altrimenti None.
        """
        hub = get_websocket_hub()
        agent_name = agent_info.get("name", "")
        
        # Cerca connessione WebSocket che contiene il nome agent
        for conn_id in hub._connections.keys():
            if agent_name and agent_name in conn_id:
                return conn_id
        
        return None
    
    async def _execute_via_websocket(
        self,
        ws_agent_id: str,
        command: CommandType,
        params: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Esegue un comando via WebSocket Hub"""
        hub = get_websocket_hub()
        
        result = await hub.send_command(
            ws_agent_id,
            command,
            params=params,
            timeout=timeout,
        )
        
        if result.status == "success":
            return {
                "success": True,
                "data": result.data,
            }
        else:
            return {
                "success": False,
                "error": result.error or "WebSocket command failed",
            }
    
    def _get_docker_client(self, agent_info: Dict[str, Any]) -> AgentClient:
        """Crea/ottiene client per agent Docker (HTTP legacy)"""
        agent_id = agent_info["id"]
        
        # URL dell'agent
        agent_url = agent_info.get("agent_url")
        if not agent_url:
            address = agent_info["address"]
            port = agent_info.get("agent_api_port", 8080)
            agent_url = f"http://{address}:{port}"
        
        config = AgentConfig(
            agent_id=agent_id,
            agent_url=agent_url,
            agent_token=agent_info.get("agent_token", ""),
            timeout=30,
        )
        
        return self._agent_manager.register_agent(config)
    
    def _get_mikrotik_agent(self, agent_info: Dict[str, Any]) -> MikroTikAgent:
        """Crea oggetto MikroTikAgent per agent MikroTik nativo"""
        return MikroTikAgent(
            address=agent_info["address"],
            username=agent_info.get("username", "admin"),
            password=agent_info.get("password", ""),
            port=agent_info.get("ssh_port", 22),
            api_port=agent_info.get("port", 8728),
            use_ssl=agent_info.get("use_ssl", False),
            dns_server=agent_info.get("dns_server"),
        )
    
    async def probe_wmi(
        self,
        agent_info: Dict[str, Any],
        target: str,
        username: str,
        password: str,
        domain: str = "",
    ) -> AgentProbeResult:
        """
        Esegue probe WMI via agent.
        Solo agent Docker può eseguire WMI.
        Supporta sia WebSocket che HTTP.
        """
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        if agent_type != "docker":
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="wmi",
                error="WMI probe requires Docker agent",
                agent_id=agent_info.get("id"),
            )
        
        try:
            # Prima prova WebSocket
            ws_agent_id = self._get_ws_agent_id(agent_info)
            
            if ws_agent_id:
                logger.info(f"Executing WMI probe via WebSocket to {target}")
                result = await self._execute_via_websocket(
                    ws_agent_id,
                    CommandType.PROBE_WMI,
                    params={
                        "target": target,
                        "username": username,
                        "password": password,
                        "domain": domain,
                    },
                    timeout=120.0,
                )
            else:
                # Fallback a HTTP
                logger.info(f"Executing WMI probe via HTTP to {target}")
                client = self._get_docker_client(agent_info)
                result = await client.probe_wmi(
                    target=target,
                    username=username,
                    password=password,
                    domain=domain,
                )
            
            return AgentProbeResult(
                success=result.get("success", False),
                target=target,
                protocol="wmi",
                data=result.get("data"),
                error=result.get("error"),
                agent_id=agent_info.get("id"),
                duration_ms=result.get("duration_ms"),
            )
        except Exception as e:
            logger.error(f"Agent WMI probe failed: {e}")
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="wmi",
                error=str(e),
                agent_id=agent_info.get("id"),
            )
    
    async def probe_ssh(
        self,
        agent_info: Dict[str, Any],
        target: str,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        port: int = 22,
    ) -> AgentProbeResult:
        """
        Esegue probe SSH via agent.
        Solo agent Docker può eseguire SSH probe.
        Supporta sia WebSocket che HTTP.
        """
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        if agent_type != "docker":
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="ssh",
                error="SSH probe requires Docker agent",
                agent_id=agent_info.get("id"),
            )
        
        try:
            # Prima prova WebSocket
            ws_agent_id = self._get_ws_agent_id(agent_info)
            
            if ws_agent_id:
                logger.info(f"Executing SSH probe via WebSocket to {target}")
                result = await self._execute_via_websocket(
                    ws_agent_id,
                    CommandType.PROBE_SSH,
                    params={
                        "target": target,
                        "username": username,
                        "password": password,
                        "private_key": private_key,
                        "port": port,
                    },
                    timeout=60.0,
                )
            else:
                # Fallback a HTTP
                logger.info(f"Executing SSH probe via HTTP to {target}")
                client = self._get_docker_client(agent_info)
                result = await client.probe_ssh(
                    target=target,
                    username=username,
                    password=password,
                    private_key=private_key,
                    port=port,
                )
            
            return AgentProbeResult(
                success=result.get("success", False),
                target=target,
                protocol="ssh",
                data=result.get("data"),
                error=result.get("error"),
                agent_id=agent_info.get("id"),
                duration_ms=result.get("duration_ms"),
            )
        except Exception as e:
            logger.error(f"Agent SSH probe failed: {e}")
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="ssh",
                error=str(e),
                agent_id=agent_info.get("id"),
            )
    
    async def probe_snmp(
        self,
        agent_info: Dict[str, Any],
        target: str,
        community: str = "public",
        version: str = "2c",
        port: int = 161,
    ) -> AgentProbeResult:
        """
        Esegue probe SNMP via agent.
        Solo agent Docker può eseguire SNMP probe.
        Supporta sia WebSocket che HTTP.
        """
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        if agent_type != "docker":
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="snmp",
                error="SNMP probe requires Docker agent",
                agent_id=agent_info.get("id"),
            )
        
        try:
            # Prima prova WebSocket
            ws_agent_id = self._get_ws_agent_id(agent_info)
            
            if ws_agent_id:
                logger.info(f"Executing SNMP probe via WebSocket to {target}")
                result = await self._execute_via_websocket(
                    ws_agent_id,
                    CommandType.PROBE_SNMP,
                    params={
                        "target": target,
                        "community": community,
                        "version": version,
                        "port": port,
                    },
                    timeout=60.0,
                )
            else:
                # Fallback a HTTP
                logger.info(f"Executing SNMP probe via HTTP to {target}")
                client = self._get_docker_client(agent_info)
                result = await client.probe_snmp(
                    target=target,
                    community=community,
                    version=version,
                    port=port,
                )
            
            return AgentProbeResult(
                success=result.get("success", False),
                target=target,
                protocol="snmp",
                data=result.get("data"),
                error=result.get("error"),
                agent_id=agent_info.get("id"),
                duration_ms=result.get("duration_ms"),
            )
        except Exception as e:
            logger.error(f"Agent SNMP probe failed: {e}")
            return AgentProbeResult(
                success=False,
                target=target,
                protocol="snmp",
                error=str(e),
                agent_id=agent_info.get("id"),
            )
    
    async def scan_ports(
        self,
        agent_info: Dict[str, Any],
        target: str,
        ports: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Esegue port scan via agent.
        Docker: usa API agent (WebSocket o HTTP)
        MikroTik: usa /tool fetch per ogni porta
        """
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        try:
            if agent_type == "docker":
                # Prima prova WebSocket
                ws_agent_id = self._get_ws_agent_id(agent_info)
                
                if ws_agent_id:
                    logger.info(f"Executing port scan via WebSocket to {target}")
                    result = await self._execute_via_websocket(
                        ws_agent_id,
                        CommandType.SCAN_PORTS,
                        params={
                            "target": target,
                            "ports": ports,
                        },
                        timeout=120.0,
                    )
                    if result.get("success"):
                        return {
                            "success": True,
                            "target": target,
                            "open_ports": result.get("data", {}).get("open_ports", []),
                        }
                    return result
                else:
                    # Fallback a HTTP
                    logger.info(f"Executing port scan via HTTP to {target}")
                    client = self._get_docker_client(agent_info)
                    result = await client.scan_ports(target, ports)
                    return result
            else:
                # MikroTik nativo: scan limitato via API
                mikrotik = self._get_mikrotik_agent(agent_info)
                open_ports = await self._scan_ports_mikrotik(mikrotik, target, ports)
                return {
                    "success": True,
                    "target": target,
                    "open_ports": open_ports,
                }
        except Exception as e:
            logger.error(f"Agent port scan failed: {e}")
            return {
                "success": False,
                "target": target,
                "error": str(e),
            }
    
    async def _scan_ports_mikrotik(
        self,
        agent: MikroTikAgent,
        target: str,
        ports: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Scansiona porte via MikroTik (limitato)"""
        from .mikrotik_service import get_mikrotik_service
        
        mikrotik = get_mikrotik_service()
        
        # Porte di default
        if ports is None:
            ports = [22, 80, 443, 3389, 445, 161, 8728]
        
        results = []
        loop = asyncio.get_event_loop()
        
        for port in ports:
            try:
                is_open = await loop.run_in_executor(
                    None,
                    lambda p=port: mikrotik.check_port(
                        agent.address,
                        agent.port,
                        agent.username,
                        agent.password,
                        target,
                        p
                    )
                )
                if is_open:
                    results.append({
                        "port": port,
                        "protocol": "tcp",
                        "open": True,
                    })
            except:
                pass
        
        return results
    
    async def reverse_dns(
        self,
        agent_info: Dict[str, Any],
        targets: List[str],
    ) -> Dict[str, Optional[str]]:
        """
        Esegue reverse DNS via agent.
        Docker: usa API agent
        MikroTik: usa /resolve
        """
        agent_type = agent_info.get("agent_type", "mikrotik")
        dns_server = agent_info.get("dns_server")
        
        try:
            if agent_type == "docker":
                client = self._get_docker_client(agent_info)
                result = await client.dns_reverse(targets, dns_server)
                return result.get("results", {})
            else:
                # MikroTik nativo
                mikrotik = self._get_mikrotik_agent(agent_info)
                return await self._reverse_dns_mikrotik(mikrotik, targets)
        except Exception as e:
            logger.error(f"Agent DNS reverse failed: {e}")
            return {}
    
    async def _reverse_dns_mikrotik(
        self,
        agent: MikroTikAgent,
        targets: List[str],
    ) -> Dict[str, Optional[str]]:
        """Esegue reverse DNS via MikroTik"""
        from .mikrotik_service import get_mikrotik_service
        
        mikrotik = get_mikrotik_service()
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            None,
            lambda: mikrotik.batch_reverse_dns_lookup(
                agent.address,
                agent.port,
                agent.username,
                agent.password,
                targets,
                agent.dns_server,
            )
        )
    
    async def check_agent_health(self, agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Verifica stato agent"""
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        try:
            if agent_type == "docker":
                client = self._get_docker_client(agent_info)
                return await client.health_check()
            else:
                # MikroTik: verifica connessione API
                mikrotik = self._get_mikrotik_agent(agent_info)
                loop = asyncio.get_event_loop()
                
                from .mikrotik_service import get_mikrotik_service
                svc = get_mikrotik_service()
                
                info = await loop.run_in_executor(
                    None,
                    lambda: svc.get_system_info(
                        mikrotik.address,
                        mikrotik.api_port,
                        mikrotik.username,
                        mikrotik.password,
                        mikrotik.use_ssl,
                    )
                )
                
                if info:
                    return {
                        "status": "healthy",
                        "agent_type": "mikrotik",
                        "version": info.get("version"),
                        "board_name": info.get("board_name"),
                    }
                else:
                    return {"status": "error", "error": "Connection failed"}
                    
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def auto_probe(
        self,
        agent_info: Dict[str, Any],
        target: str,
        open_ports: List[Dict[str, Any]],
        credentials: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Esegue auto-probe basato su porte aperte.
        Prova WMI, SNMP, SSH in ordine di priorità.
        """
        results = {
            "target": target,
            "probes": [],
            "best_result": None,
        }
        
        agent_type = agent_info.get("agent_type", "mikrotik")
        
        # Solo Docker agent può fare probe avanzati
        if agent_type != "docker":
            results["error"] = "Advanced probing requires Docker agent"
            return results
        
        # Determina quali probe fare
        open_port_nums = {p.get("port") for p in open_ports if p.get("open")}
        
        # Ordine priorità: WMI (più info), SNMP, SSH
        probe_order = []
        
        # Windows ports
        if open_port_nums & {3389, 445, 139, 135, 5985}:
            for cred in credentials:
                if cred.get("type") == "wmi":
                    probe_order.append(("wmi", cred))
                    break
        
        # SNMP
        if 161 in open_port_nums:
            for cred in credentials:
                if cred.get("type") == "snmp":
                    probe_order.append(("snmp", cred))
                    break
        
        # SSH
        if 22 in open_port_nums:
            for cred in credentials:
                if cred.get("type") == "ssh":
                    probe_order.append(("ssh", cred))
                    break
        
        # Esegui probe
        for probe_type, cred in probe_order:
            try:
                if probe_type == "wmi":
                    result = await self.probe_wmi(
                        agent_info,
                        target,
                        cred.get("username", ""),
                        cred.get("password", ""),
                        cred.get("wmi_domain", ""),
                    )
                elif probe_type == "snmp":
                    result = await self.probe_snmp(
                        agent_info,
                        target,
                        cred.get("snmp_community", "public"),
                        cred.get("snmp_version", "2c"),
                        cred.get("snmp_port", 161),
                    )
                elif probe_type == "ssh":
                    result = await self.probe_ssh(
                        agent_info,
                        target,
                        cred.get("username", ""),
                        cred.get("password"),
                        cred.get("ssh_private_key"),
                        cred.get("ssh_port", 22),
                    )
                else:
                    continue
                
                results["probes"].append({
                    "type": probe_type,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                })
                
                if result.success and not results["best_result"]:
                    results["best_result"] = {
                        "type": probe_type,
                        "data": result.data,
                    }
                    
            except Exception as e:
                results["probes"].append({
                    "type": probe_type,
                    "success": False,
                    "error": str(e),
                })
        
        return results


# Singleton
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service

