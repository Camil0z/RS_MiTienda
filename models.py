# models.py
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

# Modelo de la tabla "users".
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    whatsapp = Column(String, nullable=True)  

    # Relación: un usuario puede tener varios productos y valoraciones    
    products = relationship("Product", back_populates="owner")
    ratings = relationship("Rating", back_populates="user")

# Modelo de la tabla "products".
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
    image = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relación: cada producto pertenece a un usuario y puede recibir valoraciones
    owner = relationship("User", back_populates="products")
    ratings = relationship("Rating", back_populates="product")


# Modelo de la tabla "ratings"
class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Relación: cada valoración pertenece a un usuario y a un producto
    user = relationship("User", back_populates="ratings")
    product = relationship("Product", back_populates="ratings")
    
    # Restricción: asegura que un usuario no pueda valorar el mismo producto más de una vez
    __table_args__ = (UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)