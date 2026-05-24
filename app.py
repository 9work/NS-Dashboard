import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import os
from streamlit_theme import st_theme

APP_DIR = Path(__file__).resolve().parent
LIGHT_LOGO = APP_DIR / "assets" / "ns_logo.png"
DARK_LOGO = APP_DIR / "assets" / "ns_logo_dark.png"


def _is_dark_theme() -> bool:
    theme = st_theme(key="ns_dashboard_theme")
    if theme and isinstance(theme, dict):
        return str(theme.get("base", "")).lower() == "dark"
    return False


def _active_logo_path() -> Optional[Path]:
    if LIGHT_LOGO.is_file() and DARK_LOGO.is_file():
        return DARK_LOGO if _is_dark_theme() else LIGHT_LOGO
    if LIGHT_LOGO.is_file():
        return LIGHT_LOGO
    if DARK_LOGO.is_file():
        return DARK_LOGO
    return None


def render_dashboard_header(title: str, logo_width: int = 110):
    logo_path = _active_logo_path()

    if logo_path:
        col_logo, col_title = st.columns([1, 7], vertical_alignment="center")
        with col_logo:
            st.image(str(logo_path), width=logo_width)
        with col_title:
            st.title(title)
    else:
        st.title(title)
from auth import (
    authenticate, load_users, add_user, update_user, delete_user, save_users,
    get_user_permission_type, is_super_admin, can_access_all_branches, get_all_users
)
from data_manager import load_sales_data, load_target_data, compute_kpis, compute_mtd_target

# إعدادات الصفحة
st.set_page_config(page_title="NSTextile Dashboard", layout="wide")

# جلسة المستخدم
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "user_branches" not in st.session_state:
    st.session_state.user_branches = []
if "user_permission_type" not in st.session_state:
    st.session_state.user_permission_type = None
if "user_branch_filter_type" not in st.session_state:
    st.session_state.user_branch_filter_type = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "mtd_mode" not in st.session_state:
    st.session_state.mtd_mode = "Last sales date"
if "mtd_month_length" not in st.session_state:
    st.session_state.mtd_month_length = 25

# تعديل الدالة لتقرأ الملفات المرفوعة مؤقتاً تلقائياً في حال وجودها
@st.cache_resource
def load_all_data():
    # التحقق من ملف المبيعات
    if os.path.exists("temp_sales.xlsx"):
        sales_path = "temp_sales.xlsx"
    else:
        sales_path = "Sales (Naguib Selim) This Month.xlsx"
        
    # التحقق من ملف الأهداف
    if os.path.exists("temp_target.xlsx"):
        target_path = "temp_target.xlsx"
    else:
        target_path = "Target This Month.xlsx"
        
    sales_df = load_sales_data(sales_path)
    branch_target, rep_target = load_target_data(target_path)
    return sales_df, branch_target, rep_target

def get_sales_date_range(file_path):
    try:
        xls = pd.ExcelFile(file_path)
        sheet_name = None
        for candidate in ["Sales Final", "Sales"]:
            if candidate in xls.sheet_names:
                sheet_name = candidate
                break
        if sheet_name is None:
            sheet_name = xls.sheet_names[0]
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        df.columns = df.columns.astype(str).str.strip()
        date_cols = [c for c in df.columns if c.strip().lower() == "date" or "date" in c.lower() or "تاريخ" in c]
        if not date_cols:
            return None, None
        dates = pd.to_datetime(df[date_cols[0]], errors="coerce").dropna()
        if dates.empty:
            return None, None
        return dates.min().date(), dates.max().date()
    except Exception:
        return None, None


def get_mtd_factor(mode, sales_df, month_length=0):
    today = datetime.today()
    def days_in_month(date):
        next_month = (date.replace(day=28) + timedelta(days=4)).replace(day=1)
        return (next_month - timedelta(days=1)).day

    if mode == "Last sales date":
        if "Date" in sales_df.columns and not sales_df["Date"].dropna().empty:
            last_date = sales_df["Date"].dropna().max()
            if pd.isna(last_date):
                last_date = today
            actual_days = days_in_month(last_date)
            month_days = int(month_length) if month_length and month_length > 0 else actual_days
            month_days = max(1, month_days)
            return min(int(last_date.day), month_days) / month_days
        return 1.0
    month_days = int(month_length) if month_length and month_length > 0 else days_in_month(today)
    month_days = max(1, month_days)
    return min(today.day, month_days) / month_days

