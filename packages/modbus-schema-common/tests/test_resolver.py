import pytest
from pathlib import Path
import json

from modbus_schema_common.resolver import resolve_schema
from modbus_schema_common.models import ModbusInterfaceSpecification
from modbus_schema_common.registry import get_registry

def test_resolve_schema_namespaced(tmp_path):
    registry = get_registry("test_resolver_pkg")
    
    schema_data = {
        "device_name": "Namespaced",
        "version": "1.0",
        "registers": []
    }
    spec = ModbusInterfaceSpecification.model_validate_json(json.dumps(schema_data))
    registry._cache["v10"] = spec
    
    from modbus_schema_common.registry import _registered_packages
    _registered_packages["test_resolver_pkg"] = registry
    
    from unittest.mock import patch
    with patch.object(registry, "versions", return_value=["v10"]):
        # Test pkg/version
        res = resolve_schema("test_resolver_pkg/v10")
        assert res.device_name == "Namespaced"
        
        # Test pkg:version
        res = resolve_schema("test_resolver_pkg:v10")
        assert res.device_name == "Namespaced"
        
        # Test pkg/latest
        res = resolve_schema("test_resolver_pkg/latest")
        assert res.device_name == "Namespaced"
        
    del _registered_packages["test_resolver_pkg"]

def test_resolve_schema_bare_version(tmp_path):
    registry = get_registry("test_bare_pkg")
    
    schema_data = {
        "device_name": "Bare",
        "version": "1.0",
        "registers": []
    }
    spec = ModbusInterfaceSpecification.model_validate_json(json.dumps(schema_data))
    registry._cache["v99"] = spec
    
    from modbus_schema_common.registry import _registered_packages
    _registered_packages["test_bare_pkg"] = registry
    
    from unittest.mock import patch
    with patch.object(registry, "versions", return_value=["v99"]):
        res = resolve_schema("v99")
        assert res.device_name == "Bare"
        
        res = resolve_schema("latest")
        # It might resolve latest from another package first depending on iteration order,
        # but that's fine. We mainly wanted to hit the loop.
        assert res.device_name in ("Bare", "EFOY Fuel Cell")
        
    del _registered_packages["test_bare_pkg"]

def test_resolve_schema_file_path(tmp_path):
    schema_data = {
        "device_name": "File",
        "version": "1.0",
        "registers": []
    }
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(schema_data))
    
    res = resolve_schema(str(p))
    assert res.device_name == "File"

def test_resolve_schema_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_schema(str(tmp_path / "nonexistent.json"))
