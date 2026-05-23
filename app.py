import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os  # تم إضافة المكتبة للتحقق من مسارات الملفات المرفوعة
from auth import authenticate, load_users, add_user, update_user, delete_user, save_users
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
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "mtd_mode" not in st.session_state:
    st.session_state.mtd_mode = "Last sales date"
if "mtd_month_length" not in st.session_state:
    st.session_state.mtd_month_length = 0

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
    email = st.text_input("البريد الإلكتروني")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        user = authenticate(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.session_state.user_branches = user["branches"]
            st.session_state.is_admin = user["is_admin"]
            st.rerun()
        else:
            st.error("بيانات الدخول غير صحيحة")

# صفحة الإعدادات (للمدير فقط)
def settings_page():
    st.title("⚙️ الإعدادات - إدارة المستخدمين وتحميل الملفات")
    if not st.session_state.is_admin:
        st.warning("هذه الصفحة مخصصة للمديرين فقط.")
        return
    
    st.header("📂 تحديث ملفات البيانات")
    sales_file = st.file_uploader("رفع ملف المبيعات (Sales This Month.xlsx)", type=["xlsx"])
    target_file = st.file_uploader("رفع ملف الأهداف (Target This Month.xlsx)", type=["xlsx"])
    if st.button("تحميل ومعالجة"):
        if sales_file and target_file:
            # حفظ الملفات مؤقتاً ثم إعادة تحميل البيانات
            with open("temp_sales.xlsx", "wb") as f:
                f.write(sales_file.read())
            with open("temp_target.xlsx", "wb") as f:
                f.write(target_file.read())
            # مسح الكاش لتحميل البيانات الجديدة
            st.cache_resource.clear()
            st.success("تم رفع الملفات وتحديث البيانات بنجاح! انتقل الآن إلى الصفحة الرئيسية لعرض لوحة البيانات.")
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
    else:
        st.write("**Sales data range:** لا توجد بيانات تاريخ صالحة أو الملف غير متوفر")

    st.subheader("📆 إعدادات MTD")
    mtd_mode = st.radio(
        "MTD calculation basis",
        ["Last sales date", "Today"],
        index=["Last sales date", "Today"].index(st.session_state.mtd_mode) if st.session_state.mtd_mode in ["Last sales date", "Today"] else 0,
    )
    st.session_state.mtd_mode = mtd_mode
    month_length = st.session_state.mtd_month_length
    if mtd_mode == "Last sales date":
        default_month = month_length if month_length > 0 else 30
        month_length = st.number_input(
            "Month length to use for MTD",
            min_value=1,
            max_value=31,
            value=default_month,
            step=1,
            help="Set the effective month length when the last days are holidays or non-working.",
        )
        st.session_state.mtd_month_length = month_length
    else:
        st.session_state.mtd_month_length = month_length
    st.write("**Current MTD mode:**", mtd_mode)
    if mtd_mode == "Last sales date":
        st.write(f"**Manual month length:** {month_length} days")

    st.header("👥 إدارة المستخدمين")
    users = load_users()
    st.dataframe(pd.DataFrame(users).T)
    
    with st.expander("➕ إضافة مستخدم جديد"):
        new_email = st.text_input("البريد الإلكتروني", key="add_email")
        new_pass = st.text_input("كلمة المرور", type="password", key="add_password")
        new_branches = st.text_area("الفروع المسموحة (كل فرع في سطر جديد)", key="add_branches").split("\n")
        new_admin = st.checkbox("مدير؟", key="add_user_admin")
        if st.button("إضافة", key="btn_add_user"):
            if new_email and new_pass:
                cleaned_branches = [b.strip() for b in new_branches if b.strip()]
                add_user(new_email, new_pass, cleaned_branches, new_admin)
                st.success("تمت الإضافة بنجاح")
                st.rerun()
            else:
                st.error("يرجى ملء البريد الإلكتروني وكلمة المرور")
    
    with st.expander("✏️ تعديل مستخدم"):
        if users:
            edit_email = st.selectbox("اختر المستخدم", list(users.keys()), key="edit_select_user")
            edit_pass = st.text_input("كلمة مرور جديدة (اتركه فارغاً إذا لم ترغب في التغيير)", type="password", key="edit_password")
            current_branches = users[edit_email].get("branches", [])
            edit_branches = st.text_area("الفروع المسموحة (كل فرع في سطر جديد)", value="\n".join(current_branches), key="edit_branches")
            current_admin = users[edit_email].get("is_admin", False)
            edit_admin = st.checkbox("مدير؟", value=current_admin, key="edit_user_admin")
            if st.button("تحديث", key="btn_update_user"):
                cleaned_edit_branches = [b.strip() for b in edit_branches.split("\n") if b.strip()]
                update_user(edit_email, edit_pass if edit_pass else None, cleaned_edit_branches, edit_admin)
                st.success("تم التحديث بنجاح")
                st.rerun()
        else:
            st.info("لا يوجد مستخدمين مسجلين لتعديلهم.")
    
    with st.expander("🗑️ حذف مستخدم"):
        if users:
            del_email = st.selectbox("اختر مستخدم للحذف", list(users.keys()), key="del_select_user")
            if st.button("حذف", key="btn_delete_user"):
                delete_user(del_email)
                st.success("تم الحذف بنجاح")
                st.rerun()
        else:
            st.info("لا يوجد مستخدمين مسجلين لحذفهم.")

# واجهة لوحة المعلومات الرئيسية
def dashboard_page():
    st.title("📊 لوحة المعلومات الرئيسية")
    
    try:
        sales_df, branch_target, rep_target = load_all_data()
    except Exception as e:
        st.error("لم يتم العثور على ملفات البيانات في المجلد، أو أن هناك مشكلة توافق في الملفات المرفوعة. يرجى رفع الملفات الصحيحة من صفحة الإعدادات.")
        return
    
# اختيار مصدر الفرع: الفرع الأصلي أم الفرع حسب مندوب المبيعات
    branch_source = st.radio(
        "مصدر الفرع",
        ["الفرع الأصلي", "الفرع حسب المندوب"],
        horizontal=True,
    )
    if branch_source == "الفرع الأصلي":
        branch_column = "Branch"
        brand_column = "Brand"
    else:
        branch_column = "Branch based on sales reps"
        brand_column = "Brand based on sales reps"

    # فلتر الفروع حسب صلاحية المستخدم
    allowed_branches = st.session_state.user_branches
    if st.session_state.is_admin or not allowed_branches:
        allowed_branches = list(sales_df[branch_column].dropna().unique())

    # فلتر العلامة التجارية ونوع العميل
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        brand_options = ["الكل"] + sorted(sales_df[brand_column].dropna().unique())
        brand_filter = st.selectbox("العلامة التجارية", brand_options)
    with col2:
        # حصر خيارات الفروع حسب العلامة التجارية المختارة ومع مراعاة صلاحيات المستخدم
        if brand_filter == "الكل":
            branches_for_brand = list(sales_df[branch_column].dropna().unique())
        else:
            branches_for_brand = list(sales_df[sales_df[brand_column] == brand_filter][branch_column].dropna().unique())
        if st.session_state.is_admin or not st.session_state.user_branches:
            branch_options = sorted(branches_for_brand)
        else:
            branch_options = sorted([b for b in allowed_branches if b in branches_for_brand])
        if not branch_options:
            st.info("لا توجد فروع مطابقة للعلامة التجارية والصلاحيات.")
        # استخدم droplist (selectbox) بدلاً من multiselect لعرض فرع واحد أو الكل
        branch_choice_options = ["الكل"] + branch_options
        branch_choice = st.selectbox("الفرع", branch_choice_options)
    with col3:
        cust_filter = st.selectbox("نوع العميل", ["الكل", "B2B", "B2C"])
    with col4:
        st.write(" ")
        st.write(" ")
        st.caption(f"تصفية بـ: {branch_source}")

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
        label_text = [f"{p:.1f}%\n{v:,.0f}" for p, v in zip(cust_percent, cust_sales.values)]
        fig_cust = px.bar(
            x=cust_sales.index,
            y=cust_sales.values,
            color=cust_sales.index,
            color_discrete_map={"B2B": "#1f77b4", "B2C": "#ff7f0e"},
            text=label_text,
            labels={"x": "Customer Type", "y": "Sales Amount"},
            title="Sales by Customer Type",
        )
        fig_cust.update_traces(textposition="outside", marker_line_width=0, textfont=dict(size=12))
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
        try:
            v = float(val)
        except Exception:
            return ""
        if v < 70:
            return "color:white; background-color:#d9534f"
        elif v < 90:
            return "color:black; background-color:#f0ad4e"
        else:
            return "color:black; background-color:#5cb85c"

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
            "B2B %": (sales_b2b / target_b2b * 100) if target_b2b else 0,
            "B2C MTD Target": target_b2c,
            "Sales B2C": sales_b2c,
            "B2C %": (sales_b2c / target_b2c * 100) if target_b2c else 0,
            "Total Target": target_total,
            "Total Sales": sales_total,
            "Sales %": (sales_total / target_total * 100) if target_total else 0,
        })

    branch_perf_df = pd.DataFrame(branch_perf)
    if branch_perf_df.empty:
        st.info("No branch targets available for selected filters.")
    else:
        totals = branch_perf_df[["B2B MTD Target", "Sales B2B", "B2C MTD Target", "Sales B2C", "Total Target", "Total Sales"]].sum(numeric_only=True)
        totals["B2B %"] = (totals["Sales B2B"] / totals["B2B MTD Target"] * 100) if totals["B2B MTD Target"] else 0
        totals["B2C %"] = (totals["Sales B2C"] / totals["B2C MTD Target"] * 100) if totals["B2C MTD Target"] else 0
        totals["Sales %"] = (totals["Total Sales"] / totals["Total Target"] * 100) if totals["Total Target"] else 0
        totals_row = {
            "Branch": "Total",
            "B2B MTD Target": totals["B2B MTD Target"],
            "Sales B2B": totals["Sales B2B"],
            "B2B %": totals["B2B %"],
            "B2C MTD Target": totals["B2C MTD Target"],
            "Sales B2C": totals["Sales B2C"],
            "B2C %": totals["B2C %"],
            "Total Target": totals["Total Target"],
            "Total Sales": totals["Total Sales"],
            "Sales %": totals["Sales %"],
        }
        branch_perf_df = pd.concat([branch_perf_df, pd.DataFrame([totals_row])], ignore_index=True)

        branch_perf_df = branch_perf_df.fillna(0)
        branch_perf_df = branch_perf_df.astype({
            "B2B MTD Target": float,
            "Sales B2B": float,
            "B2B %": float,
            "B2C MTD Target": float,
            "Sales B2C": float,
            "B2C %": float,
            "Total Target": float,
            "Total Sales": float,
            "Sales %": float,
        })

        styled_branch_perf = branch_perf_df.style.format({
            "B2B MTD Target": "{:,.0f}",
            "Sales B2B": "{:,.0f}",
            "B2B %": "{:.1f}%",
            "B2C MTD Target": "{:,.0f}",
            "Sales B2C": "{:,.0f}",
            "B2C %": "{:.1f}%",
            "Total Target": "{:,.0f}",
            "Total Sales": "{:,.0f}",
            "Sales %": "{:.1f}%",
        }).apply(lambda col: col.map(pct_cell_style), subset=["B2B %", "B2C %", "Sales %"], axis=0)

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
        selected_rep_branches = sales_df[rep_branch_col].dropna().unique().tolist()
    else:
        # If the current branch_choice exists in rep-branch values, use it directly.
        if branch_choice in sales_df[rep_branch_col].dropna().unique():
            selected_rep_branches = [branch_choice]
        else:
            # Otherwise map original branch selection to rep-based branches present in the data
            selected_rep_branches = sales_df[sales_df["Branch"] == branch_choice][rep_branch_col].dropna().unique().tolist()

    # Build sales data for reps using rep-based branch mapping, include returns for net calculation
    sales_rep_data = sales_df[sales_df[rep_branch_col].isin(selected_rep_branches) & sales_df["Sales Type"].isin(["Sales", "Return"])].copy()
    # Apply customer-type filter if set
    if cust_filter and cust_filter != "الكل":
        sales_rep_data = sales_rep_data[sales_rep_data["Customer Type"] == cust_filter]
    # Apply brand filter using rep-based brand column
    if brand_filter and brand_filter != "الكل":
        sales_rep_data = sales_rep_data[sales_rep_data[rep_brand_col] == brand_filter]

    sales_reps = sales_rep_data["Sales Person"].dropna().unique()
    if isinstance(rep_target, pd.DataFrame) and "Sales Rep" in rep_target.columns:
        target_reps = rep_target[rep_target["Sales Rep"].isin(sales_reps)]["Sales Rep"].dropna().unique()
    else:
        target_reps = sales_reps

    for rep in target_reps:
        rep_row = rep_target[rep_target["Sales Rep"] == rep]
        if rep_row.empty:
            continue
        target_b2b = float(rep_row[col_r_b2b].values[0]) * factor if col_r_b2b else 0
        target_b2c = float(rep_row[col_r_b2c].values[0]) * factor if col_r_b2c else 0
        target_total = float(rep_row[col_r_total].values[0]) * factor if col_r_total else 0
        if target_total == 0 and target_b2b == 0 and target_b2c == 0:
            continue

        sales_b2b = sales_rep_data[(sales_rep_data["Sales Person"] == rep) & (sales_rep_data["Customer Type"] == "B2B")]["Total After Disc"].sum()
        sales_b2c = sales_rep_data[(sales_rep_data["Sales Person"] == rep) & (sales_rep_data["Customer Type"] == "B2C")]["Total After Disc"].sum()
        sales_total = sales_b2b + sales_b2c
        rep_perf.append({
            "Sales Rep": rep,
            "B2B MTD Target": target_b2b,
            "Sales B2B": sales_b2b,
            "B2B %": (sales_b2b / target_b2b * 100) if target_b2b else 0,
            "B2C MTD Target": target_b2c,
            "Sales B2C": sales_b2c,
            "B2C %": (sales_b2c / target_b2c * 100) if target_b2c else 0,
            "Total Target": target_total,
            "Total Sales": sales_total,
            "Sales %": (sales_total / target_total * 100) if target_total else 0,
        })

    rep_perf_df = pd.DataFrame(rep_perf)
    if rep_perf_df.empty:
        st.info("No sales rep targets available for selected filters.")
    else:
        totals = rep_perf_df[["B2B MTD Target", "Sales B2B", "B2C MTD Target", "Sales B2C", "Total Target", "Total Sales"]].sum(numeric_only=True)
        totals["B2B %"] = (totals["Sales B2B"] / totals["B2B MTD Target"] * 100) if totals["B2B MTD Target"] else 0
        totals["B2C %"] = (totals["Sales B2C"] / totals["B2C MTD Target"] * 100) if totals["B2C MTD Target"] else 0
        totals["Sales %"] = (totals["Total Sales"] / totals["Total Target"] * 100) if totals["Total Target"] else 0
        totals_row = {
            "Sales Rep": "Total",
            "B2B MTD Target": totals["B2B MTD Target"],
            "Sales B2B": totals["Sales B2B"],
            "B2B %": totals["B2B %"],
            "B2C MTD Target": totals["B2C MTD Target"],
            "Sales B2C": totals["Sales B2C"],
            "B2C %": totals["B2C %"],
            "Total Target": totals["Total Target"],
            "Total Sales": totals["Total Sales"],
            "Sales %": totals["Sales %"],
        }
        rep_perf_df = pd.concat([rep_perf_df, pd.DataFrame([totals_row])], ignore_index=True)

        rep_perf_df = rep_perf_df.fillna(0)
        rep_perf_df = rep_perf_df.astype({
            "B2B MTD Target": float,
            "Sales B2B": float,
            "B2B %": float,
            "B2C MTD Target": float,
            "Sales B2C": float,
            "B2C %": float,
            "Total Target": float,
            "Total Sales": float,
            "Sales %": float,
        })

        styled_rep_perf = rep_perf_df.style.format({
            "B2B MTD Target": "{:,.0f}",
            "Sales B2B": "{:,.0f}",
            "B2B %": "{:.1f}%",
            "B2C MTD Target": "{:,.0f}",
            "Sales B2C": "{:,.0f}",
            "B2C %": "{:.1f}%",
            "Total Target": "{:,.0f}",
            "Total Sales": "{:,.0f}",
            "Sales %": "{:.1f}%",
        }).apply(lambda col: col.map(pct_cell_style), subset=["B2B %", "B2C %", "Sales %"], axis=0)

        st.dataframe(styled_rep_perf, use_container_width=True)

# توجيه الصفحات
def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        st.sidebar.title(f"مرحباً {st.session_state.user_email}")
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