# HTTP Connector Feature Gap Analysis

**Date**: 2026-01-30
**Task**: Port http-command-connector v1.1.4 improvements from Ruby
**Status**: Gap documented - implementation not feasible without foundational systems

## Ruby Implementation v1.1.4 Features

### Feature 1: Optional Cookie Options (commit c8644de)

**Ruby Implementation**:
```ruby
# Before (v1.1.3)
def add_cookie(cookie_name, cookie_value, cookie_opts)
  cookies << Cookie.new(cookie_name, cookie_value, **cookie_opts)
end

# After (v1.1.4)
def add_cookie(cookie_name, cookie_value, **cookie_opts)
  cookies << Cookie.new(cookie_name, cookie_value, **cookie_opts)
end
```

**Purpose**: Makes cookie options truly optional by using Ruby's `**kwargs` splat operator instead of requiring a hash parameter.

**Impact**: Simplifies API usage - users can call `add_cookie(name, value)` without passing an empty hash for options.

### Feature 2: 'set:' Request Mutator Sugar (commit c2c8205)

**Ruby Implementation**:
```ruby
# Desugarizer that transforms:
connector.connect(
  command_class,
  request: { set: { foo: -> { some_value } } }
)

# Into:
connector.connect(
  command_class,
  request_mutators: [SetInputToProcResult.for(:foo, &proc)]
)
```

**Purpose**: Provides syntactic sugar for setting input values dynamically via procs/lambdas. Common use case is injecting authenticated user context.

**Components Added**:
1. `Http::Desugarizers::SetInputToProcResult` - Transforms sugar syntax into request mutators
2. `HttpCommandConnector.install!` - Registers the desugarizer
3. Modifies manifest to hide auto-set inputs from API schema

## Python HTTP Connector Current State

**File**: `/home/cancelei/Projects/foobara-universe/foobara-ecosystem-python/foobara-py/foobara_py/connectors/http.py`

**Architecture**: FastAPI-based HTTP connector with:
- Command registration as HTTP endpoints
- RouteConfig for endpoint configuration
- AuthConfig for authentication
- Manifest generation
- Direct command execution (no mutator pipeline)

**Key Differences from Ruby**:
1. **No Request/Response Mutator System**: Python connector executes commands directly without a mutation pipeline
2. **No Cookie Support**: No Cookie class or cookie handling in responses
3. **No Desugarizer System**: No infrastructure for transforming configuration syntax
4. **Different Auth Pattern**: Uses FastAPI's dependency injection instead of request mutators

## Gap Analysis

### Gap 1: Cookie Support Infrastructure

**Missing Components**:
- `Cookie` class with options (path, domain, secure, httponly, samesite, max_age)
- `Response.cookies` list
- `Response.add_cookie(name, value, **options)` method
- FastAPI response cookie setting in handlers

**Impact**: Cannot implement optional cookie options feature

**Workaround**: FastAPI has native cookie support via `Response.set_cookie()`, but the connector doesn't expose it

### Gap 2: Request/Response Mutator Pipeline

**Missing Components**:
- `RequestMutator` base class
- `ResponseMutator` base class
- Mutator registry and execution pipeline
- `SetInputToProcResult` request mutator
- Mutator chain execution in command lifecycle

**Impact**: Cannot implement 'set:' sugar feature or similar dynamic input injection

**Current Pattern**: Python uses FastAPI dependencies for auth, not request mutators

**Example (Current Python Pattern)**:
```python
# Python uses FastAPI dependency injection
async def get_current_user(token: str = Header(...)):
    return verify_token(token)

connector.register(
    command_class,
    auth_config=AuthConfig(enabled=True, dependency=get_current_user)
)
```

### Gap 3: Desugarizer System

**Missing Components**:
- `Desugarizer` base class
- Desugarizer registry
- Configuration transformation pipeline
- Connector installation/initialization system

**Impact**: Cannot transform shorthand syntax into expanded forms

**Note**: This is a framework-level feature, not HTTP-specific

## Architectural Considerations

### Why Direct Port is Not Feasible

1. **Different Execution Model**: Ruby connector has a sophisticated mutator pipeline; Python connector uses direct execution + FastAPI middleware

2. **Framework Integration**: FastAPI provides many features (auth, cookies, middleware) that Ruby implements via mutators

3. **Type System Differences**: Ruby has runtime type manipulation; Python relies on Pydantic static types

4. **Design Philosophy**: Ruby connector is highly configurable with mutators; Python connector leverages FastAPI conventions

### Why This Might Be Acceptable

1. **FastAPI Native Features**: FastAPI already provides:
   - Cookie handling via `Response.set_cookie()`
   - Auth via dependency injection
   - Middleware for request/response transformation
   - Request context injection

2. **Different Ecosystem**: Python web development patterns differ from Ruby/Rack patterns

3. **Simpler Mental Model**: Direct execution is easier to understand and debug than mutator pipelines

## Recommended Approach

### Option 1: Don't Port (Recommended)

**Rationale**: The Python connector uses idiomatic FastAPI patterns that achieve the same goals differently.

**For Cookie Options**: Enhance `CommandRoute` to support response cookies via FastAPI's native API:
```python
# Could add:
@dataclass
class ResponseConfig:
    cookies: Dict[str, CookieConfig] = field(default_factory=dict)

class CookieConfig:
    path: str = "/"
    domain: Optional[str] = None
    secure: bool = True
    httponly: bool = True
    samesite: str = "lax"
    max_age: Optional[int] = None
```

