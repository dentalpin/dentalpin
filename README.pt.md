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

**Software de gestão de clínicas dentárias com código-fonte disponível (BSL 1.1), que passa a Apache 2.0 quatro anos após a publicação.** Pacientes, odontograma,
agenda, planos de tratamento, faturação e um Copilot de IA integrado — modular,
self-hosted e API-first.

### ▶ [**Experimente a demo ao vivo**](https://demo.dentalpin.com)

Entre com `admin@demo.clinic` / `demo1234` — acesso completo de administrador a uma
clínica com dados de exemplo. É reposta todas as noites, por isso explore à vontade.

[![DentalPin — ficha de paciente com odontograma](docs/screenshots/patients.png)](https://demo.dentalpin.com)

<sub>[Site](https://www.dentalpin.com) · [Documentação](https://docs.dentalpin.com) · [Telegram](https://t.me/dentalpin) · [Mais capturas ↓](#capturas-de-ecrã)</sub>

## Porquê o DentalPin?

As clínicas dentárias de todo o mundo partilham as mesmas necessidades fundamentais: gerir pacientes, marcar consultas, acompanhar tratamentos e gerir a sua prática de forma eficiente. No entanto, o panorama do software está fragmentado em dezenas de soluções localizadas e de código fechado que prendem as clínicas a contratos caros e a tecnologia ultrapassada.

**Acreditamos que está na hora de mudar.**

O DentalPin assenta numa premissa simples: **uma plataforma aberta para clínicas dentárias em qualquer lugar**. Não mais uma solução regional, mas uma base global que qualquer clínica pode adotar, qualquer programador pode estender e qualquer comunidade pode localizar.

### Porquê agora?

A IA mudou fundamentalmente o que as equipas pequenas conseguem construir. Funcionalidades que antes exigiam grandes departamentos de desenvolvimento podem agora ser implementadas em dias. Esta é a nossa janela para criar o software dentário com código-fonte disponível (BSL 1.1, que passa a Apache 2.0 quatro anos após a publicação) que já devia existir há anos — antes de as clínicas ficarem presas a sistemas legacy dos quais não conseguem escapar.

### Os nossos princípios

- **Código-fonte disponível (BSL 1.1)** — Os dados da sua clínica pertencem-lhe. O seu software também.
- **Modular** — Comece simples, adicione o que precisar. Não pague por funcionalidades que nunca vai usar.
- **Global por Design** — Construído para a localização desde o primeiro dia. O mesmo núcleo, qualquer idioma, qualquer país.
- **API-First** — Cada funcionalidade é uma API. Integre com tudo, automatize tudo.
- **Pronto para a IA** — Estruturado para a era da IA. Preparado para agendamento inteligente, apoio à decisão clínica e automação de fluxos de trabalho.

### A visão

Não estamos apenas a construir software — estamos a construir a base de um ecossistema. Uma plataforma onde os programadores contribuem com módulos, as clínicas partilham melhorias e toda a comunidade dentária beneficia da inovação coletiva.

As clínicas merecem melhor do que software fechado e caro da década passada. O DentalPin é a alternativa aberta.

## ✨ Copilot de IA

O DentalPin inclui um **assistente de IA agêntico** integrado que transforma toda a clínica em algo com que pode simplesmente conversar. Peça-lhe para encontrar um paciente, libertar uma vaga, dar seguimento a um orçamento sem resposta ou fazer-lhe um resumo do dia — em espanhol ou inglês correntes — e ele age sobre os seus dados reais.

![AI Copilot](docs/screenshots/ia.png)

Isto não é um chatbot acrescentado por cima. O Copilot é um verdadeiro agente que **planeia e executa tarefas multi-etapa** chamando as mesmas operações que a interface, em pacientes, agenda, reconvocações, orçamentos, pagamentos e relatórios.

- **Faz, não se limita a responder.** O agente executa ferramentas reais — procurar pacientes, marcar ou remarcar consultas, registar um pagamento, obter os recebimentos do mês — e encadeia-as para completar uma tarefa de princípio a fim.
- **Nunca pode exceder a sua função.** Cada chamada de ferramenta é re-verificada contra as permissões RBAC do utilizador que a invoca, no ponto de controlo da execução. O Copilot pode ver e fazer *exatamente* o que esse utilizador poderia fazer através da interface — nada mais, limitado à sua clínica.
- **Os seus dados estão protegidos.** Os dados de saúde (PHI) são ocultados antes de qualquer coisa sair para o fornecedor de LLM: nomes de pacientes, telefones, emails e identificadores são substituídos por tokens deterministas, e as ferramentas clínicas de texto livre são totalmente excluídas do caminho cloud. A ocultação está ativa por predefinição.
- **As escritas perguntam primeiro.** Qualquer ação que altere dados (marcações, pagamentos, edições) pausa a meio da conversa para a sua confirmação explícita antes de ser executada.
- **Fluxos de trabalho guiados.** Playbooks prontos a usar — *Briefing diário*, *Preparar uma consulta*, *Preencher uma vaga*, *Reconvocações pendentes*, *Orçamentos sem resposta* — iniciam tarefas multi-etapa comuns num só toque.
- **Briefings proativos.** Opte por receber um resumo matinal determinista enviado por email à sua equipa, com a agenda do dia, as reconvocações pendentes e os orçamentos em aberto — sem LLM, sem dados de saúde fora do sistema.
- **Modular por design.** O Copilot consome ferramentas publicadas por cada módulo através de um registo partilhado; cada módulo contribui com as suas próprias capacidades, pelo que o agente cresce automaticamente à medida que novos módulos são instalados.

Independente do fornecedor por baixo do capô (uma abstração de fornecedor de LLM), com fornecedor, modelo e orçamentos de tokens por clínica configuráveis por implantação. Arquitetura: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Site

Visite [**dentalpin.com**](https://www.dentalpin.com) para informações sobre o produto, funcionalidades e detalhes comerciais.

## Comunidade

Junte-se ao nosso [**canal de Telegram**](https://t.me/dentalpin) para suporte, ajuda com a instalação e perguntas.

## Capturas de ecrã

### Painel de controlo
![Dashboard](docs/screenshots/home.png)

### Gestão de pacientes
![Patients](docs/screenshots/patients.png)

### Agenda semanal
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Agenda Kanban
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Gráfico de pagamentos
![Payments Chart](docs/screenshots/payments-chart.png)

### Definições
![Settings](docs/screenshots/settings.png)

## Instalação

Imagens pré-construídas, sem clone, sem build. Em qualquer servidor com Docker:

```bash
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dentalpin/dentalpin/main/Caddyfile
curl -o .env https://raw.githubusercontent.com/dentalpin/dentalpin/main/.env.prod.example

# Defina PUBLIC_URL, POSTGRES_PASSWORD e SECRET_KEY no .env e depois:
docker compose -f docker-compose.prod.yml up -d
```

Aponte um domínio para o servidor, defina `PUBLIC_URL=https://your-domain` e o TLS é
provisionado no primeiro arranque — o Caddy fica à frente dos dois serviços numa única
origem, pelo que não há CORS nem certificados para renovar. Defina `SEED_ON_STARTUP=1`
para carregar a clínica de demonstração e explorar antes de entrar em produção.

Imagens: [`dentalpin-backend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-backend) ·
[`dentalpin-frontend`](https://github.com/dentalpin/dentalpin/pkgs/container/dentalpin-frontend)

## Início rápido (desenvolvimento)

Compila a partir do código-fonte, com hot reload:

```bash
# Iniciar os serviços
docker-compose up -d

# Semear dados de demonstração (inglês por predefinição)
./scripts/seed-demo.sh

# Ou semear em espanhol
./scripts/seed-demo.sh --lang es

# Clínica de demonstração com GST da Índia (interface em tâmil, ou em inglês com --country in)
./scripts/seed-demo.sh --lang ta
```

Abra http://localhost:3000

### Credenciais de demonstração

Todos os utilizadores têm a palavra-passe: `demo1234`

| Email | Função | Nome (EN) | Nome (ES) |
|-------|--------|-----------|-----------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

Consulte [docs/user-manual/en/demo.md](docs/user-manual/en/demo.md) para todos os detalhes sobre os dados de demonstração.

## Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 4 + Nuxt UI |
| Base de dados | PostgreSQL 15 |
| Autenticação | JWT com refresh tokens |

## Funcionalidades

### Copilot de IA
- **Assistente agêntico** — Agente conversacional que planeia e executa tarefas multi-etapa em pacientes, agenda, reconvocações, orçamentos, pagamentos e relatórios, chamando operações reais
- **Paridade RBAC** — Cada ação é re-verificada contra as permissões do utilizador; o agente só pode fazer o que esse utilizador poderia fazer através da interface, limitado à sua clínica
- **Ocultação de PHI** — Identificadores de pacientes tokenizados antes de chegarem ao LLM; os dados clínicos de texto livre ficam fora do caminho cloud. Ativa por predefinição
- **Escritas confirmadas** — As ações que alteram dados pausam a meio da conversa para confirmação explícita do utilizador
- **Fluxos de trabalho e resumo diário** — Playbooks de um toque (briefing diário, preparar uma consulta, preencher uma vaga) mais um resumo matinal proativo por email, opcional
- **Multilingue e independente do fornecedor** — Fala consigo no idioma da sua interface; fornecedor de LLM, modelo e orçamento de tokens por clínica configuráveis

### Gestão clínica
- **Fichas de pacientes** — Perfis completos de pacientes com dados pessoais, informações de contacto, historial médico e notas
- **Carta dentária (Odontograma)** — Diagrama dentário interativo com acompanhamento de tratamentos por dente/superfície
- **Calendário de consultas** — Vistas semanal e diária com arrastar e largar, colunas por profissional, deteção de conflitos
- **Catálogo de tratamentos** — Catálogo personalizável com códigos, preços, tipos de IVA e categorias

### Gestão financeira
- **Orçamentos** — Criação de orçamentos de tratamento, acompanhamento do fluxo de aprovação (rascunho → pendente → aprovado/rejeitado), captura da assinatura do paciente, geração de PDF
- **Faturas** — Geração de faturas a partir de orçamentos ou de forma independente, numeração automática, múltiplos métodos de pagamento, exportação para PDF
- **Pagamentos** — Registo de pagamentos parciais, histórico de pagamentos, cálculo de saldo

### Gestão da prática
- **Controlo de acesso baseado em funções** — Cinco funções (admin, dentista, higienista, assistente, rececionista) com permissões granulares
- **Gestão de gabinetes/salas** — Definição de salas de tratamento com horários e cores
- **Gestão de profissionais** — Atribuição de consultas a dentistas/higienistas específicos

### Experiência de utilizador
- **Seletores visuais** — Menus pendentes inteligentes que mostram pacientes recentes e tratamentos populares
- **Interface em nove idiomas** — Inglês, espanhol, francês, português, tâmil, alemão, húngaro, polaco e italiano — aplicação principal e todos os módulos
- **Modo escuro** — Mudança de tema de acordo com o sistema
- **Design responsivo** — Funciona em desktop e tablet

### Funcionalidades técnicas
- **Arquitetura modular** — Sistema baseado em plugins para fácil extensibilidade
- **Bus de eventos** — Comunicação entre módulos para notificações e integrações
- **API REST** — API completa com documentação OpenAPI
- **Atualizações em tempo real** — Interface reativa com atualizações otimistas

## Idiomas

A interface é disponibilizada em **nove idiomas** — English, Español, Français, Português,
தமிழ் (Tamil), Deutsch, Magyar, Polski e Italiano — cobrindo a aplicação principal **e
todas as camadas de módulos**, com um teste de paridade de chaves imposto na CI para que
as localizações não divirjam silenciosamente. O polaco usa as suas regras completas de
plural com três formas.

As comunicações dirigidas ao paciente (modelos de email, PDFs) são atualmente geradas em
**cinco idiomas** (es, en, fr, pt, ta); cada clínica escolhe o seu idioma de comunicação
independentemente do idioma da interface da equipa.

Quer o seu idioma? Adicionar um é uma contribuição apenas de tradução — veja as
[issues de i18n](https://github.com/dentalpin/dentalpin/issues?q=label%3Ai18n) ou
abra uma nova.

## Desenvolvimento

### Pré-requisitos

- Docker e Docker Compose
- Python 3.11+ (para desenvolvimento local do backend)
- Node.js 18+ (para desenvolvimento local do frontend)

### Execução local

```bash
# Iniciar todos os serviços
docker-compose up

# Ou executar o backend em separado
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Ou executar o frontend em separado
cd frontend
npm install
npm run dev
```

### Gestão da base de dados

```bash
# Repor a base de dados e executar as migrações
./scripts/reset-db.sh

# Semear dados de demonstração (inglês — predefinição)
./scripts/seed-demo.sh

# Semear dados de demonstração (espanhol)
./scripts/seed-demo.sh --lang es

# Configuração completa (reset + seed num único comando)
./scripts/setup-demo.sh
```

### Execução de testes

```bash
# Unitários + integração do backend (em Docker)
docker-compose exec backend python -m pytest -v

# Round-trip Alembic lento (opt-in, ver docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Unitários do frontend (vitest)
cd frontend
npm run test
```

**E2E no navegador (Playwright)** vive em `frontend/tests/e2e/` e conduz
a stack completa em `localhost:3000` → `:8000`. Corre no host porque
o container Alpine do frontend não consegue lançar o Chromium.

```bash
# Configuração única inicial
(cd frontend && npm install && npx playwright install chromium)

# Garanta primeiro que a stack está levantada e semeada
docker-compose up -d
./scripts/seed-demo.sh

# Suite E2E completa (nav + RBAC + smoke test do detalhe de paciente)
./scripts/e2e.sh

# Um único ficheiro
./scripts/e2e.sh rbac

# Interface interativa
./scripts/e2e.sh --ui
```

Runbook completo + referência de fixtures: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Arquitetura

O DentalPin usa uma arquitetura modular de plugins. Cada funcionalidade é um módulo autónomo que:
- Declara os seus modelos SQLAlchemy
- Fornece um router FastAPI
- Pode subscrever eventos de outros módulos

Consulte [docs/adr/0001-modular-plugin-architecture.md](docs/adr/0001-modular-plugin-architecture.md) para mais detalhes.

## Licença

Business Source License 1.1 (BSL 1.1)

**Concessão de uso adicional:** Pode usar o DentalPin em produção, desde que não o ofereça como SaaS comercial para gestão de clínicas dentárias.

**Data de mudança:** 4 anos a partir do lançamento

**Licença de mudança:** Apache 2.0

Consulte [LICENSE](LICENSE) para os termos completos.

## Contribuir

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para as diretrizes.

---

Apoiado por [Dentaltix](https://www.dentaltix.com)
