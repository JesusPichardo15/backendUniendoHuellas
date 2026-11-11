from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from database import get_db
import models
import schemas
from auth import get_current_user, require_admin

router = APIRouter(prefix="/api/favoritos", tags=["Favoritos (Separados y Relacionales)"])


# =====================================================================
# 1. CONSULTAS DE TABLA SEPARADA (CRUD DE FAVORITOS)
# =====================================================================

@router.get("", response_model=List[schemas.FavoritoResponse], summary="Listar favoritos (Tabla Separada)")
def get_favoritos(
    id_usuario: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    id_animal: Optional[int] = Query(None, description="Filtrar por ID de animal"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Obtiene registros de la tabla separada `Favoritos`.
    Si el usuario es adoptante, solo puede consultar sus propios registros.
    """
    query = db.query(models.Favorito)
    if current_user.id_rol == 3:  # Adoptante
        query = query.filter(models.Favorito.id_usuario == current_user.id_usuario)
    else:
        if id_usuario:
            query = query.filter(models.Favorito.id_usuario == id_usuario)

    if id_animal:
        query = query.filter(models.Favorito.id_animal == id_animal)

    return query.order_by(models.Favorito.id_favorito.desc()).all()


@router.post("", response_model=schemas.FavoritoResponse, status_code=status.HTTP_201_CREATED, summary="Guardar animal en favoritos")
def add_favorito(
    data: schemas.FavoritoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Agrega una mascota a la lista de favoritos del usuario autenticado.
    Verifica que la mascota exista y que no esté ya agregada previamente.
    """
    # Verificar existencia del animal
    animal = db.query(models.Animal).filter(models.Animal.id_animal == data.id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El animal especificado no existe.")

    # Verificar si ya está en favoritos
    existente = db.query(models.Favorito).filter(
        models.Favorito.id_usuario == current_user.id_usuario,
        models.Favorito.id_animal == data.id_animal
    ).first()
    if existente:
        return existente

    nuevo_favorito = models.Favorito(
        id_usuario=current_user.id_usuario,
        id_animal=data.id_animal
    )
    db.add(nuevo_favorito)
    db.commit()
    db.refresh(nuevo_favorito)
    return nuevo_favorito


@router.delete("/{id_favorito}", response_model=schemas.MensajeRespuesta, summary="Quitar de favoritos por ID de favorito")
def remove_favorito_by_id(
    id_favorito: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Elimina un favorito mediante su id_favorito."""
    fav = db.query(models.Favorito).filter(models.Favorito.id_favorito == id_favorito).first()
    if not fav:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorito no encontrado")

    if current_user.id_rol != 1 and fav.id_usuario != current_user.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes eliminar el favorito de otro usuario.")

    db.delete(fav)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Eliminado de favoritos", id=id_favorito)


@router.delete("/animal/{id_animal}", response_model=schemas.MensajeRespuesta, summary="Quitar de favoritos por ID de animal (Toggle corazón)")
def remove_favorito_by_animal(
    id_animal: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Permite quitar fácilmente un animal de favoritos al hacer clic en el botón de corazón de la UI."""
    fav = db.query(models.Favorito).filter(
        models.Favorito.id_usuario == current_user.id_usuario,
        models.Favorito.id_animal == id_animal
    ).first()
    if not fav:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El animal no está en tu lista de favoritos.")

    id_eliminado = fav.id_favorito
    db.delete(fav)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Mascota removida de favoritos", id=id_eliminado)


@router.get("/verificar/{id_animal}", summary="Verificar si un animal está en favoritos")
def check_es_favorito(
    id_animal: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Retorna `{\"es_favorito\": true/false}` para el animal y el usuario logueado."""
    fav = db.query(models.Favorito).filter(
        models.Favorito.id_usuario == current_user.id_usuario,
        models.Favorito.id_animal == id_animal
    ).first()
    return {"id_animal": id_animal, "es_favorito": fav is not None}


# =====================================================================
# 2. CONSULTAS DE TABLAS JUNTAS (JOINS / RELACIONALES)
# =====================================================================

@router.get("/relacion/mis-favoritos", response_model=List[schemas.FavoritoDetalladoResponse], summary="Mis favoritos con Animal y Refugio (JOIN Favoritos + Animales + Refugios)")
def get_mis_favoritos_detallados(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Retorna la lista de favoritos del usuario conectado, uniendo:
    - ID del favorito
    - Información completa del animal (nombre, especie, raza, foto, edad, etc.)
    - Información del refugio donde se encuentra la mascota
    """
    favoritos = db.query(models.Favorito).options(
        joinedload(models.Favorito.animal).joinedload(models.Animal.refugio)
    ).filter(models.Favorito.id_usuario == current_user.id_usuario).order_by(models.Favorito.id_favorito.desc()).all()

    resultado = []
    for f in favoritos:
        resultado.append(
            schemas.FavoritoDetalladoResponse(
                id_favorito=f.id_favorito,
                id_usuario=f.id_usuario,
                animal=schemas.AnimalConRefugioResponse.model_validate(f.animal)
            )
        )
    return resultado
