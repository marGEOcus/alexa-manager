## 1.2.2 (2026-11-22)
- Umbenennen: Namen mit Sonderzeichen (z. B. @, Klammern) werden vorab erkannt und mit klarer Meldung abgelehnt – Amazon erlaubt nur Buchstaben, Zahlen, Leerzeichen und Apostrophe

# Changelog

## 1.2.1 (2026-11-19)
- Routinen: Spalten „Name" und „Trigger" sind jetzt sortierbar (wie in der Geräte-Tabelle)

## 1.2.0 (2026-11-19)
- Panels „Szenen" und „Gruppen" entfernt (Gruppen-Zugehörigkeit bleibt in den Gerätedetails/-Filtern sichtbar)
- Routinen: neue Tabelle im Geräte-Layout (gleiche Zeilenhöhe) mit Spalten Name, Trigger, Aktionen (Anzahl) und Steuerung
- Routinen-Zeile: Buttons zum Ausführen (Play), Aktivieren/Deaktivieren und Löschen (gleiche Größe wie in der Geräte-Tabelle)
- Routinen „Bearbeiten" und „Neu anlegen" entfernt (Routinen bleiben der Alexa-App vorbehalten)
- Sidebar-Icon: `mdi:emoticon-happy-outline`

## 1.1.19 (2026-11-19)
- "Alle"-Checkbox von der Titelbar in den Tabellen-Header verlegt (links neben "Name", über allen Zeilen-Checkboxen)
- Echo-Anzeige/-Filter jetzt anhand des Rohdateneintrags "value": "ALEXA_VOICE_ENABLED" (displayCategories.primary) – vorher 0 Treffer
- Button "Gruppe zuordnen" aus der Bottombar entfernt (Zuordnung über die Amazon-API funktionierte nicht)
- Detail-Ansicht (Drawer) hat jetzt einen sichtbaren Schließen-Button

## 1.1.18 (2026-11-18)
- Detail-Ansicht: Titelzeile jetzt exakt 56 px (bündig mit der Topbar)
- Seitenüberschriften (Übersicht, Geräte, Szenen, Gruppen, Routinen, Einstellungen) entfernt – mehr Platz im Panel
- Geräte: "Neu laden" wandert in die Bottombar (rechts); die Titelzeile entfällt komplett
- Geräte-Seite ist jetzt der Standard-Tab (Klick auf "Alexa Manager" öffnet direkt Geräte)

## 1.1.17 (2026-11-18)
- Geräte-Tabelle: Checkbox in der ersten Spalte (vor dem Namen)
- Bottombar mit Bulk-Aktionen (nur aktiv bei ≥1 Auswahl): Löschen (rot), Gruppe zuordnen (Popup: bestehende Gruppe wählen oder neue anlegen), Deaktivieren, Aktivieren – Buttons schwarz, nur Löschen rot
- Titelbar: Checkbox „Alle" wählt alle Geräte des aktuellen Filters an/ab (nur im Geräte-Tab sichtbar)
- Stat-Anzeigen (Gesamt, Online, Offline, Unbekannt, Echos, Gruppen) sind jetzt klickbare Filter + neue Anzeige „Home Assistant"
- Alte kleine Filterbuttons unter dem Suchfeld entfernt
- Suchfeld jetzt abgerundetes Rechteck (wie Combobox/Tabelle)
- Drei Filter-Combos rechts neben dem Suchfeld (gleiche Breite): Gruppen, Gerätetypen, Status (inkl. Aktiviert/Deaktiviert); die alte tabellebreite Gruppen-Combobox entfällt
- Nur die Tabelle scrollt: Filterzeile und Bottombar bleiben immer sichtbar

## 1.1.16 (2026-11-17)
- Sidebar-Icon auf `mdi:face-agent` (Alexa-Smile), da `mdi:amazon-alexa` im Icon-Set von HA 2026.11 fehlt
- HA-Farben werden jetzt auch im manuellen Modus (Dunkel/Hell) 1:1 übernommen, wenn sie zur gewählten Helligkeit passen → kein bläuliches Eigen-Theme mehr
- Header exakt 56 px (wie HA-Header) und fix; nur der Inhalt scrollt, Titelbar bleibt sichtbar

## 1.1.15 (2026-11-17)

- **Gruppen-Filter endgueltig funktionsfaehig:** Die Gruppen-Antwort
  bringt in `chrEndpoints[].entityId` die UUIDs der neuen Endpunkte –
  die direkten Bruecke zwischen alten SKILL_-Gruppen und den neuen
  endpointIds. Damit zeigen alle Gruppen ihre Mitglieder an
  (z. B. Wohnzimmer → Fenster, Licht, Katzenbaum, …). Phoenix bleibt
  als Reserve (ist beim Amazon oft rate-limited, Status 299).

