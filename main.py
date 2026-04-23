from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, validator
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import MongoClient
from bson import ObjectId
import re

from backend.database import get_users_collection, get_sync_users_collection
from backend.models import User
from backend.auth import hash_password, verify_password

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def get_users_collection():
    """Dependency function to get MongoDB users collection.
    
    Returns:
        MongoDB users collection
    """
    from backend.database import get_users_collection as get_collection
    return await get_collection()

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
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), users_collection: AsyncIOMotorCollection = Depends(get_users_collection)):
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
    existing_user = await users_collection.find_one({"username": username})
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"})
    
    # Check if email already exists
    existing_email = await users_collection.find_one({"email": email})
    if existing_email:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})
    
    # Create user
    user_data = User.create_new(username, email, hash_password(password))
    await users_collection.insert_one(user_data)
    
    return RedirectResponse("/login?registered=true", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, registered: bool = False, error: str = None):
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "registered": registered,
        "error": error
    })

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), users_collection: AsyncIOMotorCollection = Depends(get_users_collection)):
    if not username or not password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Please fill in all fields"
        })
    
    user_doc = await users_collection.find_one({"username": username})

    if not user_doc:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    if not verify_password(password, user_doc["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="user", value=user_doc["username"], httponly=True, secure=False, samesite="lax")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, users_collection: AsyncIOMotorCollection = Depends(get_users_collection)):
    username = request.cookies.get("user")

    if not username:
        return RedirectResponse("/login")

    user_doc = await users_collection.find_one({"username": username})
    all_users_docs = await users_collection.find().sort("created_at", -1).to_list(length=None)
    
    # Convert to User objects for template compatibility
    user = User.from_mongo_doc(user_doc) if user_doc else None
    all_users = [User.from_mongo_doc(doc) for doc in all_users_docs]

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
async def delete_user(user_id: str, request: Request, users_collection: AsyncIOMotorCollection = Depends(get_users_collection)):
    username = request.cookies.get("user")
    
    if not username:
        return RedirectResponse("/login")
    
    current_user_doc = await users_collection.find_one({"username": username})
    
    # Prevent users from deleting themselves
    if current_user_doc and str(current_user_doc["_id"]) == user_id:
        return RedirectResponse("/dashboard")
    
    # Delete user by ObjectId
    try:
        object_id = ObjectId(user_id)
        result = await users_collection.delete_one({"_id": object_id})
    except:
        # If ObjectId conversion fails, try with string ID
        result = await users_collection.delete_one({"id": user_id})
    
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/login", status_code=303)
