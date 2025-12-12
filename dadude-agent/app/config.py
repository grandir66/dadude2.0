"""
DaDude Agent - Configuration
"""
import os
import json
from typing import Optional, List, Union, Any
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Configurazione agent"""
    
    # Server
    server_url: str = "http://localhost:8000"
    
    # Agent Identity
    agent_id: str = "agent-001"
    agent_name: str = "DaDude Agent"
    agent_token: str = "change-me-in-production"
    
    # Polling
    poll_interval: int = 60  # seconds
    
    # DNS - accetta stringa singola, lista separata da virgole, o JSON array
    dns_servers: List[str] = ["8.8.8.8", "1.1.1.1"]
    
    # API
    api_port: int = 8080
    
    # Logging
    log_level: str = "INFO"
    
    @field_validator('dns_servers', mode='before')
    @classmethod
    def parse_dns_servers(cls, v: Any) -> List[str]:
        """Converte dns_servers da vari formati a lista"""
        if v is None:
            return ["8.8.8.8", "1.1.1.1"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Prova prima come JSON
            v = v.strip()
            if v.startswith('['):
                try:
                    return json.loads(v)
                except:
                    pass
            # Altrimenti splitta per virgola
            return [s.strip() for s in v.split(',') if s.strip()]
        return ["8.8.8.8"]
    
    class Config:
        env_prefix = "DADUDE_"
        env_file = ".env"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Try to load from config file
        config_paths = [
            "/app/config/config.json",
            "./config/config.json",
            os.path.expanduser("~/.dadude-agent/config.json"),
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path) as f:
                        config_data = json.load(f)
                    
                    # Override with config file values
                    for key, value in config_data.items():
                        if hasattr(self, key):
                            setattr(self, key, value)
                    
                    break
                except Exception:
                    pass


@lru_cache()
def get_settings() -> Settings:
    """Ottieni settings (cached)"""
    return Settings()

