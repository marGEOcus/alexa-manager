<div align="center">
    <h1>Alexa Manager</h1>
    <p><b>Home Assistant App</b> für dein Amazon-Alexa-Konto:<br>
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
  (Erreichbarkeit, Hersteller, Modell, Gruppen-Zugehörigkeit, Endpoint-IDs) – direkt
  **aktivieren/deaktivieren**, **umbenennen** oder **löschen**
- **Routinen**: Routinen (Trigger + Aktionen) in einer Tabelle wie der Geräteansicht
  ansehen – direkt aus der Zeile **ausführen**, **aktivieren/deaktivieren** und
  **löschen**; Details inkl. roher Daten per Klick
- **Einstellungen**: Amazon-Konto verbinden/abmelden, Theme (Hell/Dunkel/System)
- **Keine Passwortspeicherung**: Einmaliger Amazon-Login pro Home Assistant – danach
  wird die Sitzung automatisch aus dem Refresh-Token erneuert (auch nach Neustarts)

## Installation

1. Klicke auf den Button unten (in einem Browser, in dem du mit Home Assistant
   angemeldet bist). Home Assistant öffnet direkt den Dialog zum Hinzufügen des
   App-Repositories mit der vorbefüllten URL. Alternativ: **App-Store → ⋮ →
   Repositories** und die URL `https://github.com/marGEOcus/alexa-manager` eintragen.

   [![Add app repository to My Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FmarGEOcus%2Falexa-manager)

2. Im Dialog **Add → Close** klicken – das Repository „Alexa Manager" erscheint jetzt
   in der App-Store-Liste.
3. Auf **Alexa Manager** klicken und **Installieren** drücken, danach **Starten**.
4. Das Panel „Alexa Manager" erscheint in der Seitenleiste → unter **Einstellungen**
   Amazon-E-Mail + Passwort eingeben (ggf. 2-Faktor-Code bestätigen).

**Voraussetzungen:** Home Assistant OS (kein Container/VM), Architektur `aarch64` oder `amd64`.

**Alternative Installation „Von URL":** Der Add-on liegt zusätzlich als ZIP in den
[Releases](https://github.com/marGEOcus/alexa-manager/releases) – die URL des ZIPs
(„latest" zeigt immer auf die neueste Version) kann in **App-Store → Erweiterte-Sicht →
„Von URL installieren"** eingetragen werden:
`https://github.com/marGEOcus/alexa-manager/releases/latest/download/alexa-manager.zip`

Danach ist die Sitzung persistent – bei Abmeldung (Einstellungen → Abmelden)
werden alle Tokens gelöscht.

## Updates

Neue Versionen erscheinen als neues [Release](https://github.com/marGEOcus/alexa-manager/releases)
und als neuer Stand dieses Repositories. Home Assistant erkennt das automatisch –
im App-Store erscheint bei **Alexa Manager** dann der Hinweis **Update verfügbar**.

## Konfiguration

Die App hat **keine** Optionen – alles wird im Panel erledigt:

| Schritt | Wo |
|---|---|
| Amazon verbinden (einmalig) | Panel → **Einstellungen** → E-Mail + Passwort |
| Theme | Panel → **Einstellungen** → Hell / Dunkel / System |

## Changelog

Das Format basiert auf [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).
Alle relevanten Änderungen sind in der Datei
[CHANGELOG.md](alexa-manager/CHANGELOG.md) dokumentiert.

## Issues

Falls du Probleme findest, schau bitte zuerst im
[Issue-Tracker](https://github.com/marGEOcus/alexa-manager/issues) nach ähnlichen
Problemen, bevor du ein neues anlegst.

## Technische Hinweise

- Datenverzeichnis: `/data` (App „data"); Sitzung: `/data/alexa_session.json` (0600)
- Ingress-Panel, Basis-Image `ghcr.io/home-assistant/base:3.24`, Architekturen aarch64 + amd64
- Beschränkungen: Szenen werden nicht als Panel angezeigt und Routinen können hier nicht
  angelegt/bearbeitet werden (beides bleibt der Alexa-App vorbehalten); keine
  Skill-Verwaltung; gesperrte/regionale Amazon-Konten können beim Login ein Captcha
  verlangen (Meldung im Panel)
