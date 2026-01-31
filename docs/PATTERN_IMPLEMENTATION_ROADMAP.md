# Foobara Pattern Implementation Roadmap

**Based on:** [FOOBARA_RUBY_PYTHON_PATTERN_ANALYSIS.md](./FOOBARA_RUBY_PYTHON_PATTERN_ANALYSIS.md)
**Date:** 2026-01-31
**Timeline:** 6 months (24 weeks)
**Total Effort:** 200 hours

---

## Overview

This roadmap implements 7 key recommendations to improve:
- AI portability: 65% → 95% (+30%)
- Maintainability: 70% → 90% (+20%)
- Architecture similarity: 40% → 85% (+45%)

---

## Phase 1: Foundation (Weeks 1-4)

### Week 1: Ruby-Python Rosetta Stone

**Goal:** Create comprehensive mapping documentation

**Tasks:**
- ✅ Basic command patterns (DONE - see RUBY_PYTHON_QUICK_REFERENCE.md)
- [ ] Advanced patterns (callbacks, transactions, domain mappers)
- [ ] Edge cases and gotchas
- [ ] AI-specific conversion rules
- [ ] Example command library (10 Ruby → Python examples)

**Deliverables:**
- `docs/rosetta_stone/` directory
  - `01_commands.md`
  - `02_inputs_types.md`
  - `03_domains.md`
  - `04_errors.md`
  - `05_callbacks.md`
  - `06_entities.md`
  - `07_testing.md`
  - `08_advanced.md`
- `examples/ported/` - 10 complete Ruby→Python examples

**Success Metrics:**
- [ ] 100+ pattern mappings documented
- [ ] 10 full command examples ported
- [ ] AI can successfully use docs to port simple commands

**Effort:** 40 hours
**Owner:** Documentation Team
**Priority:** 🔴 CRITICAL

---

### Week 2: Naming Convention Standards

**Goal:** Standardize and enforce naming patterns

**Tasks:**
- [ ] Document naming standards
- [ ] Create linting rules (ruff config)
- [ ] Write codemod for existing code
- [ ] Update CI/CD to enforce standards

**Naming Rules:**

1. **Inputs Classes:**
   ```python
   # ALWAYS: {CommandName}Inputs
   class CreateUserInputs(BaseModel):  # ✅
       pass

   # NEVER: Nested class
   class CreateUser(Command[...]):     # ❌
       class Inputs(BaseModel):
           pass
   ```

2. **Command Metadata:**
   ```python
   # ALWAYS: Use decorator
   @command(domain="Users", organization="MyApp")  # ✅
   class CreateUser(Command[...]):
       pass

   # NEVER: Class variables only
   class CreateUser(Command[...]):  # ❌
       _domain = "Users"
   ```

3. **Source Tracking:**
   ```python
   class CreateUser(Command[...]):
       """Create a new user

       Ported from: ruby/commands/users/create_user.rb
       Ruby SHA: abc123...
       Port Date: 2026-01-31
       """
   ```

**Deliverables:**
- `NAMING_CONVENTIONS.md`
- `.ruff.toml` with custom rules
- `scripts/apply_naming_conventions.py` (codemod)
- Updated CI checks

**Success Metrics:**
- [ ] 100% of new code follows conventions
- [ ] 80% of existing code updated
- [ ] CI fails on violations

**Effort:** 8 hours
**Owner:** DevOps + Core Team
**Priority:** 🔴 CRITICAL

---

### Weeks 3-4: Planning & Preparation

**Goal:** Prepare for concern-based refactor

**Tasks:**
- [ ] Design concern structure
- [ ] Plan migration strategy
- [ ] Set up feature flags
- [ ] Create comprehensive test suite
- [ ] Document rollback procedure

**Concern Structure Design:**
```
foobara_py/core/command/
├── __init__.py              # Backward compatibility re-exports
├── base.py                  # Command base class (~200 LOC)
├── concerns/
│   ├── __init__.py
│   ├── input_handling.py    # Input validation (~150 LOC)
│   ├── error_handling.py    # Error management (~120 LOC)
│   ├── callbacks.py         # Callback system (~150 LOC)
│   ├── state_machine.py     # State transitions (~130 LOC)
│   ├── transactions.py      # Transaction mgmt (~140 LOC)
│   ├── subcommands.py       # Subcommand exec (~190 LOC)
│   ├── domain_mappers.py    # Domain mapping (~160 LOC)
│   ├── entity_loading.py    # Entity loading (~120 LOC)
│   ├── reflection.py        # Reflection/manifest (~100 LOC)
│   ├── namespace.py         # Namespace handling (~80 LOC)
│   ├── description.py       # Description metadata (~40 LOC)
│   └── result.py            # Result handling (~60 LOC)
└── tests/
    └── concerns/
        ├── test_input_handling.py
        ├── test_error_handling.py
        └── ...
```

