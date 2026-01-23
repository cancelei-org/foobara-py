"""
LoadDotenv - Smart .env file loader with multi-file support.

Loads environment variables from .env files with support for:
- Multiple environments (.env, .env.production, .env.test, etc.)
- Local overrides (.env.local, .env.production.local, etc.)
- Proper priority ordering (local > specific > general)

Usage:
    from foobara_py.util import LoadDotenv

    # Load for current environment
    LoadDotenv.run()

    # Load for specific environment
    LoadDotenv.run(env="production")

    # Load from specific directory
    LoadDotenv.run(dir="/path/to/project")
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class EnvFile:
    """Represents a .env file with its metadata."""

    file_name: str
    envs: Optional[List[str]]
    is_local: bool


class LoadDotenv:
    """
    Smart .env file loader with multi-environment support.

    Handles loading of .env files with proper priority:
    1. .env.{env}.local (highest priority)
    2. .env.local
    3. .env.{env}
    4. .env (lowest priority)

    Example file structure:
        .env                    # Base config
        .env.local              # Local overrides (git-ignored)
        .env.production         # Production config
        .env.production.local   # Local production overrides
        .env.test               # Test config
    """

    FILE_REGEX = re.compile(r"^\.env((?:\.\w+)*?)(\.local)?$")

    def __init__(
        self,
        env: Optional[str] = None,
        dir: Optional[str] = None,
    ):
        """
        Initialize the dotenv loader.

        Args:
            env: Environment name (e.g., 'development', 'production', 'test').
                 Defaults to DOTENV_ENV or FOOBARA_ENV environment variables,
                 or 'development' if neither is set.
            dir: Directory to search for .env files. Defaults to current working directory.
        """
        if env is None:
            env = os.environ.get("DOTENV_ENV") or os.environ.get("FOOBARA_ENV") or "development"

        if not env:
            raise ValueError("env must be provided")

        self.env = str(env)
        self.dir = Path(dir) if dir else Path.cwd()
        self.env_files: List[EnvFile] = []
        self.env_files_to_apply: List[EnvFile] = []

    @classmethod
    def run(
        cls,
        env: Optional[str] = None,
        dir: Optional[str] = None,
    ) -> None:
        """
        Load .env files for the specified environment.

        Args:
            env: Environment name
            dir: Directory to search for .env files
        """
        loader = cls(env=env, dir=dir)
        loader.execute()

    def execute(self) -> None:
        """Execute the dotenv loading process."""
        self._parse_env_file_names()
        self._determine_env_files_to_apply()
        self._sort_env_files()
        self._apply_env_files()

    def _parse_env_file_names(self) -> None:
        """Parse .env file names from the directory."""
        self.env_files = []

        if not self.dir.exists() or not self.dir.is_dir():
            return

        for file_path in self.dir.iterdir():
            if not file_path.is_file():
                continue

            file_name = file_path.name
            match = self.FILE_REGEX.match(file_name)

            if not match:
                continue

            envs_str = match.group(1)
            envs = envs_str[1:].split(".") if envs_str else None

            is_local = match.group(2) is not None

            self.env_files.append(
                EnvFile(
                    file_name=file_name,
                    envs=envs,
                    is_local=is_local,
                )
            )

    def _determine_env_files_to_apply(self) -> None:
        """Determine which .env files apply to the current environment."""
        self.env_files_to_apply = [
            env_file
            for env_file in self.env_files
            if env_file.envs is None or self.env in env_file.envs
        ]

    def _sort_env_files(self) -> None:
        """
        Sort env files by priority.

        Priority order (highest to lowest):
        1. Local files (.local)
        2. More specific env files (more dots)
        3. Alphabetically by env names

        This ensures:
        - .env.production.local overrides .env.production
        - .env.local overrides .env
        - .env.test.integration overrides .env.test
        """
        if not self.env_files_to_apply:
            return

        # Find max envs length for sorting
        max_envs = max(
            (len(env_file.envs) if env_file.envs else 0) for env_file in self.env_files_to_apply
        )

        # Sort by: is_local (0 = local, 1 = non-local), specificity (reversed), env names
        self.env_files_to_apply.sort(
            key=lambda env_file: (
                0 if env_file.is_local else 1,  # Local files first
                max_envs - len(env_file.envs or []) + 1,  # More specific first
                sorted(env_file.envs or []),  # Alphabetically
            )
        )

    def _apply_env_files(self) -> None:
        """Load the selected .env files into the environment."""
        if not self.env_files_to_apply:
            return

        try:
            from dotenv import load_dotenv as python_load_dotenv
        except ImportError:
            # python-dotenv not installed, use basic implementation
            self._load_env_files_basic()
            return

        # Load files in priority order (later files override earlier ones)
        # We reverse the list because python-dotenv loads files in order
        # and we want more specific files to override less specific ones
        for env_file in reversed(self.env_files_to_apply):
            file_path = self.dir / env_file.file_name
            python_load_dotenv(file_path, override=True)

    def _load_env_files_basic(self) -> None:
        """Basic .env file loader without python-dotenv dependency."""
        for env_file in reversed(self.env_files_to_apply):
            file_path = self.dir / env_file.file_name

            if not file_path.exists():
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes if present
                        if value and value[0] in ('"', "'") and value[-1] == value[0]:
                            value = value[1:-1]

                        # Set environment variable
                        os.environ[key] = value
