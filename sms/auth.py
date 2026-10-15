"""Authentication: password hashing, session tokens and role-based access control."""

import hashlib
import hmac
import os
import secrets
import time

PBKDF2_ROUNDS = 200_000
SESSION_TTL = 8 * 60 * 60

_sessions = {}


def new_salt():
    return secrets.token_hex(16)


def hash_password(password, salt=None):
    salt = salt or new_salt()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return digest.hex(), salt


def verify_password(password, stored_hash, salt):
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)


def create_session(user_id, role):
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"user_id": user_id, "role": role, "expires": time.time() + SESSION_TTL}
    return token


def get_session(token):
    if not token:
        return None
    entry = _sessions.get(token)
    if not entry:
        return None
    if entry["expires"] < time.time():
        _sessions.pop(token, None)
        return None
    return entry


def destroy_session(token):
    _sessions.pop(token, None)


ROLE_LEVELS = {"student": 1, "teacher": 2, "admin": 3}


def has_role(role, minimum):
    """True when `role` meets or exceeds the `minimum` role level."""
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(minimum, 99)


def login(conn, username, password):
    row = conn.execute(
        "SELECT id, username, password_hash, password_salt, role, is_active, full_name "
        "FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not row or not row["is_active"]:
        return None
    if not verify_password(password, row["password_hash"], row["password_salt"]):
        return None
    token = create_session(row["id"], row["role"])
    return {
        "token": token,
        "user_id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
    }


def audit(conn, user_id, action, detail=None):
    conn.execute("INSERT INTO audit_log (user_id, action, detail) VALUES (?,?,?)", (user_id, action, detail))
