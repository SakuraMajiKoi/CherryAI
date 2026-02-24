"""CherryAI Tool - initial GUI and processing skeleton.

PEP8-compliant initial version implementing:
- Tkinter GUI skeleton with required layout
- Manifest read/write (JSON)
- Config persistence via INI
- Template loading from templates/ folder (JSON)
- Basic processing for txt/csv/tsv
- Graceful handling for json/xlsx with clear logs

This is a starting point; modes Protect Code and Anchor have basic behavior
implemented for Pre and Post using token mappings in the manifest.

Requirements: Python 3.10+
Optional: openpyxl (for .xlsx)
"""

from __future__ import annotations

# Early sys.path guard: ensure project root (parent of CherryAI) is on sys.path
# and register a lowercase `CherryAI` alias so VS Code runs (which sometimes use
# the package folder as CWD) can still import `CherryAI.*`.
import os
import sys
import types as _types

try:
	_this_file: Optional[str] = __file__
except NameError:
	_this_file = sys.argv[0] if sys.argv else None

if _this_file:
	_pkg_dir = os.path.dirname(os.path.abspath(_this_file))
	_project_root = os.path.dirname(_pkg_dir)
	if _project_root and _project_root not in sys.path:
		sys.path.insert(0, _project_root)

	if "CherryAI" not in sys.modules:
		sys.modules["CherryAI"] = _types.ModuleType("CherryAI")
		# expose the CherryAI package folder as package path so submodules
		# (e.g. CherryAI.modi) can be imported when this file is executed as a
		# script. Previously this used the project root which prevented
		# locating CherryAI subpackages.
		sys.modules["CherryAI"].__path__ = [_pkg_dir]


import csv
import datetime as dt
import json
import logging
import os
import re
import sys
import tkinter as tk
import configparser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, simpledialog
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

# Import strategy:
# - When run as a package/module (python -m CherryAI.CherryAI or imported), use relative imports.
# - When run as a script (python CherryAI.py), __package__ is None/empty; use absolute imports and ensure parent
#   package path is on sys.path so CherryAI.* imports resolve.
if __package__:
	# running as a module/package
	from .modi import load_modes, MODE_REGISTRY
	from .functions.modehelper import EMPTY_LINE_PLACEHOLDER
	from .functions.mainhelper import Operation, Manifest, Processor, MANIFEST_VERSION
	# Analysis module
	from .functions.analysis import analyze_file
	# App state helpers (IO consolidated in mainhelper)
	from .functions.mainhelper import (
		load_app_state,
		save_app_state,
		select_input_files,
		remember_last_selection,
	)
else:
	# running as a script: ensure parent dir is on sys.path and use absolute imports
	_pkg_path = Path(__file__).resolve().parent
	_root = str(_pkg_path.parent)
	if _root not in sys.path:
		sys.path.insert(0, _root)
	from CherryAI.modi import load_modes, MODE_REGISTRY
	from CherryAI.functions.modehelper import EMPTY_LINE_PLACEHOLDER
	from CherryAI.functions.mainhelper import Operation, Manifest, Processor, MANIFEST_VERSION
	# Analysis module
	from CherryAI.functions.analysis import analyze_file
	# App state helpers (IO consolidated in mainhelper)
	from CherryAI.functions.mainhelper import (
		load_app_state,
		save_app_state,
		select_input_files,
		remember_last_selection,
	)
	# Provide lowercase alias modules to avoid third-party or stale 'CherryAI' imports breaking
	import types as _types
	if "CherryAI" not in sys.modules:
		sys.modules["CherryAI"] = _types.ModuleType("CherryAI")
		# Ensure the package points at the actual CherryAI package directory
		# so imports like CherryAI.modi resolve correctly when running the
		# script directly.
		sys.modules["CherryAI"].__path__ = [str(_pkg_path)]
	
	_modi_mod = sys.modules.get("CherryAI.modi")
	if _modi_mod:
		sys.modules.setdefault("CherryAI.modi", _modi_mod)
	
	_funcs_mod = sys.modules.get("CherryAI.functions")
	if _funcs_mod:
		sys.modules.setdefault("CherryAI.functions", _funcs_mod)
		
	_models_mod = sys.modules.get("CherryAI.functions.models")
	if _models_mod:
		sys.modules.setdefault("CherryAI.functions.models", _models_mod)
	# No longer expose deprecated processor module alias


