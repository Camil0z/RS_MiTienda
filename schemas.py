from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    whatsapp: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    stock: int

class ProductEdit(BaseModel):
    name: str
    description: str
    price: float
    stock: int