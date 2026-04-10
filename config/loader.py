"""Configuration loader with YAML support and dot notation access."""

import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml


class Config:
    """Configuration manager supporting YAML files and dot notation access."""

    def __init__(self):
        self._config: dict = {}
        self._config_dir = Path(__file__).parent

    def load(self, config_path: Optional[Union[str, Path]] = None) -> "Config":
        """Load configuration from YAML files.

        Args:
            config_path: Path to main config file. If None, uses settings.yaml in config dir.

        Returns:
            Self for method chaining.
        """
        if config_path is None:
            config_path = self._config_dir / "settings.yaml"
        else:
            config_path = Path(config_path)

        # Load main config
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # Merge secrets.yaml if it exists (optional)
        secrets_path = self._config_dir / "secrets.yaml"
        if secrets_path.exists():
            with open(secrets_path, "r", encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}
                self._merge(secrets)

        return self

    def _merge(self, other: dict, target: Optional[dict] = None) -> None:
        """Recursively merge dictionary into config."""
        if target is None:
            target = self._config

        for key, value in other.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge(value, target[key])
            else:
                target[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key: Dot-separated key path (e.g., "data.cache_dir").
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> "Config":
        """Set configuration value using dot notation.

        Args:
            key: Dot-separated key path.
            value: Value to set.

        Returns:
            Self for method chaining.
        """
        keys = key.split(".")
        target = self._config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value
        return self

    def to_dict(self) -> dict:
        """Return configuration as dictionary."""
        return self._config.copy()

    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access with dot notation."""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """Check if key exists using dot notation."""
        return self.get(key) is not None


# Global config instance
config = Config().load()
