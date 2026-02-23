"""Encrypted API configuration manager for CherryAI.

This module manages ``user/API.ini`` — the secure store for:

- API provider settings (non-secret)
- Encrypted API key (AES-256 via Fernet, keyed from user password)
- API presets (name → base_url|model|temperature|timeout|rate_limit)
- Rate-limit settings per model

Security model
--------------
1. The user sets a *password* once.  The password is hashed with **bcrypt**
   (work factor 10, per the HiveSystems 2025 benchmark table) and the hash is
   stored in ``[security] password_hash``.

2. A random ``PBKDF2-HMAC-SHA256`` derivation key is created and stored in
   ``[security] key_salt`` (hex-encoded random 32 bytes).

3. API keys are encrypted with **AES-256-CBC via Fernet** (from the
   ``cryptography`` package).  The Fernet key is derived from
   ``PBKDF2HMAC(password, salt, 390_000 iterations, SHA-256)``.

4. ``verify_password()`` has a **deliberate 100 ms minimum delay** to slow
   brute-force attempts even before bcrypt's own cost kicks in.

Password strength tiers (HiveSystems 2025 – bcrypt WF-10, 12× RTX 5090)
-------------------------------------------------------------------------
Colour    Label      Criteria
Purple    Instantly  < 8 chars, any composition
Red       Weak       8 chars, numbers or lowercase only
Orange    Good       8-11 chars mixed, or 8-9 chars with all types
Yellow    Great      12-15 chars, has numbers & letters; or 12+ mixed
Green     Safe       16+ chars any composition; or 12+ with upper+lower+digit+symbol
"""

from __future__ import annotations

import base64
import configparser
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports (graceful degradation if not installed)
# ---------------------------------------------------------------------------
try:
    import bcrypt as _bcrypt  # type: ignore
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False
    logger.warning("bcrypt not installed — password hashing disabled")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed — API key encryption disabled")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BCRYPT_WORK_FACTOR = 10   # HiveSystems 2025 recommendation
_KDF_ITERATIONS = 390_000  # OWASP 2023 recommendation for PBKDF2-SHA256
_BRUTEFORCE_DELAY_S = 0.1  # deliberate 100 ms trap

_API_INI_FILENAME = "API.ini"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _get_user_dir() -> Path:
    """Return the user/ directory next to the package root."""
    here = Path(__file__).resolve()
    root = here.parent.parent   # CherryAI root
    user = root / "user"
    user.mkdir(parents=True, exist_ok=True)
    return user


def get_api_ini_path() -> Path:
    """Return the canonical path to user/API.ini."""
    return _get_user_dir() / _API_INI_FILENAME


# ---------------------------------------------------------------------------
# INI helpers
# ---------------------------------------------------------------------------

def _load() -> configparser.ConfigParser:
    """Load API.ini, creating it with defaults if absent."""
    cfg = configparser.ConfigParser()
    cfg.optionxform = str  # preserve case
    path = get_api_ini_path()
    if path.exists():
        cfg.read(str(path), encoding="utf-8")
    _ensure_sections(cfg)
    return cfg


def _save(cfg: configparser.ConfigParser) -> None:
    path = get_api_ini_path()
    with open(str(path), "w", encoding="utf-8") as fh:
        cfg.write(fh)


def _ensure_sections(cfg: configparser.ConfigParser) -> None:
    for sec in ("security", "api", "api_keys", "api_presets", "rate_limits",
                "translation", "glossary"):
        if not cfg.has_section(sec):
            cfg.add_section(sec)


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------

def is_password_set() -> bool:
    """Return True if a master password has been configured."""
    cfg = _load()
    return bool(cfg.get("security", "password_hash", fallback="").strip())


def set_password(password: str) -> bool:
    """Hash *password* with bcrypt (WF-10) and store in API.ini.

    Also generates a fresh KDF salt for key derivation.

    Returns True on success, False if bcrypt unavailable.
    """
    if not _BCRYPT_AVAILABLE:
        logger.error("bcrypt unavailable — cannot set password")
        return False
    pw_bytes = password.encode("utf-8")
    pw_hash = _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt(rounds=_BCRYPT_WORK_FACTOR))
    kdf_salt = os.urandom(32)

    cfg = _load()
    cfg.set("security", "password_hash", pw_hash.decode("utf-8"))
    cfg.set("security", "key_salt", kdf_salt.hex())
    _save(cfg)
    logger.info("Master password set (bcrypt WF-%d)", _BCRYPT_WORK_FACTOR)
    return True


