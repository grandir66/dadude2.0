"""
DaDude Agent - Network Scanning Agent
Esegue scansioni WMI, SSH, SNMP dalla rete locale del cliente
"""
import os
import sys
import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import uvicorn

from .probes import wmi_probe, ssh_probe, snmp_probe
from .scanners import port_scanner, dns_resolver
from .config import get_settings, Settings


# ==========================================
# SCHEMAS
# ==========================================

class WMIProbeRequest(BaseModel):
    target: str
    username: str
    password: str
    domain: Optional[str] = ""


class SSHProbeRequest(BaseModel):
    target: str
    username: str
    password: Optional[str] = None
    private_key: Optional[str] = None
    port: int = 22


class SNMPProbeRequest(BaseModel):
    target: str
    community: str = "public"
    version: str = "2c"
    port: int = 161


class PortScanRequest(BaseModel):
    target: str
    ports: Optional[List[int]] = None  # None = default ports
    timeout: float = 1.0


class DNSReverseRequest(BaseModel):
    targets: List[str]
    dns_server: Optional[str] = None


class NetworkScanRequest(BaseModel):
    """Richiesta scansione rete"""
    network: str  # CIDR notation, es: 192.168.1.0/24
    scan_type: str = "ping"  # ping, arp, all
    timeout: float = 1.0


class BatchProbeRequest(BaseModel):
    """Richiesta batch dal server centrale"""
    task_id: str
    targets: List[Dict[str, Any]]
    credentials: Dict[str, Any]
    options: Optional[Dict[str, Any]] = None


class ProbeResult(BaseModel):
    success: bool
    target: str
    protocol: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


# ==========================================
# APP SETUP
# ==========================================

