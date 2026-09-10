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

**Software a codice sorgente disponibile (BSL 1.1) per la gestione dello studio dentistico, che passa ad Apache 2.0 quattro anni dopo la pubblicazione.** Pazienti,
odontogramma, agenda, piani di cura, fatturazione e un copilot AI integrato —
modulare, self-hosted, API-first.

### ▶ [**Prova la demo dal vivo**](https://demo.dentalpin.com)

Accedi con `admin@demo.clinic` / `demo1234` — accesso amministratore completo a uno
studio con dati di esempio. Si azzera ogni notte, quindi esplora liberamente.

[![DentalPin — scheda paziente con odontogramma](docs/screenshots/patients.png)](https://demo.dentalpin.com)

<sub>[Sito web](https://www.dentalpin.com) · [Documentazione](https://docs.dentalpin.com) · [Telegram](https://t.me/dentalpin) · [Altri screenshot ↓](#screenshot)</sub>

## Perché DentalPin?

Gli studi dentistici di tutto il mondo condividono le stesse esigenze fondamentali: gestire i pazienti, pianificare gli appuntamenti, seguire i trattamenti e amministrare l'attività in modo efficiente. Eppure il panorama software è frammentato in decine di soluzioni localizzate e a codice chiuso che vincolano gli studi a contratti costosi e a tecnologie obsolete.

**Crediamo che sia ora di cambiare.**

DentalPin nasce da una premessa semplice: **un'unica piattaforma aperta per gli studi dentistici di tutto il mondo**. Non l'ennesima soluzione regionale, ma una base globale che ogni studio può adottare, ogni sviluppatore può estendere e ogni comunità può localizzare.

### Perché ora?

L'AI ha cambiato radicalmente ciò che i piccoli team possono costruire. Funzionalità che un tempo richiedevano grandi reparti di sviluppo oggi possono essere implementate in pochi giorni. Questa è la nostra occasione per creare il software dentale a codice sorgente disponibile (BSL 1.1, che passa ad Apache 2.0 quattro anni dopo la pubblicazione) che avrebbe dovuto esistere già anni fa — prima che gli studi restassero intrappolati in sistemi legacy da cui non possono uscire.

### I nostri principi

- **Codice sorgente disponibile (BSL 1.1)** — I dati del tuo studio appartengono a te. Anche il tuo software dovrebbe.
- **Modulare** — Inizia in modo semplice, aggiungi ciò che ti serve. Non pagare per funzionalità che non userai mai.
- **Globale per progettazione** — Pensato per la localizzazione fin dal primo giorno. Stesso nucleo, qualsiasi lingua, qualsiasi paese.
- **API-first** — Ogni funzionalità è una API. Integra con qualsiasi cosa, automatizza tutto.
- **Pronto per l'AI** — Strutturato per l'era dell'AI. Pronto per la pianificazione intelligente, il supporto alle decisioni cliniche e l'automazione dei flussi di lavoro.

### La visione

Non stiamo solo costruendo un software: stiamo costruendo le fondamenta di un ecosistema. Una piattaforma in cui gli sviluppatori contribuiscono con moduli, gli studi condividono i miglioramenti e l'intera comunità odontoiatrica beneficia dell'innovazione collettiva.

Gli studi meritano di meglio del software chiuso e costoso del decennio scorso. DentalPin è l'alternativa aperta.

## ✨ AI Copilot

DentalPin include un **assistente AI agentico integrato** che trasforma l'intero studio in qualcosa con cui puoi semplicemente parlare. Chiedigli di trovare un paziente, liberare uno slot, sollecitare un preventivo rimasto senza risposta o farti un riepilogo della giornata — in normale spagnolo o inglese — e agisce sui tuoi dati reali.

![AI Copilot](docs/screenshots/ia.png)

Non è un chatbot appiccicato sopra. Il Copilot è un vero agente che **pianifica ed esegue attività in più passaggi** richiamando le stesse operazioni dell'interfaccia, su pazienti, agenda, richiami, preventivi, pagamenti e report.

- **Agisce, non si limita a rispondere.** L'agente esegue strumenti reali — cercare pazienti, prenotare o riprogrammare appuntamenti, registrare un pagamento, estrarre gli incassi del mese — e li concatena per completare un'attività dall'inizio alla fine.
- **Non può mai superare il tuo ruolo.** Ogni chiamata a uno strumento viene riverificata rispetto ai permessi RBAC dell'utente chiamante nel punto di controllo dell'esecuzione. Il Copilot può vedere e fare *esattamente* ciò che quell'utente potrebbe fare dall'interfaccia — niente di più, limitatamente al suo studio.
- **I tuoi dati sono protetti.** I dati sanitari (PHI) vengono oscurati prima che qualsiasi cosa raggiunga il provider LLM: nomi dei pazienti, telefoni, e-mail e identificativi vengono sostituiti con token deterministici, e gli strumenti clinici a testo libero sono del tutto esclusi dal percorso cloud. L'oscuramento è attivo per impostazione predefinita.
- **Le scritture chiedono prima.** Qualsiasi azione che modifica i dati (prenotazioni, pagamenti, modifiche) si mette in pausa durante la conversazione in attesa della tua conferma esplicita prima di essere eseguita.
- **Flussi di lavoro guidati.** Playbook pronti all'uso — *Riepilogo del giorno*, *Prepara una visita*, *Riempi un buco in agenda*, *Richiami in scadenza*, *Preventivi senza risposta* — avviano con un tocco le attività multi-passaggio più comuni.
- **Riepiloghi proattivi.** Attiva, se vuoi, un digest mattutino deterministico inviato via e-mail al tuo team, con il riepilogo dell'agenda del giorno, dei richiami in scadenza e dei preventivi aperti — senza LLM, senza dati sanitari fuori sede.
- **Modulare per progettazione.** Il Copilot utilizza gli strumenti pubblicati da ciascun modulo attraverso un registro condiviso; ogni modulo contribuisce con le proprie capacità, quindi l'agente cresce automaticamente man mano che si installano nuovi moduli.

Indipendente dal fornitore sotto il cofano (un'astrazione del provider LLM), con provider, modello e budget di token per studio configurabili per ogni installazione. Architettura: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Sito web

Visita [**dentalpin.com**](https://www.dentalpin.com) per informazioni sul prodotto, funzionalità e dettagli commerciali.

## Community

Unisciti al nostro [**canale Telegram**](https://t.me/dentalpin) per supporto, aiuto con l'installazione e domande.

## Screenshot

### Dashboard
![Dashboard](docs/screenshots/home.png)

### Gestione pazienti
![Patients](docs/screenshots/patients.png)

### Agenda settimanale
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Agenda Kanban
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Grafico dei pagamenti
![Payments Chart](docs/screenshots/payments-chart.png)

### Impostazioni
![Settings](docs/screenshots/settings.png)

## Installazione

Immagini precompilate, senza clone, senza build. Su qualsiasi server con Docker:

```bash
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/Caddyfile
curl -o .env https://raw.githubusercontent.com/dentalpin/dentalpin/main/.env.prod.example

# Imposta PUBLIC_URL, POSTGRES_PASSWORD e SECRET_KEY in .env, poi:
docker compose -f docker-compose.prod.yml up -d
```

Punta un dominio al server, imposta `PUBLIC_URL=https://your-domain` e il TLS viene
configurato al primo avvio — Caddy serve entrambi i servizi da un'unica origin,
quindi niente CORS e nessun certificato da rinnovare. Imposta `SEED_ON_STARTUP=1`
per caricare lo studio demo e dare un'occhiata prima di andare in produzione.

Immagini: [`dentalpin-backend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-backend) ·
[`dentalpin-frontend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-frontend)

## Avvio rapido (sviluppo)

Compila dai sorgenti con hot reload:

```bash
# Avvia i servizi
docker-compose up -d

# Carica i dati demo (inglese per impostazione predefinita)
./scripts/seed-demo.sh

# Oppure carica in spagnolo
./scripts/seed-demo.sh --lang es

# Studio demo India GST (interfaccia in tamil, o in inglese con --country in)
./scripts/seed-demo.sh --lang ta
```

Apri http://localhost:3000

### Credenziali demo

Tutti gli utenti hanno la password: `demo1234`

| E-mail | Ruolo | Nome (EN) | Nome (ES) |
|--------|-------|-----------|-----------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

Per tutti i dettagli sui dati demo consulta [docs/user-manual/en/demo.md](docs/user-manual/en/demo.md).

## Stack tecnologico

| Livello | Tecnologia |
|---------|------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 4 + Nuxt UI |
| Database | PostgreSQL 15 |
| Autenticazione | JWT con refresh token |

## Funzionalità

### AI Copilot
- **Assistente agentico** — Agente conversazionale che pianifica ed esegue attività multi-passaggio su pazienti, agenda, richiami, preventivi, pagamenti e report richiamando operazioni reali
- **Parità RBAC** — Ogni azione riverificata rispetto ai permessi dell'utente; l'agente può fare solo ciò che quell'utente potrebbe fare dall'interfaccia, limitatamente al suo studio
- **Oscuramento dei dati sanitari (PHI)** — Identificativi dei pazienti tokenizzati prima di raggiungere l'LLM; i dati clinici a testo libero restano fuori dal percorso cloud. Attivo per impostazione predefinita
- **Scritture confermate** — Le azioni che modificano i dati si fermano durante la conversazione in attesa della conferma esplicita dell'utente
- **Flussi di lavoro e digest** — Playbook con un tocco (riepilogo del giorno, preparazione di una visita, riempimento di un buco in agenda) più un digest mattutino proattivo via e-mail attivabile su richiesta
- **Multilingue e indipendente dal fornitore** — Ti parla nella lingua della tua interfaccia; provider LLM, modello e budget di token per studio configurabili

### Gestione clinica
- **Cartelle dei pazienti** — Profili completi con dati personali, contatti, anamnesi e note
- **Scheda dentale (odontogramma)** — Diagramma interattivo dei denti con tracciamento dei trattamenti per dente/superficie
- **Calendario appuntamenti** — Viste settimanale e giornaliera con drag & drop, colonne per professionista, rilevamento dei conflitti
- **Catalogo trattamenti** — Catalogo personalizzabile con codici, prezzi, aliquote IVA e categorie

### Gestione finanziaria
- **Preventivi** — Creazione di preventivi di cura, tracciamento del flusso di approvazione (bozza → in attesa → approvato/rifiutato), acquisizione della firma del paziente, generazione PDF
- **Fatture** — Generazione di fatture da preventivi o autonome, numerazione automatica, metodi di pagamento multipli, esportazione PDF
- **Pagamenti** — Tracciamento dei pagamenti parziali, storico dei pagamenti, calcolo del saldo

### Gestione dello studio
- **Controllo degli accessi basato sui ruoli** — Cinque ruoli (amministratore, dentista, igienista, assistente, receptionist) con permessi granulari
- **Gestione sale/riuniti** — Definizione delle sale di trattamento con orari e colori
- **Gestione dei professionisti** — Assegnazione degli appuntamenti a specifici dentisti/igienisti

### Esperienza utente
- **Selettori visuali** — Menu a tendina intelligenti con i pazienti recenti e i trattamenti più richiesti
- **Interfaccia in nove lingue** — inglese, spagnolo, francese, portoghese, tamil, tedesco, ungherese, polacco e italiano — app principale e ogni modulo
- **Modalità scura** — Cambio di tema in base alle impostazioni di sistema
- **Design responsive** — Funziona su desktop e tablet

### Funzionalità tecniche
- **Architettura modulare** — Sistema a plugin per un'estensibilità semplice
- **Bus di eventi** — Comunicazione tra moduli per notifiche e integrazioni
- **API REST** — API completa con documentazione OpenAPI
- **Aggiornamenti in tempo reale** — Interfaccia reattiva con aggiornamenti ottimistici

## Lingue

L'interfaccia è disponibile in **nove lingue** — English, Español, Français,
Português, தமிழ் (Tamil), Deutsch, Magyar, Polski e Italiano — coprendo l'app
principale **e ogni layer dei moduli**, con un test di parità delle chiavi imposto
dalla CI che impedisce alle localizzazioni di divergere silenziosamente. Il polacco
usa le sue regole complete di plurale a tre forme.

Le comunicazioni rivolte ai pazienti (template e-mail, PDF) sono attualmente
disponibili in **cinque lingue** (es, en, fr, pt, ta); ogni studio sceglie la lingua
di comunicazione indipendentemente dalla lingua dell'interfaccia del personale.

Vuoi la tua lingua? Aggiungerne una è un contributo di sola traduzione — consulta le
[issue i18n](https://github.com/dentalpin/dentalpin/issues?q=label%3Ai18n) o aprine
una nuova.

## Sviluppo

### Prerequisiti

- Docker e Docker Compose
- Python 3.11+ (per lo sviluppo locale del backend)
- Node.js 18+ (per lo sviluppo locale del frontend)

### Esecuzione in locale

```bash
# Avvia tutti i servizi
docker-compose up

# Oppure esegui il backend separatamente
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Oppure esegui il frontend separatamente
cd frontend
npm install
npm run dev
```

### Gestione del database

```bash
# Resetta il database ed esegui le migrazioni
./scripts/reset-db.sh

# Carica i dati demo (inglese - predefinito)
./scripts/seed-demo.sh

# Carica i dati demo (spagnolo)
./scripts/seed-demo.sh --lang es

# Configurazione completa (reset + seed in un solo comando)
./scripts/setup-demo.sh
```

### Esecuzione dei test

```bash
# Unit + integrazione backend (in Docker)
docker-compose exec backend python -m pytest -v

# Round-trip Alembic lento (opzionale, vedi docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Unit frontend (vitest)
cd frontend
npm run test
```

**L'E2E nel browser (Playwright)** si trova in `frontend/tests/e2e/` e pilota
l'intero stack su `localhost:3000` → `:8000`. Gira sull'host perché il container
frontend Alpine non può avviare Chromium.

```bash
# Configurazione una tantum
(cd frontend && npm install && npx playwright install chromium)

# Assicurati prima che lo stack sia attivo e con i dati caricati
docker-compose up -d
./scripts/seed-demo.sh

# Suite E2E completa (nav + RBAC + smoke test della scheda paziente)
./scripts/e2e.sh

# Singolo file
./scripts/e2e.sh rbac

# Interfaccia interattiva
./scripts/e2e.sh --ui
```

Runbook completo + riferimento alle fixture: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Architettura

DentalPin utilizza un'architettura modulare a plugin. Ogni funzionalità è un modulo autonomo che:
- Dichiara i propri modelli SQLAlchemy
- Fornisce un router FastAPI
- Può sottoscrivere eventi di altri moduli

Per i dettagli consulta [ADR 0001 — architettura modulare a plugin](docs/adr/0001-modular-plugin-architecture.md) e [docs/technical/creating-modules.md](docs/technical/creating-modules.md).

## Licenza

Business Source License 1.1 (BSL 1.1)

**Concessione d'uso aggiuntiva:** Puoi usare DentalPin in produzione, purché tu non lo offra come SaaS commerciale per la gestione di studi dentistici.

**Data di cambio:** 4 anni dal rilascio

**Licenza di cambio:** Apache 2.0

Per i termini completi consulta [LICENSE](LICENSE).

## Contribuire

Per le linee guida consulta [CONTRIBUTING.md](CONTRIBUTING.md).

---

Sostenuto da [Dentaltix](https://www.dentaltix.com)
