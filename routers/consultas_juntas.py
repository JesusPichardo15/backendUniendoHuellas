from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from database import get_db
import models
import schemas
from auth import require_admin, require_refugio_or_admin

router = APIRouter(prefix="/api/consultas-juntas", tags=["Consultas de Tablas Juntas (JOINS y Dashboard)"])


@router.get("/catalogo", response_model=List[schemas.AnimalConRefugioResponse], summary="Catálogo Principal Web (JOIN Animales + Refugios)")
def get_catalogo_web(
    especie: Optional[str] = Query(None, description="Perro, Gato, Conejo, etc."),
    tamano: Optional[str] = Query(None, description="Pequeño, Mediano, Grande"),
    sexo: Optional[str] = Query(None, description="Macho, Hembra"),
    ciudad: Optional[str] = Query(None, description="Ciudad donde se ubica el refugio"),
    estado: Optional[str] = Query(None, description="Estado de la república"),
    q: Optional[str] = Query(None, description="Texto de búsqueda libre"),
    db: Session = Depends(get_db)
):
    """
    JOIN Animales + Refugios:
    Retorna los animales disponibles para adopción junto a todos los datos de contacto
    y ubicación del refugio correspondiente. Listo para poblar la vista principal de la web.
    """
    query = db.query(models.Animal).join(models.Refugio).options(joinedload(models.Animal.refugio))

    # Solo animales disponibles y de refugios con estado de cuenta activo
    query = query.filter(
        models.Animal.estado_adopcion == "disponible",
        models.Refugio.estado_cuenta == "activo"
    )

    if especie:
        query = query.filter(models.Animal.especie.ilike(f"%{especie.strip()}%"))
    if tamano:
        query = query.filter(models.Animal.tamano.ilike(f"%{tamano.strip()}%"))
    if sexo:
        query = query.filter(models.Animal.sexo.ilike(f"%{sexo.strip()}%"))
    if ciudad:
        query = query.filter(models.Refugio.ciudad.ilike(f"%{ciudad.strip()}%"))
    if estado:
        query = query.filter(models.Refugio.estado.ilike(f"%{estado.strip()}%"))
    if q:
        termino = f"%{q.strip()}%"
        query = query.filter(
            (models.Animal.nombre.ilike(termino)) |
            (models.Animal.especie.ilike(termino)) |
            (models.Animal.raza.ilike(termino)) |
            (models.Animal.tamano.ilike(termino)) |
            (models.Animal.descripcion.ilike(termino)) |
            (models.Refugio.nombre_organizacion.ilike(termino))
        )

    return query.order_by(models.Animal.id_animal.desc()).all()


@router.get("/refugios-directorio", response_model=List[schemas.RefugioConAnimalesResponse], summary="Directorio de Refugios con sus Mascotas (JOIN Refugios + Animales)")
def get_directorio_refugios(
    ciudad: Optional[str] = Query(None, description="Filtrar por ciudad"),
    db: Session = Depends(get_db)
):
    """
    JOIN Refugios + Animales:
    Directorio de casas de adopción activas, mostrando su dirección, contacto
    y la lista de todos sus animales disponibles.
    """
    query = db.query(models.Refugio).filter(models.Refugio.estado_cuenta == "activo")
    if ciudad:
        query = query.filter(models.Refugio.ciudad.ilike(f"%{ciudad.strip()}%"))

    refugios = query.all()
    resultado = []
    for ref in refugios:
        animales_disponibles = [a for a in ref.animales if a.estado_adopcion == "disponible"]
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
                animales=[schemas.AnimalResponse.model_validate(a) for a in animales_disponibles],
                total_animales=len(animales_disponibles)
            )
        )
    return resultado


@router.get("/solicitudes-completas", response_model=List[schemas.SolicitudDetalladaResponse], summary="Todas las Solicitudes con Usuarios, Animales y Refugios (JOIN 4 Tablas)")
def get_solicitudes_completas(
    estado_solicitud: Optional[str] = Query(None, description="pendiente, aprobada, rechazada"),
    db: Session = Depends(get_db),
    _current_user: models.Usuario = Depends(require_admin)
):
    """
    JOIN Cuádruple: Solicitudes + Usuarios + Animales + Refugios.
    Permite auditoría completa de adopciones para el Administrador.
    """
    query = db.query(models.SolicitudAdopcion).options(
        joinedload(models.SolicitudAdopcion.usuario),
        joinedload(models.SolicitudAdopcion.animal).joinedload(models.Animal.refugio)
    )

    if estado_solicitud:
        query = query.filter(models.SolicitudAdopcion.estado_solicitud == estado_solicitud.strip())

    solicitudes = query.order_by(models.SolicitudAdopcion.fecha_solicitud.desc()).all()

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


