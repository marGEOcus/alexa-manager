"""Amazon-Reverse-Proxy fuer den Browser-Login (1:1 nach alexa-cookie2/alexa-mcp).

Der Nutzer laedt die echte Amazon-Seite ueber diesen Proxy (im Add-on
eingebettet unter /proxy/<sess>/<host>/...) und loggt sich dort ganz
normal ein - inklusive 2FA aus der Authenticator-App. Der Proxy:

* injiziert selbst erzeugte Cookies (frc, map-md) und ein PKCE-Paar,
* startet den Login auf www.amazon.com als OIDC device-auth-Flow
  (openid.oa2.* mit client_id=device:<deviceId>),
* schreibt alle Amazon-URLs in Responses/Redirects auf die
  Proxy-URLs um (und beim Weiterreichen zurueck),
* sammelt alle Cookies aus Requests + Responses,
* erkennt den Erfolg am Redirect auf /ap/maplanding?openid.oa2.authorization_code=...

Das Ergebnis (Login-Cookies + authorization_code + PKCE-Verifier +
deviceId) wird an alexa_client.finalize_proxy_login() uebergaben, die
damit die Geraete-Registrierung (POST api.amazon.com/auth/register)
ausfuehrt und daraus den Refresh-Token ableitet.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlparse

# Hosts, die durch den Proxy laufen (alexa-cookie2: amazon.com + alexa.amazon.com
# + www.amazon.com; .de-Varianten zusaezlich erlaubt, weil Amazon dorthin umleiten kann)
PROXY_HOSTS = (
    "www.amazon.com",
    "alexa.amazon.com",
    "amazon.com",
    "www.amazon.de",
    "alexa.amazon.de",
    "amazon.de",
)

BASE_AMAZON = "amazon.com"  # Base-Seite fuer den OIDC-Flow (wie alexa-mcp-Default)
APP_VERSION = "2.2.651540.0"
API_USER_AGENT = f"AmazonWebView/Amazon Alexa/{APP_VERSION}/iOS/18.3.1/iPhone"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
)
DEVICE_TYPE = "A2IVLV5VM2W81"
DEVICE_APP_NAME = "Alexa Manager"
# hex("A2IVLV5VM2W81") wie in alexa-cookie2
DEVICE_ID_SUFFIX = "23413249564c5635564d32573831"

# Nur diese Cookie-Namen tauchen in der finalen Login-Cookie-String ein
AMAZON_COOKIE_RE = re.compile(
    r"^(session-id|session-id-time|session-token|ubid-.+|lc-.+|x-.+|at-.+|"
    r"sess-at-.+|frc|map-md|csrf|sid|csm-hit|i18n-prefs|sp-cdn|skin)$"
)

# Assets: kein Body-Rewrite, keine Cookie-Pflege (wie alexa-cookie2)
ASSET_RE = re.compile(r"\.(ico|js|ttf|svg|png|woff2?|appcache)(\?|$)", re.I)

# Header, die nicht an Amazon weitergereicht werden
_REQ_DROP = {
    "host", "connection", "content-length", "accept-encoding",
    "cookie", "referer", "origin", "upgrade",
    "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host",
    "x-forwarded-port", "x-real-ip",
}
# Header, die nicht zurueck an den Browser
_RES_DROP = {
    "connection", "keep-alive", "transfer-encoding", "upgrade",
    "content-length", "content-encoding", "server", "via",
    # WICHTIG: "upgrade-insecure-requests" wuerde alle http-Requests des
    # Browsers (Formular-POSTs!) auf https upgraden -> SSL-Fehler gegen
    # unseren http-Only-Ingress. Deshalb strippen.
    "content-security-policy", "content-security-policy-report-only",
}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def new_device_id() -> str:
    """16 Zufallsbytes -> hex -> UPPERCASE -> nochmal hex + Device-Type-Suffix (92 Zeichen)."""
    hex32 = os.urandom(16).hex().upper()
    return hex32.encode("ascii").hex() + DEVICE_ID_SUFFIX


def new_frc() -> str:
    """frc: 313 zufaellige Bytes als base64 (Amazon erwartet exakt diese Laenge)."""
    return base64.b64encode(os.urandom(313)).decode()


def new_map_md() -> str:
    payload = (
        '{"device_user_dictionary":[],'
        '"device_registration_data":{"software_version":"1"},'
        f'"app_identifier":{{"app_version":"{APP_VERSION}","bundle_id":"com.amazon.echo"}}'
    )
    return base64.b64encode(payload.encode("utf-8")).decode()


def sanitize_cookie(cookie_str: str) -> str:
    """Nur Amazon-Session-Cookies behalten (wie sanitizeAmazonCookie in alexa-cookie2)."""
    out = []
    for k, v in parse_cookie_header(cookie_str or ""):
        if AMAZON_COOKIE_RE.match(k):
            out.append(f"{k}={v}")
    return "; ".join(out)


def _parse_set_cookies(headers: list[str] | list[bytes]) -> list[tuple[str, str]]:
    """name/value aus Set-Cookie-Headern (ap-fid="" wird verworfen)."""
    out: list[tuple[str, str]] = []
    for raw in headers:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        m = re.match(r"\s*([^=]+)=([^;]*);?.*", raw)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        if name == "ap-fid" and value == '""':
            continue
        out.append((name, value))
    return out


def parse_cookie_header(s: str) -> list[tuple[str, str]]:
    """Cookie-String 'a=b; c=d' als Paare.

    WICHTIG: Trenner ist ';' (nicht '&' wie bei Querystrings); Werte
    duerfen '=' enthalten (z. B. base64 frc/map-md mit Padding).
    """
    out: list[tuple[str, str]] = []
    for chunk in (c.strip() for c in (s or "").split(";")):
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        out.append((k.strip(), v))
    return out


class ProxyState:
    """Zustand eines einzelnen Browser-Logins (eines Tabs)."""

    def __init__(self, prefix_base: str, cookie_path: str, https: bool) -> None:
        self.sess = secrets.token_hex(16)
        # proxy_prefix = "<panel-base>/proxy/<sess>" (absolute, ohne trailing Slash)
        self.proxy_prefix = prefix_base.rstrip("/") + "/" + self.sess
        self.cookie_path = cookie_path  # Pfad, fuer den Browser-Cookies gelten
        self.https = https
        self.frc = new_frc()
        self.map_md = new_map_md()
        self.device_id = new_device_id()
        self.code_verifier = b64url(os.urandom(32))
        self.code_challenge = b64url(hashlib.sha256(self.code_verifier.encode("ascii")).digest())
        self.cookies: dict[str, str] = {}  # kumuliert (Requests + Responses)
        self.created = time.time()
        self.done = False
        self.result: dict | None = None
        self.last_event: str | None = None  # letzter URL-Schritt (Diagnose)
        self.events: list[str] = []        # letzte Schritte (Diagnose, max. 80)

    def record(self, line: str) -> None:
        """Diagnose-Schritt merken (Proxy-Log, max. 80 Zeilen)."""
        self.events.append(line)
        if len(self.events) > 80:
            self.events.pop(0)
        self.last_event = line

    # ------------------------------------------------------------------
    # OIDC-Start-URL (amazon.com, wie alexa-cookie2 buildInitialUrl)
    # ------------------------------------------------------------------

    def initial_url(self) -> str:
        base = BASE_AMAZON
        return (
            f"https://www.{base}/ap/signin"
            f"?openid.return_to=https%3A%2F%2Fwww.{base}%2Fap%2Fmaplanding"
            f"&openid.assoc_handle=amzn_dp_project_dee_ios"
            f"&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            f"&pageId=amzn_dp_project_dee_ios"
            f"&accountStatusPolicy=P1"
            f"&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            f"&openid.mode=checkid_setup"
            # WICHTIG: openid.ns.oa2 MUSS http:// sein (wie alexa-cookie2 /
            # alexa-mcp). Mit https:// bucht Amazon die OA2-Assoziation NICHT
            # ein: der Claim-Flow enthaelt dann keine openid.oa2-Felder und der
            # finale maplanding-Redirect kommt OHNE openid.oa2.authorization_code.
            # (A/B-verifiziert gegen echtes Amazon am 2026-11-17.)
            f"&openid.ns.oa2=http%3A%2F%2Fwww.{base}%2Fap%2Fext%2Foauth%2F2"
            f"&openid.oa2.client_id=device%3A{self.device_id}"
            f"&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0"
            f"&openid.oa2.response_type=code"
            f"&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
            f"&openid.pape.max_auth_age=0"
            f"&openid.oa2.scope=device_auth_access"
            f"&openid.oa2.code_challenge_method=S256"
            f"&openid.oa2.code_challenge={self.code_challenge}"
            f"&language=de_DE"
        )

    def start_url(self) -> str:
        u = urlparse(self.initial_url())
        qs = f"?{u.query}" if u.query else ""
        return f"{self.proxy_prefix}/www.{BASE_AMAZON}{u.path}{qs}"

    # ------------------------------------------------------------------
    # URL-Rewrites
    # ------------------------------------------------------------------

    def rewrite_out(self, url: str) -> str:
        """Amazon-URL -> Proxy-URL (Response-Body/Location, Richtung Browser)."""
        url = url.replace("&#x2F;", "/")
        for host in PROXY_HOSTS:
            url = re.sub(
                rf"https?://{re.escape(host)}(?::\d+)?/",
                f"{self.proxy_prefix}/{host}/",
                url,
            )
        return url

    # Relative HTML-Attribute-URLs (action/href/src), z. B.
    #   <form action="/ax/claim?openid...">
    # wuerde der Browser an den HA-Root senden (statt zum Proxy) -> 404.
    _REL_ATTR_RE = re.compile(
        r"\b(action|href|src|data-src|poster)(\s*=\s*)([\"'])(/)(?![/])"
    )
    _META_REFRESH_RE = re.compile(
        r"(<meta\b[^>]*\brefresh\b[^>]*\burl\s*=\s*)([\"']?)(/)(?![/])"
    )

    def rewrite_out_body(self, body: str, host: str) -> str:
        """HTML-Body Richtung Browser: absolute + relative Amazon-URLs
        auf Proxy-URLs umschreiben."""
        body = self.rewrite_out(body)
        # Protokoll-relative Amazon-URLs: //www.amazon.com/...
        for h in PROXY_HOSTS:
            body = re.sub(
                rf"//{re.escape(h)}(?::\d+)?/",
                f"{self.proxy_prefix}/{h}/",
                body,
            )
        base = f"{self.proxy_prefix}/{host}"

        def _abs_attr(m: re.Match) -> str:
            return m.group(1) + m.group(2) + m.group(3) + base + m.group(4)

        body = self._REL_ATTR_RE.sub(_abs_attr, body)

        def _abs_refresh(m: re.Match) -> str:
            return m.group(1) + m.group(2) + base + m.group(3)

        body = self._META_REFRESH_RE.sub(_abs_refresh, body)
        return body

    def rewrite_in(self, url: str) -> str:
        """Proxy-URL -> echte Amazon-URL (Request-Header/Query/Body, Richtung Amazon)."""
        base = self.proxy_prefix
        for host in PROXY_HOSTS:
            url = url.replace(f"{base}/{host}/", f"https://{host}/")
        if url == base:
            return self.initial_url()
        if url.startswith(base + "/"):
            return f"https://www.{BASE_AMAZON}/{url[len(base) + 1:]}"
        return url

    def fix_qs(self, query: str) -> str:
        """Proxy-URLs in Query-Parameter-Werten zurueck zur echten Amazon-URL."""
        if not query:
            return query
        pairs = parse_qsl(query, keep_blank_values=True)
        changed = False
        fixed = []
        for k, v in pairs:
            nv = self.rewrite_in(v)
            if nv != v:
                changed = True
            fixed.append((k, nv))
        return urlencode(fixed) if changed else query

    # ------------------------------------------------------------------
    # Cookies
    # ------------------------------------------------------------------

    def browser_cookie_header(self, incoming: str) -> str:
        """Cookie-Header fuer den Amazon-Request.

        WICHTIG: Basen auf den AKKUMULIERTEN Amazon-Cookies (self.cookies,
        aus allen Set-Cookie-Antworten) und nicht nur auf den Browser-Cookies.
        Verliert der Browser ein Cookie (z. B. wegen SameSite/Secure), kommt
        es sonst nie wieder zu Amazon -> Amazons Server-Session verliert den
        OA2-Flow-State und sendet am Ende KEIN openid.oa2.authorization_code.
        Browser-Cookies (incoming) werden drueberschrieben (neuere Werte).
        """
        merged = dict(self.cookies)
        for k, v in parse_cookie_header(incoming or ""):
            merged[k] = v
        if "frc" not in merged:
            merged["frc"] = self.frc
        if "map-md" not in merged:
            merged["map-md"] = self.map_md
        return "; ".join(f"{k}={v}" for k, v in merged.items())

    def absorb_set_cookies(self, headers: list[str] | list[bytes]) -> None:
        for name, value in _parse_set_cookies(headers):
            self.cookies[name] = value

    def absorb_request_cookie(self, incoming: str) -> None:
        for name, value in parse_cookie_header(incoming or ""):
            self.cookies[name] = value

    def login_cookie(self) -> str:
        return sanitize_cookie("; ".join(f"{k}={v}" for k, v in self.cookies.items()))

    def rewrite_set_cookie_for_browser(self, raw: str) -> str:
        """Set-Cookie fuer den Browser: Domain streichen, Path auf den
        Add-on-Pfad setzen, Secure nur bei https-Ingress behalten.

        SameSite=None ohne Secure ist ungueltig (Browser verwirft das
        Cookie) -> ueber http streichen.
        """
        keep: list[str] = []
        for chunk in (c.strip() for c in raw.split(";")):
            low = chunk.lower()
            if low.startswith("domain"):
                continue
            if low.startswith("path"):
                keep.append(f"Path={self.cookie_path}")
                continue
            if low.startswith("secure") and not self.https:
                continue
            if low.startswith("samesite") and not self.https:
                continue
            keep.append(chunk)
        return "; ".join(keep)

    # ------------------------------------------------------------------
    # Erfolgserkennung
    # ------------------------------------------------------------------

    @staticmethod
    def _check_success(url: str) -> str | None:
        """Authorization-Code aus einer Erfolgs-URL ziehen (oder None)."""
        if not url:
            return None
        if "/spa/index.html" in url:
            code = _code_from(url)
            if code:
                return code
            return None
        if "/ap/maplanding?" in url:
            return _code_from(url)
        return None

    def detect_success(self, request_url: str, location: str | None) -> str | None:
        """Code liefern, wenn der Login-Schritt den OIDC-Code enthalten hat."""
        for cand in (location, request_url):
            code = self._check_success(cand)
            if code:
                self.last_event = cand[:300]
                self.done = True
                self.result = {
                    "loginCookie": self.login_cookie(),
                    "authorization_code": code,
                    "frc": self.frc,
                    "map-md": self.map_md,
                    "deviceId": self.device_id,
                    "verifier": self.code_verifier,
                    "deviceSerial": os.urandom(16).hex(),
                }
                return code
        return None


def _code_from(url: str) -> str | None:
    q = url.split("?", 1)[1] if "?" in url else ""
    for k, v in parse_qsl(q, keep_blank_values=True):
        if k == "openid.oa2.authorization_code":
            return v
    return None
