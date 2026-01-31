# Testing Documentation Index

Complete index of testing resources for foobara-py.

## Quick Links

- **[Quick Reference](TESTING_QUICK_REFERENCE.md)** - Fast lookup for common patterns
- **[Full Guide](TESTING_GUIDE.md)** - Comprehensive testing documentation
- **[Improvements Summary](../TESTING_IMPROVEMENTS_SUMMARY.md)** - What's new

## Documentation

### Getting Started

1. **[Quick Reference](TESTING_QUICK_REFERENCE.md)**
   - Common patterns
   - Code snippets
   - Command reference
   - Best for: Quick lookups while writing tests

2. **[Testing Guide](TESTING_GUIDE.md)**
   - Complete documentation
   - Detailed examples
   - Best practices
   - Migration guide
   - Best for: Learning and reference

3. **[Improvements Summary](../TESTING_IMPROVEMENTS_SUMMARY.md)**
   - Overview of new features
   - Benefits and goals
   - Files created
   - Migration path
   - Best for: Understanding what's new

## Source Code

### Test Infrastructure

1. **[tests/factories.py](../tests/factories.py)**
   - Entity factories (UserFactory, ProductFactory, OrderFactory)
   - Command factories
   - Domain factories
   - Mock data generators
   - Hypothesis strategies
   - 548 lines

2. **[tests/conftest.py](../tests/conftest.py)**
   - Pytest configuration
   - Shared fixtures
   - Registry cleanup
   - Repository fixtures
   - Domain fixtures
   - 448 lines

3. **[tests/helpers.py](../tests/helpers.py)**
   - HTTPTestHelper
   - DatabaseTestHelper
   - AsyncTestHelper
   - CommandCompositionHelper
   - AssertionHelpers
   - IntegrationTestHelper
   - MockBuilder
   - 582 lines

4. **[tests/property_strategies.py](../tests/property_strategies.py)**
   - Hypothesis strategies
   - Entity data generators
   - Command input generators
   - Edge case strategies
   - Workflow strategies
   - 489 lines

### Examples

1. **[tests/test_factory_patterns.py](../tests/test_factory_patterns.py)**
   - Factory usage examples
   - Fixture usage examples
   - Helper usage examples
   - Integration test examples
   - 450 lines
   - 23 passing tests

## Documentation by Topic

### Factories

