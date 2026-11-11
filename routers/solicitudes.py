from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from database import get_db
import models
import schemas
from auth import (
    get_current_user,
    require_refugio_or_admin,
    require_admin
)

router = APIRouter(prefix="/api/solicitudes", tags=["Solicitudes de Adopción (Separadas y Relacionales)"])


# =====================================================================
# 1. CONSULTAS DE TABLA SEPARADA (CRUD DE SOLICITUDES)
# =====================================================================

@router.get("", response_model=List[schemas.SolicitudResponse], summary="Listar solicitudes (Tabla Separada con Filtros)")
def get_solicitudes(
    estado_solicitud: Optional[str] = Query(None, description="pendiente, aprobada, rechazada"),
    id_usuario: Optional[int] = Query(None, description="Filtrar por id de usuario solicitante"),
    id_animal: Optional[int] = Query(None, description="Filtrar por id de animal"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Obtiene la lista de solicitudes de adopción directamente de la tabla separada `Solicitudes_Adopcion`.
    Requiere rol de Encargado de Refugio o Administrador.
    """
    query = db.query(models.SolicitudAdopcion)
    if estado_solicitud:
        query = query.filter(models.SolicitudAdopcion.estado_solicitud == estado_solicitud.strip())
    if id_usuario:
        query = query.filter(models.SolicitudAdopcion.id_usuario == id_usuario)
    if id_animal:
        query = query.filter(models.SolicitudAdopcion.id_animal == id_animal)

    return query.order_by(models.SolicitudAdopcion.id_solicitud.desc()).all()


@router.get("/{id_solicitud}", response_model=schemas.SolicitudResponse, summary="Obtener una solicitud por ID")
def get_solicitud_by_id(
    id_solicitud: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Obtiene una solicitud específica por su ID."""
    solicitud = db.query(models.SolicitudAdopcion).filter(models.SolicitudAdopcion.id_solicitud == id_solicitud).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    # Validar permisos: el solicitante, el refugio del animal o el admin
    if current_user.id_rol == 3 and solicitud.id_usuario != current_user.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver la solicitud de otro usuario.")

    return solicitud


@router.post("", response_model=schemas.SolicitudResponse, status_code=status.HTTP_201_CREATED, summary="Enviar una nueva solicitud de adopción")
def create_solicitud(
    data: schemas.SolicitudCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Crea una nueva solicitud de adopción para una mascota.
    Toma automáticamente el `id_usuario` del usuario logueado.
    """
    # Verificar que el animal existe y está disponible
    animal = db.query(models.Animal).filter(models.Animal.id_animal == data.id_animal).first()
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El animal especificado no existe.")

    if animal.estado_adopcion == "adoptado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este animal ya ha sido adoptado.")

    # Verificar si el usuario ya tiene una solicitud pendiente para este animal
    solicitud_existente = db.query(models.SolicitudAdopcion).filter(
        models.SolicitudAdopcion.id_usuario == current_user.id_usuario,
        models.SolicitudAdopcion.id_animal == data.id_animal,
        models.SolicitudAdopcion.estado_solicitud == "pendiente"
    ).first()
    if solicitud_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya tienes una solicitud pendiente para esta mascota."
        )

    nueva_solicitud = models.SolicitudAdopcion(
        id_usuario=current_user.id_usuario,
        id_animal=data.id_animal,
        mensaje=data.mensaje.strip() if data.mensaje else None,
        estado_solicitud="pendiente",
        notas_internas=None,
        fecha_solicitud=datetime.utcnow()
    )
    db.add(nueva_solicitud)
    db.commit()
    db.refresh(nueva_solicitud)
    return nueva_solicitud


@router.put("/{id_solicitud}/estado", response_model=schemas.SolicitudResponse, summary="Aprobar o Rechazar solicitud (Refugio o Admin)")
def update_solicitud_estado(
    id_solicitud: int,
    data: schemas.SolicitudUpdateEstado,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Permite al personal del refugio o al Admin cambiar el estado de la solicitud:
    - 'aprobada' (puede cambiar automáticamente el estado_adopcion del animal a 'en_proceso' o 'adoptado')
    - 'rechazada'
    - 'pendiente'
    """
    solicitud = db.query(models.SolicitudAdopcion).filter(models.SolicitudAdopcion.id_solicitud == id_solicitud).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    # Si es encargado de refugio, validar que el animal pertenezca a su refugio
    if current_user.id_rol != 1 and solicitud.animal.id_refugio != current_user.id_refugio:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes gestionar solicitudes de mascotas de otro refugio."
        )

    estado_normalizado = data.estado_solicitud.strip().lower()
    if estado_normalizado not in ("pendiente", "aprobada", "rechazada"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado de solicitud inválido.")

    solicitud.estado_solicitud = estado_normalizado
    if data.notas_internas is not None:
        solicitud.notas_internas = data.notas_internas.strip()

    # Si se aprueba la adopción, actualizar el estado del animal
    if estado_normalizado == "aprobada":
        solicitud.animal.estado_adopcion = "adoptado"
    elif estado_normalizado == "pendiente" and solicitud.animal.estado_adopcion == "adoptado":
        solicitud.animal.estado_adopcion = "disponible"

    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.delete("/{id_solicitud}", response_model=schemas.MensajeRespuesta, summary="Cancelar o eliminar solicitud")
def delete_solicitud(
    id_solicitud: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Permite al solicitante cancelar su propia solicitud, o al administrador eliminarla."""
    solicitud = db.query(models.SolicitudAdopcion).filter(models.SolicitudAdopcion.id_solicitud == id_solicitud).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    if current_user.id_rol != 1 and solicitud.id_usuario != current_user.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes cancelar una solicitud que no te pertenece.")

    db.delete(solicitud)
    db.commit()
    return schemas.MensajeRespuesta(mensaje="Solicitud eliminada o cancelada exitosamente", id=id_solicitud)


# =====================================================================
# 2. CONSULTAS DE TABLAS JUNTAS (JOINS / RELACIONALES)
# =====================================================================

@router.get("/relacion/detalladas", response_model=List[schemas.SolicitudDetalladaResponse], summary="Solicitudes Detalladas (JOIN Solicitudes + Usuarios + Animales + Refugios)")
def get_solicitudes_detalladas(
    estado_solicitud: Optional[str] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Consulta relacional completa (JOIN de 4 tablas):
    Retorna la lista de solicitudes con los datos del adoptante, de la mascota y del refugio resguardante.
    """
    query = db.query(models.SolicitudAdopcion).options(
        joinedload(models.SolicitudAdopcion.usuario),
        joinedload(models.SolicitudAdopcion.animal).joinedload(models.Animal.refugio)
    )

    if estado_solicitud:
        query = query.filter(models.SolicitudAdopcion.estado_solicitud == estado_solicitud.strip())

    solicitudes = query.order_by(models.SolicitudAdopcion.id_solicitud.desc()).all()

    resultado = []
    for s in solicitudes:
        resultado.append(
            schemas.SolicitudDetalladaResponse(
                id_solicitud=s.id_solicitud,
                mensaje=s.mensaje,
                estado_solicitud=s.estado_solicitud,
                notas_internas=s.notas_internas,
                fecha_solicitud=s.fecha_solicitud,
                usuario=schemas.UsuarioResponse.model_validate(s.usuario),
                animal=schemas.AnimalConRefugioResponse.model_validate(s.animal)
            )
        )
    return resultado


@router.get("/relacion/mis-solicitudes", response_model=List[schemas.SolicitudDetalladaResponse], summary="Mis solicitudes de adopción (Usuario Autenticado)")
def get_mis_solicitudes(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """
    Retorna todas las solicitudes realizadas por el usuario actualmente logueado,
    con la información completa de la mascota solicitada y el refugio.
    """
    solicitudes = db.query(models.SolicitudAdopcion).options(
        joinedload(models.SolicitudAdopcion.usuario),
        joinedload(models.SolicitudAdopcion.animal).joinedload(models.Animal.refugio)
    ).filter(models.SolicitudAdopcion.id_usuario == current_user.id_usuario).order_by(models.SolicitudAdopcion.id_solicitud.desc()).all()

    resultado = []
    for s in solicitudes:
        resultado.append(
            schemas.SolicitudDetalladaResponse(
                id_solicitud=s.id_solicitud,
                mensaje=s.mensaje,
                estado_solicitud=s.estado_solicitud,
                notas_internas=s.notas_internas,
                fecha_solicitud=s.fecha_solicitud,
                usuario=schemas.UsuarioResponse.model_validate(s.usuario),
                animal=schemas.AnimalConRefugioResponse.model_validate(s.animal)
            )
        )
    return resultado


@router.get("/relacion/refugio/{id_refugio}", response_model=List[schemas.SolicitudDetalladaResponse], summary="Solicitudes recibidas por un refugio específico (JOIN)")
def get_solicitudes_por_refugio(
    id_refugio: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_refugio_or_admin)
):
    """
    Retorna todas las solicitudes de adopción dirigidas a los animales resguardados por el refugio.
    Permite al administrador o al encargado ver a los postulantes con su información de contacto.
    """
    if current_user.id_rol != 1 and current_user.id_refugio != id_refugio:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para ver las solicitudes de otro refugio."
        )

    solicitudes = db.query(models.SolicitudAdopcion).join(models.Animal).filter(
        models.Animal.id_refugio == id_refugio
    ).options(
        joinedload(models.SolicitudAdopcion.usuario),
        joinedload(models.SolicitudAdopcion.animal).joinedload(models.Animal.refugio)
    ).order_by(models.SolicitudAdopcion.id_solicitud.desc()).all()

    resultado = []
    for s in solicitudes:
        resultado.append(
            schemas.SolicitudDetalladaResponse(
                id_solicitud=s.id_solicitud,
                mensaje=s.mensaje,
                estado_solicitud=s.estado_solicitud,
                notas_internas=s.notas_internas,
                fecha_solicitud=s.fecha_solicitud,
                usuario=schemas.UsuarioResponse.model_validate(s.usuario),
                animal=schemas.AnimalConRefugioResponse.model_validate(s.animal)
            )
        )
    return resultado
