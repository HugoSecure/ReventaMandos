#!/usr/bin/env python3
"""
VintedMandos Bot - Monitor de chollos de mandos de videoconsola en Vinted
========================================================================
Escanea periódicamente Vinted en busca de mandos de PS5, PS4, Switch y Xbox
por debajo de un precio máximo configurado, y envía alertas instantáneas
a un canal o chat privado de Telegram con formato visual y botón inline.

Diseñado para ejecutarse 24/7 en la nube (Render, Railway, Fly.io, etc.).

Autor: Hugo - ReventaMandos
Licencia: MIT
"""

import os
import sys
import json
import time
import random
import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, quote_plus
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("VintedMandos")

# ---------------------------------------------------------------------------
# Carga de variables de entorno
# ---------------------------------------------------------------------------
load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
MAX_PRICE: float = float(os.getenv("MAX_PRICE", "23.00"))
MIN_INTERVAL: int = int(os.getenv("MIN_INTERVAL", "30"))
MAX_INTERVAL: int = int(os.getenv("MAX_INTERVAL", "60"))

# Puerto para el mini servidor HTTP (necesario para Render/Fly.io)
PORT: int = int(os.getenv("PORT", "8080"))

# Archivo local para persistir los IDs de publicaciones ya procesadas
SEEN_FILE: Path = Path("seen_items.json")

# ---------------------------------------------------------------------------
# Base de datos de búsquedas
# ---------------------------------------------------------------------------
SEARCH_QUERIES: list[dict] = [
    # PS5 DualSense
    {"search": "mando ps5 dualsense", "title_keywords": ["ps5", "dualsense", "mando"]},
    # PS4 DualShock 4
    {"search": "mando ps4 dualshock", "title_keywords": ["ps4", "dualshock", "mando"]},
    # Nintendo Switch
    {"search": "mando nintendo switch", "title_keywords": ["switch", "joycon", "joy-con", "pro controller", "mando"]},
    # Xbox
    {"search": "mando xbox", "title_keywords": ["xbox", "controller", "mando"]},
    # Búsqueda genérica de mandos baratos
    {"search": "mando videoconsola", "title_keywords": ["mando", "controller", "drift", "piezas", "roto", "averiado", "fallo"]},
]

# Palabras clave adicionales para filtrar por descripción/título
KEYWORDS: list[str] = [
    "mando", "controller", "drift", "piezas", "roto", "averiado",
    "fallo", "joycon", "joy-con", "ps5", "ps4", "xbox", "switch",
    "dualsense", "dualshock", "pro controller",
]

# User-Agents rotativos para simular tráfico de navegador real
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
]

# ---------------------------------------------------------------------------
# Mini servidor HTTP para mantener vivo el servicio en Render/Fly.io
# Render apaga los workers "free" tras 15 min sin actividad HTTP.
# Este servidor responde a pings de UptimeRobot / cron para evitarlo.
# ---------------------------------------------------------------------------

class HealthHandler(BaseHTTPRequestHandler):
    """Handler HTTP que responde con estado del bot."""

    def do_GET(self):
        """Responde a cualquier petición GET con el estado actual."""
        try:
            status = {
                "status": "ok",
                "service": "VintedMandos Bot",
                "uptime": time.time() - START_TIME,
                "scan_count": SCAN_COUNT,
                "seen_items": len(SEEN_IDS),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, indent=2).encode())
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        """Suprime los logs de peticiones HTTP para no llenar la consola."""
        pass


# Variables globales compartidas entre el hilo HTTP y el monitor
START_TIME = time.time()
SCAN_COUNT = 0
SEEN_IDS: set = set()


def start_health_server():
    """Inicia el servidor HTTP de salud en un hilo separado (daemon)."""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("🟢 Servidor de salud HTTP activo en puerto %d", PORT)
    return server


# ---------------------------------------------------------------------------
# Clase principal: VintedMonitor
# ---------------------------------------------------------------------------