# واجهة تسجيل الدخول
def login_page():
    st.title("🔐 تسجيل الدخول")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("البريد الإلكتروني")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول")
    if submitted:
        user = authenticate(email.strip(), password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_email = email.strip()
            st.session_state.user_branches = user.get("branches", [])
            st.session_state.user_permission_type = user.get("permission_type", "specific_branches")
            st.session_state.user_branch_filter_type = user.get("branch_filter_type")
            st.session_state.is_admin = user.get("is_admin", False)
            st.rerun()
        else:
            st.error("بيانات الدخول غير صحيحة")

# صفحة الإعدادات (للمدير فقط)
# صفحة الإعدادات
def settings_page():
    from auth import is_super_admin, get_all_users, PERMISSION_TYPES
    
    st.title("⚙️ الإعدادات")
    
    # =============================================
    # قسم تغيير كلمة المرور (يظهر للجميع)
    # =============================================
    with st.expander("🔑 تغيير كلمة المرور", expanded=True):
        
        # التحقق إذا كان المستخدم مدير عام أم لا
        is_admin = is_super_admin(st.session_state.user_email)
        
        if is_admin:
            # المدير العام: يمكنه تغيير كلمة المرور لأي مستخدم
            st.markdown("**🔐 تغيير كلمة المرور لأي مستخدم (صلاحية المدير العام)**")
            users = get_all_users()
            
            if users:
                # اختيار المستخدم من القائمة
                selected_user_email = st.selectbox(
                    "اختر المستخدم", 
                    list(users.keys()), 
                    key="admin_pass_change_select"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    new_password = st.text_input("كلمة المرور الجديدة", type="password", key="admin_new_pass")
                with col2:
                    confirm_password = st.text_input("تأكيد كلمة المرور", type="password", key="admin_confirm_pass")
                
                if st.button("تحديث كلمة المرور", key="admin_update_pass"):
                    if new_password and new_password == confirm_password:
                        update_user(
                            selected_user_email,
                            password=new_password,
                            permission_type=None,
                            branch_filter_type=None,
                            branches=None
                        )
                        st.success(f"✅ تم تحديث كلمة المرور للمستخدم {selected_user_email} بنجاح")
                        st.rerun()
                    elif not new_password:
                        st.error("❌ يرجى إدخال كلمة المرور الجديدة")
                    else:
                        st.error("❌ كلمات المرور غير متطابقة")
            else:
                st.info("لا يوجد مستخدمون")
        
        else:
            # المستخدم العادي: يغير كلمة المرور الخاصة به فقط
            st.markdown(f"**🔐 تغيير كلمة المرور الخاصة بحسابك: {st.session_state.user_email}**")
            
            col1, col2 = st.columns(2)
            with col1:
                new_password = st.text_input("كلمة المرور الجديدة", type="password", key="user_new_pass")
            with col2:
                confirm_password = st.text_input("تأكيد كلمة المرور", type="password", key="user_confirm_pass")
            
            if st.button("تحديث كلمة المرور", key="user_update_pass"):
                if new_password and new_password == confirm_password:
                    update_user(
                        st.session_state.user_email,
                        password=new_password,
                        permission_type=None,
                        branch_filter_type=None,
                        branches=None
                    )
                    st.success("✅ تم تحديث كلمة المرور بنجاح")
                    st.info("🔐 سيتم تطبيق التغيير عند تسجيل الدخول下一次")
                    st.rerun()
                elif not new_password:
                    st.error("❌ يرجى إدخال كلمة المرور الجديدة")
                else:
                    st.error("❌ كلمات المرور غير متطابقة")
    
    st.markdown("---")
    
    # =============================================
    # باقي الإعدادات (تظهر فقط للمدير العام)
    # =============================================
    if not is_super_admin(st.session_state.user_email):
        st.warning("⚠️ الإعدادات المتقدمة متاحة للمديرين العامين فقط.")
        return
    
    # تبويبات الإعدادات للمدير
    settings_tabs = st.tabs(["📂 البيانات", "👥 المستخدمون", "📆 إعدادات أخرى"])
    
    # تبويب 1: تحميل البيانات
    with settings_tabs[0]:
        st.header("📂 تحديث ملفات البيانات")
        sales_file = st.file_uploader("رفع ملف المبيعات (Sales This Month.xlsx)", type=["xlsx"])
        target_file = st.file_uploader("رفع ملف الأهداف (Target This Month.xlsx)", type=["xlsx"])
        if st.button("تحميل ومعالجة"):
            if sales_file and target_file:
                with open("temp_sales.xlsx", "wb") as f:
                    f.write(sales_file.read())
                with open("temp_target.xlsx", "wb") as f:
                    f.write(target_file.read())
                st.cache_resource.clear()
                st.success("تم رفع الملفات وتحديث البيانات بنجاح!")
            else:
                st.error("يرجى رفع كلا الملفين")
        
        st.subheader("📌 معلومات الملفات المرفوعة")
        sales_path = "temp_sales.xlsx" if os.path.exists("temp_sales.xlsx") else "Sales (Naguib Selim) This Month.xlsx"
        target_path = "temp_target.xlsx" if os.path.exists("temp_target.xlsx") else "Target This Month.xlsx"
        st.write("**Sales data file:**", sales_path)
        st.write("**Target data file:**", target_path)
        min_date, max_date = get_sales_date_range(sales_path)
        if min_date and max_date:
            st.write(f"**Sales data range:** {min_date} to {max_date}")
    
    # تبويب 2: إدارة المستخدمين
    with settings_tabs[1]:
        st.header("👥 إدارة المستخدمين")
        users = get_all_users()
        
        # عرض جدول المستخدمين
        users_display = []
        for email, user_data in users.items():
            users_display.append({
                "البريد الإلكتروني": email,
                "نوع الصلاحية": PERMISSION_TYPES.get(user_data.get("permission_type"), "غير محدد"),
                "مصدر الفروع": "مبيعات الفرع (System)" if user_data.get("branch_filter_type") == "branch" else ("مندوب المبيعات" if user_data.get("branch_filter_type") == "sales_rep" else "-"),
                "الفروع": ", ".join(user_data.get("branches", [])) if user_data.get("branches") else "—"
            })
        st.dataframe(pd.DataFrame(users_display), use_container_width=True)
        
        # إضافة مستخدم جديد
        with st.expander("➕ إضافة مستخدم جديد"):
            col1, col2 = st.columns(2)
            with col1:
                new_email = st.text_input("البريد الإلكتروني", key="add_email")
                new_password = st.text_input("كلمة المرور", type="password", key="add_password")
            with col2:
                permission_type = st.selectbox(
                    "نوع الصلاحية", 
                    ["all_branches", "specific_branches"],
                    format_func=lambda x: PERMISSION_TYPES.get(x, x),
                    key="add_permission"
                )
            
            branch_filter_type = None
            branches = []
            
            if permission_type == "specific_branches":
                col1, col2 = st.columns(2)
                with col1:
                    branch_filter_type = st.radio(
                        "تصفية الفروع حسب:",
                        ["branch", "sales_rep"],
                        format_func=lambda x: "مبيعات الفرع (System)" if x == "branch" else "مندوب المبيعات",
                        key="add_filter_type"
                    )
                with col2:
                    branches_input = st.text_area("الفروع المسموحة (كل فرع في سطر)", key="add_branches")
                    branches = [b.strip() for b in branches_input.split("\n") if b.strip()]
            
            if st.button("إضافة المستخدم", key="btn_add_user"):
                if new_email and new_password:
                    add_user(new_email, new_password, permission_type, branch_filter_type, branches)
                    st.success("✅ تمت الإضافة بنجاح")
                    st.rerun()
                else:
                    st.error("❌ يرجى ملء جميع الحقول المطلوبة")
        
        # تعديل صلاحيات مستخدم
        with st.expander("⚙️ تعديل صلاحيات مستخدم"):
            if users:
                edit_email = st.selectbox("اختر المستخدم", list(users.keys()), key="edit_email")
                user_data = users[edit_email]
                
                st.subheader("الصلاحيات")
                current_perm_type = user_data.get("permission_type", "specific_branches")
                new_perm_type = st.selectbox(
                    "نوع الصلاحية",
                    ["all_branches", "specific_branches"],
                    index=["all_branches", "specific_branches"].index(current_perm_type),
                    format_func=lambda x: PERMISSION_TYPES.get(x, x),
                    key="edit_permission"
                )
                
                edit_branches = []
                edit_filter_type = None
                
                if new_perm_type == "specific_branches":
                    current_filter_type = user_data.get("branch_filter_type", "branch")
                    edit_filter_type = st.radio(
                        "تصفية الفروع حسب:",
                        ["branch", "sales_rep"],
                        index=["branch", "sales_rep"].index(current_filter_type),
                        format_func=lambda x: "مبيعات الفرع (System)" if x == "branch" else "مندوب المبيعات",
                        key="edit_filter_type",
                        horizontal=True
                    )
                    
                    current_branches = user_data.get("branches", [])
                    branches_input = st.text_area(
                        "الفروع المسموحة (كل فرع في سطر)",
                        value="\n".join(current_branches),
                        key="edit_branches"
                    )
                    edit_branches = [b.strip() for b in branches_input.split("\n") if b.strip()]
                
                if st.button("حفظ التعديلات", key="btn_update_user"):
                    update_user(
                        edit_email,
                        password=None,
                        permission_type=new_perm_type,
                        branch_filter_type=edit_filter_type,
                        branches=edit_branches if edit_branches else None
                    )
                    st.success("✅ تم تحديث الصلاحيات بنجاح")
                    st.rerun()
        
        # حذف مستخدم
        with st.expander("🗑️ حذف مستخدم"):
            if users:
                del_email = st.selectbox("اختر مستخدم للحذف", list(users.keys()), key="del_email")
                if st.button("حذف المستخدم", key="btn_delete_user"):
                    if del_email != "mahmoud.bayoumi@nstextile-eg.com":
                        delete_user(del_email)
                        st.success("✅ تم الحذف بنجاح")
                        st.rerun()
                    else:
                        st.error("❌ لا يمكن حذف حساب المدير الرئيسي")
    
    # تبويب 3: إعدادات أخرى
    with settings_tabs[2]:
        st.header("📆 إعدادات MTD")
        mtd_mode = st.radio(
            "أساس حساب MTD",
            ["Last sales date", "Today"],
            index=["Last sales date", "Today"].index(st.session_state.mtd_mode) if st.session_state.mtd_mode in ["Last sales date", "Today"] else 0,
        )
        st.session_state.mtd_mode = mtd_mode
        
        if mtd_mode == "Last sales date":
            default_month = st.session_state.mtd_month_length if st.session_state.mtd_month_length > 0 else 25
            month_length = st.number_input(
                "طول الشهر المستخدم للحساب",
                min_value=1,
                max_value=31,
                value=default_month,
                step=1,
                help="حدد عدد أيام الشهر الفعلي عند وجود عطل في الأيام الأخيرة."
            )
            st.session_state.mtd_month_length = month_length
        
        st.write("**نمط MTD الحالي:**", mtd_mode)
        if mtd_mode == "Last sales date":
            st.write(f"**طول الشهر المعين:** {st.session_state.mtd_month_length} يوم")

# واجهة NS Dashboard (Daily Sales) - May 2026
def resolve_allowed_branches(sales_df, branch_column, user_branches, user_branch_filter_type):
    if not user_branches:
        return sorted(sales_df[branch_column].dropna().unique())
    # بما أن أسماء الفروع مطابقة تماماً في كلا العمودين (مبيعات الفرع (System) ومبيعات الفرع حسب البياع)، فإن قائمة الفروع المسموحة هي نفس قائمة فروع حساب المستخدم مباشرة دون الحاجة لأي ربط
    return sorted(user_branches)

# واجهة NS Dashboard (Daily Sales) - May 2026
def dashboard_page():
    render_dashboard_header("NS Dashboard (Daily Sales) - May 2026")
    
    try:
        sales_df, branch_target, rep_target = load_all_data()
    except Exception as e:
        st.error("لم يتم العثور على ملفات البيانات في المجلد، أو أن هناك مشكلة توافق في الملفات المرفوعة. يرجى رفع الملفات الصحيحة من صفحة الإعدادات.")
        return
    
    # --- 1. فلاتر تصفية البيانات في الشريط الجانبي (تظهر أولاً) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 فلاتر تصفية البيانات")

    # اختيار مصدر الفرع: مبيعات الفرع (System) أم الفرع حسب مندوب المبيعات
    branch_source = st.sidebar.radio(
        "مصدر الفرع",
        ["مبيعات الفرع حسب البياع", "مبيعات الفرع (System)"],
    )
    if branch_source == "مبيعات الفرع (System)":
        branch_column = "Branch"
        brand_column = "Brand"
    else:
        branch_column = "Branch based on sales reps"
        brand_column = "Brand based on sales reps"

    # فلتر الفروع حسب صلاحية المستخدم
    user_permission_type = get_user_permission_type(st.session_state.user_email)
    
    if user_permission_type in ["super_admin", "all_branches"] or not st.session_state.user_branches:
        allowed_branches = sorted(sales_df[branch_column].dropna().unique())
    else:
        allowed_branches = resolve_allowed_branches(
            sales_df,
            branch_column,
            st.session_state.user_branches,
            st.session_state.user_branch_filter_type,
        )
    # التحقق من ما إذا كان يجب إظهار فلتر البراند
    # إخفاء فلتر البراند للمستخدمين ذوي صلاحيات على فروع معينة
    show_brand_filter = user_permission_type in ["super_admin", "all_branches"]

    # فلتر العلامة التجارية ونوع العميل في القائمة الجانبية
    if show_brand_filter:
        brand_options = ["الكل"] + sorted(sales_df[brand_column].dropna().unique())
        brand_filter = st.sidebar.selectbox("العلامة التجارية", brand_options)
        
        # حصر خيارات الفروع حسب العلامة التجارية المختارة ومع مراعاة صلاحيات المستخدم
        if brand_filter == "الكل":
            branches_for_brand = list(sales_df[branch_column].dropna().unique())
        else:
            branches_for_brand = list(sales_df[sales_df[brand_column] == brand_filter][branch_column].dropna().unique())
        
        # تصفية الفروع من allowed_branches المحسوبة بناءً على صلاحيات المستخدم
        if user_permission_type in ["super_admin", "all_branches"] or not st.session_state.user_branches:
            branch_options = sorted(branches_for_brand)
        else:
            # استخدام allowed_branches فقط - التي تم حسابها مع مراعاة صلاحيات المستخدم وتحويل الأعمدة
            branch_options = sorted([b for b in allowed_branches if b in branches_for_brand])
            
        branch_choice_options = ["الكل"] + branch_options
        branch_choice = st.sidebar.selectbox("الفرع", branch_choice_options)
    else:
        # اختيار تلقائي "الكل" للعلامة التجارية عند إخفائها للمستخدمين ذوي صلاحيات محدودة
        brand_filter = "الكل"
        # حصر خيارات الفروع حسب الفروع المسموحة فقط
        branches_for_brand = list(sales_df[branch_column].dropna().unique())
        # استخدام allowed_branches فقط (التي تم حسابها بناءً على صلاحيات المستخدم)
        branch_options = sorted([b for b in allowed_branches if b in branches_for_brand])
        
        branch_choice_options = ["الكل"] + branch_options
        branch_choice = st.sidebar.selectbox("الفرع", branch_choice_options)
        
    cust_filter = st.sidebar.selectbox("نوع العميل", ["الكل", "B2B", "B2C"])

    # --- 2. إعدادات MTD في الشريط الجانبي (تظهر ثانياً) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📆 حساب الهدف والنسب (MTD)")
    
    month_length_choice = st.sidebar.radio(
        "طول الشهر المستخدم للحساب",
        ["25 يوم", "عدد أيام الشهر الفعلية"],
        index=0 if st.session_state.mtd_month_length == 25 else 1,
        help="حدد إجمالي عدد الأيام في الشهر المستخدم لحساب نسبة الإنجاز والترجت حتى اليوم."
    )
    
    if month_length_choice == "25 يوم":
        st.session_state.mtd_month_length = 25
    else:
        st.session_state.mtd_month_length = 0

    # تحويل اختيار الفرع إلى قائمة فروع مستخدمة (مطلوب من compute_kpis)
    if branch_choice == "الكل":
        selected_branches = branch_options
    else:
        selected_branches = [branch_choice]

    # إنشاء نسخة مفلترة من بيانات المبيعات تتفاعل مع كل الفلاتر
    filtered_sales = sales_df.copy()
    if selected_branches:
        filtered_sales = filtered_sales[filtered_sales[branch_column].isin(selected_branches)]
    if cust_filter and cust_filter != "الكل":
        filtered_sales = filtered_sales[filtered_sales["Customer Type"] == cust_filter]
    if brand_filter and brand_filter != "الكل":
        filtered_sales = filtered_sales[filtered_sales[brand_column] == brand_filter]

    # حساب المؤشرات الرئيسية باستخدام الفروع المختارة والفلترة حسب البراند
    factor = get_mtd_factor(st.session_state.mtd_mode, sales_df, st.session_state.mtd_month_length)
    kpis = compute_kpis(
        sales_df,
        branch_target,
        selected_branches,
        None if cust_filter=="الكل" else cust_filter,
        None if brand_filter=="الكل" else brand_filter,
        factor,
        branch_col=branch_column,
        brand_col=brand_column,
    )
    
    # عرض بطاقات KPI
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 قيمة المبيعات", f"{kpis['Sales Amount']:,.0f} جنيه", f"{kpis['Sales Ach%']:.1f}% من الهدف")
    col1.metric("🎯 الهدف", f"{kpis['Target Sales']:,.0f} جنيه")
    col2.metric("📦 الكميات المباعة", f"{kpis['Quantity']:,.0f}", f"{kpis['Qty Ach%']:.1f}%")
    col2.metric("🎯 هدف الكميات", f"{kpis['Target Quantity']:,.0f}")
    col3.metric("🧾 عدد الفواتير", f"{kpis['Invoices']:,.0f}", f"{kpis['Invoices Ach%']:.1f}%")
    col3.metric("🎯 هدف الفواتير", f"{kpis['Target Invoices']:,.0f}")
    col4.metric("💵 متوسط الفاتورة (ATV)", f"{kpis['ATV']:,.0f}", f"{kpis['ATV Ach%']:.1f}%")
    col4.metric("🎯 هدف ATV", f"{kpis['Target ATV']:,.0f}")
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔄 قيمة المرتجعات", f"{kpis['Return']:,.0f} جنيه", f"نسبة المرتجعات {kpis['Return Ratio']:.1%}")
    c2.metric("👥 عدد العملاء الفريدين", f"{kpis['Customers']:,.0f}")
    c3.metric("🏷️ الخصم", f"{kpis['Discount']:,.0f} جنيه", f"نسبة الخصم {kpis['Discount Ratio']:.1%}")
    
    # Daily sales chart with achievement percentage (صافي = مبيعات - مرتجعات)
    st.subheader("Daily Sales & Achievement Ratio")
    daily_sales = filtered_sales[filtered_sales["Sales Type"].isin(["Sales", "Return"])].groupby("Date")["Total After Disc"].sum().reset_index()
    daily_sales["Date"] = pd.to_datetime(daily_sales["Date"], errors="coerce")
    daily_sales = daily_sales.dropna(subset=["Date"]).sort_values("Date")
    current_day = datetime.today().day
    target_daily = kpis["Target Sales"] / current_day if current_day > 0 else 0
    daily_sales["Target daily"] = target_daily
    daily_sales["Achievement %"] = daily_sales.apply(
        lambda row: (row["Total After Disc"] / row["Target daily"] * 100) if row["Target daily"] else 0,
        axis=1,
    )
    daily_sales["Date Label"] = daily_sales["Date"].dt.strftime("%d %b<br>%a")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=daily_sales["Date Label"],
            y=daily_sales["Total After Disc"],
            text=daily_sales["Total After Disc"].map(lambda v: f"{v:,.0f}"),
            textposition="outside",
            marker_color="#1f77b4",
            name="Sales",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=daily_sales["Date Label"],
            y=daily_sales["Achievement %"],
            mode="lines+markers",
            marker=dict(color="#ff7f0e", size=8),
            name="Achievement %",
            yaxis="y2",
            hovertemplate="%{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Daily Sales and Achievement",
        xaxis_title="Date",
        yaxis_title="Sales Amount",
        yaxis2=dict(
            title="Achievement %",
            overlaying="y",
            side="right",
            tickformat=".1f%",
            range=[0, max(daily_sales["Achievement %"].max() * 1.2, 100)],
            fixedrange=True,
        ),
        height=520,
        margin=dict(l=50, r=60, t=70, b=90),
        bargap=0.2,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        hovermode="x unified",
        xaxis=dict(tickangle=-45, fixedrange=True),
        yaxis=dict(fixedrange=True),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Sales by Brand and Sales by Customer Type side by side
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sales by Brand")
        # This chart only follows the branch source selection and ignores other filters.
        brand_sales = sales_df[sales_df["Sales Type"].isin(["Sales", "Return"])].groupby(brand_column)["Total After Disc"].sum()
        fig_pie = px.pie(
            values=brand_sales.values,
            names=brand_sales.index,
            title="Sales by Brand",
            hole=0.35,
        )
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(height=420, margin=dict(l=40, r=40, t=60, b=40), legend_title_text="Brand")
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.subheader("Sales by Customer Type")
        cust_sales = filtered_sales[filtered_sales["Sales Type"].isin(["Sales", "Return"])].groupby("Customer Type")["Total After Disc"].sum()
        total_cust = cust_sales.sum()
        cust_percent = (cust_sales / total_cust * 100).round(1)
        fig_cust = px.bar(
            x=cust_sales.index,
            y=cust_sales.values,
            color=cust_sales.index,
            color_discrete_map={"B2B": "#1f77b4", "B2C": "#ff7f0e"},
            text=[f"{p:.1f}%" for p in cust_percent],
            labels={"x": "Customer Type", "y": "Sales Amount"},
            title="Sales by Customer Type",
        )
        fig_cust.update_traces(textposition="outside", marker_line_width=0)
        fig_cust.update_layout(
            height=420,
            margin=dict(l=50, r=40, t=60, b=70),
            xaxis_tickangle=-45,
            yaxis=dict(fixedrange=True),
            xaxis=dict(fixedrange=True),
            showlegend=False,
        )
        st.plotly_chart(fig_cust, use_container_width=True, config={"displayModeBar": False})

    # جداول الأداء
    st.subheader("Branch Performance")
    branch_perf = []
    def find_target_column(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def pct_cell_style(val):
        import math
        try:
            v = float(val)
            if math.isnan(v):
                return ""
        except Exception:
            return ""
        if v < 70:
            return "color:white; background-color:#d9534f"
        elif v < 90:
            return "color:black; background-color:#f0ad4e"
        else:
            return "color:black; background-color:#5cb85c"

    def fmt_pct(val):
        import math
        try:
            v = float(val)
            if math.isnan(v):
                return ""
        except Exception:
            return ""
        return f"{v:.1f}%"

    col_s_b2b = find_target_column(branch_target, ["Sales Target | B2B", "Sales Target B2B", "B2B MTD Target"])
    col_s_b2c = find_target_column(branch_target, ["Sales Target | B2C", "Sales Target B2C", "B2C MTD Target"])
    col_s_total = find_target_column(branch_target, ["Sales Target | TOTAL", "Sales Target TOTAL", "Total Target"])

    for branch in selected_branches:
        target_row = branch_target[branch_target["Branch"] == branch]
        if target_row.empty:
            continue
        target_b2b = float(target_row[col_s_b2b].values[0]) * factor if col_s_b2b else 0
        target_b2c = float(target_row[col_s_b2c].values[0]) * factor if col_s_b2c else 0
        target_total = float(target_row[col_s_total].values[0]) * factor if col_s_total else 0
        if target_total == 0 and target_b2b == 0 and target_b2c == 0:
            continue

        # احسب صافي المبيعات: مجموع Sales و Return (المرتجعات مُسجَّلة بإشارة سالبة عادة)
        sales_b2b = filtered_sales[(filtered_sales[branch_column] == branch) & (filtered_sales["Customer Type"] == "B2B") & (filtered_sales["Sales Type"].isin(["Sales","Return"]))]["Total After Disc"].sum()
        sales_b2c = filtered_sales[(filtered_sales[branch_column] == branch) & (filtered_sales["Customer Type"] == "B2C") & (filtered_sales["Sales Type"].isin(["Sales","Return"]))]["Total After Disc"].sum()
        sales_total = sales_b2b + sales_b2c
        branch_perf.append({
            "Branch": branch,
            "B2B MTD Target": target_b2b,
            "Sales B2B": sales_b2b,
            "B2B %": (sales_b2b / target_b2b * 100) if target_b2b else None,
            "B2C MTD Target": target_b2c,
            "Sales B2C": sales_b2c,
            "B2C %": (sales_b2c / target_b2c * 100) if target_b2c else None,
            "Total Target": target_total,
            "Total Sales": sales_total,
            "Sales %": (sales_total / target_total * 100) if target_total else None,
        })

    branch_perf_df = pd.DataFrame(branch_perf)
    if branch_perf_df.empty:
        st.info("No branch targets available for selected filters.")
    else:
        totals = branch_perf_df[["B2B MTD Target", "Sales B2B", "B2C MTD Target", "Sales B2C", "Total Target", "Total Sales"]].sum(numeric_only=True)
        totals_row = {
            "Branch": "Total",
            "B2B MTD Target": totals["B2B MTD Target"],
            "Sales B2B": totals["Sales B2B"],
            "B2B %": (totals["Sales B2B"] / totals["B2B MTD Target"] * 100) if totals["B2B MTD Target"] else None,
            "B2C MTD Target": totals["B2C MTD Target"],
            "Sales B2C": totals["Sales B2C"],
            "B2C %": (totals["Sales B2C"] / totals["B2C MTD Target"] * 100) if totals["B2C MTD Target"] else None,
            "Total Target": totals["Total Target"],
            "Total Sales": totals["Total Sales"],
            "Sales %": (totals["Total Sales"] / totals["Total Target"] * 100) if totals["Total Target"] else None,
        }
        branch_perf_df = pd.concat([branch_perf_df, pd.DataFrame([totals_row])], ignore_index=True)

        branch_perf_df["B2B MTD Target"] = branch_perf_df["B2B MTD Target"].astype(float)
        branch_perf_df["Sales B2B"] = branch_perf_df["Sales B2B"].astype(float)
        branch_perf_df["B2C MTD Target"] = branch_perf_df["B2C MTD Target"].astype(float)
        branch_perf_df["Sales B2C"] = branch_perf_df["Sales B2C"].astype(float)
        branch_perf_df["Total Target"] = branch_perf_df["Total Target"].astype(float)
        branch_perf_df["Total Sales"] = branch_perf_df["Total Sales"].astype(float)

        styled_branch_perf = branch_perf_df.style.format({
            "B2B MTD Target": "{:,.0f}",
            "Sales B2B": "{:,.0f}",
            "B2B %": fmt_pct,
            "B2C MTD Target": "{:,.0f}",
            "Sales B2C": "{:,.0f}",
            "B2C %": fmt_pct,
            "Total Target": "{:,.0f}",
            "Total Sales": "{:,.0f}",
            "Sales %": fmt_pct,
            "Branch": "{}",
        }, na_rep="").apply(lambda col: col.map(pct_cell_style), subset=["B2B %", "B2C %", "Sales %"], axis=0)

        st.dataframe(styled_branch_perf, use_container_width=True)

    # Sales Rep Performance
    st.subheader("Sales Rep Performance")
    rep_perf = []
    col_r_b2b = find_target_column(rep_target, ["Sales Target | B2B", "Sales Target B2B", "B2B MTD Target"])
    col_r_b2c = find_target_column(rep_target, ["Sales Target | B2C", "Sales Target B2C", "B2C MTD Target"])
    col_r_total = find_target_column(rep_target, ["Sales Target | TOTAL", "Sales Target TOTAL", "Total Target"])

    # Sales Rep Performance should always use 'Branch based on sales reps' as branch source
    rep_branch_col = "Branch based on sales reps"
    rep_brand_col = "Brand based on sales reps"

    # Determine which rep-based branches to include based on the current branch selection.
    if branch_choice == "الكل":
        selected_rep_branches = selected_branches
    else:
        selected_rep_branches = [branch_choice]

    # تصفية الفروع المسموحة للبياعين بناءً على صلاحيات فروع المستخدم (من عمود Branch based on sales reps)
    if user_permission_type not in ["super_admin", "all_branches"] and st.session_state.user_branches:
        selected_rep_branches = [b for b in selected_rep_branches if b in st.session_state.user_branches]

    # Build sales data for reps using rep-based branch mapping, include returns for net calculation
    sales_rep_data = sales_df[sales_df[rep_branch_col].isin(selected_rep_branches) & sales_df["Sales Type"].isin(["Sales", "Return"])].copy()
    # Apply customer-type filter if set
    if cust_filter and cust_filter != "الكل":
        sales_rep_data = sales_rep_data[sales_rep_data["Customer Type"] == cust_filter]
    # Apply brand filter using rep-based brand column
    if brand_filter and brand_filter != "الكل":
        sales_rep_data = sales_rep_data[sales_rep_data[rep_brand_col] == brand_filter]

    # Build complete list of (Sales Rep, Branch) combinations from targets only
    all_pairs = []
    target_pairs = set()
    if isinstance(rep_target, pd.DataFrame) and "Sales Rep" in rep_target.columns and "Branch" in rep_target.columns:
        # Filter rep_target by selected branches and brand
        filtered_rep_target = rep_target[rep_target["Branch"].isin(selected_rep_branches)].copy()
        if brand_filter and brand_filter != "الكل" and "Brand" in filtered_rep_target.columns:
            filtered_rep_target = filtered_rep_target[filtered_rep_target["Brand"] == brand_filter]
        
        for _, row in filtered_rep_target.iterrows():
            r = row["Sales Rep"]
            b = row["Branch"]
            if pd.notna(r) and pd.notna(b):
                target_pairs.add((str(r).strip(), str(b).strip()))

    # Sort them by Branch first, then by Sales Rep name
    all_pairs = sorted(list(target_pairs), key=lambda x: (x[1], x[0]))

    for rep, branch in all_pairs:
        # Find targets for this rep in this branch
        rep_row = pd.DataFrame()
        if isinstance(rep_target, pd.DataFrame) and "Sales Rep" in rep_target.columns and "Branch" in rep_target.columns:
            rep_row = rep_target[
                (rep_target["Sales Rep"].astype(str).str.strip() == rep) & 
                (rep_target["Branch"].astype(str).str.strip() == branch)
            ]
        
        target_b2b = float(pd.to_numeric(rep_row[col_r_b2b], errors="coerce").fillna(0).sum()) * factor if col_r_b2b and not rep_row.empty else 0
        target_b2c = float(pd.to_numeric(rep_row[col_r_b2c], errors="coerce").fillna(0).sum()) * factor if col_r_b2c and not rep_row.empty else 0
        target_total = float(pd.to_numeric(rep_row[col_r_total], errors="coerce").fillna(0).sum()) * factor if col_r_total and not rep_row.empty else 0

        # Find actual sales for this rep in this branch
        rep_sales_df = sales_rep_data[
            (sales_rep_data["Sales Person"].astype(str).str.strip() == rep) & 
            (sales_rep_data[rep_branch_col].astype(str).str.strip() == branch)
        ]
        
        sales_b2b = rep_sales_df[rep_sales_df["Customer Type"] == "B2B"]["Total After Disc"].sum()
        sales_b2c = rep_sales_df[rep_sales_df["Customer Type"] == "B2C"]["Total After Disc"].sum()
        sales_total = sales_b2b + sales_b2c

        # Skip reps that have no target and no sales
        if target_total == 0 and target_b2b == 0 and target_b2c == 0 and sales_total == 0:
            continue

        rep_perf.append({
            "Branch": branch,
            "Sales Rep": rep,
            "B2B MTD Target": target_b2b,
            "Sales B2B": sales_b2b,
            "B2B %": (sales_b2b / target_b2b * 100) if target_b2b else None,
            "B2C MTD Target": target_b2c,
            "Sales B2C": sales_b2c,
            "B2C %": (sales_b2c / target_b2c * 100) if target_b2c else None,
            "Total Target": target_total,
            "Total Sales": sales_total,
            "Sales %": (sales_total / target_total * 100) if target_total else None,
        })

    rep_perf_df = pd.DataFrame(rep_perf)
    if rep_perf_df.empty:
        st.info("No sales rep targets available for selected filters.")
    else:
        totals = rep_perf_df[["B2B MTD Target", "Sales B2B", "B2C MTD Target", "Sales B2C", "Total Target", "Total Sales"]].sum(numeric_only=True)
        totals_row = {
            "Branch": "",
            "Sales Rep": "Total",
            "B2B MTD Target": totals["B2B MTD Target"],
            "Sales B2B": totals["Sales B2B"],
            "B2B %": (totals["Sales B2B"] / totals["B2B MTD Target"] * 100) if totals["B2B MTD Target"] else None,
            "B2C MTD Target": totals["B2C MTD Target"],
            "Sales B2C": totals["Sales B2C"],
            "B2C %": (totals["Sales B2C"] / totals["B2C MTD Target"] * 100) if totals["B2C MTD Target"] else None,
            "Total Target": totals["Total Target"],
            "Total Sales": totals["Total Sales"],
            "Sales %": (totals["Total Sales"] / totals["Total Target"] * 100) if totals["Total Target"] else None,
        }
        rep_perf_df = pd.concat([rep_perf_df, pd.DataFrame([totals_row])], ignore_index=True)

        rep_perf_df["B2B MTD Target"] = rep_perf_df["B2B MTD Target"].astype(float)
        rep_perf_df["Sales B2B"] = rep_perf_df["Sales B2B"].astype(float)
        rep_perf_df["B2C MTD Target"] = rep_perf_df["B2C MTD Target"].astype(float)
        rep_perf_df["Sales B2C"] = rep_perf_df["Sales B2C"].astype(float)
        rep_perf_df["Total Target"] = rep_perf_df["Total Target"].astype(float)
        rep_perf_df["Total Sales"] = rep_perf_df["Total Sales"].astype(float)

        styled_rep_perf = rep_perf_df.style.format({
            "B2B MTD Target": "{:,.0f}",
            "Sales B2B": "{:,.0f}",
            "B2B %": fmt_pct,
            "B2C MTD Target": "{:,.0f}",
            "Sales B2C": "{:,.0f}",
            "B2C %": fmt_pct,
            "Total Target": "{:,.0f}",
            "Total Sales": "{:,.0f}",
            "Sales %": fmt_pct,
            "Branch": "{}",
            "Sales Rep": "{}",
        }, na_rep="").apply(lambda col: col.map(pct_cell_style), subset=["B2B %", "B2C %", "Sales %"], axis=0)

        st.dataframe(styled_rep_perf, use_container_width=True)

# توجيه الصفحات
def get_first_name_from_email(email):
    local_part = email.split('@')[0]
    first_name = local_part.split('.')[0]
    return first_name

def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        first_name = get_first_name_from_email(st.session_state.user_email)
        st.sidebar.title(f"مرحباً {first_name}")
        if st.sidebar.button("تسجيل الخروج"):
            st.session_state.logged_in = False
            st.rerun()
        page = st.sidebar.radio("التنقل", ["الرئيسية", "الإعدادات"])
        if page == "الرئيسية":
            dashboard_page()
        else:
            settings_page()

if __name__ == "__main__":
    main()
