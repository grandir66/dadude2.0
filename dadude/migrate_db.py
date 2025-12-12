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
        
        # Verifica colonne esistenti in credentials
        cursor.execute("PRAGMA table_info(credentials)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonne esistenti in credentials: {columns}")
        
        # Aggiungi is_global se mancante
        if 'is_global' not in columns:
            print("Aggiungo colonna is_global a credentials...")
            cursor.execute("ALTER TABLE credentials ADD COLUMN is_global BOOLEAN DEFAULT 0")
        
        # Rendi customer_id nullable (non possibile in SQLite, ma almeno possiamo inserire NULL)
        # In SQLite non è possibile modificare le constraint, quindi per le nuove credenziali globali
        # il customer_id sarà NULL
        
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

