# ☕ Cafezinho — Sistema de Controle de Estoque

Sistema de gerenciamento operacional para cafeterias. Controla estoque, compras, vendas, receitas e fluxo financeiro em uma interface web simples e visual.

> **Fase atual:** MVP com Streamlit + SQLite  
> **Próxima fase:** Migração para React + FastAPI

---

## Funcionalidades

| Página | Descrição |
|--------|-----------|
| **Cadastro de Produtos** | Cadastra matérias-primas, consumíveis, produtos finais e receitas com ingredientes e custos |
| **Registro de Compras** | Registra entradas de estoque com rastreamento de fornecedor, prazo e preço histórico |
| **Alertas** | Exibe produtos abaixo do estoque mínimo e lotes próximos ao vencimento |
| **Dashboard Financeiro** | Receita, investimento em estoque, gastos operacionais e lucro estimado com gráficos |
| **Estoque** | Visão em tempo real do estoque fechado e aberto, abertura de lotes e ações rápidas |
| **Vendas (PDV)** | Ponto de Venda com carrinho, consumo automático de estoque via FEFO, histórico filtrado e gráfico de receita diária |

---

## Tecnologias

- **[Python 3.11+](https://python.org)** — linguagem principal
- **[Streamlit](https://streamlit.io)** — interface web
- **[SQLAlchemy 2.0](https://sqlalchemy.org)** — ORM e acesso ao banco
- **[SQLite](https://sqlite.org)** — banco de dados local (sem instalação)
- **[Alembic](https://alembic.sqlalchemy.org)** — migrações de banco de dados
- **[Plotly](https://plotly.com/python)** — gráficos interativos
- **[Pandas](https://pandas.pydata.org)** — manipulação de dados
- **[Babel](https://babel.pocoo.org)** — formatação de moeda em Real brasileiro (R$ 1.234,56)

---

## Arquitetura

O projeto segue uma arquitetura em camadas que facilita a futura migração para React + FastAPI:

```
app/
├── pages/              # Camada de UI (Streamlit) — só chama services
│   ├── 1_Cadastro_de_Produtos.py
│   ├── 2_Registro_de_Compras.py
│   ├── 3_alertas.py
│   ├── 4_dashboard.py
│   ├── 5_Estoque.py
│   └── 6_Vendas.py
│
├── services/           # Camada de negócio — orquestra repositórios e regras
│   ├── application_service.py   # Fachada principal: uma função por caso de uso da UI
│   ├── inventory_service.py     # Regras de estoque, movimentações e FEFO
│   ├── recipe_service.py        # Gerenciamento de receitas e ingredientes
│   ├── cost_service.py          # Cálculo de custo de receitas
│   └── session_scope.py         # Context manager de sessão SQLAlchemy
│
├── repositories/       # Camada de dados — queries SQL via SQLAlchemy
│   ├── product_repository.py
│   ├── finance_repository.py    # Vendas e gastos
│   ├── movement_repository.py
│   └── receita_repository.py
│
├── models/             # Definição das tabelas do banco
│   ├── product.py          # Catálogo de produtos
│   ├── stock_movement.py   # Ledger imutável de movimentações
│   ├── stock_lot.py        # Lotes abertos (rastreamento FEFO)
│   ├── sales.py            # Transações de venda
│   ├── expenses.py         # Gastos operacionais
│   ├── recipes.py          # Ingredientes de receitas
│   ├── tenant.py           # Multi-tenant (preparado para SaaS)
│   └── mixins.py           # TenantMixin, TimestampMixin
│
├── database/           # Configuração do banco
│   ├── connection.py       # Engine e SessionFactory
│   ├── init_db.py          # Criação das tabelas
│   └── seed.py             # Dados iniciais (tenant padrão)
│
└── utils/              # Funções auxiliares
    ├── unit_converter.py   # Conversão g/kg, ml/L
    ├── data_formater.py    # Formatação de datas e cores
    └── ui_formater.py      # Formatação de preços e variações
```

### Por que essa separação?

A regra mais importante desta arquitetura é: **as páginas Streamlit nunca fazem queries SQL diretamente.** Elas só chamam funções de `application_service.py`.

Isso significa que, quando migrarmos para FastAPI, cada função de `application_service.py` vira um endpoint de API. As páginas Streamlit serão substituídas por componentes React que chamam esses endpoints. O núcleo do negócio permanece o mesmo.

---

## Modelo de Estoque

O estoque é calculado, nunca armazenado manualmente. Isso garante rastreabilidade completa e auditoria.

```
Estoque Total = Estoque Fechado + Estoque Aberto

Estoque Fechado (ledger de StockMovement):
  + entradas (compras)
  - aberturas (produto fechado → aberto)
  - perdas em estoque fechado
  ± ajustes manuais
  + estornos

Estoque Aberto (soma dos StockLot ativos):
  Cada lote representa uma embalagem aberta,
  consumida por FEFO (Primeiro a Vencer, Primeiro a Sair)
```

---

## Como rodar localmente

**Pré-requisitos:** Python 3.11+ e pip.

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd controle-de-estoque

# 2. Crie e ative o ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Rode o sistema
streamlit run app/main.py
```

O banco de dados SQLite é criado automaticamente na primeira execução.

---

## Fluxo operacional da cafeteria

```
1. COMPRA
   Fornecedor entrega produto → Registro de Compras
   → StockMovement tipo "entrada"
   → Estoque fechado aumenta

2. PREPARO (para produtos com controle de abertura)
   Embalagem aberta para uso → Página Estoque → "Abrir produto"
   → StockMovement tipo "abertura" + criação de StockLot
   → Estoque fechado diminui, estoque aberto aumenta

3. CONSUMO
   Ingrediente usado no preparo → Página Estoque → "Consumo"
   → StockMovement tipo "consumo" (FEFO automático)
   → Lote do produto aberto diminui

4. VENDA
   Cliente paga pela receita/produto → Página Vendas (PDV)
   → Itens adicionados ao carrinho, total calculado em tempo real
   → "Finalizar Venda" registra cada item como Sale com snapshot do nome e preço
   → Receitas: ingredientes descontados automaticamente via FEFO em transação única
   → Produto Final: lotes abertos descontados via FEFO (aviso se não houver lotes)
   → Falhas de estoque viram avisos — a venda é sempre registrada
   → Receita financeira contabilizada no Dashboard
```

---

## Tipos de produto

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `materia_prima` | Ingrediente comprado a granel | Café em grão, leite, açúcar |
| `consumivel` | Material de uso geral | Copos, guardanapos, embalagens |
| `produto_final` | Produto pronto para venda sem receita | Bolo comprado de fornecedor |
| `receita` | Produto feito com ingredientes cadastrados | Café com leite, suco natural |

---

## Executar os testes

```bash
pytest app/test/ -v
```

---

## Roadmap

### Fase 2 — Melhorias no MVP atual
- [x] PDV com carrinho e consumo automático de estoque por FEFO
- [x] Formatação monetária em Real brasileiro (Babel)
- [x] Validação de dados inválidos na camada de serviço (qtd ≤ 0, preço < 0)
- [x] Proteção contra lotes vencidos no FEFO
- [x] Atomicidade no cadastro de receitas com múltiplos ingredientes
- [ ] Exclusão de vendas (soft delete)
- [ ] Edição de preço de venda diretamente na página de vendas
- [ ] Relatório de margem por produto
- [ ] Filtro por produto no histórico de vendas

### Fase 3 — Migração para React + FastAPI
- [ ] API REST com FastAPI (os `application_service` viram endpoints)
- [ ] Autenticação JWT
- [ ] Interface React com componentes reutilizáveis
- [ ] Deploy em nuvem (Railway, Render ou VPS)
- [ ] Multi-tenant real (isolamento por `tenant_id` nas queries)

---

## Decisões técnicas

**Por que SQLite e não PostgreSQL?**  
Para um MVP local sem servidor, SQLite elimina infraestrutura desnecessária. A migração para PostgreSQL é simples: basta trocar a string de conexão em `database/connection.py`.

**Por que o ledger de movimentações é imutável?**  
Nunca modificamos um `StockMovement` existente. Erros são corrigidos com estornos. Isso garante trilha de auditoria completa e elimina inconsistências entre o que foi registrado e o saldo atual.

**Por que `produto_nome` é salvo no registro de venda?**  
Se um produto for renomeado ou desativado no futuro, o histórico de vendas continua correto. É o mesmo princípio de uma nota fiscal: captura o estado no momento da transação.

**Por que FEFO e não FIFO?**  
Em uma cafeteria, o critério de consumo mais importante é a validade (First Expiration, First Out), não a data de entrada. FEFO minimiza desperdício e perdas. Lotes vencidos são excluídos automaticamente da fila de consumo.

**Por que a venda sempre é registrada mesmo com estoque insuficiente?**  
Em um PDV real, interromper a venda porque o sistema não sabe da validade de um lote seria pior do que o problema. Erros de estoque viram avisos visíveis ao operador, que pode corrigir manualmente — a receita financeira nunca é perdida por um dado de estoque desatualizado.

**Por que `Decimal` e não `float` nos valores de venda?**  
`float` acumula erro de arredondamento em operações repetidas (ex.: `0.1 * 3 != 0.3`). A coluna `valor_total` usa `Numeric(12,2)` no banco. `Decimal(str(valor))` garante que o que entra é exatamente o que o usuário digitou, sem surpresas na casa dos centavos.
