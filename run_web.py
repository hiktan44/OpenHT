#!/usr/bin/env python3
"""
OpenHT Web UI - Sunucu Başlatma Scripti
"""
import asyncio
import os
import sys

import uvicorn

# Proje kök dizinini sys.path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    """Web sunucusunu başlat"""
    print("\n" + "=" * 50)
    print("⚡ OpenHT Web UI")
    print("=" * 50)
    print("\n🚀 Sunucu başlatılıyor...")
    print("📍 http://localhost:8080 adresini ziyaret edin")
    print("\n💡 Durdurmak için Ctrl+C tuşlarına basın\n")

    # Uvicorn ile sunucuyu başlat
    uvicorn.run("web.api:app", host="0.0.0.0", port=8080, reload=True, log_level="info")


if __name__ == "__main__":
    main()
