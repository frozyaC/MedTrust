"""Local identities and revocable, opaque sessions. No plaintext session tokens persist."""
from datetime import datetime, timezone
from uuid import uuid4

from app.db.database import get_connection


class AuthRepository:
    def find_user(self, login: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, login, name, role, is_active, password_hash FROM auth_users WHERE login=%s",
                (login,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("id", "login", "name", "role", "is_active", "password_hash"), row))

    def create_user(self, login: str, name: str, password_hash: str, role: str) -> str:
        user_id = str(uuid4())
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO auth_users(id,login,name,password_hash,role) VALUES (%s,%s,%s,%s,%s)",
                (user_id, login, name, password_hash, role),
            )
            conn.commit()
        return user_id

    def create_session(self, token_hash: str, user_id: str, expires_at: datetime,
                       expected_password_hash: str) -> bool:
        # Serialize login with password changes/blocking. A stale password check
        # must not mint a session after a password reset has revoked sessions.
        with get_connection() as conn:
            row = conn.execute(
                "SELECT is_active, password_hash FROM auth_users WHERE id=%s FOR UPDATE", (user_id,),
            ).fetchone()
            if not row or not row[0] or row[1] != expected_password_hash:
                return False
            conn.execute(
                "DELETE FROM auth_sessions WHERE user_id=%s AND expires_at<=%s",
                (user_id, datetime.now(timezone.utc)),
            )
            conn.execute(
                "INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)",
                (token_hash, user_id, expires_at),
            )
            conn.commit()
        return True

    def session_user(self, token_hash: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT u.id, u.login, u.name, u.role
                   FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
                   WHERE s.token_hash=%s AND s.expires_at>%s AND u.is_active=TRUE""",
                (token_hash, datetime.now(timezone.utc)),
            ).fetchone()
        return dict(zip(("id", "login", "name", "role"), row)) if row else None

    def delete_session(self, token_hash: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash=%s", (token_hash,))
            conn.commit()

    def update_user(self, login: str, *, password_hash: str | None = None,
                    role: str | None = None, is_active: bool | None = None) -> bool:
        fields, values = [], []
        for column, value in (("password_hash", password_hash), ("role", role), ("is_active", is_active)):
            if value is not None:
                fields.append(f"{column}=%s")
                values.append(value)
        if not fields:
            return False
        with get_connection() as conn:
            row = conn.execute(
                f"UPDATE auth_users SET {', '.join(fields)} WHERE login=%s RETURNING id",
                (*values, login),
            ).fetchone()
            if not row:
                return False
            if password_hash is not None or is_active is False:
                conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (row[0],))
            conn.commit()
        return True
