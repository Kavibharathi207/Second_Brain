"""
Encryption layer — Second Brain
AES-256 via Fernet; key derived from passphrase using PBKDF2HMAC (SHA-256).
Salt is stored in a local file (never hardcoded).  All memory content is
encrypted before it touches SQLite or ChromaDB metadata.
"""

import os
import json
import base64
from typing import Dict, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from .config import config


def _load_or_create_salt() -> bytes:
    """Load the persistent salt from disk, creating it on first run."""
    salt_path = config.SALT_FILE
    os.makedirs(os.path.dirname(salt_path) if os.path.dirname(salt_path) else ".", exist_ok=True)
    if os.path.exists(salt_path):
        with open(salt_path, "rb") as f:
            return f.read()
    salt = os.urandom(16)
    with open(salt_path, "wb") as f:
        f.write(salt)
    return salt


def derive_fernet_key(passphrase: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from *passphrase* using PBKDF2."""
    salt = _load_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=config.PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    raw = kdf.derive(passphrase.encode())
    return base64.urlsafe_b64encode(raw)


class SecurityManager:
    """Handles encryption/decryption and passphrase verification."""

    def __init__(self, passphrase: str = None):
        self._passphrase = passphrase or config.ENCRYPTION_KEY
        self.cipher = self._build_cipher(self._passphrase)

    def _build_cipher(self, passphrase: str) -> Fernet:
        return Fernet(derive_fernet_key(passphrase))

    # ── Public API ────────────────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a UTF-8 string → raw bytes (stored in SQLite BLOB)."""
        return self.cipher.encrypt(plaintext.encode())

    def decrypt(self, token: bytes) -> str:
        """Decrypt raw bytes → UTF-8 string."""
        return self.cipher.decrypt(token).decode()

    # Convenience wrappers used by legacy code / ChromaDB layer
    def encrypt_text(self, text: str) -> str:
        return base64.urlsafe_b64encode(self.encrypt(text)).decode()

    def decrypt_text(self, encoded: str) -> str:
        return self.decrypt(base64.urlsafe_b64decode(encoded.encode()))

    def encrypt_data(self, data: Dict[str, Any]) -> str:
        return self.encrypt_text(json.dumps(data))

    def decrypt_data(self, encoded: str) -> Dict[str, Any]:
        return json.loads(self.decrypt_text(encoded))

    def verify_secret_code(self, provided: str) -> bool:
        return provided == config.SECRET_CODE

    def set_secret_code(self, new_code: str) -> bool:
        code = (new_code or "").strip()
        if not code:
            return False
        config.SECRET_CODE = code
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        try:
            if os.path.exists(env_path):
                lines = []
                updated = False
                with open(env_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        if line.startswith("SECRET_CODE="):
                            lines.append(f"SECRET_CODE={code}\n")
                            updated = True
                        else:
                            lines.append(line)
                if not updated:
                    lines.append(f"SECRET_CODE={code}\n")
                with open(env_path, "w", encoding="utf-8") as handle:
                    handle.write("".join(lines))
            else:
                with open(env_path, "w", encoding="utf-8") as handle:
                    handle.write(f"SECRET_CODE={code}\n")
        except Exception:
            return False
        return True

    def generate_encryption_key(self) -> str:
        return Fernet.generate_key().decode()

    def rekey(self, new_passphrase: str) -> None:
        """Switch to a new passphrase (updates in-memory cipher only)."""
        self.cipher = self._build_cipher(new_passphrase)
        self._passphrase = new_passphrase


# Global instance — uses ENCRYPTION_KEY from .env as the default passphrase
security_manager = SecurityManager()
