"""
PyPI API Client for foobara-py.

Provides commands to interact with the Python Package Index (PyPI) JSON API.

Usage:
    from foobara_py.apis.pypi import SearchPackages, GetPackageInfo

    # Search for packages
    outcome = SearchPackages.run(query="requests")

    # Get package information
    outcome = GetPackageInfo.run(package_name="requests")
"""

from foobara_py.apis.pypi.commands import (
    GetPackageInfo,
    GetPackageVersions,
    SearchPackages,
)

__all__ = [
    "SearchPackages",
    "GetPackageInfo",
    "GetPackageVersions",
]