class VintedMonitor:
    """
    Monitor que consulta la API web de Vinted periódicamente,
    filtra por precio y palabras clave, y envía alertas a Telegram.
    """

    # Base URL de la API interna de Vinted (España)
    VINTED_BASE_URL = "https://www.vinted.es"
    API_CATALOG_URL = f"{VINTED_BASE_URL}/api/v2/catalog/items"
    API_ITEM_URL = f"{VINTED_BASE_URL}/api/v2/items"

    def __init__(self):
        global SEEN_IDS

        # Sesión HTTP reutilizable con headers realistas
        self.session = requests.Session()
        self._rotate_ua()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.VINTED_BASE_URL,
            "Origin": self.VINTED_BASE_URL,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        })

        # Estado de la sesión Vinted (cookies, CSRF, etc.)
        self._csrf_token: Optional[str] = None
        self._session_cookies: dict = {}

        # Cargar IDs ya vistos desde disco
        self.seen_ids: set[str] = self._load_seen()
        SEEN_IDS = self.seen_ids  # Sincronizar con variable global

        # Contador de escaneos
        self.scan_count = 0

        logger.info("VintedMonitor inicializado | MAX_PRICE=%.2f€ | Intervalo: %d-%ds",
                     MAX_PRICE, MIN_INTERVAL, MAX_INTERVAL)
        logger.info("Publicaciones ya conocidas en memoria: %d", len(self.seen_ids))

    # -------------------------------------------------------------------
    # Gestión de cookies y sesión de Vinted
    # -------------------------------------------------------------------

    def _rotate_ua(self) -> None:
        """Selecciona un User-Agent aleatorio de la lista."""
        ua = random.choice(USER_AGENTS)
        self.session.headers["User-Agent"] = ua

    def _init_session(self) -> bool:
        """
        Inicializa la sesión con Vinted obteniendo cookies de sesión
        y el token CSRF necesario para las peticiones a la API.
        Retorna True si la sesión se inicializó correctamente.
        """
        try:
            logger.info("Inicializando sesión con Vinted...")
            self._rotate_ua()

            # 1) Obtener la página principal para las cookies de sesión
            resp = self.session.get(
                self.VINTED_BASE_URL,
                timeout=30,
                allow_redirects=True,
            )
            resp.raise_for_status()

            # 2) Buscar el CSRF token en las cookies o en la respuesta
            self._csrf_token = None

            # Intentar extraer CSRF de las cookies
            for cookie_name, cookie_val in self.session.cookies.items():
                if "csrf" in cookie_name.lower():
                    self._csrf_token = cookie_val
                    break

            # Si no se encontró en cookies, intentar de la respuesta HTML
            if not self._csrf_token:
                csrf_match = re.search(
                    r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
                    resp.text,
                )
                if csrf_match:
                    self._csrf_token = csrf_match.group(1)

            # Como último recurso, usar un valor de las cookies de sesión
            if not self._csrf_token:
                for name, val in self.session.cookies.items():
                    if name.startswith("_vinted"):
                        self._csrf_token = val[:32]
                        break

            # 3) Añadir headers de autenticación CSRF si se obtuvo
            if self._csrf_token:
                self.session.headers["X-CSRF-Token"] = self._csrf_token
                logger.info("Sesión inicializada correctamente (CSRF obtenido)")
            else:
                logger.warning("CSRF token no encontrado; se intentará sin él")

            logger.info("Cookies de sesión: %d obtenidas", len(self.session.cookies))
            return True

        except requests.RequestException as e:
            logger.error("Error al inicializar sesión con Vinted: %s", e)
            return False

    # -------------------------------------------------------------------
    # Persistencia de IDs vistos
    # -------------------------------------------------------------------

    def _load_seen(self) -> set[str]:
        """Carga los IDs previamente procesados desde el archivo JSON."""
        if SEEN_FILE.exists():
            try:
                with open(SEEN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
                    elif isinstance(data, dict) and "seen_ids" in data:
                        return set(data["seen_ids"])
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Error al leer %s: %s — Se creará uno nuevo", SEEN_FILE, e)
        return set()

    def _save_seen(self) -> None:
        """Persiste los IDs vistos en disco."""
        try:
            # Mantener solo los últimos 10.000 IDs para no crecer indefinidamente
            ids_list = list(self.seen_ids)[-10000:]
            with open(SEEN_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"seen_ids": ids_list, "count": len(ids_list),
                     "updated": datetime.now(timezone.utc).isoformat()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            # Actualizar variable global para el endpoint de salud
            SEEN_IDS = self.seen_ids
        except IOError as e:
            logger.error("Error al guardar %s: %s", SEEN_FILE, e)

    def mark_seen(self, item_id: str) -> None:
        """Marca un ID como visto y guarda en disco."""
        self.seen_ids.add(item_id)
        self._save_seen()

    # -------------------------------------------------------------------
    # Búsqueda en Vinted
    # -------------------------------------------------------------------

    def search_vinted(self, query: str, page: int = 1, per_page: int = 20) -> list[dict]:
        """
        Realiza una búsqueda en el catálogo de Vinted usando la API interna.
        Retorna una lista de items brutos (diccionarios JSON de la API).
        """
        params = {
            "search_text": query,
            "price_to": MAX_PRICE,
            "currency": "EUR",
            "page": page,
            "per_page": per_page,
            "order": "newest_first",
            "status_ids[]": [1, 2, 3, 6],
            "catalog_ids[]": [],
        }

        try:
            self._rotate_ua()

            resp = self.session.get(
                self.API_CATALOG_URL,
                params=params,
                timeout=30,
            )

            # Si recibe 401/403, re-inicializar sesión
            if resp.status_code in (401, 403):
                logger.warning("Sesión expirada (HTTP %d). Re-inicializando...", resp.status_code)
                self._init_session()
                resp = self.session.get(
                    self.API_CATALOG_URL,
                    params=params,
                    timeout=30,
                )

            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            logger.info("Búsqueda '%s': %d items encontrados (página %d)", query, len(items), page)
            return items

        except requests.RequestException as e:
            logger.error("Error en la búsqueda '%s': %s", query, e)
            return []
        except json.JSONDecodeError as e:
            logger.error("Error al decodificar respuesta JSON para '%s': %s", query, e)
            return []

    def get_item_details(self, item_id: str) -> Optional[dict]:
        """
        Obtiene los detalles completos de un item por su ID.
        """
        try:
            self._rotate_ua()
            resp = self.session.get(
                f"{self.API_ITEM_URL}/{item_id}",
                timeout=30,
            )
            if resp.status_code in (401, 403):
                self._init_session()
                resp = self.session.get(
                    f"{self.API_ITEM_URL}/{item_id}",
                    timeout=30,
                )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error("Error al obtener detalles del item %s: %s", item_id, e)
            return None

    # -------------------------------------------------------------------
    # Filtrado de items
    # -------------------------------------------------------------------

    def matches_keywords(self, item: dict) -> bool:
        """Verifica si un item coincide con las palabras clave de interés."""
        title = (item.get("title") or "").lower()
        description = (item.get("description") or "").lower()
        text = f"{title} {description}"
        return any(kw.lower() in text for kw in KEYWORDS)

    def is_valid_item(self, item: dict) -> bool:
        """
        Valida que un item cumple todos los criterios:
        - Precio <= MAX_PRICE
        - Contiene palabras clave relevantes
        - No ha sido visto previamente
        """
        # 1. Comprobar precio
        try:
            price_str = str(item.get("price", "0")).replace("€", "").replace(",", ".").strip()
            price = float(price_str)
        except (ValueError, TypeError):
            return False

        if price > MAX_PRICE or price <= 0:
            return False

        # 2. Comprobar palabras clave
        if not self.matches_keywords(item):
            return False

        # 3. Comprobar que no está en la lista de vistos
        item_id = str(item.get("id", ""))
        if item_id in self.seen_ids:
            return False

        return True

    # -------------------------------------------------------------------
    # Envío de mensajes a Telegram
    # -------------------------------------------------------------------

    def send_telegram_alert(self, item: dict) -> bool:
        """
        Envía un mensaje formateado a Telegram con los detalles del chollo.
        Incluye un botón inline con enlace directo a Vinted.
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.error("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")
            return False

        # Extraer datos del item
        item_id = item.get("id", "")
        title = item.get("title", "Sin título")
        price = item.get("price", "???")
        if isinstance(price, (int, float)):
            price = f"{price:.2f}"
        else:
            price = str(price).replace("€", "").strip()

        status = item.get("status", "No especificado")

        # Información del vendedor
        user = item.get("user", {})
        username = user.get("login", "Desconocido")
        num_reviews = user.get("feedback_reputation", 0)

        # URL del item
        item_url = item.get("url", "")
        if not item_url:
            slug = title.lower().replace(" ", "-")
            slug = re.sub(r"[^a-z0-9-]", "", slug)
            slug = re.sub(r"-+", "-", slug).strip("-")
            item_url = f"{self.VINTED_BASE_URL}/{slug}-i{item_id}"

        # Descripción (primeros 150 caracteres)
        description = item.get("description", "Sin descripción disponible")
        if len(description) > 150:
            description = description[:147] + "..."

        # --- Construir el mensaje con MarkdownV2 ---
        message = (
            f"🎮 *¡NUEVO CHOLLO EN VINTED\\!* 🎮\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Título:* {self._escape_md(title)}\n"
            f"💰 *Precio:* {self._escape_md(price)} €\n"
            f"🏷️ *Estado:* {self._escape_md(str(status))}\n"
            f"👤 *Vendedor:* {self._escape_md(username)} "
            f"\\({num_reviews} ⭐\\)\n"
            f"📝 *Descripción:* {self._escape_md(description)}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 [ABRIR EN VINTED]({item_url})"
        )

        # --- Keyboard inline con botón "Comprar en Vinted" ---
        inline_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🛒 Comprar en Vinted",
                        "url": item_url,
                    }
                ]
            ]
        }

        # --- Enviar el mensaje ---
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "MarkdownV2",
            "reply_markup": json.dumps(inline_keyboard),
            "disable_web_page_preview": False,
        }

        try:
            resp = requests.post(api_url, json=payload, timeout=15)
            resp.raise_for_status()
            result = resp.json()

            if result.get("ok"):
                logger.info("✅ Alerta enviada a Telegram: %s (%s€)", title, price)
                return True
            else:
                logger.error("Telegram respondió con error: %s", result)
                return False

        except requests.RequestException as e:
            logger.error("Error al enviar mensaje a Telegram: %s", e)
            return False

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escapa caracteres especiales para MarkdownV2 de Telegram."""
        text = str(text)
        # Caracteres que deben escaparse en MarkdownV2
        special_chars = r"_*[]()~`>#+-=|{}.!"
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    # -------------------------------------------------------------------
    # Bucle principal de monitorización
    # -------------------------------------------------------------------

    def run(self) -> None:
        """
        Bucle principal: escanea Vinted periódicamente y envía alertas.
        Se ejecuta indefinidamente con reconexión automática.
        """
        global SCAN_COUNT

        logger.info("=" * 60)
        logger.info("🚀 VintedMandos Bot iniciado")
        logger.info("=" * 60)

        # Inicializar sesión con Vinted (con reintentos)
        session_ok = False
        retry_count = 0
        while not session_ok:
            session_ok = self._init_session()
            if not session_ok:
                retry_count += 1
                wait = min(60 * retry_count, 300)  # Máximo 5 min
                logger.error("No se pudo inicializar sesión. Reintento #%d en %ds...", retry_count, wait)
                time.sleep(wait)

        consecutive_errors = 0

        while True:
            try:
                self.scan_count += 1
                SCAN_COUNT = self.scan_count
                logger.info("─── Escaneo #%d ───", self.scan_count)

                new_items_found = 0

                for search_config in SEARCH_QUERIES:
                    query = search_config["search"]
                    logger.info("🔍 Buscando: '%s'", query)

                    items = self.search_vinted(query, page=1, per_page=30)

                    if not items:
                        logger.info("   No se encontraron resultados para '%s'", query)
                        continue

                    for item in items:
                        item_id = str(item.get("id", ""))

                        # Saltar si ya fue procesado
                        if item_id in self.seen_ids:
                            continue

                        if self.is_valid_item(item):
                            logger.info(
                                "🎯 ¡Chollo encontrado! ID=%s | %s | %s€",
                                item_id,
                                item.get("title", "?"),
                                item.get("price", "?"),
                            )

                            # Obtener detalles completos si la descripción está vacía
                            if not item.get("description"):
                                details = self.get_item_details(item_id)
                                if details:
                                    item = details

                            # Enviar alerta a Telegram
                            if self.send_telegram_alert(item):
                                new_items_found += 1

                        # Marcar como visto
                        self.mark_seen(item_id)

                    # Pausa aleatoria entre búsquedas diferentes
                    pause = random.uniform(3, 8)
                    logger.info("   Pausa %.1fs antes de la siguiente búsqueda...", pause)
                    time.sleep(pause)

                consecutive_errors = 0  # Reset errores en escaneo exitoso

                logger.info(
                    "Escaneo #%d completado | Nuevos chollos: %d | Total conocidos: %d",
                    self.scan_count,
                    new_items_found,
                    len(self.seen_ids),
                )

            except Exception as e:
                consecutive_errors += 1
                logger.error("Error durante el escaneo: %s", e)

                # Si hay muchos errores seguidos, re-inicializar sesión
                if consecutive_errors >= 3:
                    logger.warning("Muchos errores consecutivos. Re-inicializando sesión Vinted...")
                    self._init_session()
                    consecutive_errors = 0

            # Intervalo aleatorio antes del siguiente escaneo
            interval = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
            logger.info("⏳ Próximo escaneo en %.0f segundos...", interval)
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    """Función principal: valida config, inicia servidor HTTP y el monitor."""
    # Validar configuración
    if not TELEGRAM_BOT_TOKEN:
        logger.error(
            "❌ TELEGRAM_BOT_TOKEN no está configurado.\n"
            "   Crea un archivo .env con tu token (ver .env.example)\n"
            "   O define la variable de entorno TELEGRAM_BOT_TOKEN."
        )
        sys.exit(1)

    if not TELEGRAM_CHAT_ID:
        logger.error(
            "❌ TELEGRAM_CHAT_ID no está configurado.\n"
            "   Añade tu chat ID al archivo .env\n"
            "   (ver tutorial en README.md para obtenerlo)."
        )
        sys.exit(1)

    logger.info("Configuración verificada ✓")
    logger.info("Token: ...%s", TELEGRAM_BOT_TOKEN[-8:])
    logger.info("Chat ID: %s", TELEGRAM_CHAT_ID)
    logger.info("Precio máximo: %.2f€", MAX_PRICE)

    # Iniciar servidor HTTP de salud (para mantener vivo en Render/Fly.io)
    start_health_server()

    # Iniciar el monitor
    monitor = VintedMonitor()

    try:
        monitor.run()
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot detenido por el usuario (Ctrl+C)")
        monitor._save_seen()
        logger.info("Estado guardado. ¡Hasta pronto!")


if __name__ == "__main__":
    main()
