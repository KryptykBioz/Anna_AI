# Filename: BASE/recall/memory_encryption.py
"""
Memory Encryption Layer for AI Agent Memory System
AES-256-GCM encryption with crash-safe atomic writes.

Protection model:
- Key derived from password via Argon2id (memory-hard, GPU-resistant)
- AES-256-GCM authenticated encryption (tamper-evident)
- Atomic writes via temp-file + os.replace() (POSIX and Windows safe)
- Backup-before-write (.bak) for one-deep rollback on corruption
- Pending-write recovery on startup for interrupted flushes

File format (binary):
  [4 bytes magic] [1 byte version] [16 bytes salt] [12 bytes nonce]
  [N bytes ciphertext] [16 bytes GCM tag]

Magic: b'AMEM' (Anna Memory)
Version: 0x01
"""

import os
import struct
import secrets
import getpass
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# ============================================================================
# CONSTANTS
# ============================================================================

_MAGIC       = b'AMEM'
_VERSION     = b'\x01'
_SALT_LEN    = 16
_NONCE_LEN   = 12
_TAG_LEN     = 16
_HEADER_LEN  = len(_MAGIC) + len(_VERSION) + _SALT_LEN + _NONCE_LEN  # 33 bytes

# Scrypt parameters — tuned for ~100ms on modest hardware
# N=2^17 (131072), r=8, p=1 -> ~128MB RAM required
_SCRYPT_N = 131072
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN  = 32  # 256-bit AES key


# ============================================================================
# KEY DERIVATION
# ============================================================================

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from password + salt using Scrypt."""
    kdf = Scrypt(
        salt=salt,
        length=_KEY_LEN,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return kdf.derive(password.encode('utf-8'))


# ============================================================================
# ENCRYPT / DECRYPT
# ============================================================================

def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    """
    Encrypt plaintext with AES-256-GCM.
    A fresh random nonce is generated per call.

    Returns packed binary: magic + version + salt_placeholder + nonce + ciphertext+tag
    Note: salt is stored externally in the key derivation header; nonce is per-write.
    """
    nonce = secrets.token_bytes(_NONCE_LEN)
    aesgcm = AESGCM(key)
    # ciphertext includes 16-byte GCM tag appended by cryptography library
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext_with_tag


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    """
    Decrypt blob produced by encrypt_bytes.
    Raises InvalidTag if key is wrong or data is tampered.
    """
    if len(blob) < _NONCE_LEN + _TAG_LEN + 1:
        raise ValueError("Blob too short to be valid ciphertext")
    nonce = blob[:_NONCE_LEN]
    ciphertext_with_tag = blob[_NONCE_LEN:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext_with_tag, None)


# ============================================================================
# FILE FORMAT: full file read/write with salt header
# ============================================================================

def _pack_file(salt: bytes, encrypted_blob: bytes) -> bytes:
    """Pack into on-disk file format: magic + version + salt + encrypted_blob."""
    return _MAGIC + _VERSION + salt + encrypted_blob


def _unpack_file(data: bytes) -> tuple[bytes, bytes]:
    """
    Unpack on-disk file format.
    Returns (salt, encrypted_blob).
    Raises ValueError on format errors.
    """
    if len(data) < _HEADER_LEN + _TAG_LEN + 1:
        raise ValueError("File too short to be a valid encrypted memory file")
    if data[:4] != _MAGIC:
        raise ValueError(f"Invalid magic bytes: expected {_MAGIC!r}, got {data[:4]!r}")
    if data[4:5] != _VERSION:
        raise ValueError(f"Unsupported version: {data[4]:#x}")
    salt = data[5 : 5 + _SALT_LEN]
    encrypted_blob = data[5 + _SALT_LEN :]
    return salt, encrypted_blob


# ============================================================================
# ATOMIC WRITE HELPERS
# ============================================================================

def _atomic_write(path: Path, data: bytes) -> None:
    """
    Write data to path atomically:
    1. Write to path.tmp
    2. os.replace(tmp, path)  -- atomic on POSIX + Windows NTFS

    On crash between steps 1 and 2, path is untouched (old version preserved).
    The .tmp is an incomplete write and is cleaned up on next startup.
    """
    tmp = path.with_suffix(path.suffix + '.tmp')
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except Exception:
        # Clean up partial tmp if replace failed
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _backup_existing(path: Path) -> None:
    """
    Copy current file to path.bak before overwriting.
    If path doesn't exist yet, skip silently.
    On crash after backup but before new write, .bak is the safe fallback.
    """
    if path.exists():
        bak = path.with_suffix(path.suffix + '.bak')
        try:
            bak.write_bytes(path.read_bytes())
        except OSError:
            pass  # Non-fatal: proceed without backup


def _write_pending_marker(path: Path) -> None:
    """
    Write a .pending marker before beginning a write sequence.
    Presence of .pending at startup signals an interrupted write.
    Marker contains the target path for recovery.
    """
    marker = path.with_suffix(path.suffix + '.pending')
    try:
        marker.write_text(str(path), encoding='utf-8')
    except OSError:
        pass


def _clear_pending_marker(path: Path) -> None:
    """Remove the .pending marker after a successful write."""
    marker = path.with_suffix(path.suffix + '.pending')
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        pass


# ============================================================================
# HIGH-LEVEL ENCRYPTED FILE I/O
# ============================================================================

def save_encrypted(path: Path, plaintext: bytes, key: bytes) -> None:
    """
    Crash-safe encrypted file write sequence:
    1. Write .pending marker
    2. Backup existing file to .bak
    3. Encrypt plaintext
    4. Atomic write to .tmp then os.replace to target
    5. Clear .pending marker

    A crash at any point leaves the original file intact (or recoverable from .bak).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Signal intent
    _write_pending_marker(path)

    # Step 2: Backup current file (one-deep rollback)
    _backup_existing(path)

    # Step 3: Derive a fresh salt per write, encrypt
    salt = secrets.token_bytes(_SALT_LEN)
    encrypted_blob = encrypt_bytes(plaintext, key)
    file_data = _pack_file(salt, encrypted_blob)

    # Step 4: Atomic write
    _atomic_write(path, file_data)

    # Step 5: Clear intent marker
    _clear_pending_marker(path)


