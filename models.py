from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Rol(Base):
    __tablename__ = "roles"

    id_rol = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_rol = Column(String(50), nullable=False)

    # Relaciones
    usuarios = relationship("Usuario", back_populates="rol")


class Refugio(Base):
    __tablename__ = "refugios"

    id_refugio = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_organizacion = Column(String(150), nullable=False)
    direccion = Column(String(255), nullable=False)
    ciudad = Column(String(100), nullable=False)
    estado = Column(String(100), nullable=False)
    telefono = Column(String(30), nullable=False)
    logo_url = Column(String(500), nullable=True)
    estado_cuenta = Column(String(30), nullable=False, default="activo")  # activo, pendiente, suspendido

    # Relaciones
    usuarios = relationship("Usuario", back_populates="refugio")
    animales = relationship("Animal", back_populates="refugio", cascade="all, delete-orphan")


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_rol = Column(Integer, ForeignKey("roles.id_rol"), nullable=False)
    id_refugio = Column(Integer, ForeignKey("refugios.id_refugio"), nullable=True)
    nombre_completo = Column(String(150), nullable=False)
    correo = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    telefono = Column(String(30), nullable=False)

    # Relaciones
    rol = relationship("Rol", back_populates="usuarios")
    refugio = relationship("Refugio", back_populates="usuarios")
    solicitudes = relationship("SolicitudAdopcion", back_populates="usuario", cascade="all, delete-orphan")
    favoritos = relationship("Favorito", back_populates="usuario", cascade="all, delete-orphan")


class Animal(Base):
    __tablename__ = "animales"

    id_animal = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_refugio = Column(Integer, ForeignKey("refugios.id_refugio"), nullable=False)
    nombre = Column(String(100), nullable=False)
    especie = Column(String(50), nullable=False)  # Perro, Gato, etc.
    raza = Column(String(100), nullable=False)
    sexo = Column(String(20), nullable=False)     # Macho, Hembra
    edad_estimada = Column(String(50), nullable=False)
    tamano = Column(String(30), nullable=False)   # Pequeño, Mediano, Grande
    descripcion = Column(Text, nullable=True)
    foto_url = Column(String(500), nullable=True)
    estado_adopcion = Column(String(30), nullable=False, default="disponible") # disponible, en_proceso, adoptado

    # Relaciones
    refugio = relationship("Refugio", back_populates="animales")
    solicitudes = relationship("SolicitudAdopcion", back_populates="animal", cascade="all, delete-orphan")
    favoritos = relationship("Favorito", back_populates="animal", cascade="all, delete-orphan")


class SolicitudAdopcion(Base):
    __tablename__ = "solicitudes_adopcion"

    id_solicitud = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_animal = Column(Integer, ForeignKey("animales.id_animal"), nullable=False)
    mensaje = Column(Text, nullable=True)
    estado_solicitud = Column(String(30), nullable=False, default="pendiente") # pendiente, aprobada, rechazada
    notas_internas = Column(Text, nullable=True)
    fecha_solicitud = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relaciones
    usuario = relationship("Usuario", back_populates="solicitudes")
    animal = relationship("Animal", back_populates="solicitudes")


class Favorito(Base):
    __tablename__ = "favoritos"

    id_favorito = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_animal = Column(Integer, ForeignKey("animales.id_animal"), nullable=False)

    # Relaciones
    usuario = relationship("Usuario", back_populates="favoritos")
    animal = relationship("Animal", back_populates="favoritos")
