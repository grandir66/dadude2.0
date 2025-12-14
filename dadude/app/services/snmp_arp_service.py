"""
DaDude - SNMP ARP Service
Lettura tabella ARP da router generici via SNMP
Supporta: Cisco, Ubiquiti, HP, Juniper, e qualsiasi device SNMP standard
"""
from typing import Optional, List, Dict, Any
from loguru import logger
import ipaddress


class SNMPArpService:
    """
    Servizio per lettura ARP table via SNMP.
    Usa OID standard RFC 1213/RFC 4293 compatibili con la maggior parte dei router.
    """
    
    # OID standard per ARP table (RFC 1213 - ipNetToMediaTable)
    # .1.3.6.1.2.1.4.22.1.2.{ifIndex}.{ipAddress} = MAC address
    OID_ARP_TABLE = ".1.3.6.1.2.1.4.22.1.2"
    
    # OID alternativo per dispositivi più recenti (RFC 4293 - ipNetToPhysicalTable)
    # .1.3.6.1.2.1.4.35.1.4.{ifIndex}.{addressType}.{ipAddress} = MAC
    OID_ARP_TABLE_V2 = ".1.3.6.1.2.1.4.35.1.4"
    
    # OID per sysDescr (identificazione dispositivo)
    OID_SYS_DESCR = ".1.3.6.1.2.1.1.1.0"
    OID_SYS_NAME = ".1.3.6.1.2.1.1.5.0"
    
    def __init__(self):
        self._pysnmp_available = self._check_pysnmp()
    
    def _check_pysnmp(self) -> bool:
        """Verifica se pysnmp è disponibile"""
        try:
            # pysnmp 7.x
            from pysnmp.hlapi.v3arch import (
                getCmd, nextCmd, SnmpEngine, CommunityData,
                UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
            )
            return True
        except ImportError:
            try:
                # pysnmp 4.x fallback
                from pysnmp.hlapi import (
                    getCmd, nextCmd, SnmpEngine, CommunityData,
                    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
                )
                return True
            except ImportError:
                logger.warning("pysnmp not available - SNMP ARP lookup disabled")
                return False
    
    def get_arp_table(
        self,
        address: str,
        community: str = "public",
        port: int = 161,
        network_filter: Optional[str] = None,
        timeout: int = 5,
        retries: int = 2,
        snmp_version: str = "2c",
    ) -> Dict[str, Any]:
        """
        Legge la tabella ARP da un router via SNMP.
        
        Args:
            address: IP del router
            community: SNMP community string (per v1/v2c)
            port: Porta SNMP (default 161)
            network_filter: Filtra risultati per questa rete CIDR (opzionale)
            timeout: Timeout in secondi
            retries: Numero di retry
            snmp_version: Versione SNMP (1, 2c, 3)
            
        Returns:
            Dict con lista di {ip, mac, interface_index}
        """
        if not self._pysnmp_available:
            return {"success": False, "error": "pysnmp not installed"}
        
        try:
            # pysnmp 7.x / 4.x compatibility
            try:
                from pysnmp.hlapi.v3arch import (
                    nextCmd, SnmpEngine, CommunityData,
                    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
                )
            except ImportError:
                from pysnmp.hlapi import (
                    nextCmd, SnmpEngine, CommunityData,
                    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
                )
            
            # Parse network filter se specificato
            net_filter = None
            if network_filter:
                try:
                    net_filter = ipaddress.ip_network(network_filter, strict=False)
                except ValueError:
                    logger.warning(f"Invalid network filter: {network_filter}")
            
            results = []
            
            # Walk ARP table (RFC 1213)
            logger.debug(f"SNMP walking ARP table on {address}:{port}")
            
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=0 if snmp_version == "1" else 1),
                UdpTransportTarget((address, port), timeout=timeout, retries=retries),
                ContextData(),
                ObjectType(ObjectIdentity(self.OID_ARP_TABLE)),
                lexicographicMode=False,
            ):
                if errorIndication:
                    logger.debug(f"SNMP error: {errorIndication}")
                    break
                elif errorStatus:
                    logger.debug(f"SNMP error: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid = str(varBind[0])
                        value = varBind[1]
                        
                        # Parse OID per estrarre ifIndex e IP
                        # Formato: .1.3.6.1.2.1.4.22.1.2.{ifIndex}.{ip1}.{ip2}.{ip3}.{ip4}
                        try:
                            oid_parts = oid.split(".")
                            if len(oid_parts) >= 15:
                                if_index = oid_parts[10]
                                ip_parts = oid_parts[11:15]
                                ip_addr = ".".join(ip_parts)
                                
                                # MAC address è il valore (bytes)
                                mac_bytes = value.asOctets() if hasattr(value, 'asOctets') else bytes(value)
                                if len(mac_bytes) == 6:
                                    mac = ":".join(f"{b:02X}" for b in mac_bytes)
                                else:
                                    mac = value.prettyPrint() if hasattr(value, 'prettyPrint') else str(value)
                                    # Normalizza formato MAC
                                    mac = mac.replace("0x", "").upper()
                                    if len(mac) == 12:
                                        mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))
                                
                                # Filtra per network se specificato
                                if net_filter:
                                    try:
                                        if ipaddress.ip_address(ip_addr) not in net_filter:
                                            continue
                                    except ValueError:
                                        continue
                                
                                # Ignora MAC vuoti o broadcast
                                if mac and mac not in ["00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"]:
                                    results.append({
                                        "ip": ip_addr,
                                        "mac": mac,
                                        "interface_index": if_index,
                                    })
                        except Exception as e:
                            logger.debug(f"Error parsing ARP entry: {e}")
                            continue
            
            logger.info(f"SNMP ARP from {address}: found {len(results)} entries")
            
            return {
                "success": True,
                "address": address,
                "entries": results,
                "count": len(results),
            }
            
        except Exception as e:
            logger.error(f"SNMP ARP table read failed for {address}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_device_info(
        self,
        address: str,
        community: str = "public",
        port: int = 161,
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """
        Ottiene informazioni base del dispositivo via SNMP.
        
        Returns:
            Dict con sysDescr, sysName
        """
        if not self._pysnmp_available:
            return {"success": False, "error": "pysnmp not installed"}
        
        try:
            # pysnmp 7.x / 4.x compatibility
            try:
                from pysnmp.hlapi.v3arch import (
                    getCmd, SnmpEngine, CommunityData,
                    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
                )
            except ImportError:
                from pysnmp.hlapi import (
                    getCmd, SnmpEngine, CommunityData,
                    UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
                )
            
            result = {}
            
            # Get sysDescr e sysName
            for oid, key in [(self.OID_SYS_DESCR, "description"), (self.OID_SYS_NAME, "name")]:
                errorIndication, errorStatus, errorIndex, varBinds = next(getCmd(
                    SnmpEngine(),
                    CommunityData(community),
                    UdpTransportTarget((address, port), timeout=timeout),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                ))
                
                if not errorIndication and not errorStatus:
                    for varBind in varBinds:
                        result[key] = str(varBind[1])
            
            # Identifica vendor dal sysDescr
            desc = result.get("description", "").lower()
            if "cisco" in desc:
                result["vendor"] = "Cisco"
            elif "mikrotik" in desc or "routeros" in desc:
                result["vendor"] = "MikroTik"
            elif "ubiquiti" in desc or "edgeos" in desc or "unifi" in desc:
                result["vendor"] = "Ubiquiti"
            elif "juniper" in desc or "junos" in desc:
                result["vendor"] = "Juniper"
            elif "hp" in desc or "procurve" in desc or "aruba" in desc:
                result["vendor"] = "HPE/Aruba"
            elif "fortinet" in desc or "fortigate" in desc:
                result["vendor"] = "Fortinet"
            elif "palo alto" in desc:
                result["vendor"] = "Palo Alto"
            else:
                result["vendor"] = "Unknown"
            
            result["success"] = True
            return result
            
        except Exception as e:
            logger.error(f"SNMP device info failed for {address}: {e}")
            return {"success": False, "error": str(e)}


# Singleton
_snmp_arp_service: Optional[SNMPArpService] = None


def get_snmp_arp_service() -> SNMPArpService:
    global _snmp_arp_service
    if _snmp_arp_service is None:
        _snmp_arp_service = SNMPArpService()
    return _snmp_arp_service

