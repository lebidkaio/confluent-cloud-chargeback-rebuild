# Confluent Billing Portal — Documentação Completa

> Plataforma de Chargeback/Showback para Confluent Cloud com dashboards Grafana, coleta automática de custos e API REST.

---

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Pré-requisitos](#pré-requisitos)
4. [Configuração e Execução](#configuração-e-execução)
5. [Variáveis de Ambiente](#variáveis-de-ambiente)
6. [Estrutura do Projeto](#estrutura-do-projeto)
7. [API REST](#api-rest)
8. [Coleta de Dados](#coleta-de-dados)
9. [Dashboards Grafana](#dashboards-grafana)
10. [Comandos Úteis](#comandos-úteis)
11. [Troubleshooting](#troubleshooting)

---

## Visão Geral

O **Confluent Billing Portal** é uma solução para monitoramento, análise e alocação de custos do Confluent Cloud. A plataforma:

- **Coleta automaticamente** dados de faturamento da API do Confluent Cloud
- **Normaliza e enriquece** os dados com dimensões organizacionais (org, env, cluster)
- **Armazena historicamente** em PostgreSQL para consultas de longo prazo (30+ dias)
- **Exporta métricas** para Prometheus para alertas em tempo real
- **Visualiza** tudo em 6 dashboards Grafana com queries SQL para dados históricos

### Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Backend/API | Python 3.11 + FastAPI |
| Banco de Dados | PostgreSQL 15 |
| Métricas | Prometheus |
| Dashboards | Grafana |
| Containerização | Docker + Docker Compose |
| Gerenciamento de Deps | Poetry |

---

### Fluxo de Dados

1. **Collector** busca dados de custos na API REST do Confluent Cloud
2. **Enricher** normaliza respostas brutas, distribui custos diários em registros horários e mapeia `resource_id` para `cluster_id`
3. **Storage** persiste no PostgreSQL nas tabelas `hourly_cost_facts` e tabelas de dimensão
4. **Exporter** lê os últimos 30 dias do banco e expõe como Gauge Prometheus (`ccloud_cost_usd_hourly`)
5. **Grafana** consulta **diretamente o PostgreSQL** via SQL para dashboards históricos, e o Prometheus para alertas

---

## Pré-requisitos

| Software | Versão Mínima |
|---|---|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Git | 2.30+ |

> **Nota:** Python e Poetry só são necessários para desenvolvimento local sem Docker.

---

## Configuração e Execução

### Passo 1 — Clonar o repositório

```bash
git clone <url-do-repositorio>
cd confluent-billing-portal
```

### Passo 2 — Configurar variáveis de ambiente

```bash
# Copiar o arquivo de exemplo
cp .env.example docker/.env

# Editar com suas credenciais da API Confluent
# (editor de sua preferência)
notepad docker/.env     # Windows
nano docker/.env        # Linux/Mac
```

**Campos obrigatórios para coleta de dados:**

```env
CONFLUENT_API_KEY=sua_api_key_aqui
CONFLUENT_API_SECRET=seu_api_secret_aqui
```

### Passo 3 — Subir a aplicação

```bash
# Via Makefile
make docker-up

# Ou diretamente
docker compose -f docker/docker-compose.yml up -d
```

### Passo 4 — Verificar se tudo subiu

```bash
docker ps --filter "name=billing" --format "table {{.Names}}\t{{.Status}}"
```

Resultado esperado:

```
NAMES                STATUS
billing-grafana      Up X minutes (healthy)
billing-prometheus   Up X minutes (healthy)
billing-app          Up X minutes (healthy)
billing-postgres     Up X minutes (healthy)
```

### Passo 5 — Acessar os serviços

| Serviço | URL | Credenciais |
|---|---|---|
| **Grafana** (Dashboards) | http://localhost:3000 | admin / admin |
| **API REST** (Swagger) | http://localhost:8000/docs | — |
| **Prometheus** | http://localhost:9090 | — |
| **PostgreSQL** | localhost:5432 | billing_user / billing_password |

### Passo 6 — Coletar dados (primeira vez)

A coleta pode ser disparada manualmente via API:

```bash
# Coletar custos do mês atual
curl -X POST http://localhost:8000/api/v1/costs/collect

# Verificar dados no banco
curl http://localhost:8000/api/v1/costs/summary
```

### Passo 7 — Visualizar Dashboards

1. Acesse http://localhost:3000
2. Faça login com `admin` / `admin`
3. Navegue para **Dashboards** no menu lateral
4. Todos os 6 dashboards estarão disponíveis automaticamente

---

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `CONFLUENT_API_KEY` | Chave de API do Confluent Cloud | — |
| `CONFLUENT_API_SECRET` | Segredo da API do Confluent Cloud | — |
| `CONFLUENT_CLOUD_URL` | URL base da API | `https://api.confluent.cloud` |
| `DATABASE_URL` | Connection string PostgreSQL | `postgresql://billing_user:billing_password@postgres:5432/billing_db` |
| `LOG_LEVEL` | Nível de log (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `ENVIRONMENT` | Ambiente (development, production) | `development` |
| `SCHEDULER_ENABLED` | Habilitar agendador de tarefas | `false` |
| `HOURLY_JOB_ENABLED` | Habilitar coleta a cada hora | `false` |
| `DAILY_JOB_ENABLED` | Habilitar coleta diária | `false` |
| `API_HOST` | Host do servidor | `0.0.0.0` |
| `API_PORT` | Porta do servidor | `8000` |

---

## Estrutura do Projeto

```
confluent-billing-portal/
├── docker/
│   ├── Dockerfile                  # Build multi-estágio Python 3.11
│   ├── docker-compose.yml          # Stack completa (4 serviços)
│   └── docker-compose.prod.yml     # Configuração de produção
│
├── src/
│   ├── main.py                     # Entrypoint FastAPI
│   ├── api/                        # Endpoints REST
│   │   ├── costs.py                #   /api/v1/costs/*
│   │   ├── dimensions.py           #   /api/v1/dimensions/*
│   │   └── health.py               #   /healthz
│   ├── collector/                  # Integração com API Confluent
│   │   ├── client.py               #   Cliente HTTP para billing API
│   │   └── service.py              #   Lógica de orquestração
│   ├── enricher/                   # Normalização e enriquecimento
│   │   └── normalizer.py           #   Transformação de dados brutos
│   ├── exporter/                   # Exportação Prometheus
│   │   └── metrics.py              #   Gauge ccloud_cost_usd_hourly
│   ├── jobs/                       # Agendamento de tarefas
│   │   └── scheduler.py            #   APScheduler (cron)
│   ├── storage/                    # Persistência
│   │   ├── database.py             #   SQLAlchemy engine
│   │   ├── models.py               #   ORM models
│   │   └── repository.py           #   Data access layer
│   └── common/                     # Utilitários
│       ├── config.py               #   Pydantic settings
│       └── logging.py              #   Structured logging
│
├── grafana/
│   ├── dashboards/                 # 6 dashboards JSON (provisionados)
│   └── provisioning/
│       ├── datasources/            # Config PostgreSQL + Prometheus
│       └── dashboards/             # Configuração de provisioning
│
├── config/
│   └── prometheus.yml              # Scrape config do Prometheus
│
├── migrations/
│   └── versions/                   # SQL de criação do schema
│
├── tests/                          # Testes unitários e integração
├── docs/                           # Esta documentação
├── Makefile                        # Atalhos de desenvolvimento
└── pyproject.toml                  # Dependências Python (Poetry)
```

---

## API REST

A API expõe os seguintes endpoints (documentação interativa em `/docs`):

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/` | Informações do serviço |
| `GET` | `/healthz` | Health check |
| `GET` | `/metrics` | Métricas Prometheus |
| `GET` | `/api/v1/costs/summary` | Resumo de custos |
| `POST` | `/api/v1/costs/collect` | Disparar coleta manual |
| `GET` | `/api/v1/dimensions/orgs` | Listar organizações |
| `GET` | `/api/v1/dimensions/envs` | Listar ambientes |
| `GET` | `/api/v1/dimensions/clusters` | Listar clusters |

---

## Coleta de Dados

### Processo Automatizado

Quando habilitado (`SCHEDULER_ENABLED=true`), o agendador executa:

- **Coleta horária**: Busca custos incrementais a cada hora
- **Coleta diária**: Reconciliação completa do dia anterior

### Modelo de Dados

A tabela principal é `hourly_cost_facts`:

| Coluna | Tipo | Descrição |
|---|---|---|
| `timestamp` | `TIMESTAMP` | Data/hora do registro |
| `org_id` | `VARCHAR` | ID da organização Confluent |
| `env_id` | `VARCHAR` | ID do ambiente (ex: `env-abc123`) |
| `cluster_id` | `VARCHAR` | ID do recurso (ex: `lkc-abc123`) |
| `product` | `VARCHAR` | Produto (KAFKA, CONNECT, FLINK, etc.) |
| `cost_usd` | `DECIMAL` | Custo em dólares (negativo = créditos) |
| `business_unit` | `VARCHAR` | Unidade de negócio |
| `cost_center` | `VARCHAR` | Centro de custo |
| `allocation_confidence` | `ENUM` | Confiança da alocação (high, medium, low) |
| `allocation_method` | `VARCHAR` | Método de alocação usado |

### Tabelas de Dimensão

| Tabela | Propósito |
|---|---|
| `dimensions_orgs` | Organizações com nomes e metadados |
| `dimensions_envs` | Ambientes com `display_name` (ex: "Production", "DEV") |
| `dimensions_clusters` | Clusters com tipo, região, cloud provider |

---

## Dashboards Grafana

Todos os dashboards utilizam **queries SQL diretas no PostgreSQL** para cobertura histórica de 30+ dias. O time range padrão é `now-30d` a `now`.

### 1. C-Level — Confluent Cloud Cost

**Arquivo:** `clevel-cost-overview.json`
**Público:** Executivos, gerência, tomadores de decisão

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Total Spend | Stat | Soma total dos custos positivos no período |
| Total Credits | Stat | Total de créditos/descontos aplicados |
| Net Cost | Stat | Custo líquido (spend - credits) |
| Daily Cost Trend | Time Series | Linha temporal de custos diários com tendência |
| Cost by Environment | Pie Chart | Distribuição de custos por ambiente (Production, DEV, etc.) |
| Top 10 Clusters | Bar Gauge | Os 10 clusters com maior custo |
| Cost by Product | Bar Gauge | Custos por produto (Kafka, Connect, Flink, Schema Registry) |
| Organization Overview | Table | Resumo por organização com total, clusters, dias ativos |

**Insights que proporciona:**
- Quanto estamos gastando no total com Confluent Cloud?
- Qual ambiente consome mais recursos?
- Quais clusters são os mais caros?
- Como os custos evoluem dia a dia?

---

### 2. Confluent Cloud Chargeback

**Arquivo:** `ccloud_chargeback.json`
**Público:** FinOps, gestores de custo, equipes de infraestrutura

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Data Coverage | Time Series | Quantidade de registros por dia (validação de cobertura) |
| Overall Cost Breakdown | Stat | Total Cost, Usage Cost e Credits em cards separados |
| Cost per Environment | Pie Chart | Distribuição de custos com nomes de ambiente legíveis |
| Cost per Kafka Cluster | Pie Chart | Custos dos clusters Kafka (filtro `lkc-*`) |
| Cost per Product Group | Pie Chart | Distribuição por produto |
| Cost per Resource Type | Pie Chart | Classificação de recursos (Kafka, Connector, Flink, Schema Registry) |
| Cost by Cluster | Bar Gauge | Top 15 clusters em ranking horizontal com gradiente |
| Environment Details | Row (colapsável) | Detalhamento stat por ambiente expandível |
| Kafka Cluster Details | Row (colapsável) | Detalhamento stat por cluster Kafka expandível |
| Resource Details | Row (colapsável) | Detalhamento stat por recurso expandível |
| Product Details | Row (colapsável) | Detalhamento stat por produto expandível |
| Chargeback Detail Table | Row (colapsável) | Tabela completa com Environment, Resource, Product, Total Cost, Avg Hourly, Days Active e Share % |

**Insights que proporciona:**
- Como alocar custos entre equipes/ambientes?
- Qual a participação percentual de cada cluster no custo total?
- Quais recursos estão ativos e por quantos dias?
- Qual o custo médio por hora de cada recurso?

---

### 3. Cost by Business Unit

**Arquivo:** `cost-by-business-unit.json`
**Público:** Gestores de negócio, controllers

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Cost by Product | Pie Chart | Distribuição de custos entre produtos |
| Cost by Environment | Pie Chart | Distribuição de custos entre ambientes |
| Summary Statistics | Stat | Total Spend, Active Clusters, Active Environments, Average Daily Cost |
| Daily Cost by Product | Time Series | Tendência diária empilhada por produto |
| Product × Environment Matrix | Table | Tabela cruzada mostrando custos médios diários de cada produto em cada ambiente |

**Insights que proporciona:**
- Qual produto consome mais orçamento?
- Como os custos se distribuem entre produção e não-produção?
- A tendência de custos está subindo ou estabilizando?
- Qual ambiente tem mais diversidade de produtos?

---

### 4. Cost by Cluster

**Arquivo:** `cost-by-cluster.json`
**Público:** Platform engineers, SREs, DevOps

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Total Cluster Cost | Stat | Soma de custos de todos os clusters |
| Active Clusters | Stat | Contagem de clusters distintos |
| Avg Daily Cost | Stat | Custo médio diário por cluster |
| Active Environments | Stat | Número de ambientes com clusters |
| Daily Cost by Cluster | Time Series | Tendência temporal empilhada por cluster |
| Cluster Ranking Table | Table | Ranking de clusters com Ambiente, Produto, Total Cost, Avg Daily, Days Active |
| Cost by Product | Pie Chart | Distribuição de custos dos clusters por produto |
| Environment × Cluster Matrix | Table | Cross-tab: custos de Kafka, Connectors, Flink, Schema Registry por ambiente |

**Insights que proporciona:**
- Quais clusters representam os maiores custos?
- Há clusters ociosos ou subutilizados?
- Como os custos se distribuem entre tipos de recurso por ambiente?
- Qual ambiente tem mais diversidade de clusters?

---

### 5. Historical Costs (SQL)

**Arquivo:** `historical_costs.json`
**Público:** Analistas financeiros, engenheiros de dados, auditoria

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| 30-Day Cost Trend by Product | Time Series | Linha temporal empilhada de custos por produto |
| Product Cost Summary | Bar Gauge | Total de custos por produto em barras horizontais |
| Organization Overview | Table | Resumo por org: Total Spend, Credits, Net Cost, Active Clusters, Active Envs |
| Environment Health | Table | Custos por ambiente com breakdown: Kafka, Connectors, Flink, Schema Registry |
| Cost Optimization Insights | Table | **Análise avançada com CTE**: identifica clusters inativos, com alta variância de custos e alto custo |
| Credits & Discounts Tracking | Time Series | Evolução de créditos e descontos ao longo do tempo |
| Daily Audit Table | Table | Tabela diária com data, produto, records, total cost, avg hourly, min/max cost para auditoria |

**Insights que proporciona:**
- Como os custos evoluíram nos últimos 30 dias?
- Há clusters com custos anômalos (alta variância)?
- Quais clusters estão inativos mas gerando custo?
- Como os créditos/descontos foram aplicados ao longo do tempo?
- Dados granulares para auditoria financeira

---

### 6. Confidence Metrics

**Arquivo:** `confidence-metrics.json`
**Público:** Engenheiros de dados, equipe FinOps, qualidade de dados

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Allocation Confidence Distribution | Pie Chart (donut) | Distribuição percentual dos registros por nível de confiança (High, Medium, Low) |
| Cost by Confidence Level | Bar Gauge | Custos associados a cada nível de confiança |
| Data Quality Score | Stat | Percentual de registros com confiança High ou Medium (indicador de qualidade) |
| Total Records | Stat | Contagem total de registros no período |
| Confidence over Time | Time Series (barras empilhadas) | Evolução diária da distribuição de confiança |
| Allocation Method Breakdown | Table | Detalhamento por método de alocação: registros, clusters, custo rastreado, share % |
| Confidence by Environment | Table | Qualidade de confiança por ambiente com breakdown High/Medium/Low e Quality % |

**Insights que proporciona:**
- Qual a qualidade geral da alocação de custos?
- Há ambientes com baixa confiança na alocação?
- Como a qualidade da alocação evolui ao longo do tempo?
- Quais métodos de alocação são mais utilizados?

---

---

### 7. Cost by Principal (Custo por Principal)

**Arquivo:** `cost-by-principal.json`
**Público:** Equipes de segurança, donos de automação, engenheiros de plataforma

**Visões disponíveis:**

| Painel | Tipo | O que mostra |
|---|---|---|
| Cost by Principal Type | Pie Chart | Quebra de custos por tipo (Service Account vs Usuário) |
| Top 10 Principals | Bar Gauge | Principais com maiores gastos (Service Accounts ou Usuários) |
| Daily Cost Trend | Time Series | Evolução diária de custo por principal |
| Principal Cost Detail | Table | Lista detalhada com Nome, Email, Custo Total e clusters ativos |

**Insights que proporciona:**
- Qual Service Account está gerando mais custo?
- Existem usuários individuais gerando custos inesperados?
- Qual automação (sa-*) está com tendência de alta no custo?

---

## Comandos Úteis

### Makefile

```bash
make help             # Listar todos os comandos disponíveis
make docker-up        # Subir toda a stack
make docker-down      # Derrubar toda a stack
make docker-logs      # Ver logs em tempo real
make docker-rebuild   # Rebuild e restart
make install          # Instalar dependências (dev local)
make dev              # Rodar servidor local de desenvolvimento
make test             # Rodar testes
make lint             # Verificar código
make format           # Formatar código
make migrate          # Rodar migrações
```

### Docker

```bash
# Ver status dos containers
docker ps --filter "name=billing"

# Reiniciar um container específico
docker restart billing-grafana

# Ver logs de um container
docker logs billing-app --tail 50 -f

# Acessar o PostgreSQL via CLI
docker exec -it billing-postgres psql -U billing_user -d billing_db

# Consultar dados diretamente
docker exec -it billing-postgres psql -U billing_user -d billing_db -c \
  "SELECT product, ROUND(SUM(cost_usd)::numeric, 2) FROM hourly_cost_facts GROUP BY 1 ORDER BY 2 DESC;"
```

---

## Troubleshooting

### Dashboards vazios

1. **Verifique o time range** — o padrão é 30 dias. Se os dados são mais antigos, ajuste o range no canto superior direito do Grafana
2. **Verifique os dados** — rode: `curl http://localhost:8000/api/v1/costs/summary`
3. **Verifique o datasource PostgreSQL** — em Grafana → Configuration → Data Sources → PostgreSQL → Test

### Containers não sobem

```bash
# Verificar logs de erro
docker compose -f docker/docker-compose.yml logs --tail 20

# Rebuild forçado
docker compose -f docker/docker-compose.yml up -d --build --force-recreate
```

### Coleta não funciona

1. Verifique se `CONFLUENT_API_KEY` e `CONFLUENT_API_SECRET` estão corretos em `docker/.env`
2. Teste a conectividade: `curl -u "KEY:SECRET" https://api.confluent.cloud/billing/v1/costs`
3. Verifique os logs do app: `docker logs billing-app --tail 50`

### Grafana perdeu login/dashboards

Se o banco interno do Grafana foi corrompido:

```bash
# Limpar e recriar a DB do Grafana
docker exec billing-grafana sh -c "rm -f /var/lib/grafana/grafana.db"
docker restart billing-grafana
# Login padrão: admin / admin
```
