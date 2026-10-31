"""
core/encryption.py
==================
Thin re-export so both `from core.encryption import ...` and
`from backend.security import ...` work throughout the codebase.

The real implementation lives in backend/security.py (PBKDF2HMAC, AES-256 Fernet).
"""

import sys, os
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.security import (   # noqa: F401  (re-export)
    SecurityManager,
    derive_fernet_key,
    security_manager,
)

__all__ = ["SecurityManager", "derive_fernet_key", "security_manager"]