- **Quick Reference:** [Factories Section](TESTING_QUICK_REFERENCE.md#factories)
- **Full Guide:** [Using Factories](TESTING_GUIDE.md#using-factories)
- **Source:** [tests/factories.py](../tests/factories.py)
- **Examples:** [test_factory_patterns.py::TestFactoryPatterns](../tests/test_factory_patterns.py)

### Fixtures

- **Quick Reference:** [Fixtures Section](TESTING_QUICK_REFERENCE.md#fixtures)
- **Full Guide:** [Fixtures and Helpers](TESTING_GUIDE.md#fixtures-and-helpers)
- **Source:** [tests/conftest.py](../tests/conftest.py)
- **Examples:** [test_factory_patterns.py::TestFixtureUsage](../tests/test_factory_patterns.py)

### Helpers

- **Quick Reference:** [Helpers Section](TESTING_QUICK_REFERENCE.md#helpers)
- **Full Guide:** [Fixtures and Helpers](TESTING_GUIDE.md#fixtures-and-helpers)
- **Source:** [tests/helpers.py](../tests/helpers.py)
- **Examples:** [test_factory_patterns.py::TestHelperPatterns](../tests/test_factory_patterns.py)

### Property-Based Testing

- **Quick Reference:** [Property-Based Testing](TESTING_QUICK_REFERENCE.md#property-based-testing)
- **Full Guide:** [Property-Based Testing](TESTING_GUIDE.md#property-based-testing)
- **Source:** [tests/property_strategies.py](../tests/property_strategies.py)
- **Examples:** [tests/test_property_based.py](../tests/test_property_based.py)

### Integration Testing

- **Quick Reference:** [Common Patterns](TESTING_QUICK_REFERENCE.md#common-patterns)
- **Full Guide:** [Integration Testing](TESTING_GUIDE.md#integration-testing)
- **Source:** [tests/helpers.py](../tests/helpers.py)
- **Examples:** [test_factory_patterns.py::TestFactoryIntegration](../tests/test_factory_patterns.py)

## Testing by Component

### Commands

- **Patterns:** [Testing Commands](TESTING_GUIDE.md#testing-commands)
- **Factories:** CommandFactory
- **Examples:** test_command.py, test_command_lifecycle.py
- **Fixtures:** test_domain

### Entities

- **Patterns:** [Testing Entities](TESTING_GUIDE.md#testing-entities)
- **Factories:** UserFactory, ProductFactory, OrderFactory
- **Examples:** test_entity.py, test_detached_entity.py
- **Fixtures:** user_repository, product_repository

### Domains

- **Patterns:** [Testing Domains](TESTING_GUIDE.md#testing-domains)
- **Factories:** DomainFactory
- **Examples:** test_domain.py
- **Fixtures:** test_domain, multiple_domains

### Persistence

- **Patterns:** [Database Integration](TESTING_GUIDE.md#database-integration)
- **Helpers:** DatabaseTestHelper
- **Examples:** test_persistence_comprehensive.py
- **Fixtures:** in_memory_repository, transactional_repository

### HTTP Connectors

- **Patterns:** [HTTP Integration](TESTING_GUIDE.md#http-integration)
- **Helpers:** HTTPTestHelper
- **Examples:** test_http.py, test_auth_http.py
- **Fixtures:** fastapi_test_client, mock_http_client

### Async Operations

- **Patterns:** [Async Testing](TESTING_GUIDE.md#async-testing)
- **Helpers:** AsyncTestHelper
- **Examples:** test_async_command.py
- **Fixtures:** event_loop, async_repository

## Common Tasks

### Write a New Test

1. Choose appropriate fixtures from [conftest.py](../tests/conftest.py)
2. Use factories from [factories.py](../tests/factories.py) for data
3. Use helpers from [helpers.py](../tests/helpers.py) for assertions
4. Follow patterns in [test_factory_patterns.py](../tests/test_factory_patterns.py)
5. See [Testing Guide](TESTING_GUIDE.md#testing-patterns) for patterns

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=foobara_py --cov-report=html

# Specific tests
pytest tests/test_command.py

# By marker
pytest -m unit
pytest -m integration
```

See [Quick Reference - Running Tests](TESTING_QUICK_REFERENCE.md#running-tests) for more options.

### Add Property-Based Test

1. Choose strategy from [property_strategies.py](../tests/property_strategies.py)
2. Write test using `@given` decorator
3. Test invariants, not specific values
4. See [Property-Based Testing Guide](TESTING_GUIDE.md#property-based-testing)

### Add Integration Test

1. Use integration fixtures (repositories, domains)
2. Use DatabaseTestHelper for data seeding
3. Test complete workflows
4. Mark with `@pytest.mark.integration`
5. See [Integration Testing Guide](TESTING_GUIDE.md#integration-testing)

### Create Custom Factory

1. Extend EntityFactory or Factory base class
2. Implement `get_defaults()` method
3. Set `entity_class` attribute
4. See [Creating Custom Factories](TESTING_GUIDE.md#creating-custom-factories)

## Migration Guide

### Updating Existing Tests

1. **Replace manual data creation:**
   - Before: `user = User(username="test", email="test@test.com")`
   - After: `user = UserFactory.create()`

2. **Use fixtures for setup:**
   - Before: Manual repository setup
   - After: `def test_something(user_repository):`

3. **Use helpers for assertions:**
   - Before: `assert outcome.is_success()`
   - After: `AssertionHelpers.assert_outcome_success(outcome)`

See [Migration Guide](TESTING_GUIDE.md#migration-guide) for complete details.

## Coverage

Current test coverage: **78.16%**

- Core modules: 86%+
- Generators: 95%+
- Serializers: 96%+
- Persistence: 87%+

Target: **85%+ overall**

See [Coverage Guidelines](TESTING_GUIDE.md#coverage-guidelines) for details.

## Best Practices

1. Use factories for all data creation
2. Use fixtures for setup/teardown
3. Use helpers for common assertions
4. Follow AAA (Arrange, Act, Assert)
5. One assertion per test (when possible)
6. Descriptive test names
7. Property tests for invariants
8. Integration tests for workflows
9. Mock external dependencies
10. Test behavior, not implementation

See [Best Practices](TESTING_GUIDE.md#best-practices) for complete list.

## Support

### Getting Help

1. Check [Quick Reference](TESTING_QUICK_REFERENCE.md)
2. Read [Full Guide](TESTING_GUIDE.md)
3. Look at [Examples](../tests/test_factory_patterns.py)
4. Check existing tests for patterns

### Contributing

When adding new test infrastructure:

1. Add to appropriate module (factories.py, helpers.py, etc.)
2. Document in TESTING_GUIDE.md
3. Add examples to test_factory_patterns.py
4. Update this index

## File Summary

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| tests/factories.py | Test factories | 548 | ✅ Ready |
| tests/conftest.py | Pytest fixtures | 448 | ✅ Ready |
| tests/helpers.py | Test helpers | 582 | ✅ Ready |
| tests/property_strategies.py | Hypothesis strategies | 489 | ✅ Ready |
| tests/test_factory_patterns.py | Examples | 450 | ✅ 23 passing |
| docs/TESTING_GUIDE.md | Full documentation | 750 | ✅ Ready |
| docs/TESTING_QUICK_REFERENCE.md | Quick reference | 350 | ✅ Ready |
| docs/TESTING_INDEX.md | This file | 250 | ✅ Ready |
| TESTING_IMPROVEMENTS_SUMMARY.md | Summary | 550 | ✅ Ready |

**Total:** ~4,417 lines of testing infrastructure and documentation

## Version History

### v1.0 (Current)
- Initial release of new testing infrastructure
- Factory pattern implementation
- Enhanced fixtures
- Test helpers
- Property-based testing strategies
- Comprehensive documentation

## Next Steps

1. Migrate existing tests to use new patterns
2. Add more integration tests
3. Expand property-based tests
4. Increase coverage to 85%+
5. Add domain-specific factories as needed

---

**Last Updated:** 2026-01-31
**Status:** Production Ready
**Coverage:** 78.16%
**Tests Passing:** 2316 passing, 34 skipped