**Migration Strategy:**
```python
# Step 1: Extract concern
# Step 2: Write isolated tests
# Step 3: Update Command to use concern
# Step 4: Verify all existing tests pass
# Step 5: Update documentation
# Step 6: Merge to main

# Feature flag for gradual rollout
USE_CONCERN_ARCHITECTURE = os.getenv("FOOBARA_USE_CONCERNS", "false") == "true"
```

**Deliverables:**
- `CONCERN_REFACTOR_PLAN.md`
- Concern structure skeleton
- Test plan for each concern
- Feature flag implementation
- Rollback procedures

**Success Metrics:**
- [ ] All concerns designed with clear interfaces
- [ ] Test coverage plan covers 100% of existing functionality
- [ ] Team alignment on migration strategy

**Effort:** 8 hours
**Owner:** Architecture Team
**Priority:** 🔴 CRITICAL

---

## Phase 2: Core Improvements (Weeks 5-12)

### Weeks 5-12: Concern-Based Refactor

**Goal:** Extract command.py into modular concerns

**One Concern Per Week:** (8 weeks)

#### Week 5: InputHandling Concern
```python
# File: foobara_py/core/command/concerns/input_handling.py

class InputHandling(Generic[InputT]):
    """Concern for input validation and type extraction"""

    _cached_inputs_type: ClassVar[Optional[Type[BaseModel]]] = None

    def __init__(self, inputs: dict):
        self._raw_inputs: Dict[str, Any] = inputs
        self._inputs: Optional[InputT] = None

    @property
    def inputs(self) -> InputT:
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        # Type extraction logic
        pass

    def cast_and_validate_inputs(self) -> None:
        # Validation logic
        pass
```

**Tasks:**
- [ ] Extract InputHandling concern
- [ ] Write 20+ tests for InputHandling
- [ ] Update Command to use InputHandling
- [ ] Verify all existing tests pass
- [ ] Document InputHandling API

**Effort:** 5 hours

---

#### Week 6: ErrorHandling Concern
```python
# File: foobara_py/core/command/concerns/error_handling.py

class ErrorHandling:
    """Concern for error management"""

    def __init__(self):
        self._errors: ErrorCollection = ErrorCollection()
        self._subcommand_runtime_path: Tuple[str, ...] = ()

    def add_error(self, error: FoobaraError) -> None:
        # Error addition logic
        pass

    def add_input_error(self, path, symbol, message, **ctx) -> None:
        # Input error logic
        pass

    def add_runtime_error(self, symbol, message, halt=True, **ctx) -> None:
        # Runtime error logic
        pass
```

**Tasks:**
- [ ] Extract ErrorHandling concern
- [ ] Write 15+ tests
- [ ] Update Command
- [ ] Verify tests
- [ ] Document API

**Effort:** 5 hours

---

#### Week 7: StateMachine Concern
**Effort:** 5 hours

#### Week 8: Callbacks Concern
**Effort:** 5 hours

#### Week 9: Transactions Concern
**Effort:** 5 hours

#### Week 10: Subcommands Concern
**Effort:** 5 hours

#### Week 11: DomainMappers Concern
**Effort:** 5 hours

#### Week 12: EntityLoading Concern
**Effort:** 5 hours

---

### Week 12: Integration & Polish

**Goal:** Finalize concern refactor

**Tasks:**
- [ ] Extract remaining small concerns (namespace, description, result, reflection)
- [ ] Update backward compatibility layer in `__init__.py`
- [ ] Performance benchmarking (ensure no regression)
- [ ] Update all documentation
- [ ] Migration guide for users
- [ ] Blog post announcing new architecture

**Deliverables:**
- Complete concern-based architecture
- Performance benchmarks (before/after)
- Migration guide
- Updated documentation
- Blog post

**Success Metrics:**
- [ ] All 1,200+ tests pass
- [ ] No performance regression
- [ ] Documentation updated
- [ ] Zero breaking changes for users

**Effort:** 8 hours
**Owner:** Core Team
**Priority:** 🔴 CRITICAL

---

## Phase 3: AI Enablement (Weeks 13-20)