def verify_password(password: str) -> bool:
    """Verify *password* against the stored bcrypt hash.

    Enforces a deliberate 100 ms minimum delay as a brute-force trap.

    Returns True if correct, False otherwise (or if no password set).
    """
    t_start = time.monotonic()
    result = _verify_password_inner(password)
    # Deliberate minimum delay — do not remove
    elapsed = time.monotonic() - t_start
    if elapsed < _BRUTEFORCE_DELAY_S:
        time.sleep(_BRUTEFORCE_DELAY_S - elapsed)
    return result


def _verify_password_inner(password: str) -> bool:
    if not _BCRYPT_AVAILABLE:
        return False
    cfg = _load()
    pw_hash = cfg.get("security", "password_hash", fallback="").strip()
    if not pw_hash:
        return False
    try:
        return _bcrypt.checkpw(password.encode("utf-8"), pw_hash.encode("utf-8"))
    except Exception as exc:
        logger.error("bcrypt verify error: %s", exc)
        return False


def change_password(old_password: str, new_password: str) -> Tuple[bool, str]:
    """Change the master password.

    Re-encrypts all stored API keys with the new password.

    Returns (success, message).
    """
    if not verify_password(old_password):
        return False, "Current password is incorrect."
    # Decrypt all keys with old password first
    cfg = _load()
    decrypted: dict[str, str] = {}
    if cfg.has_section("api_keys"):
        for name, enc_val in cfg.items("api_keys"):
            try:
                decrypted[name] = _decrypt_value(enc_val, old_password, cfg)
            except Exception:
                decrypted[name] = ""  # lose the key if decrypt fails
    # Set new password (generates new salt)
    if not set_password(new_password):
        return False, "Failed to hash new password."
    # Re-encrypt keys with new password
    cfg = _load()  # reload to pick up new salt
    for name, plaintext in decrypted.items():
        if plaintext:
            enc = _encrypt_value(plaintext, new_password, cfg)
            cfg.set("api_keys", name, enc)
    _save(cfg)
    return True, "Password changed successfully."


# ---------------------------------------------------------------------------
# Key derivation (PBKDF2)
# ---------------------------------------------------------------------------

def _derive_fernet_key(password: str, salt_hex: str) -> bytes:
    """Derive a 32-byte Fernet key from *password* and *salt_hex*."""
    salt = bytes.fromhex(salt_hex)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


# ---------------------------------------------------------------------------
# Encryption / Decryption helpers
# ---------------------------------------------------------------------------

