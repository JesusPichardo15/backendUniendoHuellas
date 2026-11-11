from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from auth import require_admin

router = APIRouter(prefix="/api/roles", tags=["Roles (Tabla Separada)"])


@router.get("", response_model=List[schemas.RolResponse], summary="Listar todos los roles")
def get_all_roles(db: Session = Depends(get_db)):
    """Obtiene la lista completa de roles del sistema."""
    return db.query(models.Rol).order_by(models.Rol.id_rol.asc()).all()


@router.get("/{id_rol}", response_model=schemas.RolResponse, summary="Obtener un rol por ID")
def get_role_by_id(id_rol: int, db: Session = Depends(get_db)):
    """Obtiene el detalle de un rol específico por su id_rol."""
    rol = db.query(models.Rol).filter(models.Rol.id_rol == id_rol).first()
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    return rol


@router.post("", response_model=schemas.RolResponse, status_code=status.HTTP_201_CREATED, summary="Crear un nuevo rol (Admin)")
def create_role(
    data: schemas.RolCreate,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Crea un nuevo rol en la base de datos (Requiere rol de Administrador)."""
    existente = db.query(models.Rol).filter(models.Rol.nombre_rol.ilike(data.nombre_rol.strip())).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un rol con ese nombre")

    nuevo_rol = models.Rol(nombre_rol=data.nombre_rol.strip())
    db.add(nuevo_rol)
    db.commit()
    db.refresh(nuevo_rol)
    return nuevo_rol


@router.put("/{id_rol}", response_model=schemas.RolResponse, summary="Actualizar un rol (Admin)")
def update_role(
    id_rol: int,
    data: schemas.RolUpdate,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Actualiza los datos de un rol existente (Requiere rol de Administrador)."""
    rol = db.query(models.Rol).filter(models.Rol.id_rol == id_rol).first()
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    if data.nombre_rol is not None:
        rol.nombre_rol = data.nombre_rol.strip()

    db.commit()
    db.refresh(rol)
    return rol


@router.delete("/{id_rol}", response_model=schemas.MensajeRespuesta, summary="Eliminar un rol (Admin)")
def delete_role(
    id_rol: int,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Elimina un rol si no tiene usuarios asociados (Requiere rol de Administrador)."""
    rol = db.query(models.Rol).filter(models.Rol.id_rol == id_rol).first()
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    usuarios_asociados = db.query(models.Usuario).filter(models.Usuario.id_rol == id_rol).count()
    if usuarios_asociados > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el rol porque tiene {usuarios_asociados} usuarios vinculados."
        )

    db.delete(rol)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Rol eliminado exitosamente", id=id_rol)
