"""
CRUD drivers for Foobara Python.

Provides pluggable storage backends for entity persistence.
"""

from foobara_py.drivers.local_files_driver import LocalFilesDriver

__all__ = [
    "LocalFilesDriver",
]
