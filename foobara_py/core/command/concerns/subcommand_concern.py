"""
SubcommandConcern - Subcommand execution and domain dependency validation.

Handles:
- Running subcommands with error propagation
- Domain dependency validation
- Mapped subcommand execution (with domain mappers)
- Runtime path tracking for nested commands

Pattern: Ruby Foobara's Subcommands and DomainMappers concerns
"""

from typing import Any, Dict, Type


class SubcommandConcern:
    """Mixin for subcommand execution."""

    def run_subcommand(
        self, command_class: Type["Command[Any, Any]"], **inputs
    ) -> Any:
        """
        Run a subcommand and return its result.

        Propagates errors from subcommand to parent command.
        Returns None if the subcommand fails.

        Validates domain dependencies before execution.

        Args:
            command_class: The subcommand class to run
            **inputs: Inputs to pass to the subcommand

        Returns:
            Subcommand result, or None if failed

        Raises:
            DomainDependencyError: If cross-domain call is not allowed
        """
        # Validate domain dependencies
        self._validate_cross_domain_call(command_class)

        # Create subcommand with runtime path
        runtime_path = self._subcommand_runtime_path + (self.full_command_symbol(),)
        subcommand = command_class(_runtime_path=runtime_path, **inputs)
        outcome = subcommand.run_instance()

        if outcome.is_failure():
            # Propagate errors from subcommand with context
            from foobara_py.core.errors import FoobaraError

            for error in outcome.errors:
                # Add subcommand name to error context
                error_with_context = FoobaraError(
                    category=error.category,
                    symbol=error.symbol,
                    path=error.path,
                    message=error.message,
                    context={**error.context, "subcommand": command_class.__name__},
                    runtime_path=error.runtime_path,
                    is_fatal=error.is_fatal,
                )
                self._errors.add(error_with_context)
            return None

        return outcome.result

    def run_subcommand_bang(self, command_class: Type["Command[Any, Any]"], **inputs) -> Any:
        """
        Run a subcommand, halting on failure.

        Similar to Ruby's run_subcommand!
        Returns result on success, raises Halt on failure (errors already propagated).

        Args:
            command_class: The subcommand class to run
            **inputs: Inputs to pass to the subcommand

        Returns:
            Subcommand result

        Raises:
            Halt: If subcommand fails
        """
        from foobara_py.core.state_machine import Halt

        result = self.run_subcommand(command_class, **inputs)

        if result is None and self._errors.has_errors():
            # Subcommand failed, errors already propagated by run_subcommand
            raise Halt()

        return result

    # Alias for Ruby-like syntax
    run_subcommand_ = run_subcommand_bang

    def _validate_cross_domain_call(self, target_command: Type["Command"]) -> None:
        """
        Validate that calling target_command from this command is allowed per domain dependencies.

        Args:
            target_command: The command class to call

        Raises:
            DomainDependencyError: If the cross-domain call is not allowed
        """
        # Get domain information
        source_domain = getattr(self.__class__, "_domain", None)
        target_domain = getattr(target_command, "_domain", None)

        # If either command has no domain, allow (global domain)
        if not source_domain or not target_domain:
            return

        # If same domain, always allow
        if source_domain == target_domain:
            return

        # Import here to avoid circular dependency
        from foobara_py.domain.domain import Domain, DomainDependencyError

        # Get the source domain object
        with Domain._lock:
            domain_obj = Domain._registry.get(source_domain)

        if not domain_obj:
            # Domain not registered, allow (lenient mode)
            return

        # Validate using domain's can_call_from logic
        if not domain_obj.can_call_from(target_domain):
            raise DomainDependencyError(
                f"Domain '{source_domain}' cannot call commands from '{target_domain}'. "
                f"Add '{target_domain}' to {source_domain}.depends_on() or use GlobalDomain."
            )

        # Track the cross-domain call for observability
        if source_domain != target_domain:
            Domain.track_cross_domain_call(source_domain, target_domain)

    def run_mapped_subcommand(
        self,
        command_class: Type["Command[Any, Any]"],
        unmapped_inputs: Dict[str, Any] = None,
        to: Type = None,
        **extra_inputs,
    ) -> Any:
        """
        Run a subcommand with automatic domain mapping.

        Automatically finds and applies domain mappers to:
        1. Transform unmapped_inputs to the subcommand's input type
        2. Transform the subcommand's result to the target 'to' type

        Args:
            command_class: The subcommand to run
            unmapped_inputs: Inputs to map before passing to subcommand
            to: Optional target type for result mapping
            **extra_inputs: Additional inputs to pass directly (not mapped)

        Returns:
            The mapped result value

        Raises:
            Halt: If mapping fails or subcommand fails

        Usage:
            # Map inputs and result
            result = self.run_mapped_subcommand(
                ExternalServiceCommand,
                unmapped_inputs={"user": internal_user},
                to=ExternalUser
            )
        """
        from foobara_py.domain.domain import Domain
        from foobara_py.domain.domain_mapper import DomainMapperRegistry

        if unmapped_inputs is None:
            unmapped_inputs = {}

        mapped_something = False
        final_inputs = unmapped_inputs.copy()
        final_inputs.update(extra_inputs)

        # Get the command's domain for mapper lookup
        domain = Domain.find_domain_for_command(self.__class__)

        # Try to find mapper for inputs
        if unmapped_inputs:
            inputs_type = command_class.inputs_type()

            # First try to map the whole inputs dict
            inputs_mapper = None
            if domain:
                inputs_mapper = DomainMapperRegistry.find_matching_mapper(
                    unmapped_inputs, inputs_type, domain=domain.name
                )
            if not inputs_mapper:
                inputs_mapper = DomainMapperRegistry.find_matching_mapper(
                    unmapped_inputs, inputs_type
                )

            if inputs_mapper:
                mapped_something = True
                mapped_inputs = inputs_mapper.map_value(unmapped_inputs)

                if isinstance(mapped_inputs, dict):
                    final_inputs = {**mapped_inputs, **extra_inputs}
                else:
                    if hasattr(mapped_inputs, "model_dump"):
                        final_inputs = {**mapped_inputs.model_dump(), **extra_inputs}
                    else:
                        final_inputs = mapped_inputs
            else:
                # If whole dict can't be mapped, try mapping individual values
                # Get expected input types from the Pydantic model
                inputs_schema = inputs_type.model_fields
                mapped_inputs = {}

                for key, value in unmapped_inputs.items():
                    # Get the expected type for this field
                    field_info = inputs_schema.get(key)
                    if field_info:
                        expected_type = field_info.annotation

                        # Try to find a mapper for this specific value
                        value_mapper = None
                        if domain:
                            value_mapper = DomainMapperRegistry.find_matching_mapper(
                                value, expected_type, domain=domain.name
                            )
                        if not value_mapper:
                            value_mapper = DomainMapperRegistry.find_matching_mapper(
                                value, expected_type
                            )

                        if value_mapper:
                            mapped_something = True
                            mapped_inputs[key] = value_mapper.map_value(value)
                        else:
                            mapped_inputs[key] = value
                    else:
                        mapped_inputs[key] = value

                final_inputs = {**mapped_inputs, **extra_inputs}

        # Run the subcommand
        result = self.run_subcommand_bang(command_class, **final_inputs)

        # Try to find mapper for result
        if to is not None:
            result_mapper = None

            if domain:
                result_mapper = DomainMapperRegistry.find_matching_mapper(
                    result, to, domain=domain.name
                )

            if not result_mapper:
                result_mapper = DomainMapperRegistry.find_matching_mapper(result, to)

            if result_mapper:
                mapped_something = True
                result = result_mapper.map_value(result)

        if not mapped_something:
            # No mapping occurred - add runtime error
            self.add_runtime_error(
                "no_domain_mapper_found",
                f"No domain mapper found for {command_class.full_name()}",
                halt=True,
                subcommand=command_class.full_name(),
                to=str(to) if to else None,
            )

        return result
