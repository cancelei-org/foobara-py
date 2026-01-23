"""Tests for PyPI API Client"""

import pytest
from unittest.mock import Mock, patch
import httpx

from foobara_py.apis.pypi import (
    SearchPackages,
    GetPackageInfo,
    GetPackageVersions,
)
from foobara_py.apis.pypi.commands import (
    PackageSearchResult,
    PackageInfo,
    PackageVersion,
    _cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test"""
    _cache.clear()
    yield
    _cache.clear()


class TestGetPackageInfo:
    """Test GetPackageInfo command"""

    @pytest.fixture
    def mock_pypi_response(self):
        """Mock PyPI JSON API response"""
        return {
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "summary": "Python HTTP for Humans.",
                "description": "Requests is an elegant and simple HTTP library for Python.",
                "author": "Kenneth Reitz",
                "author_email": "me@kennethreitz.org",
                "license": "Apache 2.0",
                "home_page": "https://requests.readthedocs.io",
                "project_urls": {
                    "Documentation": "https://requests.readthedocs.io",
                    "Source": "https://github.com/psf/requests"
                },
                "requires_python": ">=3.7",
                "classifiers": [
                    "Development Status :: 5 - Production/Stable",
                    "Intended Audience :: Developers",
                ],
                "keywords": "http, requests",
                "requires_dist": [
                    "urllib3 (>=1.21.1,<3)",
                    "certifi (>=2017.4.17)",
                    "charset-normalizer (>=2,<4)"
                ]
            },
            "releases": {}
        }

    @patch('httpx.get')
    def test_get_package_info_success(self, mock_get, mock_pypi_response):
        """Should fetch package information"""
        mock_response = Mock()
        mock_response.json.return_value = mock_pypi_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        outcome = GetPackageInfo.run(package_name="requests")

        assert outcome.is_success()
        pkg = outcome.unwrap()
        assert isinstance(pkg, PackageInfo)
        assert pkg.name == "requests"
        assert pkg.version == "2.31.0"
        assert pkg.summary == "Python HTTP for Humans."
        assert pkg.author == "Kenneth Reitz"
        assert pkg.license == "Apache 2.0"
        assert pkg.requires_python == ">=3.7"
        assert len(pkg.dependencies) > 0

    @patch('httpx.get')
    def test_get_package_info_with_version(self, mock_get, mock_pypi_response):
        """Should fetch specific version"""
        mock_response = Mock()
        mock_response.json.return_value = mock_pypi_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        outcome = GetPackageInfo.run(package_name="requests", version="2.30.0")

        assert outcome.is_success()
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        assert "2.30.0" in url

    @patch('httpx.get')
    def test_get_package_info_not_found(self, mock_get):
        """Should handle package not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=Mock(),
            response=mock_response
        )
        mock_get.return_value = mock_response

        outcome = GetPackageInfo.run(package_name="nonexistent-package-xyz")

        assert outcome.is_failure()

    @patch('httpx.get')
    def test_get_package_info_caching(self, mock_get, mock_pypi_response):
        """Should cache results"""
        mock_response = Mock()
        mock_response.json.return_value = mock_pypi_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call
        outcome1 = GetPackageInfo.run(package_name="requests")
        assert outcome1.is_success()

        # Second call should use cache
        outcome2 = GetPackageInfo.run(package_name="requests")
        assert outcome2.is_success()

        # Should only call API once
        assert mock_get.call_count == 1

    @patch('httpx.get')
    def test_get_package_info_handles_missing_fields(self, mock_get):
        """Should handle missing optional fields"""
        minimal_response = {
            "info": {
                "name": "test-package",
                "version": "1.0.0",
                "summary": None,
                "description": None,
                "author": None,
                "requires_dist": None,
                "classifiers": None,
            }
        }

        mock_response = Mock()
        mock_response.json.return_value = minimal_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        outcome = GetPackageInfo.run(package_name="test-package")

        assert outcome.is_success()
        pkg = outcome.unwrap()
        assert pkg.name == "test-package"
        assert pkg.summary is None
        assert pkg.dependencies == []


