"""Reset an existing reviewer password locally; never accepts passwords in arguments."""
import argparse
import getpass
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.security import hash_password
from backend.config import DB_PATH


def reset_password(database, username, password):
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        raise ValueError('Password must contain 12–200 characters.')
    database = Path(database).resolve()
    # Read/write mode refuses to create a new database if a path was mistyped.
    connection = sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)
    try:
        salt, digest = hash_password(password)
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            account = connection.execute('SELECT id FROM reviewer_accounts WHERE username=?',
                                         (username.strip().lower(),)).fetchone()
            if account is None:
                raise ValueError('Username not found. No account was created or changed.')
            connection.execute('UPDATE reviewer_accounts SET salt=?,password_hash=? WHERE id=?',
                               (salt, digest, account[0]))
            connection.execute('DELETE FROM reviewer_sessions WHERE account_id=?', (account[0],))
            connection.execute('INSERT INTO audit_logs(event_type,entity_id,reviewer,details_json) VALUES (?,?,?,?)',
                ('LOCAL_PASSWORD_RESET', str(account[0]), 'local-recovery', json.dumps({
                    'username': username.strip().lower(), 'os_user': getpass.getuser(),
                    'method': 'local terminal; existing account sessions revoked'})))
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username', help='Existing reviewer username')
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        parser.error('Run this command directly in an interactive terminal. Do not pipe a password.')
    print(f'Database: {DB_PATH}')
    print(f'Reset existing account: {args.username.strip().lower()}')
    print('Loan records are preserved. Existing sessions for this account will be revoked.')
    try:
        password = getpass.getpass('New password (12–200 characters; typing is hidden): ')
        confirmation = getpass.getpass('Repeat new password: ')
        if password != confirmation:
            raise ValueError('Passwords do not match. Nothing was changed.')
        reset_password(DB_PATH, args.username, password)
    except (ValueError, sqlite3.Error) as error:
        print(f'Reset failed: {error}', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled. Nothing was changed.', file=sys.stderr)
        return 1
    print('Password updated. Sign in using the new password.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