### Weeks 13-17: DSL-to-Pydantic Generator

**Goal:** Automate Ruby → Python input conversion

**Architecture:**
```python
# File: foobara_py/generators/ruby_dsl_converter.py

class RubyDSLParser:
    """Parse Ruby DSL blocks"""

    TYPE_MAP = {
        ":string": "str",
        ":integer": "int",
        ":float": "float",
        ":boolean": "bool",
        ":array": "List",
        ":hash": "Dict",
        ":duck": "Any",
        # ... more mappings
    }

    def parse_inputs_block(self, ruby_code: str) -> List[FieldDef]:
        """Parse `inputs do ... end` block"""
        pass

class PydanticGenerator:
    """Generate Pydantic models from field definitions"""

    def generate_model(self, name: str, fields: List[FieldDef]) -> str:
        """Generate Pydantic BaseModel code"""
        pass

    def generate_validators(self, fields: List[FieldDef]) -> str:
        """Generate @field_validator methods"""
        pass

class RubyToPythonConverter:
    """Main converter orchestrator"""

    def convert_command(self, ruby_file: str) -> str:
        """Convert entire Ruby command to Python"""
        pass
```

**Week-by-Week:**

**Week 13:** Ruby AST parsing
- [ ] Set up Ruby parser (ripper or tree-sitter)
- [ ] Extract inputs block
- [ ] Extract field definitions
- [ ] 30+ tests for parser

**Week 14:** Type mapping
- [ ] Implement TYPE_MAP
- [ ] Handle edge cases (:array element_type, :hash key/value types)
- [ ] Custom type support
- [ ] 40+ tests for type mapping

**Week 15:** Pydantic code generation
- [ ] Generate BaseModel classes
- [ ] Generate Field(...) constraints
- [ ] Generate @field_validator methods
- [ ] 30+ tests for generation

**Week 16:** Full command conversion
- [ ] Extract command structure
- [ ] Convert execute method
- [ ] Preserve comments and docstrings
- [ ] 20+ tests for end-to-end conversion

**Week 17:** CLI tool & integration
- [ ] `foob-py port ruby/commands/my_command.rb`
- [ ] Batch conversion support
- [ ] Dry-run mode
- [ ] Report generation
- [ ] Integration tests

**Deliverables:**
- `foobara_py/generators/ruby_dsl_converter.py`
- `foob-py port` CLI command
- 120+ tests
- Documentation with examples
- Porting guide

**Success Metrics:**
- [ ] Can convert 90% of Ruby commands automatically
- [ ] Converted code passes tests
- [ ] Conversion errors are clear and actionable

**Effort:** 60 hours
**Owner:** Generators Team
**Priority:** 🟡 HIGH

---

### Weeks 18-20: Type Registry Bridge

**Goal:** Support Ruby-style type definitions

**Architecture:**
```python
# File: foobara_py/types/ruby_bridge.py

class FoobaraType:
    """Ruby-compatible type definition"""

    def __init__(self, name: str, base_type: Type, **options):
        self.name = name
        self.base_type = base_type
        self.validators = options.get('validators', [])
        self.casters = options.get('casters', [])

    def to_pydantic_type(self) -> Type:
        """Convert to Pydantic-compatible type"""
        pass

    @classmethod
    def define(cls, name: str, base_type: Type, **options):
        """Define new type (Ruby-compatible API)"""
        type_def = cls(name, base_type, **options)
        TypeRegistry.register(name, type_def)
        return type_def.to_pydantic_type()

# Usage
EmailAddress = FoobaraType.define(
    "EmailAddress",
    base_type=str,
    validators=[
        lambda v: "@" in v or raise_error("missing_at_symbol"),
    ]
)

class MyInputs(BaseModel):
    email: EmailAddress  # Pydantic-compatible
```

**Tasks:**
- [ ] Implement FoobaraType class
- [ ] Type registry
- [ ] Pydantic integration
- [ ] Validator/caster support
- [ ] Documentation
- [ ] 30+ tests

**Deliverables:**
- `foobara_py/types/ruby_bridge.py`
- Updated type documentation
- Migration examples

**Success Metrics:**
- [ ] Ruby type definitions can be copy-pasted
- [ ] Full Pydantic compatibility
- [ ] No runtime overhead

**Effort:** 24 hours
**Owner:** Core Team
**Priority:** 🟡 HIGH

---

## Phase 4: Polish (Weeks 21-24)

### Week 21: Enhanced Type Annotations

**Goal:** Add comprehensive type hints everywhere

