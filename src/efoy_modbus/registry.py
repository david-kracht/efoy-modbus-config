"""
Schema registry for efoy-modbus-config.

Provides convenient, version-aware access to all Modbus register
specifications bundled with this package.  Results are parsed once and
cached for the lifetime of the interpreter.

Usage::

    import efoy_modbus

    # List all bundled versions
    efoy_modbus.versions()                # ['v1', 'v2']

    # Load a specific version — accepts int, bare string, or prefixed string
    spec = efoy_modbus.load("v1")
    spec = efoy_modbus.load(1)
    spec = efoy_modbus.load("1")

    # Load the latest version
    spec = efoy_modbus.latest()

    # Inspect the spec
    print(spec.firmware)                  # '24.15.303'
    print(spec.device_name)              # 'EFOY'
    for reg in spec.registers:
        print(reg.name, reg.address_dec, reg.access)
"""

from __future__ import annotations

import re
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from efoy_modbus.models import ModbusInterfaceSpecification

_VERSION_RE = re.compile(r"^v(\d+)\.json$")

# Module-level cache: version key → parsed spec object
_cache: dict[str, "ModbusInterfaceSpecification"] = {}


def _normalise(version: str | int) -> str:
    """Normalise *version* to the canonical key form ``'v1'``.

    Accepted inputs: ``1`` (int), ``"1"`` (bare string), ``"v1"`` (prefixed).

    Raises:
        ValueError: if the input cannot be interpreted as a version key.
    """
    v = str(version).strip()
    if re.fullmatch(r"\d+", v):
        return f"v{v}"
    if re.fullmatch(r"v\d+", v):
        return v
    raise ValueError(
        f"Invalid version specifier {version!r}. "
        "Expected an integer (1), a bare string ('1'), or a prefixed string ('v1')."
    )


def versions() -> list[str]:
    """Return a sorted list of all available schema version keys.

    Example::

        >>> import efoy_modbus
        >>> efoy_modbus.versions()
        ['v1', 'v2']
    """
    schema_dir = files("efoy_modbus.schemas")
    keys: list[str] = []
    for item in schema_dir.iterdir():
        m = _VERSION_RE.match(item.name)
        if m:
            keys.append(f"v{m.group(1)}")
    return sorted(keys, key=lambda k: int(k[1:]))


def load(version: str | int) -> "ModbusInterfaceSpecification":
    """Load and return the Modbus register specification for *version*.

    The first call for a given version parses the bundled JSON file and
    populates the cache.  Subsequent calls return the cached object directly
    with no I/O overhead.

    Args:
        version: Version identifier — any of ``1``, ``"1"``, or ``"v1"``.

    Returns:
        A fully-validated :class:`~efoy_modbus.models.ModbusInterfaceSpecification`
        instance.

    Raises:
        ValueError: if *version* is not a recognised specifier or does not
            correspond to a bundled schema file.

    Example::

        >>> spec = efoy_modbus.load("v2")
        >>> len(spec.registers)
        348
    """
    from efoy_modbus.models import ModbusInterfaceSpecification

    key = _normalise(version)
    if key in _cache:
        return _cache[key]

    schema_dir = files("efoy_modbus.schemas")
    resource = schema_dir.joinpath(f"{key}.json")
    try:
        data = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        available = versions()
        raise ValueError(
            f"Schema version {key!r} not found in package data. "
            f"Available versions: {available}"
        ) from exc

    spec = ModbusInterfaceSpecification.model_validate_json(data)
    _cache[key] = spec
    return spec


def latest() -> "ModbusInterfaceSpecification":
    """Load and return the most recent bundled schema version.

    Equivalent to ``load(versions()[-1])``.

    Raises:
        RuntimeError: if no schema files are present in the package.

    Example::

        >>> spec = efoy_modbus.latest()
        >>> spec.firmware
        '24.15.303'
    """
    available = versions()
    if not available:
        raise RuntimeError(
            "No schema files found in efoy_modbus.schemas. "
            "Re-install the package or run 'efoy-generate' to generate a schema first."
        )
    return load(available[-1])
