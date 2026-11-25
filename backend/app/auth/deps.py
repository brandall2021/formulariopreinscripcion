from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from app.infra.config import get_settings

bearer = HTTPBearer(auto_error=False)


def get_current_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "autenticación requerida")
    try:
        return jwt.decode(creds.credentials, get_settings().secret_key, algorithms=["HS256"])
    except Exception as exc:
        raise HTTPException(401, "token inválido") from exc


def require_roles(*roles: str):
    def dep(claims: dict = Depends(get_current_claims)) -> dict:
        rol = claims.get("rol")
        # OTP session tokens have no rol; treat them as alumno.
        if rol is None:
            rol = "alumno"
        if roles and rol not in roles:
            raise HTTPException(403, "rol no autorizado")
        claims["rol"] = rol
        return claims
    return dep
