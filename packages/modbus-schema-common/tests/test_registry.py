import pytest
import os
import json
from pathlib import Path
from modbus_schema_common.registry import SchemaRegistry, register_package, get_registry
from modbus_schema_common.models import ModbusInterfaceSpecification

def test_registry_singleton():
    reg1 = get_registry("test_pkg")
    reg2 = get_registry("test_pkg")
    assert reg1 is reg2

def test_registry_register_custom_schema(tmp_path):
    registry = SchemaRegistry("custom_pkg", "schemas")
    
    # Create a dummy schema
    schema_data = {
        "device_name": "Test",
        "version": "1.0",
        "registers": []
    }
    
    # The registry loads via importlib.resources normally, so testing 
    # it with a mock cache is easier to simulate a loaded schema.
    spec = ModbusInterfaceSpecification.model_validate_json(json.dumps(schema_data))
    registry._cache["v10"] = spec
    
    loaded_spec = registry.load("10")
    assert isinstance(loaded_spec, ModbusInterfaceSpecification)
    assert loaded_spec.version == "1.0"
    assert loaded_spec.device_name == "Test"

def test_registry_missing_schema():
    registry = SchemaRegistry("modbus_config", "schemas")
    with pytest.raises(ValueError) as exc:
        registry.load("999")
    assert "not found in package data" in str(exc.value)

def test_registry_latest_no_schemas():
    registry = SchemaRegistry("modbus_common", "tests")
    with pytest.raises(RuntimeError) as exc:
        registry.latest_version()
    assert "No schema files found" in str(exc.value)

def test_get_available_schemas():
    from modbus_schema_common.registry import get_available_schemas, _registered_packages
    # Just ensure we get a list without crashing
    schemas = get_available_schemas()
    assert isinstance(schemas, list)
    
    # Let's mock entry points to hit that branch
    from unittest.mock import patch, MagicMock
    mock_ep = MagicMock()
    mock_ep.name = "fake_plugin"
    # mock_ep.load() will do nothing
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        schemas2 = get_available_schemas()
        assert isinstance(schemas2, list)
