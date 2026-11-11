import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Union
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import models

# Configuración JWT
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_nubira_weather_2026_adopciones")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Esquema de autenticación Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Genera hash seguro usando bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica contraseña compatible con bcrypt y con hashes SHA-256 de desarrollo/semillas"""
    if not hashed_password:
        return False

    # Compatibilidad con hash SHA-256 (64 caracteres hexadecimales)
    if len(hashed_password) == 64 and all(c in "0123456789abcdefABCDEF" for c in hashed_password):
        sha256_attempt = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        if sha256_attempt.lower() == hashed_password.lower():
            return True

    # Verificación estándar Bcrypt
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea token JWT firmado"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def get_token_from_request(
    token_oauth2: Optional[str] = Depends(oauth2_scheme),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Optional[str]:
    """Extrae el token ya sea desde OAuth2PasswordBearer o desde Header Authorization Bearer"""
    if bearer_creds and bearer_creds.credentials:
        return bearer_creds.credentials
    if token_oauth2:
        return token_oauth2
    return None


def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> models.Usuario:
    """Valida el JWT y obtiene el usuario autenticado actual"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario del token no existe en el sistema"
        )
    return user


def get_optional_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> Optional[models.Usuario]:
    """Obtiene el usuario actual si hay token válido, o None si es petición anónima"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            return None
        return db.query(models.Usuario).filter(models.Usuario.id_usuario == int(user_id_str)).first()
    except Exception:
        return None


def require_role(allowed_roles: List[Union[str, int]]):
    """
    Filtro de autorización basado en roles.
    Permite validar tanto por nombre ('Administrador', 'Refugio') como por id_rol (1, 2, 3).
    """
    def role_checker(current_user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
        user_role_id = current_user.id_rol
        user_role_name = current_user.rol.nombre_rol if current_user.rol else ""

        # Comprobar si coincide con id_rol o con el nombre del rol
        authorized = False
        for allowed in allowed_roles:
            if isinstance(allowed, int) and user_role_id == allowed:
                authorized = True
                break
            if isinstance(allowed, str):
                allowed_clean = allowed.strip().lower()
                user_role_clean = user_role_name.strip().lower()
                if allowed_clean in user_role_clean or user_role_clean in allowed_clean:
                    authorized = True
                    break

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado. Se requiere uno de los siguientes roles: {allowed_roles}. Tu rol actual es: {user_role_name or user_role_id}"
            )
        return current_user

    return role_checker


# Shortcuts para dependencias comunes
require_admin = require_role(["Administrador", 1])
require_refugio_or_admin = require_role(["Administrador", "Refugio / Encargado", "Refugio", 1, 2])