@router.get("/adopciones-exitosas", summary="Historial de Adopciones Aprobadas (JOIN)")
def get_adopciones_exitosas(db: Session = Depends(get_db)):
    """
    Retorna la lista de todas las adopciones concretadas (solicitud aprobada),
    mostrando el animal adoptado, el refugio de origen y el adoptante.
    """
    solicitudes = db.query(models.SolicitudAdopcion).options(
        joinedload(models.SolicitudAdopcion.usuario),
        joinedload(models.SolicitudAdopcion.animal).joinedload(models.Animal.refugio)
    ).filter(models.SolicitudAdopcion.estado_solicitud == "aprobada").order_by(models.SolicitudAdopcion.fecha_solicitud.desc()).all()

    historial = []
    for s in solicitudes:
        historial.append({
            "id_solicitud": s.id_solicitud,
            "fecha_adopcion": s.fecha_solicitud,
            "adoptante": {
                "id_usuario": s.usuario.id_usuario,
                "nombre_completo": s.usuario.nombre_completo,
                "correo": s.usuario.correo,
                "telefono": s.usuario.telefono
            },
            "animal": {
                "id_animal": s.animal.id_animal,
                "nombre": s.animal.nombre,
                "especie": s.animal.especie,
                "raza": s.animal.raza,
                "foto_url": s.animal.foto_url
            },
            "refugio": {
                "id_refugio": s.animal.refugio.id_refugio if s.animal.refugio else None,
                "nombre_organizacion": s.animal.refugio.nombre_organizacion if s.animal.refugio else None,
                "ciudad": s.animal.refugio.ciudad if s.animal.refugio else None
            }
        })
    return historial


@router.get("/dashboard", response_model=schemas.DashboardResumenResponse, summary="Panel de Control y Métricas Generales")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Calcula todas las métricas agregadas del sistema:
    - Conteo de refugios totales y activos
    - Conteo de animales totales, disponibles y adoptados
    - Conteo de solicitudes y desglose por estado (pendientes, aprobadas)
    - Agrupación de animales por especie (Perros, Gatos, etc.)
    - Últimos animales dados de alta
    """
    total_refugios = db.query(models.Refugio).count()
    total_refugios_activos = db.query(models.Refugio).filter(models.Refugio.estado_cuenta == "activo").count()

    total_animales = db.query(models.Animal).count()
    total_animales_disponibles = db.query(models.Animal).filter(models.Animal.estado_adopcion == "disponible").count()
    total_animales_adoptados = db.query(models.Animal).filter(models.Animal.estado_adopcion == "adoptado").count()

    total_usuarios = db.query(models.Usuario).count()
    total_solicitudes = db.query(models.SolicitudAdopcion).count()
    solicitudes_pendientes = db.query(models.SolicitudAdopcion).filter(models.SolicitudAdopcion.estado_solicitud == "pendiente").count()
    solicitudes_aprobadas = db.query(models.SolicitudAdopcion).filter(models.SolicitudAdopcion.estado_solicitud == "aprobada").count()

    # Agrupación por especie
    especies_conteo = db.query(
        models.Animal.especie,
        func.count(models.Animal.id_animal)
    ).group_by(models.Animal.especie).all()

    dict_especies = {esp: cnt for esp, cnt in especies_conteo}

    # Últimos 5 animales ingresados
    ultimos_animales = db.query(models.Animal).options(
        joinedload(models.Animal.refugio)
    ).order_by(models.Animal.id_animal.desc()).limit(5).all()

    return schemas.DashboardResumenResponse(
        total_refugios=total_refugios,
        total_refugios_activos=total_refugios_activos,
        total_animales=total_animales,
        total_animales_disponibles=total_animales_disponibles,
        total_animales_adoptados=total_animales_adoptados,
        total_usuarios=total_usuarios,
        total_solicitudes=total_solicitudes,
        solicitudes_pendientes=solicitudes_pendientes,
        solicitudes_aprobadas=solicitudes_aprobadas,
        animales_por_especie=dict_especies,
        ultimos_animales=[schemas.AnimalConRefugioResponse.model_validate(a) for a in ultimos_animales]
    )
