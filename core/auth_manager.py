# core/auth_manager.py
import os
import json
import base64
import hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from pathlib import Path

AUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "auth.json"

def is_password_set():
    return AUTH_PATH.exists()

def _load_auth_data():
    if not AUTH_PATH.exists():
        return None
    with open(AUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_auth_data(salt: bytes, hash_pw: bytes):
    AUTH_PATH.parent.mkdir(exist_ok=True)
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "salt": base64.b64encode(salt).decode(),
            "hash": base64.b64encode(hash_pw).decode()
        }, f)

def _derive_key(password: str, salt: bytes, length: int = 32) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=150_000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def criar_hash_senha(password: str):
    salt = os.urandom(16)
    hash_pw = _derive_key(password, salt)
    _save_auth_data(salt, hash_pw)

def verificar_senha(password: str) -> bool:
    data = _load_auth_data()
    if not data:
        return False
    try:
        salt = base64.b64decode(data["salt"])
        expected_hash = base64.b64decode(data["hash"])
        test_hash = _derive_key(password, salt)
        return hmac.compare_digest(expected_hash, test_hash)
    except Exception:
        return False

def get_fernet_key(password: str) -> bytes:
    data = _load_auth_data()
    if not data:
        raise ValueError("Senha não configurada.")
    salt = base64.b64decode(data["salt"])
    key = _derive_key(password, salt)
    return base64.urlsafe_b64encode(key)