## 1.1.14 (2026-11-17)

- `/api/debug` erweitert um einen Raw-Path-Probe-Block
  (Status/Body-Vorschau von Phoenix-/Device-Endpunkten) zur
  Diagnose der Gruppen-Mapping-Datenquelle.

## 1.1.13 (2026-11-17)

- **Gruppen-Filter funktional gefixt:** Die alten Amazon-Gruppen tragen
  applianceIds im altem Format (SKILL_…/JSON), die neuen Endpunkte aber
  nur endpointIds ohne legacyAppliance.applianceId – die Zuordnung
  scheiterte, jede Gruppe zeigte 0 Geräte. Jetzt brückt die Auflösung
  über Phoenix-Geräte (applianceId ↔ deviceId) + UUID-Muster; Geräte
  können mehreren Gruppen zugeordnet sein.
- Gruppen-DIALOG: Mitglieder von bestehenden Gruppen werden korrekt
  vorgeprüft (auch alte SKILL_-Gruppen).
- `/api/debug` liefert zusätzlich den rohen Phoenix-Dump (Diagnose).

## 1.1.12 (2026-11-17)

- **Icon-Fix (Wurzelursache):** Die Icon-Pfade wurden ohne `<path>`-
  Wrapper in das `<svg>` eingebettet → der Browser renderte nichts
  (leere Buttons). Jetzt werden rohe Pfad-Daten korrekt in `<path>`
  gewickelt: Alle Icons (Zeilen-Buttons, Stat-Cards, Suche,
  "Neu laden", Tabs) sind wieder sichtbar.
- **Panel passt exakt zum HA-Theme:** In System-Mode übernimmt das
  Panel die HA-Theme-Variablen (Hintergrund, Karten, Linien, Text,
  Akzent) 1:1 aus dem HA-Kontext – schwarzes HA → schwarzes Panel,
  auch bei Custom-Theme. Theme-Wechsel in HA wird live übernommen.
- **Theme beim ersten Klick korrekt:** Das HA-Theme wird schon vor
  dem Body-Render ausgelesen (Hex- und RGB-Helligkeit) – kein
  heller Flicker mehr.
- **Gruppen-Filter:** Dropdown "Alle Gruppen" im Geräte-Panel;
  filtert Geräte nach ihrer Alexa-Gruppe.

## 1.1.11 (2026-11-17)

- **Online/Offline korrigiert:** `reachabilityStatusValue` ("OK"/
  "UNREACHABLE") wird jetzt richtig ausgewertet – "OK" heißt online
  (war vorher "Unbekannt"). Betrifft Status-Spalte, Stat-Cards,
  Filter und die Übersicht.
- **Sortierung:** Spaltenheader (Name, Beschreibung, Typ, Status, ID)
  sind klickbar; zweiter Klick kehrt die Richtung um (↑/↓).
- **Neuer Filter "Home Assistant"** (Hersteller aus den Rohdaten).
- **"Filter löschen"**-Button (×) im Suchfeld von Geräten und Routinen.
- **Theme "System"** folgt jetzt dem Home-Assistant-Theme (wird aus
  dem HA-Kontext gelesen), nicht nur dem Betriebssystem.
- Drawer-Buttons (Aktivieren/Umbenennen/Löschen) mit Hover-Hinweisen.

## 1.1.10 (2026-11-17)

- **Geräte-Ansicht neu (Aura-Device-Master-Style):** kompakte Zeilen,
  Stat-Cards (Gesamt/Online/Offline/Unbekannt/Echos/Gruppen), Spalten
  Name · Beschreibung · Typ (Badge) · Status (2 Zeilen) · Quelle · ID
  (monospace, gekürzt) · Aktionen (Aktiv/Schalter + Löschen) pro Zeile.
- **Such-/Filter-Fix:** Geräte- und Routinen-Suche aktualisieren jetzt
  nur die Zeilen, nicht das ganze Panel – der Input verliert weder
  Fokus noch Zeichen beim Tippen.

## 1.1.9 (2026-11-17)

- **Fix: Crash bei fehlendem Set-Cookie** – multidict >= 6.9 wirft bei
  `headers.getall()` einen KeyError; das Register-Resultat ohne
  Set-Cookie-Header crashed die Finalisierung (der Login-Code war
  bereits korrekt erfasst).
- **Diagnose:** Register-Aufruf loggt HTTP-Status + Groesse;
  maplanding-Loggt die OA2-Parameter (ohne den Code selbst).
- **Panel:** ueberwacht das Login-Fenster; nach dem Schliessen des
  Tabs sofortiger Status-Refresh + kurzes Schnell-Polling;
  Diagnose-Box zeigt neue Proxy-Schritte live an.