def load_encrypted(path: Path, key: bytes) -> Optional[bytes]:
    """
    Load and decrypt an encrypted memory file.

    Returns plaintext bytes, or None if file does not exist.
    Raises InvalidTag if the key is wrong or the file has been tampered with.
    Raises ValueError on format errors.
    """
    if not path.exists():
        return None

    file_data = path.read_bytes()
    salt, encrypted_blob = _unpack_file(file_data)
    # salt is stored in file for format completeness; key is pre-derived and passed in
    return decrypt_bytes(encrypted_blob, key)


def load_encrypted_with_fallback(path: Path, key: bytes) -> Optional[bytes]:
    """
    Load encrypted file with automatic .bak fallback on corruption.

    Tries main file first; if InvalidTag or ValueError, attempts .bak.
    Logs which source was used to stderr (no logger dependency here).
    Returns plaintext bytes, or None if neither file exists.
    """
    # Try primary
    try:
        result = load_encrypted(path, key)
        if result is not None:
            return result
    except (InvalidTag, ValueError, OSError) as e:
        print(f"[Encryption] Primary file corrupted ({path.name}): {e} — trying .bak")

    # Try backup
    bak = path.with_suffix(path.suffix + '.bak')
    if bak.exists():
        try:
            bak_data = bak.read_bytes()
            salt, encrypted_blob = _unpack_file(bak_data)
            plaintext = decrypt_bytes(encrypted_blob, key)
            print(f"[Encryption] Recovered from .bak: {bak.name}")
            # Restore .bak as the primary so next startup is clean
            _atomic_write(path, bak_data)
            return plaintext
        except (InvalidTag, ValueError, OSError) as e:
            print(f"[Encryption] Backup also corrupted ({bak.name}): {e}")

    return None


