-- =============================================================================
-- Curva ABC de faturamento
-- =============================================================================
-- Pergunta de negócio: "quais itens do cardápio realmente sustentam a
-- cafeteria, e quais só ocupam espaço no menu?"
--
-- Classificação de Pareto sobre a receita do período:
--   A = itens que somam até 80% do faturamento  (nunca podem faltar)
--   B = de 80% a 95%                            (importantes, não críticos)
--   C = os 5% finais                            (candidatos a sair do menu)
--
-- Demonstra window functions acumuladas: SUM() OVER (ORDER BY ...) para o
-- acumulado e SUM() OVER () para o total geral, sem subquery de agregação.
--
-- Parâmetros: tenant_id, data_inicio, data_fim
-- =============================================================================

WITH receita_por_produto AS (
    SELECT
        -- produto_nome é o snapshot gravado na venda: se o produto for
        -- renomeado ou desativado, o histórico não se perde.
        COALESCE(p.nome, s.produto_nome)  AS produto,
        p.tipo_produto,
        COUNT(*)                          AS num_vendas,
        SUM(s.quantidade)                 AS qtd_vendida,
        SUM(s.valor_total)                AS receita,
        AVG(s.valor_unitario)             AS ticket_medio_item
    FROM sales s
    LEFT JOIN products p ON p.id = s.product_id
    WHERE s.tenant_id = :tenant_id
      AND s.data_venda BETWEEN :data_inicio AND :data_fim
    GROUP BY COALESCE(p.nome, s.produto_nome), p.tipo_produto
),

ranqueado AS (
    SELECT
        produto,
        tipo_produto,
        num_vendas,
        qtd_vendida,
        receita,
        ticket_medio_item,
        ROW_NUMBER() OVER (ORDER BY receita DESC)              AS posicao,
        SUM(receita) OVER ()                                   AS receita_total,
        SUM(receita) OVER (ORDER BY receita DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING
                                    AND CURRENT ROW)           AS receita_acumulada
    FROM receita_por_produto
)

SELECT
    posicao,
    produto,
    tipo_produto,
    num_vendas,
    ROUND(qtd_vendida, 2)                                  AS qtd_vendida,
    ROUND(receita, 2)                                      AS receita,
    ROUND(ticket_medio_item, 2)                            AS ticket_medio_item,
    ROUND(100.0 * receita / receita_total, 2)              AS perc_receita,
    ROUND(100.0 * receita_acumulada / receita_total, 2)    AS perc_acumulado,
    CASE
        WHEN 100.0 * receita_acumulada / receita_total <= 80 THEN 'A'
        WHEN 100.0 * receita_acumulada / receita_total <= 95 THEN 'B'
        ELSE 'C'
    END                                                    AS classe_abc
FROM ranqueado
ORDER BY posicao;
