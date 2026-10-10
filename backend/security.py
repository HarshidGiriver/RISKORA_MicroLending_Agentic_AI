"""Local reviewer accounts and revocable sessions, adapted from OraAgent's login design.

Sessions are opaque random tokens; only their hashes are stored. No default password
or signing secret is shipped. The first account is created from loopback setup.
"""
import hashlib
import hmac
import secrets
import time
from backend.database import get_connection


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(32)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt, digest


def create_account(username, password, role='REVIEWER'):
    if not isinstance(username, str) or not 3 <= len(username.strip()) <= 80:
        raise ValueError('Username must have 3–80 characters.')
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        raise ValueError('Password must have 12–200 characters.')
    if not isinstance(role, str) or role not in {'ADMIN', 'REVIEWER', 'VIEWER'}:
        raise ValueError('Unknown role.')
    salt, digest = hash_password(password)
    with get_connection() as conn:
        conn.execute('INSERT INTO reviewer_accounts(username,salt,password_hash,role) VALUES (?,?,?,?)',
                     (username.strip().lower(), salt, digest, role))


def new_session(account_id):
    token = secrets.token_urlsafe(32)
    with get_connection() as conn:
        conn.execute('DELETE FROM reviewer_sessions WHERE expires_at <= ?', (time.time(),))
        conn.execute('INSERT INTO reviewer_sessions VALUES (?,?,?)',
                     (hashlib.sha256(token.encode()).hexdigest(), account_id, time.time()+28800))
    return token


def session_user(token):
    if not token:
        return None
    with get_connection() as conn:
        row = conn.execute('''SELECT a.id,a.username,a.role FROM reviewer_accounts a
            JOIN reviewer_sessions s ON a.id=s.account_id
            WHERE s.token_hash=? AND s.expires_at>?''',
            (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return dict(row) if row else None


def authenticate(username, password):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM reviewer_accounts WHERE username=?', (username.strip().lower(),)).fetchone()
    salt = row['salt'] if row else '00'*32
    _, digest = hash_password(password, salt)
    return dict(row) if row and hmac.compare_digest(row['password_hash'], digest) else None