def _encrypt_value(plaintext: str, password: str, cfg: configparser.ConfigParser) -> str:
    """Encrypt *plaintext* with Fernet derived from *password*."""
    if not _CRYPTO_AVAILABLE:
        return plaintext  # fallback: store plain if crypto unavailable
    salt_hex = cfg.get("security", "key_salt", fallback="")
    if not salt_hex:
        return plaintext
    fernet_key = _derive_fernet_key(password, salt_hex)
    f = Fernet(fernet_key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def _decrypt_value(ciphertext: str, password: str, cfg: configparser.ConfigParser) -> str:
    """Decrypt *ciphertext* with Fernet derived from *password*."""
    if not _CRYPTO_AVAILABLE:
        return ciphertext  # fallback: return as-is
    salt_hex = cfg.get("security", "key_salt", fallback="")
    if not salt_hex:
        return ciphertext
    try:
        fernet_key = _derive_fernet_key(password, salt_hex)
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# API key storage
# ---------------------------------------------------------------------------

def _api_key_option(provider: str, name: str) -> str:
    """Build the INI option name for a named API key.

    Format: ``provider, name``  (case-preserved).
    """
    return f"{provider.strip()}, {name.strip()}"


def set_api_key(
    provider: str,
    key: str,
    password: str,
    name: str = "default",
) -> bool:
    """Encrypt and store an API key for *provider* under *name*.

    The key is stored in ``[api_keys]`` as ``provider, name = <encrypted>``.

    Returns False if encryption is unavailable or password incorrect.
    """
    if not verify_password(password):
        return False
    cfg = _load()
    encrypted = _encrypt_value(key, password, cfg)
    option = _api_key_option(provider, name)
    cfg.set("api_keys", option, encrypted)
    _save(cfg)
    return True


def get_api_key(
    provider: str,
    password: str,
    name: str = "default",
) -> Optional[str]:
    """Retrieve and decrypt the API key for *provider* / *name*.

    Returns None if key not found, password wrong, or decryption fails.
    """
    if not verify_password(password):
        return None
    cfg = _load()
    option = _api_key_option(provider, name)
    enc = cfg.get("api_keys", option, fallback="").strip()
    if not enc:
        return None
    return _decrypt_value(enc, password, cfg) or None


def list_api_keys() -> list[tuple[str, str]]:
    """Return ``[(provider, name), …]`` for every saved API key.

    Does **not** require the password — only metadata is returned.
    """
    cfg = _load()
    if not cfg.has_section("api_keys"):
        return []
    result: list[tuple[str, str]] = []
    for option in cfg.options("api_keys"):
        if ", " in option:
            provider, name = option.split(", ", 1)
            result.append((provider.strip(), name.strip()))
        else:
            # Legacy single-name keys (provider only, no name)
            result.append((option.strip(), "default"))
    return result


def delete_api_key(provider: str, name: str = "default") -> bool:
    """Remove a saved API key.  Returns True if it existed."""
    cfg = _load()
    option = _api_key_option(provider, name)
    if cfg.has_option("api_keys", option):
        cfg.remove_option("api_keys", option)
        _save(cfg)
        return True
    return False


# ---------------------------------------------------------------------------
# API provider settings (non-secret)
# ---------------------------------------------------------------------------

def get_api_setting(key: str, fallback: str = "") -> str:
    """Read a non-secret setting from [api] section."""
    return _load().get("api", key, fallback=fallback)


def set_api_setting(key: str, value: str) -> None:
    """Write a non-secret setting to [api] section."""
    cfg = _load()
    cfg.set("api", key, value)
    _save(cfg)


# ---------------------------------------------------------------------------
# API presets
# ---------------------------------------------------------------------------

def get_api_presets() -> dict[str, str]:
    """Return all API presets as {name: 'base_url|model|temp|timeout|rpm'}."""
    cfg = _load()
    if not cfg.has_section("api_presets"):
        return {}
    return dict(cfg.items("api_presets"))


def set_api_preset(name: str, base_url: str, model: str,
                   temperature: float, timeout: int, rpm: int) -> None:
    """Save an API preset."""
    cfg = _load()
    value = f"{base_url}|{model}|{temperature}|{timeout}|{rpm}"
    cfg.set("api_presets", name.lower(), value)
    _save(cfg)


def delete_api_preset(name: str) -> bool:
    """Delete an API preset.  Returns True if it existed."""
    cfg = _load()
    if cfg.has_section("api_presets") and cfg.has_option("api_presets", name.lower()):
        cfg.remove_option("api_presets", name.lower())
        _save(cfg)
        return True
    return False


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------

def get_rate_limit(model: str) -> dict[str, int]:
    """Return rate limit settings for *model* as {rpm, tpm, rpd, tpd}."""
    cfg = _load()
    raw = cfg.get("rate_limits", model.lower(), fallback="").strip()
    defaults = {"rpm": 60, "tpm": 100000, "rpd": 0, "tpd": 0}
    if not raw:
        return defaults
    parts = raw.split("|")
    try:
        keys = list(defaults.keys())
        return {k: int(parts[i]) if i < len(parts) else defaults[k]
                for i, k in enumerate(keys)}
    except ValueError:
        return defaults


def set_rate_limit(model: str, rpm: int, tpm: int, rpd: int = 0, tpd: int = 0) -> None:
    """Save rate limits for *model*."""
    cfg = _load()
    cfg.set("rate_limits", model.lower(), f"{rpm}|{tpm}|{rpd}|{tpd}")
    _save(cfg)


# ---------------------------------------------------------------------------
# API profile settings (non-secret: model, temperature, base_url etc.)
# Phase 62: Consolidates api_profiles.ini into user/API.ini [translation] / [glossary]
# ---------------------------------------------------------------------------

_KNOWN_PROFILES = ("translation", "glossary")


def get_profile_setting(profile: str, key: str, fallback: str = "") -> str:
    """Read one non-secret setting from a profile section (e.g. ``[translation]``).

    Args:
        profile: Section name, e.g. ``"translation"`` or ``"glossary"``.
        key:     Option name, e.g. ``"model"`` or ``"base_url"``.
        fallback: Value to return if not found.
    """
    return _load().get(profile.lower(), key, fallback=fallback)


def set_profile_setting(profile: str, key: str, value: str) -> None:
    """Write one non-secret setting to a profile section.

    The section is created automatically if it does not exist.
    """
    cfg = _load()
    sec = profile.lower()
    if not cfg.has_section(sec):
        cfg.add_section(sec)
    cfg.set(sec, key, value)
    _save(cfg)


def get_all_profile_settings(profile: str) -> dict[str, str]:
    """Return a dict of all non-secret settings for *profile*.

    Returns an empty dict if the section does not exist.
    """
    cfg = _load()
    sec = profile.lower()
    if not cfg.has_section(sec):
        return {}
    return dict(cfg.items(sec))


def migrate_profiles_ini(profiles_ini_path: Path) -> int:
    """Migrate ``api_profiles.ini`` non-secret settings into ``user/API.ini``.

    For each section in *profiles_ini_path* the non-secret fields (provider,
    base_url, model, temperature, timeout, retries, rate_limit_requests,
    chunk_size, display_name, system_prompt_tweak) are written to the
    matching section in API.ini.

    The ``api_key`` field is intentionally excluded (it is handled by
    ``set_api_key()`` with encryption).

    After migration the source file is renamed to ``api_profiles.ini.migrated``.

    Returns:
        Number of settings migrated (0 if file absent or already migrated).
    """
    if not profiles_ini_path.exists():
        return 0

    src = configparser.ConfigParser()
    src.optionxform = str
    try:
        src.read(str(profiles_ini_path), encoding="utf-8")
    except Exception as exc:
        logger.warning("Cannot read api_profiles.ini for migration: %s", exc)
        return 0

    cfg = _load()
    count = 0
    _NON_SECRET_KEYS = {
        "provider", "base_url", "model", "temperature", "timeout",
        "retries", "rate_limit_requests", "chunk_size",
        "display_name", "system_prompt_tweak",
    }
    for section in src.sections():
        sec = section.lower()
        if not cfg.has_section(sec):
            cfg.add_section(sec)
        for key, value in src.items(section):
            if key.lower() == "api_key":
                continue  # encrypted separately — don't migrate plain-text key
            if key.lower() not in _NON_SECRET_KEYS:
                continue
            cfg.set(sec, key, value)
            count += 1

    if count:
        _save(cfg)
        try:
            profiles_ini_path.rename(profiles_ini_path.with_suffix(".ini.migrated"))
        except Exception as exc:
            logger.warning("Could not rename api_profiles.ini: %s", exc)
        logger.info("Migrated %d settings from api_profiles.ini → API.ini", count)

    return count


# ---------------------------------------------------------------------------
# Legacy migration helpers
# ---------------------------------------------------------------------------

def migrate_from_ini(source_ini_path: Path, password: Optional[str] = None) -> int:
    """Migrate API settings from a legacy CherryAI.ini to API.ini.

    Reads ``[api]`` and ``[api_presets]`` sections from *source_ini_path*
    and copies all non-secret settings.  If *password* is provided, the
    ``api_key`` value is encrypted and stored; otherwise it is discarded.

    Returns the number of settings migrated.
    """
    src = configparser.ConfigParser()
    src.optionxform = str
    src.read(str(source_ini_path), encoding="utf-8")

    cfg = _load()
    count = 0

    # Migrate [api] → [api] (skip api_key which needs encryption)
    if src.has_section("api"):
        for key, val in src.items("api"):
            if key.lower() == "api_key":
                continue  # handle separately below
            cfg.set("api", key, val)
            count += 1
        # Migrate api_key if password provided
        raw_key = src.get("api", "api_key", fallback="").strip()
        if raw_key and password and verify_password(password):
            enc = _encrypt_value(raw_key, password, cfg)
            provider = src.get("api", "provider", fallback="default").strip()
            cfg.set("api_keys", provider.lower(), enc)
            count += 1

    # Migrate [api_presets]
    if src.has_section("api_presets"):
        for name, val in src.items("api_presets"):
            cfg.set("api_presets", name, val)
            count += 1

    _save(cfg)
    logger.info("Migrated %d settings from %s → API.ini", count, source_ini_path)
    return count


# ---------------------------------------------------------------------------
# Provider default base URLs
# ---------------------------------------------------------------------------

PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1/",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "anthropic": "https://api.anthropic.com/v1/",
    "mistral": "https://api.mistral.ai/v1/",
    "ollama": "http://localhost:11434/v1/",
    "lmstudio": "http://localhost:1234/v1/",
    "local": "http://localhost:1234/v1/",
}