**For Dynamic Input Injection**: Continue using FastAPI dependencies:
```python
# This is the Pythonic way:
from fastapi import Depends

def inject_current_user():
    # ... auth logic ...
    return user

connector.register(
    MyCommand,
    auth_config=AuthConfig(
        enabled=True,
        dependency=Depends(inject_current_user)
    )
)
```

### Option 2: Implement Request/Response Mutators

**Effort**: HIGH (2-3 weeks)

**Prerequisites**:
1. Design mutator base classes
2. Implement mutator registry
3. Refactor connector to use mutator pipeline
4. Implement desugarizer system
5. Add Cookie class and response cookie support
6. Port SetInputToProcResult mutator
7. Add comprehensive tests

**Risk**: May break existing code; adds complexity

**Benefit**: Closer parity with Ruby implementation

### Option 3: Hybrid Approach

**Effort**: MEDIUM (1 week)

**Implementation**:
1. Add Cookie support to responses (use FastAPI native API)
2. Add optional middleware hooks to connector
3. Document FastAPI patterns as equivalents to Ruby mutators
4. Provide migration guide for Ruby users

## Conclusion

**Decision**: Document the gap and maintain Python-idiomatic patterns

**Reasoning**:
1. Python connector is functional and well-tested
2. FastAPI provides equivalent capabilities via different patterns
3. Implementing mutators would be a major refactor with marginal benefit
4. Python and Ruby ecosystems have different conventions - forcing Ruby patterns onto Python reduces code quality

**Recommendation for Task #3**: Mark as "Documented - Implementation Deferred" rather than "Completed"

## Alternative Solutions for Ruby Use Cases

### Use Case: Inject Authenticated User

**Ruby Approach**:
```ruby
connector.connect(
  MyCommand,
  request: { set: { current_user: -> { authenticated_user } } }
)
```

**Python Equivalent**:
```python
from fastapi import Depends, Request

def get_authenticated_user(request: Request):
    # Extract from request, validate token, etc.
    return request.state.user

# Option 1: Use dependency injection
connector.register(
    MyCommand,
    auth_config=AuthConfig(
        enabled=True,
        dependency=Depends(get_authenticated_user)
    )
)

# Option 2: Use middleware to inject into command inputs
@app.middleware("http")
async def inject_user_middleware(request: Request, call_next):
    request.state.user = await get_user_from_token(request)
    response = await call_next(request)
    return response
```

### Use Case: Move Result Attribute to Cookie

**Ruby Approach**:
```ruby
connector.connect(
  LoginCommand,
  response_mutators: [
    MoveAttributeToCookie.for(:auth_token, :session, httponly: true, secure: true)
  ]
)
```

**Python Equivalent**:
```python
# Customize the route handler to set cookies
class CustomCommandRoute(CommandRoute):
    def __init__(self, *args, cookie_mapping: Dict[str, CookieConfig] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cookie_mapping = cookie_mapping or {}

    def execute(self, inputs: Dict[str, Any], response: Response) -> Dict[str, Any]:
        result = super().execute(inputs)

        # Move specified attributes to cookies
        if result["success"]:
            for attr, cookie_config in self.cookie_mapping.items():
                if attr in result["result"]:
                    value = result["result"].pop(attr)
                    response.set_cookie(
                        key=cookie_config.name,
                        value=value,
                        **cookie_config.options
                    )

        return result

# Usage:
connector.register(
    LoginCommand,
    route_class=CustomCommandRoute,
    cookie_mapping={
        "auth_token": CookieConfig(
            name="session",
            httponly=True,
            secure=True
        )
    }
)
```

## Future Considerations

If request/response mutators become critical for feature parity:

1. **Start with Desugarizer System**: This is framework-level and reusable
2. **Add Cookie Class**: Simple data class with validation
3. **Implement Mutator Protocol**: Use Python's Protocol for duck typing
4. **Build Registry**: Simple dict-based registry
5. **Refactor Connector**: Add mutator pipeline before/after execution

**Estimated Effort**: 40-60 hours for full implementation with tests

## References

- Ruby HTTP Connector: `/home/cancelei/Projects/foobara-universe/foobara-ecosystem-ruby/connectors/http-command-connector`
- Ruby Commit c8644de: "Make cookie options optional"
- Ruby Commit c2c8205: "Add `set:` request mutator sugar"
- Python HTTP Connector: `/home/cancelei/Projects/foobara-universe/foobara-ecosystem-python/foobara-py/foobara_py/connectors/http.py`
- Python Tests: `/home/cancelei/Projects/foobara-universe/foobara-ecosystem-python/foobara-py/tests/test_http.py`

## Task Status

**Task #3**: Update HTTP connector with v1.1.4 features
**Status**: Documented - Implementation not feasible without foundational infrastructure
**Action**: Gap documented; idiomatic Python alternatives provided
**Recommendation**: Close task as "Documented" and defer implementation pending broader architectural discussion

---

**Created by**: Claude Sonnet 4.5
**Date**: 2026-01-30
**Related**: PARITY_CHECKLIST.md, FEATURE_PARITY.md
