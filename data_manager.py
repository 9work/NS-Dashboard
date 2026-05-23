import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ------------------- قراءة وتنظيف البيانات -------------------
def load_sales_data(file_path):
    # محاولة قراءة الشيت "Sales Final" أو الشيت الأول تلقائياً إذا لم يجد الاسم
    try:
        df = pd.read_excel(file_path, sheet_name="Sales Final")
    except Exception:
        try:
            df = pd.read_excel(file_path, sheet_name="Sales")
        except Exception:
            df = pd.read_excel(file_path, sheet_name=0) # قراءة أول شيت في الملف مهما كان اسمه
            
    # توحيد أسماء الأعمدة (إزالة المسافات وتحويلها لنصوص)
    df.columns = df.columns.astype(str).str.strip()
    
    # تحويل التاريخ إلى datetime بشكل آمن
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        # البحث عن أي عمود يحتوي على كلمة تاريخ
        date_cols = [c for c in df.columns if "date" in c.lower() or "تاريخ" in c]
        if date_cols:
            df["Date"] = pd.to_datetime(df[date_cols[0]], errors="coerce")
            df.rename(columns={date_cols[0]: "Date"}, inplace=True)
            
    # تصفية الشهر الحالي بأكمله لضمان عدم حدوث جدول فارغ بسبب الساعات
    today = datetime.today()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # تصفية حتى نهاية الشهر الحالي بالكامل لتجنب مشاكل فروق التوقيت اليومية
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    
    df = df[(df["Date"] >= start_of_month) & (df["Date"] <= end_of_month)]
    
    # معالجة مرنة لعمود (Sales Type) بالرمز # أو بدونه
    sales_type_col = "Sales Type #" if "Sales Type #" in df.columns else "Sales Type"
    if sales_type_col in df.columns:
        df["Sales Type"] = df[sales_type_col].astype(str).str.strip()
    else:
        df["Sales Type"] = "Sales" # قيمة افتراضية لحماية الكود من الانهيار
        
    # معالجة مرنة لعمود (Customer Type) بالرمز # أو بدونه
    cust_type_col = "Customer Type #" if "Customer Type #" in df.columns else "Customer Type"
    if cust_type_col in df.columns:
        df["Customer Type"] = df[cust_type_col].astype(str).str.strip()
    else:
        df["Customer Type"] = "B2C"

    # معالجة مرنة لعمود الكمية (Qty)
    qty_col = "Qty #" if "Qty #" in df.columns else ("Qty" if "Qty" in df.columns else "Quantity")
    if qty_col in df.columns:
        df["Qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0)
    else:
        df["Qty"] = 0

    # معالجة مرنة لاسم الفاتورة
    inv_col = "Invoice No" if "Invoice No" in df.columns else ("InvoiceNo" if "InvoiceNo" in df.columns else "Invoice No.")
    if inv_col in df.columns and inv_col != "Invoice No":
        df.rename(columns={inv_col: "Invoice No"}, inplace=True)

    # تحويل بقية الأعمدة المالية والأرقام بشكل آمن لمنع الـ NaN
    df["Total After Disc"] = pd.to_numeric(df.get("Total After Disc", 0), errors="coerce").fillna(0)
    df["Disc"] = pd.to_numeric(df.get("Disc", 0), errors="coerce").fillna(0)
    df["Discount%"] = pd.to_numeric(df.get("Discount%", 0), errors="coerce").fillna(0)
    
    # إنشاء عمود المبلغ الصافي للمبيعات
    df["NetSales"] = df.apply(lambda row: row["Total After Disc"] if row["Sales Type"] == "Sales" else -row["Total After Disc"], axis=1)
    return df

def load_target_data(file_path):
    # تحميل أهداف الفروع بشكل مرن (الشيت اسمه Branch أو أول شيت)
    try:
        branch_target = pd.read_excel(file_path, sheet_name="Branch")
    except Exception:
        branch_target = pd.read_excel(file_path, sheet_name=0)
    branch_target.columns = branch_target.columns.astype(str).str.strip()
    
    # تحميل أهداف مندوبي المبيعات بشكل مرن (الشيت اسمه Sales Rep أو ثاني شيت)
    try:
        rep_target = pd.read_excel(file_path, sheet_name="Sales Rep")
    except Exception:
        try:
            rep_target = pd.read_excel(file_path, sheet_name=1)
        except Exception:
            rep_target = branch_target.copy() # حماية في حال عدم وجود شيت ثانٍ
            
    rep_target.columns = rep_target.columns.astype(str).str.strip()
    return branch_target, rep_target

# ------------------- حساب MTD للهدف -------------------
def mtd_factor():
    today = datetime.today()
    days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days_in_month = days_in_month.day
    elapsed = today.day
    return elapsed / days_in_month if days_in_month > 0 else 1

def compute_mtd_target(target_df, target_col, branch_col="Branch"):
    factor = mtd_factor()
    target_df = target_df.copy()
    if target_col in target_df.columns:
        target_df["MTD_Target"] = target_df[target_col] * factor
    else:
        target_df["MTD_Target"] = 0
    return target_df.set_index(branch_col)["MTD_Target"]

# ------------------- حساب مؤشرات البطاقات الرئيسية -------------------
def compute_kpis(sales_df, branch_target_df, selected_branches, customer_type=None, brand_filter=None, mtd_factor_value=None, branch_col="Branch", brand_col="Brand"):
    if sales_df.empty:
        return {k: 0 for k in ["Sales Amount", "Target Sales", "Sales Ach%", "Quantity", "Target Quantity", "Qty Ach%", "Invoices", "Target Invoices", "Invoices Ach%", "ATV", "Target ATV", "ATV Ach%", "Return", "Return Ratio", "Customers", "Discount", "Discount Ratio"]}

    # تصفية حسب الفروع المسموحة
    sales_filtered = sales_df[sales_df[branch_col].isin(selected_branches)]
    if customer_type and customer_type != "الكل":
        sales_filtered = sales_filtered[sales_filtered["Customer Type"] == customer_type]
    if brand_filter and brand_filter != "الكل" and brand_col in sales_filtered.columns:
        sales_filtered = sales_filtered[sales_filtered[brand_col] == brand_filter]
    
    # فصل المبيعات عن المرتجعات
    sales_amount = sales_filtered[sales_filtered["Sales Type"] == "Sales"]["Total After Disc"].sum()
    return_amount = sales_filtered[sales_filtered["Sales Type"] == "Return"]["Total After Disc"].sum()
    quantity = sales_filtered[sales_filtered["Sales Type"] == "Sales"]["Qty"].sum()
    
    invoices = sales_filtered[sales_filtered["Sales Type"] == "Sales"]["Invoice No"].nunique() if "Invoice No" in sales_filtered.columns else 0
    unique_customers = sales_filtered[sales_filtered["Sales Type"] == "Sales"]["Customer Name"].nunique() if "Customer Name" in sales_filtered.columns else 0
    discount = sales_filtered[sales_filtered["Sales Type"] == "Sales"]["Disc"].sum()
    
    gross_sales_before_discount = sales_amount + discount
    discount_ratio = discount / gross_sales_before_discount if gross_sales_before_discount else 0
    return_ratio = return_amount / sales_amount if sales_amount else 0
    atv = sales_amount / invoices if invoices else 0
    
    # حساب الأهداف مع مراعاة التصفية حسب نوع العميل والفرع
    factor = mtd_factor() if mtd_factor_value is None else mtd_factor_value
    target_sales = 0
    target_qty = 0
    target_invoices = 0
    
    if "Branch" in branch_target_df.columns:
        target_branch_data = branch_target_df[branch_target_df["Branch"].isin(selected_branches)]
        if brand_filter and brand_filter != "الكل" and "Brand" in target_branch_data.columns:
            target_branch_data = target_branch_data[target_branch_data["Brand"] == brand_filter]

        # التحقق الآمن من أسماء أعمدة الأهداف وحسابها
        col_s_b2b = "Sales Target | B2B" if "Sales Target | B2B" in branch_target_df.columns else "Sales Target B2B"
        col_q_b2b = "Quantity Target | B2B" if "Quantity Target | B2B" in branch_target_df.columns else "Quantity Target B2B"
        col_i_b2b = "Invoices Target | B2B" if "Invoices Target | B2B" in branch_target_df.columns else "Invoices Target B2B"
        
        col_s_b2c = "Sales Target | B2C" if "Sales Target | B2C" in branch_target_df.columns else "Sales Target B2C"
        col_q_b2c = "Quantity Target | B2C" if "Quantity Target | B2C" in branch_target_df.columns else "Quantity Target B2C"
        col_i_b2c = "Invoices Target | B2C" if "Invoices Target | B2C" in branch_target_df.columns else "Invoices Target B2C"

        if (customer_type == "B2B" or not customer_type or customer_type == "الكل"):
            target_sales += (target_branch_data[col_s_b2b].sum() if col_s_b2b in target_branch_data.columns else 0) * factor
            target_qty += (target_branch_data[col_q_b2b].sum() if col_q_b2b in target_branch_data.columns else 0) * factor
            target_invoices += (target_branch_data[col_i_b2b].sum() if col_i_b2b in target_branch_data.columns else 0) * factor
        if (customer_type == "B2C" or not customer_type or customer_type == "الكل"):
            target_sales += (target_branch_data[col_s_b2c].sum() if col_s_b2c in target_branch_data.columns else 0) * factor
            target_qty += (target_branch_data[col_q_b2c].sum() if col_q_b2c in target_branch_data.columns else 0) * factor
            target_invoices += (target_branch_data[col_i_b2c].sum() if col_i_b2c in target_branch_data.columns else 0) * factor

    target_atv = target_sales / target_invoices if target_invoices else 0

    return {
        "Sales Amount": sales_amount,
        "Target Sales": target_sales,
        "Sales Ach%": (sales_amount / target_sales * 100) if target_sales else 0,
        "Quantity": quantity,
        "Target Quantity": target_qty,
        "Qty Ach%": (quantity / target_qty * 100) if target_qty else 0,
        "Invoices": invoices,
        "Target Invoices": target_invoices,
        "Invoices Ach%": (invoices / target_invoices * 100) if target_invoices else 0,
        "ATV": atv,
        "Target ATV": target_atv,
        "ATV Ach%": (atv / target_atv * 100) if target_atv else 0,
        "Return": return_amount,
        "Return Ratio": return_ratio,
        "Customers": unique_customers,
        "Discount": discount,
        "Discount Ratio": discount_ratio
    }
