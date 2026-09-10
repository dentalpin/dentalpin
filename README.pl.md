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

**Oprogramowanie o dostępnym kodzie źródłowym (BSL 1.1) do zarządzania gabinetem stomatologicznym, przechodzące na Apache 2.0 cztery lata po publikacji.** Pacjenci,
diagram zębowy, terminarz, plany leczenia, fakturowanie i wbudowany copilot AI —
modułowe, self-hosted, API-first.

### ▶ [**Wypróbuj demo na żywo**](https://demo.dentalpin.com)

Zaloguj się jako `admin@demo.clinic` / `demo1234` — pełny dostęp administratora do
gabinetu z przykładowymi danymi. Baza resetuje się co noc, więc śmiało testuj wszystko.

[![DentalPin — karta pacjenta z diagramem zębowym](docs/screenshots/patients.png)](https://demo.dentalpin.com)

<sub>[Strona](https://www.dentalpin.com) · [Dokumentacja](https://docs.dentalpin.com) · [Telegram](https://t.me/dentalpin) · [Więcej zrzutów ekranu ↓](#zrzuty-ekranu)</sub>

## Dlaczego DentalPin?

Gabinety stomatologiczne na całym świecie mają te same podstawowe potrzeby: zarządzanie pacjentami, planowanie wizyt, śledzenie leczenia i sprawne prowadzenie praktyki. Tymczasem rynek oprogramowania jest rozdrobniony na dziesiątki lokalnych, zamkniętych rozwiązań, które wiążą gabinety kosztownymi umowami i przestarzałą technologią.

**Uważamy, że czas na zmianę.**

DentalPin opiera się na prostym założeniu: **jedna otwarta platforma dla gabinetów stomatologicznych na całym świecie**. Nie kolejne rozwiązanie regionalne, lecz globalny fundament, który każdy gabinet może wdrożyć, każdy programista rozszerzyć, a każda społeczność zlokalizować.

### Dlaczego teraz?

AI fundamentalnie zmieniła to, co mogą zbudować małe zespoły. Funkcje, które kiedyś wymagały dużych działów rozwoju, dziś można wdrożyć w kilka dni. To nasza szansa, aby stworzyć oprogramowanie stomatologiczne o dostępnym kodzie źródłowym (BSL 1.1, przechodzące na Apache 2.0 cztery lata po publikacji), które powinno istnieć już lata temu — zanim gabinety zostały uwięzione w systemach legacy, z których nie mogą się wydostać.

### Nasze zasady

- **Dostępny kod źródłowy (BSL 1.1)** — Dane Twojego gabinetu należą do Ciebie. Twoje oprogramowanie też powinno.
- **Modułowość** — Zacznij prosto, dodawaj to, czego potrzebujesz. Nie płać za funkcje, których nigdy nie użyjesz.
- **Globalność w założeniu** — Zaprojektowany z myślą o lokalizacji od pierwszego dnia. Ten sam rdzeń, dowolny język, dowolny kraj.
- **API-first** — Każda funkcja to API. Integruj z czymkolwiek, automatyzuj wszystko.
- **Gotowość na AI** — Zbudowany z myślą o erze AI. Gotowy na inteligentne planowanie wizyt, wsparcie decyzji klinicznych i automatyzację pracy.

### Wizja

Nie budujemy tylko oprogramowania — budujemy fundament ekosystemu. Platformę, w której programiści tworzą moduły, gabinety dzielą się usprawnieniami, a cała społeczność stomatologiczna korzysta ze wspólnych innowacji.

Gabinety zasługują na coś lepszego niż zamknięte, drogie oprogramowanie sprzed dekady. DentalPin to otwarta alternatywa.

## ✨ AI Copilot

DentalPin ma wbudowanego **agentowego asystenta AI**, który zamienia cały gabinet w coś, z czym można po prostu porozmawiać. Poproś go o znalezienie pacjenta, zwolnienie terminu, upomnienie się o kosztorys bez odpowiedzi albo podsumowanie nadchodzącego dnia — zwykłym hiszpańskim lub angielskim — a on działa na Twoich prawdziwych danych.

![AI Copilot](docs/screenshots/ia.png)

To nie chatbot doklejony na wierzch. Copilot to prawdziwy agent, który **planuje i wykonuje wieloetapowe zadania**, wywołując te same operacje co interfejs — na pacjentach, terminarzu, wizytach kontrolnych, kosztorysach, płatnościach i raportach.

- **Działa, a nie tylko odpowiada.** Agent uruchamia prawdziwe narzędzia — wyszukuje pacjentów, umawia lub przekłada wizyty, rejestruje płatność, pobiera wpływy z bieżącego miesiąca — i łączy je w łańcuch, aby wykonać zadanie od początku do końca.
- **Nigdy nie przekroczy Twojej roli.** Każde wywołanie narzędzia jest ponownie sprawdzane względem uprawnień RBAC wywołującego użytkownika w punkcie kontrolnym wykonania. Copilot widzi i robi *dokładnie* to, co dany użytkownik mógłby zrobić przez interfejs — nic więcej, w granicach jego gabinetu.
- **Twoje dane są chronione.** Dane medyczne (PHI) są maskowane, zanim cokolwiek trafi do dostawcy LLM: imiona i nazwiska pacjentów, telefony, e-maile i identyfikatory są zastępowane deterministycznymi tokenami, a narzędzia kliniczne operujące na tekście swobodnym są całkowicie wyłączone ze ścieżki chmurowej. Maskowanie jest domyślnie włączone.
- **Zapisy najpierw pytają.** Każda akcja zmieniająca dane (rezerwacje, płatności, edycje) zatrzymuje się w trakcie rozmowy i czeka na Twoje wyraźne potwierdzenie przed wykonaniem.
- **Prowadzone przepływy pracy.** Gotowe scenariusze — *Poranne podsumowanie*, *Przygotuj wizytę*, *Wypełnij lukę*, *Zaległe wizyty kontrolne*, *Kosztorysy bez odpowiedzi* — uruchamiają typowe wieloetapowe zadania jednym dotknięciem.
- **Proaktywne podsumowania.** Włącz deterministyczny poranny raport wysyłany e-mailem do Twojego zespołu, podsumowujący plan dnia, zaległe wizyty kontrolne i otwarte kosztorysy — bez LLM, bez danych medycznych poza serwerem.
- **Modułowy w założeniu.** Copilot korzysta z narzędzi publikowanych przez każdy moduł we wspólnym rejestrze; każdy moduł wnosi własne możliwości, więc agent rozwija się automatycznie wraz z instalowaniem nowych modułów.

Pod maską niezależny od dostawcy (abstrakcja dostawcy LLM), z konfigurowanym per wdrożenie dostawcą, modelem i budżetem tokenów dla każdego gabinetu. Architektura: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Strona internetowa

Odwiedź [**dentalpin.com**](https://www.dentalpin.com), aby poznać informacje o produkcie, funkcje i szczegóły komercyjne.

## Społeczność

Dołącz do naszego [**kanału na Telegramie**](https://t.me/dentalpin) — wsparcie, pomoc w instalacji i pytania.

## Zrzuty ekranu

### Pulpit
![Dashboard](docs/screenshots/home.png)

### Zarządzanie pacjentami
![Patients](docs/screenshots/patients.png)

### Terminarz tygodniowy
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Terminarz Kanban
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Wykres płatności
![Payments Chart](docs/screenshots/payments-chart.png)

### Ustawienia
![Settings](docs/screenshots/settings.png)

## Instalacja

Gotowe obrazy, bez klonowania, bez budowania. Na dowolnym serwerze z Dockerem:

```bash
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/Caddyfile
curl -o .env https://raw.githubusercontent.com/dentalpin/dentalpin/main/.env.prod.example

# Ustaw PUBLIC_URL, POSTGRES_PASSWORD i SECRET_KEY w .env, a następnie:
docker compose -f docker-compose.prod.yml up -d
```

Skieruj domenę na serwer, ustaw `PUBLIC_URL=https://your-domain`, a TLS zostanie
skonfigurowany przy pierwszym uruchomieniu — Caddy obsługuje obie usługi z jednego
originu, więc nie ma CORS ani certyfikatu do odnawiania. Ustaw `SEED_ON_STARTUP=1`,
aby załadować gabinet demo i rozejrzeć się przed startem produkcyjnym.

Obrazy: [`dentalpin-backend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-backend) ·
[`dentalpin-frontend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-frontend)

## Szybki start (rozwój)

Buduje ze źródeł z hot reload:

```bash
# Uruchom usługi
docker-compose up -d

# Załaduj dane demo (domyślnie po angielsku)
./scripts/seed-demo.sh

# Lub załaduj po hiszpańsku
./scripts/seed-demo.sh --lang es

# Gabinet demo India GST (interfejs tamilski lub angielski z --country in)
./scripts/seed-demo.sh --lang ta
```

Otwórz http://localhost:3000

### Dane logowania do demo

Wszyscy użytkownicy mają hasło: `demo1234`

| E-mail | Rola | Imię i nazwisko (EN) | Imię i nazwisko (ES) |
|--------|------|----------------------|----------------------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

Pełne informacje o danych demo znajdziesz w [docs/user-manual/en/demo.md](docs/user-manual/en/demo.md).

## Stack technologiczny

| Warstwa | Technologia |
|---------|-------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 4 + Nuxt UI |
| Baza danych | PostgreSQL 15 |
| Uwierzytelnianie | JWT z refresh tokenami |

## Funkcje

### AI Copilot
- **Agentowy asystent** — Konwersacyjny agent, który planuje i wykonuje wieloetapowe zadania na pacjentach, terminarzu, wizytach kontrolnych, kosztorysach, płatnościach i raportach, wywołując prawdziwe operacje
- **Parytet RBAC** — Każda akcja ponownie sprawdzana względem uprawnień użytkownika; agent może zrobić tylko to, co dany użytkownik mógłby zrobić przez interfejs, w granicach jego gabinetu
- **Maskowanie danych medycznych (PHI)** — Identyfikatory pacjentów tokenizowane, zanim dotrą do LLM; kliniczne dane tekstowe pozostają poza ścieżką chmurową. Domyślnie włączone
- **Potwierdzane zapisy** — Akcje zmieniające dane zatrzymują się w trakcie rozmowy do wyraźnego potwierdzenia przez użytkownika
- **Przepływy pracy i raport dnia** — Scenariusze na jedno dotknięcie (poranne podsumowanie, przygotowanie wizyty, wypełnienie luki) oraz opcjonalny proaktywny poranny raport e-mail
- **Wielojęzyczny i niezależny od dostawcy** — Rozmawia z Tobą w języku Twojego interfejsu; konfigurowalny dostawca LLM, model i budżet tokenów per gabinet

### Zarządzanie kliniczne
- **Kartoteki pacjentów** — Kompletne profile pacjentów z danymi osobowymi, kontaktowymi, historią medyczną i notatkami
- **Diagram zębowy (odontogram)** — Interaktywny diagram zębów ze śledzeniem leczenia dla każdego zęba/powierzchni
- **Kalendarz wizyt** — Widoki tygodniowy i dzienny z przeciąganiem i upuszczaniem, kolumnami specjalistów, wykrywaniem konfliktów
- **Katalog zabiegów** — Konfigurowalny katalog z kodami, cenami, stawkami VAT i kategoriami

### Zarządzanie finansami
- **Kosztorysy** — Tworzenie kosztorysów leczenia, śledzenie procesu akceptacji (szkic → oczekujący → zaakceptowany/odrzucony), podpis pacjenta, generowanie PDF
- **Faktury** — Generowanie faktur z kosztorysów lub samodzielnych, automatyczna numeracja, wiele metod płatności, eksport do PDF
- **Płatności** — Śledzenie płatności częściowych, historia płatności, wyliczanie salda

### Zarządzanie gabinetem
- **Kontrola dostępu oparta na rolach** — Pięć ról (administrator, dentysta, higienistka, asystent, recepcjonista) z granularnymi uprawnieniami
- **Zarządzanie gabinetami/salami** — Definiowanie sal zabiegowych z harmonogramami i kolorami
- **Zarządzanie specjalistami** — Przypisywanie wizyt do konkretnych dentystów/higienistek

### Doświadczenie użytkownika
- **Selektory wizualne** — Inteligentne listy rozwijane z ostatnimi pacjentami i popularnymi zabiegami
- **Interfejs w dziewięciu językach** — angielski, hiszpański, francuski, portugalski, tamilski, niemiecki, węgierski, polski i włoski — rdzeń aplikacji i każdy moduł
- **Tryb ciemny** — Przełączanie motywu zgodnie z ustawieniami systemu
- **Responsywny design** — Działa na komputerze i tablecie

### Funkcje techniczne
- **Architektura modułowa** — System oparty na pluginach zapewniający łatwą rozszerzalność
- **Szyna zdarzeń** — Komunikacja między modułami dla powiadomień i integracji
- **REST API** — Kompletne API z dokumentacją OpenAPI
- **Aktualizacje w czasie rzeczywistym** — Reaktywny interfejs z optymistycznymi aktualizacjami

## Języki

Interfejs jest dostępny w **dziewięciu językach** — English, Español, Français,
Português, தமிழ் (Tamil), Deutsch, Magyar, Polski i Italiano — obejmując rdzeń
aplikacji **i każdą warstwę modułów**, z wymuszanym przez CI testem parytetu kluczy,
dzięki któremu tłumaczenia nie mogą się po cichu rozjechać. Polski używa pełnych
trzech form liczby mnogiej.

Komunikacja kierowana do pacjentów (szablony e-mail, PDF-y) jest obecnie generowana
w **pięciu językach** (es, en, fr, pt, ta); każdy gabinet wybiera język komunikacji
niezależnie od języka interfejsu personelu.

Chcesz swój język? Dodanie języka to wkład czysto tłumaczeniowy — zobacz
[zgłoszenia i18n](https://github.com/dentalpin/dentalpin/issues?q=label%3Ai18n)
lub otwórz nowe.

## Rozwój

### Wymagania wstępne

- Docker i Docker Compose
- Python 3.11+ (do lokalnej pracy nad backendem)
- Node.js 18+ (do lokalnej pracy nad frontendem)

### Uruchamianie lokalnie

```bash
# Uruchom wszystkie usługi
docker-compose up

# Lub uruchom backend osobno
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Lub uruchom frontend osobno
cd frontend
npm install
npm run dev
```

### Zarządzanie bazą danych

```bash
# Zresetuj bazę danych i uruchom migracje
./scripts/reset-db.sh

# Załaduj dane demo (angielski — domyślnie)
./scripts/seed-demo.sh

# Załaduj dane demo (hiszpański)
./scripts/seed-demo.sh --lang es

# Pełna konfiguracja (reset + dane demo jednym poleceniem)
./scripts/setup-demo.sh
```

### Uruchamianie testów

```bash
# Testy jednostkowe + integracyjne backendu (w Dockerze)
docker-compose exec backend python -m pytest -v

# Wolny round-trip Alembic (opcjonalny, zobacz docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Testy jednostkowe frontendu (vitest)
cd frontend
npm run test
```

**E2E w przeglądarce (Playwright)** znajduje się w `frontend/tests/e2e/` i steruje
pełnym stackiem pod `localhost:3000` → `:8000`. Działa na hoście, ponieważ kontener
frontendu na Alpine nie może uruchomić Chromium.

```bash
# Jednorazowa konfiguracja
(cd frontend && npm install && npx playwright install chromium)

# Najpierw upewnij się, że stack działa i ma załadowane dane
docker-compose up -d
./scripts/seed-demo.sh

# Pełny zestaw E2E (nawigacja + RBAC + smoke test karty pacjenta)
./scripts/e2e.sh

# Pojedynczy plik
./scripts/e2e.sh rbac

# Interaktywny interfejs
./scripts/e2e.sh --ui
```

Pełny runbook + opis fixture'ów: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Architektura

DentalPin używa modułowej architektury pluginów. Każda funkcja to samodzielny moduł, który:
- Deklaruje swoje modele SQLAlchemy
- Udostępnia router FastAPI
- Może subskrybować zdarzenia innych modułów

Szczegóły znajdziesz w [ADR 0001 — modułowa architektura pluginów](docs/adr/0001-modular-plugin-architecture.md) oraz [docs/technical/creating-modules.md](docs/technical/creating-modules.md).

## Licencja

Business Source License 1.1 (BSL 1.1)

**Dodatkowe prawo użytkowania:** Możesz używać DentalPin produkcyjnie, o ile nie oferujesz go jako komercyjnego SaaS do zarządzania gabinetami stomatologicznymi.

**Data zmiany:** 4 lata od wydania

**Licencja docelowa:** Apache 2.0

Pełne warunki znajdziesz w [LICENSE](LICENSE).

## Współtworzenie

Wytyczne znajdziesz w [CONTRIBUTING.md](CONTRIBUTING.md).

---

Wspierane przez [Dentaltix](https://www.dentaltix.com)