APP_NAME = "CherryAI"
# MANIFEST_VERSION is now imported from functions.mainhelper (v2.0)
CONFIG_FILE = Path(__file__).with_name("user") / "CherryAI.ini"
TEMPLATES_DIR = Path(__file__).with_name("templates")
OUTPUT_DIR = Path(__file__).with_name("Output")
MANIFESTS_DIR = Path(__file__).with_name("Projects")
LOGS_DIR = Path(__file__).with_name("logs")

# Placeholders and defaults
# Keep a canonical double-underscore dedup sentinel
DEDUP_PLACEHOLDER = "__DEDUP__"
DEDUP_THRESHOLD_DEFAULT = 1

# Debug UI toggle
DEBUG = True


MODES = [
	"Protect Code",
	"Custom Placeholder",
	"Only Remove",
	"Only replace after TL",
	"Only replace before TL",
	"Temporary Replacement",
	"Free",
	"Remove and Restore at Anchor",
	"Deduplicate Lines",
]

# ----------------------------- Utilities ---------------------------------- #


def derive_manifest_path(input_path: Path) -> Path:
	MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
	return MANIFESTS_DIR / f"{input_path.stem}.CherryAI.json"


def save_template_file(name: str, description: str, ops: List[Operation], overwrite: bool = False) -> Path:
	TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
	# create safe filename
	safe = re.sub(r"[^0-9A-Za-z_-]", "_", name.strip()).strip("_").lower()
	if not safe:
		safe = "template"
	base_path = TEMPLATES_DIR / f"{safe}.json"
	path = base_path
	if base_path.exists() and not overwrite:
		# version if not overwriting
		n = 2
		while True:
			cand = TEMPLATES_DIR / f"{safe}.v{n}.json"
			if not cand.exists():
				path = cand
				break
			n += 1
	data = {
		"name": name,
		"description": description,
		"operations": [op.__dict__ for op in ops],
	}
	path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
	return path


def template_base_path(name: str) -> Path:
	safe = re.sub(r"[^0-9A-Za-z_-]", "_", name.strip()).strip("_").lower()
	if not safe:
		safe = "template"
	return TEMPLATES_DIR / f"{safe}.json"


def derive_output_path(input_path: Path, stage: str) -> Path:
	"""Return a non-destructive versioned path inside OUTPUT_DIR.

	Pattern: filename.stage[.vN].ext where stage is 'CherryAI' or 'postplacement'.
	"""
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	stem = input_path.stem
	suffix = input_path.suffix
	base = OUTPUT_DIR / f"{stem}.{stage}{suffix}"
	if not base.exists():
		return base
	# increment version
	n = 2
	while True:
		candidate = OUTPUT_DIR / f"{stem}.{stage}.v{n}{suffix}"
		if not candidate.exists():
			return candidate
		n += 1


def now_iso() -> str:
	# Use timezone-aware UTC to avoid deprecation of utcnow()
	return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_delimiter(path: Path) -> str:
	if path.suffix.lower() == ".tsv":
		return "\t"
	return ","


def safe_regex_replace(text: str, pattern: str, repl: str) -> Tuple[str, int]:
	compiled = re.compile(pattern)
	return compiled.subn(repl, text)


def literal_replace(text: str, old: str, new: str) -> Tuple[str, int]:
	if not old:
		return text, 0
	count = text.count(old)
	return text.replace(old, new), count


def generate_token(prefix: str, index: int) -> str:
	# For compatibility with new spec, return unified placeholder name
	# Without numeric identifier. Index is unused but kept for signature stability.
	return "__PROTECTED__"


# State persistence and multi-file picker moved to functions.mainhelper


# ----------------------------- Processing --------------------------------- #


## Anchor helpers were moved to functions/modehelper.py


# ----------------------------- File IO ------------------------------------- #

# IO helpers (read_table, write_table, read_json_pairs, etc.) consolidated
# in functions/mainhelper.py - import directly from there when needed.


# ----------------------------- GUI launcher -------------------------------- #