def test_api_connection(
    api_key: str,
    provider: str = "openai",
    base_url: str = "",
    timeout: float = 15.0,
) -> Tuple[bool, str]:
    """Test connectivity to an API provider by listing models.

    Uses the OpenAI-compatible ``models.list()`` endpoint which all major
    providers support.

    Args:
        api_key:  The API key to authenticate with.
        provider: Provider name (openai, gemini, mistral, …).
        base_url: Custom base URL (empty → provider default).
        timeout:  Request timeout in seconds.

    Returns:
        ``(success, message)`` — *message* contains model count on
        success or a descriptive error string on failure.
    """
    if not api_key or not api_key.strip():
        return False, "No API key provided."

    url = base_url.strip() or PROVIDER_BASE_URLS.get(provider.lower(), "")
    if not url:
        return False, f"No base URL for provider '{provider}'."

    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return False, "openai package not installed."

    try:
        client = OpenAI(api_key=api_key.strip(), base_url=url, timeout=timeout)
        models = client.models.list()
        count = sum(1 for _ in models)
        return True, f"Connection successful — {count} model(s) available."
    except Exception as exc:
        err_msg = str(exc)
        # Extract the most useful part of the error
        if "401" in err_msg or "Unauthorized" in err_msg:
            return False, "Authentication failed — invalid API key."
        if "403" in err_msg or "Forbidden" in err_msg:
            return False, "Access denied — check API key permissions."
        if "404" in err_msg or "Not Found" in err_msg:
            return False, f"Endpoint not found — check base URL: {url}"
        if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            return False, "Connection timed out — check URL and network."
        if "Connection" in err_msg and ("refused" in err_msg or "error" in err_msg.lower()):
            return False, f"Connection refused — is the server running at {url}?"
        return False, f"Connection failed: {err_msg}"


