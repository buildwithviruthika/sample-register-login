from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import User
from backend.auth import hash_password, verify_password
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, validator
import re

app = FastAPI()
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    return True, ""

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None

def validate_username(username: str) -> tuple[bool, str]:
    """Validate username"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 50:
        return False, "Username must be less than 50 characters"
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, ""

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.post("/register")
def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Validate username
    username_valid, username_error = validate_username(username)
    if not username_valid:
        return templates.TemplateResponse("register.html", {"request": request, "error": username_error})
    
    # Validate email
    if not validate_email(email):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Invalid email format"})
    
    # Validate password
    password_valid, password_error = validate_password(password)
    if not password_valid:
        return templates.TemplateResponse("register.html", {"request": request, "error": password_error})
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"})
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})
    
    # Create user
    user = User(username=username, email=email, password=hash_password(password))
    db.add(user)
    db.commit()
    return RedirectResponse("/login?registered=true", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, registered: bool = False, error: str = None):
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "registered": registered,
        "error": error
    })

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if not username or not password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Please fill in all fields"
        })
    
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    if not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="user", value=user.username, httponly=True, secure=False, samesite="lax")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("user")

    if not username:
        return RedirectResponse("/login")

    user = db.query(User).filter(User.username == username).first()
    all_users = db.query(User).order_by(User.created_at.desc()).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "all_users": all_users
    })

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key="user")
    return response

@app.post("/delete-user/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("user")
    
    if not username:
        return RedirectResponse("/login")
    
    current_user = db.query(User).filter(User.username == username).first()
    
    # Prevent users from deleting themselves
    if current_user.id == user_id:
        return RedirectResponse("/dashboard")
    
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    
    if user_to_delete:
        db.delete(user_to_delete)
        db.commit()
    
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/login", status_code=303)
