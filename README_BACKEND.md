# 🐾 Backend - Plataforma de Adopción de Mascotas (Nubira / Huellitas)

Backend RESTful desarrollado en **FastAPI** con **SQLAlchemy**, **PyMySQL**, **JWT**, autenticación con roles, CORS flexible y soporte completo tanto para **MySQL (MySQL Workbench)** como para SQLite de respaldo.

---

## 🚀 Cómo Iniciar el Servidor

1. **Activar el entorno virtual de Python**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Ejecutar el servidor de desarrollo**:
   ```powershell
   python main.py
   # o bien:
   uvicorn main:app --reload --port 8000
   ```

3. **Abrir la documentación interactiva en el navegador**:
   - **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🗄️ Conexión con MySQL Workbench

En el archivo [`.env`](.env) encontrarás la configuración para tu base de datos local de MySQL:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=tu_password_de_workbench
DB_NAME=adopciones_db
DATABASE_URL=mysql+pymysql://root:tu_password_de_workbench@localhost:3306/adopciones_db?charset=utf8mb4
USE_SQLITE_FALLBACK=true
```

> **Nota:** Si en algún momento MySQL está apagado, el sistema conmuta automáticamente a la base de datos SQLite local (`adopciones.db`) para que nunca se interrumpa tu desarrollo en el frontend.

---

## 🔐 Autenticación y Roles

El backend implementa autenticación basada en **JSON Web Tokens (JWT)** con 3 roles jerárquicos:

| ID Rol | Nombre del Rol | Descripción |
|---|---|---|
| **1** | `Administrador` | Acceso total: gestión de roles, todos los refugios, usuarios y métricas globales. |
| **2** | `Refugio / Encargado` | Vinculado a un `id_refugio`. Puede dar de alta sus animales, editar sus datos y aprobar/rechazar solicitudes. |
| **3** | `Adoptante` | Usuario público. Puede ver el catálogo, guardar favoritos y enviar solicitudes de adopción. |

### Cuentas de Prueba Preconfiguradas:
- **Admin**: `admin@nubiraweather.com` / Contraseña: `admin123`
- **Encargado de Refugio**: `maria@huellitasconamor.org` / Contraseña: `refugio123`
- **Adoptante**: `jesus@ejemplo.com` / Contraseña: `adoptante123`

---

## 📋 Resumen de Endpoints Disponibles

### 1. Autenticación y Registro (`/api/auth`)
- `POST /api/auth/register`: Registro público de adoptantes.
- `POST /api/auth/register-refugio`: Alta simultánea de la casa de adopción (`Refugios`) y su usuario encargado (`Usuarios`).
- `POST /api/auth/login`: Inicio de sesión (retorna Token JWT + datos del usuario y rol).
- `GET /api/auth/me`: Perfil del usuario actualmente autenticado.

### 2. Consultas de Tablas Separadas (CRUD Directo)
- **Roles**:
  - `GET /api/roles` (listar todos)
  - `GET /api/roles/{id_rol}` (por ID)
  - `POST /api/roles` (crear - Admin)
  - `PUT /api/roles/{id_rol}` (editar - Admin)
  - `DELETE /api/roles/{id_rol}` (eliminar - Admin)
- **Refugios**:
  - `GET /api/refugios` (listar con filtros: `ciudad`, `estado`, `estado_cuenta`)
  - `GET /api/refugios/{id_refugio}` (por ID)
  - `POST /api/refugios` (crear)
  - `PUT /api/refugios/{id_refugio}` (editar)
  - `DELETE /api/refugios/{id_refugio}` (eliminar)
- **Animales**:
  - `GET /api/animales` (listar con filtros: `especie`, `raza`, `sexo`, `tamano`, `estado_adopcion`, `id_refugio`, `q`)
  - `GET /api/animales/{id_animal}` (por ID)
  - `POST /api/animales` (dar de alta mascota)
  - `PUT /api/animales/{id_animal}` (editar mascota)
  - `DELETE /api/animales/{id_animal}` (eliminar mascota)
- **Usuarios**:
  - `GET /api/usuarios` (listar con filtros: `id_rol`, `id_refugio`)
  - `GET /api/usuarios/{id_usuario}` (por ID)
  - `POST /api/usuarios` (crear)
  - `PUT /api/usuarios/{id_usuario}` (editar)
  - `DELETE /api/usuarios/{id_usuario}` (eliminar)
- **Solicitudes de Adopción**:
  - `GET /api/solicitudes` (listar con filtros: `estado_solicitud`, `id_usuario`, `id_animal`)
  - `GET /api/solicitudes/{id_solicitud}` (por ID)
  - `POST /api/solicitudes` (enviar solicitud)
  - `PUT /api/solicitudes/{id_solicitud}/estado` (aprobar / rechazar con notas internas)
  - `DELETE /api/solicitudes/{id_solicitud}` (cancelar solicitud)
- **Favoritos**:
  - `GET /api/favoritos` (listar)
  - `POST /api/favoritos` (agregar mascota a favoritos)
  - `DELETE /api/favoritos/{id_favorito}` (quitar por ID de favorito)
  - `DELETE /api/favoritos/animal/{id_animal}` (quitar directo por ID de animal para botón toggle)
  - `GET /api/favoritos/verificar/{id_animal}` (retorna `{"es_favorito": true/false}`)

### 3. Consultas de Tablas Juntas (JOINS / Relacionales)
- **Animales + Refugios**:
  - `GET /api/animales/relacion/con-refugio`: Listado de animales con todos los datos de su refugio embebidos.
  - `GET /api/animales/{id_animal}/detalle-completo`: Detalle con refugio, si el usuario logueado lo tiene en favoritos y conteo de solicitudes.
- **Refugios + Animales**:
  - `GET /api/refugios/{id_refugio}/animales`: Lista de animales de un refugio en específico.
  - `GET /api/refugios/{id_refugio}/completo`: Datos del refugio + lista de encargados + animales registrados.
  - `GET /api/refugios/relacion/con-animales`: Todos los refugios con sus mascotas disponibles.
- **Solicitudes + Usuarios + Animales + Refugios (JOIN Cuádruple)**:
  - `GET /api/solicitudes/relacion/detalladas`: Lista completa con datos del adoptante, animal y refugio.
  - `GET /api/solicitudes/relacion/mis-solicitudes`: Solicitudes del usuario logueado con la ficha de la mascota y refugio.
  - `GET /api/solicitudes/relacion/refugio/{id_refugio}`: Postulaciones recibidas por un refugio específico con datos de contacto del adoptante.
- **Favoritos + Animales + Refugios**:
  - `GET /api/favoritos/relacion/mis-favoritos`: Favoritos del usuario con ficha completa de la mascota y del refugio.
- **Usuarios + Roles + Refugios**:
  - `GET /api/usuarios/relacion/detallados`: Lista de usuarios con objetos completos de su rol y refugio asignado.
  - `GET /api/usuarios/{id_usuario}/perfil-completo`: Perfil de usuario con su rol, refugio, historial de solicitudes y favoritos.

### 4. Consultas Especiales y Dashboard Web (`/api/consultas-juntas`)
- `GET /api/consultas-juntas/catalogo`: Catálogo público optimizado para el portal web con filtros combinados (especie, tamaño, sexo, ciudad, texto libre).
- `GET /api/consultas-juntas/refugios-directorio`: Directorio de refugios activos con su conteo de animales disponibles.
- `GET /api/consultas-juntas/adopciones-exitosas`: Historial de animales adoptados con datos del adoptante y refugio.
- `GET /api/consultas-juntas/dashboard`: Métricas globales consolidadas (totales, desglose por especie, solicitudes pendientes/aprobadas y últimos animales).

---

## 🌐 Configuración de CORS
CORS está configurado en [`main.py`](main.py) permitiendo:
- `http://localhost:3000` (Next.js / React)
- `http://localhost:5173` (Vite)
- Despliegues en Vercel con la expresión regular `r"https://.*\.vercel\.app"`
- Todos los métodos HTTP (`GET`, `POST`, `PUT`, `DELETE`, etc.) y cabeceras (`Authorization`, `Content-Type`, etc.).
