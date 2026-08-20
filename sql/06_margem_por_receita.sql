-- =============================================================================
-- Margem por item do cardápio (ficha técnica x preço de venda)
-- =============================================================================
-- Pergunta de negócio: "qual item me dá dinheiro de verdade? O mais vendido é
-- o mais lucrativo?"
--
-- Custo de uma receita = soma de (quantidade do ingrediente na ficha técnica x
-- custo unitário médio de compra desse ingrediente). O custo médio vem do
-- ledger de entradas — preço real pago, não tabela de preço.
--
-- Junta a ficha técnica (recipe_items, self-join em products: uma receita e
-- seus ingredientes moram na mesma tabela) com a receita realizada em vendas.
--
-- Parâmetros: tenant_id, data_inicio, data_fim
-- =============================================================================

WITH custo_insumo AS (
    -- Custo unitário médio ponderado de cada insumo, a partir das compras
    SELECT
        m.product_id,
        SUM(m.preco_total) / NULLIF(SUM(m.quantidade), 0) AS custo_unitario
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.tipo = 'entrada'
      AND m.preco_total IS NOT NULL
      AND m.quantidade > 0
    GROUP BY m.product_id
),

custo_ficha_tecnica AS (
    -- Uma linha por receita: soma do custo de todos os ingredientes
    SELECT
        ri.recipe_id                                    AS produto_id,
        COUNT(*)                                        AS num_ingredientes,
        SUM(ri.quantity * COALESCE(ci.custo_unitario, 0)) AS custo_unitario,
        -- Ingrediente sem histórico de compra deixa o custo subestimado:
        -- sinalizar é mais honesto que esconder.
        SUM(CASE WHEN ci.custo_unitario IS NULL THEN 1 ELSE 0 END) AS ingredientes_sem_custo
    FROM recipe_items ri
    JOIN products ing        ON ing.id = ri.ingredient_id   -- self-join: ingrediente
    LEFT JOIN custo_insumo ci ON ci.product_id = ri.ingredient_id
    WHERE ri.tenant_id = :tenant_id
    GROUP BY ri.recipe_id
),

-- Produto final revendido não tem ficha técnica: o custo é a própria compra
custo_unificado AS (
    SELECT produto_id, custo_unitario, num_ingredientes, ingredientes_sem_custo
    FROM custo_ficha_tecnica
    UNION ALL
    SELECT
        p.id,
        ci.custo_unitario,
        0,
        0
    FROM products p
    JOIN custo_insumo ci ON ci.product_id = p.id
    WHERE p.tenant_id = :tenant_id
      AND p.tipo_produto = 'PRODUTO_FINAL'
),

vendido AS (
    SELECT
        s.product_id,
        SUM(s.quantidade)  AS qtd_vendida,
        SUM(s.valor_total) AS receita,
        AVG(s.valor_unitario) AS preco_medio_praticado
    FROM sales s
    WHERE s.tenant_id = :tenant_id
      AND s.data_venda BETWEEN :data_inicio AND :data_fim
    GROUP BY s.product_id
)

SELECT
    p.nome                                              AS produto,
    p.tipo_produto,
    cu.num_ingredientes,
    ROUND(COALESCE(v.qtd_vendida, 0), 2)                AS qtd_vendida,
    ROUND(p.preco_venda, 2)                             AS preco_tabela,
    ROUND(v.preco_medio_praticado, 2)                   AS preco_medio_praticado,
    ROUND(cu.custo_unitario, 4)                         AS custo_unitario,

    ROUND(COALESCE(v.preco_medio_praticado, p.preco_venda)
          - cu.custo_unitario, 2)                       AS margem_unitaria,

    ROUND(100.0 * (COALESCE(v.preco_medio_praticado, p.preco_venda) - cu.custo_unitario)
          / NULLIF(COALESCE(v.preco_medio_praticado, p.preco_venda), 0), 1)
                                                        AS margem_pct,

    -- Markup: quantas vezes o preço cobre o custo (referência do setor: 3x+)
    ROUND(COALESCE(v.preco_medio_praticado, p.preco_venda)
          / NULLIF(cu.custo_unitario, 0), 2)            AS markup,

    ROUND(COALESCE(v.receita, 0), 2)                    AS receita_total,
    ROUND(COALESCE(v.qtd_vendida, 0)
          * (COALESCE(v.preco_medio_praticado, p.preco_venda) - cu.custo_unitario), 2)
                                                        AS lucro_bruto_total,

    -- Ranking por lucro TOTAL, não por margem %: um item de margem baixa e
    -- volume alto contribui mais que um item de margem alta que ninguém pede.
    RANK() OVER (
        ORDER BY COALESCE(v.qtd_vendida, 0)
               * (COALESCE(v.preco_medio_praticado, p.preco_venda) - cu.custo_unitario) DESC
    )                                                   AS rank_lucro,

    CASE WHEN cu.ingredientes_sem_custo > 0
         THEN 'custo parcial: ' || cu.ingredientes_sem_custo || ' ingrediente(s) sem compra registrada'
    END                                                 AS ressalva

FROM products p
JOIN custo_unificado cu ON cu.produto_id = p.id
LEFT JOIN vendido    v  ON v.product_id  = p.id
WHERE p.tenant_id = :tenant_id
  AND p.ativo = 1
  AND p.preco_venda IS NOT NULL
ORDER BY lucro_bruto_total DESC;
