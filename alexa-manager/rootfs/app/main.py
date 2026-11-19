"""Alexa Manager - FastAPI-Entry-Point des Home-Assistant-Add-ons."""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse, RedirectResponse, Response

from alexa_client import (
    DATA_DIR,
    AlexaError,
    SessionNotReady,
    session,
)
from amazon_proxy import ASSET_RE, API_USER_AGENT, PROXY_HOSTS, _REQ_DROP, _RES_DROP

# Optional: Upstream-Hosts umleiten (Test/Debug), z. B.
# AM_PROXY_UPSTREAM_MAP='{"www.amazon.com": "http://127.0.0.1:18642"}'
try:
    UPSTREAM_MAP: dict[str, str] = (
        _json.loads(os.environ.get("AM_PROXY_UPSTREAM_MAP", ""))
        if os.environ.get("AM_PROXY_UPSTREAM_MAP")
        else {}
    )
except Exception:
    UPSTREAM_MAP = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("alexa-manager")

VERSION = "1.1.19"

# alexapy-Details (Login-Flow, Seiten, Fehler) in Datei + In-Memory-Puffer
from collections import deque

_log_lines: deque = deque(maxlen=1000)


class _MemHandler(logging.Handler):
    def emit(self, record):
        try:
            _log_lines.append(self.format(record))
        except Exception:
            pass


_fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
try:
    _log_file = DATA_DIR / "alexa_manager.log"
    _fh = logging.FileHandler(str(_log_file), encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(_fmt)
    logging.getLogger().addHandler(_fh)
except Exception:
    pass
_mem_handler = _MemHandler()
_mem_handler.setLevel(logging.DEBUG)
_mem_handler.setFormatter(_fmt)
logging.getLogger().addHandler(_mem_handler)
logging.getLogger("alexapy").setLevel(logging.DEBUG)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Alexa Manager startet (Datenverzeichnis: %s)", DATA_DIR)
    await session.restore()
    yield
    try:
        if session.login is not None:
            await session.login.close()
    except Exception:
        pass
    await session.close()


app = FastAPI(title="Alexa Manager", version=VERSION, lifespan=lifespan)


def _err(ex: Exception) -> dict:
    return {"error": str(ex), "state": session.status()["state"]}


def _guard() -> None:
    if session.state != "ready":
        raise HTTPException(
            status_code=401,
            detail="Nicht angemeldet. Bitte in den Einstellungen Amazon-Konto verbinden.",
        )


# ---------------------------------------------------------------------------
# Modelle
# ---------------------------------------------------------------------------


class LoginReq(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    domain: str | None = None


class CodeReq(BaseModel):
    code: str = Field(min_length=4)


class OptionReq(BaseModel):
    option: str


class DeviceEnableReq(BaseModel):
    enabled: bool


class RenameReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DeleteDeviceReq(BaseModel):
    endpointId: str | None = None
    applianceId: str | None = None


class GroupCreateReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    applianceIds: list[str] = []


class GroupUpdateReq(BaseModel):
    name: str | None = None
    applianceIds: list[str] | None = None


class RoutineAction(BaseModel):
    type: str
    operationPayload: dict = {}
    skillId: str | None = None


class RoutineCreateReq(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Trigger in Lese-Form: {"type": "CustomUtterance", "utterance": "..."}
    #                       {"type": "AbsoluteTimeSchedule", "time": "07:30",
    #                        "days": ["MO","TU"], "timeZoneId": "Europe/Berlin"}
    trigger: dict
    actions: list[RoutineAction] = Field(min_length=1)
    status: str = "ENABLED"


class RoutineUpdateReq(BaseModel):
    name: str | None = None
    status: str | None = None
    trigger: dict | None = None
    actionOverrides: list[RoutineAction] | None = None


class RunReq(BaseModel):
    serialNumber: str | None = None


# ---------------------------------------------------------------------------
# Konto / Login
# ---------------------------------------------------------------------------


@app.get("/api/status")
async def api_status():
    out = {**session.status(), "version": VERSION}
    p = session.proxy
    if p is not None:
        out["proxy"] = {
            "active": not p.done,
            "done": p.done,
            "lastEvent": (p.last_event or "")[:400],
            "events": p.events[-25:],
            "cookieCount": len(p.cookies),
            "cookieNames": sorted(p.cookies.keys())[:40],
            "resultCaptured": bool(p.result),
            "hasCode": bool(p.result and p.result.get("authorization_code")),
        }
    return out


@app.get("/api/debug")
async def api_debug():
    """Diagnose (nur fuer Troubleshooting): letztes Amazon-Antwort-HTML + Log-Schwanz."""
    out: dict = {
        "version": VERSION,
        "state": session.state,
        "detail": session.state_detail,
        "loginStatus": dict(session.login.status) if session.login is not None and session.login.status else None,
    }
    if session.proxy is not None:
        p = session.proxy
        out["proxy"] = {
            "active": not p.done,
            "prefix": p.proxy_prefix,
            "lastEvent": p.last_event,
            "events": p.events[-40:],
            "cookieNames": sorted(p.cookies.keys()),
            "resultCaptured": bool(p.result),
        }
    if session.state == "ready":
        try:
            raw_phoenix = await session._raw("get", "/api/phoenix")
            out["rawPhoenix"] = _json.dumps(raw_phoenix, ensure_ascii=False)[:15000]
        except Exception as ex:
            out["rawPhoenixError"] = str(ex)
        # Diagnose: Kandidaten-Pfade direkt mit Status + Korper-Vorschau
        probe = {}
        for p in ("/api/phoenix", "/api/phoenix/device", "/api/devices",
                  "/api/phoenix/group"):
            try:
                async with session._ensure_http().request(
                    "GET", f"https://{session._api_host}{p}",
                    headers={
                        "User-Agent": API_USER_AGENT,
                        "Accept": "application/json; charset=utf-8",
                        "Accept-Language": "de-DE",
                        "Referer": f"https://{session._api_host}/spa/index.html",
                        "Origin": f"https://{session._api_host}",
                        "Host": session._api_host,
                        "Cookie": session._cookie,
                        "csrf": session._csrf or "",
                    },
                ) as resp:
                    text = await resp.text()
                    probe[p] = {"status": resp.status, "len": len(text),
                                "head": text[:200]}
            except Exception as ex:
                probe[p] = f"ERR {ex}"
        out["rawProbe"] = probe
    lg = session.login
    if lg is not None:
        try:
            lr = lg.lastreq
            if lr is not None:
                out["lastUrl"] = str(lr.url)
                out["lastStatus"] = lr.status
                try:
                    out["lastHtml"] = (await lr.text())[:60000]
                except Exception as ex:
                    out["lastHtml"] = f"<Body nicht mehr verfuegbar: {ex}>"
        except Exception as ex:
            out["lastError"] = str(ex)
    tail = "\n".join(list(_log_lines)[-500:])
    out["logTail"] = tail[-30000:]
    return out


@app.get("/api/logs")
async def api_logs(lines: int = 400):
    """Log-Datei-Schwanz (/data/alexa_manager.log) - fuer Diagnose.

    Enthaealt nur Log-Zeilen (keine Tokens/Passwoerter: der Proxy loggt
    keine Cookie-Werte, nur Methoden/Pfade/Status/Redirect-Ziele).
    """
    n = max(1, min(lines, 2000))
    out: dict = {"file": None, "lines": ""}
    try:
        _log_file = DATA_DIR / "alexa_manager.log"
        if _log_file.exists():
            data = _log_file.read_bytes()
            keep = data[-400_000:]
            raw = keep.decode("utf-8", "replace")
            ls = raw.splitlines()
            out["lines"] = "\n".join(ls[-n:])
            out["file"] = str(_log_file)
            out["bytes"] = len(data)
    except Exception as ex:
        out["error"] = str(ex)
    return out


@app.post("/api/login")
async def api_login(req: LoginReq):
    try:
        await session.login_start(req.email, req.password, req.domain)
        return session.status()
    except Exception as ex:
        log.exception("Login fehlgeschlagen")
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@app.post("/api/login/code")
async def api_login_code(req: CodeReq):
    try:
        await session.submit_code(req.code)
        return session.status()
    except AlexaError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@app.post("/api/login/option")
async def api_login_option(req: OptionReq):
    try:
        await session.submit_option(req.option)
        return session.status()
    except AlexaError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@app.post("/api/logout")
async def api_logout():
    await session.logout()
    return session.status()


@app.get("/api/account")
async def api_account():
    _guard()
    try:
        return await session.account()
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


# ---------------------------------------------------------------------------
# Gerate
# ---------------------------------------------------------------------------


@app.get("/api/devices")
async def api_devices():
    _guard()
    try:
        return await session.devices()
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/devices/enable")
async def api_device_enable(payload: dict):
    _guard()
    req = DeviceEnableReq(**payload)
    endpoint_id = payload.get("endpointId")
    try:
        return await session.set_enablement(endpoint_id, req.enabled)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/devices/rename")
async def api_device_rename(payload: dict):
    _guard()
    req = RenameReq(**payload)
    endpoint_id = payload.get("endpointId")
    try:
        return await session.rename(endpoint_id, req.name)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/devices/delete")
async def api_device_delete(payload: dict):
    _guard()
    req = DeleteDeviceReq(**payload)
    try:
        return await session.delete_device(req.endpointId, req.applianceId)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


# ---------------------------------------------------------------------------
# Szenen
# ---------------------------------------------------------------------------


@app.get("/api/scenes")
async def api_scenes():
    _guard()
    try:
        return await session.scenes()
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


# ---------------------------------------------------------------------------
# Gruppen
# ---------------------------------------------------------------------------


@app.get("/api/groups")
async def api_groups():
    _guard()
    try:
        return await session.groups()
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/groups")
async def api_group_create(req: GroupCreateReq):
    _guard()
    try:
        return await session.group_create(req.name, req.applianceIds)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.put("/api/groups/{group_id}")
async def api_group_update(group_id: str, req: GroupUpdateReq):
    _guard()
    try:
        return await session.group_update(group_id, req.name, req.applianceIds)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.delete("/api/groups/{group_id}")
async def api_group_delete(group_id: str):
    _guard()
    try:
        return await session.group_delete(group_id)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


# ---------------------------------------------------------------------------
# Routinen
# ---------------------------------------------------------------------------


@app.get("/api/routines")
async def api_routines():
    _guard()
    try:
        return await session.routines()
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.get("/api/routines/{automation_id}")
async def api_routine_get(automation_id: str):
    _guard()
    try:
        return await session.routine_get(automation_id)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/routines")
async def api_routine_create(req: RoutineCreateReq):
    _guard()
    try:
        return await session.routine_create(req.name, req.trigger, [a.model_dump() for a in req.actions], req.status)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.put("/api/routines/{automation_id}")
async def api_routine_update(automation_id: str, req: RoutineUpdateReq):
    _guard()
    try:
        return await session.routine_update(
            automation_id,
            name=req.name,
            status=req.status,
            trigger=req.trigger,
            action_overrides=[a.model_dump() for a in req.actionOverrides] if req.actionOverrides else None,
        )
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.delete("/api/routines/{automation_id}")
async def api_routine_delete(automation_id: str):
    _guard()
    try:
        return await session.routine_delete(automation_id)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


@app.post("/api/routines/{automation_id}/run")
async def api_routine_run(automation_id: str, payload: dict | None = None):
    _guard()
    req = RunReq(**(payload or {}))
    try:
        return await session.routine_run(automation_id, req.serialNumber)
    except (AlexaError, SessionNotReady) as ex:
        raise HTTPException(status_code=401 if isinstance(ex, SessionNotReady) else 502, detail=str(ex)) from ex


# ---------------------------------------------------------------------------
# Browser-Login: Reverse-Proxy zu Amazon (wie alexa-mcp "npm run auth")
# ---------------------------------------------------------------------------

SUCCESS_HTML = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alexa Manager - Angemeldet</title>
<style>
body{font-family:'Segoe UI',system-ui,sans-serif;background:#f4f6f8;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;color:#263238}
.card{background:#fff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.08);padding:36px 40px;max-width:460px;text-align:center}
.ok{width:64px;height:64px;border-radius:50%;background:#e8f5e9;color:#2e7d32;display:flex;align-items:center;justify-content:center;margin:0 auto 18px}
h1{font-size:20px;margin:0 0 10px}
p{font-size:14px;line-height:1.5;color:#546e7a;margin:0 0 8px}
</style></head><body>
<div class="card">
  <div class="ok"><svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></div>
  <h1>Amazon-Anmeldung erfolgreich</h1>
  <p>Dieses Tab kann geschlossen werden.</p>
  <p>Im <b>Alexa Manager</b>-Panel wird die Verbindung automatisch uebernommen:
  Refresh-Token und Cookies werden gespeichert, kein Passwort.</p>
</div></body></html>"""


@app.post("/api/proxy/login/start")
async def api_proxy_start(request: Request):
    """Browser-Login vorbereiten; liefert die URL, die im neuen Tab geoeffnet wird."""
    panel_url = request.headers.get("x-panel-url") or request.headers.get("referer")
    try:
        st = session.start_proxy(panel_url, request.headers.get("host"))
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    return {"url": st.start_url(), "session": st.sess}


@app.api_route("/proxy", methods=["GET"])
@app.api_route("/proxy/", methods=["GET"])
async def proxy_root():
    st = session.proxy
    if st is None or st.done:
        return Response(
            "Kein aktives Amazon-Login. Bitte in den Einstellungen "
            "'Amazon-Login im Browser starten' ausloesen.",
            status_code=404,
        )
    return RedirectResponse(st.start_url(), status_code=302)


@app.get("/proxy/{sess}/cookie-success")
async def proxy_cookie_success(sess: str):
    st = session.proxy
    if st is None or st.sess != sess or not st.done:
        return Response("Anmeldung noch nicht finalisiert.", status_code=404)
    return HTMLResponse(SUCCESS_HTML)


@app.api_route("/proxy/{sess}/{host}/{rest:path}",
               methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_amazon(sess: str, host: str, rest: str, request: Request):
    """Einzelner Proxy-Request: Browser <-> Amazon (mit URL-/Cookie-Rewrites)."""
    st = session.proxy
    if st is None or st.sess != sess or st.done:
        return Response("Dieses Login-Fenster ist nicht (mehr) aktiv.", status_code=404)
    if host not in PROXY_HOSTS:
        return Response(f"Host wird nicht proxied: {host}", status_code=403)

    raw_query = request.url.query
    if isinstance(raw_query, bytes):
        raw_query = raw_query.decode("utf-8", "replace")
    query = st.fix_qs(raw_query) if raw_query else ""
    upstream = f"{UPSTREAM_MAP.get(host, 'https://' + host)}/{rest}"
    if query:
        upstream += "?" + query

    # Request-Header an Amazon (Proxy-URLs zurueckgeschrieben)
    headers: dict[str, str] = {}
    for k, v in request.headers.items():
        if k.lower() in _REQ_DROP:
            continue
        headers[k] = v
    headers["accept-encoding"] = "identity"
    headers["origin"] = f"https://{host}"
    ref = request.headers.get("referer")
    if ref:
        headers["referer"] = st.rewrite_in(ref)
    cookie_in = request.headers.get("cookie", "")
    headers["cookie"] = st.browser_cookie_header(cookie_in)

    body = await request.body()
    ctype = request.headers.get("content-type", "")
    if body and request.method in ("POST", "PUT") and "application/x-www-form-urlencoded" in ctype:
        try:
            pairs = parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True)
            body = urlencode([(k, st.rewrite_in(v)) for k, v in pairs]).encode("utf-8")
        except Exception:
            pass

    if not ASSET_RE.search(rest or ""):
        log.info("Proxy: %s %s/%s%s", request.method, host, rest,
                 (f"?{query[:80]}" if query else ""))
        st.record(f"REQ {request.method} {host}/{rest}"
                  + (f"?{query[:200]}" if query else ""))

    try:
        # WICHTIG: Redirects NICHT folgen - der Browser muss jeden 302-Schritt
        # selbst ablaufen (Cookies + finaler maplanding-Redirect)
        async with session._ensure_http().request(
            request.method, upstream, headers=headers, data=body or None,
            allow_redirects=False
        ) as up:
            set_cookies = (
                up.headers.getall("set-cookie")
                if "set-cookie" in up.headers
                else []
            )
            st.absorb_set_cookies(set_cookies)
            st.absorb_request_cookie(cookie_in)

            location = up.headers.get("location")
            if not ASSET_RE.search(rest or ""):
                log.info("Proxy-RES: %s %s %s%s%s", up.status, request.method,
                         host, rest,
                         (f" -> {location[:200]}" if location else ""))
                st.record(f"RES {up.status} {host}/{rest}"
                          + (f" -> {location[:300]}" if location else ""))

            if st.detect_success(f"https://{host}/{rest}" + (f"?{query}" if query else ""),
                                 location):
                log.info("Proxy: Login-Erfolg erkannt (Code: %d Zeichen)",
                         len((st.result or {}).get("authorization_code", "")))
                if location and "?" in location:
                    oa2 = [k for k, _ in parse_qsl(location.split("?", 1)[1])
                           if k.startswith("openid.oa2")]
                    log.info("Proxy: OA2-Parameter im maplanding: %s",
                             ", ".join(oa2) or "(keine!)")
                asyncio.create_task(session.finalize_proxy_login())
                return RedirectResponse(f"{st.proxy_prefix}/cookie-success", status_code=302)

            out_headers: dict[str, str] = {}
            for k, v in up.headers.items():
                lk = k.lower()
                if lk in _RES_DROP or lk == "set-cookie":
                    continue
                if lk == "location":
                    if location:
                        if "://" in location:
                            # absolute (http/https) -> Hosts auf Proxy umschreiben
                            out_headers["location"] = st.rewrite_out(location)
                        elif location.startswith("//"):
                            # protokoll-relativ: als https behandeln
                            out_headers["location"] = st.rewrite_out("https:" + location)
                        elif location.startswith("/"):
                            # path-absolut (z. B. "/ax/claim"): Browser wuerde
                            # es an den HA-Root senden -> Proxy-Praefix ergaenzen
                            out_headers["location"] = f"{st.proxy_prefix}/{host}{location}"
                        else:
                            # relativer Pfad ohne Slash
                            out_headers["location"] = f"{st.proxy_prefix}/{host}/{location}"
                    continue
                out_headers[k] = v

            resp_body = await up.read()
            resp_ctype = up.headers.get("content-type", "")
            if (not ASSET_RE.search(rest or "")) and (
                "text/html" in resp_ctype or "xhtml" in resp_ctype
            ):
                try:
                    resp_body = st.rewrite_out_body(
                        resp_body.decode("utf-8", "replace"), host
                    ).encode("utf-8")
                except (UnicodeDecodeError, LookupError):
                    pass
            resp = Response(content=resp_body, status_code=up.status,
                            headers=out_headers)
            for raw in set_cookies:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                resp.headers.append("set-cookie",
                                    st.rewrite_set_cookie_for_browser(raw))
            return resp
    except aiohttp.ClientError as ex:
        log.warning("Proxy-Fehler: %s", ex)
        return Response(f"Proxy-Fehler: {ex}", status_code=502)


# ---------------------------------------------------------------------------
# Static (Panel)
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
