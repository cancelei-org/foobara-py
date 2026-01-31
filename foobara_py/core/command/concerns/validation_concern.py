"""
ValidationConcern - Record loading and validation hooks.

Handles:
- Entity record loading from database
- Record existence validation
- Custom business logic validation hooks

Pattern: Ruby Foobara's Entities and ValidateRecords concerns
"""

from typing import Any, Dict


class ValidationConcern:
    """Mixin for record loading and validation."""

    # Instance attributes (defined in __slots__ in Command)
    _loaded_records: Dict[str, Any]

    def load_records(self) -> None:
        """
        Load entity records from the database.

        Automatically loads entities specified in LoadSpec declarations into
        command instance variables. Entities are fetched from their repositories
        using primary keys from validated inputs.

        Example:
            class UpdateUser(Command[UpdateUserInputs, User]):
                user: Loaded[User]  # Auto-loaded from inputs.user_id

                def execute(self) -> User:
                    # self.user is already loaded and available
                    self.user.name = self.inputs.name
                    return self.user.save()

        Note:
            Runs automatically after cast_and_validate_inputs().
            Override for custom loading logic or to load from multiple sources.
        """
        # Process _loads declarations
        loads = getattr(self.__class__, "_loads", None)
        if not loads:
            return

        for load_spec in loads:
            # Get the primary key from inputs
            input_value = getattr(self.inputs, load_spec.from_input, None)
            if input_value is None:
                if load_spec.required:
                    self.add_input_error(
                        (load_spec.from_input,),
                        "not_found",
                        f"{load_spec.entity_class.__name__} not found",
                    )
                continue

            # Load the entity
            entity = load_spec.entity_class.find(input_value)

            if entity is None:
                if load_spec.required:
                    self.add_input_error(
                        (load_spec.from_input,),
                        "not_found",
                        f"{load_spec.entity_class.__name__} with id {input_value} not found",
                    )
                else:
                    setattr(self, load_spec.into, None)
            else:
                setattr(self, load_spec.into, entity)

    def validate_records(self) -> None:
        """
        Validate that loaded entity records exist and are accessible.

        Override this method to verify loaded entities meet existence requirements,
        permissions checks, or state validations before execute() runs.

        Example:
            def validate_records(self) -> None:
                if not self.user.is_active:
                    self.add_runtime_error('inactive_user', 'User is inactive')

        Raises:
            Halt: If validation errors occur (via add_error with halt=True)

        Note:
            Runs automatically after load_records().
        """
        pass

    def validate(self) -> None:
        """
        Custom business logic validation hook.

        Override this method to implement domain-specific validation rules that
        go beyond input type checking. Use this for cross-field validations,
        business rule checks, or invariant enforcement.

        Example:
            def validate(self) -> None:
                if self.inputs.start_date > self.inputs.end_date:
                    self.add_input_error('date_range', 'Start must be before end')

        Raises:
            Halt: If validation errors occur (via add_error with halt=True)

        Note:
            Runs automatically after validate_records() and before execute().
        """
        pass
