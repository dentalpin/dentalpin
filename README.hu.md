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

**Elérhető forráskódú (BSL 1.1) fogászati rendelőirányító szoftver, amely a megjelenés után négy évvel Apache 2.0 licencre vált.** Páciensek, fogtérkép,
időpontkezelés, kezelési tervek, számlázás és beépített AI copilot — moduláris,
self-hosted, API-first.

### ▶ [**Próbálja ki az élő demót**](https://demo.dentalpin.com)

Jelentkezzen be az `admin@demo.clinic` / `demo1234` adatokkal — teljes rendszergazdai
hozzáférés egy demóadatokkal feltöltött rendelőhöz. Minden éjjel visszaáll, így bátran
kipróbálhat bármit.

[![DentalPin — páciens adatlap fogtérképpel](docs/screenshots/patients.png)](https://demo.dentalpin.com)

<sub>[Weboldal](https://www.dentalpin.com) · [Dokumentáció](https://docs.dentalpin.com) · [Telegram](https://t.me/dentalpin) · [További képernyőképek ↓](#képernyőképek)</sub>

## Miért a DentalPin?

A fogorvosi rendelőknek világszerte ugyanazok az alapvető igényeik: a páciensek kezelése, az időpontok szervezése, a kezelések nyomon követése és a rendelő hatékony működtetése. A szoftverpiac mégis tucatnyi lokalizált, zárt forráskódú megoldásra tagolódik, amelyek drága szerződésekbe és elavult technológiába zárják a rendelőket.

**Úgy gondoljuk, ideje változtatni.**

A DentalPin egyszerű alapvetésre épül: **egyetlen nyílt platform a fogorvosi rendelők számára, bárhol a világon**. Nem egy újabb regionális megoldás, hanem globális alap, amelyet bármely rendelő bevezethet, bármely fejlesztő bővíthet, és bármely közösség lokalizálhat.

### Miért most?

Az MI alapjaiban változtatta meg, hogy mire képesek a kis csapatok. Azok a funkciók, amelyekhez korábban nagy fejlesztői részlegek kellettek, ma napok alatt megvalósíthatók. Ez a mi lehetőségünk arra, hogy megalkossuk azt az elérhető forráskódú (BSL 1.1, a megjelenés után négy évvel Apache 2.0) fogászati szoftvert, amelynek már évekkel ezelőtt léteznie kellett volna — mielőtt a rendelők olyan örökölt rendszerekbe záródtak, amelyekből nincs kiút.

### Alapelveink

- **Elérhető forráskód (BSL 1.1)** — A rendelője adatai Önt illetik. A szoftverének is így kellene lennie.
- **Moduláris** — Kezdje egyszerűen, és adja hozzá, amire szüksége van. Ne fizessen olyan funkciókért, amelyeket soha nem fog használni.
- **Alapból globális** — Az első naptól lokalizációra tervezve. Ugyanaz a mag, bármely nyelven, bármely országban.
- **API-first** — Minden funkció egy API. Integrálható bármivel, automatizálható minden.
- **MI-re kész** — Az MI korszakára strukturálva. Készen áll az intelligens időpontszervezésre, a klinikai döntéstámogatásra és a munkafolyamatok automatizálására.

### A jövőkép

Nem csupán szoftvert építünk — egy ökoszisztéma alapjait rakjuk le. Egy platformot, ahol a fejlesztők modulokkal járulnak hozzá, a rendelők megosztják egymással a fejlesztéseiket, és az egész fogászati közösség profitál a közös innovációból.

A rendelők jobbat érdemelnek az elmúlt évtized zárt és drága szoftvereinél. A DentalPin a nyílt alternatíva.

## ✨ AI Copilot

A DentalPin beépített **agentikus MI-asszisztenssel** érkezik, amely az egész rendelőt olyasvalamivé alakítja, amivel egyszerűen beszélgetni lehet. Kérje meg, hogy keressen meg egy pácienst, szabadítson fel egy időpontot, kövessen fel egy megválaszolatlan árajánlatot, vagy foglalja össze az Ön előtt álló napot — közérthető spanyol vagy angol nyelven — és a valós adatain cselekszik.

![AI Copilot](docs/screenshots/ia.png)

Ez nem egy utólag ráépített chatbot. A Copilot valódi ágens, amely **többlépéses feladatokat tervez meg és hajt végre** ugyanazokat a műveleteket meghívva, mint a felhasználói felület — a páciensek, a naptár, a visszahívások, az árajánlatok, a befizetések és a riportok területén.

- **Cselekszik, nem csak válaszol.** Az ágens valódi eszközöket futtat — páciensek keresése, időpont foglalása vagy átütemezése, befizetés rögzítése, a havi bevételek lekérdezése — és láncba fűzi őket, hogy egy feladatot az elejétől a végéig elvégezzen.
- **Soha nem lépheti túl az Ön szerepkörét.** Minden eszközhívás újraellenőrzésre kerül a hívó felhasználó RBAC-jogosultságai alapján a végrehajtási ellenőrzőponton. A Copilot *pontosan* azt láthatja és teheti, amit az adott felhasználó a felületen keresztül tehetne — semmivel sem többet, a saját rendelőjére korlátozva.
- **Az adatai védve vannak.** Az egészségügyi adatok (PHI) maszkolásra kerülnek, mielőtt bármi az LLM-szolgáltatóhoz jutna: a páciensnevek, telefonszámok, e-mail-címek és azonosítók determinisztikus tokenekre cserélődnek, a szabadszöveges klinikai eszközök pedig teljes egészében kimaradnak a felhő felé vezető útból. A maszkolás alapértelmezés szerint be van kapcsolva.
- **Az írások előbb kérdeznek.** Minden adatmódosító művelet (foglalás, befizetés, szerkesztés) a beszélgetés közben megáll, és az Ön kifejezett jóváhagyására vár a végrehajtás előtt.
- **Vezetett munkafolyamatok.** Kész forgatókönyvek — *Napi összefoglaló*, *Vizit előkészítése*, *Lyuk kitöltése*, *Esedékes visszahívások*, *Megválaszolatlan árajánlatok* — egyetlen érintéssel elindítják a gyakori többlépéses feladatokat.
- **Proaktív összefoglalók.** Igény szerint bekapcsolható determinisztikus reggeli összefoglaló, amelyet e-mailben kap meg a csapata a napi naptárról, az esedékes visszahívásokról és a nyitott árajánlatokról — LLM nélkül, egészségügyi adatok kiadása nélkül.
- **Modularitásra tervezve.** A Copilot az egyes modulok által egy közös registryn keresztül közzétett eszközöket használja; minden modul a saját képességeivel járul hozzá, így az ágens automatikusan bővül az új modulok telepítésével.

A motorháztető alatt szolgáltatófüggetlen (LLM-szolgáltatói absztrakcióval), telepítésenként konfigurálható szolgáltatóval, modellel és rendelőnkénti tokenkerettel. Architektúra: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Weboldal

Látogasson el a [**dentalpin.com**](https://www.dentalpin.com) oldalra a termékinformációkért, a funkciókért és a kereskedelmi részletekért.

## Közösség

Csatlakozzon a [**Telegram-csatornánkhoz**](https://t.me/dentalpin) támogatásért, telepítési segítségért és kérdésekkel.

## Képernyőképek

### Kezdőlap
![Dashboard](docs/screenshots/home.png)

### Páciensek kezelése
![Patients](docs/screenshots/patients.png)

### Heti naptár
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Kanban nézet
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Befizetések grafikonja
![Payments Chart](docs/screenshots/payments-chart.png)

### Beállítások
![Settings](docs/screenshots/settings.png)

## Telepítés

Előre elkészített image-ek, klónozás és build nélkül. Bármely Dockerrel futó szerveren:

```bash
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/Caddyfile
curl -o .env https://raw.githubusercontent.com/dentalpin/dentalpin/main/.env.prod.example

# Állítsa be a PUBLIC_URL, POSTGRES_PASSWORD és SECRET_KEY értékét a .env fájlban, majd:
docker compose -f docker-compose.prod.yml up -d
```

Irányítson egy domaint a szerverre, állítsa be a `PUBLIC_URL=https://your-domain`
értéket, és a TLS az első indításkor automatikusan létrejön — a Caddy egyetlen
originről szolgálja ki mindkét szolgáltatást, így nincs CORS és nincs megújítandó
tanúsítvány. Állítsa be a `SEED_ON_STARTUP=1` értéket a demórendelő betöltéséhez,
hogy élesítés előtt körülnézhessen.

Image-ek: [`dentalpin-backend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-backend) ·
[`dentalpin-frontend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-frontend)

## Gyors kezdés (fejlesztés)

Forrásból épít, hot reloaddal:

```bash
# Szolgáltatások indítása
docker-compose up -d

# Demóadatok betöltése (alapértelmezés szerint angolul)
./scripts/seed-demo.sh

# Vagy betöltés spanyolul
./scripts/seed-demo.sh --lang es

# Indiai GST demórendelő (tamil felület, vagy angol felület a --country in kapcsolóval)
./scripts/seed-demo.sh --lang ta
```

Nyissa meg: http://localhost:3000

### Demó belépési adatok

Minden felhasználó jelszava: `demo1234`

| E-mail | Szerepkör | Név (EN) | Név (ES) |
|--------|-----------|----------|----------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

A demóadatok teljes leírását lásd: [docs/user-manual/en/demo.md](docs/user-manual/en/demo.md).

## Technológiai stack

| Réteg | Technológia |
|-------|-------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 4 + Nuxt UI |
| Adatbázis | PostgreSQL 15 |
| Hitelesítés | JWT refresh tokenekkel |

## Funkciók

### AI Copilot
- **Agentikus asszisztens** — Társalgó ágens, amely valós műveleteket meghívva tervez meg és hajt végre többlépéses feladatokat a páciensek, a naptár, a visszahívások, az árajánlatok, a befizetések és a riportok területén
- **RBAC-paritás** — Minden művelet újraellenőrzésre kerül a felhasználó jogosultságai alapján; az ágens csak azt teheti, amit az adott felhasználó a felületen keresztül tehetne, a saját rendelőjére korlátozva
- **Egészségügyi adatok maszkolása (PHI)** — A páciensazonosítók tokenizálva jutnak csak az LLM elé; a szabadszöveges klinikai adatok nem kerülnek a felhő felé vezető útra. Alapértelmezés szerint bekapcsolva
- **Megerősített írások** — Az adatmódosító műveletek a beszélgetés közben megállnak a felhasználó kifejezett jóváhagyásáig
- **Munkafolyamatok és összefoglaló** — Egyérintéses forgatókönyvek (napi összefoglaló, vizit előkészítése, lyuk kitöltése), valamint igény szerint bekapcsolható proaktív reggeli e-mail-összefoglaló
- **Többnyelvű és szolgáltatófüggetlen** — A felülete nyelvén beszél Önnel; konfigurálható LLM-szolgáltató, modell és rendelőnkénti tokenkeret

### Klinikai adminisztráció
- **Páciensnyilvántartás** — Teljes páciensprofilok személyes adatokkal, elérhetőségekkel, kórtörténettel és jegyzetekkel
- **Fogtérkép (odontogram)** — Interaktív fogdiagram fogankénti/felszínenkénti kezeléskövetéssel
- **Időpontnaptár** — Heti és napi nézetek drag & drop funkcióval, kezelőnkénti oszlopokkal, ütközésészleléssel
- **Kezeléskatalógus** — Testreszabható katalógus kódokkal, árakkal, áfatípusokkal és kategóriákkal

### Pénzügyi adminisztráció
- **Árajánlatok** — Kezelési árajánlatok készítése, a jóváhagyási folyamat követése (piszkozat → függőben → elfogadva/elutasítva), páciensaláírás rögzítése, PDF-generálás
- **Számlák** — Számlák készítése árajánlatból vagy önállóan, automatikus sorszámozás, többféle fizetési mód, PDF-export
- **Befizetések** — Részfizetések követése, befizetési előzmények, egyenlegszámítás

### Rendelőmenedzsment
- **Szerepköralapú hozzáférés-kezelés** — Öt szerepkör (rendszergazda, fogorvos, dentálhigiénikus, asszisztens, recepciós) részletes jogosultságokkal
- **Kezelőhelyiségek kezelése** — Kezelőhelyiségek meghatározása beosztással és színekkel
- **Szakemberek kezelése** — Időpontok hozzárendelése adott fogorvosokhoz/dentálhigiénikusokhoz

### Felhasználói élmény
- **Vizuális választók** — Intelligens legördülő menük a legutóbbi páciensekkel és a népszerű kezelésekkel
- **Kilencnyelvű felület** — angol, spanyol, francia, portugál, tamil, német, magyar, lengyel és olasz — az alapalkalmazásban és minden modulban
- **Sötét mód** — A rendszerbeállításhoz igazodó témaváltás
- **Reszponzív dizájn** — Asztali gépen és tableten is működik

### Technikai jellemzők
- **Moduláris architektúra** — Pluginalapú rendszer az egyszerű bővíthetőségért
- **Eseménybusz** — Modulok közötti kommunikáció értesítésekhez és integrációkhoz
- **REST API** — Teljes API OpenAPI-dokumentációval
- **Valós idejű frissítések** — Reaktív felület optimista frissítésekkel

## Nyelvek

A felület **kilenc nyelven** érhető el — English, Español, Français, Português,
தமிழ் (Tamil), Deutsch, Magyar, Polski és Italiano — lefedve az alapalkalmazást
**és minden modulréteget**, CI által kikényszerített kulcsparitás-teszttel, hogy a
fordítások ne csúszhassanak szét észrevétlenül. A lengyel a teljes, háromalakú
többesszám-szabályait használja.

A páciensek felé irányuló kommunikáció (e-mail-sablonok, PDF-ek) jelenleg
**öt nyelven** készül (es, en, fr, pt, ta); minden rendelő a személyzeti felület
nyelvétől függetlenül választja meg a kommunikáció nyelvét.

Hiányzik az Ön nyelve? Egy új nyelv hozzáadása kizárólag fordítási feladat — nézze
meg az [i18n issue-kat](https://github.com/dentalpin/dentalpin/issues?q=label%3Ai18n),
vagy nyisson újat.

## Fejlesztés

### Előfeltételek

- Docker és Docker Compose
- Python 3.11+ (a backend helyi fejlesztéséhez)
- Node.js 18+ (a frontend helyi fejlesztéséhez)

### Futtatás helyben

```bash
# Minden szolgáltatás indítása
docker-compose up

# Vagy a backend futtatása külön
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Vagy a frontend futtatása külön
cd frontend
npm install
npm run dev
```

### Adatbázis-kezelés

```bash
# Adatbázis visszaállítása és a migrációk futtatása
./scripts/reset-db.sh

# Demóadatok betöltése (angol – alapértelmezett)
./scripts/seed-demo.sh

# Demóadatok betöltése (spanyol)
./scripts/seed-demo.sh --lang es

# Teljes beállítás (reset + betöltés egyetlen paranccsal)
./scripts/setup-demo.sh
```

### Tesztek futtatása

```bash
# Backend unit + integrációs tesztek (Dockerben)
docker-compose exec backend python -m pytest -v

# Lassú Alembic round-trip (opcionális, lásd docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Frontend unit tesztek (vitest)
cd frontend
npm run test
```

A **böngészős E2E (Playwright)** a `frontend/tests/e2e/` mappában található, és a
teljes stacket vezérli a `localhost:3000` → `:8000` címen. A hoszton fut, mert az
Alpine frontend konténer nem tudja elindítani a Chromiumot.

```bash
# Egyszeri beállítás
(cd frontend && npm install && npx playwright install chromium)

# Először győződjön meg róla, hogy a stack fut és fel van töltve adatokkal
docker-compose up -d
./scripts/seed-demo.sh

# Teljes E2E csomag (nav + RBAC + páciens-adatlap smoke teszt)
./scripts/e2e.sh

# Egyetlen fájl
./scripts/e2e.sh rbac

# Interaktív felület
./scripts/e2e.sh --ui
```

Teljes runbook + fixture-referencia: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Architektúra

A DentalPin moduláris pluginarchitektúrát használ. Minden funkció önálló modul, amely:
- Deklarálja a SQLAlchemy-modelljeit
- FastAPI routert biztosít
- Feliratkozhat más modulok eseményeire

A részleteket lásd: [ADR 0001 — moduláris pluginarchitektúra](docs/adr/0001-modular-plugin-architecture.md) és [docs/technical/creating-modules.md](docs/technical/creating-modules.md).

## Licenc

Business Source License 1.1 (BSL 1.1)

**Kiegészítő használati engedély:** A DentalPin éles környezetben is használható, amennyiben nem kínálja kereskedelmi SaaS-ként fogorvosi rendelők irányítására.

**Váltás dátuma:** a kiadástól számított 4 év

**Váltás utáni licenc:** Apache 2.0

A teljes feltételeket lásd: [LICENSE](LICENSE).

## Közreműködés

Az irányelveket lásd: [CONTRIBUTING.md](CONTRIBUTING.md).

---

Támogatja a [Dentaltix](https://www.dentaltix.com)
