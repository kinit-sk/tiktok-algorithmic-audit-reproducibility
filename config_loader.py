"""
config_loader.py

This module provides functionality for loading configurations dynamically.
It helps avoid circular imports by separating config loading logic.
"""

import importlib.util
import os

def load_config():
    """
    Loads configuration from the specified path or falls back to default config.py
    
    Returns:
        module: The loaded configuration module
    """
    config_path = os.environ.get("CONFIG_PATH")
    if not config_path:
        raise ValueError("CONFIG_PATH environment variable not set")
    
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config 