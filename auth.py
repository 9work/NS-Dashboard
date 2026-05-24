import json
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")

# أنواع الصلاحيات
PERMISSION_TYPES = {
    "super_admin": "مدير عام",
    "all_branches": "جميع الفروع",
    "specific_branches": "فروع معينة"
}

def load_users():
    if not os.path.exists(USERS_FILE):
        # مستخدمين أوليين مع الصلاحيات المحسّنة
        default_users = {
            "ahmed.essam@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",  # branch أو sales_rep
                "branches": ["فرع الازهر2", "فرع الازهر3", "فرع القلعة", "فرع الموسكى"],
                "sales_reps": []
            },
            "shenouda.samir@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",
                "branches": ["فرع فيصل", "فرع حلوان", "فرع الحصرى - اكتوبر"],
                "sales_reps": []
            },
            "abdelrahmanmagdy@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",
                "branches": ["فرع مدينة نصر", "فرع النزهة", "فرع زهراء المعادي"],
                "sales_reps": []
            },
            "amr.elshenawy@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",
                "branches": ["فرع طنطا", "فرع الاسكندرية", "فرع المنصورة", "فرع سموحة"],
                "sales_reps": []
            },
            "youssef.ramzy@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "all_branches",
                "branch_filter_type": None,
                "branches": [],
                "sales_reps": []
            },
            "ahmed.magdy.bedir@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",
                "branches": ["فرع مول العرب", "فرع مول مصر", "فرع الشيخ زايد"],
                "sales_reps": []
            },
            "sherif.hassieb@nstextile-eg.com": {
                "password": hash_password("123"),
                "permission_type": "specific_branches",
                "branch_filter_type": "branch",
                "branches": ["فرع دمياط - تجزئة"],
                "sales_reps": []
            },
            "mohamed.hussein@nstextile-eg.com": {
                "password": hash_password("admin123"),
                "permission_type": "all_branches",
                "branch_filter_type": None,
                "branches": [],
                "sales_reps": []
            },
            "mahmoud.bayoumi@nstextile-eg.com": {
                "password": hash_password("123456"),
                "permission_type": "super_admin",
                "branch_filter_type": None,
                "branches": [],
                "sales_reps": []
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
        user = users[email].copy()
        # التوافقية مع النظام القديم
        user["is_admin"] = user.get("permission_type") in ["super_admin", "all_branches"]
        if user.get("permission_type") == "super_admin":
            user["branches"] = []
        elif user.get("permission_type") == "all_branches":
            user["branches"] = []
        else:
            user["branches"] = user.get("branches", [])
        return user
    return None

def get_user_permission_type(email):
    """الحصول على نوع صلاحية المستخدم"""
    users = load_users()
    if email in users:
        return users[email].get("permission_type", "specific_branches")
    return None

def is_super_admin(email):
    """التحقق من أن المستخدم مدير عام"""
    return get_user_permission_type(email) == "super_admin"

def can_access_all_branches(email):
    """التحقق من أن المستخدم له صلاحية على كل الفروع"""
    perm_type = get_user_permission_type(email)
    return perm_type in ["super_admin", "all_branches"]

def add_user(email, password, permission_type="specific_branches", branch_filter_type="branch", branches=None, sales_reps=None):
    users = load_users()
    users[email] = {
        "password": hash_password(password),
        "permission_type": permission_type,
        "branch_filter_type": branch_filter_type if permission_type == "specific_branches" else None,
        "branches": branches or [],
        "sales_reps": sales_reps or []
    }
    save_users(users)

def update_user(email, password=None, permission_type=None, branch_filter_type=None, branches=None, sales_reps=None):
    users = load_users()
    if email in users:
        if password:
            users[email]["password"] = hash_password(password)
        if permission_type is not None:
            users[email]["permission_type"] = permission_type
            if permission_type != "specific_branches":
                users[email]["branch_filter_type"] = None
        if branch_filter_type is not None:
            users[email]["branch_filter_type"] = branch_filter_type if permission_type == "specific_branches" else None
        if branches is not None:
            users[email]["branches"] = branches
        if sales_reps is not None:
            users[email]["sales_reps"] = sales_reps
        save_users(users)

def delete_user(email):
    users = load_users()
    if email in users:
        del users[email]
        save_users(users)

def get_all_users():
    """الحصول على قائمة بجميع المستخدمين"""
    return load_users()
