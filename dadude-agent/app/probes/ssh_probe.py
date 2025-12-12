"""
DaDude Agent - SSH Probe
Scansione dispositivi Linux/Unix via SSH
"""
import asyncio
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from io import StringIO


_executor = ThreadPoolExecutor(max_workers=5)


async def probe(
    target: str,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    port: int = 22,
) -> Dict[str, Any]:
    """
    Esegue probe SSH su un target Linux/Unix.
    
    Returns:
        Dict con info sistema: hostname, os, kernel, cpu, ram, disco
    """
    loop = asyncio.get_event_loop()
    
    def connect():
        import paramiko
        
        logger.debug(f"SSH probe: connecting to {target}:{port} as {username}")
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_args = {
            "hostname": target,
            "port": port,
            "username": username,
            "timeout": 15,
            "allow_agent": False,
            "look_for_keys": False,
        }
        
        if private_key:
            key = paramiko.RSAKey.from_private_key(StringIO(private_key))
            connect_args["pkey"] = key
        else:
            connect_args["password"] = password
        
        client.connect(**connect_args)
        
        info = {}
        
        def exec_cmd(cmd: str, timeout: int = 5) -> str:
            try:
                stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                return stdout.read().decode().strip()
            except:
                return ""
        
        # Hostname
        info["hostname"] = exec_cmd("hostname")
        
        # OS Info
        os_release = exec_cmd("cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null")
        if os_release:
            for line in os_release.split('\n'):
                if line.startswith('PRETTY_NAME='):
                    info["os_name"] = line.split('=')[1].strip('"')
                elif line.startswith('ID='):
                    info["os_id"] = line.split('=')[1].strip('"')
                elif line.startswith('VERSION_ID='):
                    info["os_version"] = line.split('=')[1].strip('"')
        
        # Check for RouterOS (MikroTik)
        ros = exec_cmd(":put [/system resource get version]")
        if ros and ("RouterOS" in ros or "." in ros):
            info["os_name"] = "RouterOS"
            info["os_version"] = ros
            info["device_type"] = "mikrotik"
        
        # Kernel
        info["kernel"] = exec_cmd("uname -r")
        
        # Architecture
        info["architecture"] = exec_cmd("uname -m")
        
        # CPU Info
        cpu_info = exec_cmd("cat /proc/cpuinfo | grep 'model name' | head -1")
        if cpu_info and ':' in cpu_info:
            info["cpu_model"] = cpu_info.split(':')[1].strip()
        
        # CPU Cores
        cores = exec_cmd("nproc 2>/dev/null || grep -c processor /proc/cpuinfo")
        if cores.isdigit():
            info["cpu_cores"] = int(cores)
        
        # RAM
        mem = exec_cmd("free -m | grep Mem | awk '{print $2}'")
        if mem.isdigit():
            info["ram_total_mb"] = int(mem)
        
        # Disk
        disk = exec_cmd("df -BG / | awk 'NR==2 {print $2, $4}'")
        if disk:
            parts = disk.split()
            if len(parts) >= 2:
                try:
                    info["disk_total_gb"] = int(parts[0].replace('G', ''))
                    info["disk_free_gb"] = int(parts[1].replace('G', ''))
                except:
                    pass
        
        # Uptime
        uptime = exec_cmd("uptime -p 2>/dev/null || uptime")
        if uptime:
            info["uptime"] = uptime
        
        # Serial (se disponibile)
        serial = exec_cmd("sudo dmidecode -s system-serial-number 2>/dev/null || cat /sys/class/dmi/id/product_serial 2>/dev/null")
        if serial and "Permission" not in serial:
            info["serial_number"] = serial
        
        client.close()
        
        logger.info(f"SSH probe successful: {info.get('hostname')} ({info.get('os_name', 'Linux')})")
        return info
    
    return await loop.run_in_executor(_executor, connect)

