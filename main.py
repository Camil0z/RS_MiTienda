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

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

sessions = {}

def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if session_token and session_token in sessions:
        user_id = sessions[session_token]
        user = db.query(models.User).filter(models.User.id == user_id).first()
        return user
    return None

@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(request: Request, 
                  username: str = Form(...),
                  email: str = Form(...), 
                  password: str = Form(...), 
                  whatsapp: str = Form(...),  
                  db: Session = Depends(get_db)):
                  
    existing_user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "msg": "El usuario o el correo ya existen"})
    
    hashed_password = pwd_context.hash(password)
    user = models.User(username=username, email=email, hashed_password=hashed_password, whatsapp=whatsapp)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_user(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Credenciales incorrectas"})
    
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token and session_token in sessions:
        del sessions[session_token]
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response

@app.get("/", response_class=HTMLResponse)
def read_products(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    products = db.query(models.Product).all()
    products_with_ratings = []
    
    for product in products:
        rating_count = len(product.ratings)
        products_with_ratings.append((product, rating_count))
    
    products_with_ratings.sort(key=lambda x: x[1], reverse=True)
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "products_with_ratings": products_with_ratings, 
        "current_user": current_user
    })


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
    
    image_dir = os.path.join("static", "images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

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


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    rating_count = len(product.ratings)
    
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
    
    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    
    if image and image.filename:
        old_image_path = os.path.join("static", "images", product.image)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)
        
        image_filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join("static", "images", image_filename)
        
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        product.image = image_filename
    
    db.commit()
    db.refresh(product)
    
    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)


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
    
    image_path = os.path.join("static", "images", product.image)
    if os.path.exists(image_path):
        os.remove(image_path)
    
    db.delete(product)
    db.commit()
    
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


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


@app.post("/rate_product/{product_id}")
def rate_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para puntuar un producto")
    
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    existing_rating = db.query(models.Rating).filter(
        models.Rating.user_id == current_user.id, 
        models.Rating.product_id == product_id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=400, detail="Ya has puntuado este producto")
    
    rating = models.Rating(user_id=current_user.id, product_id=product_id)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    
    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)