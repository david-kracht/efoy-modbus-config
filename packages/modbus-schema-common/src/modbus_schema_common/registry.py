from __future__ import annotations

import re
from importlib.resources import files
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from modbus_schema_common.models import ModbusInterfaceSpecification

# Global registry of namespaces (package names -> SchemaRegistry instances)
_registered_packages: dict[str, SchemaRegistry] = {}


class SchemaRegistry:
    def __init__(self, package_name: str, schema_subdir: str = "schemas"):
        self.package_name = package_name
        self.schema_subdir = schema_subdir
        self._cache: dict[str, ModbusInterfaceSpecification] = {}
        self._VERSION_RE = re.compile(r"^v(\d+)\.json$")

    def _normalise(self, version: str | int) -> str:
        v = str(version).strip()
        if re.fullmatch(r"\d+", v):
            return f"v{v}"
        if re.fullmatch(r"v\d+", v):
            return v
        raise ValueError(
            f"Invalid version specifier {version!r}. "
            "Expected an integer (1), a bare string ('1'), or a prefixed string ('v1')."
        )

    def versions(self) -> list[str]:
        try:
            schema_dir = files(f"{self.package_name}.{self.schema_subdir}")
            keys: list[str] = []
            for item in schema_dir.iterdir():
                m = self._VERSION_RE.match(item.name)
                if m:
                    keys.append(f"v{m.group(1)}")
            return sorted(keys, key=lambda k: int(k[1:]))
        except Exception:
            return []

    def load(self, version: str | int) -> ModbusInterfaceSpecification:
        from modbus_schema_common.models import ModbusInterfaceSpecification

        key = self._normalise(version)
        if key in self._cache:
            return self._cache[key]

        schema_dir = files(f"{self.package_name}.{self.schema_subdir}")
        resource = schema_dir.joinpath(f"{key}.json")
        try:
            data = resource.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as exc:
            available = self.versions()
            raise ValueError(
                f"Schema version {key!r} not found in package data for {self.package_name}. "
                f"Available versions: {available}"
            ) from exc

        spec = ModbusInterfaceSpecification.model_validate_json(data)
        self._cache[key] = spec
        return spec

    def latest_version(self) -> str:
        available = self.versions()
        if not available:
            raise RuntimeError(
                f"No schema files found in {self.package_name}.{self.schema_subdir}."
            )
        return available[-1]

    def latest(self) -> ModbusInterfaceSpecification:
        return self.load(self.latest_version())


def register_package(name: str, schema_subdir: str = "schemas") -> SchemaRegistry:
    registry = SchemaRegistry(name, schema_subdir)
    _registered_packages[name] = registry
    return registry


def get_registry(package_name: str) -> SchemaRegistry:
    if package_name not in _registered_packages:
        return register_package(package_name)
    return _registered_packages[package_name]


def get_available_schemas() -> list[str]:
    """
    Returns a list of all available schema identifiers in the format 'pkg/version'
    across all currently registered packages. Also includes 'pkg/latest'.
    """
    # Discover packages via Python entry points (group "modbus.schema")
    import importlib.metadata
    try:
        eps = importlib.metadata.entry_points(group="modbus.schema")
        for ep in eps:
            pkg_name = ep.name
            if pkg_name not in _registered_packages:
                try:
                    # Loading the entry point triggers __init__.py which calls register_package
                    ep.load()
                except Exception:
                    pass
    except Exception:
        pass

    schemas = []
    for pkg, registry in _registered_packages.items():
        versions = registry.versions()
        if versions:
            schemas.append(f"{pkg}/latest")
            for ver in reversed(versions):
                schemas.append(f"{pkg}/{ver}")
    return schemas
