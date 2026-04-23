"""Netlify serverless function entry point for FastAPI."""
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import re

load_dotenv()

# MongoDB connection settings
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "log_res")

# MongoDB clients
sync_client = MongoClient(MONGODB_URL)
sync_database = sync_client[DATABASE_NAME]

# Async client
async_client = None
async_database = None


async def get_mongodb():
    global async_client, async_database
    if async_client is None:
        async_client = AsyncIOMotorClient(MONGODB_URL)
        async_database = async_client[DATABASE_NAME]
    return async_database


async def get_users_collection():
    db = await get_mongodb()
    return db["users"]


# Auth
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


# User model
from datetime import datetime
from typing import Dict, Any


class User:
    def __init__(self, user_data: Dict[str, Any]):
        self._data = user_data
        self.id = str(user_data.get("_id", "")) if "_id" in user_data else user_data.get("id", "")
        self.username = user_data.get("username", "")
        self.email = user_data.get("email", "")
        self.password = user_data.get("password", "")
        self.created_at = user_data.get("created_at", datetime.utcnow())
        self.updated_at = user_data.get("updated_at", datetime.utcnow())

    def to_dict(self) -> Dict[str, Any]:
        result = self._data.copy()
        if "_id" in result:
            result["id"] = str(result["_id"])
            del result["_id"]
        if isinstance(result.get("created_at"), datetime):
            result["created_at"] = result["created_at"].strftime('%B %d, %Y')
        if isinstance(result.get("updated_at"), datetime):
            result["updated_at"] = result["updated_at"].strftime('%B %d, %Y')
        return result

    @staticmethod
    def create_new(username: str, email: str, hashed_password: str) -> Dict[str, Any]:
        return {
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

    @staticmethod
    def from_mongo_doc(doc: Dict[str, Any]) -> 'User':
        return User(doc)


# Create FastAPI app
app = FastAPI()

# Get the directory paths for templates and static
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# Validation functions
def validate_password(password: str) -> tuple[bool, str]:
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
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


def validate_username(username: str) -> tuple[bool, str]:
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 50:
        return False, "Username must be less than 50 characters"
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, ""


# Routes
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), users_collection=Depends(get_users_collection)):
    username_valid, username_error = validate_username(username)
    if not username_valid:
        return templates.TemplateResponse("register.html", {"request": request, "error": username_error})

    if not validate_email(email):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Invalid email format"})

    password_valid, password_error = validate_password(password)
    if not password_valid:
        return templates.TemplateResponse("register.html", {"request": request, "error": password_error})

    existing_user = await users_collection.find_one({"username": username})
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"})

    existing_email = await users_collection.find_one({"email": email})
    if existing_email:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})

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
async def login(request: Request, username: str = Form(...), password: str = Form(...), users_collection=Depends(get_users_collection)):
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
async def dashboard(request: Request, users_collection=Depends(get_users_collection)):
    username = request.cookies.get("user")

    if not username:
        return RedirectResponse("/login")

    user_doc = await users_collection.find_one({"username": username})
    all_users_docs = await users_collection.find().sort("created_at", -1).to_list(length=None)

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
async def delete_user(user_id: str, request: Request, users_collection=Depends(get_users_collection)):
    username = request.cookies.get("user")

    if not username:
        return RedirectResponse("/login")

    current_user_doc = await users_collection.find_one({"username": username})

    if current_user_doc and str(current_user_doc["_id"]) == user_id:
        return RedirectResponse("/dashboard")

    try:
        object_id = ObjectId(user_id)
        await users_collection.delete_one({"_id": object_id})
    except:
        await users_collection.delete_one({"id": user_id})

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/login", status_code=303)


# Netlify serverless function handler
handler = app
