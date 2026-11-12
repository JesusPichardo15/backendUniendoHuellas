-- ====================================================================
-- ESQUEMA COMPLETO PARA MYSQL WORKBENCH / DOCKER
-- Base de Datos: adopciones_db
-- ====================================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE DATABASE IF NOT EXISTS adopciones_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE adopciones_db;

-- 1. Tabla: Roles
CREATE TABLE IF NOT EXISTS roles (
    id_rol INT AUTO_INCREMENT PRIMARY KEY,
    nombre_rol VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Tabla: Refugios
CREATE TABLE IF NOT EXISTS refugios (
    id_refugio INT AUTO_INCREMENT PRIMARY KEY,
    nombre_organizacion VARCHAR(150) NOT NULL,
    direccion VARCHAR(255) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    estado VARCHAR(100) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    logo_url VARCHAR(500) NULL,
    estado_cuenta VARCHAR(30) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Tabla: Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    id_rol INT NOT NULL,
    id_refugio INT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    CONSTRAINT fk_usuarios_roles FOREIGN KEY (id_rol) REFERENCES roles(id_rol) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_usuarios_refugios FOREIGN KEY (id_refugio) REFERENCES refugios(id_refugio) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Tabla: Animales
CREATE TABLE IF NOT EXISTS animales (
    id_animal INT AUTO_INCREMENT PRIMARY KEY,
    id_refugio INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    especie VARCHAR(50) NOT NULL,
    raza VARCHAR(100) NOT NULL,
    sexo VARCHAR(20) NOT NULL,
    edad_estimada VARCHAR(50) NOT NULL,
    tamano VARCHAR(30) NOT NULL,
    descripcion TEXT NULL,
    foto_url VARCHAR(500) NULL,
    estado_adopcion VARCHAR(30) NOT NULL DEFAULT 'disponible',
    CONSTRAINT fk_animales_refugios FOREIGN KEY (id_refugio) REFERENCES refugios(id_refugio) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Tabla: Solicitudes_Adopcion
CREATE TABLE IF NOT EXISTS solicitudes_adopcion (
    id_solicitud INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    id_animal INT NOT NULL,
    mensaje TEXT NULL,
    estado_solicitud VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    notas_internas TEXT NULL,
    fecha_solicitud DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_solicitudes_usuarios FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_solicitudes_animales FOREIGN KEY (id_animal) REFERENCES animales(id_animal) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Tabla: Favoritos
CREATE TABLE IF NOT EXISTS favoritos (
    id_favorito INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    id_animal INT NOT NULL,
    CONSTRAINT uq_favorito_usuario_animal UNIQUE (id_usuario, id_animal),
    CONSTRAINT fk_favoritos_usuarios FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_favoritos_animales FOREIGN KEY (id_animal) REFERENCES animales(id_animal) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================================================================
-- DATOS INICIALES DE PRUEBA (SEEDS)
-- ====================================================================

-- Roles
INSERT IGNORE INTO roles (id_rol, nombre_rol) VALUES
(1, 'Administrador'),
(2, 'Refugio / Encargado'),
(3, 'Adoptante');

-- Refugios
INSERT IGNORE INTO refugios (id_refugio, nombre_organizacion, direccion, ciudad, estado, telefono, logo_url, estado_cuenta) VALUES
(1, 'Huellitas con Amor', 'Av. Siempre Viva 742, Col. Primavera', 'Monterrey', 'Nuevo León', '8181234567', 'https://images.unsplash.com/photo-1548767797-d8c844163c4c?w=400', 'activo'),
(2, 'Refugio Esperanza Animal', 'Calle Los Olivos 120, Col. Centro', 'Guadalajara', 'Jalisco', '3339876543', 'https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=400', 'activo');

-- Usuarios (Contraseñas de prueba: admin123, refugio123, adoptante123)
-- Hashes SHA-256 compatibles con el backend
INSERT IGNORE INTO usuarios (id_usuario, id_rol, id_refugio, nombre_completo, correo, password_hash, telefono) VALUES
(1, 1, NULL, 'Carlos Méndez', 'admin@nubiraweather.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '8110001122'),
(2, 2, 1, 'María Fernández', 'maria@huellitasconamor.org', 'cde8c765ccc2c4df9ff7ddfaabd3eb75dec43244912be09b378a59c8e9de1d4a', '8189998877'),
(3, 3, NULL, 'Jesús Pichardo', 'jesus@ejemplo.com', 'c8775dee4a4e7db87c6a9fb1d30067ef0835f0b717d86d7f4fefb91ff6960f40', '8123456789'),
(4, 3, NULL, 'Sofía Gómez', 'sofia@ejemplo.com', 'c8775dee4a4e7db87c6a9fb1d30067ef0835f0b717d86d7f4fefb91ff6960f40', '3312345678');

-- Animales
INSERT IGNORE INTO animales (id_animal, id_refugio, nombre, especie, raza, sexo, edad_estimada, tamano, descripcion, foto_url, estado_adopcion) VALUES
(1, 1, 'Max', 'Perro', 'Golden Retriever Mestizo', 'Macho', '2 años', 'Grande', 'Muy cariñoso, juguetón y convive excelente con niños y otros perros.', 'https://images.unsplash.com/photo-1552053831-71594a27632d?w=600', 'disponible'),
(2, 1, 'Luna', 'Gato', 'Siamés Mestizo', 'Hembra', '1 año', 'Pequeño', 'Tranquila, ronroneadora y adora dormir cerca de la ventana.', 'https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=600', 'disponible'),
(3, 2, 'Rocky', 'Perro', 'Husky Siberiano', 'Macho', '3 años', 'Grande', 'Energético, requiere espacio para correr y paseos diarios.', 'https://images.unsplash.com/photo-1507146426996-ef05306b995a?w=600', 'disponible'),
(4, 2, 'Milo', 'Gato', 'Europeo común', 'Macho', '6 meses', 'Pequeño', 'Cachorro juguetón, desparasitado y con todas sus vacunas al corriente.', 'https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=600', 'en_proceso'),
(5, 1, 'Firulais', 'Perro', 'Mestizo cariñoso', 'Macho', '2 años', 'Mediano', 'Juguetón, alegre y muy leal. Le encanta pasear en parques.', 'https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=600', 'disponible');

-- Solicitudes de Adopción
INSERT IGNORE INTO solicitudes_adopcion (id_solicitud, id_usuario, id_animal, mensaje, estado_solicitud, notas_internas, fecha_solicitud) VALUES
(1, 3, 1, 'Hola, tengo una casa con patio grande y busco un perrito cariñoso para mi familia.', 'pendiente', 'Casa con jardín inspeccionada telefónicamente.', NOW()),
(2, 4, 2, 'Vivo sola en departamento y me encantaría darle un hogar tranquilo a Luna.', 'aprobada', 'Adoptante verificada, entrega agendada.', NOW());

-- Favoritos
INSERT IGNORE INTO favoritos (id_favorito, id_usuario, id_animal) VALUES
(1, 3, 1),
(2, 3, 3),
(3, 4, 2);
