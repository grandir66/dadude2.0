"""
DaDude Agent - WMI Probe
Scansione dispositivi Windows via WMI/DCOM
"""
import asyncio
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from loguru import logger


_executor = ThreadPoolExecutor(max_workers=5)


async def probe(
    target: str,
    username: str,
    password: str,
    domain: str = "",
) -> Dict[str, Any]:
    """
    Esegue probe WMI su un target Windows.
    
    Returns:
        Dict con info sistema: hostname, os, cpu, ram, disco, seriale
    """
    loop = asyncio.get_event_loop()
    
    def connect():
        from impacket.dcerpc.v5.dcom import wmi as dcom_wmi
        from impacket.dcerpc.v5.dcomrt import DCOMConnection
        
        logger.debug(f"WMI probe: connecting to {target} as {domain}\\{username}")
        
        # Connessione DCOM
        dcom = DCOMConnection(
            target,
            username=username,
            password=password,
            domain=domain
        )
        
        # Query WMI
        iInterface = dcom.CoCreateInstanceEx(
            dcom_wmi.CLSID_WbemLevel1Login,
            dcom_wmi.IID_IWbemLevel1Login
        )
        iWbemLevel1Login = dcom_wmi.IWbemLevel1Login(iInterface)
        iWbemServices = iWbemLevel1Login.NTLMLogin('//./root/cimv2', dcom_wmi.NULL, dcom_wmi.NULL)
        
        info = {}
        
        def get_prop(props, name, default=""):
            if name in props:
                return props[name].get('value', default) or default
            return default
        
        # Win32_OperatingSystem
        try:
            result = iWbemServices.ExecQuery("SELECT Caption, Version, BuildNumber, OSArchitecture, SerialNumber FROM Win32_OperatingSystem")
            item = result.Next(0xffffffff, 1)[0]
            props = item.getProperties()
            info["os_name"] = str(get_prop(props, "Caption"))
            info["os_version"] = str(get_prop(props, "Version"))
            info["os_build"] = str(get_prop(props, "BuildNumber"))
            info["architecture"] = str(get_prop(props, "OSArchitecture"))
            info["os_serial"] = str(get_prop(props, "SerialNumber"))
        except Exception as e:
            logger.warning(f"WMI Win32_OperatingSystem failed: {e}")
        
        # Win32_ComputerSystem
        try:
            result = iWbemServices.ExecQuery("SELECT Name, Domain, Model, Manufacturer, TotalPhysicalMemory FROM Win32_ComputerSystem")
            item = result.Next(0xffffffff, 1)[0]
            props = item.getProperties()
            info["hostname"] = str(get_prop(props, "Name"))
            info["domain"] = str(get_prop(props, "Domain"))
            info["model"] = str(get_prop(props, "Model"))
            info["manufacturer"] = str(get_prop(props, "Manufacturer"))
            mem = get_prop(props, "TotalPhysicalMemory")
            if mem:
                try:
                    info["ram_total_mb"] = int(mem) // (1024 * 1024)
                except:
                    pass
        except Exception as e:
            logger.warning(f"WMI Win32_ComputerSystem failed: {e}")
        
        # Win32_Processor
        try:
            result = iWbemServices.ExecQuery("SELECT Name, NumberOfCores, NumberOfLogicalProcessors FROM Win32_Processor")
            item = result.Next(0xffffffff, 1)[0]
            props = item.getProperties()
            info["cpu_model"] = str(get_prop(props, "Name"))
            cores = get_prop(props, "NumberOfCores")
            if cores:
                info["cpu_cores"] = int(cores)
            threads = get_prop(props, "NumberOfLogicalProcessors")
            if threads:
                info["cpu_threads"] = int(threads)
        except Exception as e:
            logger.warning(f"WMI Win32_Processor failed: {e}")
        
        # Win32_LogicalDisk (C:)
        try:
            result = iWbemServices.ExecQuery("SELECT Size, FreeSpace FROM Win32_LogicalDisk WHERE DeviceID='C:'")
            item = result.Next(0xffffffff, 1)[0]
            props = item.getProperties()
            size = get_prop(props, "Size")
            free = get_prop(props, "FreeSpace")
            if size:
                info["disk_total_gb"] = int(size) // (1024 ** 3)
            if free:
                info["disk_free_gb"] = int(free) // (1024 ** 3)
        except Exception as e:
            logger.warning(f"WMI Win32_LogicalDisk failed: {e}")
        
        # Win32_BIOS
        try:
            result = iWbemServices.ExecQuery("SELECT SerialNumber, Manufacturer FROM Win32_BIOS")
            item = result.Next(0xffffffff, 1)[0]
            props = item.getProperties()
            info["bios_serial"] = str(get_prop(props, "SerialNumber"))
            info["bios_manufacturer"] = str(get_prop(props, "Manufacturer"))
        except Exception as e:
            logger.warning(f"WMI Win32_BIOS failed: {e}")
        
        dcom.disconnect()
        
        logger.info(f"WMI probe successful: {info.get('hostname')} ({info.get('os_name')})")
        return info
    
    return await loop.run_in_executor(_executor, connect)

