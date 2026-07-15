# DentalPin

[![en](https://img.shields.io/badge/lang-en-red.svg)](./README.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](./README.es.md)
[![fr](https://img.shields.io/badge/lang-fr-blue.svg)](./README.fr.md)

Logiciel open source de gestion de cliniques dentaires. Conçu avec une architecture modulaire pour l'extensibilité.

## Pourquoi DentalPin ?

Les cliniques dentaires du monde entier partagent les mêmes besoins fondamentaux : gérer les patients, planifier les rendez-vous, suivre les traitements et exploiter leur pratique efficacement. Pourtant, le paysage logiciel est fragmenté en dizaines de solutions localisées et propriétaires qui enferment les cliniques dans des contrats coûteux et des technologies obsolètes.

**Nous croyons qu'il est temps d'agir.**

DentalPin repose sur un principe simple : **une plateforme ouverte pour les cliniques dentaires partout**. Pas une autre solution régionale, mais une base mondiale que toute clinique peut adopter, que tout développeur peut étendre, et que toute communauté peut localiser.

### Pourquoi maintenant ?

L'IA a fondamentalement changé ce que les petites équipes peuvent construire. Des fonctionnalités qui nécessitaient autrefois de grands départements de développement peuvent désormais être implémentées en quelques jours. C'est notre fenêtre pour créer le logiciel dentaire open source qui aurait dû exister il y a des années — avant que les cliniques ne soient enfermées dans des systèmes hérités dont elles ne peuvent plus s'extraire.

### Nos principes

- **Open Source** — Les données de votre clinique vous appartiennent. Votre logiciel aussi.
- **Modulaire** — Commencez simplement, ajoutez ce dont vous avez besoin. Ne payez pas pour des fonctionnalités que vous n'utiliserez jamais.
- **Global dès la conception** — Conçu pour la localisation dès le premier jour. Même cœur, n'importe quelle langue, n'importe quel pays.
- **API-First** — Chaque fonctionnalité est une API. Intégrez tout, automatisez tout.
- **Prêt pour l'IA** — Structuré pour l'ère de l'IA. Prêt pour la planification intelligente, l'aide à la décision clinique et l'automatisation des flux de travail.

### La vision

Nous ne construisons pas seulement un logiciel — nous posons les fondations d'un écosystème. Une plateforme où les développeurs contribuent des modules, les cliniques partagent des améliorations, et toute la communauté dentaire bénéficie de l'innovation collective.

Les cliniques méritent mieux que des logiciels propriétaires et coûteux de la décennie précédente. DentalPin est l'alternative ouverte.

## ✨ Copilot IA

DentalPin est livré avec un **assistant IA agentic intégré** qui transforme toute la clinique en quelque chose avec quoi vous pouvez simplement discuter. Demandez-lui de trouver un patient, libérer un créneau, relancer un devis sans réponse, ou vous faire un briefing de la journée — en français, espagnol ou anglais — et il agit sur vos données réelles.

![AI Copilot](docs/screenshots/ia.png)

Ce n'est pas un chatbot ajouté en catastrophe. Le Copilot est un véritable agent qui **planifie et exécute des tâches multi-étapes** en appelant les mêmes opérations que l'interface utilisateur, à travers les patients, l'agenda, les rappels, les devis, les paiements et les rapports.

- **Il agit, pas seulement il répond.** L'agent exécute de vrais outils — rechercher des patients, réserver ou déplacer des rendez-vous, enregistrer un paiement, extraire les encaissements du mois — et les enchaîne pour achever une tâche de bout en bout.
- **Il ne dépasse jamais votre rôle.** Chaque appel d'outil est re-vérifié par rapport aux permissions RBAC de l'utilisateur appelant au point de contrôle d'exécution. Le Copilot peut voir et faire *exactement* ce que cet utilisateur pourrait faire via l'interface — rien de plus, limité à sa clinique.
- **Vos données sont protégées.** Les données de santé sont masquées avant tout envoi vers le fournisseur LLM : noms, téléphones, e-mails et identifiants sont remplacés par des jetons déterministes, et les outils cliniques en texte libre sont exclus du chemin cloud. Le masquage est activé par défaut.
- **Les écritures demandent d'abord.** Toute action modifiant des données (réservation, paiements, modifications) fait une pause en milieu de conversation pour votre confirmation explicite avant de s'exécuter.
- **Flux de travail guidés.** Des playbooks prêts à l'emploi — *Briefing matinal*, *Préparer une consultation*, *Remplir un créneau*, *Rappels dus*, *Devis sans réponse* — lancent des tâches multi-étapes courantes en un tap.
- **Briefings proactifs.** Optez pour un digest matinal déterministe envoyé par e-mail à votre équipe, résumant l'agenda du jour, les rappels dus et les devis en attente — sans LLM, sans données de santé hors site.
- **Modulaire par design.** Le Copilot consomme des outils publiés par chaque module via un registre partagé ; chaque module contribue ses propres capacités, donc l'agent croît automatiquement à mesure que de nouveaux modules sont installés.

Agnostique au fournisseur en couche interne (abstraction du fournisseur LLM), avec modèle, fournisseur et budgets de jetons par clinique configurables par déploiement. Architecture : [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Site web

Rendez-vous sur [**dentalpin.com**](https://www.dentalpin.com) pour des informations produit, des fonctionnalités et des détails commerciaux.

## Communauté

Rejoignez notre [**chaîne Telegram**](https://t.me/dentalpin) pour du support, de l'aide à l'installation et des questions.

## Captures d'écran

### Copilot IA
![AI Copilot](docs/screenshots/ia.png)

### Tableau de bord
![Dashboard](docs/screenshots/home.png)

### Gestion des patients
![Patients](docs/screenshots/patients.png)

### Agenda hebdomadaire
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Planning Kanban
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Graphique des paiements
![Payments Chart](docs/screenshots/payments-chart.png)

### Paramètres
![Settings](docs/screenshots/settings.png)

## Démarrage rapide

```bash
# Démarrer les services
docker-compose up -d

# Peupler les données démo (anglais par défaut)
./scripts/seed-demo.sh

# Ou en espagnol
./scripts/seed-demo.sh --lang es

# Ou en français
./scripts/seed-demo.sh --lang fr
```

Ouvrir http://localhost:3000

### Identifiants de démo

Tous les utilisateurs ont le mot de passe : `demo1234`

| Email | Rôle | Nom (EN) | Nom (ES) | Nom (FR) |
|-------|------|----------|----------|----------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López | Dr. Marie Dubois |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez | Thomas Moreau |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz | Camille Petit |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez | Julie Bernard |

Voir [docs/user-manual/demo.md](docs/user-manual/demo.md) pour les détails complets sur les données démo.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 3 + Nuxt UI |
| Base de données | PostgreSQL 15 |
| Authentification | JWT avec refresh tokens |

## Fonctionnalités

### Copilot IA
- **Assistant agentic** — Agent conversationnel qui planifie et exécute des tâches multi-étapes à travers les patients, l'agenda, les rappels, les devis, les paiements et les rapports en appelant de vraies opérations
- **Parité RBAC** — Chaque action re-vérifiée par rapport aux permissions de l'utilisateur ; l'agent ne peut faire que ce que cet utilisateur pourrait faire via l'interface, limité à sa clinique
- **Masquage des données de santé** — Identifiants des patients tokenisés avant d'atteindre le LLM ; les données cliniques en texte libre restent hors du chemin cloud. Activé par défaut
- **Écritures confirmées** — Les actions modifiant des données font une pause pour confirmation explicite de l'utilisateur en milieu de conversation
- **Flux de travail et digest** — Playbooks en un tap (briefing matinal, préparer une consultation, remplir un créneau) plus un digest matinal par e-mail proactif optionnel
- **Bilingue et agnostique au fournisseur** — Fonctionne en français, espagnol et anglais ; fournisseur LLM, modèle et budget de jetons par clinique configurables

### Gestion clinique
- **Dossiers patients** — Profils complets avec données personnelles, coordonnées, antécédents médicaux et notes
- **Carte dentaire (Odontogramme)** — Diagramme dentaire interactif avec suivi des traitements par dent/surface
- **Calendrier des rendez-vous** — Vues hebdomadaire et journalière avec glisser-déposer, colonnes professionnelles, détection de conflits
- **Catalogue de traitements** — Catalogue personnalisable avec codes, prix, types de TVA et catégories

### Gestion financière
- **Devis** — Création de devis de traitement, suivi du workflow d'approbation (brouillon → en attente → approuvé/rejeté), capture de signature patient, génération PDF
- **Factures** — Génération de factures à partir de devis ou de manière autonome, numérotation automatique, modes de paiement multiples, export PDF
- **Paiements** — Suivi des paiements partiels, historique des paiements, calcul du solde

### Gestion de la pratique
- **Contrôle d'accès basé sur les rôles** — Cinq rôles (admin, dentiste, hygiéniste, assistant, réceptionniste) avec permissions granulaires
- **Gestion des cabinets/cabinets** — Définition des salles de traitement avec emplois du temps et couleurs
- **Gestion des professionnels** — Attribution des rendez-vous à des dentistes/hygénistes spécifiques

### Expérience utilisateur
- **Sélecteurs visuels** — Menus déroulants intelligents affichant les patients récents et les traitements populaires
- **Interface bilingue** — Localisation complète en français, espagnol et anglais
- **Mode sombre** — Basculement de thème adapté au système
- **Design réactif** — Fonctionne sur ordinateur et tablette

### Fonctionnalités techniques
- **Architecture modulaire** — Système basé sur des plugins pour une extensibilité facile
- **Bus d'événements** — Communication inter-modules pour les notifications et intégrations
- **API REST** — API complète avec documentation OpenAPI
- **Mises à jour en temps réel** — Interface réactive avec mises à jour optimistes

## Développement

### Prérequis

- Docker et Docker Compose
- Python 3.11+ (pour le développement local du backend)
- Node.js 18+ (pour le développement local du frontend)

### Exécution locale

```bash
# Démarrer tous les services
docker-compose up

# Ou exécuter le backend séparément
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Ou exécuter le frontend séparément
cd frontend
npm install
npm run dev
```

### Gestion de la base de données

```bash
# Réinitialiser la base et appliquer les migrations
./scripts/reset-db.sh

# Peupler les données démo (anglais - par défaut)
./scripts/seed-demo.sh

# Peupler les données démo (espagnol)
./scripts/seed-demo.sh --lang es

# Peupler les données démo (français)
./scripts/seed-demo.sh --lang fr

# Configuration complète (réinitialisation + peuplement en une commande)
./scripts/setup-demo.sh
```

### Exécution des tests

```bash
# Tests unitaires + intégration backend (dans Docker)
docker-compose exec backend python -m pytest -v

# Round-trip Alembic lent (optionnel, voir docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Tests unitaires frontend (vitest)
cd frontend
npm run test
```

**E2E navigateur (Playwright)** se trouve dans `frontend/tests/e2e/` et pilote
la pile complète sur `localhost:3000` → `:8000`. S'exécute sur l'hôte car
le conteneur frontend Alpine ne peut pas lancer Chromium.

```bash
# Configuration initiale
(cd frontend && npm install && npx playwright install chromium)

# Assurez-vous que la pile est démarrée et peuplée d'abord
docker-compose up -d
./scripts/seed-demo.sh

# Suite E2E complète (nav + RBAC + smoke test détail patient)
./scripts/e2e.sh

# Un seul fichier
./scripts/e2e.sh rbac

# Interface interactive
./scripts/e2e.sh --ui
```

Runbook complet + référence des fixtures : [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Architecture

DentalPin utilise une architecture modulaire de type plugin. Chaque fonctionnalité est un module autonome qui :
- Déclare ses modèles SQLAlchemy
- Fournit un routeur FastAPI
- Peut s'abonner aux événements d'autres modules

Voir [docs/architecture.md](docs/architecture.md) pour les détails.

## Licence

Business Source License 1.1 (BSL 1.1)

**Limitation d'utilisation :** Vous ne pouvez pas proposer DentalPin en tant que SaaS commercial pour la gestion de cliniques dentaires.

**Date de conversion :** 4 ans après la publication

**Licence de conversion :** Apache 2.0

Voir [LICENSE](LICENSE) pour les conditions complètes.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives.

---

Porté par [Dentaltix](https://www.dentaltix.com)
