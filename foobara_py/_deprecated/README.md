# Deprecated V1 Implementations

This directory contains legacy V1 implementations that have been superseded by V2.

**Status:** DEPRECATED as of v0.3.0
**Removal:** Scheduled for v0.4.0

## Files

- `core/command_v1.py` - Legacy command implementation (use `foobara_py.core.command`)
- `core/errors_v1.py` - Legacy error implementation (use `foobara_py.core.errors`)
- `domain/domain_v1.py` - Legacy domain implementation (use `foobara_py.domain.domain`)
- `connectors/mcp_v1.py` - Legacy MCP connector (use `foobara_py.connectors.mcp`)

## Migration

If you are importing from these files directly, update your imports:

```python
# ⚠️ DEPRECATED
from foobara_py.core.command import Command

# ✅ USE PUBLIC API INSTEAD
from foobara_py import Command
```

The public API in `foobara_py/__init__.py` has always used V2 implementations, so most users do not need to change anything.

## For Contributors

Do not modify these files. All new development happens in the current (formerly V2) implementations.
