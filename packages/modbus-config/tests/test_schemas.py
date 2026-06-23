import pytest
from modbus_config import versions, load

def test_all_bundled_schemas_are_valid():
    """
    Ensure all schemas bundled in modbus_config can be successfully parsed
    into ModbusInterfaceSpecification models without validation errors.
    """
    schemas = versions()
    assert len(schemas) > 0, "No bundled schemas found"
    
    for schema_name in schemas:
        spec = load(schema_name)
        assert spec.version is not None
        assert isinstance(spec.registers, list)
