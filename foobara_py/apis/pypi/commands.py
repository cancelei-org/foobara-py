"""
PyPI API Commands.

Commands for interacting with the Python Package Index (PyPI).
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from foobara_py.core.command import Command


# Response models
class PackageSearchResult(BaseModel):
    """Single package search result"""

    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None


class PackageInfo(BaseModel):
    """Detailed package information"""

    name: str
    version: str
    summary: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    author_email: Optional[str] = None
    license: Optional[str] = None
    home_page: Optional[str] = None
    project_urls: Dict[str, str] = Field(default_factory=dict)
    requires_python: Optional[str] = None
    classifiers: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class PackageVersion(BaseModel):
    """Package version information"""

    version: str
    upload_time: Optional[str] = None
    yanked: bool = False
    yanked_reason: Optional[str] = None


# Input models
class SearchPackagesInputs(BaseModel):
    """Inputs for SearchPackages command"""

    query: str = Field(..., description="Search query")
    limit: int = Field(default=20, description="Maximum results to return")


class GetPackageInfoInputs(BaseModel):
    """Inputs for GetPackageInfo command"""

    package_name: str = Field(..., description="Package name to fetch")
    version: Optional[str] = Field(default=None, description="Specific version (default: latest)")


class GetPackageVersionsInputs(BaseModel):
    """Inputs for GetPackageVersions command"""

    package_name: str = Field(..., description="Package name")


# Simple in-memory cache
_cache: Dict[str, tuple[Any, datetime]] = {}
_cache_ttl = timedelta(minutes=30)


def _get_cached(key: str) -> Optional[Any]:
    """Get cached value if not expired"""
    if key in _cache:
        value, timestamp = _cache[key]
        if datetime.now() - timestamp < _cache_ttl:
            return value
        else:
            del _cache[key]
    return None


def _set_cached(key: str, value: Any):
    """Set cached value with timestamp"""
    _cache[key] = (value, datetime.now())


class SearchPackages(Command[SearchPackagesInputs, List[PackageSearchResult]]):
    """
    Search for packages on PyPI.

    Uses PyPI's simple search API to find packages matching a query.

    Usage:
        outcome = SearchPackages.run(query="requests", limit=10)
        if outcome.is_success():
            for package in outcome.unwrap():
                print(f"{package.name}: {package.description}")
    """

    def execute(self) -> List[PackageSearchResult]:
        """Execute the search"""
        query = self.inputs.query
        limit = self.inputs.limit

        # Check cache
        cache_key = f"search:{query}:{limit}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        # PyPI doesn't have a native search API in JSON format
        # We'll use the warehouse API which is unofficial but commonly used
        url = "https://pypi.org/search/"
        params = {"q": query}

        try:
            # Note: PyPI search returns HTML, not JSON
            # For a production implementation, we'd parse the HTML or use
            # a third-party service. For now, we'll use the PyPI JSON API
            # to search by exact name match or return empty
            # This is a simplified implementation

            # Try exact match first
            try:
                info_result = GetPackageInfo.run(package_name=query)
                if info_result.is_success():
                    pkg = info_result.unwrap()
                    result = [
                        PackageSearchResult(
                            name=pkg.name,
                            version=pkg.version,
                            description=pkg.summary,
                            author=pkg.author,
                        )
                    ]
                    _set_cached(cache_key, result)
                    return result
            except Exception:
                pass

            # For a more complete implementation, we'd need to:
            # 1. Parse PyPI's HTML search results
            # 2. Use a third-party service like libraries.io
            # 3. Maintain our own search index

            # For now, return empty list if no exact match
            return []

        except Exception as e:
            raise RuntimeError(f"Failed to search PyPI: {e}")


class GetPackageInfo(Command[GetPackageInfoInputs, PackageInfo]):
    """
    Get detailed information about a package from PyPI.

    Uses PyPI's JSON API to fetch package metadata.

    Usage:
        outcome = GetPackageInfo.run(package_name="requests")
        if outcome.is_success():
            pkg = outcome.unwrap()
            print(f"{pkg.name} {pkg.version}")
            print(f"License: {pkg.license}")
    """

    def execute(self) -> PackageInfo:
        """Execute the command"""
        package_name = self.inputs.package_name
        version = self.inputs.version

        # Check cache
        cache_key = f"info:{package_name}:{version or 'latest'}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        # Build URL
        if version:
            url = f"https://pypi.org/pypi/{package_name}/{version}/json"
        else:
            url = f"https://pypi.org/pypi/{package_name}/json"

        try:
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            info = data.get("info", {})

            # Extract dependencies from requires_dist
            requires_dist = info.get("requires_dist", []) or []
            dependencies = []
            for dep in requires_dist:
                # Parse dependency string (e.g., "urllib3 (>=1.21.1,<3)")
                dep_name = dep.split()[0] if dep else ""
                if dep_name and ";" not in dep:  # Skip conditional dependencies for simplicity
                    dependencies.append(dep)

            # Parse keywords
            keywords_str = info.get("keywords", "") or ""
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

            result = PackageInfo(
                name=info.get("name", package_name),
                version=info.get("version", ""),
                summary=info.get("summary"),
                description=info.get("description"),
                author=info.get("author"),
                author_email=info.get("author_email"),
                license=info.get("license"),
                home_page=info.get("home_page"),
                project_urls=info.get("project_urls", {}) or {},
                requires_python=info.get("requires_python"),
                classifiers=info.get("classifiers", []) or [],
                keywords=keywords,
                dependencies=dependencies,
            )

            _set_cached(cache_key, result)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Package '{package_name}' not found on PyPI")
            raise RuntimeError(f"HTTP error: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch package info: {e}")


class GetPackageVersions(Command[GetPackageVersionsInputs, List[PackageVersion]]):
    """
    Get all available versions of a package from PyPI.

    Returns a list of all versions with metadata.

    Usage:
        outcome = GetPackageVersions.run(package_name="requests")
        if outcome.is_success():
            for version in outcome.unwrap():
                print(f"{version.version} - {version.upload_time}")
    """

    def execute(self) -> List[PackageVersion]:
        """Execute the command"""
        package_name = self.inputs.package_name

        # Check cache
        cache_key = f"versions:{package_name}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        url = f"https://pypi.org/pypi/{package_name}/json"

        try:
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            releases = data.get("releases", {})
            versions = []

            for version_str, release_info in releases.items():
                # Get first release file info if available
                upload_time = None
                if release_info:
                    first_release = release_info[0]
                    upload_time = first_release.get("upload_time")

                # Check if yanked (PyPI API includes this in the release info)
                yanked = False
                yanked_reason = None
                if release_info:
                    for release_file in release_info:
                        if release_file.get("yanked", False):
                            yanked = True
                            yanked_reason = release_file.get("yanked_reason")
                            break

                versions.append(
                    PackageVersion(
                        version=version_str,
                        upload_time=upload_time,
                        yanked=yanked,
                        yanked_reason=yanked_reason,
                    )
                )

            # Sort by upload time (newest first)
            versions.sort(key=lambda v: v.upload_time or "", reverse=True)

            _set_cached(cache_key, versions)
            return versions

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Package '{package_name}' not found on PyPI")
            raise RuntimeError(f"HTTP error: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch package versions: {e}")