def main() -> None:
	"""Entry point to start the Tkinter GUI app.

	The GUI implementation lives in gui/app.py (v2).
	Import locally to avoid any potential circular import during module initialization.
	"""
	# Local import to avoid circular dependency during module import
	# GUI v2: Step-partitioned workflow with pastel blue theme
	if __package__:
		from .gui.app import App
	else:
		from CherryAI.gui.app import App
	app = App()
	# Try to restore any previously saved UI state. The App may provide a
	# `restore_state` or `set_state` method; if not, we try common attributes.
	try:
		_saved = load_app_state()
		if _saved:
			if hasattr(app, "restore_state") and callable(app.restore_state):
				try:
					app.restore_state(_saved)
				except Exception:
					# best-effort restore; ignore failures
					pass
			elif hasattr(app, "set_state") and callable(app.set_state):
				try:
					app.set_state(_saved)
				except Exception:
					pass
			else:
				# try populating common attributes (selected_files is a common name)
				last = _saved.get("last_files")
				if isinstance(last, list):
					try:
						setattr(app, "selected_files", [Path(p) for p in last])
					except Exception:
						pass
	except Exception:
		# ignore any restore errors
		pass

	# Install a close handler that attempts to gather state from the App and save it.
	def _save_and_quit() -> None:
		state: Dict[str, Any] = {}
		try:
			if hasattr(app, "get_state") and callable(app.get_state):
				try:
					state = app.get_state() or {}
				except Exception:
					state = {}
			else:
				# collect a minimal sensible state
				_sel = getattr(app, "selected_files", None)
				if _sel:
					try:
						state["last_files"] = [str(p) for p in _sel]
					except Exception:
						# fall back to str() conversions
						state["last_files"] = [str(p) for p in _sel]
				# add any other simple serializable attributes the App exposes
				for attr in ("last_mode", "operations", "manifest"):
					val = getattr(app, attr, None)
					if val is not None:
						try:
							json.dumps(val)
							state[attr] = val
						except Exception:
							state[attr] = str(val)
		except Exception:
			# swallow any state-gathering errors
			pass
		# Persist state and then destroy the app
		save_app_state(state)
		try:
			app.destroy()
		except Exception:
			try:
				app.quit()
			except Exception:
				pass

	# Use protocol if available (typical for tkinter apps)
	try:
		app.protocol("WM_DELETE_WINDOW", _save_and_quit)
	except Exception:
		# If protocol isn't available, rely on normal mainloop exit.
		pass

	app.mainloop()


def run_smoke_test_cli(path: Optional[str] = None) -> int:
	"""CLI helper that runs the smoke test runner located in dev/smoke_test.

	If path is None, the runner scans the smoke_test folder for a manifest and an
	input file. Returns subprocess-like exit code.
	"""
	# import locally to avoid top-level dependency when importing module
	try:
		from CherryAI.dev.smoke_test.run_smoke import run_smoke_test
	except Exception:
		try:
			# package relative import when running as module
			from .dev.smoke_test.run_smoke import run_smoke_test
		except Exception as exc:
			print("Smoke runner module not available:", exc)
			return 2
	return run_smoke_test(path)


def run_analysis_cli(input_path: Optional[str]) -> int:
	"""CLI helper to run analysis on the given input file.

	Returns subprocess-like exit code.
	"""
	if not input_path:
		print("--analyze requires a path to an input file")
		return 2
	try:
		from pathlib import Path
		# Ensure logging is initialized via mainhelper
		if __package__:
			from .functions.mainhelper import setup_logger
		else:
			from CherryAI.functions.mainhelper import setup_logger
		log_path = LOGS_DIR / f"{Path(input_path).stem}.analysis.log"
		setup_logger(log_path, LOGS_DIR)
		analyze_file(Path(input_path), LOGS_DIR)
		print("Analysis completed. See logs folder for details.")
		return 0
	except Exception as exc:
		print("Analysis failed:", exc)
		return 1


