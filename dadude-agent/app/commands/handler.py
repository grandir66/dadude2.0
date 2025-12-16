"""
DaDude Agent - Command Handler
Gestisce comandi ricevuti dal server via WebSocket
"""
import asyncio
import os
import subprocess
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from loguru import logger


class CommandAction(str, Enum):
    """Azioni comando supportate"""
    # Network scanning
    SCAN_NETWORK = "scan_network"
    PORT_SCAN = "port_scan"
    DNS_REVERSE = "dns_reverse"
    
    # Device probing
    PROBE_WMI = "probe_wmi"
    PROBE_SSH = "probe_ssh"
    PROBE_SNMP = "probe_snmp"
    
    # ARP table lookup (MikroTik API o SNMP)
    GET_ARP_TABLE = "get_arp_table"
    
    # Agent management
    UPDATE_AGENT = "update_agent"
    RESTART = "restart"
    REBOOT = "reboot"
    GET_STATUS = "get_status"
    GET_CONFIG = "get_config"
    SET_CONFIG = "set_config"
    
    # Scheduled tasks
    DAILY_RESTART = "daily_restart"
    CONNECTION_WATCHDOG = "connection_watchdog"
    CLEANUP_QUEUE = "cleanup_queue"
    CHECK_UPDATES = "check_updates"
    
    # Diagnostics
    PING = "ping"
    TRACEROUTE = "traceroute"
    NMAP_SCAN = "nmap_scan"
    
    # Remote shell
    EXEC_COMMAND = "exec_command"
    EXEC_SSH = "exec_ssh"


