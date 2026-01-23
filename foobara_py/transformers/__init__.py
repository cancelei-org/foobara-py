"""
Transformers system for Foobara Python.

Provides value transformation pipelines for inputs, results, and errors.
"""

from foobara_py.transformers.base import Transformer, TransformerPipeline, TransformerRegistry
from foobara_py.transformers.error_transformers import (
    AuthErrorsTransformer,
    GroupErrorsByPathTransformer,
    StripRuntimePathTransformer,
    UserFriendlyErrorsTransformer,
)
from foobara_py.transformers.input_transformers import (
    DefaultValuesTransformer,
    EntityToPrimaryKeyInputsTransformer,
    NormalizeKeysTransformer,
    RemoveNullValuesTransformer,
    StripWhitespaceTransformer,
)
from foobara_py.transformers.result_transformers import (
    EntityToPrimaryKeyResultTransformer,
    LoadAggregatesTransformer,
    LoadAtomsTransformer,
    PaginationTransformer,
    ResultToJsonTransformer,
)

__all__ = [
    "Transformer",
    "TransformerPipeline",
    "TransformerRegistry",
    "EntityToPrimaryKeyInputsTransformer",
    "NormalizeKeysTransformer",
    "StripWhitespaceTransformer",
    "DefaultValuesTransformer",
    "RemoveNullValuesTransformer",
    "LoadAggregatesTransformer",
    "LoadAtomsTransformer",
    "ResultToJsonTransformer",
    "EntityToPrimaryKeyResultTransformer",
    "PaginationTransformer",
    "AuthErrorsTransformer",
    "UserFriendlyErrorsTransformer",
    "StripRuntimePathTransformer",
    "GroupErrorsByPathTransformer",
]
