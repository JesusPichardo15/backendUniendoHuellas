from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación y Registro"])


@router.post("/register", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED, summary="Registro de Adoptante (Público)")
def register_user(data: schemas.UsuarioRegisterPublic, db: Session = Depends(get_db)):
    """
    Registra un nuevo usuario común (Adoptante).
    Asigna automáticamente el rol de Adoptante (id_rol=3).
    """
    existing_user = db.query(models.Usuario).filter(models.Usuario.correo == data.correo.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    # Buscar rol adoptante o id_rol=3
    rol_adoptante = db.query(models.Rol).filter(
        (models.Rol.nombre_rol.ilike("%adoptante%")) | (models.Rol.id_rol == 3)
    ).first()
    id_rol = rol_adoptante.id_rol if rol_adoptante else 3

    nuevo_usuario = models.Usuario(
        id_rol=id_rol,
        id_refugio=None,
        nombre_completo=data.nombre_completo.strip(),
        correo=data.correo.lower().strip(),
        password_hash=hash_password(data.password),
        telefono=data.telefono.strip()
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@router.post("/register-refugio", status_code=status.HTTP_201_CREATED, summary="Alta de Refugio con su Usuario Encargado")
def register_refugio_and_admin(data: schemas.RegistroRefugioYAdminRequest, db: Session = Depends(get_db)):
    """
    Permite a una casa de adopción registrarse en la plataforma:
    1. Da de alta la organización/refugio en la tabla `Refugios`.
    2. Crea simultáneamente la cuenta del usuario encargado con rol `Refugio / Encargado` (id_rol=2) vinculado a este nuevo refugio.
    """
    # Validar correo único
    if db.query(models.Usuario).filter(models.Usuario.correo == data.correo.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico del encargado ya está registrado."
        )

    # 1. Crear Refugio
    nuevo_refugio = models.Refugio(
        nombre_organizacion=data.nombre_organizacion.strip(),
        direccion=data.direccion.strip(),
        ciudad=data.ciudad.strip(),
        estado=data.estado.strip(),
        telefono=data.telefono_refugio.strip(),
        logo_url=data.logo_url,
        estado_cuenta="activo"
    )
    db.add(nuevo_refugio)
    db.flush()  # Obtener nuevo_refugio.id_refugio

    # 2. Buscar rol de refugio
    rol_refugio = db.query(models.Rol).filter(
        (models.Rol.nombre_rol.ilike("%refugio%")) | (models.Rol.id_rol == 2)
    ).first()
    id_rol = rol_refugio.id_rol if rol_refugio else 2

    # 3. Crear Usuario Encargado
    nuevo_encargado = models.Usuario(
        id_rol=id_rol,
        id_refugio=nuevo_refugio.id_refugio,
        nombre_completo=data.nombre_encargado.strip(),
        correo=data.correo.lower().strip(),
        password_hash=hash_password(data.password),
        telefono=data.telefono_encargado.strip()
    )
    db.add(nuevo_encargado)
    db.commit()
    db.refresh(nuevo_refugio)
    db.refresh(nuevo_encargado)

    # Crear token inmediato para inicio de sesión directo
    access_token = create_access_token(
        data={
            "sub": str(nuevo_encargado.id_usuario),
            "correo": nuevo_encargado.correo,
            "id_rol": nuevo_encargado.id_rol,
            "nombre_rol": rol_refugio.nombre_rol if rol_refugio else "Refugio",
            "id_refugio": nuevo_refugio.id_refugio
        }
    )

    return {
        "mensaje": "Refugio y usuario administrador dados de alta exitosamente",
        "refugio": schemas.RefugioResponse.model_validate(nuevo_refugio),
        "usuario": schemas.UsuarioResponse.model_validate(nuevo_encargado),
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=schemas.TokenResponse, summary="Iniciar Sesión")
def login(credentials: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    """
    Autentica al usuario mediante correo y contraseña.
    Retorna el Token JWT Bearer con expiración y el objeto de datos del usuario autenticado.
    """
    user = db.query(models.Usuario).filter(models.Usuario.correo == credentials.correo.lower()).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    nombre_rol = user.rol.nombre_rol if user.rol else f"Rol {user.id_rol}"

    token_data = {
        "sub": str(user.id_usuario),
        "correo": user.correo,
        "id_rol": user.id_rol,
        "nombre_rol": nombre_rol,
        "id_refugio": user.id_refugio,
        "nombre_completo": user.nombre_completo
    }

    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return schemas.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        usuario=schemas.UsuarioResponse.model_validate(user),
        rol_nombre=nombre_rol
    )


@router.get("/me", response_model=schemas.UsuarioConRolRefugioResponse, summary="Perfil del Usuario Autenticado")
def get_current_user_profile(current_user: models.Usuario = Depends(get_current_user)):
    """
    Retorna la información del usuario en sesión, su rol y los datos de su refugio (si es encargado).
    Requiere header `Authorization: Bearer <token>`.
    """
    return current_user
