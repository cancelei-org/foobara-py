"""
Desugarizers system for Foobara Python.

Provides input preprocessing pipelines that run before command validation.
"""

from foobara_py.desugarizers.attribute_desugarizers import (
    MergeInputs,
    OnlyInputs,
    RejectInputs,
    RenameKey,
    SetInputs,
    SymbolsToTrue,
)
from foobara_py.desugarizers.base import DesugarizePipeline, Desugarizer, DesugarizerRegistry
from foobara_py.desugarizers.format_desugarizers import (
    InputsFromCsv,
    InputsFromJson,
    InputsFromYaml,
    ParseBooleans,
    ParseNumbers,
)

__all__ = [
    "Desugarizer",
    "DesugarizePipeline",
    "DesugarizerRegistry",
    "OnlyInputs",
    "RejectInputs",
    "RenameKey",
    "SetInputs",
    "MergeInputs",
    "SymbolsToTrue",
    "InputsFromYaml",
    "InputsFromJson",
    "InputsFromCsv",
    "ParseBooleans",
    "ParseNumbers",
]
