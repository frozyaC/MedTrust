"""Local account management: python -m scripts.manage_users --help."""
import argparse
from getpass import getpass

import psycopg

from app.core.auth import hash_password, normalize_login
from app.db.auth import AuthRepository
from app.db.database import init_db


def read_password() -> str:
    password = getpass("Пароль: ")
    if password != getpass("Повторите пароль: "):
        raise ValueError("Пароли не совпадают")
    return hash_password(password)


def main() -> None:
    parser = argparse.ArgumentParser(description="Управление локальными пользователями MedTrust")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Создать учётную запись")
    create.add_argument("login")
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=("registrar", "kb_owner"), default="registrar")
    for command in ("set-password", "set-role", "block", "unblock"):
        subparser = commands.add_parser(command)
        subparser.add_argument("login")
        if command == "set-role":
            subparser.add_argument("role", choices=("registrar", "kb_owner"))
    args = parser.parse_args()
    try:
        login = normalize_login(args.login)
        name = args.name.strip() if args.command == "create" else None
        if name is not None and not 1 <= len(name) <= 200:
            raise ValueError("Имя должно содержать от 1 до 200 символов")
        password_hash = read_password() if args.command in {"create", "set-password"} else None
        init_db()
        repo = AuthRepository()
        if args.command == "create":
            repo.create_user(login, name, password_hash, args.role)
        else:
            changes = {
                "set-password": {"password_hash": password_hash},
                "set-role": {"role": getattr(args, "role", None)},
                "block": {"is_active": False}, "unblock": {"is_active": True},
            }[args.command]
            if not repo.update_user(login, **changes):
                raise ValueError("Пользователь не найден")
    except psycopg.errors.UniqueViolation:
        parser.exit(1, "Пользователь с таким логином уже существует\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Готово: {args.command} {login}")


if __name__ == "__main__":
    main()
