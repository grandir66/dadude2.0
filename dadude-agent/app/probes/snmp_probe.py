"""
DaDude Agent - SNMP Probe
Scansione dispositivi di rete via SNMP
"""
import asyncio
from typing import Dict, Any
from loguru import logger


async def probe(
    target: str,
    community: str = "public",
    version: str = "2c",
    port: int = 161,
) -> Dict[str, Any]:
    """
    Esegue probe SNMP su un target.
    
    Returns:
        Dict con info: sysDescr, sysName, vendor, model, seriale
    """
    from pysnmp.hlapi.v1arch.asyncio import (
        get_cmd, SnmpDispatcher, CommunityData, UdpTransportTarget,
        ObjectType, ObjectIdentity
    )
    
    logger.debug(f"SNMP probe: querying {target}:{port} community={community}")
    
    # OIDs
    oids_basic = {
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysObjectID": "1.3.6.1.2.1.1.2.0",
        "sysContact": "1.3.6.1.2.1.1.4.0",
        "sysLocation": "1.3.6.1.2.1.1.6.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
    }
    
    oids_entity = {
        "entPhysicalDescr": "1.3.6.1.2.1.47.1.1.1.1.2.1",
        "entPhysicalName": "1.3.6.1.2.1.47.1.1.1.1.7.1",
        "entPhysicalSerialNum": "1.3.6.1.2.1.47.1.1.1.1.11.1",
        "entPhysicalMfgName": "1.3.6.1.2.1.47.1.1.1.1.12.1",
        "entPhysicalModelName": "1.3.6.1.2.1.47.1.1.1.1.13.1",
        "entPhysicalFirmwareRev": "1.3.6.1.2.1.47.1.1.1.1.9.1",
    }
    
    info = {}
    dispatcher = SnmpDispatcher()
    
    try:
        transport = await UdpTransportTarget.create(
            (target, port),
            timeout=5,
            retries=1
        )
        
        # Query basic OIDs
        for name, oid in oids_basic.items():
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                    dispatcher,
                    CommunityData(community, mpModel=1 if version == "2c" else 0),
                    transport,
                    ObjectType(ObjectIdentity(oid))
                )
                
                if not errorIndication and not errorStatus:
                    for varBind in varBinds:
                        value = str(varBind[1])
                        if value and "No Such" not in value:
                            info[name] = value
            except:
                continue
        
        # Query entity OIDs
        for name, oid in oids_entity.items():
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                    dispatcher,
                    CommunityData(community, mpModel=1 if version == "2c" else 0),
                    transport,
                    ObjectType(ObjectIdentity(oid))
                )
                
                if not errorIndication and not errorStatus:
                    for varBind in varBinds:
                        value = str(varBind[1])
                        if value and "No Such" not in value:
                            info[name] = value
            except:
                continue
        
        # Query vendor-specific OIDs based on sysObjectID
        sys_oid = info.get("sysObjectID", "")
        vendor_oids = {}
        
        if sys_oid.startswith("1.3.6.1.4.1.41112"):  # Ubiquiti
            vendor_oids = {
                "ubntModel": "1.3.6.1.4.1.41112.1.6.3.3.0",
                "ubntVersion": "1.3.6.1.4.1.41112.1.6.3.6.0",
            }
            info["vendor"] = "Ubiquiti"
        elif sys_oid.startswith("1.3.6.1.4.1.14988"):  # MikroTik
            info["vendor"] = "MikroTik"
        elif sys_oid.startswith("1.3.6.1.4.1.9"):  # Cisco
            vendor_oids = {"ciscoSerial": "1.3.6.1.4.1.9.3.6.3.0"}
            info["vendor"] = "Cisco"
        elif sys_oid.startswith("1.3.6.1.4.1.6574"):  # Synology
            vendor_oids = {
                "synoModel": "1.3.6.1.4.1.6574.1.5.1.0",
                "synoSerial": "1.3.6.1.4.1.6574.1.5.2.0",
            }
            info["vendor"] = "Synology"
        elif sys_oid.startswith("1.3.6.1.4.1.318"):  # APC
            vendor_oids = {
                "apcModel": "1.3.6.1.4.1.318.1.1.1.1.1.1.0",
                "apcSerial": "1.3.6.1.4.1.318.1.1.1.1.2.3.0",
            }
            info["vendor"] = "APC"
        
        for name, oid in vendor_oids.items():
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                    dispatcher,
                    CommunityData(community, mpModel=1 if version == "2c" else 0),
                    transport,
                    ObjectType(ObjectIdentity(oid))
                )
                
                if not errorIndication and not errorStatus:
                    for varBind in varBinds:
                        value = str(varBind[1])
                        if value and "No Such" not in value:
                            info[name] = value
            except:
                continue
        
        # Extract model and serial
        info["model"] = (
            info.get("entPhysicalModelName") or
            info.get("entPhysicalName") or
            info.get("ubntModel") or
            info.get("synoModel") or
            info.get("apcModel") or
            (info.get("sysDescr", "").split()[0] if info.get("sysDescr") else None)
        )
        
        info["serial_number"] = (
            info.get("entPhysicalSerialNum") or
            info.get("ciscoSerial") or
            info.get("synoSerial") or
            info.get("apcSerial")
        )
        
        info["firmware_version"] = (
            info.get("entPhysicalFirmwareRev") or
            info.get("ubntVersion")
        )
        
    finally:
        dispatcher.transport_dispatcher.close_dispatcher()
    
    logger.info(f"SNMP probe successful: {info.get('sysName')} ({info.get('vendor', 'unknown')})")
    return info