@dataclass
class CommandResult:
    """Risultato esecuzione comando"""
    success: bool
    status: str  # "success", "error", "timeout", "cancelled"
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class CommandHandler:
    """
    Handler per comandi dal server.
    Esegue probe, scan e operazioni di gestione.
    """
    
    def __init__(self):
        # Import probe modules
        from ..probes import wmi_probe, ssh_probe, snmp_probe
        from ..scanners import port_scanner, dns_resolver
        
        self._wmi_probe = wmi_probe
        self._ssh_probe = ssh_probe
        self._snmp_probe = snmp_probe
        self._port_scanner = port_scanner
        self._dns_resolver = dns_resolver
        
        # Custom handlers
        self._custom_handlers: Dict[str, Callable[[Dict], Awaitable[CommandResult]]] = {}
        
        # Update callback (per self-update)
        self._update_callback: Optional[Callable[[str, str], Awaitable[bool]]] = None
    
    async def handle(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gestisce comando e ritorna risultato.
        
        Args:
            command: Dict con id, action, params
            
        Returns:
            Dict con status, data, error
        """
        action = command.get("action", "")
        params = command.get("params", {})
        command_id = command.get("id", "unknown")
        
        start_time = datetime.utcnow()
        
        logger.info(f"Executing command: {action} (id={command_id})")
        
        try:
            result = await self._execute_action(action, params)
            
        except asyncio.TimeoutError:
            result = CommandResult(
                success=False,
                status="timeout",
                error="Command execution timed out",
            )
        except asyncio.CancelledError:
            result = CommandResult(
                success=False,
                status="cancelled",
                error="Command was cancelled",
            )
        except Exception as e:
            logger.error(f"Command error: {e}")
            result = CommandResult(
                success=False,
                status="error",
                error=str(e),
            )
        
        # Calcola tempo esecuzione
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.execution_time_ms = int(execution_time)
        
        return result.to_dict()
    
    async def _execute_action(self, action: str, params: Dict) -> CommandResult:
        """Esegue azione specifica"""
        
        # Check custom handlers first
        if action in self._custom_handlers:
            return await self._custom_handlers[action](params)
        
        # Network scanning
        if action == CommandAction.SCAN_NETWORK.value:
            return await self._scan_network(params)
        
        elif action == CommandAction.PORT_SCAN.value:
            return await self._port_scan(params)
        
        elif action == CommandAction.DNS_REVERSE.value:
            return await self._dns_reverse(params)
        
        # Device probing
        elif action == CommandAction.PROBE_WMI.value:
            return await self._probe_wmi(params)
        
        elif action == CommandAction.PROBE_SSH.value:
            return await self._probe_ssh(params)
        
        elif action == CommandAction.PROBE_SNMP.value:
            return await self._probe_snmp(params)
        
        elif action == CommandAction.GET_ARP_TABLE.value:
            return await self._get_arp_table(params)
        
        # Agent management
        elif action == CommandAction.UPDATE_AGENT.value:
            return await self._update_agent(params)
        
        elif action == CommandAction.RESTART.value:
            return await self._restart()
        
        elif action == CommandAction.REBOOT.value:
            return await self._reboot()
        
        elif action == CommandAction.GET_STATUS.value:
            return await self._get_status()
        
        # Diagnostics
        elif action == CommandAction.PING.value:
            return await self._ping(params)
        
        elif action == CommandAction.NMAP_SCAN.value:
            return await self._nmap_scan(params)
        
        # Scheduled tasks
        elif action == CommandAction.DAILY_RESTART.value:
            return await self._daily_restart(params)
        
        elif action == CommandAction.CONNECTION_WATCHDOG.value:
            return await self._connection_watchdog(params)
        
        elif action == CommandAction.CLEANUP_QUEUE.value:
            return await self._cleanup_queue(params)
        
        elif action == CommandAction.CHECK_UPDATES.value:
            return await self._check_updates(params)
        
        # Remote shell
        elif action == CommandAction.EXEC_COMMAND.value:
            return await self._exec_command(params)
        
        elif action == CommandAction.EXEC_SSH.value:
            return await self._exec_ssh(params)
        
        else:
            return CommandResult(
                success=False,
                status="error",
                error=f"Unknown action: {action}",
            )
    
    # ==========================================
    # NETWORK SCANNING
    # ==========================================
    
    async def _scan_network(self, params: Dict) -> CommandResult:
        """Scansione rete"""
        network = params.get("network")
        scan_type = params.get("scan_type", "ping")
        
        if not network:
            return CommandResult(success=False, status="error", error="Missing 'network' parameter")
        
        try:
            # Usa nmap se disponibile
            if self._is_nmap_available():
                result = await self._nmap_network_scan(network, scan_type)
            else:
                # Fallback a scan ping base
                result = await self._basic_ping_scan(network)
            
            return CommandResult(
                success=True,
                status="success",
                data={"hosts": result},
            )
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _port_scan(self, params: Dict) -> CommandResult:
        """Scansione porte"""
        target = params.get("target")
        ports = params.get("ports")
        timeout = params.get("timeout", 1.0)
        
        if not target:
            return CommandResult(success=False, status="error", error="Missing 'target' parameter")
        
        try:
            result = await asyncio.to_thread(
                self._port_scanner.scan_ports,
                target, ports, timeout
            )
            return CommandResult(success=True, status="success", data=result)
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _dns_reverse(self, params: Dict) -> CommandResult:
        """Reverse DNS lookup"""
        targets = params.get("targets", [])
        dns_server = params.get("dns_server")
        
        if not targets:
            return CommandResult(success=False, status="error", error="Missing 'targets' parameter")
        
        try:
            result = await asyncio.to_thread(
                self._dns_resolver.reverse_lookup_batch,
                targets, dns_server
            )
            return CommandResult(success=True, status="success", data={"results": result})
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    # ==========================================
    # DEVICE PROBING
    # ==========================================
    
    async def _probe_wmi(self, params: Dict) -> CommandResult:
        """Probe WMI"""
        target = params.get("target")
        username = params.get("username")
        password = params.get("password")
        domain = params.get("domain") or ""  # Handle None explicitly
        
        if not all([target, username, password]):
            return CommandResult(
                success=False, 
                status="error", 
                error="Missing required parameters: target, username, password"
            )
        
        try:
            logger.info(f"WMI probe: target={target}, user={domain}\\{username if domain else username}")
            # wmi_probe.probe è già async, chiamalo direttamente
            result = await self._wmi_probe.probe(
                target, username, password, domain
            )
            logger.info(f"WMI probe result: {len(result) if result else 0} fields")
            return CommandResult(success=True, status="success", data=result)
        except Exception as e:
            import traceback
            logger.error(f"WMI probe error: {e}")
            logger.error(traceback.format_exc())
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _probe_ssh(self, params: Dict) -> CommandResult:
        """Probe SSH"""
        target = params.get("target")
        username = params.get("username")
        password = params.get("password")
        private_key = params.get("private_key")
        port = params.get("port", 22)
        
        if not target or not username:
            return CommandResult(
                success=False,
                status="error",
                error="Missing required parameters: target, username"
            )
        
        if not password and not private_key:
            return CommandResult(
                success=False,
                status="error",
                error="Either password or private_key required"
            )
        
        try:
            # ssh_probe.probe è già async, chiamalo direttamente
            result = await self._ssh_probe.probe(
                target, username, password, private_key, port
            )
            return CommandResult(success=True, status="success", data=result)
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _probe_snmp(self, params: Dict) -> CommandResult:
        """Probe SNMP"""
        target = params.get("target")
        community = params.get("community", "public")
        version = params.get("version", "2c")
        port = params.get("port", 161)
        
        if not target:
            return CommandResult(success=False, status="error", error="Missing 'target' parameter")
        
        try:
            # snmp_probe.probe è già async, chiamalo direttamente
            result = await self._snmp_probe.probe(
                target, community, version, port
            )
            return CommandResult(success=True, status="success", data=result)
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _get_arp_table(self, params: Dict) -> CommandResult:
        """
        Ottiene tabella ARP da un gateway (MikroTik API o SNMP generico).
        
        Params:
            method: "mikrotik" o "snmp"
            network_cidr: es. "192.168.1.0/24" per filtrare
            
            Per MikroTik:
                address, port, username, password, use_ssl
                
            Per SNMP:
                address, community, version (1, 2c)
        """
        method = params.get("method", "mikrotik")
        network_cidr = params.get("network_cidr")
        
        if method == "mikrotik":
            return await self._get_arp_mikrotik(params, network_cidr)
        elif method == "snmp":
            return await self._get_arp_snmp(params, network_cidr)
        else:
            return CommandResult(
                success=False, 
                status="error", 
                error=f"Unknown method: {method}. Use 'mikrotik' or 'snmp'"
            )
    
    async def _get_arp_mikrotik(self, params: Dict, network_cidr: str = None) -> CommandResult:
        """Query ARP table via MikroTik RouterOS API"""
        import ipaddress
        
        address = params.get("address")
        port = params.get("port", 8728)
        username = params.get("username", "admin")
        password = params.get("password", "")
        use_ssl = params.get("use_ssl", False)
        
        if not address:
            return CommandResult(success=False, status="error", error="Missing 'address' parameter")
        
        try:
            import routeros_api
            
            loop = asyncio.get_event_loop()
            
            def connect_and_get_arp():
                # Connessione MikroTik
                connection = routeros_api.RouterOsApiPool(
                    address,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl,
                    ssl_verify=False,
                    plaintext_login=True,
                )
                api = connection.get_api()
                
                # Ottieni ARP table
                arp_resource = api.get_resource('/ip/arp')
                arps = arp_resource.get()
                
                connection.disconnect()
                return arps
            
            arps = await loop.run_in_executor(None, connect_and_get_arp)
            
            # Filtra per network se specificato
            entries = []
            net = None
            if network_cidr:
                try:
                    net = ipaddress.ip_network(network_cidr, strict=False)
                except:
                    pass
            
            for a in arps:
                ip = a.get("address", "")
                mac = a.get("mac-address", "")
                
                if not ip or not mac:
                    continue
                    
                # Filtra per network
                if net:
                    try:
                        if ipaddress.ip_address(ip) not in net:
                            continue
                    except:
                        continue
                
                entries.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": a.get("interface", ""),
                })
            
            logger.info(f"[ARP MikroTik] Got {len(entries)} entries from {address}")
            return CommandResult(
                success=True, 
                status="success", 
                data={"entries": entries, "count": len(entries), "source": f"mikrotik:{address}"}
            )
            
        except Exception as e:
            logger.error(f"[ARP MikroTik] Error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _get_arp_snmp(self, params: Dict, network_cidr: str = None) -> CommandResult:
        """Query ARP table via SNMP (generic router) - pysnmp 7.x async API"""
        import ipaddress
        
        address = params.get("address")
        community = params.get("community", "public")
        version = params.get("version", "2c")
        
        if not address:
            return CommandResult(success=False, status="error", error="Missing 'address' parameter")
        
        try:
            # pysnmp 7.x usa v3arch con API async
            from pysnmp.hlapi.v3arch import (
                SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
                ObjectType, ObjectIdentity, walk_cmd
            )
            
            # OID per ipNetToMediaPhysAddress (ARP table)
            OID_ARP_TABLE = "1.3.6.1.2.1.4.22.1.2"
            
            # Parse network filter
            net = None
            if network_cidr:
                try:
                    net = ipaddress.ip_network(network_cidr, strict=False)
                except:
                    pass
            
            mp_model = 1 if version == "2c" else 0
            
            # Crea transport target (async in pysnmp 7.x)
            logger.debug(f"[ARP SNMP] Querying {address} with community {community}")
            transport = await UdpTransportTarget.create((address, 161), timeout=5, retries=2)
            
            entries = []
            
            # Walk ARP table - async iterator in pysnmp 7.x
            async for (errorIndication, errorStatus, errorIndex, varBinds) in walk_cmd(
                SnmpEngine(),
                CommunityData(community, mpModel=mp_model),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(OID_ARP_TABLE)),
            ):
                if errorIndication:
                    logger.debug(f"[ARP SNMP] Error: {errorIndication}")
                    break
                if errorStatus:
                    logger.debug(f"[ARP SNMP] Status error: {errorStatus.prettyPrint()}")
                    break
                
                for varBind in varBinds:
                    oid = str(varBind[0])
                    value = varBind[1]
                    
                    # Debug: log raw values
                    logger.debug(f"[ARP SNMP] OID: {oid}, Value type: {type(value).__name__}, Value: {value}")
                    
                    # Estrai IP dall'OID
                    # OID format: 1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ip1>.<ip2>.<ip3>.<ip4>
                    try:
                        parts = oid.split('.')
                        # L'OID base è 1.3.6.1.2.1.4.22.1.2 (10 parti), poi ifIndex (1), poi IP (4)
                        # Quindi le ultime 4 parti sono l'IP
                        if len(parts) >= 4:
                            ip = '.'.join(parts[-4:])
                            
                            # Verifica che sia un IP valido
                            try:
                                ipaddress.ip_address(ip)
                            except:
                                logger.debug(f"[ARP SNMP] Invalid IP from OID: {ip}")
                                continue
                            
                            # Estrai MAC address dal valore
                            mac = None
                            
                            # Metodo 1: asOctets() per OctetString
                            if hasattr(value, 'asOctets'):
                                try:
                                    mac_bytes = value.asOctets()
                                    if len(mac_bytes) == 6:
                                        mac = ':'.join(format(b, '02X') for b in mac_bytes)
                                except:
                                    pass
                            
                            # Metodo 2: hasValue e __bytes__
                            if not mac and hasattr(value, '__bytes__'):
                                try:
                                    mac_bytes = bytes(value)
                                    if len(mac_bytes) == 6:
                                        mac = ':'.join(format(b, '02X') for b in mac_bytes)
                                except:
                                    pass
                            
                            # Metodo 3: prettyPrint per format 0x...
                            if not mac and hasattr(value, 'prettyPrint'):
                                try:
                                    pretty = value.prettyPrint()
                                    # Format: "0xAABBCCDDEEFF" o "AA:BB:CC:DD:EE:FF"
                                    if pretty.startswith('0x'):
                                        hex_str = pretty[2:].upper()
                                        if len(hex_str) == 12:
                                            mac = ':'.join(hex_str[i:i+2] for i in range(0, 12, 2))
                                    elif ':' in pretty and len(pretty) == 17:
                                        mac = pretty.upper()
                                except:
                                    pass
                            
                            # Metodo 4: raw string
                            if not mac:
                                try:
                                    raw = str(value)
                                    # Potrebbe essere in formato hex senza 0x
                                    clean = raw.replace(':', '').replace('-', '').replace(' ', '').upper()
                                    if len(clean) == 12 and all(c in '0123456789ABCDEF' for c in clean):
                                        mac = ':'.join(clean[i:i+2] for i in range(0, 12, 2))
                                except:
                                    pass
                            
                            if not mac:
                                logger.debug(f"[ARP SNMP] Could not parse MAC for IP {ip}: {value} (type: {type(value).__name__})")
                                continue
                            
                            # Ignora MAC invalidi
                            if mac in ["00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"]:
                                continue
                            
                            # Filtra per network se specificato
                            if net:
                                try:
                                    if ipaddress.ip_address(ip) not in net:
                                        continue
                                except:
                                    continue
                            
                            logger.debug(f"[ARP SNMP] Found: {ip} -> {mac}")
                            entries.append({"ip": ip, "mac": mac})
                    except Exception as e:
                        logger.debug(f"[ARP SNMP] Parse error: {e}")
                        continue
            
            logger.info(f"[ARP SNMP] Got {len(entries)} entries from {address}")
            return CommandResult(
                success=True, 
                status="success", 
                data={"entries": entries, "count": len(entries), "source": f"snmp:{address}"}
            )
            
        except Exception as e:
            logger.error(f"[ARP SNMP] Error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    # ==========================================
    # AGENT MANAGEMENT
    # ==========================================
    
    async def _update_agent(self, params: Dict) -> CommandResult:
        """
        Self-update agent.
        Per agent Docker WebSocket, esegue git pull nella directory montata.
        Il restart deve essere fatto manualmente perché il container non può
        riavviarsi in modo affidabile da solo.
        """
        logger.info("Update agent requested")
        
        agent_dir = "/opt/dadude-agent"
        
        try:
            import shutil
            
            # Prova git fetch + reset (più robusto con file locali)
            if os.path.exists(os.path.join(agent_dir, ".git")):
                logger.info("Fetching latest code...")
                
                # Fetch
                fetch_result = subprocess.run(
                    ["git", "fetch", "origin", "main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if fetch_result.returncode != 0:
                    logger.warning(f"Git fetch failed: {fetch_result.stderr}")
                    return CommandResult(
                        success=False,
                        status="error",
                        error=f"Git fetch failed: {fetch_result.stderr[:200]}",
                    )
                
                # Reset hard to origin/main (ignora modifiche locali)
                logger.info("Resetting to origin/main...")
                result = subprocess.run(
                    ["git", "reset", "--hard", "origin/main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    logger.warning(f"Git reset failed: {result.stderr}")
                    return CommandResult(
                        success=False,
                        status="error",
                        error=f"Git reset failed: {result.stderr[:200]}",
                    )
                else:
                    logger.info(f"Git update success: {result.stdout}")
                    
                    # Copia app files se struttura diversa
                    src_app = os.path.join(agent_dir, "dadude-agent", "app")
                    if os.path.exists(src_app):
                        dst_app = os.path.join(agent_dir, "app")
                        if os.path.exists(dst_app):
                            shutil.rmtree(dst_app)
                        shutil.copytree(src_app, dst_app)
                        logger.info("Copied app files to correct location")
            else:
                logger.warning("Directory is not a git repo")
                return CommandResult(
                    success=False,
                    status="error",
                    error="Agent directory is not a git repository",
                )
            
            # Rebuild e restart Docker container
            # Cerca docker-compose.yml prima nel root, poi in dadude-agent/
            agent_compose_dir = agent_dir
            if not os.path.exists(os.path.join(agent_compose_dir, "docker-compose.yml")):
                agent_compose_dir = os.path.join(agent_dir, "dadude-agent")
            
            if os.path.exists(os.path.join(agent_compose_dir, "docker-compose.yml")):
                logger.info("Rebuilding Docker image...")
                
                # Build
                build_result = subprocess.run(
                    ["docker", "compose", "build", "--quiet"],
                    cwd=agent_compose_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if build_result.returncode != 0:
                    logger.warning(f"Docker build failed: {build_result.stderr}")
                    return CommandResult(
                        success=True,
                        status="success",
                        data={
                            "message": f"Git pull OK, but Docker build failed. Manual rebuild required.",
                            "needs_restart": True,
                            "build_error": build_result.stderr[:200],
                        },
                    )
                
                logger.info("Docker build completed. Restarting container...")
                
                # Restart in background (container will stop after this)
                subprocess.Popen(
                    ["docker", "compose", "up", "-d", "--force-recreate"],
                    cwd=agent_compose_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                
                return CommandResult(
                    success=True,
                    status="success",
                    data={
                        "message": "Update complete. Container restarting...",
                        "restarting": True,
                    },
                )
            else:
                return CommandResult(
                    success=True,
                    status="success",
                    data={
                        "message": "Code updated via git pull. Manual restart required.",
                        "needs_restart": True,
                    },
                )
            
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, status="error", error="Update timed out")
        except Exception as e:
            logger.error(f"Update error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _restart(self) -> CommandResult:
        """Riavvia agent (container/service)"""
        try:
            # Se in Docker, riavvia container
            if os.path.exists("/.dockerenv"):
                # Segnala al sistema di riavviare
                import signal
                os.kill(os.getpid(), signal.SIGTERM)
                return CommandResult(
                    success=True,
                    status="success",
                    data={"message": "Restart initiated"},
                )
            else:
                # Riavvia servizio systemd
                subprocess.Popen(
                    ["systemctl", "restart", "dadude-agent"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return CommandResult(
                    success=True,
                    status="success",
                    data={"message": "Service restart initiated"},
                )
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _reboot(self) -> CommandResult:
        """Riavvia sistema host"""
        try:
            # Richiede privilegi elevati
            subprocess.Popen(
                ["reboot"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return CommandResult(
                success=True,
                status="success",
                data={"message": "System reboot initiated"},
            )
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _get_status(self) -> CommandResult:
        """Ottieni stato agent"""
        import platform
        import psutil
        
        try:
            status = {
                "agent_version": "2.0.0",
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "hostname": platform.node(),
                "uptime_seconds": int(psutil.boot_time()),
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory": {
                    "total_mb": psutil.virtual_memory().total // (1024*1024),
                    "used_mb": psutil.virtual_memory().used // (1024*1024),
                    "percent": psutil.virtual_memory().percent,
                },
                "disk": {
                    "total_gb": psutil.disk_usage("/").total // (1024*1024*1024),
                    "free_gb": psutil.disk_usage("/").free // (1024*1024*1024),
                    "percent": psutil.disk_usage("/").percent,
                },
                "network_interfaces": [
                    {"name": name, "addresses": [addr.address for addr in addrs if addr.family.name == "AF_INET"]}
                    for name, addrs in psutil.net_if_addrs().items()
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            return CommandResult(success=True, status="success", data=status)
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    # ==========================================
    # DIAGNOSTICS
    # ==========================================
    
    async def _ping(self, params: Dict) -> CommandResult:
        """Ping host"""
        target = params.get("target")
        count = params.get("count", 4)
        
        if not target:
            return CommandResult(success=False, status="error", error="Missing 'target' parameter")
        
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), target],
                capture_output=True,
                text=True,
                timeout=30
            )
            return CommandResult(
                success=result.returncode == 0,
                status="success" if result.returncode == 0 else "error",
                data={
                    "output": result.stdout,
                    "error": result.stderr if result.returncode != 0 else None,
                },
            )
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, status="timeout", error="Ping timed out")
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _nmap_scan(self, params: Dict) -> CommandResult:
        """Scansione Nmap avanzata"""
        target = params.get("target")
        options = params.get("options", "-sV -sC")
        
        if not target:
            return CommandResult(success=False, status="error", error="Missing 'target' parameter")
        
        if not self._is_nmap_available():
            return CommandResult(success=False, status="error", error="Nmap not available")
        
        try:
            result = subprocess.run(
                ["nmap"] + options.split() + [target],
                capture_output=True,
                text=True,
                timeout=300
            )
            return CommandResult(
                success=result.returncode == 0,
                status="success" if result.returncode == 0 else "error",
                data={"output": result.stdout},
            )
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, status="timeout", error="Nmap scan timed out")
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    # ==========================================
    # HELPERS
    # ==========================================
    
    def _is_nmap_available(self) -> bool:
        """Verifica se nmap è disponibile"""
        try:
            result = subprocess.run(
                ["which", "nmap"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def _nmap_network_scan(self, network: str, scan_type: str) -> list:
        """Scansione rete con nmap (asincrono per non bloccare heartbeat)"""
        try:
            # Scan con parametri ottimizzati per affidabilità
            # -sn = no port scan (solo discovery)
            # -PE = ICMP echo ping
            # -PP = ICMP timestamp ping  
            # -PS22,80,443 = TCP SYN ping su porte comuni
            # --max-retries=3 = riprova 3 volte
            # --host-timeout=30s = timeout per host
            # --max-rtt-timeout=1000ms = attendi fino a 1s per risposta
            # -T3 = timing normale (non troppo veloce)
            cmd = [
                "nmap", "-sn", "-PE", "-PP", "-PS22,80,443,3389", 
                "-n", "-T3", 
                "--max-retries=3", 
                "--host-timeout=30s",
                "--max-rtt-timeout=1000ms",
                network
            ]
            
            if scan_type == "arp":
                # ARP scan - funziona solo su subnet locale
                cmd = ["nmap", "-sn", "-PR", "--send-eth", "-T3", network]
            elif scan_type == "aggressive" or scan_type == "slow":
                # Scan lento ma completo
                cmd = [
                    "nmap", "-sn", "-PE", "-PP", "-PM", 
                    "-PS21,22,23,25,80,443,445,3389,8080", 
                    "-PA80,443", "-PU53,161", 
                    "-n", "-T2",  # Timing più lento
                    "--max-retries=5",
                    "--host-timeout=60s",
                    "--max-rtt-timeout=2000ms",
                    network
                ]
            elif scan_type == "all":
                cmd = ["nmap", "-sS", "-sV", "-O", "--top-ports", "100", "-T3", network]
            
            # Usa subprocess asincrono per non bloccare l'event loop
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
                output = stdout.decode('utf-8', errors='replace')
            except asyncio.TimeoutError:
                proc.kill()
                raise TimeoutError("Nmap scan timed out after 600 seconds")
            
            # Parse output
            hosts = []
            current_host = None
            
            for line in output.split("\n"):
                if "Nmap scan report for" in line:
                    if current_host:
                        hosts.append(current_host)
                    # Estrai IP
                    parts = line.split()
                    ip = parts[-1].strip("()")
                    current_host = {"ip": ip, "status": "up"}
                elif "MAC Address:" in line and current_host:
                    parts = line.split()
                    if len(parts) >= 3:
                        current_host["mac"] = parts[2]
                        if len(parts) > 3:
                            current_host["vendor"] = " ".join(parts[3:]).strip("()")
            
            if current_host:
                hosts.append(current_host)
            
            return hosts
            
        except Exception as e:
            logger.error(f"Nmap scan error: {e}")
            raise
    
    async def _basic_ping_scan(self, network: str) -> list:
        """Scansione base con ping (fallback senza nmap)"""
        import ipaddress
        
        hosts = []
        
        try:
            net = ipaddress.ip_network(network, strict=False)
            
            # Limita a /24 max
            if net.num_addresses > 256:
                logger.warning(f"Network too large, limiting scan to first 256 addresses")
                net = list(net.hosts())[:256]
            else:
                net = list(net.hosts())
            
            # Ping parallelo
            async def ping_host(ip):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "ping", "-c", "1", "-W", "1", str(ip),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    await asyncio.wait_for(proc.wait(), timeout=2)
                    if proc.returncode == 0:
                        return {"ip": str(ip), "status": "up"}
                except Exception:
                    pass
                return None
            
            results = await asyncio.gather(*[ping_host(ip) for ip in net])
            hosts = [r for r in results if r is not None]
            
        except Exception as e:
            logger.error(f"Ping scan error: {e}")
        
        return hosts
    
    def register_handler(self, action: str, handler: Callable[[Dict], Awaitable[CommandResult]]):
        """Registra handler custom per azione"""
        self._custom_handlers[action] = handler
    
    def set_update_callback(self, callback: Callable[[str, str], Awaitable[bool]]):
        """Imposta callback per self-update"""
        self._update_callback = callback
    
    # ==========================================
    # SCHEDULED TASKS
    # ==========================================
    
    async def _daily_restart(self, params: Dict) -> CommandResult:
        """
        Riavvio giornaliero programmato.
        Esegue git fetch + reset + rebuild + restart ogni 24 ore.
        """
        logger.info("Daily restart triggered - performing full update and restart")
        
        try:
            agent_dir = "/opt/dadude-agent"
            
            # Se è un repository git, aggiorna prima
            if os.path.exists(os.path.join(agent_dir, ".git")):
                logger.info("Fetching latest code before restart...")
                
                # Fetch
                subprocess.run(
                    ["git", "fetch", "origin", "main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                # Reset
                subprocess.run(
                    ["git", "reset", "--hard", "origin/main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                logger.info("Code updated, rebuilding container...")
            
            # Rebuild e restart
            agent_compose_dir = os.path.join(agent_dir, "dadude-agent")
            if os.path.exists(os.path.join(agent_compose_dir, "docker-compose.yml")):
                # Build in background
                subprocess.Popen(
                    ["docker", "compose", "build", "--quiet"],
                    cwd=agent_compose_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                
                # Attendi build
                await asyncio.sleep(30)
                
                # Restart (in background, non aspettare)
                subprocess.Popen(
                    ["docker", "compose", "up", "-d", "--force-recreate"],
                    cwd=agent_compose_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                
                return CommandResult(
                    success=True,
                    status="success",
                    data={"message": "Daily restart: rebuild and restart initiated"},
                )
            else:
                # Fallback: semplice restart
                return await self._restart()
                
        except Exception as e:
            logger.error(f"Daily restart error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _connection_watchdog(self, params: Dict) -> CommandResult:
        """
        Watchdog connessione: se disconnesso per più di N ore, 
        esegue reset completo da git e riavvia.
        """
        max_hours = params.get("max_disconnected_hours", 24)
        
        try:
            # Leggi stato connessione da file
            state_file = "/var/lib/dadude-agent/connection_state.json"
            last_connected = None
            
            if os.path.exists(state_file):
                import json
                with open(state_file, "r") as f:
                    state = json.load(f)
                    last_connected_str = state.get("last_connected")
                    if last_connected_str:
                        from datetime import datetime
                        last_connected = datetime.fromisoformat(last_connected_str)
            
            if last_connected is None:
                # Prima esecuzione, salva stato attuale
                await self._save_connection_state(connected=False)
                return CommandResult(
                    success=True,
                    status="success",
                    data={"message": "Connection watchdog initialized"},
                )
            
            # Calcola ore di disconnessione
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            disconnected_hours = (now - last_connected).total_seconds() / 3600
            
            logger.info(f"Connection watchdog: last connected {disconnected_hours:.1f} hours ago")
            
            if disconnected_hours >= max_hours:
                logger.warning(f"Disconnected for {disconnected_hours:.1f} hours - triggering full reset")
                
                # Reset completo
                result = await self._daily_restart({"force": True})
                
                return CommandResult(
                    success=True,
                    status="success",
                    data={
                        "message": f"Full reset triggered after {disconnected_hours:.1f}h disconnect",
                        "action_taken": "full_reset",
                        "restart_result": result.data if result.success else result.error,
                    },
                )
            else:
                return CommandResult(
                    success=True,
                    status="success",
                    data={
                        "message": f"Connection OK - last connected {disconnected_hours:.1f}h ago",
                        "action_taken": "none",
                    },
                )
                
        except Exception as e:
            logger.error(f"Connection watchdog error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _save_connection_state(self, connected: bool):
        """Salva stato connessione su file"""
        import json
        from datetime import datetime
        
        state_file = "/var/lib/dadude-agent/connection_state.json"
        
        try:
            state = {}
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    state = json.load(f)
            
            if connected:
                state["last_connected"] = datetime.utcnow().isoformat()
            
            state["last_check"] = datetime.utcnow().isoformat()
            state["is_connected"] = connected
            
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving connection state: {e}")
    
    async def _cleanup_queue(self, params: Dict) -> CommandResult:
        """Pulizia coda locale"""
        try:
            # Placeholder - la coda si pulisce automaticamente
            return CommandResult(
                success=True,
                status="success",
                data={"message": "Queue cleanup completed"},
            )
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _check_updates(self, params: Dict) -> CommandResult:
        """Verifica aggiornamenti disponibili"""
        try:
            agent_dir = "/opt/dadude-agent"
            
            if os.path.exists(os.path.join(agent_dir, ".git")):
                # Fetch per vedere se ci sono update
                result = subprocess.run(
                    ["git", "fetch", "--dry-run", "origin", "main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                has_updates = bool(result.stdout.strip() or result.stderr.strip())
                
                return CommandResult(
                    success=True,
                    status="success",
                    data={
                        "has_updates": has_updates,
                        "message": "Updates available" if has_updates else "No updates",
                    },
                )
            else:
                return CommandResult(
                    success=False,
                    status="error",
                    error="Not a git repository",
                )
        except Exception as e:
            return CommandResult(success=False, status="error", error=str(e))
    
    # ==========================================
    # REMOTE SHELL / COMMAND EXECUTION
    # ==========================================
    
    async def _exec_command(self, params: Dict) -> CommandResult:
        """
        Esegue un comando localmente sull'agent.
        
        Params:
            command: str - comando da eseguire
            timeout: int - timeout in secondi (default 60)
            shell: bool - esegui in shell (default True)
        """
        command = params.get("command")
        timeout = params.get("timeout", 60)
        use_shell = params.get("shell", True)
        
        if not command:
            return CommandResult(success=False, status="error", error="Missing 'command' parameter")
        
        # Limita comandi pericolosi
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd", "shutdown", "reboot", "init 0", "init 6"]
        for d in dangerous:
            if d in command.lower():
                return CommandResult(
                    success=False, 
                    status="error", 
                    error=f"Command contains dangerous pattern: {d}"
                )
        
        logger.info(f"[EXEC] Running command: {command[:100]}...")
        
        try:
            if use_shell:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *command.split(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return CommandResult(
                    success=False,
                    status="timeout",
                    error=f"Command timed out after {timeout}s",
                )
            
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            return CommandResult(
                success=proc.returncode == 0,
                status="success" if proc.returncode == 0 else "error",
                data={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": proc.returncode,
                    "command": command,
                },
                error=stderr_str if proc.returncode != 0 else None,
            )
            
        except Exception as e:
            logger.error(f"[EXEC] Error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
    
    async def _exec_ssh(self, params: Dict) -> CommandResult:
        """
        Esegue un comando su un host remoto via SSH.
        
        Params:
            host: str - indirizzo host
            command: str - comando da eseguire
            username: str - username SSH (default root)
            password: str - password (opzionale)
            port: int - porta SSH (default 22)
            timeout: int - timeout in secondi (default 60)
            key_file: str - path chiave privata (opzionale)
        """
        host = params.get("host")
        command = params.get("command")
        username = params.get("username", "root")
        password = params.get("password")
        port = params.get("port", 22)
        timeout = params.get("timeout", 60)
        key_file = params.get("key_file")
        
        if not host:
            return CommandResult(success=False, status="error", error="Missing 'host' parameter")
        if not command:
            return CommandResult(success=False, status="error", error="Missing 'command' parameter")
        
        logger.info(f"[SSH] Executing on {host}: {command[:100]}...")
        
        try:
            import paramiko
            
            # Crea client SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connetti
            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 30,
                "allow_agent": False,
                "look_for_keys": False,
            }
            
            if key_file and os.path.exists(key_file):
                connect_kwargs["key_filename"] = key_file
            elif password:
                connect_kwargs["password"] = password
            else:
                # Prova senza autenticazione (chiavi di sistema)
                connect_kwargs["allow_agent"] = True
                connect_kwargs["look_for_keys"] = True
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: ssh.connect(**connect_kwargs))
            
            # Esegui comando
            stdin, stdout, stderr = await loop.run_in_executor(
                None, 
                lambda: ssh.exec_command(command, timeout=timeout)
            )
            
            # Leggi output
            stdout_str = await loop.run_in_executor(None, stdout.read)
            stderr_str = await loop.run_in_executor(None, stderr.read)
            exit_code = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            stdout_decoded = stdout_str.decode('utf-8', errors='replace') if stdout_str else ""
            stderr_decoded = stderr_str.decode('utf-8', errors='replace') if stderr_str else ""
            
            return CommandResult(
                success=exit_code == 0,
                status="success" if exit_code == 0 else "error",
                data={
                    "stdout": stdout_decoded,
                    "stderr": stderr_decoded,
                    "exit_code": exit_code,
                    "host": host,
                    "command": command,
                },
                error=stderr_decoded if exit_code != 0 else None,
            )
            
        except paramiko.AuthenticationException:
            return CommandResult(success=False, status="error", error="SSH authentication failed")
        except paramiko.SSHException as e:
            return CommandResult(success=False, status="error", error=f"SSH error: {e}")
        except Exception as e:
            logger.error(f"[SSH] Error: {e}")
            return CommandResult(success=False, status="error", error=str(e))

