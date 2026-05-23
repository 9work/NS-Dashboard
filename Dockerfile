FROM python:3.9-slim

WORKDIR /app

# نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# فتح البورت الخاص بـ Streamlit
EXPOSE 8501

# أمر تشغيل التطبيق
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]