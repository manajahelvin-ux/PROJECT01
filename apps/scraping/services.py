"""
Scraping services — HTTP fetching, HTML parsing, JS rendering, robots.txt.
"""

import hashlib
import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from django.conf import settings

logger = logging.getLogger(__name__)

# --- User-Agent rotation list ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Domain rate limiting tracker
_domain_last_request = {}


def get_user_agent() -> str:
    """Get a rotated User-Agent string."""
    if settings.USER_AGENT_ROTATION:
        idx = int(time.time()) % len(USER_AGENTS)
        return USER_AGENTS[idx]
    return USER_AGENTS[0]


def validate_url_safety(url: str) -> tuple[bool, str]:
    """
    Anti-SSRF: Validate URL is safe to fetch.
    Blocks localhost, private IPs, cloud metadata endpoints.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL invalide"

    if parsed.scheme not in ("http", "https"):
        return False, "Seuls les protocoles HTTP/HTTPS sont autorisés"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL sans nom d'hôte"

    # Block localhost
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"):
        return False, "Accès aux adresses locales bloqué (anti-SSRF)"

    # Block cloud metadata
    if hostname == "169.254.169.254":
        return False, "Accès aux métadonnées cloud bloqué (anti-SSRF)"

    # Resolve DNS and check for private IPs
    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"Adresse IP privée/réservée détectée: {ip} (anti-SSRF)"
    except socket.gaierror:
        return False, f"Impossible de résoudre le nom d'hôte: {hostname}"

    return True, "OK"


def fetch_static(url: str, timeout: int = 30) -> dict:
    """
    Fetch a page via HTTP (static mode).
    Returns: {success, status_code, html, headers, error, url_final}
    """
    # Safety check
    safe, msg = validate_url_safety(url)
    if not safe:
        return {"success": False, "error": msg, "status_code": 0, "html": "", "headers": {}, "url_final": url}

    # Politeness: rate limiting per domain
    domain = urlparse(url).netloc
    _apply_rate_limit(domain)

    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, max_redirects=5) as client:
            response = client.get(url, headers=headers)

            # Check response size
            max_size = settings.MAX_RESPONSE_SIZE_KB * 1024
            if len(response.content) > max_size:
                return {
                    "success": False,
                    "error": f"Réponse trop volumineuse ({len(response.content)} bytes, max {max_size})",
                    "status_code": response.status_code,
                    "html": "",
                    "headers": dict(response.headers),
                    "url_final": str(response.url),
                }

            # Backoff on 429/5xx
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limited (429). Retry after delay.",
                    "status_code": 429,
                    "html": "",
                    "headers": dict(response.headers),
                    "url_final": str(response.url),
                }

            if response.status_code >= 500:
                return {
                    "success": False,
                    "error": f"Erreur serveur: {response.status_code}",
                    "status_code": response.status_code,
                    "html": "",
                    "headers": dict(response.headers),
                    "url_final": str(response.url),
                }

            html = response.text
            return {
                "success": True,
                "status_code": response.status_code,
                "html": html,
                "headers": dict(response.headers),
                "error": "",
                "url_final": str(response.url),
            }

    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout lors de la requête", "status_code": 0, "html": "", "headers": {}, "url_final": url}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Erreur de connexion: {str(e)}", "status_code": 0, "html": "", "headers": {}, "url_final": url}


def fetch_javascript(url: str, wait_selector: str = "", timeout_ms: int = 30000) -> dict:
    """
    Fetch a page with JavaScript rendering via Playwright.
    Returns same structure as fetch_static.
    """
    safe, msg = validate_url_safety(url)
    if not safe:
        return {"success": False, "error": msg, "status_code": 0, "html": "", "headers": {}, "url_final": url}

    if not settings.PLAYWRIGHT_ENABLED:
        return {"success": False, "error": "Playwright désactivé. Utilisez le mode statique.", "status_code": 0, "html": "", "headers": {}, "url_final": url}

    _apply_rate_limit(urlparse(url).netloc)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
            context = browser.new_context(
                user_agent=get_user_agent(),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")

            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)

            html = page.content()
            browser.close()

            return {
                "success": True,
                "status_code": 200,
                "html": html,
                "headers": {},
                "error": "",
                "url_final": url,
            }

    except ImportError:
        return {"success": False, "error": "Playwright non installé. Exécutez: playwright install chromium", "status_code": 0, "html": "", "headers": {}, "url_final": url}
    except Exception as e:
        return {"success": False, "error": f"Erreur Playwright: {str(e)}", "status_code": 0, "html": "", "headers": {}, "url_final": url}


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML into BeautifulSoup object."""
    return BeautifulSoup(html, "lxml")


def extract_with_selector(html: str, selector: str, method: str = "css", attribute: str = "") -> list[str]:
    """Extract data from HTML using CSS, XPath, or Regex selector."""
    soup = parse_html(html)
    results = []

    try:
        if method == "css":
            elements = soup.select(selector)
            for el in elements:
                if attribute:
                    results.append(el.get(attribute, ""))
                else:
                    results.append(el.get_text(strip=True))

        elif method == "xpath":
            from lxml import etree
            tree = etree.HTML(html)
            elements = tree.xpath(selector)
            for el in elements:
                if isinstance(el, str):
                    results.append(el.strip())
                elif attribute:
                    results.append(el.get(attribute, ""))
                else:
                    results.append(el.text_content().strip())

        elif method == "regex":
            pattern = re.compile(selector)
            matches = pattern.findall(html)
            for m in matches:
                if isinstance(m, tuple):
                    results.append(" ".join(m))
                else:
                    results.append(m.strip())

    except Exception as e:
        logger.error(f"Selector error ({method}: {selector}): {e}")

    return results


def check_robots_txt(url: str) -> dict:
    """Check if URL is allowed by robots.txt."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(robots_url, headers={"User-Agent": get_user_agent()})
            if response.status_code == 200:
                content = response.text
                path = parsed.path or "/"
                # Simple check: look for Disallow rules
                for line in content.split("\n"):
                    line = line.strip()
                    if line.lower().startswith("disallow:"):
                        disallowed_path = line.split(":", 1)[1].strip()
                        if path.startswith(disallowed_path):
                            return {"allowed": False, "robots_txt": content, "reason": f"Path {path} disallowed by robots.txt"}

                # Check crawl-delay
                crawl_delay = 2.0
                for line in content.split("\n"):
                    if line.lower().startswith("crawl-delay:"):
                        try:
                            crawl_delay = float(line.split(":")[1].strip())
                        except (ValueError, IndexError):
                            pass

                return {"allowed": True, "robots_txt": content, "crawl_delay": crawl_delay}
    except Exception:
        pass

    return {"allowed": True, "robots_txt": "", "crawl_delay": 2.0}


def _apply_rate_limit(domain: str):
    """Enforce minimum delay between requests to same domain."""
    now = time.time()
    delay = settings.DEFAULT_REQUEST_DELAY_SECONDS

    if domain in _domain_last_request:
        elapsed = now - _domain_last_request[domain]
        if elapsed < delay:
            time.sleep(delay - elapsed)

    _domain_last_request[domain] = time.time()
