#!/usr/bin/env python3
"""
VintedMandos Bot - Monitor de chollos de mandos de videoconsola en Vinted
========================================================================
Diseñado para ejecutarse como cron job en GitHub Actions (cada 5 minutos).
Cada ejecución escanea Vinted, envía alertas a Telegram y guarda el estado.

Autor: Hugo - ReventaMandos
Licencia: MIT
"""

import os
import sys
import json
import time
import random
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VintedMandos")

# ---------------------------------------------------------------------------
# Variables de entorno (configuradas en GitHub Actions Secrets)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
MAX_PRICE: float = float(os.getenv("MAX_PRICE", "23.00"))

# Archivos de persistencia (se mantienen entre ejecuciones con cache de GitHub)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
SEEN_FILE: Path = DATA_DIR / "seen_items.json"
SESSION_FILE: Path = DATA_DIR / "session.json"

# ---------------------------------------------------------------------------
# Búsquedas configuradas
# ---------------------------------------------------------------------------
SEARCH_QUERIES: list[dict] = [
    {"search": "mando ps5 dualsense", "title_keywords": ["ps5", "dualsense", "mando"]},
    {"search": "mando ps4 dualshock", "title_keywords": ["ps4", "dualshock", "mando"]},
    {"search": "mando nintendo switch", "title_keywords": ["switch", "joycon", "joy-con", "pro controller", "mando"]},
    {"search": "mando xbox", "title_keywords": ["xbox", "controller", "mando"]},
    {"search": "mando videoconsola", "title_keywords": ["mando", "controller", "drift", "piezas", "roto", "averiado", "fallo"]},
]

KEYWORDS: list[str] = [
    "mando", "controller", "drift", "piezas", "roto", "averiado",
    "fallo", "joycon", "joy-con", "ps5", "ps4", "xbox", "switch",
    "dualsense", "dualshock", "pro controller",
]

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def load_seen() -> set[str]:
    """Carga IDs ya procesados desde disco."""
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict) and "seen_ids" in data:
                    return set(data["seen_ids"])
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def save_seen(seen_ids: set[str]) -> None:
    """Guarda IDs procesados en disco (se mantiene entre ejecuciones con cache)."""
    ids_list = list(seen_ids)[-10000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"seen_ids": ids_list, "count": len(ids_list),
             "updated": datetime.now(timezone.utc).isoformat()},
            f, ensure_ascii=False, indent=2,
        )