**Tasks:**
- [ ] Audit all methods for type hints
- [ ] Add generics to subcommand methods
- [ ] Document all parameters
- [ ] Run mypy in strict mode
- [ ] Fix all type errors

**Example:**
```python
# Before
def run_subcommand(self, command_class, **inputs):
    pass

# After
CT = TypeVar('CT', bound='Command')
RT = TypeVar('RT')

def run_subcommand(
    self,
    command_class: Type[Command[Any, RT]],
    **inputs: Any
) -> Optional[RT]:
    """Run a subcommand and return its result.

    Args:
        command_class: The command class to execute
        **inputs: Keyword arguments passed to command

    Returns:
        Command result or None if failed

    Example:
        user = self.run_subcommand(GetUser, user_id=123)
        if user:
            print(f"Found {user.name}")
    """
    pass
```

**Deliverables:**
- 100% type coverage
- Passing mypy strict mode
- Updated documentation

**Success Metrics:**
- [ ] `mypy --strict` passes
- [ ] All methods have type hints
- [ ] All parameters documented

**Effort:** 16 hours
**Owner:** Core Team
**Priority:** 🟡 MEDIUM

---

### Week 22-23: Test Pattern Standardization

**Goal:** Create RSpec-like matchers for pytest

**Implementation:**
```python
# File: foobara_py/testing/matchers.py

class Expectation:
    """RSpec-like expectation API"""

    def __init__(self, value):
        self.value = value

    def to_be_success(self):
        """Assert outcome is success"""
        assert self.value.is_success(), \
            f"Expected success, got errors: {self.value.errors}"

    def to_be_failure(self):
        """Assert outcome is failure"""
        assert self.value.is_failure(), \
            f"Expected failure, got success: {self.value.result}"

    def to_equal(self, expected):
        """Assert equality"""
        assert self.value == expected, \
            f"Expected {expected}, got {self.value}"

    def to_have_error(self, symbol: str):
        """Assert specific error present"""
        assert any(e.symbol == symbol for e in self.value.errors), \
            f"Expected error '{symbol}', got: {[e.symbol for e in self.value.errors]}"

def expect(value):
    """Create expectation"""
    return Expectation(value)

# Usage
outcome = CreateUser.run(name="John", email="john@example.com")
expect(outcome).to_be_success()
expect(outcome.result.name).to_equal("John")
```

**Tasks:**
- [ ] Implement Expectation class
- [ ] Add 20+ matchers
- [ ] pytest plugin
- [ ] Documentation
- [ ] Convert 10 example tests
- [ ] 40+ tests for testing utilities

**Deliverables:**
- `foobara_py/testing/matchers.py`
- pytest plugin
- Conversion guide
- Updated test examples

**Success Metrics:**
- [ ] Ruby tests can be ported with minimal changes
- [ ] Better error messages than standard assert

**Effort:** 12 hours
**Owner:** Testing Team
**Priority:** 🟢 LOW

---

### Week 24: Documentation & Launch

**Goal:** Finalize and launch improvements

**Tasks:**
- [ ] Update README with new architecture
- [ ] Write migration guide (v2 → v3)
- [ ] Create video tutorial
- [ ] Write blog post series (3 posts)
- [ ] Update API documentation
- [ ] Create example projects
- [ ] Performance benchmarks
- [ ] Release v3.0.0

**Deliverables:**
- Updated documentation
- Migration guide
- 3 blog posts
- Video tutorial
- Example projects
- Release notes
- v3.0.0 release

**Success Metrics:**
- [ ] Documentation is comprehensive
- [ ] Migration guide tested by 3+ developers
- [ ] Blog posts published
- [ ] v3.0.0 released

**Effort:** 16 hours
**Owner:** Full Team
**Priority:** 🔴 CRITICAL

---

## Resource Allocation

### Team Structure

| Role | Allocation | Focus |
|------|-----------|-------|
| **Architecture Lead** | 50% (12 hrs/week) | Design, review, integration |
| **Core Developer 1** | 100% (24 hrs/week) | Concern refactor, generators |
| **Core Developer 2** | 100% (24 hrs/week) | Testing, type system |
| **Documentation** | 50% (12 hrs/week) | Docs, examples, blog posts |
| **DevOps** | 25% (6 hrs/week) | CI/CD, tooling, linting |

**Total:** 2.75 FTE

---

## Risk Management

### Risk 1: Breaking Changes

