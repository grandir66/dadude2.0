"""
DaDude Agent - Port Scanner
Scansione porte TCP/UDP
"""
import asyncio
import socket
from typing import List, Dict, Any, Optional
from loguru import logger


# Porte di default da scansionare
DEFAULT_PORTS = [
    22, 23, 25, 53, 80, 110, 135, 139, 143, 161, 389, 443, 445,
    636, 993, 995, 1433, 3306, 3389, 5432, 5900, 5985, 5986,
    8080, 8443, 8728, 8729, 8291,
]

# Mappa porte -> servizi
PORT_SERVICES = {
    22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 135: "wmi", 139: "netbios", 143: "imap", 161: "snmp",
    389: "ldap", 443: "https", 445: "smb", 636: "ldaps", 993: "imaps",
    995: "pop3s", 1433: "mssql", 3306: "mysql", 3389: "rdp",
    5432: "postgresql", 5900: "vnc", 5985: "winrm", 5986: "winrm-ssl",
    8080: "http-alt", 8443: "https-alt", 8728: "mikrotik-api",
    8729: "mikrotik-api-ssl", 8291: "winbox",
}


async def scan_port(target: str, port: int, timeout: float = 1.0) -> Dict[str, Any]:
    """Scansiona una singola porta TCP"""
    loop = asyncio.get_event_loop()
    
    def check():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((target, port))
            return result == 0
        except:
            return False
        finally:
            sock.close()
    
    try:
        is_open = await loop.run_in_executor(None, check)
        return {
            "port": port,
            "protocol": "tcp",
            "service": PORT_SERVICES.get(port, f"port-{port}"),
            "open": is_open,
        }
    except:
        return {
            "port": port,
            "protocol": "tcp",
            "service": PORT_SERVICES.get(port, f"port-{port}"),
            "open": False,
        }


async def scan(
    target: str,
    ports: Optional[List[int]] = None,
    timeout: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Scansiona multiple porte TCP.
    
    Args:
        target: IP o hostname
        ports: Lista porte (default: porte comuni)
        timeout: Timeout per porta in secondi
    
    Returns:
        Lista di risultati per ogni porta
    """
    if ports is None:
        ports = DEFAULT_PORTS
    
    logger.debug(f"Scanning {len(ports)} ports on {target}")
    
    # Scansiona in parallelo
    tasks = [scan_port(target, port, timeout) for port in ports]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filtra solo porte aperte
    open_ports = []
    for result in results:
        if isinstance(result, dict) and result.get("open"):
            open_ports.append(result)
    
    logger.info(f"Port scan complete: {len(open_ports)}/{len(ports)} ports open on {target}")
    
    return open_ports

