"""
Manifest caching for remote imports.

Provides caching layer to avoid repeatedly fetching manifests
from remote services.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """A cached manifest entry."""

    data: Dict[str, Any]
    fetched_at: datetime
    expires_at: datetime
    etag: Optional[str] = None
    url: str = ""

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.now() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return (datetime.now() - self.fetched_at).total_seconds()


class ManifestCache:
    """
    Cache for remote manifests.

    Features:
    - TTL-based expiration
    - ETag support for conditional requests
    - In-memory storage (default)
    - Optional persistence to file

    Usage:
        cache = ManifestCache(ttl_seconds=300)  # 5 minute cache

        # Store manifest
        cache.set("https://api.example.com/manifest", manifest_data)

        # Retrieve manifest
        manifest = cache.get("https://api.example.com/manifest")
        if manifest is None:
            # Cache miss or expired - need to fetch

        # Check if needs refresh (for conditional requests)
        entry = cache.get_entry("https://api.example.com/manifest")
        if entry and entry.is_expired:
            # Use entry.etag for If-None-Match header
    """

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_entries: int = 100,
    ):
        """
        Initialize manifest cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default 5 minutes).
            max_entries: Maximum number of cached manifests.
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: Dict[str, CacheEntry] = {}

    def _cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get cached manifest data if valid.

        Args:
            url: The manifest URL.

        Returns:
            Manifest data if cached and not expired, None otherwise.
        """
        entry = self.get_entry(url)
        if entry and not entry.is_expired:
            return entry.data
        return None

    def get_entry(self, url: str) -> Optional[CacheEntry]:
        """
        Get cache entry (even if expired).

        Useful for conditional requests using ETag.

        Args:
            url: The manifest URL.

        Returns:
            CacheEntry if exists, None otherwise.
        """
        key = self._cache_key(url)
        return self._entries.get(key)

    def set(
        self,
        url: str,
        data: Dict[str, Any],
        etag: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> CacheEntry:
        """
        Cache manifest data.

        Args:
            url: The manifest URL.
            data: The manifest data to cache.
            etag: Optional ETag from response headers.
            ttl_seconds: Optional custom TTL (overrides default).

        Returns:
            The created cache entry.
        """
        # Evict old entries if at capacity
        if len(self._entries) >= self.max_entries:
            self._evict_oldest()

        ttl = ttl_seconds or self.ttl_seconds
        now = datetime.now()

        entry = CacheEntry(
            data=data,
            fetched_at=now,
            expires_at=now + timedelta(seconds=ttl),
            etag=etag,
            url=url,
        )

        key = self._cache_key(url)
        self._entries[key] = entry

        return entry

    def invalidate(self, url: str) -> bool:
        """
        Remove a manifest from cache.

        Args:
            url: The manifest URL.

        Returns:
            True if entry was removed, False if not found.
        """
        key = self._cache_key(url)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def clear(self) -> int:
        """
        Clear all cached manifests.

        Returns:
            Number of entries cleared.
        """
        count = len(self._entries)
        self._entries.clear()
        return count

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._entries:
            return

        oldest_key = min(self._entries.keys(), key=lambda k: self._entries[k].fetched_at)
        del self._entries[oldest_key]

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        expired_keys = [key for key, entry in self._entries.items() if entry.is_expired]

        for key in expired_keys:
            del self._entries[key]

        return len(expired_keys)

    @property
    def size(self) -> int:
        """Get number of cached entries."""
        return len(self._entries)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now()
        expired_count = sum(1 for e in self._entries.values() if e.is_expired)

        return {
            "total_entries": len(self._entries),
            "expired_entries": expired_count,
            "valid_entries": len(self._entries) - expired_count,
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
        }


class FileManifestCache(ManifestCache):
    """
    Manifest cache with file persistence.

    Stores cache entries to disk for persistence across restarts.
    """

    def __init__(
        self,
        cache_dir: str,
        ttl_seconds: int = 300,
        max_entries: int = 100,
    ):
        """
        Initialize file-based manifest cache.

        Args:
            cache_dir: Directory to store cache files.
            ttl_seconds: Time-to-live for cache entries.
            max_entries: Maximum number of cached manifests.
        """
        super().__init__(ttl_seconds=ttl_seconds, max_entries=max_entries)
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        self._load_from_disk()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        import os

        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_file(self, key: str) -> str:
        """Get file path for a cache key."""
        import os

        return os.path.join(self.cache_dir, f"{key}.json")

    def _load_from_disk(self) -> None:
        """Load cached entries from disk."""
        import glob
        import os

        pattern = os.path.join(self.cache_dir, "*.json")
        for filepath in glob.glob(pattern):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                entry = CacheEntry(
                    data=data["data"],
                    fetched_at=datetime.fromisoformat(data["fetched_at"]),
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    etag=data.get("etag"),
                    url=data.get("url", ""),
                )

                # Skip expired entries
                if not entry.is_expired:
                    key = os.path.basename(filepath)[:-5]  # Remove .json
                    self._entries[key] = entry

            except (json.JSONDecodeError, KeyError, ValueError):
                # Remove corrupted cache files
                os.remove(filepath)

    def set(
        self,
        url: str,
        data: Dict[str, Any],
        etag: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> CacheEntry:
        """Cache manifest data and persist to disk."""
        entry = super().set(url, data, etag, ttl_seconds)

        # Persist to disk
        key = self._cache_key(url)
        filepath = self._cache_file(key)

        cache_data = {
            "data": entry.data,
            "fetched_at": entry.fetched_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "etag": entry.etag,
            "url": entry.url,
        }

        with open(filepath, "w") as f:
            json.dump(cache_data, f)

        return entry

    def invalidate(self, url: str) -> bool:
        """Remove manifest from cache and disk."""
        import os

        key = self._cache_key(url)
        filepath = self._cache_file(key)

        if os.path.exists(filepath):
            os.remove(filepath)

        return super().invalidate(url)

    def clear(self) -> int:
        """Clear all cached manifests from memory and disk."""
        import glob
        import os

        pattern = os.path.join(self.cache_dir, "*.json")
        for filepath in glob.glob(pattern):
            os.remove(filepath)

        return super().clear()


# Global default cache instance
_default_cache: Optional[ManifestCache] = None


def get_manifest_cache() -> ManifestCache:
    """Get the default manifest cache."""
    global _default_cache
    if _default_cache is None:
        _default_cache = ManifestCache()
    return _default_cache


def set_manifest_cache(cache: ManifestCache) -> None:
    """Set the default manifest cache."""
    global _default_cache
    _default_cache = cache