**Mitigation:**
- Feature flags for gradual rollout
- Backward compatibility via re-exports
- Comprehensive deprecation warnings
- Migration guide with examples

### Risk 2: Performance Regression

**Mitigation:**
- Benchmark before/after each concern
- Performance test suite
- Profile critical paths
- Optimize as needed

### Risk 3: Timeline Slippage

**Mitigation:**
- Weekly check-ins
- Buffer time in Weeks 12, 20, 24
- Can skip Phase 4 if needed (nice-to-have)
- Parallel work where possible

### Risk 4: Team Capacity

**Mitigation:**
- Clearly defined tasks
- Good documentation
- Pair programming for complex parts
- External contractors if needed

---

## Success Criteria

### Phase 1 (Foundation)
- [ ] Rosetta Stone with 100+ mappings
- [ ] Naming conventions enforced in CI
- [ ] Refactor plan approved by team

### Phase 2 (Core)
- [ ] All concerns extracted
- [ ] 100% test coverage maintained
- [ ] No breaking changes
- [ ] Performance maintained

### Phase 3 (AI)
- [ ] 90% of Ruby commands auto-convertible
- [ ] Type bridge supports Ruby types
- [ ] Documentation complete

### Phase 4 (Polish)
- [ ] Full type coverage
- [ ] RSpec-like matchers available
- [ ] v3.0.0 released

---

## Metrics & KPIs

### AI Portability
- **Baseline:** 65%
- **Week 4:** 70% (Rosetta Stone)
- **Week 12:** 80% (Concerns)
- **Week 20:** 95% (Generators)

### Maintainability
- **Baseline:** 70%
- **Week 12:** 90% (Concerns)

### Code Quality
- **Test Coverage:** Maintain 95%+
- **Type Coverage:** 0% → 100%
- **Linting:** 100% passing
- **Documentation:** 100% API docs

### Developer Experience
- **Time to Port Ruby Command:**
  - Baseline: 2 hours (manual)
  - Week 20: 15 minutes (automated)
- **Onboarding Time:**
  - Baseline: 2 weeks
  - Week 24: 1 week

---

## Go/No-Go Gates

### Gate 1: End of Phase 1 (Week 4)
- [ ] Rosetta Stone complete
- [ ] Naming conventions enforced
- [ ] Team alignment on refactor plan

**Decision:** Proceed to Phase 2?

### Gate 2: End of Phase 2 (Week 12)
- [ ] All concerns extracted
- [ ] Tests passing
- [ ] No performance regression

**Decision:** Proceed to Phase 3?

### Gate 3: End of Phase 3 (Week 20)
- [ ] Generator working
- [ ] Type bridge complete
- [ ] Documentation updated

**Decision:** Proceed to Phase 4 or release v3.0.0?

---

## Rollback Plan

If issues arise, we can rollback:

1. **Immediate Rollback:** Revert to previous version
   - Feature flags allow instant switch
   - `USE_CONCERN_ARCHITECTURE=false`

2. **Gradual Rollback:** Fix-forward
   - Fix bug in concern
   - Re-deploy with fix
   - No need to rollback entire refactor

3. **Full Rollback:** Emergency only
   - Revert all commits in Phase 2
   - Return to monolithic architecture
   - Lessons learned for v4.0.0

---

## Communication Plan

### Weekly Updates
- Every Friday: Progress report
- Metrics dashboard
- Blockers and risks

### Monthly Reviews
- End of each phase
- Demo to stakeholders
- Go/No-Go decision

### Release Communication
- Blog post series (3 posts)
- Video tutorial
- Migration guide
- Twitter/social media
- Email to users

---

## Next Steps

1. **Week 1 (Start Now):**
   - [ ] Create project in task tracker
   - [ ] Assign team members
   - [ ] Kick-off meeting
   - [ ] Begin Rosetta Stone

2. **Week 2:**
   - [ ] Implement naming conventions
   - [ ] Set up linting rules
   - [ ] Update CI/CD

3. **Weeks 3-4:**
   - [ ] Design concern structure
   - [ ] Write test plan
   - [ ] Prepare for refactor

4. **Week 5:**
   - [ ] Begin concern extraction
   - [ ] Ship InputHandling concern

---

**Questions or feedback?** Contact the Architecture Team

**See Also:**
- [Full Analysis](./FOOBARA_RUBY_PYTHON_PATTERN_ANALYSIS.md)
- [Quick Reference](./RUBY_PYTHON_QUICK_REFERENCE.md)
- [Summary](./PATTERN_ANALYSIS_SUMMARY.md)
