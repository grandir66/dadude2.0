"""
DaDude Agent - SSH Probe
Scansione dispositivi Linux/Unix/MikroTik via SSH
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
    Esegue probe SSH su un target Linux/Unix/MikroTik.
    Rileva automaticamente il tipo di device ed esegue comandi appropriati.
    
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
        
        # ===== PRIMA RILEVA IL TIPO DI DEVICE =====
        # Prova MikroTik RouterOS (non supporta comandi Linux)
        ros_out = exec_cmd("/system resource print")
        
        if "version:" in ros_out.lower() or "uptime:" in ros_out.lower() or "routeros" in ros_out.lower():
            # ===== MIKROTIK ROUTEROS =====
            logger.info(f"SSH probe: Detected MikroTik RouterOS on {target}")
            info["device_type"] = "mikrotik"
            info["os_name"] = "RouterOS"
            info["manufacturer"] = "MikroTik"
            info["category"] = "router"
            
            # Parse /system resource print
            for line in ros_out.split('\n'):
                ll = line.lower().strip()
                if ll.startswith('version:'):
                    info["os_version"] = line.split(':', 1)[1].strip()
                elif ll.startswith('board-name:'):
                    info["model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('cpu:') and 'cpu-count' not in ll:
                    info["cpu_model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('cpu-count:'):
                    try:
                        info["cpu_cores"] = int(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif ll.startswith('total-memory:'):
                    try:
                        mem_str = line.split(':', 1)[1].strip()
                        if 'MiB' in mem_str:
                            info["ram_total_mb"] = int(float(mem_str.replace('MiB', '').strip()))
                        elif 'GiB' in mem_str:
                            info["ram_total_mb"] = int(float(mem_str.replace('GiB', '').strip()) * 1024)
                    except:
                        pass
                elif ll.startswith('free-memory:'):
                    try:
                        mem_str = line.split(':', 1)[1].strip()
                        if 'MiB' in mem_str:
                            info["ram_free_mb"] = int(float(mem_str.replace('MiB', '').strip()))
                    except:
                        pass
                elif ll.startswith('architecture-name:'):
                    info["architecture"] = line.split(':', 1)[1].strip()
                elif ll.startswith('uptime:'):
                    info["uptime"] = line.split(':', 1)[1].strip()
            
            # Get hostname from /system identity
            identity_out = exec_cmd("/system identity print")
            for line in identity_out.split('\n'):
                if 'name:' in line.lower():
                    info["hostname"] = line.split(':', 1)[1].strip()
                    break
            
            # Get serial/model from /system routerboard
            rb_out = exec_cmd("/system routerboard print")
            for line in rb_out.split('\n'):
                ll = line.lower().strip()
                if ll.startswith('serial-number:'):
                    info["serial_number"] = line.split(':', 1)[1].strip()
                elif ll.startswith('model:') and not info.get("model"):
                    info["model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('current-firmware:'):
                    info["firmware"] = line.split(':', 1)[1].strip()
            
            # Get license
            lic_out = exec_cmd("/system license print")
            for line in lic_out.split('\n'):
                if 'level:' in line.lower():
                    info["license_level"] = line.split(':', 1)[1].strip()
            
            # Get interface count
            iface_count = exec_cmd("/interface print count-only")
            if iface_count.isdigit():
                info["interface_count"] = int(iface_count)
        
        else:
            # ===== LINUX/UNIX/OTHER =====
            logger.debug(f"SSH probe: Detecting Linux/Unix on {target}")
            
            # Hostname
            info["hostname"] = exec_cmd("hostname")
            
            # OS Info
            os_release = exec_cmd("cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null")
            if os_release:
                for line in os_release.split('\n'):
                    if line.startswith('PRETTY_NAME='):
                        info["os_name"] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('ID='):
                        info["os_id"] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('VERSION_ID='):
                        info["os_version"] = line.split('=', 1)[1].strip('"')
            
            # Check for special devices
            # Ubiquiti
            ubnt_out = exec_cmd("cat /etc/board.info 2>/dev/null")
            if ubnt_out and 'board.' in ubnt_out.lower():
                info["device_type"] = "network"
                info["manufacturer"] = "Ubiquiti"
                info["os_name"] = "UniFi"
                for line in ubnt_out.split('\n'):
                    if 'board.name' in line.lower():
                        info["model"] = line.split('=')[-1].strip()
                    elif 'board.sysid' in line.lower():
                        info["serial_number"] = line.split('=')[-1].strip()
            
            # Synology
            syno_out = exec_cmd("cat /etc/synoinfo.conf 2>/dev/null")
            if syno_out and 'synology' in syno_out.lower():
                info["device_type"] = "nas"
                info["manufacturer"] = "Synology"
                info["os_name"] = "DSM"
                for line in syno_out.split('\n'):
                    if 'upnpmodelname' in line.lower():
                        info["model"] = line.split('=')[-1].strip().strip('"')
            
            # Proxmox VE Detection (più robusta - Proxmox è basato su Debian)
            pve_ver = exec_cmd("pveversion 2>/dev/null")
            if pve_ver and 'pve-manager' in pve_ver.lower():
                info["device_type"] = "hypervisor"
                info["category"] = "hypervisor"
                info["os_name"] = "Proxmox VE"
                info["os_family"] = "Proxmox VE"
                info["manufacturer"] = "Proxmox Server Solutions GmbH"
                info["os_version"] = pve_ver
                # Conta container e VM
                lxc = exec_cmd("pct list 2>/dev/null | tail -n +2 | wc -l")
                if lxc.isdigit():
                    info["lxc_containers"] = int(lxc)
                vms = exec_cmd("qm list 2>/dev/null | tail -n +2 | wc -l")
                if vms.isdigit():
                    info["vms"] = int(vms)
                # Cluster info
                cluster = exec_cmd("pvecm status 2>/dev/null | grep 'Cluster Name' | cut -d: -f2")
                if cluster:
                    info["cluster_name"] = cluster.strip()
                # Storage
                storage = exec_cmd("pvesm status 2>/dev/null | tail -n +2 | wc -l")
                if storage.isdigit():
                    info["storage_count"] = int(storage)
            elif 'proxmox' in os_release.lower():
                info["device_type"] = "hypervisor"
                info["category"] = "hypervisor"
                info["os_name"] = "Proxmox VE"
                info["manufacturer"] = "Proxmox Server Solutions GmbH"
            
            # Default device type
            if not info.get("device_type"):
                info["device_type"] = "linux"
            
            # Kernel
            kernel = exec_cmd("uname -r")
            if kernel:
                info["kernel"] = kernel
            
            # Architecture
            arch = exec_cmd("uname -m")
            if arch:
                info["architecture"] = arch
            
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
            
            # Serial (DMI)
            serial = exec_cmd("cat /sys/class/dmi/id/product_serial 2>/dev/null")
            if serial and serial != "To Be Filled By O.E.M." and "Permission" not in serial:
                info["serial_number"] = serial
            
            # Manufacturer/Model (DMI)
            vendor = exec_cmd("cat /sys/class/dmi/id/sys_vendor 2>/dev/null")
            if vendor and vendor != "To Be Filled By O.E.M.":
                info["manufacturer"] = vendor
            
            model = exec_cmd("cat /sys/class/dmi/id/product_name 2>/dev/null")
            if model and model != "To Be Filled By O.E.M.":
                info["model"] = model
            
            # ===== INFORMAZIONI DETTAGLIATE LINUX =====
            
            # RAM dettagli
            mem_free = exec_cmd("free -m | grep Mem | awk '{print $4}'")
            if mem_free.isdigit():
                info["ram_free_mb"] = int(mem_free)
            
            # CPU speed
            cpu_speed = exec_cmd("lscpu 2>/dev/null | grep 'CPU MHz' | awk '{print $3}'")
            if cpu_speed:
                try:
                    info["cpu_speed_mhz"] = int(float(cpu_speed))
                except:
                    pass
            
            # All disks
            disks_out = exec_cmd("df -BG -x tmpfs -x devtmpfs 2>/dev/null | tail -n +2")
            if disks_out:
                disks = []
                for line in disks_out.split('\n'):
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            disks.append({
                                "device": parts[0],
                                "mount": parts[5],
                                "size_gb": int(parts[1].replace('G', '')),
                                "free_gb": int(parts[3].replace('G', '')),
                            })
                        except:
                            pass
                if disks:
                    info["disks"] = disks
            
            # Network interfaces
            ifaces_out = exec_cmd("ip -o addr show 2>/dev/null | grep -v '127.0.0.1' | awk '{print $2, $4}'")
            if ifaces_out:
                interfaces = []
                for line in ifaces_out.split('\n'):
                    parts = line.split()
                    if len(parts) >= 2:
                        interfaces.append({
                            "name": parts[0],
                            "address": parts[1].split('/')[0],
                        })
                if interfaces:
                    info["network_interfaces"] = interfaces
            
            # MAC addresses
            macs_out = exec_cmd("ip link show 2>/dev/null | grep 'link/ether' | awk '{print $2}'")
            if macs_out:
                macs = [m for m in macs_out.split('\n') if m]
                if macs:
                    info["mac_addresses"] = macs
            
            # Docker installed?
            docker_ver = exec_cmd("docker --version 2>/dev/null")
            if docker_ver:
                info["docker_version"] = docker_ver.replace('Docker version ', '').split(',')[0]
                # Docker containers count
                containers = exec_cmd("docker ps -q 2>/dev/null | wc -l")
                if containers.isdigit():
                    info["docker_containers_running"] = int(containers)
            
            # LXC/LXD containers (Proxmox)
            lxc_count = exec_cmd("pct list 2>/dev/null | tail -n +2 | wc -l")
            if lxc_count.isdigit() and int(lxc_count) > 0:
                info["lxc_containers"] = int(lxc_count)
            
            # VMs (Proxmox)
            vm_count = exec_cmd("qm list 2>/dev/null | tail -n +2 | wc -l")
            if vm_count.isdigit() and int(vm_count) > 0:
                info["vms"] = int(vm_count)
            
            # Important services
            services_out = exec_cmd("systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | head -30 | awk '{print $1}'")
            if services_out:
                services = [s.replace('.service', '') for s in services_out.split('\n') if s]
                # Filtra solo servizi interessanti
                important = ["nginx", "apache", "httpd", "mysql", "mariadb", "postgresql", "redis", 
                           "mongodb", "docker", "sshd", "postfix", "dovecot", "named", "bind", 
                           "haproxy", "squid", "samba", "nfs", "pve", "ceph"]
                filtered = [s for s in services if any(imp in s.lower() for imp in important)]
                if filtered:
                    info["important_services"] = filtered
            
            # Timezone
            tz = exec_cmd("timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null")
            if tz:
                info["timezone"] = tz
            
            # Users with shell access
            users_out = exec_cmd("grep -E '/bin/(ba)?sh$' /etc/passwd | cut -d: -f1")
            if users_out:
                users = [u for u in users_out.split('\n') if u and u not in ['root']]
                if users:
                    info["shell_users"] = users
            
            # Last login
            last_login = exec_cmd("last -1 -w 2>/dev/null | head -1")
            if last_login and 'wtmp' not in last_login:
                info["last_login"] = last_login
            
            # Virtualization type
            virt = exec_cmd("systemd-detect-virt 2>/dev/null")
            if virt and virt != "none":
                info["virtualization"] = virt
        
        client.close()
        
        logger.info(f"SSH probe successful: {info.get('hostname')} ({info.get('os_name', 'Unknown')})")
        return info
    
    return await loop.run_in_executor(_executor, connect)
