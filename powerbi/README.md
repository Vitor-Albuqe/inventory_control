# Dashboard Power BI — Cafezinho

KPIs de operação de estoque: **estoque mínimo por produto**, **giro de estoque**,
**alertas de reposição** e **evolução de consumo por período**, a partir dos dados
reais gerados pelo sistema.

> **Por que isso é um guia e não um `.pbix` pronto?** Power BI Desktop é um aplicativo
> gráfico do Windows sem interface de linha de comando para autoria de relatórios — não
> tem como um script gerar os visuais sozinho. O que está pronto aqui é tudo o que dá
> trabalho de verdade: os dados exportados em modelo estrela e todas as medidas DAX. Montar
> os visuais no Power BI Desktop leva uns 30–40 minutos seguindo os passos abaixo.

---

## 0. Pré-requisitos

- [Power BI Desktop](https://powerbi.microsoft.com/pt-br/desktop/) (gratuito, só Windows).
- Os dados exportados em `powerbi/dados/*.csv`. Se ainda não gerou (ou quer atualizar com
  dados mais recentes), rode a partir da raiz do projeto:

  ```bash
  python scripts/exportar_powerbi.py
  ```

  Isso lê o `cafeteria_estoque.db` atual e regrava os 6 CSVs em `powerbi/dados/`.

---

## 1. Importar os dados

No Power BI Desktop: **Página Inicial → Obter Dados → Pasta**, aponte para
`powerbi/dados/`, e **Transformar Dados**. No Editor Power Query, selecione os 6
arquivos (`dim_produtos`, `dim_calendario`, `fato_vendas`, `fato_movimentacoes`,
`fato_gastos`, `fato_estoque`) e use **Combinar → Como Nova Consulta** um por vez — ou,
mais simples, importe cada CSV individualmente com **Obter Dados → Texto/CSV**.

Confira os tipos de dado depois de importar (o Power BI costuma acertar sozinho, mas
vale checar):
- `dim_calendario[Data]`, `fato_vendas[data]`, `fato_movimentacoes[data]`,
  `fato_gastos[data]`, `fato_estoque[data]` → **Data**
- `fato_estoque[abaixo_minimo]`, `dim_produtos[ativo]`, `dim_calendario[FimDeSemana]` →
  **Verdadeiro/Falso**
- Colunas de valor (`valor_total`, `preco_total`...) → **Decimal fixo** ou **Número
  decimal**

## 2. Modelagem — relacionamentos (esquema estrela)

Vá em **Modelagem → Gerenciar Relacionamentos** (ou arraste na visão de Modelo) e crie:

```
dim_produtos[produto_id]  1 ──< * fato_vendas[produto_id]
dim_produtos[produto_id]  1 ──< * fato_movimentacoes[produto_id]
dim_produtos[produto_id]  1 ──< * fato_estoque[produto_id]
dim_calendario[Data]      1 ──< * fato_vendas[data]
dim_calendario[Data]      1 ──< * fato_movimentacoes[data]
dim_calendario[Data]      1 ──< * fato_gastos[data]
dim_calendario[Data]      1 ──< * fato_estoque[data]
```

`dim_produtos` e `dim_calendario` são as dimensões (atributos que não mudam a cada
evento: nome do produto, unidade de medida, ano/mês/dia); as quatro tabelas `fato_*`
são os fatos (uma linha por evento que aconteceu numa data — venda, movimentação de
estoque, gasto, **e o saldo de estoque em cada dia do período**). Isso é um
**esquema estrela** clássico: é o que se espera ver num teste técnico ou numa
explicação de portfólio.

`fato_estoque` merece destaque: é uma **periodic snapshot fact table** (termo do livro
*The Data Warehouse Toolkit*, de Kimball) — o padrão certo para "quanto eu tenho agora"
quando esse valor muda o tempo todo. Cada linha é "produto X tinha Y de estoque no dia
Z". Ela cobre **todo o período** simulado (um snapshot por produto por dia, ~3.600
linhas) — o script reconstrói isso reproduzindo (replay) o ledger de movimentações e o
histórico de cada lote até cada data, não só "hoje". Dá pra fazer isso porque o ledger é
imutável e já tem tudo (ver `exportar_fato_estoque` em `scripts/exportar_powerbi.py`);
num sistema com dados reais entrando dia a dia, o normal seria só ir fazendo 1 snapshot
por dia a partir de agora (agendado), sem poder reconstruir o passado.

## 3. Medidas DAX

Abra [`medidas_dax.md`](medidas_dax.md) e cole cada medida na tabela indicada
(botão direito na tabela → **Nova medida**). São ~18 medidas cobrindo os 4 KPIs do
pitch, mais o financeiro (receita/gastos/lucro) que já existe no sistema.

## 4. Montar os visuais

Sugestão de página única "Visão Geral do Estoque", 4 seções:

**Topo — cards de KPI** (visual "Cartão"):
`Produtos Abaixo do Mínimo` · `Giro de Estoque` · `Receita Total` · `Margem de Lucro %`