- Fehlender Autorisierungs-Code liefert jetzt eine eindeutige
  Fehlermeldung (stattdessen blindem Register-Versuch).

## 1.1.8 (2026-11-17)

- **Config-Korrektur:** `watchdog: true` entfernt — der neue Supervisor
  erwartet hier einen Health-Check-URL-String und verwarf die ganze
  Config, sonst (Add-on fiel aus dem Store, Rebuilds liefen leer).
- **Fix: fehlender Autorisierungs-Code (Ursache gefunden).**
  `openid.ns.oa2` in der Login-Start-URL war `https://…` – Amazon bucht die
  OAuth2-Assoziation aber nur mit exakt `http://www.amazon.com/ap/ext/oauth/2`
  ein (so wie es die Referenz-Implementierungen alexa-cookie2/alexa-mcp
  senden). Mit `https` lief der Login zwar komplett (inkl. 2FA), aber ohne
  OA2-Assoziation -> `maplanding` kam ohne `openid.oa2.authorization_code`.
  Gegen echtes Amazon A/B-verifiziert: nur mit `http` enthält der
  Claim-Flow die `openid.oa2.*`-Felder.

## 1.1.7 (2026-11-17)

- **Diagnose ausgebaut** (Login lief durch, aber Amazon sendet am Ende
  `maplanding` ohne `openid.oa2.authorization_code`):
  - Proxy loggt jetzt jeden Schritt (Request + Antwort-Status + Redirect-Ziel)
    und zeigt die letzten Schritte live in der Diagnose-Box des Panels an.
  - Neuer Endpunkt `/api/logs`: Schwanz der Log-Datei (uebersteht
    Neustarts) - damit auch vergangene Logins nachvollziehbar sind.
- **`watchdog: true`**: Supervisor startet das Add-on neu, falls der
  Prozess unerwartet endet (war vorher still stehen geblieben).

## 1.1.6 (2026-11-17)

- Cache-Busting fuer `app.js`/`style.css` (`?v=`-Parameter): Panel laedt nach
  jedem Update garantiert das aktuelle UI (inkl. Diagnose-Box) statt einer
  gecachten Version.
- `index.html`/`style.css` werden jetzt mit deployed (fehlten in der
  Deploy-Liste).

## 1.1.5 (2026-11-17)

- **Fix fehlender Autorisierungs-Code** (Login lief durch 2FA, aber am Ende
  ohne `openid.oa2.authorization_code` -> "nicht angemeldet"):
  - Der Proxy schickt Amazon jetzt die **akkumulierten** Amazon-Cookies mit
    (unabhaengig davon, ob der Browser sie gespeichert hat) + frc/map-md.
    Damit verliert Amazons Server-Session den OA2-Flow-State nicht.
  - `SameSite=None` wird ueber http zusammen mit `Secure` gestrichen –
    `SameSite=None` ohne `Secure` ist ungueltig, der Browser wuerfe das
    Cookie sonst weg.
- **Diagnose im Panel**: Die Login-Karte zeigt jetzt auf Wunsch den
  Proxy-Status (letzter Schritt, Cookies, ob Code gefangen wurde) – bei
  Problemen einfach aufklappen und melden.
- Intern: API-Aufrufe (Registrierung, Token-Erneuerung) laufen mit
  `allow_redirects=False`.

## 1.1.4 (2026-11-17)

- **Fix SSL-Fehler beim Login** (`SSL_ERROR_RX_RECORD_TOO_LONG`): Amazon sendet
  den Header `Content-Security-Policy: upgrade-insecure-requests`, der den
  Browser zwaengte, alle http-Requests (Formular-POSTs) auf https zu upgraden
  -> gegen unseren http-Only-Ingress crasht das. CSP-Header werden jetzt
  gestrippt.
- **Fix relative URLs**: Die echten Amazon-Seiten nutzen relative Formular-
  Actions (`/ax/claim?...`) und relative Location-Redirects. Der Browser
  wuerde diese an den HA-Root senden (statt zum Proxy). Jetzt werden sie
  auf absolute Proxy-URLs umgeschrieben (Body: action/href/src + Meta-Refresh;
  Header: relative Location wird mit Proxy-Praefix versorgt).
- **Fix Redirect-Folgen**: Der Proxy folgt Amazon-Redirects nicht mehr
  (`allow_redirects=False`), damit der Browser jeden Login-Schritt selbst
  ablaeuft und alle Cookies mitsammelt (wie in der Referenz-Implementierung).
- API-Aufrufe (Registrierung, Token-Erneuerung, Cookie-Austausch) laufen ohne
  Redirect-Folgen, damit 302-Chains Fehler nicht verdecken.

