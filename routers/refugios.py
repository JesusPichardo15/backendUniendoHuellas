from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from auth import get_current_user, require_admin, require_refugio_or_admin

router = APIRouter(prefix="/api/refugios", tags=["Refugios (Separados y Relacionales)"])


# =====================================================================
# 1. TABLA SEPARADA: CRUD DE REFUGIOS
# =====================================================================

@router.get("", response_model=List[schemas.RefugioResponse], summary="Listar refugios (Tabla Separada con Filtros)")
def get_refugios(
    ciudad: Optional[str] = Query(None, description="Filtrar por ciudad"),
    estado: Optional[str] = Query(None, description="Filtrar por estado/provincia"),
    estado_cuenta: Optional[str] = Query(None, description="Filtrar por estado de cuenta (ej: 'activo')"),
    db: Session = Depends(get_db)
):
    """
    Obtiene los refugios registrados con filtros opcionales.
    Consulta de tabla separada directa.
    """
    query = db.query(models.Refugio)
    if ciudad:
        query = query.filter(models.Refugio.ciudad.ilike(f"%{ciudad.strip()}%"))
    if estado:
        query = query.filter(models.Refugio.estado.ilike(f"%{estado.strip()}%"))
    if estado_cuenta:
        query = query.filter(models.Refugio.estado_cuenta == estado_cuenta.strip())

    return query.order_by(models.Refugio.id_refugio.desc()).all()


@router.get("/{id_refugio}", response_model=schemas.RefugioResponse, summary="Obtener un refugio por ID")
def get_refugio_by_id(id_refugio: int, db: Session = Depends(get_db)):
    """Obtiene los datos de un refugio específico."""
    refugio = db.query(models.Refugio).filter(models.Refugio.id_refugio == id_refugio).first()
    if not refugio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refugio no encontrado")
    return refugio


@router.post("", response_model=schemas.RefugioResponse, status_code=status.HTTP_201_CREATED, summary="Crear un refugio (Admin)")
def create_refugio(
    data: schemas.RefugioCreate,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Crea una nueva organización de refugio (Requiere Administrador)."""
    nuevo_refugio = models.Refugio(**data.model_dump())
    db.add(nuevo_refugio)
    db.commit()
    db.refresh(nuevo_refugio)
    return nuevo_refugio


@router.put("/{id_refugio}", response_model=schemas.RefugioResponse, summary="Actualizar datos de un refugio")
def update_refugio(
    id_refugio: int,
    data: schemas.RefugioUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Actualiza la información de un refugio.
    Solo el Administrador o el Encargado asignado a dicho refugio pueden modificarlo.
    """
    # Si es encargado de refugio, verificar que sea de su propio refugio
    if current_user.id_rol != 1 and current_user.id_refugio != id_refugio:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar la información de otro refugio."
        )

    refugio = db.query(models.Refugio).filter(models.Refugio.id_refugio == id_refugio).first()
    if not refugio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refugio no encontrado")

    update_dict = data.model_dump(exclude_unset=True)
    # Solo admin puede cambiar el estado_cuenta (ej. suspenderlo)
    if "estado_cuenta" in update_dict and current_user.id_rol != 1:
        del update_dict["estado_cuenta"]

    for key, value in update_dict.items():
        setattr(refugio, key, value)

    db.commit()
    db.refresh(refugio)
    return refugio


@router.delete("/{id_refugio}", response_model=schemas.MensajeRespuesta, summary="Eliminar un refugio (Admin)")
def delete_refugio(
    id_refugio: int,
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """Elimina un refugio del sistema (Requiere Administrador)."""
    refugio = db.query(models.Refugio).filter(models.Refugio.id_refugio == id_refugio).first()
    if not refugio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refugio no encontrado")

    db.delete(refugio)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Refugio eliminado exitosamente", id=id_refugio)


# =====================================================================
# 2. TABLAS JUNTAS: CONSULTAS RELACIONALES DE REFUGIOS
# =====================================================================

@router.get("/{id_refugio}/animales", response_model=List[schemas.AnimalResponse], summary="Obtener los animales de un refugio (JOIN Refugios + Animales)")
def get_refugio_animales(
    id_refugio: int,
    estado_adopcion: Optional[str] = Query(None, description="Filtrar por 'disponible', 'adoptado', etc."),
    db: Session = Depends(get_db)
):
    """Retorna todos los animales que pertenecen a este refugio."""
    query = db.query(models.Animal).filter(models.Animal.id_refugio == id_refugio)
    if estado_adopcion:
        query = query.filter(models.Animal.estado_adopcion == estado_adopcion.strip())
    return query.order_by(models.Animal.id_animal.desc()).all()


@router.get("/{id_refugio}/completo", response_model=schemas.RefugioCompletoResponse, summary="Refugio Completo con Encargados y Animales (JOIN 3 tablas)")
def get_refugio_completo(id_refugio: int, db: Session = Depends(get_db)):
    """
    Retorna el detalle completo de un refugio, uniendo:
    - Datos del refugio
    - Lista de usuarios/encargados vinculados
    - Lista de animales registrados y conteo de disponibles
    """
    refugio = db.query(models.Refugio).filter(models.Refugio.id_refugio == id_refugio).first()
    if not refugio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refugio no encontrado")

    animales_disponibles = [a for a in refugio.animales if a.estado_adopcion == "disponible"]

    return schemas.RefugioCompletoResponse(
        id_refugio=refugio.id_refugio,
        nombre_organizacion=refugio.nombre_organizacion,
        direccion=refugio.direccion,
        ciudad=refugio.ciudad,
        estado=refugio.estado,
        telefono=refugio.telefono,
        logo_url=refugio.logo_url,
        estado_cuenta=refugio.estado_cuenta,
        usuarios=[schemas.UsuarioResponse.model_validate(u) for u in refugio.usuarios],
        animales=[schemas.AnimalResponse.model_validate(a) for a in refugio.animales],
        total_animales_disponibles=len(animales_disponibles)
    )


@router.get("/relacion/con-animales", response_model=List[schemas.RefugioConAnimalesResponse], summary="Todos los refugios con su lista de animales (JOIN)")
def get_all_refugios_con_animales(
    estado_cuenta: str = Query("activo", description="Filtrar por estado de cuenta"),
    db: Session = Depends(get_db)
):
    """Retorna la lista de refugios activos junto con los animales que tienen en resguardo."""
    refugios = db.query(models.Refugio).filter(models.Refugio.estado_cuenta == estado_cuenta).all()
    resultado = []
    for ref in refugios:
        resultado.append(
            schemas.RefugioConAnimalesResponse(
                id_refugio=ref.id_refugio,
                nombre_organizacion=ref.nombre_organizacion,
                direccion=ref.direccion,
                ciudad=ref.ciudad,
                estado=ref.estado,
                telefono=ref.telefono,
                logo_url=ref.logo_url,
                estado_cuenta=ref.estado_cuenta,
                animales=[schemas.AnimalResponse.model_validate(a) for a in ref.animales],
                total_animales=len(ref.animales)
            )
        )
    return resultado
