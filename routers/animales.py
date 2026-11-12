from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from database import get_db
import models
import schemas
from auth import (
    get_current_user,
    get_optional_current_user,
    require_refugio_or_admin,
    require_admin
)

router = APIRouter(prefix="/api/animales", tags=["Animales (Separados y Relacionales)"])


# =====================================================================
# 1. CONSULTAS DE TABLA SEPARADA (CRUD DE ANIMALES)
# =====================================================================

@router.get("", response_model=List[schemas.AnimalResponse], summary="Listar animales (Tabla Separada con Filtros)")
def get_animales(
    especie: Optional[str] = Query(None, description="Filtrar por especie: Perro, Gato, etc."),
    raza: Optional[str] = Query(None, description="Filtrar por raza"),
    sexo: Optional[str] = Query(None, description="Filtrar por sexo: Macho, Hembra"),
    tamano: Optional[str] = Query(None, description="Filtrar por tamaño: Pequeño, Mediano, Grande"),
    estado_adopcion: Optional[str] = Query(None, description="Filtrar por estado: disponible, adoptado"),
    id_refugio: Optional[int] = Query(None, description="Filtrar por ID de refugio"),
    q: Optional[str] = Query(None, description="Buscar término en nombre, raza o descripción"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Obtiene la lista de animales de la tabla separada `Animales`.
    Permite filtrar por especie, raza, sexo, tamaño, estado de adopción y refugio.
    """
    query = db.query(models.Animal)

    if especie:
        query = query.filter(models.Animal.especie.ilike(f"%{especie.strip()}%"))
    if raza:
        query = query.filter(models.Animal.raza.ilike(f"%{raza.strip()}%"))
    if sexo:
        query = query.filter(models.Animal.sexo.ilike(f"%{sexo.strip()}%"))
    if tamano:
        query = query.filter(models.Animal.tamano.ilike(f"%{tamano.strip()}%"))
    if estado_adopcion:
        query = query.filter(models.Animal.estado_adopcion == estado_adopcion.strip())
    if id_refugio:
        query = query.filter(models.Animal.id_refugio == id_refugio)
    if q:
        termino = f"%{q.strip()}%"
        query = query.filter(
            (models.Animal.nombre.ilike(termino)) |
            (models.Animal.especie.ilike(termino)) |
            (models.Animal.raza.ilike(termino)) |
            (models.Animal.tamano.ilike(termino)) |
            (models.Animal.descripcion.ilike(termino))
        )

    return query.order_by(models.Animal.id_animal.desc()).offset(offset).limit(limit).all()


@router.get("/{id_animal}", response_model=schemas.AnimalResponse, summary="Obtener animal por ID (Tabla Separada)")
def get_animal_by_id(id_animal: int, db: Session = Depends(get_db)):
    """Obtiene los datos directos de un animal específico."""
    animal = db.query(models.Animal).filter(models.Animal.id_animal == id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal no encontrado")
    return animal


@router.post("", response_model=schemas.AnimalResponse, status_code=status.HTTP_201_CREATED, summary="Dar de alta una mascota (Refugio o Admin)")
def create_animal(
    data: schemas.AnimalCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Registra un nuevo animal para adopción.
    - Si el usuario es de rol Refugio, automáticamente se le asigna a su propio refugio.
    - Si es Admin, puede asignarlo a cualquier refugio existente.
    """
    # Si es encargado de refugio, asegurar que usa su propio refugio
    id_refugio = data.id_refugio
    if current_user.id_rol != 1:  # No es admin
        if not current_user.id_refugio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tu usuario de refugio no tiene un id_refugio asignado."
            )
        id_refugio = current_user.id_refugio

    # Verificar que el refugio existe
    refugio = db.query(models.Refugio).filter(models.Refugio.id_refugio == id_refugio).first()
    if not refugio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El refugio especificado no existe.")

    animal_dict = data.model_dump()
    animal_dict["id_refugio"] = id_refugio

    nuevo_animal = models.Animal(**animal_dict)
    db.add(nuevo_animal)
    db.commit()
    db.refresh(nuevo_animal)
    return nuevo_animal


@router.put("/{id_animal}", response_model=schemas.AnimalResponse, summary="Actualizar información de un animal")
def update_animal(
    id_animal: int,
    data: schemas.AnimalUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Actualiza los datos de una mascota (nombre, foto, estado, etc.).
    Solo permitido para el refugio que lo resguarda o el Administrador.
    """
    animal = db.query(models.Animal).filter(models.Animal.id_animal == id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal no encontrado")

    # Si es encargado de refugio, verificar que el animal pertenezca a su refugio
    if current_user.id_rol != 1 and animal.id_refugio != current_user.id_refugio:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar un animal perteneciente a otro refugio."
        )

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(animal, key, value)

    db.commit()
    db.refresh(animal)
    return animal


@router.delete("/{id_animal}", response_model=schemas.MensajeRespuesta, summary="Eliminar un animal")
def delete_animal(
    id_animal: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Elimina el registro de una mascota.
    Solo el Administrador o el refugio dueño del animal pueden eliminarlo.
    """
    animal = db.query(models.Animal).filter(models.Animal.id_animal == id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal no encontrado")

    if current_user.id_rol != 1 and animal.id_refugio != current_user.id_refugio:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes eliminar un animal de otro refugio."
        )

    db.delete(animal)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Animal eliminado exitosamente", id=id_animal)


# =====================================================================
# 2. CONSULTAS DE TABLAS JUNTAS (JOINS / RELACIONALES)
# =====================================================================

@router.get("/relacion/con-refugio", response_model=List[schemas.AnimalConRefugioResponse], summary="Listar animales con datos de su Refugio (JOIN Animales + Refugios)")
def get_animales_con_refugio(
    especie: Optional[str] = Query(None, description="Perro, Gato, etc."),
    estado_adopcion: str = Query("disponible", description="Por defecto 'disponible'"),
    ciudad: Optional[str] = Query(None, description="Filtrar por ciudad del refugio"),
    db: Session = Depends(get_db)
):
    """
    Consulta relacional (JOIN):
    Obtiene la información de los animales junto con el nombre, dirección, teléfono y ciudad del refugio.
    Ideal para mostrar las tarjetas del catálogo en el frontend.
    """
    query = db.query(models.Animal).join(models.Refugio).options(joinedload(models.Animal.refugio))

    if estado_adopcion and estado_adopcion.lower() != "todos":
        query = query.filter(models.Animal.estado_adopcion == estado_adopcion)
    if especie:
        query = query.filter(models.Animal.especie.ilike(f"%{especie.strip()}%"))
    if ciudad:
        query = query.filter(models.Refugio.ciudad.ilike(f"%{ciudad.strip()}%"))

    return query.order_by(models.Animal.id_animal.desc()).all()


@router.get("/{id_animal}/detalle-completo", response_model=schemas.AnimalDetalleCompletoResponse, summary="Detalle completo de un animal (JOIN Animal + Refugio + Favorito)")
def get_animal_detalle_completo(
    id_animal: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.Usuario] = Depends(get_optional_current_user)
):
    """
    Consulta detallada de una mascota para la vista individual:
    - Retorna datos del animal
    - Datos del refugio que lo resguarda
    - Indica si el usuario actual lo tiene en favoritos (`es_favorito`: true/false)
    - Total de solicitudes de adopción recibidas
    """
    animal = db.query(models.Animal).options(joinedload(models.Animal.refugio)).filter(models.Animal.id_animal == id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal no encontrado")

    es_favorito = False
    if current_user:
        fav = db.query(models.Favorito).filter(
            models.Favorito.id_usuario == current_user.id_usuario,
            models.Favorito.id_animal == id_animal
        ).first()
        es_favorito = fav is not None

    total_solicitudes = db.query(models.SolicitudAdopcion).filter(
        models.SolicitudAdopcion.id_animal == id_animal
    ).count()

    return schemas.AnimalDetalleCompletoResponse(
        id_animal=animal.id_animal,
        id_refugio=animal.id_refugio,
        nombre=animal.nombre,
        especie=animal.especie,
        raza=animal.raza,
        sexo=animal.sexo,
        edad_estimada=animal.edad_estimada,
        tamano=animal.tamano,
        descripcion=animal.descripcion,
        foto_url=animal.foto_url,
        estado_adopcion=animal.estado_adopcion,
        refugio=schemas.RefugioResponse.model_validate(animal.refugio) if animal.refugio else None,
        es_favorito=es_favorito,
        total_solicitudes=total_solicitudes
    )
