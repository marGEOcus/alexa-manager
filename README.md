<div align="center">
    <h1>Alexa Manager</h1>
    <p><b>Home Assistant Add-on</b> für dein Amazon-Alexa-Konto:<br>
    Geräte, Szenen, Gruppen und Routinen verwalten – direkt in Home Assistant.</p>
</div>

---

> [!CAUTION]
> Der Zugriff auf dein Amazon-Konto erfolgt über die **inoffizielle Amazon-Web-API**
> (dieselbe, die die Alexa-App nutzt – wie auch bei alexa_media bzw. Alexa-Device-Manager).
> Amazon kann Endpunkte jederzeit ändern oder den Zugriff einschränken.
> Dieses Projekt ist **nicht** mit Amazon verbunden oder von Amazon freigegeben.

## Funktionen

- **Geräte**: Alle Alexa-Geräte mit Suche, Filtern (Gruppe, Typ, Status) und Details
  (Erreichbarkeit, Hersteller, Modell, Endpoint-IDs) – direkt **aktivieren/deaktivieren**,
  **umbenennen** oder **löschen**
- **Szenen**: Szenen des Kontos ansehen (Szenen sind in Routinen als Aktion nutzbar)
- **Gruppen**: Gruppen, -Zugehörigkeiten und Mitglieder ansehen
- **Routinen**: Routinen (Trigger + Aktionen) ansehen, **ausführen**, **anlegen**
  (Sprach- oder Zeitplan-Trigger), **aktivieren/deaktivieren** und **löschen**
- **Einstellungen**: Amazon-Konto verbinden/abmelden, Theme (Hell/Dunkel/System)
- **Keine Passwortspeicherung**: Einmaliger Amazon-Login pro Home Assistant – danach
  wird die Sitzung automatisch aus dem Refresh-Token erneuert (auch nach Neustarts)

## Installation

Der Add-on wird direkt aus diesem Repository installiert – der Link hinter dem
Button unten ist die **Download-URL des Add-on-ZIPs** für
**„Von URL installieren"**. Die URL zeigt **immer auf die neueste Version** –
aktuelle Releases findest du hier: [Releases](https://github.com/marGEOcus/alexa-manager/releases).

[![Home Assistant Add-on installieren](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://github.com/marGEOcus/alexa-manager/releases/latest/download/alexa-manager.zip)

**So geht's:**

1. In Home Assistant: **Einstellungen → Add-ons, Themes & Geräte → Add-on-Store**
2. Oben rechts die **Erweiterte-Sicht** aktivieren
3. **„Von URL installieren"** wählen und die URL aus dem Button oben eintragen
   (`https://github.com/marGEOcus/alexa-manager/releases/latest/download/alexa-manager.zip`)
4. **Alexa Manager** erscheint im Store → **Installieren** → **Starten**
5. Das Panel „Alexa Manager" erscheint in der Seitenleiste → unter
   **Einstellungen** Amazon-E-Mail + Passwort eingeben (ggf. 2-Faktor-Code bestätigen)

**Updates:** Neue Versionen erscheinen als neues [Release](https://github.com/marGEOcus/alexa-manager/releases)
dieses Repositories. Da die Installations-URL immer auf das neueste Release zeigt,
erkennt Home Assistant verfügbare Updates automatisch (Add-on-Store → „Update verfügbar").

**Voraussetzungen:** Home Assistant OS (kein Container/VM), Architektur `aarch64` oder `amd64`.

Danach ist die Sitzung persistent – bei Abmeldung (Einstellungen → Abmelden)
werden alle Tokens gelöscht.

## Konfiguration

Der Add-on hat **keine** Optionen – alles wird im Panel erledigt:

| Schritt | Wo |
|---|---|
| Amazon verbinden (einmalig) | Panel → **Einstellungen** → E-Mail + Passwort |
| Theme | Panel → **Einstellungen** → Hell / Dunkel / System |

## Changelog

Das Format basiert auf [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).
Alle relevanten Änderungen sind in der Datei [CHANGELOG.md](CHANGELOG.md) dokumentiert.

## Issues

Falls du Probleme findest, schau bitte zuerst im
[Issue-Tracker](https://github.com/marGEOcus/alexa-manager/issues) nach ähnlichen
Problemen, bevor du ein neues anlegst.

## Technische Hinweise

- Datenverzeichnis: `/data` (Add-on „data"); Sitzung: `/data/alexa_session.json` (0600)
- Ingress-Panel, Basis-Image `ghcr.io/home-assistant/base:3.24`, Architekturen aarch64 + amd64
- Beschränkungen: Kein Skill-Management, kein Szenen-Anlegen/Löschen (bleibt der Alexa-App
  vorbehalten); gesperrte/regionale Amazon-Konten können beim Login ein Captcha verlangen
  (Meldung im Panel)
