#!/usr/bin/env python3
"""
Script di migrazione database per aggiungere colonne mancanti
"""
import sqlite3
import sys
import os

# Aggiungi il path del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_database(db_path: str = "./data/dadude.db"):
    """Aggiunge colonne mancanti al database esistente"""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} non trovato. Verrà creato al prossimo avvio.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verifica colonne esistenti in device_assignments
        cursor.execute("PRAGMA table_info(device_assignments)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in device_assignments: {columns}")
        
        # Aggiungi colonne hardware se mancanti
        if 'serial_number' not in columns:
            print("Aggiungo colonna serial_number...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN serial_number VARCHAR(100)")
        
        if 'os_version' not in columns:
            print("Aggiungo colonna os_version...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN os_version VARCHAR(100)")
        
        if 'cpu_model' not in columns:
            print("Aggiungo colonna cpu_model...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN cpu_model VARCHAR(255)")
        
        if 'cpu_cores' not in columns:
            print("Aggiungo colonna cpu_cores...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN cpu_cores INTEGER")
        
        if 'ram_total_mb' not in columns:
            print("Aggiungo colonna ram_total_mb...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN ram_total_mb INTEGER")
        
        if 'disk_total_gb' not in columns:
            print("Aggiungo colonna disk_total_gb...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN disk_total_gb INTEGER")
        
        if 'disk_free_gb' not in columns:
            print("Aggiungo colonna disk_free_gb...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN disk_free_gb INTEGER")
        
        if 'open_ports' not in columns:
            print("Aggiungo colonna open_ports...")
            cursor.execute("ALTER TABLE device_assignments ADD COLUMN open_ports JSON")
        
        # Verifica colonne esistenti in discovered_devices
        cursor.execute("PRAGMA table_info(discovered_devices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in discovered_devices: {columns}")
        
        # Aggiungi colonne hardware se mancanti
        if 'os_family' not in columns:
            print("Aggiungo colonna os_family a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN os_family VARCHAR(100)")
        
        if 'os_version' not in columns:
            print("Aggiungo colonna os_version a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN os_version VARCHAR(100)")
        
        if 'vendor' not in columns:
            print("Aggiungo colonna vendor a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN vendor VARCHAR(100)")
        
        if 'model' not in columns:
            print("Aggiungo colonna model a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN model VARCHAR(100)")
        
        if 'category' not in columns:
            print("Aggiungo colonna category a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN category VARCHAR(50)")
        
        if 'cpu_cores' not in columns:
            print("Aggiungo colonna cpu_cores a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN cpu_cores INTEGER")
        
        if 'ram_total_mb' not in columns:
            print("Aggiungo colonna ram_total_mb a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN ram_total_mb INTEGER")
        
        if 'disk_total_gb' not in columns:
            print("Aggiungo colonna disk_total_gb a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN disk_total_gb INTEGER")
        
        if 'serial_number' not in columns:
            print("Aggiungo colonna serial_number a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN serial_number VARCHAR(100)")
        
        if 'open_ports' not in columns:
            print("Aggiungo colonna open_ports a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN open_ports JSON")
        
        if 'hostname' not in columns:
            print("Aggiungo colonna hostname a discovered_devices...")
            cursor.execute("ALTER TABLE discovered_devices ADD COLUMN hostname VARCHAR(255)")
        
        # Verifica colonne esistenti in agent_assignments
        cursor.execute("PRAGMA table_info(agent_assignments)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in agent_assignments: {columns}")
        
        # Aggiungi colonne Docker Agent se mancanti
        if 'agent_type' not in columns:
            print("Aggiungo colonna agent_type a agent_assignments...")
            cursor.execute("ALTER TABLE agent_assignments ADD COLUMN agent_type VARCHAR(20) DEFAULT 'mikrotik'")
        
        if 'agent_api_port' not in columns:
            print("Aggiungo colonna agent_api_port a agent_assignments...")
            cursor.execute("ALTER TABLE agent_assignments ADD COLUMN agent_api_port INTEGER DEFAULT 8080")
        
        if 'agent_token' not in columns:
            print("Aggiungo colonna agent_token a agent_assignments...")
            cursor.execute("ALTER TABLE agent_assignments ADD COLUMN agent_token VARCHAR(255)")
        
        if 'agent_url' not in columns:
            print("Aggiungo colonna agent_url a agent_assignments...")
            cursor.execute("ALTER TABLE agent_assignments ADD COLUMN agent_url VARCHAR(255)")
        
        if 'dns_server' not in columns:
            print("Aggiungo colonna dns_server a agent_assignments...")
            cursor.execute("ALTER TABLE agent_assignments ADD COLUMN dns_server VARCHAR(255)")
        
        # Verifica se customer_id in agent_assignments accetta NULL (per auto-registrazione)
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_assignments'")
        table_def = cursor.fetchone()
        if table_def and 'customer_id' in table_def[0] and 'NOT NULL' in table_def[0]:
            print("Ricreo tabella agent_assignments per permettere customer_id NULL (auto-registrazione)...")
            
            # 1. Rinomina tabella esistente
            cursor.execute("ALTER TABLE agent_assignments RENAME TO agent_assignments_old")
            
            # 2. Crea nuova tabella con customer_id nullable
            cursor.execute("""
                CREATE TABLE agent_assignments (
                    id VARCHAR(8) PRIMARY KEY,
                    dude_agent_id VARCHAR(50),
                    customer_id VARCHAR(8),
                    name VARCHAR(100) NOT NULL,
                    address VARCHAR(255) NOT NULL,
                    port INTEGER DEFAULT 8728,
                    status VARCHAR(20) DEFAULT 'unknown',
                    last_seen DATETIME,
                    version VARCHAR(50),
                    location VARCHAR(255),
                    site_name VARCHAR(100),
                    username VARCHAR(255),
                    password VARCHAR(255),
                    use_ssl BOOLEAN DEFAULT 0,
                    connection_type VARCHAR(20) DEFAULT 'api',
                    ssh_port INTEGER DEFAULT 22,
                    ssh_key TEXT,
                    agent_type VARCHAR(20) DEFAULT 'mikrotik',
                    agent_api_port INTEGER DEFAULT 8080,
                    agent_token VARCHAR(255),
                    agent_url VARCHAR(255),
                    dns_server VARCHAR(255),
                    default_scan_type VARCHAR(50) DEFAULT 'ping',
                    auto_add_devices BOOLEAN DEFAULT 0,
                    description TEXT,
                    notes TEXT,
                    active BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """)
            
            # 3. Copia dati
            cursor.execute("""
                INSERT INTO agent_assignments 
                SELECT * FROM agent_assignments_old
            """)
            
            # 4. Elimina vecchia tabella
            cursor.execute("DROP TABLE agent_assignments_old")
            
            print("Tabella agent_assignments ricreata con successo")
        
        # Verifica colonne esistenti in credentials
        cursor.execute("PRAGMA table_info(credentials)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in credentials: {columns}")
        
        # Aggiungi is_global se mancante
        if 'is_global' not in columns:
            print("Aggiungo colonna is_global a credentials...")
            cursor.execute("ALTER TABLE credentials ADD COLUMN is_global BOOLEAN DEFAULT 0")
        
        # Verifica se customer_id accetta NULL (per credenziali globali)
        # Se esiste il vincolo NOT NULL, dobbiamo ricreare la tabella
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='credentials'")
        table_def = cursor.fetchone()
        if table_def and 'customer_id' in table_def[0] and 'NOT NULL' in table_def[0] and 'customer_id VARCHAR(8) NOT NULL' in table_def[0]:
            print("Ricreo tabella credentials per permettere customer_id NULL (credenziali globali)...")
            
            # 1. Rinomina tabella esistente
            cursor.execute("ALTER TABLE credentials RENAME TO credentials_old")
            
            # 2. Crea nuova tabella con customer_id nullable
            cursor.execute("""
                CREATE TABLE credentials (
                    id VARCHAR(8) PRIMARY KEY,
                    customer_id VARCHAR(8),
                    is_global BOOLEAN DEFAULT 0,
                    name VARCHAR(100) NOT NULL,
                    credential_type VARCHAR(50) DEFAULT 'device',
                    username VARCHAR(255),
                    password VARCHAR(255),
                    ssh_port INTEGER,
                    ssh_private_key TEXT,
                    ssh_passphrase VARCHAR(255),
                    ssh_key_type VARCHAR(20),
                    snmp_community VARCHAR(100),
                    snmp_version VARCHAR(10),
                    snmp_port INTEGER,
                    snmp_security_level VARCHAR(20),
                    snmp_auth_protocol VARCHAR(20),
                    snmp_priv_protocol VARCHAR(20),
                    snmp_auth_password VARCHAR(255),
                    snmp_priv_password VARCHAR(255),
                    wmi_domain VARCHAR(255),
                    wmi_namespace VARCHAR(255),
                    mikrotik_api_port INTEGER,
                    mikrotik_api_ssl BOOLEAN,
                    api_key VARCHAR(500),
                    api_secret VARCHAR(500),
                    api_endpoint VARCHAR(500),
                    vpn_type VARCHAR(50),
                    vpn_config TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    device_filter VARCHAR(255),
                    description TEXT,
                    notes TEXT,
                    active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """)
            
            # 3. Copia dati
            cursor.execute("""
                INSERT INTO credentials 
                SELECT id, customer_id, 
                       COALESCE(is_global, 0), 
                       name, credential_type, username, password,
                       ssh_port, ssh_private_key, ssh_passphrase, ssh_key_type,
                       snmp_community, snmp_version, snmp_port, snmp_security_level,
                       snmp_auth_protocol, snmp_priv_protocol, snmp_auth_password, snmp_priv_password,
                       wmi_domain, wmi_namespace, mikrotik_api_port, mikrotik_api_ssl,
                       api_key, api_secret, api_endpoint, vpn_type, vpn_config,
                       is_default, device_filter, description, notes, active,
                       created_at, updated_at
                FROM credentials_old
            """)
            
            # 4. Elimina vecchia tabella
            cursor.execute("DROP TABLE credentials_old")
            
            print("✓ Tabella credentials ricreata con customer_id nullable")
        
        # Verifica colonne esistenti in inventory_devices
        cursor.execute("PRAGMA table_info(inventory_devices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in inventory_devices: {columns}")
        
        # Aggiungi colonne monitoring se mancanti
        if 'monitored' not in columns:
            print("Aggiungo colonna monitored a inventory_devices...")
            cursor.execute("ALTER TABLE inventory_devices ADD COLUMN monitored BOOLEAN DEFAULT 0")
        
        if 'monitoring_type' not in columns:
            print("Aggiungo colonna monitoring_type a inventory_devices...")
            cursor.execute("ALTER TABLE inventory_devices ADD COLUMN monitoring_type VARCHAR(20) DEFAULT 'none'")
        
        if 'monitoring_agent_id' not in columns:
            print("Aggiungo colonna monitoring_agent_id a inventory_devices...")
            cursor.execute("ALTER TABLE inventory_devices ADD COLUMN monitoring_agent_id VARCHAR(8)")
        
        if 'netwatch_id' not in columns:
            print("Aggiungo colonna netwatch_id a inventory_devices...")
            cursor.execute("ALTER TABLE inventory_devices ADD COLUMN netwatch_id VARCHAR(50)")
        
        if 'last_check' not in columns:
            print("Aggiungo colonna last_check a inventory_devices...")
            cursor.execute("ALTER TABLE inventory_devices ADD COLUMN last_check DATETIME")
        
        # Crea tabella customer_credential_links se non esiste
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='customer_credential_links'
        """)
        if not cursor.fetchone():
            print("Creo tabella customer_credential_links...")
            cursor.execute("""
                CREATE TABLE customer_credential_links (
                    id VARCHAR(8) PRIMARY KEY,
                    customer_id VARCHAR(8) NOT NULL REFERENCES customers(id),
                    credential_id VARCHAR(8) NOT NULL REFERENCES credentials(id),
                    is_default BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(customer_id, credential_id)
                )
            """)
            cursor.execute("CREATE INDEX idx_cred_link_customer ON customer_credential_links(customer_id)")
            cursor.execute("CREATE INDEX idx_cred_link_credential ON customer_credential_links(credential_id)")
            print("✓ Tabella customer_credential_links creata")
        
        conn.commit()
        print("✓ Migrazione completata con successo!")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Errore durante la migrazione: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migra database aggiungendo colonne mancanti")
    parser.add_argument("--db", default="./data/dadude.db", help="Path al database")
    args = parser.parse_args()
    
    migrate_database(args.db)

