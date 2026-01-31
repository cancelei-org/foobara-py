#!/usr/bin/env python
"""
Verification script for enhanced callback system.

Checks that all components are working correctly.
"""

import sys
import time


def check_imports():
    """Verify all classes can be imported."""
    print("Checking imports...")
    try:
        from foobara_py.core.callbacks_enhanced import (
            CallbackCondition,
            RegisteredCallback,
            EnhancedCallbackRegistry,
            EnhancedCallbackExecutor,
        )
        from foobara_py.core.state_machine import CommandState
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def check_basic_functionality():
    """Verify basic functionality."""
    print("\nChecking basic functionality...")
    try:
        from foobara_py.core.callbacks_enhanced import (
            EnhancedCallbackRegistry,
            EnhancedCallbackExecutor,
        )
        from foobara_py.core.state_machine import CommandState

        class MockCommand:
            def __init__(self):
                self.log = []

        # Create registry
        registry = EnhancedCallbackRegistry()

        # Register callback
        def test_callback(cmd):
            cmd.log.append("callback_executed")

        registry.register("before", test_callback, transition="execute")

        # Create executor and execute
        cmd = MockCommand()
        executor = EnhancedCallbackExecutor(registry, cmd)

        def action():
            cmd.log.append("action_executed")
            return "result"

        result = executor.execute_transition(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute",
            action
        )

        # Verify
        assert result == "result", "Action result incorrect"
        assert "callback_executed" in cmd.log, "Callback not executed"
        assert "action_executed" in cmd.log, "Action not executed"

        print("✓ Basic functionality working")
        return True
    except Exception as e:
        print(f"✗ Basic functionality failed: {e}")
        return False


def check_performance():
    """Verify performance is within targets."""
    print("\nChecking performance...")
    try:
        from foobara_py.core.callbacks_enhanced import (
            EnhancedCallbackRegistry,
            EnhancedCallbackExecutor,
        )
        from foobara_py.core.state_machine import CommandState

        class MockCommand:
            def __init__(self):
                self.value = 0

        # Create registry
        registry = EnhancedCallbackRegistry()

        # Register callbacks
        def cb1(cmd):
            cmd.value += 1

        def cb2(cmd):
            cmd.value += 1

        registry.register("before", cb1, transition="execute")
        registry.register("after", cb2, transition="execute")

        # Pre-compile
        registry.precompile_common_transitions()

        # Benchmark
        cmd = MockCommand()
        executor = EnhancedCallbackExecutor(registry, cmd)

        def action():
            return "result"

        iterations = 10000
        start = time.time()

        for _ in range(iterations):
            executor.execute_transition(
                CommandState.VALIDATING,
                CommandState.EXECUTING,
                "execute",
                action
            )

        elapsed = time.time() - start
        per_iteration_us = (elapsed / iterations) * 1000000

        print(f"  Per iteration: {per_iteration_us:.2f}μs")
        print(f"  Throughput: {iterations/elapsed:.0f} ops/sec")

        # Check against targets
        if per_iteration_us > 5.0:
            print(f"✗ Performance below target (<5μs expected)")
            return False

        print("✓ Performance within targets")
        return True
    except Exception as e:
        print(f"✗ Performance check failed: {e}")
        return False


def check_cache():
    """Verify cache functionality."""
    print("\nChecking cache...")
    try:
        from foobara_py.core.callbacks_enhanced import EnhancedCallbackRegistry
        from foobara_py.core.state_machine import CommandState

        # Create registry
        registry = EnhancedCallbackRegistry()

        # Register callback
        def cb(cmd):
            pass

        registry.register("before", cb, transition="execute")

        # Pre-compile
        registry.compile_chain(
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute"
        )

        # Get callbacks (should hit cache)
        registry.get_callbacks(
            "before",
            CommandState.VALIDATING,
            CommandState.EXECUTING,
            "execute"
        )

        # Check stats
        stats = registry.get_cache_stats()

        assert stats["hits"] > 0, "No cache hits"
        assert stats["compiled_chains"] > 0, "No compiled chains"

        print(f"  Cache hit rate: {stats['hit_rate']:.1f}%")
        print("✓ Cache working correctly")
        return True
    except Exception as e:
        print(f"✗ Cache check failed: {e}")
        return False


def check_features():
    """Verify all features are implemented."""
    print("\nChecking features...")
    try:
        from foobara_py.core.callbacks_enhanced import (
            CallbackCondition,
            RegisteredCallback,
            EnhancedCallbackRegistry,
            EnhancedCallbackExecutor,
        )

        # Check CallbackCondition
        assert hasattr(CallbackCondition, "matches"), "CallbackCondition.matches missing"
        assert hasattr(CallbackCondition, "from_state"), "CallbackCondition.from_state missing"
        assert hasattr(CallbackCondition, "to_state"), "CallbackCondition.to_state missing"
        assert hasattr(CallbackCondition, "transition"), "CallbackCondition.transition missing"

        # Check RegisteredCallback
        assert hasattr(RegisteredCallback, "callback"), "RegisteredCallback.callback missing"
        assert hasattr(RegisteredCallback, "callback_type"), "RegisteredCallback.callback_type missing"
        assert hasattr(RegisteredCallback, "condition"), "RegisteredCallback.condition missing"
        assert hasattr(RegisteredCallback, "priority"), "RegisteredCallback.priority missing"

        # Check EnhancedCallbackRegistry
        assert hasattr(EnhancedCallbackRegistry, "register"), "register method missing"
        assert hasattr(EnhancedCallbackRegistry, "get_callbacks"), "get_callbacks method missing"
        assert hasattr(EnhancedCallbackRegistry, "compile_chain"), "compile_chain method missing"
        assert hasattr(EnhancedCallbackRegistry, "clear_cache"), "clear_cache method missing"
        assert hasattr(EnhancedCallbackRegistry, "precompile_common_transitions"), "precompile_common_transitions missing"
        assert hasattr(EnhancedCallbackRegistry, "has_callbacks"), "has_callbacks method missing"
        assert hasattr(EnhancedCallbackRegistry, "get_cache_stats"), "get_cache_stats method missing"

        # Check EnhancedCallbackExecutor
        assert hasattr(EnhancedCallbackExecutor, "execute_transition"), "execute_transition method missing"
        assert hasattr(EnhancedCallbackExecutor, "execute_simple"), "execute_simple method missing"

        print("✓ All features implemented")
        return True
    except Exception as e:
        print(f"✗ Feature check failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Enhanced Callback System - Verification")
    print("=" * 70)

    checks = [
        check_imports,
        check_features,
        check_basic_functionality,
        check_cache,
        check_performance,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"✗ Check failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 70)
    print(f"Results: {sum(results)}/{len(results)} checks passed")
    print("=" * 70)

    if all(results):
        print("\n✓ All verification checks passed!")
        print("Enhanced callback system is ready for use.")
        return 0
    else:
        print("\n✗ Some verification checks failed.")
        print("Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
