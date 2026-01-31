# Foobara Python v0.5.1 Port - Changelog

## Overview
This release ports improvements from Ruby foobara v0.5.1 to foobara-py, ensuring feature parity between the Ruby and Python implementations.

## Changes

### 1. Fully Qualified CRUD Driver Table Names (commit 90cdb332)
**Breaking Change:** CRUD driver table names now use fully qualified entity names.

- **File**: `foobara_py/persistence/crud_driver.py`
- **Change**: Modified `CRUDTable._default_table_name()` to use full module path
- **Impact**: Table/collection names will now include domain/namespace information
- **Example**:
  - Before: `user`
  - After: `acme_org_users_domain_types_user`
- **Migration**: Existing data stores will need table/key renaming or explicit table_name configuration

### 2. BaseManifest#domain_reference Method (commit 0c0b3377)
**New Feature:** Added domain reference accessor to manifest classes.

- **Files**:
  - `foobara_py/manifest/base.py`
  - `foobara_py/manifest/command_manifest.py`
  - `foobara_py/manifest/domain_manifest.py`
- **Change**: Added `domain_reference()` method returning domain identifier string
- **Usage**: `manifest.domain_reference()` returns `"Organization::Domain"` or `None`

### 3. Deterministic Domain Manifest Ordering (commit f15edf7c)
**Improvement:** Domain manifests now return sorted data for consistent serialization.

- **File**: `foobara_py/manifest/domain_manifest.py`
- **Change**: `to_dict()` now sorts:
  - Dictionary keys alphabetically
  - Command names list
  - Dependencies list
- **Benefit**: Consistent JSON serialization, better git diffs, easier testing

### 4. Authenticators Without Foobara Entities (commit 3629b462)
**Improvement:** Authenticators can now work without entity support.

- **File**: `foobara_py/auth/authenticator.py`
- **Change**: Added default `relevant_entity_classes()` method returning empty list
- **Impact**: Authenticators no longer required to implement entity-related methods
- **Usage**: Simple authenticators can omit entity handling entirely

### 5. Request Class for Standalone Operation (commit e34ce225)
**New Feature:** Request objects can now operate without command_connector instance.

- **File**: `foobara_py/connectors/request.py` (new file)
- **Features**:
  - Standalone authentication support
  - Auth-mapped attributes via `__getattr__`
  - Works with or without command_connector
  - Support for custom auth mappers
- **Usage**:
  ```python
  request = Request(
      inputs={"name": "test"},
      authenticator=MyAuthenticator(),
      auth_mappers={"email": extract_email}
  )
  request.authenticate()
  email = request.email  # Uses auth mapper
  ```

### 6. Type Reference Defaults Handling (commit a35d1aca)
**Note:** No code changes needed for Python.

- Ruby fix checked if `attribute_type_declaration` is Hash before accessing `:allow_nil`
- Python uses Pydantic BaseModel which handles this automatically via `Optional[]` type hints
- Documented in `foobara_py/types/type_declarations.py`

### 7. Dependent Domain Model Type Extension Lookup (commit b08636a5)
**Note:** Not applicable to current Python implementation.

- Ruby change: Use `ABSOLUTE` lookup mode instead of `ABSOLUTE_SINGLE_NAMESPACE`
- Python implementation doesn't currently have equivalent namespace lookup modes
- Will be implemented when namespace/type lookup system is added

## Testing
All changes include comprehensive test coverage in `tests/test_v0_5_1_improvements.py`:
- 11 test cases covering all ported features
- Tests verify behavior matches Ruby implementation
- All tests pass successfully

## Migration Guide

### Breaking Change: CRUD Table Names

If you have existing data in CRUD drivers (Redis, LocalFiles, etc.), you'll need to either:

**Option 1: Rename existing data** (recommended for production)
```python
# Before upgrade: user
# After upgrade: myorg_mydomain_types_user
```

**Option 2: Explicitly set table names** (quick fix)
```python
class User(Entity):
    @classmethod
    def get_table_name(cls):
        return "user"  # Use old table name
```

**Option 3: Migration script**
```python
# Rename keys/tables from old format to new format
old_name = "user"
new_name = "myorg_mydomain_types_user"
# ... rename logic for your driver
```

## Compatibility
- **Python**: 3.9+
- **Ruby foobara compatibility**: v0.5.1
- **Breaking changes**: CRUD table names only
- **Backward compatibility**: All other changes are additions/improvements

## Contributors
Ported from Ruby foobara v0.5.1 by following commits:
- a35d1aca - Type reference defaults
- 90cdb332 - CRUD table names
- 0c0b3377 - BaseManifest#domain_reference
- f15edf7c - Deterministic ordering
- b08636a5 - Type extension lookup
- 3629b462 - Authenticators without entities
- e34ce225 - Request without connector
