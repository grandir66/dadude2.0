"""
DaDude - Customer Service
Gestione clienti, reti, credenziali e assegnazioni device
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models.database import (
    Customer as CustomerDB,
    Network as NetworkDB,
    Credential as CredentialDB,
    DeviceAssignment as DeviceAssignmentDB,
    AgentAssignment as AgentAssignmentDB,
    init_db, get_session
)
from ..models.customer_schemas import (
    CustomerCreate, CustomerUpdate, Customer,
    NetworkCreate, NetworkUpdate, Network,
    CredentialCreate, CredentialUpdate, Credential, CredentialSafe,
    DeviceAssignmentCreate, DeviceAssignmentUpdate, DeviceAssignment,
    AgentAssignmentCreate, AgentAssignmentUpdate, AgentAssignment, AgentAssignmentSafe,
)
from ..config import get_settings
from .encryption_service import get_encryption_service


class CustomerService:
    """Servizio per gestione multi-tenant"""
    
    def __init__(self):
        settings = get_settings()
        # Usa database sincrono (sqlite standard, non aiosqlite)
        db_url = settings.database_url.replace("+aiosqlite", "")
        self._engine = init_db(db_url)
        logger.info("CustomerService initialized with database")
    
    def _get_session(self) -> Session:
        """Ottiene sessione database"""
        return get_session(self._engine)
    
    # ==========================================
    # CUSTOMERS
    # ==========================================
    
    def create_customer(self, data: CustomerCreate) -> Customer:
        """Crea nuovo cliente"""
        session = self._get_session()
        try:
            # Verifica codice univoco
            existing = session.query(CustomerDB).filter(
                CustomerDB.code == data.code.upper()
            ).first()
            if existing:
                raise ValueError(f"Cliente con codice {data.code} già esistente")
            
            customer = CustomerDB(
                code=data.code.upper(),
                name=data.name,
                description=data.description,
                contact_name=data.contact_name,
                contact_email=data.contact_email,
                contact_phone=data.contact_phone,
                address=data.address,
                notes=data.notes,
                active=data.active,
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)
            
            logger.info(f"Created customer: {customer.code} - {customer.name}")
            return Customer.model_validate(customer)
            
        finally:
            session.close()
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Ottiene cliente per ID"""
        session = self._get_session()
        try:
            customer = session.query(CustomerDB).filter(
                CustomerDB.id == customer_id
            ).first()
            return Customer.model_validate(customer) if customer else None
        finally:
            session.close()
    
    def get_customer_by_code(self, code: str) -> Optional[Customer]:
        """Ottiene cliente per codice"""
        session = self._get_session()
        try:
            customer = session.query(CustomerDB).filter(
                CustomerDB.code == code.upper()
            ).first()
            return Customer.model_validate(customer) if customer else None
        finally:
            session.close()
    
    def list_customers(
        self,
        active_only: bool = True,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Customer]:
        """Lista clienti con filtri"""
        session = self._get_session()
        try:
            query = session.query(CustomerDB)
            
            if active_only:
                query = query.filter(CustomerDB.active == True)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(or_(
                    CustomerDB.code.ilike(search_pattern),
                    CustomerDB.name.ilike(search_pattern),
                ))
            
            query = query.order_by(CustomerDB.name)
            query = query.offset(offset).limit(limit)
            
            return [Customer.model_validate(c) for c in query.all()]
            
        finally:
            session.close()
    
    def update_customer(self, customer_id: str, data: CustomerUpdate) -> Optional[Customer]:
        """Aggiorna cliente"""
        session = self._get_session()
        try:
            customer = session.query(CustomerDB).filter(
                CustomerDB.id == customer_id
            ).first()
            
            if not customer:
                return None
            
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(customer, key, value)
            
            session.commit()
            session.refresh(customer)
            
            logger.info(f"Updated customer: {customer.code}")
            return Customer.model_validate(customer)
            
        finally:
            session.close()
    
    def delete_customer(self, customer_id: str) -> bool:
        """Elimina cliente (soft delete)"""
        session = self._get_session()
        try:
            customer = session.query(CustomerDB).filter(
                CustomerDB.id == customer_id
            ).first()
            
            if not customer:
                return False
            
            customer.active = False
            session.commit()
            
            logger.info(f"Deactivated customer: {customer.code}")
            return True
            
        finally:
            session.close()
    
    # ==========================================
    # NETWORKS
    # ==========================================
    
    def create_network(self, data: NetworkCreate) -> Network:
        """Crea nuova rete per cliente"""
        session = self._get_session()
        try:
            network = NetworkDB(
                customer_id=data.customer_id,
                name=data.name,
                network_type=data.network_type.value,
                ip_network=data.ip_network,
                gateway=data.gateway,
                vlan_id=data.vlan_id,
                vlan_name=data.vlan_name,
                dns_primary=data.dns_primary,
                dns_secondary=data.dns_secondary,
                dhcp_start=data.dhcp_start,
                dhcp_end=data.dhcp_end,
                description=data.description,
                notes=data.notes,
                active=data.active,
            )
            session.add(network)
            session.commit()
            session.refresh(network)
            
            logger.info(f"Created network: {network.name} ({network.ip_network})")
            return Network.model_validate(network)
            
        finally:
            session.close()
    
    def get_network(self, network_id: str) -> Optional[Network]:
        """Ottiene rete per ID"""
        session = self._get_session()
        try:
            network = session.query(NetworkDB).filter(
                NetworkDB.id == network_id
            ).first()
            return Network.model_validate(network) if network else None
        finally:
            session.close()
    
    def list_networks(
        self,
        customer_id: Optional[str] = None,
        network_type: Optional[str] = None,
        vlan_id: Optional[int] = None,
        active_only: bool = True,
    ) -> List[Network]:
        """Lista reti con filtri"""
        session = self._get_session()
        try:
            query = session.query(NetworkDB)
            
            if customer_id:
                query = query.filter(NetworkDB.customer_id == customer_id)
            if network_type:
                query = query.filter(NetworkDB.network_type == network_type)
            if vlan_id:
                query = query.filter(NetworkDB.vlan_id == vlan_id)
            if active_only:
                query = query.filter(NetworkDB.active == True)
            
            return [Network.model_validate(n) for n in query.all()]
            
        finally:
            session.close()
    
    def update_network(self, network_id: str, data: NetworkUpdate) -> Optional[Network]:
        """Aggiorna rete"""
        session = self._get_session()
        try:
            network = session.query(NetworkDB).filter(
                NetworkDB.id == network_id
            ).first()
            
            if not network:
                return None
            
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key == "network_type" and value:
                    value = value.value
                setattr(network, key, value)
            
            session.commit()
            session.refresh(network)
            
            return Network.model_validate(network)
            
        finally:
            session.close()
    
    def delete_network(self, network_id: str) -> bool:
        """Elimina rete"""
        session = self._get_session()
        try:
            network = session.query(NetworkDB).filter(
                NetworkDB.id == network_id
            ).first()
            
            if not network:
                return False
            
            session.delete(network)
            session.commit()
            return True
            
        finally:
            session.close()
    
    # ==========================================
    # CREDENTIALS
    # ==========================================
    
    def create_credential(self, data: CredentialCreate) -> CredentialSafe:
        """Crea nuove credenziali con encryption"""
        session = self._get_session()
        encryption = get_encryption_service()
        try:
            credential = CredentialDB(
                customer_id=data.customer_id if not data.is_global else None,
                is_global=data.is_global,
                name=data.name,
                credential_type=data.credential_type.value,
                username=data.username,
                password=encryption.encrypt(data.password) if data.password else None,
                # SSH
                ssh_port=data.ssh_port,
                ssh_private_key=encryption.encrypt(data.ssh_private_key) if data.ssh_private_key else None,
                ssh_passphrase=encryption.encrypt(data.ssh_passphrase) if data.ssh_passphrase else None,
                ssh_key_type=data.ssh_key_type,
                # SNMP
                snmp_community=data.snmp_community,
                snmp_version=data.snmp_version,
                snmp_port=data.snmp_port,
                snmp_security_level=data.snmp_security_level,
                snmp_auth_protocol=data.snmp_auth_protocol,
                snmp_priv_protocol=data.snmp_priv_protocol,
                snmp_auth_password=encryption.encrypt(data.snmp_auth_password) if data.snmp_auth_password else None,
                snmp_priv_password=encryption.encrypt(data.snmp_priv_password) if data.snmp_priv_password else None,
                # WMI
                wmi_domain=data.wmi_domain,
                wmi_namespace=data.wmi_namespace,
                # MikroTik
                mikrotik_api_port=data.mikrotik_api_port,
                mikrotik_api_ssl=data.mikrotik_api_ssl,
                # API
                api_key=encryption.encrypt(data.api_key) if data.api_key else None,
                api_secret=encryption.encrypt(data.api_secret) if data.api_secret else None,
                api_endpoint=data.api_endpoint,
                # VPN
                vpn_type=data.vpn_type,
                vpn_config=data.vpn_config,
                # Common
                is_default=data.is_default,
                device_filter=data.device_filter,
                description=data.description,
                notes=data.notes,
                active=data.active,
            )
            session.add(credential)
            session.commit()
            session.refresh(credential)
            
            logger.info(f"Created credential: {credential.name}")
            return self._to_credential_safe(credential)
            
        finally:
            session.close()
    
    def _to_credential_safe(self, cred: CredentialDB) -> CredentialSafe:
        """Converte credenziale DB in versione safe (senza password)"""
        return CredentialSafe(
            id=cred.id,
            customer_id=cred.customer_id,
            is_global=cred.is_global or False,
            name=cred.name,
            credential_type=cred.credential_type,
            username=cred.username,
            # SSH
            ssh_port=cred.ssh_port,
            ssh_key_type=cred.ssh_key_type,
            # SNMP
            snmp_community=cred.snmp_community,
            snmp_version=cred.snmp_version,
            snmp_port=cred.snmp_port,
            snmp_security_level=cred.snmp_security_level,
            snmp_auth_protocol=cred.snmp_auth_protocol,
            snmp_priv_protocol=cred.snmp_priv_protocol,
            # WMI
            wmi_domain=cred.wmi_domain,
            wmi_namespace=cred.wmi_namespace,
            # MikroTik
            mikrotik_api_port=cred.mikrotik_api_port,
            mikrotik_api_ssl=cred.mikrotik_api_ssl,
            # API
            api_endpoint=cred.api_endpoint,
            # VPN
            vpn_type=cred.vpn_type,
            # Common
            is_default=cred.is_default,
            device_filter=cred.device_filter,
            description=cred.description,
            notes=cred.notes,
            active=cred.active,
            # Flags for secrets
            has_password=bool(cred.password),
            has_ssh_key=bool(cred.ssh_private_key),
            has_api_key=bool(cred.api_key),
            has_vpn_config=bool(cred.vpn_config),
            created_at=cred.created_at,
            updated_at=cred.updated_at,
        )
    
    def get_credential(self, credential_id: str, include_secrets: bool = False) -> Optional[Any]:
        """Ottiene credenziali per ID"""
        session = self._get_session()
        try:
            cred = session.query(CredentialDB).filter(
                CredentialDB.id == credential_id
            ).first()
            
            if not cred:
                return None
            
            if include_secrets:
                return self._decrypt_credential(cred)
            return self._to_credential_safe(cred)
            
        finally:
            session.close()
    
    def _decrypt_credential(self, cred: CredentialDB) -> Credential:
        """Decripta una credenziale per uso interno"""
        encryption = get_encryption_service()
        return Credential(
            id=cred.id,
            customer_id=cred.customer_id,
            name=cred.name,
            credential_type=cred.credential_type,
            username=cred.username,
            password=encryption.decrypt(cred.password) if cred.password else None,
            # SSH
            ssh_port=cred.ssh_port,
            ssh_private_key=encryption.decrypt(cred.ssh_private_key) if cred.ssh_private_key else None,
            ssh_passphrase=encryption.decrypt(cred.ssh_passphrase) if cred.ssh_passphrase else None,
            ssh_key_type=cred.ssh_key_type,
            # SNMP
            snmp_community=cred.snmp_community,
            snmp_version=cred.snmp_version,
            snmp_port=cred.snmp_port,
            snmp_security_level=cred.snmp_security_level,
            snmp_auth_protocol=cred.snmp_auth_protocol,
            snmp_priv_protocol=cred.snmp_priv_protocol,
            snmp_auth_password=encryption.decrypt(cred.snmp_auth_password) if cred.snmp_auth_password else None,
            snmp_priv_password=encryption.decrypt(cred.snmp_priv_password) if cred.snmp_priv_password else None,
            # WMI
            wmi_domain=cred.wmi_domain,
            wmi_namespace=cred.wmi_namespace,
            # MikroTik
            mikrotik_api_port=cred.mikrotik_api_port,
            mikrotik_api_ssl=cred.mikrotik_api_ssl,
            # API
            api_key=encryption.decrypt(cred.api_key) if cred.api_key else None,
            api_secret=encryption.decrypt(cred.api_secret) if cred.api_secret else None,
            api_endpoint=cred.api_endpoint,
            # VPN
            vpn_type=cred.vpn_type,
            vpn_config=cred.vpn_config,
            # Common
            is_default=cred.is_default,
            device_filter=cred.device_filter,
            description=cred.description,
            notes=cred.notes,
            active=cred.active,
            created_at=cred.created_at,
            updated_at=cred.updated_at,
        )
    
    def list_credentials(
        self,
        customer_id: Optional[str] = None,
        credential_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CredentialSafe]:
        """Lista credenziali (senza secrets)"""
        session = self._get_session()
        try:
            query = session.query(CredentialDB)
            
            if customer_id:
                query = query.filter(CredentialDB.customer_id == customer_id)
            if credential_type:
                query = query.filter(CredentialDB.credential_type == credential_type)
            if active_only:
                query = query.filter(CredentialDB.active == True)
            
            return [self._to_credential_safe(c) for c in query.all()]
            
        finally:
            session.close()
    
    def list_global_credentials(
        self,
        credential_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CredentialSafe]:
        """Lista credenziali globali (senza customer_id)"""
        session = self._get_session()
        try:
            query = session.query(CredentialDB).filter(
                CredentialDB.is_global == True
            )
            
            if credential_type:
                query = query.filter(CredentialDB.credential_type == credential_type)
            if active_only:
                query = query.filter(CredentialDB.active == True)
            
            credentials = []
            for c in query.all():
                cred_safe = self._to_credential_safe(c)
                # Conta quanti clienti usano questa credenziale
                cred_safe.used_by_count = self._count_credential_usage(session, c.id)
                credentials.append(cred_safe)
            
            return credentials
            
        finally:
            session.close()
    
    def _count_credential_usage(self, session, credential_id: str) -> int:
        """Conta quanti clienti utilizzano una credenziale globale"""
        # Questo potrebbe essere implementato con una tabella di join
        # Per ora ritorna 0
        return 0
    
    def list_available_credentials(
        self,
        customer_id: str,
        credential_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CredentialSafe]:
        """
        Lista credenziali disponibili per un cliente.
        Include sia le credenziali del cliente che quelle globali.
        """
        session = self._get_session()
        try:
            # Credenziali del cliente
            query = session.query(CredentialDB).filter(
                or_(
                    CredentialDB.customer_id == customer_id,
                    CredentialDB.is_global == True
                )
            )
            
            if credential_type:
                query = query.filter(CredentialDB.credential_type == credential_type)
            if active_only:
                query = query.filter(CredentialDB.active == True)
            
            return [self._to_credential_safe(c) for c in query.all()]
            
        finally:
            session.close()
    
    def get_device_credential(
        self,
        customer_id: str,
        device_name: Optional[str] = None,
    ) -> Optional[Credential]:
        """
        Ottiene credenziali appropriate per un device (decriptate).
        Prima cerca match specifico, poi default del cliente.
        """
        session = self._get_session()
        try:
            # Cerca credenziali specifiche se device_name fornito
            if device_name:
                creds = session.query(CredentialDB).filter(
                    CredentialDB.customer_id == customer_id,
                    CredentialDB.active == True,
                    CredentialDB.device_filter.isnot(None),
                ).all()
                
                import fnmatch
                for cred in creds:
                    if cred.device_filter and fnmatch.fnmatch(device_name, cred.device_filter):
                        return self._decrypt_credential(cred)
            
            # Cerca credenziale di default
            default_cred = session.query(CredentialDB).filter(
                CredentialDB.customer_id == customer_id,
                CredentialDB.is_default == True,
                CredentialDB.active == True,
            ).first()
            
            return self._decrypt_credential(default_cred) if default_cred else None
            
        finally:
            session.close()
    
    def get_default_credentials_by_type(
        self,
        customer_id: str,
        credential_types: List[str] = None,
    ) -> Dict[str, Credential]:
        """
        Ottiene le credenziali di default per ogni tipo richiesto.
        
        Args:
            customer_id: ID del cliente
            credential_types: Lista di tipi da cercare (ssh, snmp, wmi, mikrotik)
                             Se None, cerca tutti i tipi disponibili
        
        Returns:
            Dict[tipo -> Credential] con credenziali decriptate
        """
        session = self._get_session()
        try:
            # Query credenziali attive del cliente
            query = session.query(CredentialDB).filter(
                CredentialDB.customer_id == customer_id,
                CredentialDB.active == True,
            )
            
            if credential_types:
                query = query.filter(CredentialDB.credential_type.in_(credential_types))
            
            # Ordina per is_default DESC per avere i default per primi
            creds = query.order_by(CredentialDB.is_default.desc()).all()
            
            # Raggruppa per tipo, prendendo il primo (che è default se esiste)
            result = {}
            for cred in creds:
                cred_type = cred.credential_type
                if cred_type not in result:
                    result[cred_type] = self._decrypt_credential(cred)
            
            return result
            
        finally:
            session.close()
    
    def get_credentials_for_auto_detect(
        self,
        customer_id: str,
        open_ports: List[Dict[str, Any]],
    ) -> List[Credential]:
        """
        Ottiene le credenziali da provare in base alle porte aperte.
        
        Logica:
        - SSH (22) aperta → credenziali ssh
        - SNMP (161) aperta → credenziali snmp
        - RDP/SMB/LDAP (3389, 445, 139, 389, 135) → credenziali wmi
        - MikroTik API (8728) → credenziali mikrotik
        
        Args:
            customer_id: ID del cliente
            open_ports: Lista porte aperte [{port, protocol, service, open}]
        
        Returns:
            Lista di Credential ordinate per priorità
        """
        # Determina quali tipi di credenziali servono
        types_needed = set()
        
        # Mappa porte → tipo credenziale
        port_type_map = {
            22: "ssh",
            23: "ssh",  # telnet, proviamo ssh
            161: "snmp",
            162: "snmp",
            3389: "wmi",  # RDP = Windows
            445: "wmi",   # SMB = Windows
            139: "wmi",   # NetBIOS = Windows
            389: "wmi",   # LDAP = Windows AD
            135: "wmi",   # RPC = Windows
            5985: "wmi",  # WinRM = Windows
            5986: "wmi",  # WinRM SSL = Windows
            8728: "mikrotik",
            8729: "mikrotik",
            8291: "mikrotik",  # Winbox
        }
        
        for port_info in open_ports:
            if port_info.get("open"):
                port = port_info.get("port")
                if port in port_type_map:
                    types_needed.add(port_type_map[port])
        
        if not types_needed:
            logger.debug(f"No credential types detected from open ports")
            return []
        
        logger.info(f"Credential types needed based on ports: {types_needed}")
        
        # Ottieni credenziali per i tipi necessari
        creds_by_type = self.get_default_credentials_by_type(
            customer_id, 
            list(types_needed)
        )
        
        # Ordina per priorità: wmi prima (più informativo), poi snmp, poi ssh
        priority_order = ["wmi", "snmp", "ssh", "mikrotik"]
        result = []
        
        for cred_type in priority_order:
            if cred_type in creds_by_type:
                result.append(creds_by_type[cred_type])
        
        # Aggiungi eventuali tipi non in priority_order
        for cred_type, cred in creds_by_type.items():
            if cred not in result:
                result.append(cred)
        
        logger.info(f"Found {len(result)} credentials for auto-detect: {[c.credential_type for c in result]}")
        return result
    
    def update_credential(self, credential_id: str, data: CredentialUpdate) -> Optional[CredentialSafe]:
        """Aggiorna credenziali esistenti"""
        session = self._get_session()
        encryption = get_encryption_service()
        try:
            cred = session.query(CredentialDB).filter(
                CredentialDB.id == credential_id
            ).first()
            
            if not cred:
                return None
            
            # Aggiorna solo i campi forniti
            update_data = data.model_dump(exclude_unset=True)
            
            # Campi da criptare se presenti
            encrypt_fields = ['password', 'ssh_private_key', 'ssh_passphrase', 
                              'snmp_auth_password', 'snmp_priv_password',
                              'api_key', 'api_secret']
            
            for key, value in update_data.items():
                if value is not None:
                    if key in encrypt_fields and value:
                        value = encryption.encrypt(value)
                    setattr(cred, key, value)
            
            session.commit()
            session.refresh(cred)
            
            logger.info(f"Updated credential: {cred.name}")
            return self._to_credential_safe(cred)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating credential: {e}")
            return None
        finally:
            session.close()
    
    def delete_credential(self, credential_id: str) -> bool:
        """Elimina credenziali"""
        session = self._get_session()
        try:
            cred = session.query(CredentialDB).filter(
                CredentialDB.id == credential_id
            ).first()
            
            if not cred:
                return False
            
            session.delete(cred)
            session.commit()
            
            logger.info(f"Deleted credential: {cred.name}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting credential: {e}")
            return False
        finally:
            session.close()
    
    # ==========================================
    # DEVICE ASSIGNMENTS
    # ==========================================
    
    def assign_device(self, data: DeviceAssignmentCreate) -> DeviceAssignment:
        """Assegna device a cliente"""
        session = self._get_session()
        try:
            # Verifica se già assegnato
            existing = session.query(DeviceAssignmentDB).filter(
                DeviceAssignmentDB.dude_device_id == data.dude_device_id
            ).first()
            
            if existing:
                raise ValueError(f"Device {data.dude_device_id} già assegnato")
            
            assignment = DeviceAssignmentDB(
                dude_device_id=data.dude_device_id,
                dude_device_name=data.dude_device_name,
                customer_id=data.customer_id,
                local_name=data.local_name,
                location=data.location,
                role=data.role.value if data.role else None,
                primary_network_id=data.primary_network_id,
                management_ip=data.management_ip,
                credential_id=data.credential_id,
                contract_type=data.contract_type.value if data.contract_type else None,
                sla_level=data.sla_level.value if data.sla_level else None,
                notes=data.notes,
                tags=data.tags,
                custom_fields=data.custom_fields,
                active=data.active,
                monitored=data.monitored,
            )
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            
            logger.info(f"Assigned device {data.dude_device_id} to customer {data.customer_id}")
            return DeviceAssignment.model_validate(assignment)
            
        finally:
            session.close()
    
    def get_device_assignment(self, dude_device_id: str) -> Optional[DeviceAssignment]:
        """Ottiene assegnazione per device ID"""
        session = self._get_session()
        try:
            assignment = session.query(DeviceAssignmentDB).filter(
                DeviceAssignmentDB.dude_device_id == dude_device_id
            ).first()
            return DeviceAssignment.model_validate(assignment) if assignment else None
        finally:
            session.close()
    
    def list_device_assignments(
        self,
        customer_id: Optional[str] = None,
        role: Optional[str] = None,
        active_only: bool = True,
    ) -> List[DeviceAssignment]:
        """Lista assegnazioni device"""
        session = self._get_session()
        try:
            query = session.query(DeviceAssignmentDB)
            
            if customer_id:
                query = query.filter(DeviceAssignmentDB.customer_id == customer_id)
            if role:
                query = query.filter(DeviceAssignmentDB.role == role)
            if active_only:
                query = query.filter(DeviceAssignmentDB.active == True)
            
            return [DeviceAssignment.model_validate(a) for a in query.all()]
            
        finally:
            session.close()
    
    def update_device_assignment(
        self,
        dude_device_id: str,
        data: DeviceAssignmentUpdate,
    ) -> Optional[DeviceAssignment]:
        """Aggiorna assegnazione device"""
        session = self._get_session()
        try:
            assignment = session.query(DeviceAssignmentDB).filter(
                DeviceAssignmentDB.dude_device_id == dude_device_id
            ).first()
            
            if not assignment:
                return None
            
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key in ["role", "contract_type", "sla_level"] and value:
                    value = value.value
                setattr(assignment, key, value)
            
            session.commit()
            session.refresh(assignment)
            
            return DeviceAssignment.model_validate(assignment)
            
        finally:
            session.close()
    
    def unassign_device(self, dude_device_id: str) -> bool:
        """Rimuove assegnazione device"""
        session = self._get_session()
        try:
            assignment = session.query(DeviceAssignmentDB).filter(
                DeviceAssignmentDB.dude_device_id == dude_device_id
            ).first()
            
            if not assignment:
                return False
            
            session.delete(assignment)
            session.commit()
            
            logger.info(f"Unassigned device {dude_device_id}")
            return True
            
        finally:
            session.close()

    # ==========================================
    # AGENT ASSIGNMENTS (SONDE)
    # ==========================================
    
    def create_agent(self, data: AgentAssignmentCreate) -> AgentAssignment:
        """Crea nuova sonda per cliente"""
        session = self._get_session()
        try:
            # Verifica cliente
            customer = session.query(CustomerDB).filter(
                CustomerDB.id == data.customer_id
            ).first()
            if not customer:
                raise ValueError(f"Customer {data.customer_id} not found")
            
            # Encrypt password e ssh_key se presenti
            enc_service = get_encryption_service()
            password = data.password
            if password:
                password = enc_service.encrypt(password)
            
            ssh_key = data.ssh_key
            if ssh_key:
                ssh_key = enc_service.encrypt(ssh_key)
            
            # Encrypt agent_token se presente
            agent_token = getattr(data, 'agent_token', None)
            if agent_token:
                agent_token = enc_service.encrypt(agent_token)
            
            # Crea sonda
            agent = AgentAssignmentDB(
                customer_id=data.customer_id,
                dude_agent_id=data.dude_agent_id,
                name=data.name,
                address=data.address,
                port=data.port,
                location=data.location,
                site_name=data.site_name,
                connection_type=data.connection_type,
                username=data.username,
                password=password,
                use_ssl=data.use_ssl,
                ssh_port=data.ssh_port,
                ssh_key=ssh_key,
                # Nuovi campi Docker Agent
                agent_type=getattr(data, 'agent_type', 'mikrotik'),
                agent_api_port=getattr(data, 'agent_api_port', 8080),
                agent_token=agent_token,
                agent_url=getattr(data, 'agent_url', None),
                dns_server=getattr(data, 'dns_server', None),
                # Altri campi
                default_scan_type=data.default_scan_type,
                auto_add_devices=data.auto_add_devices,
                assigned_networks=data.assigned_networks,
                description=data.description,
                notes=data.notes,
                active=data.active,
            )
            
            session.add(agent)
            session.commit()
            session.refresh(agent)
            
            logger.info(f"Created agent: {data.name} ({data.address})")
            return AgentAssignment.model_validate(agent)
            
        finally:
            session.close()
    
    def get_agent(self, agent_id: str, include_password: bool = False) -> Optional[AgentAssignment]:
        """Ottiene sonda per ID"""
        session = self._get_session()
        try:
            agent = session.query(AgentAssignmentDB).filter(
                AgentAssignmentDB.id == agent_id
            ).first()
            
            if not agent:
                return None
            
            result = AgentAssignment.model_validate(agent)
            
            enc_service = get_encryption_service()
            
            # Decrypt password se richiesto
            if include_password and agent.password:
                try:
                    result.password = enc_service.decrypt(agent.password)
                except:
                    result.password = agent.password  # Fallback a valore in chiaro
            else:
                result.password = None
            
            # Decrypt agent_token se presente
            if include_password and agent.agent_token:
                try:
                    result.agent_token = enc_service.decrypt(agent.agent_token)
                except:
                    result.agent_token = agent.agent_token  # Fallback a valore in chiaro
            
            return result
            
        finally:
            session.close()
    
    def list_agents(
        self,
        customer_id: Optional[str] = None,
        active_only: bool = True,
        include_password: bool = False,
    ) -> List[AgentAssignmentSafe]:
        """Lista sonde"""
        session = self._get_session()
        try:
            query = session.query(AgentAssignmentDB)
            
            if customer_id:
                query = query.filter(AgentAssignmentDB.customer_id == customer_id)
            if active_only:
                query = query.filter(AgentAssignmentDB.active == True)
            
            agents = query.order_by(AgentAssignmentDB.name).all()
            
            results = []
            for agent in agents:
                safe = AgentAssignmentSafe.model_validate(agent)
                results.append(safe)
            
            return results
            
        finally:
            session.close()
    
    def update_agent(self, agent_id: str, data: AgentAssignmentUpdate) -> Optional[AgentAssignment]:
        """Aggiorna sonda"""
        session = self._get_session()
        try:
            agent = session.query(AgentAssignmentDB).filter(
                AgentAssignmentDB.id == agent_id
            ).first()
            
            if not agent:
                return None
            
            update_data = data.model_dump(exclude_unset=True)
            
            # Encrypt password, ssh_key e agent_token se presenti
            enc_service = get_encryption_service()
            if "password" in update_data and update_data["password"]:
                update_data["password"] = enc_service.encrypt(update_data["password"])
            if "ssh_key" in update_data and update_data["ssh_key"]:
                update_data["ssh_key"] = enc_service.encrypt(update_data["ssh_key"])
            if "agent_token" in update_data and update_data["agent_token"]:
                update_data["agent_token"] = enc_service.encrypt(update_data["agent_token"])
            
            for key, value in update_data.items():
                setattr(agent, key, value)
            
            session.commit()
            session.refresh(agent)
            
            logger.info(f"Updated agent: {agent.name}")
            return AgentAssignment.model_validate(agent)
            
        finally:
            session.close()
    
    def delete_agent(self, agent_id: str) -> bool:
        """Elimina sonda"""
        session = self._get_session()
        try:
            agent = session.query(AgentAssignmentDB).filter(
                AgentAssignmentDB.id == agent_id
            ).first()
            
            if not agent:
                return False
            
            session.delete(agent)
            session.commit()
            
            logger.info(f"Deleted agent: {agent.name}")
            return True
            
        finally:
            session.close()
    
    def update_agent_status(self, agent_id: str, status: str, version: str = None) -> bool:
        """Aggiorna stato sonda"""
        session = self._get_session()
        try:
            agent = session.query(AgentAssignmentDB).filter(
                AgentAssignmentDB.id == agent_id
            ).first()
            
            if not agent:
                return False
            
            agent.status = status
            agent.last_seen = datetime.utcnow()
            if version:
                agent.version = version
            
            session.commit()
            return True
            
        finally:
            session.close()


# Singleton
_customer_service: Optional[CustomerService] = None


def get_customer_service() -> CustomerService:
    """Get singleton CustomerService instance"""
    global _customer_service
    if _customer_service is None:
        _customer_service = CustomerService()
    return _customer_service