# ---------------------------------------------------------------------------
# Password strength meter (HiveSystems 2025 bcrypt WF-10, 12× RTX 5090)
# ---------------------------------------------------------------------------

class PasswordStrength:
    """Assess password strength using HiveSystems 2025 table tiers."""

    INSTANTLY = "Instantly"   # Purple
    WEAK      = "Weak"        # Red
    GOOD      = "Good"        # Orange
    GREAT     = "Great"       # Yellow
    SAFE      = "Safe"        # Green

    # Colour map for GUI use
    COLOURS = {
        INSTANTLY: "#9B59B6",   # Purple
        WEAK:      "#E74C3C",   # Red
        GOOD:      "#E67E22",   # Orange
        GREAT:     "#F1C40F",   # Yellow
        SAFE:      "#2ECC71",   # Green
    }

    @staticmethod
    def _char_types(pw: str) -> tuple[bool, bool, bool, bool]:
        """Return (has_lower, has_upper, has_digit, has_symbol)."""
        return (
            any(c.islower() for c in pw),
            any(c.isupper() for c in pw),
            any(c.isdigit() for c in pw),
            any(not c.isalnum() for c in pw),
        )

    @classmethod
    def assess(cls, password: str) -> tuple[str, str]:
        """Return (tier_label, hex_colour) for *password*.

        Based on HiveSystems 2025 bcrypt (WF-10) crack-time table with
        12× RTX 5090 GPUs.
        """
        length = len(password)
        has_lower, has_upper, has_digit, has_symbol = cls._char_types(password)
        type_count = sum([has_lower, has_upper, has_digit, has_symbol])

        # Tier 1: Instantly crackable
        if length < 8:
            return cls.INSTANTLY, cls.COLOURS[cls.INSTANTLY]

        # Tier 2: Weak — 8 chars, low-complexity only
        if length == 8:
            if type_count == 1 and (has_digit or has_lower):
                return cls.WEAK, cls.COLOURS[cls.WEAK]

        # Tier 5: Safe — 16+ chars always safe; 12+ with all 4 types
        if length >= 16:
            return cls.SAFE, cls.COLOURS[cls.SAFE]
        if length >= 12 and type_count == 4:
            return cls.SAFE, cls.COLOURS[cls.SAFE]

        # Tier 4: Great — 12+ chars with ≥ 3 types
        if length >= 12 and type_count >= 3:
            return cls.GREAT, cls.COLOURS[cls.GREAT]
        if length >= 15 and type_count >= 2:
            return cls.GREAT, cls.COLOURS[cls.GREAT]

        # Tier 3: Good — everything else
        return cls.GOOD, cls.COLOURS[cls.GOOD]

    @classmethod
    def meter_text(cls, password: str) -> str:
        """Return a human-readable description e.g. 'Safe ✓ (16+ chars, all types)'."""
        tier, _ = cls.assess(password)
        length = len(password)
        types = sum(cls._char_types(password))
        return f"{tier} ({length} chars, {types} character type{'s' if types != 1 else ''})"
