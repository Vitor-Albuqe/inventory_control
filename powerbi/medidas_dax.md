# Medidas DAX

Cole cada bloco como uma **Nova Medida** (botão direito na tabela indicada → *Nova
medida*), exatamente como está — o `//` é comentário do DAX, pode deixar.

---

## Na tabela `dim_produtos`

```dax
Produtos Cadastrados = COUNTROWS(dim_produtos)
```

---

## Na tabela `fato_estoque` (snapshot de estoque)

```dax
Estoque Total Atual = SUM(fato_estoque[estoque_total])
```

```dax
Produtos Abaixo do Mínimo =
CALCULATE(
    COUNTROWS(fato_estoque),
    fato_estoque[abaixo_minimo] = TRUE
)
```

```dax
% Produtos Abaixo do Mínimo =
DIVIDE([Produtos Abaixo do Mínimo], [Produtos Cadastrados])
```

```dax
// Texto pronto pra usar num rótulo de card ou num tooltip.
Status do Estoque =
IF(
    SELECTEDVALUE(fato_estoque[abaixo_minimo]) = TRUE,
    "🔴 Repor",
    "🟢 OK"
)
```

---

## Na tabela `fato_movimentacoes`

```dax
// quantidade_efetiva já vem com sinal (positivo = entrou, negativo = saiu) —
// direto de StockMovement.get_quantidade_efetiva() no back-end.
Movimentação Líquida = SUM(fato_movimentacoes[quantidade_efetiva])
```

```dax
Qtd Consumida =
CALCULATE(
    SUM(fato_movimentacoes[quantidade]),
    fato_movimentacoes[tipo] = "consumo"
)
```

```dax
Qtd Comprada =
CALCULATE(
    SUM(fato_movimentacoes[quantidade]),
    fato_movimentacoes[tipo] = "entrada"
)
```

```dax
Valor Investido em Compras =
CALCULATE(
    SUM(fato_movimentacoes[preco_total]),
    fato_movimentacoes[tipo] = "entrada"
)
```

```dax
Qtd Perdida (Perda/Vencimento) =
CALCULATE(
    SUM(fato_movimentacoes[quantidade]),
    fato_movimentacoes[tipo] = "perda"
)
```

```dax
// GIRO DE ESTOQUE — versão simplificada para portfólio: quanto foi consumido
// no período dividido pelo estoque médio. fato_estoque tem um snapshot por
// produto por DIA reconstruído do ledger (~180 dias), então essa média já é
// real, não um valor único — ver observação no README.md do Power BI.
// Quanto maior, mais rápido o produto "roda" no estoque.
Giro de Estoque =
DIVIDE(
    [Qtd Consumida],
    AVERAGE(fato_estoque[estoque_total])
)
```

---

## Na tabela `fato_vendas`

```dax
Receita Total = SUM(fato_vendas[valor_total])
```

```dax
Quantidade Vendida = SUM(fato_vendas[quantidade])
```

```dax
Ticket Médio = DIVIDE([Receita Total], DISTINCTCOUNT(fato_vendas[venda_id]))
```

```dax
// Mês a mês, usa a coluna AnoMes de dim_calendario no eixo do gráfico.
Receita Mês Anterior = CALCULATE([Receita Total], DATEADD(dim_calendario[Data], -1, MONTH))
```

```dax
Variação Receita vs. Mês Anterior =
DIVIDE([Receita Total] - [Receita Mês Anterior], [Receita Mês Anterior])
```

---

## Na tabela `fato_gastos`

```dax
Gastos Totais = SUM(fato_gastos[valor])
```

```dax
Gastos Fixos = CALCULATE(SUM(fato_gastos[valor]), fato_gastos[categoria] = "fixo")
```

```dax
Gastos Variáveis = CALCULATE(SUM(fato_gastos[valor]), fato_gastos[categoria] = "variavel")
```

---

## Medida combinada (crie numa tabela nova, "Medidas", ou em `fato_vendas`)

```dax
Lucro Estimado = [Receita Total] - [Valor Investido em Compras] - [Gastos Totais]
```

```dax
Margem de Lucro % = DIVIDE([Lucro Estimado], [Receita Total])
```
