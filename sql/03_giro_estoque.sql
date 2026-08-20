-- =============================================================================
-- Giro de estoque e dias de cobertura
-- =============================================================================
-- Pergunta de negócio: "que produtos giram e quais estão parados travando
-- capital de giro na prateleira?"
--
-- Giro = quantidade que saiu no período / estoque médio do período.
-- Giro alto  -> item de alto movimento; o risco é a ruptura.
-- Giro baixo -> dinheiro parado; o risco é a perda por validade.
--
-- O estoque médio é reconstruído do ledger: para cada movimento, o saldo
-- acumulado até aquele ponto (window function), depois a média ponderada
-- não é necessária porque o ledger da cafeteria tem granularidade diária.
--
-- Parâmetros: tenant_id, data_inicio, data_fim
-- =============================================================================

WITH movimentos_com_sinal AS (
    SELECT
        m.product_id,
        m.data_movimento,
        m.id,
        CASE
            WHEN m.tipo IN ('entrada', 'estorno')            THEN  m.quantidade
            WHEN m.tipo IN ('consumo', 'perda')              THEN -m.quantidade
            WHEN m.tipo = 'ajuste' AND m.direcao = 'entrada' THEN  m.quantidade
            WHEN m.tipo = 'ajuste'                           THEN -m.quantidade
            -- 'abertura' apenas move lacrado -> aberto: não altera o total
            ELSE 0
        END AS delta
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.data_movimento <= :data_fim
),

-- Saldo acumulado do produto após cada movimento (soma corrente no ledger)
saldo_corrente AS (
    SELECT
        product_id,
        data_movimento,
        SUM(delta) OVER (
            PARTITION BY product_id
            ORDER BY data_movimento, id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS saldo
    FROM movimentos_com_sinal
),

estoque_medio AS (
    SELECT
        product_id,
        AVG(saldo) AS saldo_medio,
        MIN(saldo) AS saldo_minimo,
        MAX(saldo) AS saldo_maximo
    FROM saldo_corrente
    WHERE data_movimento BETWEEN :data_inicio AND :data_fim
    GROUP BY product_id
),

saidas AS (
    SELECT
        m.product_id,
        SUM(CASE WHEN m.tipo = 'consumo' THEN m.quantidade ELSE 0 END) AS qtd_consumida,
        SUM(CASE WHEN m.tipo = 'perda'   THEN m.quantidade ELSE 0 END) AS qtd_perdida,
        SUM(m.quantidade)                                              AS qtd_saida_total,
        COUNT(DISTINCT m.data_movimento)                               AS dias_com_saida
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.tipo IN ('consumo', 'perda')
      AND m.data_movimento BETWEEN :data_inicio AND :data_fim
    GROUP BY m.product_id
),

-- Preço médio de compra no período, para converter giro em dinheiro parado
custo AS (
    SELECT
        m.product_id,
        SUM(m.preco_total) / NULLIF(SUM(m.quantidade), 0) AS custo_unitario_medio
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.tipo = 'entrada'
      AND m.preco_total IS NOT NULL
      AND m.data_movimento BETWEEN :data_inicio AND :data_fim
    GROUP BY m.product_id
)

SELECT
    p.nome                                          AS produto,
    p.tipo_produto,
    p.unidade_medida                                AS unidade,
    ROUND(COALESCE(s.qtd_saida_total, 0), 3)        AS qtd_saida,
    ROUND(COALESCE(s.qtd_consumida, 0), 3)          AS qtd_consumida,
    ROUND(COALESCE(s.qtd_perdida, 0), 3)            AS qtd_perdida,
    ROUND(COALESCE(e.saldo_medio, 0), 3)            AS estoque_medio,

    -- Giro: quantas vezes o estoque médio "virou" no período
    ROUND(COALESCE(s.qtd_saida_total, 0)
          / NULLIF(e.saldo_medio, 0), 2)            AS giro,

    -- Dias de cobertura: com o estoque médio, quantos dias eu aguento
    ROUND(e.saldo_medio
          / NULLIF(s.qtd_saida_total / NULLIF(
                JULIANDAY(:data_fim) - JULIANDAY(:data_inicio), 0), 0), 1)
                                                    AS dias_cobertura,

    -- % do que saiu que virou lixo em vez de virar venda
    ROUND(100.0 * COALESCE(s.qtd_perdida, 0)
          / NULLIF(s.qtd_saida_total, 0), 2)        AS perc_perda,

    ROUND(COALESCE(c.custo_unitario_medio, 0), 2)   AS custo_unitario_medio,
    ROUND(COALESCE(e.saldo_medio, 0)
          * COALESCE(c.custo_unitario_medio, 0), 2) AS capital_parado_medio,

    CASE
        WHEN COALESCE(s.qtd_saida_total, 0) = 0                     THEN 'PARADO'
        WHEN COALESCE(s.qtd_saida_total, 0)
             / NULLIF(e.saldo_medio, 0) < 1                          THEN 'GIRO BAIXO'
        WHEN COALESCE(s.qtd_saida_total, 0)
             / NULLIF(e.saldo_medio, 0) < 5                          THEN 'GIRO MEDIO'
        ELSE 'GIRO ALTO'
    END                                             AS classificacao_giro

FROM products p
LEFT JOIN estoque_medio e ON e.product_id = p.id
LEFT JOIN saidas        s ON s.product_id = p.id
LEFT JOIN custo         c ON c.product_id = p.id
WHERE p.tenant_id = :tenant_id
  AND p.ativo = 1
  AND p.tipo_produto <> 'RECEITA'
ORDER BY giro DESC NULLS LAST;