app = FastAPI(
    title="DaDude Agent",
    description="Network scanning agent for DaDude inventory system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# AUTHENTICATION
# ==========================================

async def verify_token(authorization: str = Header(None)) -> bool:
    """Verifica token di autenticazione"""
    settings = get_settings()
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    # Formato: "Bearer <token>"
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization[7:]
    
    if token != settings.agent_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return True


# ==========================================
# HEALTH ENDPOINTS
# ==========================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    return {
        "status": "healthy",
        "agent_id": settings.agent_id,
        "agent_name": settings.agent_name,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/info")
async def agent_info(authorized: bool = Depends(verify_token)):
    """Informazioni dettagliate sull'agent"""
    settings = get_settings()
    return {
        "agent_id": settings.agent_id,
        "agent_name": settings.agent_name,
        "server_url": settings.server_url,
        "dns_servers": settings.dns_servers,
        "capabilities": ["wmi", "ssh", "snmp", "port_scan", "dns_reverse"],
    }


# ==========================================
# PROBE ENDPOINTS
# ==========================================

@app.post("/probe/wmi", response_model=ProbeResult)
async def probe_wmi(
    request: WMIProbeRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Esegue probe WMI su un target Windows.
    Raccoglie: OS, hostname, CPU, RAM, disco, seriale.
    """
    start_time = datetime.now()
    
    try:
        result = await wmi_probe.probe(
            target=request.target,
            username=request.username,
            password=request.password,
            domain=request.domain or "",
        )
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ProbeResult(
            success=True,
            target=request.target,
            protocol="wmi",
            data=result,
            duration_ms=duration,
        )
        
    except Exception as e:
        logger.error(f"WMI probe failed for {request.target}: {e}")
        return ProbeResult(
            success=False,
            target=request.target,
            protocol="wmi",
            error=str(e),
        )


@app.post("/probe/ssh", response_model=ProbeResult)
async def probe_ssh(
    request: SSHProbeRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Esegue probe SSH su un target Linux/Unix.
    Raccoglie: hostname, OS, kernel, CPU, RAM, disco.
    """
    start_time = datetime.now()
    
    try:
        result = await ssh_probe.probe(
            target=request.target,
            username=request.username,
            password=request.password,
            private_key=request.private_key,
            port=request.port,
        )
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ProbeResult(
            success=True,
            target=request.target,
            protocol="ssh",
            data=result,
            duration_ms=duration,
        )
        
    except Exception as e:
        logger.error(f"SSH probe failed for {request.target}: {e}")
        return ProbeResult(
            success=False,
            target=request.target,
            protocol="ssh",
            error=str(e),
        )


@app.post("/probe/snmp", response_model=ProbeResult)
async def probe_snmp(
    request: SNMPProbeRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Esegue probe SNMP su un target.
    Raccoglie: sysDescr, sysName, vendor, model, seriale.
    """
    start_time = datetime.now()
    
    try:
        result = await snmp_probe.probe(
            target=request.target,
            community=request.community,
            version=request.version,
            port=request.port,
        )
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ProbeResult(
            success=True,
            target=request.target,
            protocol="snmp",
            data=result,
            duration_ms=duration,
        )
        
    except Exception as e:
        logger.error(f"SNMP probe failed for {request.target}: {e}")
        return ProbeResult(
            success=False,
            target=request.target,
            protocol="snmp",
            error=str(e),
        )


# ==========================================
# SCANNER ENDPOINTS
# ==========================================

@app.post("/scan/ports")
async def scan_ports(
    request: PortScanRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Scansiona porte TCP su un target.
    """
    start_time = datetime.now()
    
    try:
        result = await port_scanner.scan(
            target=request.target,
            ports=request.ports,
            timeout=request.timeout,
        )
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return {
            "success": True,
            "target": request.target,
            "open_ports": result,
            "duration_ms": duration,
        }
        
    except Exception as e:
        logger.error(f"Port scan failed for {request.target}: {e}")
        return {
            "success": False,
            "target": request.target,
            "error": str(e),
        }


@app.post("/scan/network")
async def scan_network(
    request: NetworkScanRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Scansiona una rete per trovare host attivi.
    Combina ping, port scan e ARP per massima rilevazione.
    """
    import ipaddress
    import subprocess
    import asyncio
    import socket
    
    start_time = datetime.now()
    
    # Porte da scansionare per rilevare host anche senza ping
    COMMON_PORTS = [22, 80, 443, 445, 139, 3389, 8080, 8443, 161, 21, 23, 25, 53, 110, 143, 993, 995, 8728, 8729]
    
    try:
        network = ipaddress.ip_network(request.network, strict=False)
        hosts = list(network.hosts())
        
        # Limita a max 256 host per evitare timeout
        if len(hosts) > 256:
            hosts = hosts[:256]
        
        logger.info(f"Scanning network {request.network} ({len(hosts)} hosts) - ping + port scan")
        
        found_hosts = {}  # IP -> info
        
        async def check_host(ip: str) -> Optional[Dict]:
            """Controlla host via ping e porte comuni"""
            ip_str = str(ip)
            result = {"address": ip_str, "alive": False, "open_ports": [], "mac_address": None}
            
            # 1. Prova ping
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ping", "-c", "1", "-W", "1", ip_str,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=2)
                if proc.returncode == 0:
                    result["alive"] = True
            except:
                pass
            
            # 2. Prova porte comuni (solo se ping fallisce, per velocità)
            if not result["alive"]:
                for port in [80, 443, 22]:  # Solo 3 porte critiche
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.2)  # Timeout breve
                        if sock.connect_ex((ip_str, port)) == 0:
                            result["alive"] = True
                            result["open_ports"].append(port)
                            sock.close()
                            break  # Trovato, non serve continuare
                        sock.close()
                    except:
                        pass
            
            if result["alive"]:
                # 3. Ottieni MAC dalla tabella ARP (prova più metodi)
                mac = None
                
                # Metodo 1: ip neigh
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "ip", "neigh", "show", ip_str,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await proc.communicate()
                    output = stdout.decode().strip()
                    if "lladdr" in output:
                        parts = output.split()
                        for i, p in enumerate(parts):
                            if p == "lladdr" and i + 1 < len(parts):
                                mac = parts[i + 1].upper()
                                break
                except:
                    pass
                
                # Metodo 2: arp -n (fallback)
                if not mac:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "arp", "-n", ip_str,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        stdout, _ = await proc.communicate()
                        output = stdout.decode().strip()
                        # Cerca pattern MAC xx:xx:xx:xx:xx:xx
                        import re
                        mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', output)
                        if mac_match:
                            mac = mac_match.group(0).upper().replace('-', ':')
                    except:
                        pass
                
                # Metodo 3: /proc/net/arp
                if not mac:
                    try:
                        with open('/proc/net/arp', 'r') as f:
                            for line in f:
                                if ip_str in line:
                                    parts = line.split()
                                    if len(parts) >= 4:
                                        mac = parts[3].upper()
                                        if mac != "00:00:00:00:00:00":
                                            break
                                        else:
                                            mac = None
                    except:
                        pass
                
                result["mac_address"] = mac
                return result
            return None
        
        # Esegui in parallelo (max 100 alla volta per velocità)
        batch_size = 100
        results = []
        for i in range(0, len(hosts), batch_size):
            batch = hosts[i:i+batch_size]
            tasks = [check_host(str(ip)) for ip in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, dict) and r:
                    results.append(r)
            
            # Log progresso ogni batch
            logger.info(f"Scanned {min(i+batch_size, len(hosts))}/{len(hosts)} hosts, found {len(results)} so far")
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        logger.info(f"Network scan completed: {len(results)}/{len(hosts)} hosts found in {duration}ms")
        
        return {
            "success": True,
            "network": request.network,
            "scan_type": request.scan_type,
            "devices_found": len(results),
            "results": results,
            "duration_ms": duration,
        }
        
    except Exception as e:
        logger.error(f"Network scan failed for {request.network}: {e}")
        return {
            "success": False,
            "network": request.network,
            "error": str(e),
        }


@app.post("/dns/reverse")
async def dns_reverse(
    request: DNSReverseRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Esegue reverse DNS lookup per una lista di IP.
    """
    settings = get_settings()
    dns_server = request.dns_server or (settings.dns_servers[0] if settings.dns_servers else None)
    
    try:
        results = await dns_resolver.batch_reverse_lookup(
            targets=request.targets,
            dns_server=dns_server,
        )
        
        return {
            "success": True,
            "results": results,
            "dns_server": dns_server,
        }
        
    except Exception as e:
        logger.error(f"DNS reverse lookup failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ==========================================
# BATCH OPERATIONS
# ==========================================

@app.post("/batch/probe")
async def batch_probe(
    request: BatchProbeRequest,
    authorized: bool = Depends(verify_token)
):
    """
    Esegue probe batch su più target.
    Usato dal server centrale per scansioni massive.
    """
    results = []
    
    for target_info in request.targets:
        target = target_info.get("address")
        probe_type = target_info.get("probe_type", "auto")
        
        if probe_type == "wmi":
            result = await probe_wmi(WMIProbeRequest(
                target=target,
                username=request.credentials.get("username", ""),
                password=request.credentials.get("password", ""),
                domain=request.credentials.get("domain", ""),
            ), authorized=True)
        elif probe_type == "ssh":
            result = await probe_ssh(SSHProbeRequest(
                target=target,
                username=request.credentials.get("username", ""),
                password=request.credentials.get("password"),
                port=request.credentials.get("port", 22),
            ), authorized=True)
        elif probe_type == "snmp":
            result = await probe_snmp(SNMPProbeRequest(
                target=target,
                community=request.credentials.get("community", "public"),
                version=request.credentials.get("version", "2c"),
            ), authorized=True)
        else:
            # Auto-detect: prova in base alle porte
            result = ProbeResult(
                success=False,
                target=target,
                protocol="unknown",
                error="Probe type not specified",
            )
        
        results.append(result.dict())
    
    return {
        "task_id": request.task_id,
        "total": len(request.targets),
        "success": sum(1 for r in results if r.get("success")),
        "results": results,
    }


# ==========================================
# MAIN
# ==========================================

def main():
    """Entry point"""
    settings = get_settings()
    
    # Setup logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    
    logger.info(f"Starting DaDude Agent {settings.agent_id}")
    logger.info(f"Server URL: {settings.server_url}")
    logger.info(f"API Port: {settings.api_port}")
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.api_port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()

