"""Dependency checker and installer for CherryAI.

This module checks whether required Python packages are installed by comparing
the hash of requirements.txt against a cached version file. If the version file
is missing or the hash doesn't match, dependencies are installed.

Designed to run early in CherryAI.py startup to ensure all required packages
are available before importing gui or other modules.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


# Constants
DEFAULT_REQUIREMENTS = "requirements.txt"
DEFAULT_VERSION_FILE = ".cherryai_deps.hash"


def compute_file_hash(path: Path) -> str:
	"""Compute MD5 hash of a file.

	Args:
		path: Path to file to hash.

	Returns:
		Hexadecimal hash string.
	"""
	hasher = hashlib.md5()
	try:
		with path.open("rb") as f:
			for chunk in iter(lambda: f.read(8192), b""):
				hasher.update(chunk)
		return hasher.hexdigest()
	except Exception as exc:
		logging.warning(f"Failed to compute hash for {path}: {exc}")
		return ""


def load_cached_hash(version_file: Path) -> Optional[str]:
	"""Load cached requirements hash from version file.

	Args:
		version_file: Path to version file (.cherryai_deps.hash).

	Returns:
		Cached hash string, or None if file doesn't exist or is empty.
	"""
	try:
		if version_file.exists():
			content = version_file.read_text(encoding="utf-8").strip()
			return content if content else None
	except Exception as exc:
		logging.warning(f"Failed to read version file {version_file}: {exc}")
	return None


def save_cached_hash(version_file: Path, hash_value: str) -> bool:
	"""Save requirements hash to version file.

	Args:
		version_file: Path to version file.
		hash_value: Hash string to save.

	Returns:
		True on success, False on failure.
	"""
	try:
		version_file.parent.mkdir(parents=True, exist_ok=True)
		version_file.write_text(hash_value, encoding="utf-8")
		return True
	except Exception as exc:
		logging.warning(f"Failed to save version file {version_file}: {exc}")
		return False


def install_requirements(requirements_file: Path, verbose: bool = False) -> bool:
	"""Install packages from requirements.txt using pip.

	Args:
		requirements_file: Path to requirements.txt.
		verbose: If True, show pip output. If False, suppress output.

	Returns:
		True if installation succeeded, False otherwise.
	"""
	try:
		cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
		if not verbose:
			cmd.append("-q")  # quiet mode

		result = subprocess.run(cmd, capture_output=not verbose, text=True)

		if result.returncode == 0:
			logging.info(f"Successfully installed requirements from {requirements_file}")
			return True
		else:
			if result.stderr:
				logging.error(f"pip install failed: {result.stderr}")
			return False
	except Exception as exc:
		logging.error(f"Failed to run pip install: {exc}")
		return False


def check_and_install_dependencies(
	requirements_file: Optional[Path] = None,
	version_file: Optional[Path] = None,
	force_reinstall: bool = False,
	verbose: bool = False,
) -> Tuple[bool, str]:
	"""Check if dependencies are installed and install if necessary.

	Compares MD5 hash of requirements.txt with cached version. If they don't
	match or the version file is missing, dependencies are reinstalled.

	Args:
		requirements_file: Path to requirements.txt. If None, looks in package root.
		version_file: Path to version cache file. If None, uses default name.
		force_reinstall: If True, skip hash check and reinstall unconditionally.
		verbose: If True, show detailed output during installation.

	Returns:
		Tuple of (success: bool, message: str).
		- success: True if all requirements are met, False otherwise.
		- message: Human-readable status message.
	"""
	# Resolve file paths
	if requirements_file is None:
		requirements_file = Path(__file__).resolve().parent.parent / DEFAULT_REQUIREMENTS

	if version_file is None:
		version_file = requirements_file.parent / DEFAULT_VERSION_FILE

	# Check if requirements file exists
	if not requirements_file.exists():
		msg = f"Requirements file not found: {requirements_file}"
		logging.warning(msg)
		return True, msg  # Return True to not block startup

	# Compute current hash of requirements
	current_hash = compute_file_hash(requirements_file)
	if not current_hash:
		return False, "Failed to compute requirements file hash"

	# Load cached hash
	cached_hash = load_cached_hash(version_file) if not force_reinstall else None

	# Check if reinstall is needed
	if not force_reinstall and cached_hash == current_hash:
		msg = "Dependencies already installed and up-to-date"
		logging.debug(msg)
		return True, msg

	# Install or reinstall
	action = "Reinstalling" if cached_hash else "Installing"
	logging.info(f"{action} requirements from {requirements_file}")

	success = install_requirements(requirements_file, verbose=verbose)

	if success:
		# Save the hash for next time
		save_cached_hash(version_file, current_hash)
		msg = f"Dependencies {action.lower()} successfully"
		return True, msg
	else:
		msg = f"Failed to {action.lower()} dependencies"
		return False, msg


def setup_dependency_checker(
	log_level: int = logging.INFO,
) -> None:
	"""Configure logging for dependency checker.

	Args:
		log_level: Logging level (default: logging.INFO).
	"""
	if not logging.getLogger("cherryai_deps").handlers:
		handler = logging.StreamHandler(sys.stdout)
		formatter = logging.Formatter(
			"[%(name)s] %(levelname)s: %(message)s",
			datefmt="%Y-%m-%d %H:%M:%S",
		)
		handler.setFormatter(formatter)
		logger = logging.getLogger("cherryai_deps")
		logger.addHandler(handler)
		logger.setLevel(log_level)


# Convenience function for startup integration
def ensure_dependencies() -> bool:
	"""Ensure all dependencies are installed.

	This is the main entry point for checking dependencies at startup.
	Returns True if all is well, False if there were critical errors.

	Can be called from CherryAI.py main() before importing gui.
	"""
	setup_dependency_checker()
	logger = logging.getLogger("cherryai_deps")

	try:
		success, message = check_and_install_dependencies(verbose=False)
		if success:
			logger.debug(message)
		else:
			logger.warning(message)
		return success
	except Exception as exc:
		logger.error(f"Unexpected error checking dependencies: {exc}")
		return False


if __name__ == "__main__":
	# Allow script to be run directly for testing/manual reinstalls
	import argparse

	parser = argparse.ArgumentParser(
		description="Check and install CherryAI dependencies"
	)
	parser.add_argument(
		"--force",
		action="store_true",
		help="Force reinstall of all dependencies",
	)
	parser.add_argument(
		"--verbose",
		action="store_true",
		help="Show detailed output during installation",
	)
	parser.add_argument(
		"--requirements",
		type=Path,
		help="Path to requirements.txt (default: auto-detect)",
	)
	args = parser.parse_args()

	setup_dependency_checker(log_level=logging.DEBUG)
	success, message = check_and_install_dependencies(
		requirements_file=args.requirements,
		force_reinstall=args.force,
		verbose=args.verbose,
	)
	print(message)
	sys.exit(0 if success else 1)
