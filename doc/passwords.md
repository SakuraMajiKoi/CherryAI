CHERRYAI - PASSWORD & ENCRYPTION SYSTEM

For Developers and Security-Conscious Users

=============================================================================

OVERVIEW
--------

CherryAI uses a master-password system to protect API keys stored on disk.
No API key is ever written in plaintext.  The entire security stack is
implemented in ``functions/api_config.py`` and the UI lives in
``gui/dialogs/password_dialog.py`` and ``gui/widgets/password_strength.py``.


=============================================================================

FILE LOCATIONS
--------------

  user/API.ini          Encrypted configuration file (never commit this)
  functions/api_config.py       Business logic (hashing, encryption, strength)
  gui/dialogs/password_dialog.py  Set / Change / Verify password dialogs
  gui/widgets/password_strength.py  Reusable Tkinter strength-meter widget


=============================================================================

STORAGE LAYOUT  (user/API.ini)
--------------------------------

  [security]
  password_hash = $2b$10$...   ; bcrypt WF-10 hash of the master password
  key_salt      = <hex>        ; 32-byte random salt for PBKDF2 key derivation

  [api_keys]
  openai  = gAAAAAB...         ; Fernet-encrypted, base64-encoded ciphertext
  gemini  = gAAAAAB...
  ...

All other sections ([api], [api_presets], [rate_limits]) hold non-secret
configuration values and are not encrypted.


=============================================================================

HASHING  (bcrypt WF-10)
-----------------------

The master password is hashed with bcrypt at work-factor 10 (WF-10) before
being stored:

  import bcrypt
  salt  = bcrypt.gensalt(rounds=10)
  digest = bcrypt.hashpw(password.encode(), salt)

WF-10 means bcrypt runs 2^10 = 1 024 rounds of the BlowFish cipher per hash
attempt.  On 12× RTX 5090 GPUs (the HiveSystems 2025 benchmark setup) this
yields roughly 1 000 000 hash attempts per second — far fewer than the
billions/second possible with simpler algorithms like MD5.

Work-factor reference (HiveSystems 2025, 12× RTX 5090):
  WF-10  ≈  1 000 000 attempts/sec  (used by CherryAI)
  WF-12  ≈    250 000 attempts/sec  (2× slower)
  WF-14  ≈     62 500 attempts/sec  (4× slower again)

The password hash is used ONLY for authentication.  It is NOT used as the
encryption key — see the PBKDF2 section below.


=============================================================================

100 ms BRUTE-FORCE TRAP
------------------------

``api_config.verify_password()`` always takes at least 100 ms to return,
regardless of whether the password is correct:

  _VERIFY_MIN_MS = 0.100  # 100 milliseconds

  def verify_password(password: str) -> bool:
      t0 = time.monotonic()
      ok = bcrypt.checkpw(...)
      elapsed = time.monotonic() - t0
      if elapsed < _VERIFY_MIN_MS:
          time.sleep(_VERIFY_MIN_MS - elapsed)
      return ok

This imposes an application-level rate limit: even if an attacker bypasses
the bcrypt cost, they still get at most 10 password attempts per second
through this function.

⚠️  DO NOT REMOVE this delay.  It is a deliberate security control, not
    performance waste.


=============================================================================

KEY DERIVATION  (PBKDF2-SHA256)
---------------------------------

After the password is verified, a 256-bit AES encryption key is derived
using PBKDF2-HMAC-SHA256:

  salt      = os.urandom(32)          # 32 random bytes, stored in [security]
  iterations = 390_000                # NIST SP 800-132 minimum for SHA-256
  dk         = hashlib.pbkdf2_hmac(
                   "sha256",
                   password.encode(),
                   salt,
                   390_000,
                   dklen=32,
               )

The salt is stored as hex in ``[security] key_salt`` and read back on each
unlock.  Because the salt is random and unique per installation, rainbow
tables are useless.

390 000 iterations is the OWASP/NIST 2023 recommended minimum for
PBKDF2-SHA256.  CherryAI uses exactly this value.


=============================================================================

ENCRYPTION  (Fernet / AES-256-CBC + HMAC-SHA256)
-------------------------------------------------

The 256-bit key derived by PBKDF2 is given to
``cryptography.fernet.Fernet``, which implements authenticated symmetric
encryption:

  Algorithm    : AES-128-CBC + HMAC-SHA256  (128-bit AES key, 128-bit HMAC key,
                 256-bit total Fernet key)
  Key input    : 32-byte raw key (URL-safe base64 encoded before passing to Fernet)
  Ciphertext   : URL-safe base64, starts with "gAAAAA"