## 1.1.3 (2026-11-17)

- **Fix 500 im Browser-Login-Proxy**: Proxy-Antworten crashten (uvicorn 500),
  weil die Set-Cookie-Header als Liste statt als Mapping an die Response
  uebergaben wurden; jetzt werden sie per `headers.append()` angehaengt.
- **Fix Set-Cookie-Lesen**: `getall("set-cookie")` crashte, wenn Amazon keine
  Cookies mitsendet (KeyError); jetzt abgefangen.
- **Fix HTTP-Sitzung**: Die aiohttp-ClientSession wird jetzt an den aktuellen
  Event-Loop gebunden und bei Bedarf neu erzeugt (statt "Event loop is closed").
- Intern: Upstream-Umleitung per `AM_PROXY_UPSTREAM_MAP` (nur Test/Debug).

## 1.1.2 (2026-11-17)

- **Browser-Login (neuer Standard)**: Anmeldung ueber die echte Amazon-Seite im
  Browser (Reverse-Proxy, identisch mit dem alexa-mcp-Auth-Flow `npm run auth`):
  E-Mail, Passwort und 2FA-Code aus der Authenticator-App funktionieren damit.
  Nach dem Login registriert der Add-on ein Geraet
  (POST api.amazon.com/auth/register) und leitet Refresh-Token + Cookies ab.
- **API-Modell**: Alle API-Zugriffe laufen jetzt mit localCookie + csrf-Header
  gegen alexa.amazon.de (identisch mit alexa-remote2/alexa-mcp) statt ueber
  alexapy. E-Mail+Passwort-Login bleibt als Alternative (kommt je nach Konto
  nicht immer durch).
- **Sitzungsdatei**: `/data/alexa_registration.json` (0600) mit Refresh-Token,
  Cookies und stabiler Geraete-Identitaet (deviceId/deviceSerial) – wie
  alexa-mcp, dadurch kein Geraet-Müll und Push-freundlich.
- Neustart: Sitzung wird still aus dem Refresh-Token erneuert
  (api.amazon.com/auth/token + Token-Austausch + csrf).
- Diagnose: `/api/debug` zeigt jetzt auch den Proxy-Status (Cookies-Namen,
  letztes Ereignis, ob Ergebnis gefangen).

## 1.1.1 (2026-11-17)

- **Fix**: `/data/alexa/` + `.storage/` werden jetzt vor dem Login angelegt
  (fehlendes Verzeichnis crashte den Login beim Schreiben der alexapy-Debug-HTML).
- Versionsanzeige wird beim Öffnen der Einstellungen stets aktualisieren.

## 1.1.0 (2026-11-17)

- **Login-Loop**: Der Amazon-Login-Flow braucht mehrere Formularschritte; der
  Add-on laeuft `login()` jetzt automatisch so lange weiter, bis ein Endzustand
  (2FA, Auswahl, Fehler, Erfolg) erreicht ist.
- **Version**: Versionsnummer wird im Panel (Einstellungen) angezeigt und bei
  jedem Update hochgezählt.
- **Diagnose**: `/api/debug` liefert letztes Amazon-Antwort-HTML + Log-Schwanz
  (In-Memory), Fehlermeldungen enthalten jetzt Status + letzte Amazon-URL.
- alexapy-Debug-HTML wird nach `/data/alexa/` geschrieben (AM_DEBUG=0 zum Abschalten).

## 1.0.0 (2026-11-17)

- Erste Version.
- Amazon-Login (E-Mail + Passwort + 2-Faktor-Code, auch claimspicker/authselect-Optionen)
  über alexapy; nur Refresh-Token + Cookies gespeichert (kein Passwort), automatische
  Sitzungs-Erneuerung beim Start.
- Geräte: Liste (Name, Kategorie, Hersteller, Skill/connectedVia, Erreichbarkeit,
  Aktivierungsstatus, Gruppen), Suche + Filter, Details, aktivieren/deaktivieren,
  umbenennen, löschen (forgetEndpoint + Phoenix-Fallback mit URL-Kodierung).
- Szenen: Liste mit Details.
- Gruppen: ansehen, erstellen, bearbeiten (Name + Mitglieder), löschen.
- Routinen: ansehen (Trigger + Aktionen dekodiert), ausführen (Ziel-Echo wählbar),
  aktivieren/deaktivieren, bearbeiten, anlegen (Sprach-/Zeitplan-Trigger, mehrere
  Aktionen mit operation/validate-Normalisierung), löschen (mit Verifikation).
- German UI, HA-Style, Light/Dark, Ingress-Panel in der HA-Seitenleiste.
