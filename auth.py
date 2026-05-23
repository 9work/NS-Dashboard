import json
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        # مستخدمين أوليين مع الصلاحيات المطلوبة (تم تصحيح الدومين بوضع الشرطة - بدلاً من النقطة)
        default_users = {
            "ahmed.essam@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع الازهر2", "فرع الازهر3", "فرع القلعة", "فرع الموسكى"],
                "is_admin": False
            },
            "shenouda.samir@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع فيصل", "فرع حلوان", "فرع الحصرى - اكتوبر"],
                "is_admin": False
            },
            "abdelrahmanmagdy@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع مدينة نصر", "فرع النزهة", "فرع زهراء المعادي"],
                "is_admin": False
            },
            "amr.elshenawy@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع طنطا", "فرع الاسكندرية", "فرع المنصورة", "فرع سموحة"],
                "is_admin": False
            },
            "youssef.ramzy@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع ثاوث جيت - التجمع", "فرع اير مول - مدينتى", "فرع مافيدا", "فرع مول العرب", "فرع مول مصر", "فرع الشيخ زايد"],
                "is_admin": False
            },
            "ahmed.magdy.bedir@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع مول العرب", "فرع مول مصر", "فرع الشيخ زايد"],
                "is_admin": False
            },
            "sherif.hassieb@nstextile-eg.com": {
                "password": hash_password("123"),
                "branches": ["فرع دمياط - تجزئة"],
                "is_admin": False
            },
            "mohamed.hussein@nstextile-eg.com": {
                "password": hash_password("admin123"),
                "branches": [],
                "is_admin": True
            },
            "mahmoud.bayoumi@nstextile-eg.com": {
                "password": hash_password("123456"),
                "branches": [],
                "is_admin": True
            }
        }
        if not save_users(default_users):
            print(f"Warning: could not create {USERS_FILE}; using default users in memory.")
        return default_users
    
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
    except PermissionError as e:
        print(f"Warning: could not write users file at {USERS_FILE}: {e}")
        return False
    return True

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(email, password):
    users = load_users()
    if email in users and users[email]["password"] == hash_password(password):
        return users[email]
    return None

def add_user(email, password, branches, is_admin=False):
    users = load_users()
    users[email] = {
        "password": hash_password(password),
        "branches": branches,
        "is_admin": is_admin
    }
    save_users(users)

def update_user(email, password=None, branches=None, is_admin=None):
    users = load_users()
    if email in users:
        if password:
            users[email]["password"] = hash_password(password)
        if branches is not None:
            users[email]["branches"] = branches
        if is_admin is not None:
            users[email]["is_admin"] = is_admin
        save_users(users)

def delete_user(email):
    users = load_users()
    if email in users:
        del users[email]
        save_users(users)