**Estoque mínimo por produto** (visual "Tabela" ou "Matriz"):
Colunas: `dim_produtos[nome]`, `fato_estoque[estoque_total]`, `dim_produtos[estoque_minimo]`,
`Status do Estoque` (a medida, que vem de `fato_estoque`). Como as duas primeiras colunas
vêm de tabelas diferentes ligadas por relacionamento, isso já mostra na prática que o
relacionamento dim↔fato está funcionando. Em **Formatação Condicional** na coluna
`estoque_total`, regra "Regras" com condição `abaixo_minimo = Verdadeiro → fundo vermelho
claro`. Ordene por `estoque_total` crescente pra chamar atenção pro mais crítico primeiro.

**Alertas de reposição** (visual "Tabela", com filtro/segmentação):
Mesma tabela acima, mas com um filtro de visual `fato_estoque[abaixo_minimo] = Verdadeiro`
— é o "o que preciso comprar hoje" de relance.

**Giro de estoque por produto** (visual "Gráfico de Barras"):
Eixo Y = `dim_produtos[nome]`, Eixo X = medida `Giro de Estoque`. Ordene decrescente —
mostra quais produtos "andam" mais rápido no estoque (café, leite) vs. os parados.

**Evolução de consumo por período** (visual "Gráfico de Linhas"):
Eixo X = `dim_calendario[AnoMes]` (ou a hierarquia `Ano/Mês` do calendário, pra poder
dar drill-down), Eixo Y = medida `Qtd Consumida`, com filtro de visual
`fato_movimentacoes[tipo] = "consumo"`. Adicione uma segunda linha com `Receita Total`
(eixo secundário) pra cruzar consumo com faturamento — bom gancho pra explicar
"consumo subindo mas receita estável = desperdício" numa entrevista.

**Evolução do estoque ao longo do tempo** (visual "Gráfico de Linhas"):
Eixo X = `dim_calendario[Data]` (dia a dia — agora dá, já que `fato_estoque` cobre o
período inteiro), Eixo Y = medida `Estoque Total Atual`, filtrado por produto num
slicer (ou uma linha por categoria com `dim_produtos[tipo_produto]` na legenda). Dá
pra apontar visualmente onde o estoque cruzou a linha do mínimo — bom complemento
visual pra "alertas de reposição".

**Segmentações (slicers) no topo da página:** `dim_calendario[Ano]`/`[NomeMes]` e
`dim_produtos[tipo_produto]`, pra filtrar tudo de uma vez.

## 5. Formatação rápida

- Tema: **Exibir → Temas** → escolha um tema com boa leitura (ex.: "Cidade" ou
  "Executivo"); evita ficar com a paleta padrão.
- Formate os cards de moeda como `R$ #.##0,00` (Formato → Moeda → Real Brasileiro).
- Título da página e dos visuais em português, consistente com o resto do projeto.

## 6. Publicar / exportar pra portfólio

- **Print/GIF**: capture a página cheia (com filtros aplicados mostrando alertas reais)
  pra colocar no README principal e no LinkedIn.
- **Publicar** (se tiver conta Power BI, mesmo grátis): **Página Inicial → Publicar** →
  gera um link compartilhável do relatório online.
- Salve o arquivo como `powerbi/dashboard.pbix` neste repositório (o `.gitignore` do
  projeto não bloqueia `.pbix`, então ele fica versionado junto do resto).

---

## Observações honestas (bom material pra entrevista)

- **Por que estoque não é coluna de `dim_produtos`.** Dimensão é atributo que descreve
  o produto e muda pouco (nome, unidade, o *limite* mínimo configurado). Estoque atual é
  medida — muda a cada compra/venda/consumo. Colocar isso na dimensão faria cada
  exportação *sobrescrever* o valor anterior, sem deixar rastro, e sem jeito de calcular
  "estoque médio" de verdade. Por isso virou `fato_estoque`, uma periodic snapshot fact
  table de verdade — e como o ledger de movimentações é imutável e cobre os 6 meses
  inteiros, o script reconstrói o snapshot de **cada dia** do período, não só de hoje.
- **Giro de estoque agora usa histórico de verdade.** `AVERAGE(fato_estoque[estoque_total])`
  faz média sobre ~180 dias reconstruídos por produto, não um valor único. Isso só foi
  possível reconstruindo o passado a partir do ledger; num sistema real recebendo dados
  novos todo dia (sem histórico de estoque guardado desde o início), o normal seria
  começar a acumular `fato_estoque` dali pra frente (1 snapshot por dia, agendado) — a
  média ficaria mais representativa com o tempo, mas não dá pra reconstruir o que já
  passou se o dado bruto (o ledger) não existisse.
- **Os dados são sintéticos**, gerados por `scripts/gerar_dados_sinteticos.py` (6 meses
  de operação simulada de uma cafeteria: vendas, compras, perdas, sazonalidade). Isso é
  esperado num projeto de portfólio — deixe isso claro na descrição, não apresente como
  dado real de um negócio.
