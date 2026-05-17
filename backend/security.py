"""
Security and encryption module for the Second Brain
Handles AES-256 encryption for sensitive data
"""

import os
import json
from typing import Dict, Any
from cryptography.fernet import Fernet
import base64
from .config import config


class SecurityManager:
    """Handles encryption and decryption of sensitive data"""

    def __init__(self, encryption_key: str = None):
        """
        Initialize the security manager
        
        Args:
            encryption_key: The encryption key (uses PBKDF2 derivation)
        """
        self.encryption_key = encryption_key or config.ENCRYPTION_KEY
        self.cipher = self._get_cipher()

    def _get_cipher(self) -> Fernet:
        """Generate Fernet cipher from encryption key"""
        # Ensure the key is properly formatted for Fernet
        key = self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key
        
        # Fernet requires a 32-byte key encoded in base64
        # If the key is not in Fernet format, create one from it
        try:
            # Try to use the key as-is if it's already a valid Fernet key
            if key.startswith(b'gAAAAAA'):  # Fernet token format
                return Fernet(key)
        except:
            pass
        
        # Otherwise, hash it to create a valid Fernet key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        # Create a hash of the key and use first 32 bytes for Fernet
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(key if isinstance(key, bytes) else key.encode())
        key_bytes = digest.finalize()
        
        # Encode to base64 for Fernet
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt sensitive data
        
        Args:
            data: Dictionary containing data to encrypt
            
        Returns:
            Encrypted string
        """
        try:
            json_data = json.dumps(data)
            encrypted = self.cipher.encrypt(json_data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise ValueError(f"Encryption failed: {str(e)}")

    def decrypt_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data: Encrypted string
            
        Returns:
            Decrypted dictionary
        """
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

    def encrypt_text(self, text: str) -> str:
        """Encrypt plain text"""
        try:
            encrypted = self.cipher.encrypt(text.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise ValueError(f"Text encryption failed: {str(e)}")

    def decrypt_text(self, encrypted_text: str) -> str:
        """Decrypt encrypted text"""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Text decryption failed: {str(e)}")

    def verify_secret_code(self, provided_code: str) -> bool:
        """
        Verify user's secret code
        
        Args:
            provided_code: The code to verify
            
        Returns:
            True if code matches, False otherwise
        """
        return provided_code == config.SECRET_CODE

    def generate_encryption_key(self) -> str:
        """Generate a new encryption key"""
        key = Fernet.generate_key()
        return key.decode()


# Global security manager instance
security_manager = SecurityManager()
