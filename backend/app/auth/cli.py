"""Gestión de usuarios administrativos (admin/auditor) del sistema FACE.

Uso dentro del contenedor de la API:

    python -m app.auth.cli listar
    python -m app.auth.cli crear --email auditora@face.unt.edu.ar --rol auditor --password-stdin
    python -m app.auth.cli password --email auditora@face.unt.edu.ar --password-stdin
    python -m app.auth.cli desactivar --email admin@face.unt.edu.ar

La contraseña se lee de stdin para no dejarla en el historial ni en `ps`.
"""
import argparse
import getpass
import sys

from passlib.context import CryptContext

from app.auth.models import Usuario
from app.infra.db import SessionLocal

crypt = CryptContext(schemes=["bcrypt"])
ROLES = ("admin", "auditor")


def _leer_password(args) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Contraseña: ")
    if len(password) < 10:
        raise SystemExit("la contraseña debe tener al menos 10 caracteres")
    return password


def _normalizar(email: str) -> str:
    return email.strip().lower()


def cmd_listar(_args) -> None:
    with SessionLocal() as db:
        for u in db.query(Usuario).order_by(Usuario.id).all():
            estado = "activo" if u.activo else "inactivo"
            print(f"{u.id}\t{u.email}\t{u.rol}\t{estado}")


def cmd_crear(args) -> None:
    email = _normalizar(args.email)
    password = _leer_password(args)
    with SessionLocal() as db:
        user = db.query(Usuario).filter_by(email=email).first()
        if user is not None:
            raise SystemExit(f"el usuario {email} ya existe; usá 'password' o 'desactivar'")
        db.add(Usuario(email=email, password_hash=crypt.hash(password),
                       rol=args.rol, activo=True))
        db.commit()
        print(f"creado {email} rol={args.rol}")


def cmd_password(args) -> None:
    email = _normalizar(args.email)
    password = _leer_password(args)
    with SessionLocal() as db:
        user = db.query(Usuario).filter_by(email=email).first()
        if user is None:
            raise SystemExit(f"no existe el usuario {email}")
        user.password_hash = crypt.hash(password)
        user.activo = True
        db.commit()
        print(f"contraseña actualizada {email}")


def cmd_desactivar(args) -> None:
    email = _normalizar(args.email)
    with SessionLocal() as db:
        user = db.query(Usuario).filter_by(email=email).first()
        if user is None:
            raise SystemExit(f"no existe el usuario {email}")
        user.activo = False
        db.commit()
        print(f"desactivado {email}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.auth.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("listar", help="lista usuarios")

    crear = sub.add_parser("crear", help="crea un usuario admin/auditor")
    crear.add_argument("--email", required=True)
    crear.add_argument("--rol", choices=ROLES, required=True)
    crear.add_argument("--password-stdin", action="store_true")
    crear.set_defaults(func=cmd_crear)

    password = sub.add_parser("password", help="cambia la contraseña y reactiva")
    password.add_argument("--email", required=True)
    password.add_argument("--password-stdin", action="store_true")
    password.set_defaults(func=cmd_password)

    desactivar = sub.add_parser("desactivar", help="desactiva un usuario")
    desactivar.add_argument("--email", required=True)
    desactivar.set_defaults(func=cmd_desactivar)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
