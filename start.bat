@echo off
cd /d C:\Users\Admin\PycharmProjects\Server_pdf_local
python -m uvicorn main:app --host 0.0.0.0 --port 8000