Despite using AES-128 internally, Fernet's effective security is equivalent
to 256-bit because the key is 256 bits split 50/50 between the cipher and
the MAC.  An attacker must break both halves simultaneously.

The encrypted API key ciphertext is stored per-provider in ``[api_keys]``.


=============================================================================

PASSWORD STRENGTH TIERS  (HiveSystems 2025)
--------------------------------------------

Crack times are estimated for 12× RTX 5090 GPUs attacking bcrypt WF-10.

  Tier        Colour    Hex       Crack time        Condition
  ----------  --------  -------   ----------------  -------------------------------
  Instantly   Purple    #9B59B6   < 1 second        < 8 characters
  Weak        Red       #E74C3C   Minutes–hours     8 chars, numbers/lowercase only
  Good        Orange    #E67E22   Days–weeks        Mixed types, short length
  Great       Yellow    #F1C40F   Months–years      12+ chars with ≥ 3 char types
  Safe        Green     #2ECC71   Centuries+        16+ any, or 12+ with all 4 types

"Character types" means: lowercase letters, uppercase letters, digits, symbols.

``PasswordStrength.assess(password)`` returns ``(tier_label, hex_colour)``.
``PasswordStrength.meter_text(password)`` returns a human-readable string.


=============================================================================

PASSWORD CHANGE  (Key Re-Encryption)
--------------------------------------

When the master password is changed, ``api_config.change_password()`` does
the following atomically:

  1. Verify the old password (100 ms trap applies).
  2. Decrypt all stored API keys using the old PBKDF2-derived key.
  3. Generate a new random 32-byte key_salt.
  4. Derive a new encryption key from the new password + new salt.
  5. Re-encrypt all API keys with the new key.
  6. Hash the new password with bcrypt.
  7. Write everything to user/API.ini in one write operation.

If any step fails an exception is raised and the file is NOT modified.


=============================================================================

SECURITY SUMMARY
-----------------

  What is protected?       API keys (OpenAI, Gemini, local endpoint tokens)

  What is NOT protected?   Non-secret settings: model name, temperature,
                           timeout, rate limits, provider presets.  Those
                           stay in plain INI sections.

  What if I forget my password?
    There is no recovery mechanism.  You will need to re-enter your API keys.
    Delete user/API.ini and CherryAI will start fresh.

  Is the hash reversible?
    No.  bcrypt is a one-way function.  CherryAI cannot show you your password.

  Is user/API.ini safe to back up?
    Yes, as long as you use a strong password (Green / Safe tier).  The file
    is useless without the master password.

  Is user/CherryAI.ini sensitive?
    No.  It contains no secrets.  The API section there only holds non-secret
    settings.  The comment "see user/API.ini" points to the encrypted store.


=============================================================================

IMPLEMENTATION REFERENCE
--------------------------

  functions/api_config.py
    set_password(password)            Hash + store new master password
    verify_password(password)         Verify + 100 ms trap
    is_password_set()                 True if [security] hash exists
    set_api_key(provider, key, pw)    Encrypt + store an API key
    get_api_key(provider, pw)         Verify + decrypt an API key
    change_password(old_pw, new_pw)   Re-encrypt all keys
    PasswordStrength.assess(pw)       (tier, colour) tuple
    PasswordStrength.meter_text(pw)   Human-readable strength string

  gui/widgets/password_strength.py
    PasswordStrengthWidget            Tkinter Entry + real-time strength bar

  gui/dialogs/password_dialog.py
    SetPasswordDialog                 First-time password creation modal
    ChangePasswordDialog              Authenticated password change modal
    VerifyPasswordDialog              Single-entry unlock modal


=============================================================================

DEPENDENCIES
------------

  Package        Version   Purpose
  -----------    -------   ---------------------------------------------------
  bcrypt         ≥ 4.0     Password hashing (WF-10)
  cryptography   ≥ 41.0    Fernet AES encryption + PBKDF2 key derivation

Both are listed in requirements.txt.


=============================================================================

REFERENCES
----------

  HiveSystems 2025 Password Table
    https://www.hivesystems.com/blog/are-your-passwords-in-the-green

  OWASP Password Storage Cheat Sheet
    https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

  NIST SP 800-132 (PBKDF2 iterations)
    https://csrc.nist.gov/publications/detail/sp/800-132/final

  Fernet specification (cryptography library)
    https://cryptography.io/en/latest/fernet/