# ============================================================================
# STARTUP RECOVERY: clean up interrupted writes
# ============================================================================

def recover_pending_writes(memory_dir: Path) -> None:
    """
    Called once at startup before any file operations.
    Scans memory_dir for .pending markers and resolves interrupted writes:

    - If .tmp exists alongside a .pending: the write was interrupted before
      os.replace. The .tmp is incomplete — remove it. The original file is safe.
    - If .bak exists and primary is missing: restore from .bak.
    - Clear .pending marker after resolution.

    This ensures startup always finds a consistent state.
    """
    if not memory_dir.exists():
        return

    for marker in memory_dir.glob('*.pending'):
        target_str = marker.read_text(encoding='utf-8').strip()
        target = Path(target_str)
        tmp = target.with_suffix(target.suffix + '.tmp')
        bak = target.with_suffix(target.suffix + '.bak')

        # Remove incomplete .tmp
        if tmp.exists():
            try:
                tmp.unlink()
                print(f"[Encryption] Cleaned up incomplete write: {tmp.name}")
            except OSError as e:
                print(f"[Encryption] Could not remove {tmp.name}: {e}")

        # Restore from .bak if primary is missing
        if not target.exists() and bak.exists():
            try:
                _atomic_write(target, bak.read_bytes())
                print(f"[Encryption] Restored {target.name} from backup")
            except OSError as e:
                print(f"[Encryption] Could not restore {target.name}: {e}")

        # Clear the pending marker
        _clear_pending_marker(target)


# ============================================================================
# SESSION KEY MANAGEMENT
# ============================================================================

