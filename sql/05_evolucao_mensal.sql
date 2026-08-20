-- =============================================================================
-- Evolução mensal: consumo x receita x perdas
-- =============================================================================
-- Pergunta de negócio: "o consumo de insumo está subindo junto com a receita,
-- ou estou desperdiçando mais para vender o mesmo?"
--
-- É o cruzamento que separa crescimento saudável de descontrole operacional:
-- consumo subindo mais rápido que a receita significa perda, desperdício ou
-- porcionamento errado — não mais vendas.
--
-- Usa LAG() para variação mês a mês e uma média móvel de 3 meses para
-- suavizar sazonalidade.
--
-- Parâmetro: tenant_id
-- =============================================================================

WITH calendario AS (
    -- Espinha dorsal de meses: garante linha mesmo em mês sem venda
    -- (ex.: o mês da reforma), em vez de "sumir" do gráfico.
    SELECT DISTINCT STRFTIME('%Y-%m', data_venda) AS ano_mes
    FROM sales WHERE tenant_id = :tenant_id
    UNION
    SELECT DISTINCT STRFTIME('%Y-%m', data_movimento)
    FROM stock_movements WHERE tenant_id = :tenant_id
    UNION
    SELECT DISTINCT STRFTIME('%Y-%m', data)
    FROM expenses WHERE tenant_id = :tenant_id AND is_deleted = 0
),

vendas AS (
    SELECT
        STRFTIME('%Y-%m', data_venda) AS ano_mes,
        COUNT(*)                      AS itens_vendidos,
        SUM(valor_total)              AS receita,
        COUNT(DISTINCT data_venda)    AS dias_operados
    FROM sales
    WHERE tenant_id = :tenant_id
    GROUP BY 1
),

movimentacao AS (
    SELECT
        STRFTIME('%Y-%m', data_movimento) AS ano_mes,
        SUM(CASE WHEN tipo = 'consumo' THEN quantidade ELSE 0 END)  AS qtd_consumida,
        SUM(CASE WHEN tipo = 'perda'   THEN quantidade ELSE 0 END)  AS qtd_perdida,
        SUM(CASE WHEN tipo = 'entrada' THEN preco_total ELSE 0 END) AS investido_compras
    FROM stock_movements
    WHERE tenant_id = :tenant_id
    GROUP BY 1
),

gastos AS (
    SELECT
        STRFTIME('%Y-%m', data) AS ano_mes,
        SUM(valor)              AS gastos_operacionais
    FROM expenses
    WHERE tenant_id = :tenant_id AND is_deleted = 0
    GROUP BY 1
),

base AS (
    SELECT
        c.ano_mes,
        COALESCE(v.receita, 0)             AS receita,
        COALESCE(v.itens_vendidos, 0)      AS itens_vendidos,
        COALESCE(v.dias_operados, 0)       AS dias_operados,
        COALESCE(m.qtd_consumida, 0)       AS qtd_consumida,
        COALESCE(m.qtd_perdida, 0)         AS qtd_perdida,
        COALESCE(m.investido_compras, 0)   AS investido_compras,
        COALESCE(g.gastos_operacionais, 0) AS gastos_operacionais
    FROM calendario c
    LEFT JOIN vendas       v ON v.ano_mes = c.ano_mes
    LEFT JOIN movimentacao m ON m.ano_mes = c.ano_mes
    LEFT JOIN gastos       g ON g.ano_mes = c.ano_mes
)

SELECT
    ano_mes,
    dias_operados,
    itens_vendidos,
    ROUND(receita, 2)                                            AS receita,
    ROUND(receita / NULLIF(dias_operados, 0), 2)                 AS receita_media_dia,
    ROUND(qtd_consumida, 2)                                      AS qtd_consumida,
    ROUND(qtd_perdida, 2)                                        AS qtd_perdida,
    ROUND(investido_compras, 2)                                  AS investido_compras,
    ROUND(gastos_operacionais, 2)                                AS gastos_operacionais,
    ROUND(receita - investido_compras - gastos_operacionais, 2)  AS resultado,

    -- Variação mês a mês (LAG = valor da linha anterior na ordem cronológica)
    ROUND(100.0 * (receita - LAG(receita) OVER (ORDER BY ano_mes))
          / NULLIF(LAG(receita) OVER (ORDER BY ano_mes), 0), 1)  AS var_receita_pct,
    ROUND(100.0 * (qtd_consumida - LAG(qtd_consumida) OVER (ORDER BY ano_mes))
          / NULLIF(LAG(qtd_consumida) OVER (ORDER BY ano_mes), 0), 1)
                                                                 AS var_consumo_pct,

    -- Média móvel de 3 meses: tendência sem o ruído da sazonalidade
    ROUND(AVG(receita) OVER (ORDER BY ano_mes
                             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)
                                                                 AS receita_mm3,

    -- O KPI que importa: quanto de insumo é gasto por real faturado.
    -- Subindo mês a mês = desperdício ou porcionamento fora de controle.
    ROUND(qtd_consumida / NULLIF(receita, 0), 4)                 AS consumo_por_real

FROM base
ORDER BY ano_mes;
