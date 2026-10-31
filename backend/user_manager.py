"""
Minimal user manager — stores users in a JSON file under data/.
No external auth dependency required.
"""

import os, json, hashlib, uuid
from typing import Optional, Dict, Any

_USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")


def _load() -> dict:
    os.makedirs(os.path.dirname(_USERS_FILE), exist_ok=True)
    if not os.path.exists(_USERS_FILE):
        return {}
    with open(_USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(db: dict) -> None:
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username: str, email: str, password: str, full_name: str = "") -> Dict[str, Any]:
    db = _load()
    for u in db.values():
        if u["username"] == username:
            raise ValueError(f"Username '{username}' is already taken.")
        if email and u.get("email") == email:
            raise ValueError(f"Email '{email}' is already registered.")
    uid = str(uuid.uuid4())
    user = {"id": uid, "username": username, "email": email,
            "full_name": full_name, "password_hash": _hash(password)}
    db[uid] = user
    _save(db)
    return {k: v for k, v in user.items() if k != "password_hash"}


def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    db = _load()
    for u in db.values():
        if u["username"] == username_or_email or u.get("email") == username_or_email:
            if u["password_hash"] == _hash(password):
                return {k: v for k, v in u.items() if k != "password_hash"}
    return None


def get_user_by_id(uid: str) -> Optional[Dict[str, Any]]:
    db = _load()
    u = db.get(uid)
    if u:
        return {k: v for k, v in u.items() if k != "password_hash"}
    return None
