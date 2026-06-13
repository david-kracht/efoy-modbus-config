# Modbus Schema Registry & Extraction Pipeline

A machine-readable, versioned Modbus Register Schema Registry and PDF extraction pipeline. It normalizes vendor register documentation (PDFs) into structured, type-safe models (JSON/Pydantic) for application consumers.

---

## Architecture Overview

1. **Extraction**: Parses unstructured register specification tables from PDF manuals.
2. **Normalization**: Validates extracted registries into typed Pydantic models.
3. **Registry**: Packages and serves versioned schema JSONs (`v*.json`) dynamically.

*Reference Payload:* Ships with versioned schemas for EFOY device families (FC02, FC05, FC04, FC03 ranges).

---

## Setup & Build

### Requirements
- `uv` (Fast Python package manager)

### Installation & Sync
```bash
# Clone the repository
git clone <repo_url> && cd efoy-modbus-config

# Sync virtualenv and all workspace packages
uv sync --all-packages
```

### Build Workspace Packages
```bash
# Build all packages in the workspace
uv build --all

# Or build a specific package (e.g. the schema config package)
uv build -p modbus-config
```

---

## Schema definition

Schemas are serialized as JSON. Key attributes of `ModbusInterfaceSpecification`:
- `device_name`: Name of the device.
- `version`: Version of the schema.
- `firmware`: Targeted firmware version.
- `byte_order`: Endianness of 16-bit words (`big` | `little`).
- `word_order`: Endianness of 32/64-bit multi-register values (`big` | `little`).
- `registers`: List of registers (Coil, Discrete Input, Input, Holding).

---

## CLI: PDF Extraction Pipeline

Compile a new schema version from a manual PDF:
```bash
# Extract tables and output next schema version (vN.json)
uv run efoy-generate --pdf <path_to_spec.pdf>

# Debug/Inspect extracted tables and text mappings
uv run efoy-generate --pdf <path_to_spec.pdf> --inspect
```

---

## Library Usage

Integrate schemas dynamically in Python code:
```python
import efoy_modbus

# Get all available versions
versions = efoy_modbus.versions()

# Load latest or specific version
spec = efoy_modbus.latest()
# or: spec = efoy_modbus.load("v10")

# Access metadata and registers
print(spec.byte_order, spec.word_order)
for reg in spec.registers:
    print(reg.name, reg.address_dec, reg.data_type, reg.access)
```

---

## Runnable Examples

Complete, self-contained examples are available in the [examples/](file:///home/david/git/efoy-modbus-config/examples/) directory:
1. **[01_minimalmodbus/](file:///home/david/git/efoy-modbus-config/examples/01_minimalmodbus/)**: Look up registers by name, decode with scaling and enums.
2. **[02_codegen_jinja2/](file:///home/david/git/efoy-modbus-config/examples/02_codegen_jinja2/)**: Generate python getter functions with Jinja2 templates (zero runtime dependencies).
3. **[03_mqtt_polling_plan/](file:///home/david/git/efoy-modbus-config/examples/03_mqtt_polling_plan/)**: Generate polling plans in JSON format for Modbus-to-MQTT bridges.
4. **[04_advantech_csv/](file:///home/david/git/efoy-modbus-config/examples/04_advantech_csv/)**: Generate Modbus-to-MQTT CSV mapping configs for Advantech routers.
5. **[05_generic_client_cli/](file:///home/david/git/efoy-modbus-config/examples/05_generic_client_cli/)**: A fully generic Modbus TCP client and Typer CLI built against the register schema using python `struct` serialization.

See [EXAMPLES.md](file:///home/david/git/efoy-modbus-config/examples/EXAMPLES.md) for detailed usage guides.

---

## Deployment & Dependency Resolution

### 1. Development vs. Release Modes

The workspace supports two modes of dependency resolution via `uv`:

#### A. Local Dev Mode (Workspace Resolution)
For local development, dependencies are resolved dynamically across workspace packages or relative local directories. This is configured in `pyproject.toml` under `[tool.uv.sources]`:
```toml
# Sibling workspace resolution
modbus-schema-common = { workspace = true }
```
*Benefits:* Changes in models or registry tables are immediately reflected in consumer packages without needing intermediary builds or uploads.

#### B. Production Release Mode (Registry Resolution)
For deployments or production installations, packages are resolved directly from a PyPI or custom registry.
1. Comment out or delete the `[tool.uv.sources]` entries in all packages.
2. Sibling references will fallback to their standard definitions in the `dependencies = [...]` array (e.g., `"modbus-schema-common>=1.0.0"`).
3. `uv` will fetch and install the versioned packages from the registry index.

---

### 2. Packaging & Publishing
Build and publish wheels and source archives for all workspace packages to your target registry:
```bash
# 1. Build all workspace packages
uv build --all

# 2. Configure target registry credentials
export UV_PUBLISH_URL="https://your-custom-registry.com/repository/pypi/"
export UV_PUBLISH_USERNAME="username"
export UV_PUBLISH_PASSWORD="password"

# 3. Publish to registry
uv publish
```

---

### 3. Release & Update Workflows

#### Case A: Common Schema Model Changes
When modifying common schema Pydantic definitions (in `packages/modbus-schema-common`):
1. Make your changes in the common package.
2. Bump the version in `packages/modbus-schema-common/pyproject.toml` (e.g., `1.0.0` -> `1.0.1`).
3. Rebuild and publish: `uv build -p modbus-schema-common && uv publish`.
*Note:* Consumer packages with loose version requirements (e.g., `>=1.0.0`) do not need to be updated.

#### Case B: Schema Config / Registry Updates
When a new device schema or registry parameter is introduced (e.g. adding a new version JSON in `packages/modbus-config`):
1. Run the PDF extraction pipeline to generate the next schema version (e.g. `v30.json`).
2. Bump the version in `packages/modbus-config/pyproject.toml` (e.g., `1.1.0` -> `1.2.0`).
3. Rebuild and publish the updated schema package to the registry: `uv build -p modbus-config && uv publish`.
4. In the external control application, update the version requirement to import the new schemas: `"modbus-config>=1.2.0"`.