class MemoryKeyManager:
    """
    Holds the derived encryption key for the session lifetime.
    Key lives only in process memory — never written to disk.

    Usage:
        km = MemoryKeyManager()
        km.unlock(password)          # Derives key from password
        key = km.key                 # Use for encrypt/decrypt
        km.lock()                    # Wipe key from memory
    """

    __slots__ = ('_key', '_unlocked')

    def __init__(self):
        self._key: Optional[bytes] = None
        self._unlocked: bool = False

    @property
    def key(self) -> bytes:
        if not self._unlocked or self._key is None:
            raise RuntimeError("MemoryKeyManager is locked. Call unlock() first.")
        return self._key

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    def unlock(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Derive and store key from password.
        If salt is None, generates a new random salt (first-time setup).
        Returns the salt so caller can persist it if needed.

        Salt is NOT secret and can be stored plaintext alongside encrypted files.
        """
        if salt is None:
            salt = secrets.token_bytes(_SALT_LEN)
        self._key = _derive_key(password, salt)
        self._unlocked = True
        return salt

    def unlock_from_keyfile(self, keyfile_path: Path) -> None:
        """
        Unlock using a persistent salt stored in a keyfile.
        The keyfile stores only the salt (hex-encoded), not the key or password.

        Keyfile format: single line, hex-encoded salt.
        """
        if not keyfile_path.exists():
            raise FileNotFoundError(f"Salt keyfile not found: {keyfile_path}")
        salt_hex = keyfile_path.read_text(encoding='utf-8').strip()
        salt = bytes.fromhex(salt_hex)
        password = getpass.getpass("[Memory System] Enter memory password: ")
        self.unlock(password, salt)

    def save_salt_keyfile(self, salt: bytes, keyfile_path: Path) -> None:
        """
        Persist salt to keyfile for subsequent startups.
        Only the salt is stored — the password is never persisted.
        """
        keyfile_path.parent.mkdir(parents=True, exist_ok=True)
        keyfile_path.write_text(salt.hex(), encoding='utf-8')

    def lock(self) -> None:
        """Zero-ish wipe and discard the key from memory."""
        if self._key is not None:
            # Overwrite the bytes object — best-effort in CPython
            self._key = b'\x00' * len(self._key)
            self._key = None
        self._unlocked = False


# ============================================================================
# CONVENIENCE: prompt-based setup for first run vs subsequent runs
# ============================================================================

def setup_or_unlock(memory_dir: Path) -> MemoryKeyManager:
    """
    Interactive setup for first run or subsequent unlocks.

    First run (no .salt file):
        - Prompts for new password + confirmation
        - Derives key, saves salt to memory_dir/.salt

    Subsequent runs (.salt file exists):
        - Prompts for password only
        - Derives key using stored salt

    Returns an unlocked MemoryKeyManager.
    Raises SystemExit on password mismatch or wrong password (after 3 attempts).
    """
    salt_file = memory_dir / '.salt'
    km = MemoryKeyManager()

    if not salt_file.exists():
        # First-time setup
        print("[Memory System] First-time encryption setup.")
        print("[Memory System] Choose a password to protect the agent's memory files.")
        print("[Memory System] WARNING: If this password is lost, memories cannot be recovered.")
        for _ in range(3):
            pw1 = getpass.getpass("[Memory System] New password: ")
            pw2 = getpass.getpass("[Memory System] Confirm password: ")
            if pw1 == pw2:
                salt = km.unlock(pw1)
                km.save_salt_keyfile(salt, salt_file)
                print("[Memory System] Memory encryption initialized.")
                return km
            print("[Memory System] Passwords do not match, try again.")
        print("[Memory System] Too many failed attempts.")
        raise SystemExit(1)
    else:
        # Unlock with existing salt
        salt_hex = salt_file.read_text(encoding='utf-8').strip()
        salt = bytes.fromhex(salt_hex)
        for attempt in range(3):
            pw = getpass.getpass("[Memory System] Memory password: ")
            try:
                km.unlock(pw, salt)
                # Verify key is correct by attempting to decrypt a known file if present
                _verify_key(memory_dir, km.key)
                print("[Memory System] Memory unlocked.")
                return km
            except (InvalidTag, ValueError):
                remaining = 2 - attempt
                if remaining > 0:
                    print(f"[Memory System] Incorrect password. {remaining} attempt(s) remaining.")
                else:
                    print("[Memory System] Too many failed attempts.")
                    raise SystemExit(1)
            finally:
                # Clear password string from local scope best-effort
                pw = '\x00' * len(pw)

    raise SystemExit(1)  # Should not reach here


def _verify_key(memory_dir: Path, key: bytes) -> None:
    """
    Verify the key is correct by attempting to decrypt the verification token.
    If no verification file exists yet, create one.
    Raises InvalidTag if key is wrong.
    """
    verify_file = memory_dir / '.keycheck'

    if not verify_file.exists():
        # Write a known plaintext as verification token
        token = b'AGENT_MEMORY_KEY_OK'
        save_encrypted(verify_file, token, key)
        return

    plaintext = load_encrypted(verify_file, key)
    if plaintext != b'AGENT_MEMORY_KEY_OK':
        raise InvalidTag()
    
# ============================================================================
# PASSWORD CHANGE
# ============================================================================

def change_password(memory_dir: Path) -> bool:
    """
    Change the memory encryption password in-place.
    Decrypts all memory files with the current password, then re-encrypts
    with a new password using the same crash-safe atomic write sequence.

    All-or-nothing: if any file fails to decrypt with the current password,
    the operation is aborted before any new writes occur.

    Args:
        memory_dir: Path to personality/memory/

    Returns:
        True if successful, False if aborted.
    """
    import getpass

    salt_file  = memory_dir / '.salt'
    check_file = memory_dir / '.keycheck'

    MEMORY_FILES = [
        memory_dir / 'short_memory.json',
        memory_dir / 'medium_memory.json',
        memory_dir / 'long_memory.json',
    ]

    if not salt_file.exists():
        print("[Password Change] No .salt file found — memory encryption has not been initialized.")
        return False

    # ----------------------------------------------------------------
    # Step 1: Verify current password and decrypt all files into memory
    # ----------------------------------------------------------------
    old_salt = bytes.fromhex(salt_file.read_text(encoding='utf-8').strip())

    for attempt in range(3):
        old_password = getpass.getpass("[Password Change] Current password: ")
        old_key = _derive_key(old_password, old_salt)
        try:
            _verify_key(memory_dir, old_key)
            break
        except Exception:
            remaining = 2 - attempt
            if remaining > 0:
                print(f"[Password Change] Incorrect password. {remaining} attempt(s) remaining.")
            else:
                print("[Password Change] Too many failed attempts. Aborting.")
                return False
        finally:
            old_password = '\x00' * len(old_password)
    else:
        return False

    # Decrypt all existing files before touching anything
    decrypted: dict[Path, bytes | None] = {}
    for path in MEMORY_FILES:
        if not path.exists():
            decrypted[path] = None
            continue
        try:
            plaintext = load_encrypted_with_fallback(path, old_key)
            decrypted[path] = plaintext
        except Exception as e:
            print(f"[Password Change] Failed to decrypt {path.name}: {e}")
            print("[Password Change] Aborting — no files have been modified.")
            return False

    # ----------------------------------------------------------------
    # Step 2: Collect and confirm new password
    # ----------------------------------------------------------------
    print("[Password Change] Enter your new password.")
    for attempt in range(3):
        new_password  = getpass.getpass("[Password Change] New password: ")
        new_password2 = getpass.getpass("[Password Change] Confirm new password: ")
        if new_password == new_password2:
            break
        remaining = 2 - attempt
        if remaining > 0:
            print(f"[Password Change] Passwords do not match. {remaining} attempt(s) remaining.")
        else:
            print("[Password Change] Too many mismatches. Aborting.")
            return False
    else:
        return False

    # Derive new key with a fresh salt
    new_salt = secrets.token_bytes(_SALT_LEN)
    new_key  = _derive_key(new_password, new_salt)
    new_password  = '\x00' * len(new_password)
    new_password2 = '\x00' * len(new_password2)

    # ----------------------------------------------------------------
    # Step 3: Write new .salt and .keycheck
    # ----------------------------------------------------------------
    try:
        salt_file.write_text(new_salt.hex(), encoding='utf-8')
        # Overwrite .keycheck with token encrypted under new key
        check_file.unlink(missing_ok=True)
        save_encrypted(check_file, b'AGENT_MEMORY_KEY_OK', new_key)
    except Exception as e:
        print(f"[Password Change] Failed to write new salt/keycheck: {e}")
        print("[Password Change] Restoring old salt — memory files are unchanged.")
        salt_file.write_text(old_salt.hex(), encoding='utf-8')
        return False

    # ----------------------------------------------------------------
    # Step 4: Re-encrypt all memory files with the new key
    # ----------------------------------------------------------------
    failed: list[Path] = []
    for path, plaintext in decrypted.items():
        if plaintext is None:
            continue
        try:
            save_encrypted(path, plaintext, new_key)
        except Exception as e:
            print(f"[Password Change] Failed to re-encrypt {path.name}: {e}")
            failed.append(path)

    if failed:
        print("[Password Change] WARNING: The following files could not be re-encrypted:")
        for f in failed:
            print(f"  {f.name}")
        print("[Password Change] Their .bak copies are still encrypted with the OLD key.")
        print("[Password Change] Restore them from .bak and re-run with the old password to recover.")
        return False

    # ----------------------------------------------------------------
    # Step 5: Remove .bak files (they hold old-key ciphertext)
    # ----------------------------------------------------------------
    for path in MEMORY_FILES:
        bak = path.with_suffix(path.suffix + '.bak')
        try:
            bak.unlink(missing_ok=True)
        except OSError:
            pass

    print("[Password Change] Password changed successfully.")
    return True