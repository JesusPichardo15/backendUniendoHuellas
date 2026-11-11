from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from database import get_db
import models
import schemas
from auth import (
    get_current_user,
    require_admin,
    require_refugio_or_admin,
    hash_password
)

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios (Separados y Relacionales)"])


# =====================================================================
# 1. TABLA SEPARADA: CRUD DE USUARIOS
# =====================================================================

@router.get("", response_model=List[schemas.UsuarioResponse], summary="Listar usuarios (Tabla Separada con Filtros)")
def get_usuarios(
    id_rol: Optional[int] = Query(None, description="Filtrar por rol: 1=Admin, 2=Refugio, 3=Adoptante"),
    id_refugio: Optional[int] = Query(None, description="Filtrar por id_refugio asignado"),
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Obtiene la lista de usuarios del sistema (sin exponer el hash de contraseña).
    Permite filtrar por rol o refugio. Requiere rol de Refugio o Administrador.
    """
    query = db.query(models.Usuario)
    if id_rol:
        query = query.filter(models.Usuario.id_rol == id_rol)
    if id_refugio:
        query = query.filter(models.Usuario.id_refugio == id_refugio)

    return query.order_by(models.Usuario.id_usuario.asc()).all()


@router.get("/{id_usuario}", response_model=schemas.UsuarioResponse, summary="Obtener usuario por ID")
def get_usuario_by_id(
    id_usuario: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Obtiene los datos de un usuario por su ID (mismo usuario o admin)."""
    if current_user.id_rol != 1 and current_user.id_usuario != id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver los datos de otro usuario.")

    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.post("", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED, summary="Crear usuario manualmente (Admin)")
def create_usuario(
    data: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Permite al Administrador registrar usuarios de cualquier tipo."""
    if db.query(models.Usuario).filter(models.Usuario.correo == data.correo.lower()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El correo ya se encuentra registrado.")

    nuevo_usuario = models.Usuario(
        id_rol=data.id_rol,
        id_refugio=data.id_refugio,
        nombre_completo=data.nombre_completo.strip(),
        correo=data.correo.lower().strip(),
        password_hash=hash_password(data.password),
        telefono=data.telefono.strip()
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@router.put("/{id_usuario}", response_model=schemas.UsuarioResponse, summary="Actualizar datos de un usuario")
def update_usuario(
    id_usuario: int,
    data: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Actualiza la información de perfil de un usuario.
    Permitido para el propio usuario o para un Administrador.
    """
    if current_user.id_rol != 1 and current_user.id_usuario != id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para modificar este perfil.")

    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if data.nombre_completo is not None:
        usuario.nombre_completo = data.nombre_completo.strip()
    if data.telefono is not None:
        usuario.telefono = data.telefono.strip()
    if data.password:
        usuario.password_hash = hash_password(data.password)

    # Solo el Administrador puede reasignar el id_refugio
    if data.id_refugio is not None and current_user.id_rol == 1:
        usuario.id_refugio = data.id_refugio

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{id_usuario}", response_model=schemas.MensajeRespuesta, summary="Eliminar usuario (Admin)")
def delete_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Elimina la cuenta de un usuario (Requiere Administrador)."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    db.delete(usuario)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Usuario eliminado correctamente", id=id_usuario)


# =====================================================================
# 2. CONSULTAS DE TABLAS JUNTAS (JOINS / RELACIONALES)
# =====================================================================

@router.get("/relacion/detallados", response_model=List[schemas.UsuarioConRolRefugioResponse], summary="Listar usuarios con Rol y Refugio (JOIN Usuarios + Roles + Refugios)")
def get_usuarios_detallados(
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """
    Consulta relacional (JOIN):
    Obtiene la lista de usuarios con los objetos completos de su `Rol` y su `Refugio`.
    """
    usuarios = db.query(models.Usuario).options(
        joinedload(models.Usuario.rol),
        joinedload(models.Usuario.refugio)
    ).all()
    return usuarios


@router.get("/{id_usuario}/perfil-completo", response_model=schemas.UsuarioPerfilCompletoResponse, summary="Perfil completo de usuario con Solicitudes y Favoritos")
def get_perfil_completo(
    id_usuario: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Retorna el perfil enriquecido de un usuario:
    - Información personal
    - Su rol y refugio
    - Historial de solicitudes de adopción realizadas
    - Lista de animales guardados en favoritos con sus respectivos refugios
    """
    if current_user.id_rol != 1 and current_user.id_usuario != id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este perfil.")

    usuario = db.query(models.Usuario).options(
        joinedload(models.Usuario.rol),
        joinedload(models.Usuario.refugio),
        joinedload(models.Usuario.solicitudes),
        joinedload(models.Usuario.favoritos).joinedload(models.Favorito.animal).joinedload(models.Animal.refugio)
    ).filter(models.Usuario.id_usuario == id_usuario).first()

    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    # Formatear favoritos detallados
    favs_detallados = []
    for f in usuario.favoritos:
        favs_detallados.append(
            schemas.FavoritoDetalladoResponse(
                id_favorito=f.id_favorito,
                id_usuario=f.id_usuario,
                animal=schemas.AnimalConRefugioResponse.model_validate(f.animal)
            )
        )

    return schemas.UsuarioPerfilCompletoResponse(
        id_usuario=usuario.id_usuario,
        id_rol=usuario.id_rol,
        id_refugio=usuario.id_refugio,
        nombre_completo=usuario.nombre_completo,
        correo=usuario.correo,
        telefono=usuario.telefono,
        rol=schemas.RolResponse.model_validate(usuario.rol) if usuario.rol else None,
        refugio=schemas.RefugioResponse.model_validate(usuario.refugio) if usuario.refugio else None,
        solicitudes=[schemas.SolicitudResponse.model_validate(s) for s in usuario.solicitudes],
        favoritos=favs_detallados
    )
