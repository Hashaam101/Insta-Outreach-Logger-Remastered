"""
Centralized Configuration Management for InstaCRM.

This module provides a unified interface for loading and accessing
configuration from multiple sources (environment variables, config files, etc.).
"""

import os
import json
from typing import Any, Optional, Dict
from pathlib import Path
import sys


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """
    Centralized configuration manager.
    
    Priority order (highest to lowest):
    1. Environment variables
    2. Config file (.env or config.json)
    3. Default values
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Optional path to configuration file.
        """
        self._config = {}
        self._load_defaults()
        
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)
        
        self._load_from_env()
        self._validate()
    
    def _load_defaults(self):
        """Load default configuration values."""
        self._config = {
            # Application
            'app_name': 'Insta Outreach Logger (Remastered)',
            'app_version': '1.0.0',
            
            # IPC Configuration
            'ipc_port': 65432,
            'ipc_host': '127.0.0.1',
            'ipc_max_message_size': 1048576,  # 1MB
            'ipc_timeout': 10.0,
            
            # Security
            'max_auth_attempts': 5,
            'auth_window_seconds': 300,
            'token_expiry_days': 30,
            
            # Database
            'db_path': None,  # Will be set based on PROJECT_ROOT
            'db_backup_enabled': True,
            'db_backup_interval_hours': 24,
            
            # Sync
            'sync_interval_seconds': 60,
            'sync_batch_size': 100,
            'sync_retry_attempts': 3,
            
            # Logging
            'log_level': 'INFO',
            'log_file_max_bytes': 10485760,  # 10MB
            'log_backup_count': 5,
            
            # GitHub
            'github_owner': 'hashaam101',
            'github_repo': 'Insta-Outreach-Logger-Remastered',
            
            # Paths
            'documents_dir': os.path.join(os.path.expanduser('~'), 'Documents'),
            'app_dir_name': 'Insta Outreach Logger',
        }
        
        # Set derived paths
        self._config['log_dir'] = os.path.join(
            self._config['documents_dir'],
            self._config['app_dir_name'],
            'logs'
        )
    
    def _load_from_file(self, config_file: str):
        """
        Load configuration from a JSON file.
        
        Args:
            config_file: Path to configuration file.
        """
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                self._config.update(file_config)
        except Exception as e:
            print(f"[Config] Warning: Failed to load config file: {e}")
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # Security keys (critical)
        if 'IOL_MASTER_SECRET' in os.environ:
            self._config['master_secret'] = os.environ['IOL_MASTER_SECRET']
        
        if 'IOL_IPC_AUTH_KEY' in os.environ:
            self._config['ipc_auth_key'] = os.environ['IOL_IPC_AUTH_KEY']
        
        # Optional overrides
        if 'IOL_IPC_PORT' in os.environ:
            self._config['ipc_port'] = int(os.environ['IOL_IPC_PORT'])
        
        if 'IOL_LOG_LEVEL' in os.environ:
            self._config['log_level'] = os.environ['IOL_LOG_LEVEL']
        
        if 'IOL_SYNC_INTERVAL' in os.environ:
            self._config['sync_interval_seconds'] = int(os.environ['IOL_SYNC_INTERVAL'])
    
    def _validate(self):
        """Validate configuration values."""
        # Check critical security keys
        if 'master_secret' not in self._config:
            print("[Config] WARNING: IOL_MASTER_SECRET not set. Using fallback.")
        
        if 'ipc_auth_key' not in self._config:
            print("[Config] WARNING: IOL_IPC_AUTH_KEY not set. Using fallback.")
        
        # Validate port range
        port = self._config.get('ipc_port', 0)
        if not (1024 <= port <= 65535):
            raise ConfigurationError(f"Invalid IPC port: {port}. Must be between 1024-65535.")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self._config.get('log_level', '').upper() not in valid_levels:
            self._config['log_level'] = 'INFO'
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key.
            default: Default value if key not found.
        
        Returns:
            Configuration value.
        """
        return self._config.get(key, default)
    
    def get_required(self, key: str) -> Any:
        """
        Get a required configuration value.
        
        Args:
            key: Configuration key.
        
        Returns:
            Configuration value.
        
        Raises:
            ConfigurationError: If key is not found.
        """
        if key not in self._config:
            raise ConfigurationError(f"Required configuration key '{key}' not found")
        return self._config[key]
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value at runtime.
        
        Args:
            key: Configuration key.
            value: Configuration value.
        """
        self._config[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Get all configuration as a dictionary.
        
        Returns:
            Configuration dictionary.
        """
        # Return a copy to prevent external modification
        return self._config.copy()
    
    def save_to_file(self, config_file: str):
        """
        Save configuration to a JSON file.
        
        Note: Excludes sensitive values like secrets.
        
        Args:
            config_file: Path to save configuration.
        """
        # Create a copy without sensitive data
        safe_config = self._config.copy()
        safe_config.pop('master_secret', None)
        safe_config.pop('ipc_auth_key', None)
        
        with open(config_file, 'w') as f:
            json.dump(safe_config, f, indent=2)


# Global configuration instance
_config = None


def get_config(config_file: Optional[str] = None) -> Config:
    """
    Get the global configuration instance.
    
    Args:
        config_file: Optional path to configuration file.
    
    Returns:
        Config instance.
    """
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config


def reload_config(config_file: Optional[str] = None):
    """
    Reload the global configuration.
    
    Args:
        config_file: Optional path to configuration file.
    """
    global _config
    _config = Config(config_file)
