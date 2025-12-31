#!/usr/bin/env python3
"""
OpenHT Model Selector
========================
Interaktif model seçici - OpenRouter üzerinden en güncel modelleri listeler ve seçim yapmanızı sağlar.
"""

import os
import sys
from pathlib import Path

import httpx
import tomli

# Popüler ve güncel modeller listesi
FEATURED_MODELS = [
    # Anthropic Claude Serisi
    ("anthropic/claude-sonnet-4", "Claude Sonnet 4 - En güncel, dengeli performans"),
    ("anthropic/claude-opus-4", "Claude Opus 4 - En güçlü Claude modeli"),
    ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet - Hızlı ve yetenekli"),
    ("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku - En hızlı Claude"),
    # OpenAI GPT Serisi
    ("openai/gpt-4o", "GPT-4o - Multimodal, hızlı"),
    ("openai/gpt-4o-mini", "GPT-4o Mini - Ekonomik, hızlı"),
    ("openai/gpt-4-turbo", "GPT-4 Turbo - Güçlü reasoning"),
    ("openai/o1", "O1 - İleri düzey reasoning"),
    ("openai/o1-mini", "O1 Mini - Reasoning, ekonomik"),
    # Google Gemini Serisi
    ("google/gemini-2.5-pro-preview", "Gemini 2.5 Pro - Google'ın en güçlüsü"),
    ("google/gemini-2.0-flash", "Gemini 2.0 Flash - Hızlı ve verimli"),
    ("google/gemini-2.0-flash-thinking", "Gemini 2.0 Flash Thinking - Reasoning"),
    ("google/gemini-pro-1.5", "Gemini Pro 1.5 - 1M token context"),
    # DeepSeek
    ("deepseek/deepseek-r1", "DeepSeek R1 - Reasoning odaklı"),
    ("deepseek/deepseek-chat", "DeepSeek Chat - Genel amaçlı"),
    ("deepseek/deepseek-coder", "DeepSeek Coder - Kod yazımı"),
    # Mistral
    ("mistralai/mistral-large", "Mistral Large - En güçlü Mistral"),
    ("mistralai/mistral-medium", "Mistral Medium - Dengeli"),
    ("mistralai/codestral", "Codestral - Kod yazımı uzmanı"),
    # Meta Llama
    ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B - Açık kaynak lider"),
    ("meta-llama/llama-3.1-405b-instruct", "Llama 3.1 405B - En büyük açık model"),
    # Qwen
    ("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B - Güçlü Çince/İngilizce"),
    ("qwen/qwq-32b", "QwQ 32B - Reasoning odaklı"),
]


def print_header():
    """Başlık yazdır"""
    print("\n" + "=" * 60)
    print("🤖 OpenHT Model Seçici")
    print("=" * 60)
    print("\nOpenRouter üzerinden kullanılabilir modeller:\n")


def print_models():
    """Modelleri listele"""
    print_header()

    categories = {
        "anthropic": "🟣 Anthropic Claude",
        "openai": "🟢 OpenAI GPT",
        "google": "🔵 Google Gemini",
        "deepseek": "🔷 DeepSeek",
        "mistralai": "🟠 Mistral AI",
        "meta-llama": "🦙 Meta Llama",
        "qwen": "🔶 Qwen",
    }

    current_category = None
    idx = 1

    for model_id, description in FEATURED_MODELS:
        category = model_id.split("/")[0]

        if category != current_category:
            current_category = category
            print(f"\n{categories.get(category, category)}")
            print("-" * 40)

        print(f"  [{idx:2}] {model_id}")
        print(f"       └─ {description}")
        idx += 1

    print("\n" + "=" * 60)


def update_config(model_id: str, api_key: str = None):
    """Config dosyasını güncelle"""
    config_path = Path(__file__).parent / "config" / "config.toml"

    # Mevcut config'i oku
    with open(config_path, "r") as f:
        content = f.read()

    # Model güncelle
    import re

    content = re.sub(r'(\[llm\][^\[]*model\s*=\s*)"[^"]*"', f'\\1"{model_id}"', content)
    content = re.sub(
        r'(\[llm\.vision\][^\[]*model\s*=\s*)"[^"]*"', f'\\1"{model_id}"', content
    )

    # API key güncelle (eğer verilmişse)
    if api_key:
        content = re.sub(r'(api_key\s*=\s*)"[^"]*"', f'\\1"{api_key}"', content)

    # Dosyaya yaz
    with open(config_path, "w") as f:
        f.write(content)

    print(f"\n✅ Model güncellendi: {model_id}")
    if api_key:
        print("✅ API key güncellendi")
    print(f"📁 Config: {config_path}")


def get_current_config():
    """Mevcut config'i göster"""
    config_path = Path(__file__).parent / "config" / "config.toml"

    try:
        with open(config_path, "rb") as f:
            config = tomli.load(f)

        print("\n📋 Mevcut Ayarlar:")
        print("-" * 40)
        print(f"   Model: {config['llm'].get('model', 'N/A')}")
        print(f"   Base URL: {config['llm'].get('base_url', 'N/A')}")
        api_key = config["llm"].get("api_key", "N/A")
        if api_key and api_key != "YOUR_OPENROUTER_API_KEY":
            print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
        else:
            print(f"   API Key: ⚠️  Ayarlanmamış!")
        print("-" * 40)
    except Exception as e:
        print(f"⚠️  Config okunamadı: {e}")


def main():
    """Ana fonksiyon"""
    print_models()
    get_current_config()

    # Model seçimi
    print("\n🎯 Seçiminizi yapın:")
    print("   - Model numarası girin (1-{})".format(len(FEATURED_MODELS)))
    print("   - Veya doğrudan model ID yazın (örn: anthropic/claude-sonnet-4)")
    print("   - Çıkmak için 'q' yazın\n")

    choice = input("Seçiminiz: ").strip()

    if choice.lower() == "q":
        print("Çıkılıyor...")
        return

    # Numara mı yoksa model ID mi?
    model_id = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(FEATURED_MODELS):
            model_id = FEATURED_MODELS[idx][0]
        else:
            print("❌ Geçersiz numara!")
            return
    elif "/" in choice:
        model_id = choice
    else:
        print("❌ Geçersiz giriş!")
        return

    # API key kontrolü
    config_path = Path(__file__).parent / "config" / "config.toml"
    with open(config_path, "rb") as f:
        config = tomli.load(f)

    current_key = config["llm"].get("api_key", "")

    if current_key == "YOUR_OPENROUTER_API_KEY" or not current_key:
        print("\n🔑 OpenRouter API key gerekli!")
        print("   https://openrouter.ai/keys adresinden alabilirsiniz.")
        api_key = input("\nAPI Key: ").strip()
        if not api_key:
            print("❌ API key girilmedi!")
            return
    else:
        api_key = None
        change = (
            input("\n🔑 API key değiştirmek ister misiniz? (e/h): ").strip().lower()
        )
        if change == "e":
            api_key = input("Yeni API Key: ").strip()

    # Config'i güncelle
    update_config(model_id, api_key)

    print("\n🚀 OpenHT'yi başlatmak için:")
    print("   source .venv/bin/activate && python main.py")


if __name__ == "__main__":
    main()
