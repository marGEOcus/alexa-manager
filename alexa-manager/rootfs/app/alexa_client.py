"""Alexa Manager - Amazon-Sitzung und inoffizielle Alexa-Web-API.

Auth-Modell (identisch mit alexa-mcp / alexa-remote2):
  * Login geht primar ueber den Browser (Reverse-Proxy, amazon_proxy.py):
    der Nutzer meldet sich auf der echten Amazon-Seite an (inkl. 2FA), der
    Proxy fängt den OIDC-Authorization-Code + Cookies ab.
  * Die Geraete-Registrierung (POST api.amazon.com/auth/register) leitet
    daraus den Refresh-Token ab.
  * Alle API-Zugriffe laufen mit localCookie (Cookies der amazon.de-Seite)
    + csrf-Header gegen alexa.amazon.de.
  * Fallback: headless alexapy-Login (E-Mail + Passwort, 2FA per Code) -
    kommt je nach Konto nicht immer durch.

Wichtig: Es wird KEIN Passwort gespeichert. Nach dem Login liegen nur
Refresh-Token + Cookies + Geraete-Identitaet in
/data/alexa_registration.json (0600); beim Neustart wird die Sitzung still
aus dem Refresh-Token erneuert.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import time
import uuid as uuid_mod
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

import aiohttp

from alexapy import AlexaLogin
from alexapy.const import GQL_SMARTHOME_QUERY, GQL_SMARTHOME_QUERY_LEGACY

from amazon_proxy import (
    API_USER_AGENT,
    APP_VERSION,
    BASE_AMAZON,
    BROWSER_UA,
    DEVICE_APP_NAME,
    DEVICE_TYPE,
    ProxyState,
    parse_cookie_header,
    sanitize_cookie,
)

log = logging.getLogger("alexa-manager")

DATA_DIR = Path(os.environ.get("ALEXA_MANAGER_DATA_DIR", "/data"))
REG_FILE = DATA_DIR / "alexa_registration.json"
LEGACY_SESSION_FILE = DATA_DIR / "alexa_session.json"
ALEXA_DIR = DATA_DIR / "alexa"
DEFAULT_DOMAIN = "amazon.de"
ROUTES_VERSION = "3.0.264101"
# Debug-HTML von alexapy (ein-/aus via AM_DEBUG=0/1, Default an)
ALEXAPY_DEBUG = os.environ.get("AM_DEBUG", "1") == "1"
# Amazon-Login-Flow braucht oft mehrere Formularschritte pro login()-Aufruf
LOGIN_MAX_STEPS = 8

# Pfade, ueber die das csrf-Cookie gesetzt wird (in dieser Reihenfolge probiert)
CSRF_PATHS = (
    "/api/language",
    "/spa/index.html",
    "/api/devices-v2/device?cached=false",
    "/templates/oobe/d-device-pick.handlebars",
    "/api/strings",
)

# ---------------------------------------------------------------------------
# GraphQL-Queries und Mutationen (/nexus/v1/graphql, csrf-Header erforderlich)
# ---------------------------------------------------------------------------

GQL_ENDPOINTS = """query getDevicesBaseData {
  allDevices: listEndpoints(listEndpointsInput: { includeHouseholdDevices: true }) {
    endpoints {
      endpointId: id
      enablement
      legacyAppliance { applianceId }
      legacyIdentifiers { chrsIdentifier { entityId } }
      friendlyNameObject { value { text } }
      manufacturer { value { text } }
      displayCategories { primary { value } }
      features { name properties { name ... on Reachability { reachabilityStatusValue } } }
    }
  }
}"""

GQL_GROUPS = """query listDeviceGroups {
  listDeviceGroups(listDeviceGroupsInput: {}) {
    deviceGroups {
      id
      friendlyName { value { text } }
      memberDevices { items { id friendlyNameObject { value { text } } } }
    }
  }
}"""

MUT_ENABLE = """mutation setEndpointEnablement($input: SetEndpointEnablementInput!) {
  setEndpointEnablement(input: $input) { endpoint { endpointId: id enablement } error { __typename } }
}"""

MUT_RENAME = """mutation setEndpointFriendlyName($in: SetEndpointFriendlyNameInput!) {
  setEndpointFriendlyName(input: $in) { __typename }
}"""

MUT_FORGET = """mutation forgetEndpoint($input: ForgetEndpointInput!) {
  forgetEndpoint(forgetEndpointInput: $input) { endpointId }
}"""

TYPE_JAVA_TRIGGER = "com.amazon.alexa.behaviors.model.Trigger"
TYPE_UTTER_PAYLOAD = "com.amazon.alexa.behaviors.model.CustomUtteranceTriggerPayload"
TYPE_SEQUENCE = "com.amazon.alexa.behaviors.model.Sequence"
TYPE_SERIAL_NODE = "com.amazon.alexa.behaviors.model.SerialNode"
TYPE_OP_NODE = "com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode"

ACTION_SKILL = {
    "Alexa.TextCommand": "amzn1.ask.1p.tellalexa",
    "Alexa.SmartHome.Batch": "amzn1.ask.1p.smarthome",
    "AlexaAnnouncement": "amzn1.ask.1p.messaging",
    "Alexa.Notifications.SendMobilePush": "amzn1.ask.1p.alexanotifications",
    "Alexa.Music.PlaySearchPhrase": "amzn1.ask.1p.music",
    "Alexa.Sound": "amzn1.ask.1p.sound",
    "Alexa.System.Wait": "amzn1.ask.1p.alexa-system",
}


class AlexaError(Exception):
    """API-Fehler mit menschenlesbarer Meldung."""


class SessionNotReady(AlexaError):
    pass


# ---------------------------------------------------------------------------
# Token-Flows (exakt wie alexa-cookie2, nur aiohttp statt https-Modul)
# ---------------------------------------------------------------------------


async def _resp_json(resp: aiohttp.ClientResponse):
    text = await resp.text()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_cookie_str(s: str) -> dict[str, str]:
    """Cookie-String -> dict (Trenner ';', Werte koennen '=' enthalten)."""
    return dict(parse_cookie_header(s or ""))


def _cookie_str(d: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in d.items())


async def _merge_set_cookies(d: dict, resp: aiohttp.ClientResponse) -> None:
    # multidict >= 6.9: getall() wirft bei fehlendem Key einen KeyError
    # (trotz Doku) - also abfangen.
    try:
        raws = list(resp.headers.getall("Set-Cookie"))
    except KeyError:
        raws = []
    for raw in raws:
        m = re.match(r"\s*([^=]+)=([^;]*);?.*", raw)
        if not m:
            continue
        if m.group(1) == "ap-fid" and m.group(2) == '""':
            continue
        d[m.group(1)] = m.group(2)


async def _get_local_cookies(http: aiohttp.ClientSession, amazon_page: str,
                             refresh_token: str, app_name: str) -> str:
    """Token-Austausch: Refresh-Token -> Session-Cookies der Landes-Seite."""
    params = {
        "di.os.name": "iOS",
        "app_version": APP_VERSION,
        "domain": f".{amazon_page}",
        "source_token": refresh_token,
        "requested_token_type": "auth_cookies",
        "source_token_type": "refresh_token",
        "di.hw.version": "iPhone",
        "di.sdk.version": "6.12.4",
        "app_name": app_name,
        "di.os.version": "16.6",
    }
    headers = {
        "User-Agent": API_USER_AGENT,
        "Accept-Language": "de-DE",
        "Accept-Charset": "utf-8",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "x-amzn-identity-auth-domain": f"api.{amazon_page}",
    }
    async with http.post(
        f"https://www.{amazon_page}/ap/exchangetoken/cookies",
        data=urlencode(params), headers=headers, allow_redirects=False,
    ) as resp:
        if resp.status >= 400:
            raise AlexaError(f"Token-Austausch ({amazon_page}): HTTP {resp.status}")
        body = await _resp_json(resp)
        merged = {}
        await _merge_set_cookies(merged, resp)
    if not isinstance(body, dict):
        raise AlexaError("Token-Austausch: keine Antwort.")
    vals = ((body.get("response") or {}).get("tokens") or {}).get("cookies", {}).get(
        f".{amazon_page}")
    if not vals:
        raise AlexaError(f"Token-Austausch: keine Cookies fuer .{amazon_page}.")
    for c in vals:
        merged[c["Name"]] = c["Value"]
    return _cookie_str(merged)


async def _get_csrf(http: aiohttp.ClientSession, amazon_page: str,
                    cookie: str) -> tuple[str, str | None]:
    """Alexa-Seiten abfragen, bis das csrf-Cookie gesetzt ist.

    Returns: (aktualisierte Cookie-String, csrf oder None)
    """
    cur = cookie
    for path in CSRF_PATHS:
        headers = {
            "DNT": "1",
            "User-Agent": BROWSER_UA,
            "Connection": "keep-alive",
            "Referer": f"https://alexa.{amazon_page}/spa/index.html",
            "Cookie": cur,
            "Accept": "*/*",
            "Origin": f"https://alexa.{amazon_page}",
            "Accept-Language": "de-DE",
        }
        async with http.get(f"https://alexa.{amazon_page}{path}", headers=headers) as resp:
            merged = _parse_cookie_str(cur)
            await _merge_set_cookies(merged, resp)
            cur = _cookie_str(merged)
            m = re.search(r"(?:^|;\s*)csrf=([^;]+)", cur)
            if m:
                return cur, m.group(1)
    return cur, None


async def _register_device(http: aiohttp.ClientSession, res: dict) -> dict:
    """Geraete-Registrierung nach Browser-Login.

    `res` kommt vom Proxy (loginCookie, authorization_code, frc, map-md,
    deviceId, verifier, deviceSerial). Returns: komplette Registrierung
    (Refresh-Token, lokale Cookies, csrf, amazonPage, ...).
    """
    cookie_d = _parse_cookie_str(sanitize_cookie(res["loginCookie"]))
    code = res.get("authorization_code") or ""
    if not code:
        raise AlexaError(
            "Kein Autorisierungs-Code im maplanding-Redirect (OA2-Assoziation "
            "fehlte). Bitte im echten privaten Browser-Fenster erneut anmelden.")
    register_data = {
        "requested_extensions": ["device_info", "customer_info"],
        "cookies": {
            "website_cookies": [{"Value": v, "Name": k} for k, v in cookie_d.items()],
            "domain": f".{BASE_AMAZON}",
        },
        "registration_data": {
            "domain": "Device",
            "app_version": APP_VERSION,
            "device_type": DEVICE_TYPE,
            "device_name": "%FIRST_NAME%'s%DUPE_STRATEGY_1ST%" + DEVICE_APP_NAME,
            "os_version": "18.3.1",
            "device_serial": res["deviceSerial"],
            "device_model": "iPhone",
            "app_name": DEVICE_APP_NAME,
            "software_version": "1",
        },
        "auth_data": {
            "client_id": res["deviceId"],
            "authorization_code": res["authorization_code"],
            "code_verifier": res["verifier"],
            "code_algorithm": "SHA-256",
            "client_domain": "DeviceLegacy",
        },
        "user_context_map": {"frc": res["frc"]},
        "requested_token_type": ["bearer", "mac_dms", "website_cookies"],
    }
    headers = {
        "User-Agent": API_USER_AGENT,
        "Accept-Language": "de-DE",
        "Accept-Charset": "utf-8",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": _cookie_str(cookie_d),
        "Accept": "application/json",
        "x-amzn-identity-auth-domain": f"api.{BASE_AMAZON}",
    }
    async with http.post(
        f"https://api.{BASE_AMAZON}/auth/register",
        json=register_data, headers=headers, allow_redirects=False,
    ) as resp:
        body_text = await resp.text()
        log.info("Geräte-Registrierung: HTTP %s (%d B)",
                 resp.status, len(body_text))
        if resp.status >= 400:
            raise AlexaError(
                f"Geräte-Registrierung: HTTP {resp.status} {body_text[:300]}")
        body = None
        if body_text:
            try:
                body = json.loads(body_text)
            except ValueError:
                body = None
        await _merge_set_cookies(cookie_d, resp)
    tokens = (((body or {}).get("response") or {}).get("success") or {}).get("tokens") or {}
    bearer = tokens.get("bearer") or {}
    refresh_token = bearer.get("refresh_token")
    access_token = bearer.get("access_token")
    mac_dms = tokens.get("mac_dms")
    if not refresh_token:
        raise AlexaError(
            "Geräte-Registrierung: kein Refresh-Token in der Antwort "
            f"(Body: {body_text[:200]})")
    for c in tokens.get("website_cookies") or []:
        cookie_d[c["Name"]] = c["Value"]

    # Welcher Marktplatz? (z. B. amazon.de) - Fehler sind nicht faatal.
    amazon_page = DEFAULT_DOMAIN
    headers_me = {
        "User-Agent": API_USER_AGENT,
        "Accept-Language": "de-DE",
        "Accept-Charset": "utf-8",
        "Connection": "keep-alive",
        "Accept": "application/json",
        "Cookie": _cookie_str(cookie_d),
    }
    try:
        async with http.get(
            f"https://alexa.{BASE_AMAZON}/api/users/me?platform=ios&version={APP_VERSION}",
            headers=headers_me,
        ) as resp:
            me = await _resp_json(resp)
            await _merge_set_cookies(cookie_d, resp)
            mpd = (me or {}).get("marketPlaceDomainName") or ""
            if "." in mpd:
                amazon_page = mpd.split(".", 1)[1]
    except aiohttp.ClientError as ex:
        log.warning("users/me fehlgeschlagen, %s wird verwendet: %s", DEFAULT_DOMAIN, ex)

    local_cookie = await _get_local_cookies(http, amazon_page, refresh_token, DEVICE_APP_NAME)
    local_cookie, csrf = await _get_csrf(http, amazon_page, local_cookie)

    return {
        "dataVersion": 2,
        "refreshToken": refresh_token,
        "accessToken": access_token,
        "tokenDate": int(time.time() * 1000),
        "macDms": mac_dms,
        "loginCookie": sanitize_cookie(_cookie_str(cookie_d)),
        "localCookie": local_cookie,
        "csrf": csrf,
        "amazonPage": amazon_page,
        "frc": res["frc"],
        "map-md": res["map-md"],
        "deviceId": res["deviceId"],
        "deviceSerial": res["deviceSerial"],
        "deviceAppName": DEVICE_APP_NAME,
    }


async def _refresh_registration(http: aiohttp.ClientSession, reg: dict) -> dict:
    """Sitzung erneuern (Access-Token + lokale Cookies + csrf), ohne
    neue Geraete-Registrierung. Returns: aktualisierte reg.
    """
    app_name = reg.get("deviceAppName") or DEVICE_APP_NAME
    form = {
        "app_name": app_name,
        "app_version": APP_VERSION,
        "di.sdk.version": "6.12.4",
        "source_token": reg["refreshToken"],
        "package_name": "com.amazon.echo",
        "di.hw.version": "iPhone",
        "platform": "iOS",
        "requested_token_type": "access_token",
        "source_token_type": "refresh_token",
        "di.os.name": "iOS",
        "di.os.version": "16.6",
        "current_version": "6.12.4",
    }
    headers = {
        "User-Agent": API_USER_AGENT,
        "Accept-Language": "de-DE",
        "Accept-Charset": "utf-8",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Cookie": reg.get("loginCookie") or "",
        "x-amzn-identity-auth-domain": f"api.{BASE_AMAZON}",
    }
    async with http.post(
        f"https://api.{BASE_AMAZON}/auth/token",
        data=urlencode(form), headers=headers, allow_redirects=False,
    ) as resp:
        if resp.status >= 400:
            raise AlexaError(f"Token-Erneuerung: HTTP {resp.status}")
        body = await _resp_json(resp)
        cookie_d = _parse_cookie_str(reg.get("loginCookie") or "")
        await _merge_set_cookies(cookie_d, resp)
    access_token = (body or {}).get("access_token")
    if not access_token:
        raise AlexaError("Token-Erneuerung: kein Access-Token in der Antwort.")

    page = reg.get("amazonPage") or DEFAULT_DOMAIN
    local_cookie = await _get_local_cookies(http, page, reg["refreshToken"], app_name)
    local_cookie, csrf = await _get_csrf(http, page, local_cookie)

    out = dict(reg)
    out.update({
        "accessToken": access_token,
        "tokenDate": int(time.time() * 1000),
        "loginCookie": sanitize_cookie(_cookie_str(cookie_d)),
        "localCookie": local_cookie,
        "csrf": csrf,
    })
    return out


class AlexaSession:
    """Halter fuer die Amazon-Sitzung (Cookie-Modell) und die API-Methoden."""

    def __init__(self) -> None:
        self.login: AlexaLogin | None = None      # alexapy (Fallback, headless)
        self.proxy: ProxyState | None = None      # aktiver Browser-Login
        self.state: str = "none"  # none|working|needs_2fa|needs_option|error|ready
        self.state_detail: str | None = None
        self.state_options: dict | None = None
        self.email: str | None = None
        self.domain: str = DEFAULT_DOMAIN
        self._uuid: str | None = None
        self._customer_id: str | None = None
        self._reg: dict | None = None
        self._cookie: str | None = None        # localCookie (alexa.amazon.de)
        self._login_cookie: str | None = None  # Basis-Cookies (api.amazon.com)
        self._csrf: str | None = None
        self._api_host: str | None = None      # z. B. alexa.amazon.de
        self._http: aiohttp.ClientSession | None = None
        self._http_loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Persistenz (Refresh-Token + Cookies + Geraete-ID - niemals Passwort)
    # ------------------------------------------------------------------

    def _load_registration(self) -> dict | None:
        if not REG_FILE.exists():
            return None
        try:
            data = json.loads(REG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and (data.get("refreshToken") or data.get("localCookie")):
                return data
        except Exception as ex:
            log.warning("Registrierungsdatei nicht lesbar: %s", ex)
        return None

    def _save_registration(self) -> None:
        if not self._reg:
            return
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._reg["saved_at"] = int(time.time())
            tmp = REG_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._reg), encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(REG_FILE)
            log.info("Alexa-Registrierung gespeichert (%s)", REG_FILE)
        except Exception as ex:
            log.error("Konnte Registrierung nicht speichern: %s", ex)

    def _clear_persisted(self) -> None:
        for f in (REG_FILE, LEGACY_SESSION_FILE):
            try:
                f.unlink()
            except FileNotFoundError:
                pass
            except OSError as ex:
                log.warning("Datei nicht loeschbar %s: %s", f, ex)
        for pattern in (str(ALEXA_DIR / ".storage" / "*"), str(ALEXA_DIR / "*.cookies")):
            for p in glob.glob(pattern):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # HTTP-Sitzung
    # ------------------------------------------------------------------

    def _ensure_http(self) -> aiohttp.ClientSession:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if (
            self._http is None
            or self._http.closed
            or self._http_loop is not loop
        ):
            # Session an den aktuellen Loop binden (aiohttp verlangt das).
            # Alte Session wird verworfen, wenn der Loop nicht mehr passt.
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
            self._http_loop = loop
        return self._http

    async def close(self) -> None:
        if self._http is not None and not self._http.closed:
            try:
                await self._http.close()
            except Exception:
                pass
            self._http = None

    def _apply_registration(self, reg: dict) -> None:
        self._reg = reg
        self.domain = reg.get("amazonPage") or self.domain
        self._api_host = f"alexa.{self.domain}"
        self._cookie = reg.get("localCookie")
        self._login_cookie = reg.get("loginCookie")
        self._csrf = reg.get("csrf")
        self.email = reg.get("email") or self.email

    # ------------------------------------------------------------------
    # Browser-Login (Proxy)
    # ------------------------------------------------------------------

    def start_proxy(self, panel_url: str | None,
                    fallback_host: str | None = None) -> ProxyState:
        """Proxy-Login vorbereiten; ProxyState mit start_url() liefern.

        panel_url = URL des Panels im Browser (z. B. http://host:8123/api/alexa-manager/).
        """
        if panel_url:
            u = urlparse(panel_url)
            if u.scheme in ("http", "https") and u.netloc:
                base = f"{u.scheme}://{u.netloc}{u.path.rstrip('/')}"
                cookie_path = u.path.rstrip("/") or "/"
                https = u.scheme == "https"
            else:
                raise AlexaError(f"Ungueltige Panel-URL: {panel_url}")
        elif fallback_host:
            base = f"http://{fallback_host}/api/alexa-manager"
            cookie_path = "/api/alexa-manager"
            https = False
        else:
            raise AlexaError("Keine Panel-URL bekannt - Start ueber das Panel ausloesen.")
        self.proxy = ProxyState(base + "/proxy", cookie_path, https)
        log.info("Browser-Login vorbereitet (Prefix: %s)", self.proxy.proxy_prefix[:100])
        return self.proxy

    async def finalize_proxy_login(self) -> None:
        """Nach erkanntem Erfolg: Geraete-Registrierung + Persistenz."""
        st = self.proxy
        if st is None or not st.result:
            return
        self.state = "working"
        self.state_detail = "Anmeldung erkannt - Geraete-Registrierung laeuft ..."
        async with self._lock:
            try:
                reg = await _register_device(self._ensure_http(), st.result)
                self._apply_registration(reg)
                self._save_registration()
                self.state = "ready"
                self.state_detail = None
                self.state_options = None
                log.info("Browser-Login erfolgreich (amazonPage=%s)", reg.get("amazonPage"))
            except Exception as ex:
                log.exception("Browser-Login-Finalisierung fehlgeschlagen")
                self.state = "error"
                self.state_detail = (
                    "Anmeldung wurde erkannt, aber die Geraete-Registrierung "
                    f"fehlgeschlagen: {ex} - bitte erneut anmelden."
                )

    # ------------------------------------------------------------------
    # alexapy-Login (Fallback, headless)
    # ------------------------------------------------------------------

    def _make_login(self, email: str, password: str, oauth: dict | None = None) -> AlexaLogin:
        # alexapy schreibt Cookies (.storage/) und Debug-HTML hierher
        ALEXA_DIR.mkdir(parents=True, exist_ok=True)
        (ALEXA_DIR / ".storage").mkdir(parents=True, exist_ok=True)
        return AlexaLogin(
            url=self.domain,
            email=email,
            password=password,
            outputpath=lambda p: str(ALEXA_DIR / p),
            uuid=self._uuid,
            oauth=oauth or {},
            debug=ALEXAPY_DEBUG,
        )

    async def _close_login(self) -> None:
        if self.login is not None:
            try:
                await self.login.close()
            except Exception:
                pass
            self.login = None

    def _is_terminal(self) -> bool:
        """True, wenn der Login-Flow in einem Endzustand ist (weiterlaufen lassen nur dazwischen)."""
        st = self.login.status or {}
        return any(k in st for k in (
            "login_successful", "securitycode_required", "claimspicker_required",
            "authselect_required", "captcha_required", "ap_error", "login_failed",
            "verificationcode_required",
        ))

    def _after_login_attempt(self) -> None:
        """Status nach login() auslesen und Machine-State setzen."""
        st = self.login.status or {}
        if st.get("login_successful") or self.login.access_token:
            self._finish_auth()
            return
        if st.get("securitycode_required"):
            self.state = "needs_2fa"
            self.state_detail = "Amazon verlangt einen 2-Faktor-Code."
            return
        if st.get("claimspicker_required") or st.get("authselect_required"):
            self.state = "needs_option"
            kind = "claimspicker" if st.get("claimspicker_required") else "authselect"
            options = getattr(self.login, "options", None) or {}
            self.state_detail = (
                st.get("claimspicker_message")
                or st.get("authselect_message")
                or "Amazon verlangt eine Auswahl."
            )
            self.state_options = {"kind": kind, "options": options}
            return
        if st.get("captcha_required"):
            self.state = "error"
            self.state_detail = (
                "Captcha erforderlich. Bitte den Browser-Login verwenden."
            )
            return
        self.state = "error"
        last_url = None
        try:
            if self.login.lastreq is not None:
                last_url = str(self.login.lastreq.url)
        except Exception:
            pass
        self.state_detail = (
            st.get("error_message")
            or st.get("message")
            or f"Login fehlgeschlagen: {st.get('login_failed', 'unbekannter Fehler')}. "
               f"Status: {st}" + (f" | Seite: {last_url}" if last_url else "")
        )

    def _adopt_alexa_login(self) -> None:
        """alexapy-Sitzung in das Cookie-Modell uebernehmen (Best-Effort)."""
        lg = self.login
        hdrs = getattr(lg, "_headers", {}) or {}
        cookie = hdrs.get("Cookie") or hdrs.get("cookie")
        if not cookie:
            return
        self._cookie = cookie
        self._csrf = hdrs.get("csrf")
        self._login_cookie = cookie
        self.domain = getattr(lg, "url", None) or self.domain
        self._api_host = f"alexa.{self.domain}"
        self._reg = {
            "dataVersion": 1,
            "email": self.email,
            "amazonPage": self.domain,
            "localCookie": cookie,
            "loginCookie": cookie,
            "csrf": self._csrf,
            "accessToken": getattr(lg, "access_token", None),
        }
        self._save_registration()

    def _finish_auth(self) -> None:
        self._adopt_alexa_login()
        self.state = "ready"
        self.state_detail = None
        self.state_options = None
        log.info("Amazon-Sitzung aktiv (headless) (%s)", self.email)

    async def login_start(self, email: str, password: str, domain: str | None = None) -> None:
        """Erster Login mit E-Mail + Passwort (2FA kann folgen)."""
        async with self._lock:
            await self._close_login()
            self.email = email.strip()
            self.domain = (domain or DEFAULT_DOMAIN).strip() or DEFAULT_DOMAIN
            self._uuid = uuid_mod.uuid4().hex
            self.login = self._make_login(self.email, password)
            self.state = "working"
            self.state_detail = "Amazon wird kontaktiert ..."
            try:
                # Ein login()-Aufruf = ein Formularschritt; der Flow
                # (signin -> continue -> MFA-Seite) braucht mehrere.
                for _ in range(LOGIN_MAX_STEPS):
                    await self.login.login()
                    if self._is_terminal():
                        break
            except Exception as ex:
                log.exception("Login-Fehler")
                self.state = "error"
                self.state_detail = f"Login-Fehler: {ex}"
                return
            self._after_login_attempt()

    async def submit_code(self, code: str) -> None:
        """2-Faktor-Code uebermitteln (Formular #auth-mfa-otpcode)."""
        async with self._lock:
            if self.state != "needs_2fa":
                raise AlexaError("Kein offenes 2FA-Verfahren.")
            try:
                first = True
                for _ in range(LOGIN_MAX_STEPS):
                    if first:
                        await self.login.login(data={"securitycode": code.strip()})
                        first = False
                    else:
                        await self.login.login()
                    if self._is_terminal():
                        break
            except Exception as ex:
                log.exception("2FA-Fehler")
                self.state = "error"
                self.state_detail = f"2FA-Fehler: {ex}"
                return
            self._after_login_attempt()

    async def submit_option(self, option: str) -> None:
        """Auswahl uebermitteln (claimspicker / authselect)."""
        async with self._lock:
            if self.state != "needs_option":
                raise AlexaError("Keine Auswahl offen.")
            key = "claimsoption"
            if (self.state_options or {}).get("kind") == "authselect":
                key = "authselectoption"
            try:
                first = True
                for _ in range(LOGIN_MAX_STEPS):
                    if first:
                        await self.login.login(data={key: option})
                        first = False
                    else:
                        await self.login.login()
                    if self._is_terminal():
                        break
            except Exception as ex:
                log.exception("Auswahl-Fehler")
                self.state = "error"
                self.state_detail = f"Auswahl-Fehler: {ex}"
                return
            self._after_login_attempt()

    # ------------------------------------------------------------------
    # Restore / Logout / Status
    # ------------------------------------------------------------------

    async def restore(self) -> None:
        """Beim Start: Sitzung aus gespeicherten Daten wiederherstellen."""
        reg = self._load_registration()
        if reg is None:
            self.state = "none"
            return
        self._apply_registration(reg)
        if reg.get("refreshToken"):
            self.state = "working"
            self.state_detail = "Sitzung wird aus Refresh-Token erneuert ..."
            async with self._lock:
                try:
                    new_reg = await _refresh_registration(self._ensure_http(), reg)
                    self._apply_registration(new_reg)
                    self._save_registration()
                    self.state = "ready"
                    log.info("Sitzung aus Refresh-Token erneuert")
                    return
                except Exception as ex:
                    log.warning("Refresh fehlgeschlagen: %s", ex)
        # Fallback: gespeichertes Cookie (z. B. aus alexapy-Adoption) kann noch gueltig sein
        if reg.get("localCookie"):
            try:
                await self._raw("get", "/api/users/me")
                self.state = "ready"
                log.info("Sitzung aus gespeichertem Cookie uebernommen")
                return
            except Exception as ex:
                log.warning("Cookie-Pruefung fehlgeschlagen: %s", ex)
        self.state = "none"
        self.state_detail = "Sitzung abgelaufen - bitte erneut anmelden."

    async def logout(self) -> None:
        """Sitzung beenden und gespeicherte Tokens loeschen."""
        async with self._lock:
            self.proxy = None
            await self._close_login()
            self._clear_persisted()
            self._reg = None
            self._cookie = None
            self._login_cookie = None
            self._csrf = None
            self._api_host = None
            self.state = "none"
            self.state_detail = None
            self.state_options = None
            self.email = None
            self._customer_id = None
            log.info("Abgemeldet, Tokens geloescht")

    def status(self) -> dict:
        """Status fuer die UI (ohne geheime Werte)."""
        return {
            "state": self.state,
            "detail": self.state_detail,
            "options": self.state_options,
            "email": self.email,
            "domain": self.domain,
            "customerId": self._customer_id,
            "sessionSaved": bool(
                self._reg and (self._reg.get("refreshToken") or self._reg.get("localCookie"))
            ),
            "sessionSavedAt": (self._reg or {}).get("saved_at"),
            "proxyActive": bool(self.proxy is not None and not self.proxy.done),
        }

    # ------------------------------------------------------------------
    # Rohe API-Zugriffe (localCookie + csrf-Header gegen alexa.<page>)
    # ------------------------------------------------------------------

    def _require_ready(self) -> None:
        if self.state != "ready" or not self._cookie or not self._api_host:
            raise SessionNotReady(
                "Nicht angemeldet - bitte zuerst in den Einstellungen Amazon verbinden."
            )

    async def _raw(self, method: str, path: str, data: dict | None = None,
                   query: dict | None = None, headers: dict | None = None) -> object:
        self._require_ready()
        url = f"https://{self._api_host}{path}"
        if query:
            url += "?" + urlencode(query)
        hdrs = {
            "User-Agent": API_USER_AGENT,
            "Accept": "application/json; charset=utf-8",
            "Accept-Language": "de-DE",
            "Referer": f"https://{self._api_host}/spa/index.html",
            "Origin": f"https://{self._api_host}",
            "Host": self._api_host,
            "Cookie": self._cookie,
            "csrf": self._csrf or "",
        }
        if data is not None:
            hdrs["Content-Type"] = "application/json; charset=utf-8"
        if headers:
            hdrs.update(headers)
        for attempt in (1, 2):
            try:
                async with self._ensure_http().request(
                    method.upper(), url, json=data, headers=hdrs
                ) as resp:
                    if resp.status in (401, 403) and attempt == 1:
                        # csrf/Cookie evtl. abgelaufen - einmal neu holen und wiederholen
                        if await self._refresh_csrf_once():
                            hdrs["Cookie"] = self._cookie
                            hdrs["csrf"] = self._csrf or ""
                            continue
                    text = await resp.text()
                    if resp.status in (401, 403):
                        self.state = "none"
                        self.state_detail = "Sitzung abgelaufen - bitte erneut anmelden."
                        raise SessionNotReady(self.state_detail)
                    if resp.status >= 400:
                        try:
                            body = json.loads(text) if text else None
                        except (json.JSONDecodeError, ValueError):
                            body = None
                        msg = body.get("message") if isinstance(body, dict) else ""
                        raise AlexaError(
                            f"{method.upper()} {path}: HTTP {resp.status} "
                            f"{msg or text[:120]}".strip()
                        )
                    if not text:
                        return None
                    try:
                        return json.loads(text)
                    except (json.JSONDecodeError, ValueError):
                        return None
            except aiohttp.ClientError as ex:
                raise AlexaError(f"{method.upper()} {path} fehlgeschlagen: {ex}") from ex
        return None

    async def _refresh_csrf_once(self) -> bool:
        try:
            cookie, csrf = await _get_csrf(self._ensure_http(), self.domain, self._cookie or "")
            if csrf:
                self._cookie = cookie
                self._csrf = csrf
                if self._reg is not None:
                    self._reg["localCookie"] = cookie
                    self._reg["csrf"] = csrf
                    self._save_registration()
                return True
        except Exception as ex:
            log.debug("CSRF-Refresh fehlgeschlagen: %s", ex)
        return False

    async def gql(self, query: str, variables: dict | None = None) -> object:
        body = await self._raw("post", "/nexus/v1/graphql", data={"query": query, "variables": variables or {}})
        if isinstance(body, dict) and body.get("errors"):
            raise AlexaError("GraphQL-Fehler: " + "; ".join(
                e.get("message", "") for e in body["errors"])[:300])
        return (body or {}).get("data") if isinstance(body, dict) else body

    # ------------------------------------------------------------------
    # Konto / Echo-Geraete
    # ------------------------------------------------------------------

    async def account(self) -> dict:
        """/api/devices-v2/device: registrierte Echos + Account-Daten."""
        data = await self._raw("get", "/api/devices-v2/device", query={"cached": "true"})
        data = data or {}
        devices = data.get("devices") or []
        echoes = [
            {
                "name": d.get("accountName") or d.get("deviceType"),
                "serialNumber": d.get("serialNumber"),
                "deviceType": d.get("deviceType"),
                "customerId": d.get("deviceOwnerCustomerId"),
            }
            for d in devices
            if d.get("serialNumber") and d.get("deviceType")
        ]
        if not self.email and data.get("accountName"):
            self.email = data["accountName"]
        if not self._customer_id:
            cid = next(
                (d.get("deviceOwnerCustomerId") for d in devices
                 if d.get("deviceOwnerCustomerId")),
                None,
            )
            if cid:
                self._customer_id = cid
        return {
            "email": self.email,
            "customerId": self._customer_id or (echoes[0]["customerId"] if echoes else None),
            "locale": "de-DE",
            "marketplaceId": "A1PA6795UKMFR9",
            "echoes": echoes,
            "raw": data,
        }

    # ------------------------------------------------------------------
    # Gerate
    # ------------------------------------------------------------------

    async def devices(self) -> list[dict]:
        """Alle Smart-Home-Endpunkte inkl. connectedVia (Skill), Erreichbarkeit, Gruppizugehoerigkeit."""
        groups_data = await self._raw("get", "/api/phoenix/group")
        phoenix = await self._raw("get", "/api/phoenix")
        try:
            ep_data = await self.gql(GQL_ENDPOINTS)
        except AlexaError:
            ep_data = None
        try:
            cv_data = await self.gql(GQL_SMARTHOME_QUERY)
        except AlexaError:
            try:
                cv_data = await self.gql(GQL_SMARTHOME_QUERY_LEGACY)
            except AlexaError:
                cv_data = None
        try:
            entities = await self._raw(
                "get", "/api/behaviors/entities",
                query={"skillId": "amzn1.ask.1p.smarthome"},
            )
        except AlexaError:
            entities = None

        # Indexe aufbauen
        cv_by_appliance: dict[str, dict] = {}
        if cv_data and cv_data.get("endpoints", {}).get("items"):
            for item in cv_data["endpoints"]["items"]:
                la = item.get("legacyAppliance") or {}
                if la.get("applianceId"):
                    cv_by_appliance[la["applianceId"]] = la

        phoenix_devices = (phoenix or {}).get("devices") or []
        phoenix_by_appliance = {d.get("applianceId"): d for d in phoenix_devices if d.get("applianceId")}
        phoenix_by_deviceid = {d.get("deviceId"): d for d in phoenix_devices if d.get("deviceId")}

        entity_by_id: dict[str, dict] = {}
        if isinstance(entities, list):
            for ent in entities:
                if isinstance(ent, dict) and ent.get("id"):
                    entity_by_id[str(ent["id"])] = ent

        appliance_groups = (groups_data or {}).get("applianceGroups") or []

        # Gruppen-Zugehoerigkeit aufloesen. Die neuen getall-Endpunkte haben
        # oft KEIN legacyAppliance.applianceId mehr, waehrend Gruppen (Phoenix)
        # alte applianceIds (SKILL_…/JSON-dsn) tragen. Dagegen bruecken:
        #   * exakte applianceIds (alte + neue Endpunkte, auch Gruppen, die
        #     ueber dieses Panel mit endpointId-IDs angelegt wurden),
        #   * Phoenix-Geraete (applianceId <-> deviceId),
        #   * UUIDs, die in den ID-Formaten stecken.
        uuid_re = re.compile(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")

        def _uuids(s: object) -> set[str]:
            return {m.group(1).lower() for m in uuid_re.finditer(str(s or ""))}

        phoenix_id_owner: dict[str, dict] = {}
        for pd in phoenix_devices:
            for k in (str(pd.get("applianceId")), str(pd.get("deviceId"))):
                if k and k != "None":
                    phoenix_id_owner.setdefault(k, pd)
                for u in _uuids(k):
                    phoenix_id_owner.setdefault(u, pd)

        def _phoenix_keys(pd: dict) -> set[str]:
            ks: set[str] = set()
            for k in (str(pd.get("applianceId")), str(pd.get("deviceId"))):
                if k and k != "None":
                    ks.add(k)
                    ks |= _uuids(k)
            return ks

        def _resolve_pd(raw: str) -> dict | None:
            pd = phoenix_id_owner.get(raw)
            if pd is None:
                for u in _uuids(raw):
                    pd = phoenix_id_owner.get(u)
                    if pd is not None:
                        break
            return pd

        group_member_keys: dict[str, set[str]] = {}
        for g in appliance_groups:
            name = g.get("name") or g.get("groupId")
            if not name:
                continue
            ks: set[str] = set()
            for ap in g.get("applianceIds") or []:
                raw = str(ap)
                ks.add(raw)
                ks |= _uuids(raw)
                pd = _resolve_pd(raw)
                if pd is not None:
                    ks |= _phoenix_keys(pd)
            # Wichtigste Bruecke: chrEndpoints.entityId ist die UUID des
            # neuen Endpunkts (amzn1.alexa.endpoint.<uuid>) – direkt aus
            # der Gruppen-Antwort, ohne Phoenix.
            for ce in g.get("chrEndpoints") or []:
                if isinstance(ce, dict) and ce.get("entityId"):
                    ks.add(str(ce["entityId"]))
                    ks |= _uuids(ce["entityId"])
            group_member_keys[str(name)] = ks

        def _dev_groups(appliance_id: object, endpoint_id: object) -> list[str]:
            dev_keys: set[str] = set()
            for k in (str(appliance_id), str(endpoint_id)):
                if k and k != "None":
                    dev_keys.add(k)
                    dev_keys |= _uuids(k)
            if not dev_keys:
                return []
            return [n for n, ks in group_member_keys.items() if dev_keys & ks]

        out: list[dict] = []
        if ep_data and ep_data.get("allDevices", {}).get("endpoints"):
            for ep in ep_data["allDevices"]["endpoints"]:
                endpoint_id = ep.get("endpointId")
                la = ep.get("legacyAppliance") or {}
                appliance_id = la.get("applianceId")
                name = ((ep.get("friendlyNameObject") or {}).get("value") or {}).get("text")
                manufacturer = ((ep.get("manufacturer") or {}).get("value") or {}).get("text")
                category = ((ep.get("displayCategories") or {}).get("primary") or {}).get("value")
                reach = None
                for feat in ep.get("features") or []:
                    for prop in feat.get("properties") or []:
                        if "reachability" in (prop.get("name") or "").lower():
                            reach = prop.get("reachabilityStatusValue")
                cv = cv_by_appliance.get(appliance_id) if appliance_id else None
                pdev = phoenix_by_appliance.get(appliance_id) or phoenix_by_deviceid.get(endpoint_id)
                if pdev is None:
                    pdev = _resolve_pd(str(endpoint_id)) if endpoint_id else None
                connected_via = (cv or {}).get("connectedVia") or (pdev or {}).get("connectedVia")
                ent = entity_by_id.get(str(endpoint_id)) or (
                    entity_by_id.get(str(appliance_id)) if appliance_id else None
                )
                availability = (ent or {}).get("availability")
                out.append({
                    "endpointId": endpoint_id,
                    "applianceId": appliance_id,
                    "name": name or (cv or {}).get("friendlyName") or (pdev or {}).get("name"),
                    "category": category or (ent or {}).get("providerData", {}).get("categoryType"),
                    "manufacturer": manufacturer or (cv or {}).get("manufacturerName"),
                    "model": (cv or {}).get("modelName"),
                    "skill": connected_via,
                    "enabled": ep.get("enablement") == "ENABLED",
                    "reachable": (reach or availability),
                    "availability": availability,
                    "groups": _dev_groups(appliance_id, endpoint_id),
                    "details": {
                        "legacyAppliance": cv or {},
                        "phoenix": pdev or {},
                        "entity": ent or {},
                        "endpoint": ep,
                    },
                })
        else:
            # Fallback: nur phoenix
            for pdev in phoenix_devices:
                out.append({
                    "endpointId": pdev.get("deviceId"),
                    "applianceId": pdev.get("applianceId"),
                    "name": pdev.get("name"),
                    "category": None,
                    "manufacturer": pdev.get("manufacturerName"),
                    "model": None,
                    "skill": pdev.get("connectedVia"),
                    "enabled": True,
                    "reachable": None,
                    "availability": None,
                    "groups": _dev_groups(pdev.get("applianceId"), pdev.get("deviceId")),
                    "details": {"phoenix": pdev},
                })
        return out

    async def set_enablement(self, endpoint_id: str, enabled: bool) -> dict:
        data = await self.gql(MUT_ENABLE, {"input": {
            "endpointId": endpoint_id,
            "enablement": "ENABLED" if enabled else "DISABLED_BY_CUSTOMER",
        }})
        return data or {}

    async def rename(self, endpoint_id: str, name: str) -> dict:
        data = await self.gql(MUT_RENAME, {"in": {"endpointId": endpoint_id, "friendlyName": name}})
        return data or {}

    async def delete_device(self, endpoint_id: str, appliance_id: str | None) -> dict:
        """forgetEndpoint (zuverlaessig), Fallback: DELETE /api/phoenix/appliance/{id}."""
        result: dict = {"method": None, "verified": False}
        if endpoint_id:
            try:
                data = await self.gql(MUT_FORGET, {"input": {"endpointId": endpoint_id}})
                result["method"] = "forgetEndpoint"
                result["data"] = data
            except AlexaError as ex:
                result["forgetError"] = str(ex)
        if appliance_id:
            # WICHTIG: applianceId muss encodeURIComponent sein (enthaelt '#'),
            # sonst no-op mit leerem Erfolg.
            try:
                body = await self._raw("delete", f"/api/phoenix/appliance/{quote(appliance_id, safe='')}")
                if result["method"] is None:
                    result["method"] = "phoenix"
                result["phoenix"] = body
            except AlexaError as ex:
                result["phoenixError"] = str(ex)
        forgot = not result.get("forgetError")
        phoenix = not result.get("phoenixError")
        if not forgot and not phoenix:
            raise AlexaError(
                f"Loeschen nicht bestaetigt. forgetEndpoint: {result.get('forgetError')} | "
                f"phoenix: {result.get('phoenixError')}"
            )
        result["verified"] = True
        return result

    # ------------------------------------------------------------------
    # Szenen (aus /api/behaviors/entities - Entities ohne Endpunkt-Zuordnung)
    # ------------------------------------------------------------------

    async def scenes(self) -> list[dict]:
        entities = await self._raw("get", "/api/behaviors/entities",
                                   query={"skillId": "amzn1.ask.1p.smarthome"})
        if not isinstance(entities, list):
            raise AlexaError("Szenenliste hatte unerwartetes Format.")
        # Endpunkt-IDs herausfiltern, um nur Szenen/andere Entities zurueckzulassen
        try:
            ep_data = await self.gql(GQL_ENDPOINTS)
            endpoint_ids = {
                str(e.get("endpointId"))
                for e in (ep_data or {}).get("allDevices", {}).get("endpoints", [])
                if e.get("endpointId")
            }
        except AlexaError:
            endpoint_ids = set()
        out = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            eid = str(ent.get("id") or "")
            etype = str(ent.get("entityType") or "").upper()
            is_scene = "SCENE" in etype or (eid not in endpoint_ids and ent.get("providerData") is None)
            if is_scene or "SCENE" in etype:
                out.append({
                    "id": eid,
                    "name": ent.get("displayName") or ent.get("friendlyName"),
                    "entityType": ent.get("entityType"),
                    "availability": ent.get("availability"),
                    "details": ent,
                })
        return out

    # ------------------------------------------------------------------
    # Gruppen (/api/phoenix/group)
    # ------------------------------------------------------------------

    async def groups(self) -> list[dict]:
        data = await self._raw("get", "/api/phoenix/group")
        out = []
        for g in (data or {}).get("applianceGroups") or []:
            out.append({
                "groupId": g.get("groupId"),
                "name": g.get("name"),
                "type": g.get("type"),
                "applianceIds": g.get("applianceIds") or [],
                "raw": g,
            })
        return out

    async def group_create(self, name: str, appliance_ids: list[str]) -> dict:
        body = await self._raw("post", "/api/phoenix/group", data={
            "name": name, "applianceIds": appliance_ids,
            "type": "SPACE", "defaults": [], "childIds": [],
        })
        if isinstance(body, dict) and body.get("success") is False:
            raise AlexaError(f"Amazon hat die Gruppe nicht erstellt: {body}")
        created = next(
            (g for g in await self.groups() if g["name"] == name), None
        )
        return created or {"name": name, "groupId": None, "applianceIds": appliance_ids}

    async def group_update(self, group_id: str, name: str | None = None,
                           appliance_ids: list[str] | None = None) -> dict:
        current = next((g for g in await self.groups() if g["groupId"] == group_id), None)
        if not current:
            raise AlexaError(f"Gruppe {group_id} nicht gefunden.")
        body = {
            "name": name or current["name"],
            "applianceIds": appliance_ids if appliance_ids is not None else current["applianceIds"],
            "type": current.get("type") or "SPACE",
            "defaults": (current.get("raw") or {}).get("defaults") or [],
            "childIds": (current.get("raw") or {}).get("childIds") or [],
        }
        await self._raw("put", f"/api/phoenix/group/{quote(group_id, safe='')}", data=body)
        return next((g for g in await self.groups() if g["groupId"] == group_id), None)

    async def group_delete(self, group_id: str) -> dict:
        body = await self._raw("delete", f"/api/phoenix/group/{quote(group_id, safe='')}")
        return body if isinstance(body, dict) else {"success": True}

    # ------------------------------------------------------------------
    # Routinen
    # ------------------------------------------------------------------

    async def routines(self) -> list[dict]:
        data = await self._raw("get", "/api/behaviors/v2/automations", query={"limit": 2000})
        return [r for r in (data or []) if isinstance(r, dict)]

    async def routine_get(self, automation_id: str) -> dict:
        data = await self._raw("get", f"/api/behaviors/automations/{quote(automation_id, safe='')}")
        if not isinstance(data, dict) or not data:
            raise AlexaError(f"Routine {automation_id} nicht gefunden.")
        return data

    async def _routine_write_body(self, name: str, status: str, triggers: list[dict],
                                  sequence: dict, behavior_id: str | None) -> dict:
        trigger_jsons = [json.dumps(t) for t in triggers]
        body: dict = {
            "name": name,
            "status": status,
            "triggerJson": trigger_jsons[0] if trigger_jsons else "{}",
            "triggerJsonList": trigger_jsons,
            "sequenceJson": json.dumps(sequence),
        }
        if behavior_id:
            body["behaviorId"] = behavior_id
        return body

    @staticmethod
    def _reencode_triggers(triggers: list[dict]) -> list[dict]:
        """Lese-Trigger (payload als Objekt) in Schreib-Form (payload als JSON-String)."""
        out = []
        for t in triggers or []:
            payload = t.get("payload")
            out.append({
                "@type": TYPE_JAVA_TRIGGER,
                "id": None,
                "skillId": t.get("skillId"),
                "type": t.get("type"),
                "payload": payload if isinstance(payload, str) else json.dumps(payload),
            })
        return out

    @staticmethod
    def _rebuild_sequence(node) -> dict:
        """Sequenzbaum in Schreib-Form bringen (Struktur erhalten)."""
        if not isinstance(node, dict):
            return {"@type": TYPE_SEQUENCE, "startNode": node}
        if "startNode" in node:
            return {"@type": TYPE_SEQUENCE, "startNode": node["startNode"]}
        return {"@type": TYPE_SEQUENCE, "startNode": node}

    async def _validate_operation(self, op_type: str, operation_payload: dict) -> dict:
        body = await self._raw("post", "/api/behaviors/operation/validate", data={
            "type": op_type,
            "operationPayload": json.dumps(operation_payload),
        })
        if not isinstance(body, dict):
            raise AlexaError("Validate: keine Antwort.")
        if body.get("result") and body["result"] != "VALID":
            raise AlexaError(f"Aktion nicht gueltig ({body.get('result')}): {body.get('message', '')}")
        op = body.get("operationPayload")
        if isinstance(op, str):
            try:
                op = json.loads(op)
            except (json.JSONDecodeError, ValueError):
                pass
        return op if op is not None else operation_payload

    async def routine_create(self, name: str, trigger: dict, actions: list[dict],
                             status: str = "ENABLED") -> dict:
        """Neue Routine anlegen.

        trigger: {"type": "CustomUtterance"|"AbsoluteTimeSchedule", ...} bereits in
                 Lese-Form (payload Objekt) ODER fertiger Lese-Trigger.
        actions: [{"type": "Alexa.TextCommand", "operationPayload": {...}}, ...]
        """
        account = await self.account()
        ctx = {
            "customerId": account["customerId"],
            "marketplaceId": account["marketplaceId"],
            "locale": account["locale"],
        }
        # Trigger normalisieren (payload muss JSON-STRING sein - doppelkodiert)
        trig = trigger
        if isinstance(trig.get("payload"), dict):
            trig = {**trig, "payload": json.dumps(trig["payload"])}
        if "payload" not in trig:
            if trig.get("type") == "CustomUtterance":
                trig["payload"] = json.dumps({
                    "@type": TYPE_UTTER_PAYLOAD,
                    "locale": ctx["locale"],
                    "marketplaceId": ctx["marketplaceId"],
                    "utterance": trig.get("utterance", ""),
                    "utterances": [trig.get("utterance", "")],
                    "customerId": ctx["customerId"],
                    "person": None,
                })
            else:
                raise AlexaError("Trigger ohne payload und ohne bekannte Art.")
        trig = {
            "@type": TYPE_JAVA_TRIGGER,
            "id": None,
            "skillId": trig.get("skillId"),
            "type": trig.get("type") or "CustomUtterance",
            "payload": trig["payload"],
        }

        # Aktionen validieren (operationPayload muss server-normalisiert sein)
        nodes = []
        for a in actions:
            op_type = a.get("type")
            op = dict(a.get("operationPayload") or {})
            if op.get("customerId") is None:
                op["customerId"] = ctx["customerId"]
            if op.get("locale") is None:
                op["locale"] = ctx["locale"]
            normalized = await self._validate_operation(op_type, op)
            nodes.append({
                "@type": TYPE_OP_NODE,
                "type": op_type,
                "skillId": a.get("skillId") or ACTION_SKILL.get(op_type),
                "operationPayload": normalized,
                "context": None,
            })
        start_node = nodes[0] if len(nodes) == 1 else {"@type": TYPE_SERIAL_NODE, "nodesToExecute": nodes}
        sequence = {"@type": TYPE_SEQUENCE, "startNode": start_node}

        body = self._routine_write_body(name, status, [trig], sequence, None)
        result = await self._raw(
            "post", "/api/behaviors/automations",
            data=body, headers={"Routines-Version": ROUTES_VERSION},
        )
        if isinstance(result, dict) and result.get("message") and "automationId" not in result:
            raise AlexaError(f"Routine nicht erstellt: {result.get('message')}")
        return result if isinstance(result, dict) else {}

    async def routine_update(self, automation_id: str, name: str | None = None,
                             status: str | None = None,
                             trigger: dict | None = None,
                             action_overrides: list[dict] | None = None) -> dict:
        """Routine an der Stelle aktualisieren (vollstaendiger Write-Body)."""
        routine = await self.routine_get(automation_id)
        name = name or routine.get("name")
        status = status or routine.get("status") or "ENABLED"
        triggers = self._reencode_triggers(routine.get("triggers") or [])
        if trigger is not None:
            # CustomUtterance-Trigger austauschen
            trig = dict(trigger)
            if isinstance(trig.get("payload"), dict):
                trig["payload"] = json.dumps(trig["payload"])
            triggers = [{
                "@type": TYPE_JAVA_TRIGGER,
                "id": None,
                "skillId": trig.get("skillId"),
                "type": trig.get("type") or (triggers[0]["type"] if triggers else "CustomUtterance"),
                "payload": trig["payload"],
            }]
        seq = self._rebuild_sequence(routine.get("sequence"))
        if action_overrides is not None:
            # operationPayloads ersetzen (validiert)
            nodes = []
            for a in action_overrides:
                op_type = a.get("type")
                op = dict(a.get("operationPayload") or {})
                normalized = await self._validate_operation(op_type, op)
                nodes.append({
                    "@type": TYPE_OP_NODE,
                    "type": op_type,
                    "skillId": a.get("skillId"),
                    "operationPayload": normalized,
                    "context": None,
                })
            start_node = nodes[0] if len(nodes) == 1 else {"@type": TYPE_SERIAL_NODE, "nodesToExecute": nodes}
            seq = {"@type": TYPE_SEQUENCE, "startNode": start_node}
        body = self._routine_write_body(name, status, triggers or [{}], seq, automation_id)
        result = await self._raw(
            "put", f"/api/behaviors/automations/{quote(automation_id, safe='')}",
            data=body, headers={"Routines-Version": ROUTES_VERSION},
        )
        return result if isinstance(result, dict) else {}

    async def routine_set_enabled(self, automation_id: str, enabled: bool) -> dict:
        """Aktivieren/Deaktivieren = Write-Body mit umgeschalteter status (verifiziert)."""
        return await self.routine_update(automation_id, status="ENABLED" if enabled else "DISABLED")

    async def routine_delete(self, automation_id: str) -> dict:
        """Loeschen: DELETE /api/behaviors/automations/{id} + Verifikation."""
        result = await self._raw("delete", f"/api/behaviors/automations/{quote(automation_id, safe='')}")
        still = [r for r in await self.routines() if r.get("automationId") == automation_id]
        return {
            "deleted": not still,
            "response": result if isinstance(result, (dict, list)) else (result or None),
        }

    async def routine_run(self, automation_id: str, serial_number: str | None = None) -> dict:
        """Routine sofort ausfohren (PREVIEW-Verhalten auf Ziel-Echo)."""
        routines = await self.routines()
        routine = next((r for r in routines if r.get("automationId") == automation_id), None)
        if not routine or not routine.get("sequence"):
            raise AlexaError(f"Routine {automation_id} nicht gefunden (oder ohne Sequenz).")
        account = await self.account()
        echoes = account["echoes"]
        target = next((e for e in echoes if e["serialNumber"] == serial_number), None) or echoes[0]
        seq_str = json.dumps(routine["sequence"])
        seq_str = (
            seq_str.replace("ALEXA_CURRENT_DSN", target["serialNumber"])
            .replace("ALEXA_CURRENT_DEVICE_TYPE", target["deviceType"])
        )
        seq = json.loads(seq_str)
        await self._raw("post", "/api/behaviors/preview", data={
            "behaviorId": "PREVIEW",
            "status": "ENABLED",
            "sequenceJson": json.dumps(seq),
        })
        return {"target": target["serialNumber"], "targetName": target["name"]}


# Singleton
session = AlexaSession()
