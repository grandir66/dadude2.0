"""
DaDude - Inventory Models
Database models per inventario dispositivi: Windows, Linux, Network Devices, MikroTik
"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
import uuid

from .database import Base


def generate_uuid():
    return uuid.uuid4().hex[:8]


# ==========================================
# ENUMS
# ==========================================

class DeviceType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MIKROTIK = "mikrotik"
    NETWORK = "network"  # Switch, Firewall, AP generico
    PRINTER = "printer"
    CAMERA = "camera"
    VOIP = "voip"
    OTHER = "other"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Parzialmente funzionante
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class MonitorSource(str, Enum):
    DUDE = "dude"  # Monitorato da The Dude
    AGENT = "agent"  # Agent locale installato
    SNMP = "snmp"  # Polling SNMP
    WMI = "wmi"  # Windows WMI
    SSH = "ssh"  # SSH polling
    API = "api"  # API specifica


# ==========================================
# INVENTARIO BASE
# ==========================================

class InventoryDevice(Base):
    """
    Dispositivo inventariato - tabella base per tutti i tipi
    """
    __tablename__ = "inventory_devices"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    customer_id = Column(String(8), ForeignKey("customers.id"), nullable=False)
    
    # Credenziale associata per accesso al device
    credential_id = Column(String(8), ForeignKey("credentials.id"), nullable=True)
    
    # Identificazione
    name = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True)
    
    # Tipo e categoria
    device_type = Column(String(20), default="other")  # windows, linux, mikrotik, network, etc
    category = Column(String(50), nullable=True)  # server, workstation, router, switch, etc
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    asset_tag = Column(String(50), nullable=True)  # Codice inventario aziendale
    
    # Rete principale
    primary_ip = Column(String(50), nullable=True)
    primary_mac = Column(String(20), nullable=True)
    mac_address = Column(String(20), nullable=True)  # Alias per retrocompatibilità

    # Identificazione
    identified_by = Column(String(50), nullable=True)  # probe_wmi, probe_ssh, probe_snmp, mac_vendor
    credential_used = Column(String(255), nullable=True)  # Nome della credenziale usata
    open_ports = Column(JSON, nullable=True)  # Servizi rilevati: [{"port": 80, "protocol": "tcp", "service": "http"}]

    # Location
    site_name = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)  # Rack, stanza, piano
    
    # Stato e monitoring
    status = Column(String(20), default="unknown")
    monitor_source = Column(String(20), nullable=True)  # dude, agent, snmp, etc
    dude_device_id = Column(String(50), nullable=True)  # ID in The Dude se presente
    last_seen = Column(DateTime, nullable=True)
    last_scan = Column(DateTime, nullable=True)
    
    # Sistema operativo (generico)
    os_family = Column(String(50), nullable=True)  # Windows, Linux, RouterOS, IOS
    os_version = Column(String(100), nullable=True)
    os_build = Column(String(50), nullable=True)
    architecture = Column(String(20), nullable=True)  # x64, x86, ARM
    
    # Hardware base
    cpu_model = Column(String(200), nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    cpu_threads = Column(Integer, nullable=True)
    ram_total_gb = Column(Float, nullable=True)
    
    # Note e metadata
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["critical", "production", "backup"]
    custom_fields = Column(JSON, nullable=True)  # Campi personalizzati
    
    # Audit
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    credential = relationship("Credential", foreign_keys=[credential_id])
    network_interfaces = relationship("NetworkInterface", back_populates="device", cascade="all, delete-orphan")
    disks = relationship("DiskInfo", back_populates="device", cascade="all, delete-orphan")
    software = relationship("InstalledSoftware", back_populates="device", cascade="all, delete-orphan")
    services = relationship("ServiceInfo", back_populates="device", cascade="all, delete-orphan")
    windows_details = relationship("WindowsDetails", back_populates="device", uselist=False, cascade="all, delete-orphan")
    linux_details = relationship("LinuxDetails", back_populates="device", uselist=False, cascade="all, delete-orphan")
    mikrotik_details = relationship("MikroTikDetails", back_populates="device", uselist=False, cascade="all, delete-orphan")
    network_device_details = relationship("NetworkDeviceDetails", back_populates="device", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_inventory_customer', 'customer_id'),
        Index('idx_inventory_type', 'device_type'),
        Index('idx_inventory_ip', 'primary_ip'),
        Index('idx_inventory_status', 'status'),
        Index('idx_inventory_dude', 'dude_device_id'),
    )


# ==========================================
# COMPONENTI COMUNI
# ==========================================

class NetworkInterface(Base):
    """Interfacce di rete del dispositivo"""
    __tablename__ = "inventory_network_interfaces"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False)
    
    name = Column(String(100), nullable=False)  # eth0, ether1, Ethernet 1
    description = Column(String(255), nullable=True)
    interface_type = Column(String(50), nullable=True)  # ethernet, wifi, bridge, vlan
    
    mac_address = Column(String(20), nullable=True)
    ip_addresses = Column(JSON, nullable=True)  # [{"ip": "192.168.1.1", "mask": "24", "type": "static"}]
    
    speed_mbps = Column(Integer, nullable=True)
    duplex = Column(String(20), nullable=True)
    mtu = Column(Integer, nullable=True)
    
    admin_status = Column(String(20), nullable=True)  # up, down
    oper_status = Column(String(20), nullable=True)  # up, down
    
    vlan_id = Column(Integer, nullable=True)
    is_management = Column(Boolean, default=False)
    
    # Traffic stats (ultimo polling)
    bytes_in = Column(Integer, nullable=True)
    bytes_out = Column(Integer, nullable=True)
    packets_in = Column(Integer, nullable=True)
    packets_out = Column(Integer, nullable=True)
    errors_in = Column(Integer, nullable=True)
    errors_out = Column(Integer, nullable=True)
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="network_interfaces")
    
    __table_args__ = (
        Index('idx_nic_device', 'device_id'),
        Index('idx_nic_mac', 'mac_address'),
    )


class DiskInfo(Base):
    """Informazioni dischi/storage"""
    __tablename__ = "inventory_disks"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False)
    
    name = Column(String(100), nullable=False)  # C:, /dev/sda, disk1
    mount_point = Column(String(255), nullable=True)
    
    disk_type = Column(String(20), nullable=True)  # hdd, ssd, nvme, raid
    filesystem = Column(String(50), nullable=True)  # NTFS, ext4, ZFS
    
    size_gb = Column(Float, nullable=True)
    used_gb = Column(Float, nullable=True)
    free_gb = Column(Float, nullable=True)
    percent_used = Column(Float, nullable=True)
    
    model = Column(String(200), nullable=True)
    serial = Column(String(100), nullable=True)
    smart_status = Column(String(50), nullable=True)  # OK, Warning, Critical
    
    is_system = Column(Boolean, default=False)
    is_removable = Column(Boolean, default=False)
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="disks")
    
    __table_args__ = (
        Index('idx_disk_device', 'device_id'),
    )


class InstalledSoftware(Base):
    """Software installato"""
    __tablename__ = "inventory_software"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=True)
    vendor = Column(String(200), nullable=True)
    
    install_date = Column(DateTime, nullable=True)
    install_location = Column(String(500), nullable=True)
    
    size_mb = Column(Float, nullable=True)
    is_update = Column(Boolean, default=False)  # Windows Update/Patch
    
    license_key = Column(String(255), nullable=True)  # Se rilevabile
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="software")
    
    __table_args__ = (
        Index('idx_software_device', 'device_id'),
        Index('idx_software_name', 'name'),
    )


class ServiceInfo(Base):
    """Servizi/daemon in esecuzione"""
    __tablename__ = "inventory_services"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    service_type = Column(String(50), nullable=True)  # windows_service, systemd, docker
    
    status = Column(String(20), nullable=True)  # running, stopped, disabled
    start_type = Column(String(20), nullable=True)  # auto, manual, disabled
    
    user_account = Column(String(100), nullable=True)  # Account che esegue il servizio
    executable_path = Column(String(500), nullable=True)
    
    pid = Column(Integer, nullable=True)
    memory_mb = Column(Float, nullable=True)
    cpu_percent = Column(Float, nullable=True)
    
    port = Column(Integer, nullable=True)  # Porta in ascolto se applicabile
    
    is_critical = Column(Boolean, default=False)  # Marcato come critico
    monitored = Column(Boolean, default=False)  # Se monitorato attivamente
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="services")
    
    __table_args__ = (
        Index('idx_service_device', 'device_id'),
        Index('idx_service_status', 'status'),
    )


# ==========================================
# DETTAGLI WINDOWS
# ==========================================

class WindowsDetails(Base):
    """Dettagli specifici Windows"""
    __tablename__ = "inventory_windows_details"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False, unique=True)
    
    # Windows specifico
    edition = Column(String(100), nullable=True)  # Pro, Enterprise, Server Standard
    product_key = Column(String(50), nullable=True)
    activation_status = Column(String(50), nullable=True)
    
    # Domain
    domain_role = Column(String(50), nullable=True)  # Workstation, Member Server, DC
    domain_name = Column(String(255), nullable=True)
    ou_path = Column(String(500), nullable=True)  # Distinguished Name in AD
    
    # Hardware extra
    bios_version = Column(String(100), nullable=True)
    bios_date = Column(DateTime, nullable=True)
    secure_boot = Column(Boolean, nullable=True)
    tpm_version = Column(String(20), nullable=True)
    
    # Updates
    last_update_check = Column(DateTime, nullable=True)
    pending_updates = Column(Integer, nullable=True)
    last_reboot = Column(DateTime, nullable=True)
    uptime_days = Column(Float, nullable=True)
    
    # Security
    antivirus_name = Column(String(100), nullable=True)
    antivirus_status = Column(String(50), nullable=True)
    firewall_enabled = Column(Boolean, nullable=True)
    bitlocker_status = Column(String(50), nullable=True)
    
    # Users
    local_admins = Column(JSON, nullable=True)  # Lista admin locali
    logged_users = Column(JSON, nullable=True)  # Utenti loggati
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="windows_details")


# ==========================================
# DETTAGLI LINUX
# ==========================================

class LinuxDetails(Base):
    """Dettagli specifici Linux"""
    __tablename__ = "inventory_linux_details"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False, unique=True)
    
    # Distro
    distro_name = Column(String(100), nullable=True)  # Ubuntu, CentOS, Debian
    distro_version = Column(String(50), nullable=True)
    distro_codename = Column(String(50), nullable=True)
    
    # Kernel
    kernel_version = Column(String(100), nullable=True)
    kernel_arch = Column(String(20), nullable=True)
    
    # Package manager
    package_manager = Column(String(20), nullable=True)  # apt, yum, dnf, pacman
    packages_installed = Column(Integer, nullable=True)
    packages_upgradable = Column(Integer, nullable=True)
    
    # System
    init_system = Column(String(20), nullable=True)  # systemd, sysvinit
    selinux_status = Column(String(20), nullable=True)
    
    # Hardware
    virtualization = Column(String(50), nullable=True)  # KVM, VMware, Hyper-V, bare-metal
    
    # Uptime
    last_reboot = Column(DateTime, nullable=True)
    uptime_days = Column(Float, nullable=True)
    load_average = Column(String(50), nullable=True)  # "0.5, 0.3, 0.2"
    
    # Users
    root_login_enabled = Column(Boolean, nullable=True)
    ssh_port = Column(Integer, nullable=True)
    logged_users = Column(JSON, nullable=True)
    
    # Docker/Containers
    docker_installed = Column(Boolean, nullable=True)
    docker_version = Column(String(50), nullable=True)
    containers_running = Column(Integer, nullable=True)
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="linux_details")


# ==========================================
# DETTAGLI MIKROTIK
# ==========================================

class MikroTikDetails(Base):
    """Dettagli specifici MikroTik RouterOS"""
    __tablename__ = "inventory_mikrotik_details"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False, unique=True)
    
    # RouterOS
    routeros_version = Column(String(50), nullable=True)
    routeros_channel = Column(String(20), nullable=True)  # stable, long-term, testing
    firmware_version = Column(String(50), nullable=True)
    factory_firmware = Column(String(50), nullable=True)
    
    # Hardware
    board_name = Column(String(100), nullable=True)
    platform = Column(String(50), nullable=True)  # tile, arm, x86, mipsbe
    cpu_model = Column(String(100), nullable=True)
    cpu_count = Column(Integer, nullable=True)
    cpu_frequency = Column(Integer, nullable=True)  # MHz
    cpu_load = Column(Float, nullable=True)  # %
    
    memory_total_mb = Column(Integer, nullable=True)
    memory_free_mb = Column(Integer, nullable=True)
    hdd_total_mb = Column(Integer, nullable=True)
    hdd_free_mb = Column(Integer, nullable=True)
    
    # Identity
    identity = Column(String(100), nullable=True)
    
    # License
    license_level = Column(String(20), nullable=True)  # free, p1, p2, ...
    license_key = Column(String(50), nullable=True)
    
    # Features enabled
    has_wireless = Column(Boolean, nullable=True)
    has_lte = Column(Boolean, nullable=True)
    has_gps = Column(Boolean, nullable=True)
    
    # Dude Agent
    dude_agent_enabled = Column(Boolean, nullable=True)
    dude_agent_status = Column(String(20), nullable=True)  # connected, disconnected
    dude_server_address = Column(String(100), nullable=True)
    
    # Uptime
    uptime = Column(String(100), nullable=True)
    last_reboot = Column(DateTime, nullable=True)
    
    # Routing
    bgp_peers = Column(Integer, nullable=True)
    ospf_neighbors = Column(Integer, nullable=True)
    
    # Firewall rules count
    filter_rules = Column(Integer, nullable=True)
    nat_rules = Column(Integer, nullable=True)
    mangle_rules = Column(Integer, nullable=True)
    
    # VPN
    ipsec_peers = Column(Integer, nullable=True)
    l2tp_clients = Column(Integer, nullable=True)
    pptp_clients = Column(Integer, nullable=True)
    wireguard_peers = Column(Integer, nullable=True)
    
    # Queues
    simple_queues = Column(Integer, nullable=True)
    queue_trees = Column(Integer, nullable=True)
    
    # Netwatch configured
    netwatch_count = Column(Integer, nullable=True)
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="mikrotik_details")


# ==========================================
# DETTAGLI APPARATI DI RETE GENERICI
# ==========================================

class NetworkDeviceDetails(Base):
    """Dettagli apparati di rete (switch, firewall, AP)"""
    __tablename__ = "inventory_network_device_details"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    device_id = Column(String(8), ForeignKey("inventory_devices.id"), nullable=False, unique=True)
    
    # Tipo apparato
    device_class = Column(String(50), nullable=True)  # switch, router, firewall, ap, controller
    
    # Vendor specific
    vendor = Column(String(50), nullable=True)  # Cisco, HP, Ubiquiti, Fortinet
    firmware_version = Column(String(100), nullable=True)
    
    # Capabilities
    is_managed = Column(Boolean, nullable=True)
    supports_snmp = Column(Boolean, nullable=True)
    snmp_version = Column(String(10), nullable=True)  # v1, v2c, v3
    snmp_community = Column(String(100), nullable=True)
    
    supports_ssh = Column(Boolean, nullable=True)
    supports_telnet = Column(Boolean, nullable=True)
    supports_web = Column(Boolean, nullable=True)
    
    # Switch specifico
    total_ports = Column(Integer, nullable=True)
    ports_up = Column(Integer, nullable=True)
    poe_capable = Column(Boolean, nullable=True)
    poe_budget_watts = Column(Float, nullable=True)
    poe_consumed_watts = Column(Float, nullable=True)
    
    stacking_enabled = Column(Boolean, nullable=True)
    stack_member_id = Column(Integer, nullable=True)
    
    # VLANs
    vlans_configured = Column(JSON, nullable=True)  # [{"id": 10, "name": "Management"}, ...]
    
    # Spanning Tree
    stp_enabled = Column(Boolean, nullable=True)
    stp_root_bridge = Column(Boolean, nullable=True)
    
    # Wireless AP specifico
    ap_clients_connected = Column(Integer, nullable=True)
    ssids_configured = Column(JSON, nullable=True)
    radio_channels = Column(JSON, nullable=True)
    
    # Firewall specifico
    fw_policies_count = Column(Integer, nullable=True)
    fw_active_sessions = Column(Integer, nullable=True)
    vpn_tunnels_count = Column(Integer, nullable=True)
    
    last_updated = Column(DateTime, default=func.now())
    
    device = relationship("InventoryDevice", back_populates="network_device_details")


# ==========================================
# NETWATCH / MONITORING CONFIG
# ==========================================

class NetwatchConfig(Base):
    """Configurazione Netwatch su router MikroTik"""
    __tablename__ = "netwatch_configs"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    customer_id = Column(String(8), ForeignKey("customers.id"), nullable=False)
    agent_id = Column(String(8), ForeignKey("agent_assignments.id"), nullable=False)
    
    # Target
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)  # IP o hostname da monitorare
    port = Column(Integer, nullable=True)  # Se vuoto = ICMP
    
    # Timing
    interval = Column(String(20), default="30s")
    timeout = Column(String(20), default="3s")
    
    # Status
    status = Column(String(20), default="unknown")  # up, down, unknown
    last_check = Column(DateTime, nullable=True)
    last_change = Column(DateTime, nullable=True)
    
    # Actions (script RouterOS)
    up_script = Column(Text, nullable=True)
    down_script = Column(Text, nullable=True)
    
    # Config sul router
    mikrotik_id = Column(String(20), nullable=True)  # ID del netwatch su RouterOS
    
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_netwatch_customer', 'customer_id'),
        Index('idx_netwatch_agent', 'agent_id'),
    )


# ==========================================
# DUDE AGENT REGISTRY
# ==========================================

class DudeAgent(Base):
    """Registry agent The Dude - sincronizzato dal server"""
    __tablename__ = "dude_agents"
    
    id = Column(String(8), primary_key=True, default=generate_uuid)
    dude_id = Column(String(50), nullable=False, unique=True)  # ID in The Dude
    
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    
    status = Column(String(20), default="unknown")  # online, offline
    version = Column(String(50), nullable=True)
    
    # Collegamento a customer (opzionale)
    customer_id = Column(String(8), ForeignKey("customers.id"), nullable=True)
    agent_assignment_id = Column(String(8), ForeignKey("agent_assignments.id"), nullable=True)
    
    last_seen = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_dude_agent_dude_id', 'dude_id'),
        Index('idx_dude_agent_customer', 'customer_id'),
    )
