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
@app.get("/", response_class=HTMLResponse)
def Carga_temporal(request: Request, current_user: models.User = Depends(get_current_user)):
    return templates.TemplateResponse("base.html", {"request": request, "current_user": current_user})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)