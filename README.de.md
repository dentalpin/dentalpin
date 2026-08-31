# DentalPin

[![ar](https://img.shields.io/badge/lang-ar-white.svg)](./README.ar.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](./README.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](./README.es.md)
[![fr](https://img.shields.io/badge/lang-fr-blue.svg)](./README.fr.md)
[![pt](https://img.shields.io/badge/lang-pt-brightgreen.svg)](./README.pt.md)
[![ta](https://img.shields.io/badge/lang-ta-green.svg)](./README.ta.md)
[![de](https://img.shields.io/badge/lang-de-black.svg)](./README.de.md)
[![hu](https://img.shields.io/badge/lang-hu-orange.svg)](./README.hu.md)
[![pl](https://img.shields.io/badge/lang-pl-lightgrey.svg)](./README.pl.md)
[![it](https://img.shields.io/badge/lang-it-blueviolet.svg)](./README.it.md)

**Software für die Verwaltung von Zahnarztpraxen mit offengelegtem Quellcode (BSL 1.1), die vier Jahre nach Veröffentlichung unter Apache 2.0 übergeht.** Patienten, Zahnschema,
Terminplanung, Behandlungspläne, Abrechnung und ein integrierter KI-Copilot — modular,
self-hosted, API-first.

### ▶ [**Live-Demo ausprobieren**](https://demo.dentalpin.com)

Melden Sie sich mit `admin@demo.clinic` / `demo1234` an — voller Admin-Zugriff auf eine
Praxis mit Beispieldaten. Wird jede Nacht zurückgesetzt, probieren Sie also alles aus.

[![DentalPin — Patientenakte mit Zahnschema](docs/screenshots/patients.png)](https://demo.dentalpin.com)

<sub>[Website](https://www.dentalpin.com) · [Doku](https://docs.dentalpin.com) · [Telegram](https://t.me/dentalpin) · [Weitere Screenshots ↓](#screenshots)</sub>

## Warum DentalPin?

Zahnarztpraxen auf der ganzen Welt teilen dieselben grundlegenden Bedürfnisse: Patienten verwalten, Termine planen, Behandlungen nachverfolgen und die Praxis effizient führen. Doch die Softwarelandschaft ist in Dutzende lokalisierte Closed-Source-Lösungen zersplittert, die Praxen an teure Verträge und veraltete Technologie binden.

**Wir glauben, es ist Zeit für einen Wandel.**

DentalPin beruht auf einer einfachen Prämisse: **eine offene Plattform für Zahnarztpraxen überall**. Keine weitere regionale Lösung, sondern ein globales Fundament, das jede Praxis übernehmen, jeder Entwickler erweitern und jede Community lokalisieren kann.

### Warum jetzt?

KI hat grundlegend verändert, was kleine Teams bauen können. Funktionen, die früher große Entwicklungsabteilungen erforderten, lassen sich heute in Tagen umsetzen. Das ist unser Zeitfenster, um die Dentalsoftware mit offengelegtem Quellcode (BSL 1.1, vier Jahre nach Veröffentlichung Apache 2.0) zu schaffen, die es schon vor Jahren hätte geben sollen — bevor Praxen in Altsystemen gefangen sind, aus denen sie nicht mehr herauskommen.

### Unsere Prinzipien

- **Offengelegter Quellcode (BSL 1.1)** — Die Daten Ihrer Praxis gehören Ihnen. Ihre Software sollte es auch.
- **Modular** — Starten Sie einfach, ergänzen Sie, was Sie brauchen. Zahlen Sie nicht für Funktionen, die Sie nie nutzen werden.
- **Global by Design** — Von Tag eins für Lokalisierung gebaut. Derselbe Kern, jede Sprache, jedes Land.
- **API-First** — Jede Funktion ist eine API. Integrieren Sie alles, automatisieren Sie alles.
- **Bereit für KI** — Strukturiert für das KI-Zeitalter. Bereit für intelligente Terminplanung, klinische Entscheidungsunterstützung und Workflow-Automatisierung.

### Die Vision

Wir bauen nicht nur Software — wir bauen das Fundament für ein Ökosystem. Eine Plattform, auf der Entwickler Module beisteuern, Praxen Verbesserungen teilen und die gesamte Dental-Community von kollektiver Innovation profitiert.

Praxen verdienen Besseres als geschlossene, teure Software aus dem letzten Jahrzehnt. DentalPin ist die offene Alternative.

## ✨ KI-Copilot

DentalPin wird mit einem integrierten **agentischen KI-Assistenten** ausgeliefert, der die ganze Praxis in etwas verwandelt, mit dem Sie einfach reden können. Bitten Sie ihn, einen Patienten zu finden, einen Termin freizuräumen, einem unbeantworteten Kostenvoranschlag nachzugehen oder Sie über den anstehenden Tag zu briefen — in ganz normalem Spanisch oder Englisch — und er handelt auf Ihren echten Daten.

![AI Copilot](docs/screenshots/ia.png)

Das ist kein aufgesetzter Chatbot. Der Copilot ist ein echter Agent, der **mehrstufige Aufgaben plant und ausführt**, indem er dieselben Operationen aufruft wie die Oberfläche — über Patienten, Terminkalender, Recalls, Kostenvoranschläge, Zahlungen und Berichte hinweg.

- **Er handelt, statt nur zu antworten.** Der Agent führt echte Tools aus — Patienten suchen, Termine buchen oder verschieben, eine Zahlung erfassen, die Einnahmen des Monats abrufen — und verkettet sie, um eine Aufgabe von Anfang bis Ende zu erledigen.
- **Er kann Ihre Rolle nie überschreiten.** Jeder Tool-Aufruf wird am Kontrollpunkt der Ausführung erneut gegen die RBAC-Berechtigungen des aufrufenden Benutzers geprüft. Der Copilot kann *genau* das sehen und tun, was dieser Benutzer über die Oberfläche könnte — nicht mehr, begrenzt auf seine Praxis.
- **Ihre Daten sind geschützt.** Gesundheitsdaten (PHI) werden geschwärzt, bevor irgendetwas den LLM-Anbieter erreicht: Patientennamen, Telefonnummern, E-Mails und IDs werden durch deterministische Token ersetzt, und klinische Freitext-Tools sind vom Cloud-Pfad vollständig ausgeschlossen. Die Schwärzung ist standardmäßig aktiv.
- **Schreibzugriffe fragen zuerst.** Jede Aktion, die Daten verändert (Buchungen, Zahlungen, Bearbeitungen), pausiert mitten im Gespräch für Ihre ausdrückliche Bestätigung, bevor sie ausgeführt wird.
- **Geführte Workflows.** Fertige Playbooks — *Tagesbriefing*, *Besuch vorbereiten*, *Lücke füllen*, *Fällige Recalls*, *Unbeantwortete Kostenvoranschläge* — starten häufige mehrstufige Aufgaben mit einem Fingertipp.
- **Proaktive Briefings.** Aktivieren Sie optional einen deterministischen Morgen-Digest per E-Mail an Ihr Team, der den Terminplan des Tages, fällige Recalls und offene Kostenvoranschläge zusammenfasst — ohne LLM, ohne PHI außer Haus.
- **Modular by Design.** Der Copilot nutzt Tools, die jedes Modul über eine gemeinsame Registry veröffentlicht; jedes Modul steuert eigene Fähigkeiten bei, sodass der Agent automatisch mitwächst, wenn neue Module installiert werden.

Unter der Haube anbieterunabhängig (eine LLM-Provider-Abstraktion), mit pro Deployment konfigurierbarem Anbieter, Modell und Token-Budgets pro Praxis. Architektur: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Website

Besuchen Sie [**dentalpin.com**](https://www.dentalpin.com) für Produktinformationen, Funktionen und kommerzielle Details.

## Community

Treten Sie unserem [**Telegram-Kanal**](https://t.me/dentalpin) bei — für Support, Hilfe bei der Installation und Fragen.

## Screenshots

### Dashboard
![Dashboard](docs/screenshots/home.png)

### Patientenverwaltung
![Patients](docs/screenshots/patients.png)

### Wochenkalender
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Kanban-Terminplan
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Zahlungsdiagramm
![Payments Chart](docs/screenshots/payments-chart.png)

### Einstellungen
![Settings](docs/screenshots/settings.png)

## Installation

Vorgefertigte Images, kein Clone, kein Build. Auf jedem Server mit Docker:

```bash
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/Caddyfile
curl -o .env https://raw.githubusercontent.com/dentalpin/dentalpin/main/.env.prod.example

# PUBLIC_URL, POSTGRES_PASSWORD und SECRET_KEY in .env setzen, dann:
docker compose -f docker-compose.prod.yml up -d
```

Richten Sie eine Domain auf den Server, setzen Sie `PUBLIC_URL=https://your-domain`,
und TLS wird beim ersten Start automatisch eingerichtet — Caddy steht vor beiden
Diensten auf einem einzigen Origin, es gibt also kein CORS und kein Zertifikat zu
erneuern. Setzen Sie `SEED_ON_STARTUP=1`, um die Demo-Praxis zu laden und sich
umzusehen, bevor Sie live gehen.

Images: [`dentalpin-backend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-backend) ·
[`dentalpin-frontend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-frontend)

## Schnellstart (Entwicklung)

Baut aus dem Quellcode, mit Hot Reload:

```bash
# Dienste starten
docker-compose up -d

# Demo-Daten einspielen (standardmäßig Englisch)
./scripts/seed-demo.sh

# Oder auf Spanisch einspielen
./scripts/seed-demo.sh --lang es

# Indien-GST-Demo-Praxis (Tamil-UI, oder englische UI mit --country in)
./scripts/seed-demo.sh --lang ta
```

Öffnen Sie http://localhost:3000

### Demo-Zugangsdaten

Alle Benutzer haben das Passwort: `demo1234`

| E-Mail | Rolle | Name (EN) | Name (ES) |
|--------|-------|-----------|-----------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

Alle Details zu den Demo-Daten finden Sie in [docs/user-manual/en/demo.md](docs/user-manual/en/demo.md).

## Tech-Stack

| Ebene | Technologie |
|-------|------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 4 + Nuxt UI |
| Datenbank | PostgreSQL 15 |
| Auth | JWT mit Refresh-Tokens |

## Funktionen

### KI-Copilot
- **Agentischer Assistent** — Konversationsagent, der mehrstufige Aufgaben über Patienten, Terminkalender, Recalls, Kostenvoranschläge, Zahlungen und Berichte hinweg plant und ausführt, indem er echte Operationen aufruft
- **RBAC-Parität** — Jede Aktion wird erneut gegen die Berechtigungen des Benutzers geprüft; der Agent kann nur tun, was dieser Benutzer über die Oberfläche könnte, begrenzt auf seine Praxis
- **PHI-Schwärzung** — Patientenidentifikatoren werden tokenisiert, bevor sie das LLM erreichen; klinische Freitextdaten bleiben dem Cloud-Pfad fern. Standardmäßig aktiv
- **Bestätigte Schreibzugriffe** — Datenändernde Aktionen pausieren mitten im Gespräch für die ausdrückliche Bestätigung des Benutzers
- **Workflows & Digest** — Playbooks per Fingertipp (Tagesbriefing, Besuch vorbereiten, Lücke füllen) plus ein optionaler proaktiver Morgen-Digest per E-Mail
- **Mehrsprachig & anbieterunabhängig** — Spricht mit Ihnen in der Sprache Ihrer Oberfläche; LLM-Anbieter, Modell und Token-Budget pro Praxis konfigurierbar

### Klinische Verwaltung
- **Patientenakten** — Vollständige Patientenprofile mit persönlichen Daten, Kontaktinformationen, Anamnese und Notizen
- **Zahnschema (Odontogramm)** — Interaktives Zahndiagramm mit Behandlungsverfolgung pro Zahn/Fläche
- **Terminkalender** — Wochen- und Tagesansicht mit Drag & Drop, Spalten je Behandler, Konflikterkennung
- **Behandlungskatalog** — Anpassbarer Katalog mit Codes, Preisen, Mehrwertsteuersätzen und Kategorien

### Finanzverwaltung
- **Kostenvoranschläge** — Behandlungs-Kostenvoranschläge erstellen, Freigabe-Workflow verfolgen (Entwurf → ausstehend → genehmigt/abgelehnt), Patientenunterschrift erfassen, PDF-Generierung
- **Rechnungen** — Rechnungen aus Kostenvoranschlägen oder eigenständig erzeugen, automatische Nummerierung, mehrere Zahlungsarten, PDF-Export
- **Zahlungen** — Teilzahlungen verfolgen, Zahlungshistorie, Saldoberechnung

### Praxisverwaltung
- **Rollenbasierte Zugriffskontrolle** — Fünf Rollen (Admin, Zahnarzt, Dentalhygieniker, Assistenz, Rezeption) mit granularen Berechtigungen
- **Behandlungszimmer-Verwaltung** — Behandlungszimmer mit Zeitplänen und Farben definieren
- **Behandler-Verwaltung** — Termine bestimmten Zahnärzten/Dentalhygienikern zuweisen

### Benutzererlebnis
- **Visuelle Auswahlfelder** — Intelligente Dropdowns mit zuletzt aufgerufenen Patienten und häufig genutzten Behandlungen
- **Oberfläche in neun Sprachen** — Englisch, Spanisch, Französisch, Portugiesisch, Tamil, Deutsch, Ungarisch, Polnisch und Italienisch — Kern-App und jedes Modul
- **Dark Mode** — Themenwechsel entsprechend der Systemeinstellung
- **Responsives Design** — Funktioniert auf Desktop und Tablet

### Technische Funktionen
- **Modulare Architektur** — Plugin-basiertes System für einfache Erweiterbarkeit
- **Event-Bus** — Kommunikation zwischen Modulen für Benachrichtigungen und Integrationen
- **REST-API** — Vollständige API mit OpenAPI-Dokumentation
- **Echtzeit-Updates** — Reaktive Oberfläche mit optimistischen Updates

## Sprachen

Die Oberfläche wird in **neun Sprachen** ausgeliefert — English, Español, Français,
Português, தமிழ் (Tamil), Deutsch, Magyar, Polski und Italiano — und deckt die Kern-App
**und jede Modulebene** ab, mit einem in der CI erzwungenen Key-Paritätstest, damit
Locales nicht unbemerkt auseinanderlaufen. Polnisch nutzt seine vollständigen
Pluralregeln mit drei Formen.

Patientengerichtete Kommunikation (E-Mail-Vorlagen, PDFs) wird derzeit in
**fünf Sprachen** gerendert (es, en, fr, pt, ta); jede Praxis wählt ihre
Kommunikationssprache unabhängig von der UI-Sprache des Teams.

Ihre Sprache fehlt? Eine Sprache hinzuzufügen ist ein reiner Übersetzungsbeitrag —
sehen Sie sich die [i18n-Issues](https://github.com/dentalpin/dentalpin/issues?q=label%3Ai18n)
an oder eröffnen Sie ein neues.

## Entwicklung

### Voraussetzungen

- Docker und Docker Compose
- Python 3.11+ (für lokale Backend-Entwicklung)
- Node.js 18+ (für lokale Frontend-Entwicklung)

### Lokal ausführen

```bash
# Alle Dienste starten
docker-compose up

# Oder das Backend separat ausführen
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Oder das Frontend separat ausführen
cd frontend
npm install
npm run dev
```

### Datenbankverwaltung

```bash
# Datenbank zurücksetzen und Migrationen ausführen
./scripts/reset-db.sh

# Demo-Daten einspielen (Englisch — Standard)
./scripts/seed-demo.sh

# Demo-Daten einspielen (Spanisch)
./scripts/seed-demo.sh --lang es

# Komplette Einrichtung (Reset + Seed in einem Befehl)
./scripts/setup-demo.sh
```

### Tests ausführen

```bash
# Backend-Unit- + Integrationstests (in Docker)
docker-compose exec backend python -m pytest -v

# Langsamer Alembic-Round-Trip (opt-in, siehe docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Frontend-Unit-Tests (vitest)
cd frontend
npm run test
```

**Browser-E2E (Playwright)** liegt in `frontend/tests/e2e/` und steuert den
vollen Stack unter `localhost:3000` → `:8000`. Läuft auf dem Host, weil der
Alpine-Frontend-Container kein Chromium starten kann.

```bash
# Einmalige Einrichtung
(cd frontend && npm install && npx playwright install chromium)

# Der Stack muss zuerst laufen und geseedet sein
docker-compose up -d
./scripts/seed-demo.sh

# Komplette E2E-Suite (Nav + RBAC + Patientendetail-Smoke-Test)
./scripts/e2e.sh

# Einzelne Datei
./scripts/e2e.sh rbac

# Interaktive UI
./scripts/e2e.sh --ui
```

Vollständiges Runbook + Fixture-Referenz: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Architektur

DentalPin nutzt eine modulare Plugin-Architektur. Jede Funktion ist ein in sich geschlossenes Modul, das:
- seine SQLAlchemy-Modelle deklariert
- einen FastAPI-Router bereitstellt
- Events anderer Module abonnieren kann

Details finden Sie in [docs/adr/0001-modular-plugin-architecture.md](docs/adr/0001-modular-plugin-architecture.md).

## Lizenz

Business Source License 1.1 (BSL 1.1)

**Zusätzliche Nutzungsgewährung:** Sie dürfen DentalPin in Produktion einsetzen, solange Sie es nicht als kommerzielles SaaS für die Verwaltung von Zahnarztpraxen anbieten.

**Änderungsdatum:** 4 Jahre ab Veröffentlichung

**Änderungslizenz:** Apache 2.0

Die vollständigen Bedingungen finden Sie in [LICENSE](LICENSE).

## Mitwirken

Richtlinien finden Sie in [CONTRIBUTING.md](CONTRIBUTING.md).

---

Unterstützt von [Dentaltix](https://www.dentaltix.com)