def load_session() -> dict:
    """Carga la sesión de Vinted (cookies) desde disco."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Verificar que la sesión no sea vieja (>2 horas)
                ts = data.get("timestamp", 0)
                if time.time() - ts < 7200:
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_session(session_data: dict) -> None:
    """Guarda la sesión de Vinted en disco."""
    session_data["timestamp"] = time.time()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Sesión con Vinted
# ---------------------------------------------------------------------------

def create_session() -> requests.Session:
    """Crea una sesión HTTP con headers de navegador real."""
    try:
        session = requests.Session()
        ua = random.choice(USER_AGENTS)
        session.headers.update({
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.vinted.es",
            "Origin": "https://www.vinted.es",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        })
        return session
    except Exception as e:
        logger.error("Error creando sesión: %s", e)
        # Retornar sesión básica como fallback
        return requests.Session()


def init_vinted_session(session: requests.Session) -> bool:
    """Inicializa la sesión con Vinted obteniendo cookies y CSRF token."""
    try:
        logger.info("Inicializando sesión con Vinted...")
        resp = session.get("https://www.vinted.es", timeout=30, allow_redirects=True)
        resp.raise_for_status()

        # Buscar CSRF token
        csrf_token = None
        for name, val in session.cookies.items():
            if "csrf" in name.lower():
                csrf_token = val
                break

        if not csrf_token:
            match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', resp.text)
            if match:
                csrf_token = match.group(1)

        if not csrf_token:
            for name, val in session.cookies.items():
                if name.startswith("_vinted"):
                    csrf_token = val[:32]
                    break

        if csrf_token:
            session.headers["X-CSRF-Token"] = csrf_token
            logger.info("Sesión inicializada (CSRF obtenido)")
        else:
            logger.warning("CSRF no encontrado, se intentará sin él")

        return True
    except requests.RequestException as e:
        logger.error("Error al inicializar sesión: %s", e)
        return False
    except Exception as e:
        logger.error("Error inesperado al inicializar sesión: %s", e)
        return False


# ---------------------------------------------------------------------------
# Búsqueda en Vinted
# ---------------------------------------------------------------------------

def search_vinted(session: requests.Session, query: str) -> list[dict]:
    """Busca items en Vinted por texto y precio máximo."""
    params = {
        "search_text": query,
        "price_to": MAX_PRICE,
        "currency": "EUR",
        "page": 1,
        "per_page": 30,
        "order": "newest_first",
        "status_ids[]": [1, 2, 3, 6],
    }

    try:
        resp = session.get(
            "https://www.vinted.es/api/v2/catalog/items",
            params=params,
            timeout=30,
        )

        # Re-inicializar si sesión expirada
        if resp.status_code in (401, 403):
            logger.warning("Sesión expirada (HTTP %d), re-inicializando...", resp.status_code)
            init_vinted_session(session)
            resp = session.get(
                "https://www.vinted.es/api/v2/catalog/items",
                params=params,
                timeout=30,
            )

        if resp.status_code != 200:
            logger.warning("HTTP %d para '%s'", resp.status_code, query)

        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        logger.info("'%s': %d items", query, len(items))
        return items

    except requests.RequestException as e:
        logger.error("Error búsqueda '%s': %s", query, e)
        return []
    except json.JSONDecodeError as e:
        logger.error("Error JSON búsqueda '%s': %s", query, e)
        return []


# ---------------------------------------------------------------------------
# Filtrado
# ---------------------------------------------------------------------------

def matches_keywords(item: dict) -> bool:
    """Verifica si el item contiene palabras clave relevantes."""
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def is_valid_item(item: dict, seen_ids: set[str]) -> bool:
    """Valida si un item cumple todos los criterios."""
    item_id = str(item.get("id", ""))
    if item_id in seen_ids:
        return False

    try:
        price_str = str(item.get("price", "0")).replace("€", "").replace(",", ".").strip()
        price = float(price_str)
    except (ValueError, TypeError):
        return False

    if price > MAX_PRICE or price <= 0:
        return False

    return matches_keywords(item)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram_alert(item: dict) -> bool:
    """Envía alerta formateada a Telegram con botón inline."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Tokens de Telegram no configurados")
        return False

    item_id = item.get("id", "")
    title = item.get("title", "Sin título")
    price = item.get("price", "???")
    if isinstance(price, (int, float)):
        price = f"{price:.2f}"
    else:
        price = str(price).replace("€", "").strip()

    status = item.get("status", "No especificado")
    user = item.get("user", {})
    username = user.get("login", "Desconocido")
    num_reviews = user.get("feedback_reputation", 0)

    item_url = item.get("url", "")
    if not item_url:
        slug = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-"))
        slug = re.sub(r"-+", "-", slug).strip("-")
        item_url = f"https://www.vinted.es/{slug}-i{item_id}"

    description = item.get("description", "Sin descripción")
    if len(description) > 150:
        description = description[:147] + "..."

    # Escapar para MarkdownV2
    def esc(text):
        for c in r"_*[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    message = (
        f"🎮 *¡NUEVO CHOLLO EN VINTED\\!* 🎮\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Título:* {esc(title)}\n"
        f"💰 *Precio:* {esc(price)} €\n"
        f"🏷️ *Estado:* {esc(str(status))}\n"
        f"👤 *Vendedor:* {esc(username)} "
        f"\\({num_reviews} ⭐\\)\n"
        f"📝 *Descripción:* {esc(description)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [ABRIR EN VINTED]({item_url})"
    )

    inline_keyboard = {
        "inline_keyboard": [[{"text": "🛒 Comprar en Vinted", "url": item_url}]]
    }

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "MarkdownV2",
                "reply_markup": json.dumps(inline_keyboard),
            },
            timeout=15,
        )
        result = resp.json()
        if result.get("ok"):
            logger.info("✅ Alerta: %s (%s€)", title, price)
            return True
        else:
            logger.error("Telegram error: %s", result)
            return False
    except requests.RequestException as e:
        logger.error("Error Telegram: %s", e)
        return False


# ---------------------------------------------------------------------------
# Ejecución principal (una sola pasada — para GitHub Actions cron)
# ---------------------------------------------------------------------------

def run_once() -> None:
    """Ejecuta un solo escaneo completo. Diseñado para cron de GitHub Actions."""
    logger.info("=" * 50)
    logger.info("🚀 VintedMandos Bot — Escaneo único")
    logger.info("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")
        sys.exit(1)

    seen_ids = load_seen()
    logger.info("IDs conocidos: %d", len(seen_ids))

    # Crear sesión con Vinted
    session = create_session()
    try:
        session_ok = init_vinted_session(session)
    except Exception as e:
        logger.error("Error al inicializar sesión: %s", e)
        session_ok = False
    if not session_ok:
        logger.warning("No se pudo inicializar sesión con Vinted. Se reintentará en el próximo escaneo.")
        return  # Salir limpiamente, exit code 0

    new_items = 0

    for config in SEARCH_QUERIES:
        query = config["search"]
        logger.info("🔍 Buscando: '%s'", query)

        try:
            items = search_vinted(session, query)
        except Exception as e:
            logger.error("Error inesperado buscando '%s': %s", query, e)
            items = []

        for item in items:
            try:
                item_id = str(item.get("id", ""))
                if item_id in seen_ids:
                    continue

                if is_valid_item(item, seen_ids):
                    logger.info("🎯 Chollo: %s — %s€", item.get("title"), item.get("price"))
                    if send_telegram_alert(item):
                        new_items += 1

                seen_ids.add(item_id)
            except Exception as e:
                logger.error("Error procesando item: %s", e)

        # Pausa entre búsquedas
        time.sleep(random.uniform(2, 5))

    save_seen(seen_ids)
    logger.info("Escaneo completado | Nuevos: %d | Total conocidos: %d", new_items, len(seen_ids))


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        run_once()
        logger.info("✅ Escaneo finalizado correctamente")
    except SystemExit as e:
        if e.code != 0:
            logger.error("❌ Script terminó con código de error: %s", e.code)
        raise
    except KeyboardInterrupt:
        logger.info("⏹️ Interrumpido por el usuario")
    except Exception as e:
        logger.error("❌ Error fatal no capturado: %s", e, exc_info=True)
        sys.exit(1)
