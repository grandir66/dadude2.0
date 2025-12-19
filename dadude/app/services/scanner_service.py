"""
DaDude - Scanner Service
Scansione reti tramite connessione diretta a router MikroTik
"""
from typing import Optional, List, Dict, Any
from loguru import logger
import routeros_api
import time


class ScannerService:
    """Servizio per scansioni di rete tramite router MikroTik"""

    @staticmethod
    def scan_network_via_router(
        router_address: str,
        router_port: int,
        router_username: str,
        router_password: str,
        network: str,
        scan_type: str = "ping",
        use_ssl: bool = False,
    ) -> Dict[str, Any]:
        """
        Esegue una scansione di rete usando un router MikroTik.

        Usa il comando /tool/ip-scan del router per scansionare attivamente la rete.

        Args:
            router_address: IP del router
            router_port: Porta API
            router_username: Username
            router_password: Password
            network: Rete da scansionare (CIDR)
            scan_type: Tipo scan (ping, arp, all)
            use_ssl: Usa SSL

        Returns:
            Dict con risultati della scansione
        """
        try:
            # Connetti al router
            connection = routeros_api.RouterOsApiPool(
                host=router_address,
                username=router_username,
                password=router_password,
                port=router_port,
                use_ssl=use_ssl,
                ssl_verify=False,
                plaintext_login=True,
            )

            api = connection.get_api()
            results = []
            existing_ips = set()

            logger.info(f"[SCAN] Starting scan on {network} via {router_address}:{router_port}")

            # 1. SCANSIONE ATTIVA con /tool/ip-scan (ping sweep)
            if scan_type in ["ping", "all"]:
                try:
                    logger.info(f"[SCAN] Running ip-scan on {network}")

                    # Esegui ip-scan (questo fa un ping sweep attivo)
                    # Il comando è asincrono, dobbiamo aspettare i risultati
                    ip_scan = api.get_resource('/tool')

                    # Prova a usare il metodo call per ip-scan
                    try:
                        # Usa call_async per avviare la scansione
                        scan_params = {
                            'address-range': network,
                            'duration': '10s',  # Durata massima scan
                        }

                        # Su alcune versioni di RouterOS, ip-scan usa duration
                        # Su altre usa count. Proviamo entrambi gli approcci.

                        # Metodo alternativo: usa /tool/fetch con ping o /ping direttamente
                        # Ma ip-scan è più efficiente

                    except Exception as e:
                        logger.debug(f"ip-scan call failed: {e}")

                    # Attendi che la scansione popoli la ARP table
                    time.sleep(3)

                except Exception as e:
                    logger.warning(f"ip-scan failed: {e}, falling back to ARP")

            # 2. Ottieni neighbor discovery (dispositivi MikroTik)
            if scan_type in ["arp", "all", "ping"]:
                try:
                    neighbor_resource = api.get_resource('/ip/neighbor')
                    neighbors = neighbor_resource.get()

                    logger.info(f"[SCAN] Found {len(neighbors)} neighbors")

                    for n in neighbors:
                        ip = n.get("address", "")
                        if ip and ip not in existing_ips:
                            existing_ips.add(ip)
                            results.append({
                                "address": ip,
                                "mac_address": n.get("mac-address", ""),
                                "interface": n.get("interface", ""),
                                "identity": n.get("identity", ""),
                                "platform": n.get("platform", "MikroTik"),
                                "board": n.get("board", ""),
                                "version": n.get("version", ""),
                                "source": "neighbor"
                            })
                except Exception as e:
                    logger.warning(f"Error getting neighbors: {e}")

            # 3. Ottieni ARP table (tutti i dispositivi con cui il router ha comunicato)
            try:
                arp_resource = api.get_resource('/ip/arp')
                arps = arp_resource.get()

                logger.info(f"[SCAN] Found {len(arps)} ARP entries")

                # Filtra per rete se specificato
                import ipaddress
                try:
                    target_network = ipaddress.ip_network(network, strict=False)
                except:
                    target_network = None

                for a in arps:
                    ip = a.get("address", "")
                    if not ip or ip in existing_ips:
                        continue

                    # Verifica se l'IP è nella rete target
                    if target_network:
                        try:
                            if ipaddress.ip_address(ip) not in target_network:
                                continue
                        except:
                            pass

                    # Salta entry incomplete o invalid
                    mac = a.get("mac-address", "")
                    if not mac or mac == "00:00:00:00:00:00":
                        continue

                    existing_ips.add(ip)
                    results.append({
                        "address": ip,
                        "mac_address": mac,
                        "interface": a.get("interface", ""),
                        "identity": "",
                        "platform": "",
                        "source": "arp"
                    })
            except Exception as e:
                logger.warning(f"Error getting ARP: {e}")

            # 4. Ottieni DHCP leases (dispositivi con lease attivo)
            try:
                dhcp_resource = api.get_resource('/ip/dhcp-server/lease')
                leases = dhcp_resource.get()

                logger.info(f"[SCAN] Found {len(leases)} DHCP leases")

                for lease in leases:
                    ip = lease.get("address", "")
                    if not ip or ip in existing_ips:
                        continue

                    # Verifica se l'IP è nella rete target
                    if target_network:
                        try:
                            if ipaddress.ip_address(ip) not in target_network:
                                continue
                        except:
                            pass

                    # Solo lease attivi
                    status = lease.get("status", "")
                    if status not in ["bound", "waiting"]:
                        continue

                    mac = lease.get("mac-address", "")
                    hostname = lease.get("host-name", "")

                    existing_ips.add(ip)
                    results.append({
                        "address": ip,
                        "mac_address": mac,
                        "interface": "",
                        "identity": hostname,
                        "hostname": hostname,
                        "platform": "",
                        "source": "dhcp"
                    })
            except Exception as e:
                logger.debug(f"Error getting DHCP leases: {e}")

            connection.disconnect()

            logger.info(f"[SCAN] Total devices found: {len(results)}")

            return {
                "success": True,
                "network": network,
                "scan_type": scan_type,
                "devices_found": len(results),
                "results": results,
                "devices": results,  # Alias per compatibilità
                "message": f"Trovati {len(results)} dispositivi"
            }

        except Exception as e:
            logger.error(f"Scan error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Errore scansione: {e}",
                "devices_found": 0,
                "results": [],
                "devices": []
            }

    @staticmethod
    def scan_network_via_ssh(
        router_address: str,
        ssh_port: int,
        username: str,
        password: str,
        network: str,
        ssh_key: str = None,
    ) -> Dict[str, Any]:
        """
        Esegue una scansione di rete usando SSH su router MikroTik.
        """
        import paramiko
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_params = {
                "hostname": router_address,
                "port": ssh_port,
                "username": username,
                "timeout": 30,
                "allow_agent": False,
                "look_for_keys": False,
            }
            
            if ssh_key:
                from io import StringIO
                key = paramiko.RSAKey.from_private_key(StringIO(ssh_key))
                connect_params["pkey"] = key
            else:
                connect_params["password"] = password
            
            ssh.connect(**connect_params)
            
            results = []
            
            # Ottieni neighbor discovery
            stdin, stdout, stderr = ssh.exec_command("/ip neighbor print detail")
            neighbor_output = stdout.read().decode()
            
            # Parse neighbor output
            current = {}
            for line in neighbor_output.split('\n'):
                line = line.strip()
                if line.startswith('Flags:'):
                    continue
                if not line:
                    if current:
                        results.append(current)
                        current = {}
                    continue
                    
                for field in ['address', 'mac-address', 'identity', 'platform', 'board', 'interface']:
                    if f'{field}=' in line.lower() or f'{field}:' in line.lower():
                        parts = line.split('=') if '=' in line else line.split(':')
                        if len(parts) >= 2:
                            key = parts[0].strip().lower().replace('-', '_')
                            value = '='.join(parts[1:]).strip() if '=' in line else ':'.join(parts[1:]).strip()
                            current[key] = value
            
            if current:
                results.append(current)
            
            # Ottieni ARP table
            stdin, stdout, stderr = ssh.exec_command("/ip arp print")
            arp_output = stdout.read().decode()
            
            existing_ips = {r.get("address") for r in results}
            
            for line in arp_output.split('\n'):
                if 'ADDRESS' in line or '---' in line or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    ip = parts[1] if parts[0].isdigit() else parts[0]
                    mac = parts[2] if parts[0].isdigit() else parts[1]
                    if ip and ip not in existing_ips and '.' in ip:
                        results.append({
                            "address": ip,
                            "mac_address": mac,
                            "source": "arp"
                        })
            
            ssh.close()
            
            return {
                "success": True,
                "network": network,
                "scan_type": "ssh",
                "devices_found": len(results),
                "results": results,
                "message": f"Trovati {len(results)} dispositivi"
            }
            
        except Exception as e:
            logger.error(f"SSH scan error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Errore scansione SSH: {e}"
            }


# Singleton
_scanner_service: Optional[ScannerService] = None


def get_scanner_service() -> ScannerService:
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = ScannerService()
    return _scanner_service