def _cli_entry() -> None:
	import argparse

	# Check and install dependencies early (before GUI import)
	try:
		if __package__:
			from .functions.dependencies import ensure_dependencies
		else:
			from CherryAI.functions.dependencies import ensure_dependencies
		ensure_dependencies()
	except Exception as e:
		logger = logging.getLogger("cherryai")
		logger.warning(f"Dependency check failed (continuing anyway): {e}")

	parser = argparse.ArgumentParser(
		prog="CherryAI",
		description="CherryAI - Text preparation and translation tool",
		epilog="Use 'CherryAI help' or 'CherryAI help <command>' for more info."
	)
	subparsers = parser.add_subparsers(dest="command", help="CLI commands")

	# Legacy flags
	parser.add_argument("--run-smoke", nargs="?", const=".", help="Run smoke test in dev/smoke_test (optional path)")
	parser.add_argument("--analyze", nargs="?", help="Analyze an input file and write summary logs")

	# Estimate command
	est_parser = subparsers.add_parser("estimate", help="Estimate translation cost for file or folder")
	est_parser.add_argument("path", help="Input file or directory path")

	# Translate command
	trans_parser = subparsers.add_parser("translate", help="Run 1-Click translation for file or folder")
	trans_parser.add_argument("path", nargs="?", help="Input file or directory path (optional in interactive mode)")
	trans_parser.add_argument("-s", "--source", "--source-lang", dest="source_lang", 
		help="Source language code (e.g., ja, en, de)")
	trans_parser.add_argument("-t", "--target", "--target-lang", dest="target_lang",
		help="Target language code (e.g., en, de, fr)")
	trans_parser.add_argument("-i", "--interactive", action="store_true",
		help="Run in interactive mode with step-by-step guidance")
	trans_parser.add_argument("-n", "--lines", "--translate-lines", type=int, default=None,
		metavar="N", help="Translate only first N lines (default: all, or 100 if --partial)")
	trans_parser.add_argument("-y", "--yes", action="store_true",
		help="Skip confirmation prompts")
	trans_parser.add_argument("--partial", action="store_true",
		help="Enable partial translation mode (translate only first N lines)")
	# API override options
	trans_parser.add_argument("--model", dest="model",
		help="Override model (e.g., gpt-4o, gemini-2.0-flash)")
	trans_parser.add_argument("--temperature", type=float, dest="temperature",
		help="Override temperature (0.0-2.0)")
	trans_parser.add_argument("--timeout", type=int, dest="timeout",
		help="Override API timeout in seconds")
	trans_parser.add_argument("--chunk-size", type=int, dest="chunk_size",
		help="Override lines per API request (10-200)")
	trans_parser.add_argument("--preset", dest="preset",
		help="Apply an API preset (gemini_free, gemini_pro, gpt4, local)")
	# Line-by-line translation options
	trans_parser.add_argument("--line-by-line", action="store_true", dest="line_by_line",
		help="Translate each line individually (slower but more control)")
	trans_parser.add_argument("--context", "--context-lines", type=int, default=1, dest="context_lines",
		help="For line-by-line mode: adjacent lines as context (0-3, default 1)")
	# Thinking mode options
	trans_parser.add_argument("--thinking", action="store_true",
		help="Enable extended thinking mode for compatible models")
	trans_parser.add_argument("--thinking-budget", type=int, default=10000, dest="thinking_budget",
		help="Token budget for thinking mode (default: 10000)")
	# Chunking mode options
	trans_parser.add_argument("--chunk-mode", dest="chunk_mode", choices=["lines", "tokens", "hybrid"],
		help="Chunking strategy: lines (default), tokens, or hybrid")
	trans_parser.add_argument("--chunk-tokens", type=int, dest="chunk_max_tokens",
		help="Max tokens per chunk for tokens/hybrid mode (default: 4000)")
	# Logit bias / token banning options
	trans_parser.add_argument("--ban-tokens", dest="ban_tokens",
		help="Comma-separated tokens to ban (e.g., em_dash,smart_quotes,—)")
	trans_parser.add_argument("--logit-bias-preset", dest="logit_bias_preset",
		choices=["no_fancy_punctuation", "no_em_dash", "no_smart_quotes", 
		         "ascii_only_punctuation", "japanese_ellipsis_safe"],
		help="Apply a logit bias preset for token banning")
	# Retry strategy options
	trans_parser.add_argument("--retry-strategy", dest="retry_strategy",
		choices=["batch", "contextual", "isolated", "skip"],
		help="Retry strategy for failed translations (default: batch)")
	# Request caching options
	trans_parser.add_argument("--use-cache", action="store_true", dest="use_cache",
		help="Enable request caching to avoid duplicate API calls")
	trans_parser.add_argument("--cache-mode", dest="cache_mode",
		choices=["strict", "model_only", "any"],
		help="Cache matching mode (default: model_only)")
	trans_parser.add_argument("--clear-cache", action="store_true", dest="clear_cache",
		help="Clear the translation cache before starting")
	# Style preset options
	trans_parser.add_argument("--style-preset", dest="style_preset",
		help="Style preset(s) to apply (comma-separated, e.g., fantasy_medieval,archaic_english)")
	# Rate limit options
	trans_parser.add_argument("--rate-limit", action="store_true", dest="rate_limit_enabled",
		help="Enable rate limit management (tracks RPM/daily limits)")
	trans_parser.add_argument("--max-concurrent", type=int, dest="max_concurrent",
		help="Maximum concurrent API requests (default: 3)")
	trans_parser.add_argument("--safety-margin", type=float, dest="rate_limit_margin",
		help="Rate limit safety margin (0.0-0.5, default: 0.1)")
	# Local LLM options
	trans_parser.add_argument("--no-api-key", action="store_true", dest="no_api_key",
		help="Skip API key validation (for local LLMs that don't require keys)")
	trans_parser.add_argument("--check-local", action="store_true", dest="check_local",
		help="Check local LLM server health before translation")

	# Sample command (convenience wrapper for translate with limited lines)
	sample_parser = subparsers.add_parser("sample", help="Quick sample translation (default 50 lines)")
	sample_parser.add_argument("path", help="Input file path")
	sample_parser.add_argument("-n", "--lines", type=int, default=50,
		help="Number of lines to translate (default: 50)")
	sample_parser.add_argument("-s", "--source", dest="source_lang",
		help="Source language code")
	sample_parser.add_argument("-t", "--target", dest="target_lang",
		help="Target language code")
	# API override options for sample command
	sample_parser.add_argument("--model", dest="model",
		help="Override model")
	sample_parser.add_argument("--temperature", type=float, dest="temperature",
		help="Override temperature (0.0-2.0)")
	sample_parser.add_argument("--preset", dest="preset",
		help="Apply an API preset")

	# Test command
	test_parser = subparsers.add_parser("test", help="Run diagnostic tests on the pipeline")
	test_parser.add_argument("--skip-api", action="store_true", help="Skip API tests (offline mode)")
	
	# Languages command
	subparsers.add_parser("languages", help="List all supported languages")
	
	# Config command
	config_parser = subparsers.add_parser("config", help="View/set API configuration options")
	config_parser.add_argument("option", nargs="?", help="Configuration option name")
	config_parser.add_argument("value", nargs="?", help="Value to set (number for selection or direct input)")

	# IO command
	io_parser = subparsers.add_parser("io", help="Configure input/output file formats")
	io_parser.add_argument("option", nargs="?", 
		help="Option: extract, inject, standard, preserve_original, formats")
	io_parser.add_argument("value", nargs="?", 
		help="Format or value (txt, csv, tsv, json, xlsx, true/false)")
	io_parser.add_argument("value2", nargs="?",
		help="Second format (for 'standard' command)")

	# Glossary command
	glossary_parser = subparsers.add_parser("glossary", help="Manage translation glossary")
	glossary_parser.add_argument("action", nargs="?", 
		help="Action: list, search, add, path, export")
	glossary_parser.add_argument("args", nargs="*",
		help="Additional arguments for the action")

	# Local LLM command
	local_parser = subparsers.add_parser("local", help="Detect and check local LLM servers")
	local_parser.add_argument("action", nargs="?", default="detect",
		help="Action: detect, check, setup (default: detect)")
	local_parser.add_argument("--url", dest="url",
		help="Specific URL to check (e.g., http://localhost:1234/v1)")
	local_parser.add_argument("--provider", dest="provider",
		choices=["lmstudio", "ollama", "text-gen-webui"],
		help="Show setup instructions for a specific provider")

	# Help command
	help_parser = subparsers.add_parser("help", help="Show help information")
	help_parser.add_argument("topic", nargs="?", help="Topic for detailed help")

	args = parser.parse_args()

	# Dispatch
	if args.command == "estimate":
		try:
			if __package__:
				from .functions.CLI import run_estimate_cli
			else:
				from CherryAI.functions.CLI import run_estimate_cli
			sys.exit(run_estimate_cli(args.path))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "translate":
		try:
			if __package__:
				from .functions.CLI import run_translate_cli, run_interactive_cli
			else:
				from CherryAI.functions.CLI import run_translate_cli, run_interactive_cli
			
			# Interactive mode or no path provided
			if args.interactive or not args.path:
				sys.exit(run_interactive_cli())
			else:
				# Determine translate_lines value
				translate_lines = args.lines
				if translate_lines is None and args.partial:
					translate_lines = 100  # Default for partial mode
				
				# Build API overrides dict
				api_overrides = {}
				if args.model:
					api_overrides["model"] = args.model
				if args.temperature is not None:
					api_overrides["temperature"] = args.temperature
				if args.timeout is not None:
					api_overrides["timeout"] = args.timeout
				if args.chunk_size is not None:
					api_overrides["chunk_size"] = args.chunk_size
				if args.preset:
					api_overrides["preset"] = args.preset
				# Chunking mode overrides
				if hasattr(args, "chunk_mode") and args.chunk_mode:
					api_overrides["chunk_mode"] = args.chunk_mode
				if hasattr(args, "chunk_max_tokens") and args.chunk_max_tokens:
					api_overrides["chunk_max_tokens"] = args.chunk_max_tokens
				# Logit bias overrides
				if hasattr(args, "ban_tokens") and args.ban_tokens:
					api_overrides["banned_tokens"] = args.ban_tokens
				if hasattr(args, "logit_bias_preset") and args.logit_bias_preset:
					api_overrides["logit_bias_preset"] = args.logit_bias_preset
				# Retry strategy override
				if hasattr(args, "retry_strategy") and args.retry_strategy:
					api_overrides["retry_strategy"] = args.retry_strategy
				# Cache overrides
				if hasattr(args, "use_cache") and args.use_cache:
					api_overrides["use_cache"] = True
				if hasattr(args, "cache_mode") and args.cache_mode:
					api_overrides["cache_mode"] = args.cache_mode
				if hasattr(args, "clear_cache") and args.clear_cache:
					api_overrides["clear_cache"] = True
				# Style preset override
				if hasattr(args, "style_preset") and args.style_preset:
					api_overrides["style_preset"] = args.style_preset
				# Rate limit overrides
				if hasattr(args, "rate_limit_enabled") and args.rate_limit_enabled:
					api_overrides["rate_limit_enabled"] = True
				if hasattr(args, "max_concurrent") and args.max_concurrent is not None:
					api_overrides["max_concurrent"] = args.max_concurrent
				if hasattr(args, "rate_limit_margin") and args.rate_limit_margin is not None:
					api_overrides["rate_limit_margin"] = args.rate_limit_margin
				# Local LLM overrides
				if hasattr(args, "no_api_key") and args.no_api_key:
					api_overrides["no_api_key"] = True
				if hasattr(args, "check_local") and args.check_local:
					api_overrides["check_local"] = True
				
				sys.exit(run_translate_cli(
					args.path,
					source_lang=args.source_lang,
					target_lang=args.target_lang,
					translate_lines=translate_lines,
					api_overrides=api_overrides if api_overrides else None,
					line_by_line=getattr(args, "line_by_line", False),
					context_lines=getattr(args, "context_lines", 1),
					thinking=getattr(args, "thinking", False),
					thinking_budget=getattr(args, "thinking_budget", 10000),
					skip_confirmation=getattr(args, "yes", False),
				))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "sample":
		try:
			if __package__:
				from .functions.CLI import run_sample_cli
			else:
				from CherryAI.functions.CLI import run_sample_cli
			
			# Build API overrides dict for sample
			api_overrides = {}
			if args.model:
				api_overrides["model"] = args.model
			if args.temperature is not None:
				api_overrides["temperature"] = args.temperature
			if args.preset:
				api_overrides["preset"] = args.preset
			
			sys.exit(run_sample_cli(
				args.path,
				lines=args.lines,
				source_lang=args.source_lang,
				target_lang=args.target_lang,
				api_overrides=api_overrides if api_overrides else None
			))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "test":
		try:
			if __package__:
				from .functions.CLI import run_test_cli
			else:
				from CherryAI.functions.CLI import run_test_cli
			sys.exit(run_test_cli(skip_api=args.skip_api))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "languages":
		try:
			if __package__:
				from .functions.CLI import run_list_languages_cli
			else:
				from CherryAI.functions.CLI import run_list_languages_cli
			sys.exit(run_list_languages_cli())
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "config":
		try:
			if __package__:
				from .functions.CLI import run_config_cli
			else:
				from CherryAI.functions.CLI import run_config_cli
			sys.exit(run_config_cli(
				option=args.option,
				value=args.value
			))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "io":
		try:
			if __package__:
				from .functions.CLI import run_io_cli
			else:
				from CherryAI.functions.CLI import run_io_cli
			sys.exit(run_io_cli(
				option=args.option,
				value=args.value,
				value2=args.value2
			))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "glossary":
		try:
			if __package__:
				from .functions.CLI import run_glossary_cli
			else:
				from CherryAI.functions.CLI import run_glossary_cli
			sys.exit(run_glossary_cli(
				action=args.action,
				args=args.args
			))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.command == "local":
		try:
			if __package__:
				from .functions.local_llm import (
					detect_local_servers, check_server_health,
					format_server_status, get_provider_setup_instructions,
					LocalLLMProvider,
				)
			else:
				from CherryAI.functions.local_llm import (
					detect_local_servers, check_server_health,
					format_server_status, get_provider_setup_instructions,
					LocalLLMProvider,
				)
			
			action = args.action or "detect"
			
			if action == "detect":
				print("Scanning for local LLM servers...\n")
				servers = detect_local_servers()
				print(format_server_status(servers))
				sys.exit(0 if any(s.is_healthy for s in servers) else 1)
			
			elif action == "check":
				url = args.url or "http://localhost:1234/v1"
				print(f"Checking server at {url}...\n")
				info = check_server_health(url)
				if info.is_healthy:
					print(f"✅ Server is healthy!")
					print(f"   Response time: {info.response_time_ms:.0f}ms")
					if info.models:
						print(f"   Available models: {', '.join(info.models[:5])}")
						if len(info.models) > 5:
							print(f"   ... and {len(info.models) - 5} more")
					sys.exit(0)
				else:
					print(f"❌ Server is not responding")
					print(f"   Error: {info.error_message}")
					sys.exit(1)
			
			elif action == "setup":
				provider_name = args.provider
				if provider_name:
					provider_map = {
						"lmstudio": LocalLLMProvider.LMSTUDIO,
						"ollama": LocalLLMProvider.OLLAMA,
						"text-gen-webui": LocalLLMProvider.TEXT_GEN_WEBUI,
					}
					provider = provider_map.get(provider_name, LocalLLMProvider.GENERIC)
				else:
					provider = LocalLLMProvider.GENERIC
				print(get_provider_setup_instructions(provider))
				sys.exit(0)
			
			else:
				print(f"Unknown action: {action}")
				print("Available actions: detect, check, setup")
				sys.exit(1)
				
		except ImportError as e:
			print(f"Failed to import local_llm module: {e}")
			sys.exit(1)

	if args.command == "help":
		try:
			if __package__:
				from .functions.CLI import run_help_cli
			else:
				from CherryAI.functions.CLI import run_help_cli
			sys.exit(run_help_cli(topic=args.topic))
		except ImportError as e:
			print(f"Failed to import CLI module: {e}")
			sys.exit(1)

	if args.run_smoke is not None:
		rc = run_smoke_test_cli(args.run_smoke)
		raise SystemExit(rc)
	if args.analyze is not None:
		rc = run_analysis_cli(args.analyze)
		raise SystemExit(rc)
	
	main()


if __name__ == "__main__":
	_cli_entry()