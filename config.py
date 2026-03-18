#!/usr/bin/env python3
"""
Configuration management for SC Signature Scanner.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

import paths


class Config:
    """Handles loading and saving configuration."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = paths.get_user_data_path() / "config.json"
        self.config_path = config_path
        self._cache: Optional[Dict[str, Any]] = None

    def load(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file. Returns cached copy if already loaded."""
        if self._cache is not None:
            return self._cache
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                    return self._cache
            except Exception as e:
                print(f"Error loading config: {e}")
        return None

    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file and update the in-memory cache."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            self._cache = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a single config value."""
        cfg = self.load()
        if cfg:
            return cfg.get(key, default)
        return default

    def set(self, key: str, value: Any) -> bool:
        """Set a single config value."""
        cfg = self.load() or {}
        cfg[key] = value
        return self.save(cfg)
