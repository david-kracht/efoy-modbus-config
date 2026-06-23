import pytest
import os
from pathlib import Path
from pydantic import ValidationError
from unittest.mock import patch

from modbus_common.config import AppConfig, DeviceConfig, get_devices_yaml_path

@patch('modbus_schema_common.resolver.resolve_schema')
def test_device_config_defaults(mock_resolve):
    config = DeviceConfig(host="192.168.1.100")
    assert config.name == "192.168.1.100_502"
    assert config.port == 502
    assert config.unit_id == 1
    assert config.polling_interval == 1.0
    assert config.active is True
    assert config.schema_name == "modbus_config/latest"

@patch('modbus_schema_common.resolver.resolve_schema')
def test_device_config_custom(mock_resolve):
    config = DeviceConfig(
        name="MyDevice",
        host="10.0.0.1",
        port=5020,
        unit_id=5,
        polling_interval=0.5,
        active=False,
        schema_name="modbus_config/v1.0"
    )
    assert config.name == "MyDevice"
    assert config.port == 5020
    assert config.unit_id == 5
    assert config.polling_interval == 0.5
    assert config.active is False
    assert config.schema_name == "modbus_config/v1.0"

def test_device_config_duplicate_registers():
    with pytest.raises(ValidationError) as exc_info:
        DeviceConfig(host="127.0.0.1", registers=["State", "State", "Voltage"])
    assert "Duplicate register names are not allowed" in str(exc_info.value)

@patch('modbus_schema_common.resolver.resolve_schema')
def test_app_config_load_save(mock_resolve, tmp_path):
    yaml_file = tmp_path / "devices.yaml"
    
    # Test loading missing file
    config = AppConfig.load_from_yaml(yaml_file)
    assert len(config.devices) == 0
    
    # Save a config
    config.devices.append(DeviceConfig(host="1.1.1.1", name="TestDev"))
    config.save_to_yaml(yaml_file)
    assert yaml_file.exists()
    
    # Load the saved config
    loaded = AppConfig.load_from_yaml(yaml_file)
    assert len(loaded.devices) == 1
    assert loaded.devices[0].host == "1.1.1.1"
    assert loaded.devices[0].name == "TestDev"

def test_app_config_invalid_yaml(tmp_path):
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("devices:\n  - host: 1.1.1.1\n    port: not_an_int")
    
    with pytest.raises(ValueError) as exc_info:
        AppConfig.load_from_yaml(yaml_file)
    assert "Invalid configuration in 'bad.yaml'" in str(exc_info.value)

def test_get_devices_yaml_path(tmp_path, monkeypatch):
    test_yaml = tmp_path / "custom.yaml"
    monkeypatch.setenv("MODBUS_DEVICES_YAML", str(test_yaml))
    
    assert not test_yaml.exists()
    
    # First call should create the template
    path = get_devices_yaml_path()
    assert path == test_yaml
    assert test_yaml.exists()
    
    # Second call should just return the path
    path2 = get_devices_yaml_path()
    assert path2 == test_yaml
