# database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL para la base de datos SQLite
DATABASE_URL = "sqlite:///./mi_tienda.db"

# Crear el motor de la base de datos
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Crear una clase de sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para los modelos
Base = declarative_base()