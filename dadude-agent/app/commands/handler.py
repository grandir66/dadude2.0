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
    
    # Diagnostics
    PING = "ping"
    TRACEROUTE = "traceroute"
    NMAP_SCAN = "nmap_scan"


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
        """Query ARP table via SNMP (generic router)"""
        import ipaddress
        
        address = params.get("address")
        community = params.get("community", "public")
        version = params.get("version", "2c")
        
        if not address:
            return CommandResult(success=False, status="error", error="Missing 'address' parameter")
        
        try:
            # pysnmp 7.x usa v3arch invece di hlapi diretto
            try:
                from pysnmp.hlapi.v3arch import (
                    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
                    ObjectType, ObjectIdentity, bulkCmd
                )
            except ImportError:
                # Fallback per pysnmp 4.x
                from pysnmp.hlapi import (
                    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
                    ObjectType, ObjectIdentity, bulkCmd
                )
            
            loop = asyncio.get_event_loop()
            
            def get_arp_via_snmp():
                # OID per ipNetToMediaPhysAddress (ARP table)
                # 1.3.6.1.2.1.4.22.1.2 = MAC address
                # 1.3.6.1.2.1.4.22.1.3 = IP address
                
                arp_entries = {}
                mp_model = 1 if version == "2c" else 0
                
                for (errorIndication, errorStatus, errorIndex, varBinds) in bulkCmd(
                    SnmpEngine(),
                    CommunityData(community, mpModel=mp_model),
                    UdpTransportTarget((address, 161), timeout=2, retries=1),
                    ContextData(),
                    0, 25,  # non-repeaters, max-repetitions
                    ObjectType(ObjectIdentity('1.3.6.1.2.1.4.22.1.2')),  # MAC
                    lexicographicMode=False
                ):
                    if errorIndication or errorStatus:
                        break
                    
                    for varBind in varBinds:
                        oid = str(varBind[0])
                        value = varBind[1]
                        
                        # Estrai IP dall'OID (ultimi 4 ottetti)
                        # OID format: 1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ip1>.<ip2>.<ip3>.<ip4>
                        parts = oid.split('.')
                        if len(parts) >= 4:
                            ip = '.'.join(parts[-4:])
                            # MAC è in formato ottetti
                            mac = ':'.join(format(b, '02x') for b in bytes(value))
                            arp_entries[ip] = mac
                
                return arp_entries
            
            arp_data = await loop.run_in_executor(None, get_arp_via_snmp)
            
            # Filtra per network se specificato
            entries = []
            net = None
            if network_cidr:
                try:
                    net = ipaddress.ip_network(network_cidr, strict=False)
                except:
                    pass
            
            for ip, mac in arp_data.items():
                if net:
                    try:
                        if ipaddress.ip_address(ip) not in net:
                            continue
                    except:
                        continue
                
                entries.append({"ip": ip, "mac": mac})
            
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
            
            # Prova git pull (directory deve essere montata come volume)
            if os.path.exists(os.path.join(agent_dir, ".git")):
                logger.info("Performing git pull...")
                result = subprocess.run(
                    ["git", "pull", "--rebase", "origin", "main"],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    logger.warning(f"Git pull failed: {result.stderr}")
                    return CommandResult(
                        success=False,
                        status="error",
                        error=f"Git pull failed: {result.stderr[:200]}",
                    )
                else:
                    logger.info(f"Git pull success: {result.stdout}")
                    
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
            
            return CommandResult(
                success=True,
                status="success",
                data={
                    "message": "Code updated via git pull. Restart container to apply changes.",
                    "needs_restart": True,
                },
            )
            
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, status="error", error="Update timed out")
        except Exception as e:
            logger.error(f"Update error: {e}")
            return CommandResult(success=False, status="error", error=str(e))
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
            # Scan veloce per discovery
            cmd = ["nmap", "-sn", "-n", network]
            
            if scan_type == "arp":
                cmd = ["nmap", "-sn", "-PR", network]
            elif scan_type == "all":
                cmd = ["nmap", "-sS", "-sV", "-O", "--top-ports", "100", network]
            
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

