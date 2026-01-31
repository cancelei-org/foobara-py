# Foobara-py Tutorial Series

Welcome to the foobara-py tutorial series! These hands-on tutorials will teach you everything you need to build production-ready applications with foobara-py.

## Tutorial Path

Follow these tutorials in order for the best learning experience:

### 1. [Basic Command](./01-basic-command.md) - 15 minutes

Learn the fundamentals:
- Creating your first command
- Defining inputs with Pydantic
- Running commands and handling outcomes
- Understanding the command lifecycle

**You'll build:** A simple calculator command

---

### 2. [Input Validation](./02-validation.md) - 20 minutes

Master input validation:
- Field constraints and validators
- Custom validation logic
- Handling validation errors
- Optional and required fields

**You'll build:** A user registration command with comprehensive validation

---

### 3. [Error Handling](./03-error-handling.md) - 25 minutes

Learn error handling patterns:
- Adding custom errors
- Error categories and severity
- Error recovery mechanisms
- Testing error scenarios

**You'll build:** A money transfer command with robust error handling

---

### 4. [Testing Commands](./04-testing.md) - 30 minutes

Write comprehensive tests:
- Using factories for test data
- Property-based testing
- Testing errors and edge cases
- Integration testing patterns

**You'll build:** A complete test suite for an e-commerce command

---

### 5. [Subcommands](./05-subcommands.md) - 25 minutes

Compose commands:
- Running subcommands
- Error propagation
- Transaction management
- Building workflows

**You'll build:** A multi-step order processing workflow

---

### 6. [Advanced Types](./06-advanced-types.md) - 30 minutes

Master the type system:
- Custom type processors
- Casters, transformers, and validators
- Type composition
- Pydantic integration

**You'll build:** A content management system with rich type validation

---

### 7. [Performance Optimization](./07-performance.md) - 35 minutes

Optimize for production:
- Performance profiling
- Caching strategies
- Async commands
- Database optimization

**You'll build:** A high-performance API with caching and async operations

---

## Learning Path by Goal

### Want to build REST APIs?
1. Basic Command
2. Input Validation
3. Error Handling
4. Testing Commands
5. Then: [HTTP Connector Guide](../README.md#http-connector)

### Want to build CLI tools?
1. Basic Command
2. Input Validation
3. Testing Commands
4. Then: [CLI Connector Guide](../README.md#cli-connector)

### Want to integrate with AI assistants?
1. Basic Command
2. Input Validation
3. Error Handling
4. Then: [MCP Integration Guide](../README.md#mcp-connector)

### Want to work with databases?
1. Basic Command
2. Subcommands
3. Performance Optimization
4. Then: [Entity System Guide](../README.md#entity-loading)

---

## Prerequisites

Before starting:

```bash
# Install foobara-py
pip install foobara-py[dev]

# Verify installation
python -c "from foobara_py import Command; print('Ready!')"
```

---

## Tips for Success

1. **Follow along by coding**: Don't just read - type the examples!
2. **Run the tests**: Each tutorial includes tests you can run
3. **Experiment**: Modify the examples and see what happens
4. **Ask questions**: Use GitHub Discussions if you get stuck
5. **Take breaks**: These tutorials build on each other - take time to absorb

---

## Tutorial Format

Each tutorial follows this structure:

- **Learning Objectives**: What you'll learn
- **Prerequisites**: What you need to know
- **Step-by-step Guide**: Detailed walkthrough
- **Complete Code**: Full working example
- **Exercises**: Practice problems
- **Next Steps**: Where to go from here

---

## Additional Resources

- [Quick Reference](../QUICK_REFERENCE.md) - Cheat sheet
- [Features Guide](../FEATURES.md) - Complete feature list
- [API Reference](#) - Full API documentation
- [Examples](../../examples/) - Real-world examples

---

## Get Help

- **Stuck?** Check [GitHub Discussions](https://github.com/foobara/foobara-py/discussions)
- **Found a bug?** [Open an issue](https://github.com/foobara/foobara-py/issues)
- **Have feedback?** We'd love to hear it!

---

Ready to start? Head to [Tutorial 1: Basic Command](./01-basic-command.md)!
