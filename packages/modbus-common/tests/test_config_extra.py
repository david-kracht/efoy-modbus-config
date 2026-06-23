import pytest
import os
from pathlib import Path
from pydantic import ValidationError
from unittest.mock import patch
from modbus_common.config import AppConfig, DeviceConfig, get_devices_yaml_path

def test_get_devices_yaml_path_creates_file(tmp_path, monkeypatch):
    target = tmp_path / "custom.yaml"
    monkeypatch.setenv("MODBUS_DEVICES_YAML", str(target))
    
    assert not target.exists()
    get_devices_yaml_path()
    assert target.exists()

def test_device_config_invalid_schema():
    with patch("modbus_schema_common.resolver.resolve_schema", side_effect=ValueError("boom")):
        with pytest.raises(ValidationError) as exc:
            DeviceConfig(host="10.0.0.1", schema_name="bad_schema")
        assert "Invalid schema" in str(exc.value)

def test_device_config_compact_dict():
    # Test that defaults are not in the dictionary
    d = DeviceConfig(host="10.0.0.1")
    compact = d.to_compact_dict()
    assert "host" in compact
    assert "port" not in compact
    assert "unit_id" not in compact
    assert "polling_interval" not in compact
    assert "active" not in compact
    
    # Test that overrides ARE in the dictionary
    d2 = DeviceConfig(host="10.0.0.1", port=1502, active=False, polling_interval=5.0)
    compact2 = d2.to_compact_dict()
    assert compact2["port"] == 1502
    assert compact2["active"] is False
    assert compact2["polling_interval"] == 5.0

def test_app_config_load_invalid_validation(tmp_path):
    p = tmp_path / "bad.yaml"
    # Port must be int, but we provide string "abc"
    p.write_text("devices:\n  - host: 127.0.0.1\n    port: abc")
    with pytest.raises(ValueError) as exc:
        AppConfig.load_from_yaml(p)
    assert "Invalid configuration" in str(exc.value)
