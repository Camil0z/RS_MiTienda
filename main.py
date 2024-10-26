# main.py

from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import shutil
from typing import Optional
import uuid
import os

# Crear las tablas en la base de datos
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configuración de Jinja2 Templates y Static Files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Contexto para manejar hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependencia para obtener la sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Diccionario para almacenar sesiones (Nota: esto es básico y no persistente)
sessions = {}

# Función para obtener el usuario actual
def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if session_token and session_token in sessions:
        user_id = sessions[session_token]
        user = db.query(models.User).filter(models.User.id == user_id).first()
        return user
    return None

# Ruta para registrar usuarios
@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(request: Request, 
                  username: str = Form(...),
                  email: str = Form(...), 
                  password: str = Form(...), 
                  whatsapp: str = Form(...),  # Aceptar el campo whatsapp
                  db: Session = Depends(get_db)):
                  
    # Verificar si el usuario o email ya existen
    existing_user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "msg": "El usuario o el correo ya existen"})
    
    # Crear nuevo usuario
    hashed_password = pwd_context.hash(password)
    user = models.User(username=username, email=email, hashed_password=hashed_password, whatsapp=whatsapp)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Iniciar sesión automáticamente después del registro
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

# Ruta para iniciar sesión
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_user(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Buscar usuario por username
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Credenciales incorrectas"})
    
    # Crear sesión
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

# Ruta para cerrar sesión
@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token and session_token in sessions:
        del sessions[session_token]
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response

# Ruta principal temporal
#@app.get("/", response_class=HTMLResponse)
#def Carga_temporal(request: Request, current_user: models.User = Depends(get_current_user)):
#    return templates.TemplateResponse("base.html", {"request": request, "current_user": current_user})

# Ruta principal para mostrar productos
@app.get("/", response_class=HTMLResponse)
def read_products(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Obtener todos los productos con su número de puntuaciones
    products = db.query(models.Product).all()
    products_with_ratings = []
    
    for product in products:
        rating_count = len(product.ratings)
        products_with_ratings.append((product, rating_count))
    
    # Ordenar productos de mayor a menor según rating_count
    products_with_ratings.sort(key=lambda x: x[1], reverse=True)
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "products_with_ratings": products_with_ratings, 
        "current_user": current_user
    })


# Ruta para agregar un nuevo producto
@app.get("/add_product", response_class=HTMLResponse)
def add_product_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("add_product.html", {
        "request": request, 
        "current_user": current_user
    })

@app.post("/add_product")
async def add_product(request: Request, name: str = Form(...), description: str = Form(...), 
                      price: float = Form(...), stock: int = Form(...), 
                      image: UploadFile = File(...), db: Session = Depends(get_db), 
                      current_user: models.User = Depends(get_current_user)):
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Verificar si la carpeta 'static/images' existe, y si no, crearla
    image_dir = os.path.join("static", "images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    # Validar y guardar la imagen
    if not image.filename:
        return templates.TemplateResponse("add_product.html", {
            "request": request, 
            "current_user": current_user, 
            "msg": "No se ha cargado ninguna imagen"
        })
    
    image_filename = f"{uuid.uuid4()}_{image.filename}"
    image_path = os.path.join("static", "images", image_filename)
    
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    product = models.Product(name=name, description=description, price=price, 
                             stock=stock, image=image_filename, 
                             owner_id=current_user.id)
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


# Ruta para ver detalles de un producto
@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Contar los votos (ratings)
    rating_count = len(product.ratings)
    
    # Verificar si el usuario actual ya ha puntuado este producto
    user_has_rated = False
    if current_user:
        existing_rating = db.query(models.Rating).filter(
            models.Rating.user_id == current_user.id, 
            models.Rating.product_id == product_id
        ).first()
        
        if existing_rating:
            user_has_rated = True
    
    return templates.TemplateResponse("product_detail.html", {
        "request": request, 
        "product": product, 
        "rating_count": rating_count, 
        "user_has_rated": user_has_rated, 
        "current_user": current_user
    })


# Ruta para editar un producto
@app.get("/edit_product/{product_id}", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    product = db.query(models.Product).filter(
        models.Product.id == product_id, 
        models.Product.owner_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para editarlo")
    
    return templates.TemplateResponse("edit_product.html", {
        "request": request, 
        "product": product, 
        "current_user": current_user
    })

@app.post("/edit_product/{product_id}")
async def edit_product(product_id: int, request: Request, name: str = Form(...), description: str = Form(...), 
                       price: float = Form(...), stock: int = Form(...), 
                       image: UploadFile = File(None), db: Session = Depends(get_db), 
                       current_user: models.User = Depends(get_current_user)):
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    product = db.query(models.Product).filter(
        models.Product.id == product_id, 
        models.Product.owner_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para editarlo")
    
    # Actualizar los campos
    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    
    # Si se carga una nueva imagen, actualizarla
    if image and image.filename:
        # Eliminar la imagen anterior
        old_image_path = os.path.join("static", "images", product.image)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)
        
        # Guardar la nueva imagen
        image_filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join("static", "images", image_filename)
        
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        # Actualizar el nombre de la imagen en el producto
        product.image = image_filename
    
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)


# Ruta para eliminar un producto
@app.post("/delete_product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    product = db.query(models.Product).filter(
        models.Product.id == product_id, 
        models.Product.owner_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para eliminarlo")
    
    # Eliminar la imagen asociada
    image_path = os.path.join("static", "images", product.image)
    if os.path.exists(image_path):
        os.remove(image_path)
    
    db.delete(product)
    db.commit()
    
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


# Ruta para ver detalles del usuario (autor)
@app.get("/user/{user_id}", response_class=HTMLResponse)
def user_detail(request: Request, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return templates.TemplateResponse("user_detail.html", {
        "request": request, 
        "user": user, 
        "current_user": current_user
    })


# Ruta para puntuar un producto
@app.post("/rate_product/{product_id}")
def rate_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para puntuar un producto")
    
    # Verificar si el producto existe
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar si el usuario ya ha puntuado este producto
    existing_rating = db.query(models.Rating).filter(
        models.Rating.user_id == current_user.id, 
        models.Rating.product_id == product_id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=400, detail="Ya has puntuado este producto")
    
    # Crear una nueva puntuación
    rating = models.Rating(user_id=current_user.id, product_id=product_id)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    
    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    