class TestGetPackageVersions:
    """Test GetPackageVersions command"""

    @pytest.fixture
    def mock_versions_response(self):
        """Mock PyPI versions response"""
        return {
            "info": {
                "name": "requests",
                "version": "2.31.0"
            },
            "releases": {
                "2.31.0": [
                    {
                        "upload_time": "2023-05-22T14:20:00",
                        "yanked": False
                    }
                ],
                "2.30.0": [
                    {
                        "upload_time": "2023-05-03T10:15:00",
                        "yanked": False
                    }
                ],
                "2.29.0": [
                    {
                        "upload_time": "2023-03-15T08:30:00",
                        "yanked": True,
                        "yanked_reason": "Security vulnerability"
                    }
                ],
                "2.28.0": [
                    {
                        "upload_time": "2023-01-10T12:00:00",
                        "yanked": False
                    }
                ]
            }
        }

    @patch('httpx.get')
    def test_get_package_versions_success(self, mock_get, mock_versions_response):
        """Should fetch all versions"""
        mock_response = Mock()
        mock_response.json.return_value = mock_versions_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        outcome = GetPackageVersions.run(package_name="requests")

        assert outcome.is_success()
        versions = outcome.unwrap()
        assert isinstance(versions, list)
        assert len(versions) == 4

        # Check that versions are sorted by upload time (newest first)
        assert versions[0].version == "2.31.0"
        assert versions[1].version == "2.30.0"
        assert versions[2].version == "2.29.0"
        assert versions[3].version == "2.28.0"

    @patch('httpx.get')
    def test_get_package_versions_includes_yanked(self, mock_get, mock_versions_response):
        """Should identify yanked versions"""
        mock_response = Mock()
        mock_response.json.return_value = mock_versions_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        outcome = GetPackageVersions.run(package_name="requests")

        assert outcome.is_success()
        versions = outcome.unwrap()

        # Find yanked version
        yanked_version = next(v for v in versions if v.version == "2.29.0")
        assert yanked_version.yanked is True
        assert yanked_version.yanked_reason == "Security vulnerability"

    @patch('httpx.get')
    def test_get_package_versions_not_found(self, mock_get):
        """Should handle package not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=Mock(),
            response=mock_response
        )
        mock_get.return_value = mock_response

        outcome = GetPackageVersions.run(package_name="nonexistent-package")

        assert outcome.is_failure()

    @patch('httpx.get')
    def test_get_package_versions_caching(self, mock_get, mock_versions_response):
        """Should cache results"""
        mock_response = Mock()
        mock_response.json.return_value = mock_versions_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call
        outcome1 = GetPackageVersions.run(package_name="requests")
        assert outcome1.is_success()

        # Second call should use cache
        outcome2 = GetPackageVersions.run(package_name="requests")
        assert outcome2.is_success()

        # Should only call API once
        assert mock_get.call_count == 1


class TestSearchPackages:
    """Test SearchPackages command"""

    @patch('foobara_py.apis.pypi.commands.GetPackageInfo.run')
    def test_search_packages_exact_match(self, mock_get_info):
        """Should find package by exact match"""
        mock_outcome = Mock()
        mock_outcome.is_success.return_value = True
        mock_outcome.unwrap.return_value = PackageInfo(
            name="requests",
            version="2.31.0",
            summary="Python HTTP for Humans.",
            author="Kenneth Reitz"
        )
        mock_get_info.return_value = mock_outcome

        outcome = SearchPackages.run(query="requests", limit=10)

        assert outcome.is_success()
        results = outcome.unwrap()
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].name == "requests"

    @patch('foobara_py.apis.pypi.commands.GetPackageInfo.run')
    def test_search_packages_no_match(self, mock_get_info):
        """Should return empty list when no match"""
        mock_outcome = Mock()
        mock_outcome.is_success.return_value = False
        mock_get_info.return_value = mock_outcome

        outcome = SearchPackages.run(query="nonexistent-xyz-abc", limit=10)

        assert outcome.is_success()
        results = outcome.unwrap()
        assert results == []

    @patch('foobara_py.apis.pypi.commands.GetPackageInfo.run')
    def test_search_packages_caching(self, mock_get_info):
        """Should cache search results"""
        mock_outcome = Mock()
        mock_outcome.is_success.return_value = True
        mock_outcome.unwrap.return_value = PackageInfo(
            name="requests",
            version="2.31.0",
            summary="Python HTTP for Humans."
        )
        mock_get_info.return_value = mock_outcome

        # First call
        outcome1 = SearchPackages.run(query="requests", limit=10)
        assert outcome1.is_success()

        # Second call should use cache
        outcome2 = SearchPackages.run(query="requests", limit=10)
        assert outcome2.is_success()

        # GetPackageInfo should only be called once
        assert mock_get_info.call_count == 1


class TestPackageModels:
    """Test package data models"""

    def test_package_info_model(self):
        """Should create PackageInfo model"""
        pkg = PackageInfo(
            name="test-package",
            version="1.0.0",
            summary="Test package",
            author="Test Author",
            license="MIT"
        )

        assert pkg.name == "test-package"
        assert pkg.version == "1.0.0"
        assert pkg.summary == "Test package"

    def test_package_version_model(self):
        """Should create PackageVersion model"""
        version = PackageVersion(
            version="1.0.0",
            upload_time="2023-01-01T00:00:00",
            yanked=False
        )

        assert version.version == "1.0.0"
        assert version.yanked is False

    def test_package_search_result_model(self):
        """Should create PackageSearchResult model"""
        result = PackageSearchResult(
            name="test",
            version="1.0.0",
            description="Test package"
        )

        assert result.name == "test"
        assert result.version == "1.0.0"


class TestIntegration:
    """Integration tests (require network)"""

    @pytest.mark.skip(reason="Requires network access")
    def test_real_package_lookup(self):
        """Should fetch real package from PyPI"""
        outcome = GetPackageInfo.run(package_name="requests")

        assert outcome.is_success()
        pkg = outcome.unwrap()
        assert pkg.name == "requests"
        assert pkg.version is not None

    @pytest.mark.skip(reason="Requires network access")
    def test_real_versions_lookup(self):
        """Should fetch real versions from PyPI"""
        outcome = GetPackageVersions.run(package_name="requests")

        assert outcome.is_success()
        versions = outcome.unwrap()
        assert len(versions) > 0
        assert all(v.version for v in versions)
