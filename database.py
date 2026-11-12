import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

# Configuración de variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "adopciones_db")

MYSQL_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_FILE = os.path.join(BASE_DIR, "adopciones.db")
SQLITE_URL = f"sqlite:///{SQLITE_FILE}"

USE_FALLBACK = os.getenv("USE_SQLITE_FALLBACK", "true").lower() in ("true", "1", "yes")

engine = None
selected_db_type = "unknown"

# Intento de conexión prioritario a MySQL (MySQL Workbench o Docker DB)
if "mysql" in MYSQL_URL.lower():
    import time
    max_retries = int(os.getenv("DB_CONNECT_RETRIES", "5"))
    retry_delay = int(os.getenv("DB_CONNECT_DELAY", "2"))
    connected = False

    for attempt in range(1, max_retries + 1):
        try:
            test_engine = create_engine(
                MYSQL_URL,
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5, "charset": "utf8mb4"}
            )
            with test_engine.connect() as conn:
                pass
            engine = test_engine
            selected_db_type = "MySQL"
            connected = True
            logger.info(f"✅ Conectado exitosamente a la base de datos MySQL en {DB_HOST}:{DB_PORT}/{DB_NAME}")
            break
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"⚠️ Intento {attempt}/{max_retries} conectando a MySQL falló ({e}). Reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.warning(f"⚠️ No se pudo conectar a MySQL tras {max_retries} intentos ({e}).")

    if not connected:
        if USE_FALLBACK and os.path.exists(SQLITE_FILE):
            logger.info(f"🔄 Activando base de datos SQLite local de respaldo ({SQLITE_FILE}).")
            engine = create_engine(
                SQLITE_URL,
                connect_args={"check_same_thread": False}
            )
            selected_db_type = "SQLite (Fallback)"
        else:
            logger.error("❌ Fallback a SQLite deshabilitado o archivo no encontrado. Reintentando con MySQL...")
            engine = create_engine(MYSQL_URL, pool_recycle=3600, pool_pre_ping=True)
            selected_db_type = "MySQL"
else:
    # URL directa de SQLite u otra
    engine = create_engine(MYSQL_URL, connect_args={"check_same_thread": False} if "sqlite" in MYSQL_URL else {})
    selected_db_type = "Custom DB"

# Habilitar soporte de llaves foráneas para SQLite si aplica
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Generador de sesiones para inyección de dependencias en endpoints FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
