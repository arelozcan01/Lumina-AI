@echo off
chcp 65001 >nul
title Lumina AI Engine - Baslatici
color 0b

echo ============================================================
echo               LUMINA AI ENGINE v2.0
echo       Duygusal, Zeki, Coklu Ajan Destekli Yapay Zeka
echo ============================================================
echo.
echo [1/2] Lumina AI Backend Sunucusu Baslatiliyor...
echo       Adres: http://127.0.0.1:8000
echo.

start "" "index.html"

echo [2/2] Arayuz acildi. Sunucu loglari asagidadir:
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

pause
