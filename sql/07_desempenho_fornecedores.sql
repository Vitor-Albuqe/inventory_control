-- =============================================================================
-- Desempenho de fornecedores
-- =============================================================================
-- Pergunta de negócio: "estou comprando do fornecedor certo? Alguém está
-- cobrando mais caro pelo mesmo insumo, ou entregando mais devagar?"
--
-- Para cada par (insumo, fornecedor), compara o preço praticado contra o
-- melhor preço encontrado para aquele insumo no período. A comparação é feita
-- com window function particionada por produto — cada fornecedor é medido
-- contra os concorrentes do mesmo item, não contra a média geral da loja.
--
-- Também estima o custo de oportunidade: quanto teria sido economizado
-- comprando sempre do fornecedor mais barato daquele insumo.
--
-- Parâmetros: tenant_id, data_inicio, data_fim
-- =============================================================================

WITH compras AS (
    SELECT
        m.product_id,
        p.nome                              AS produto,
        p.unidade_medida                    AS unidade,
        m.fornecedor,
        COUNT(*)                            AS num_compras,
        SUM(m.quantidade)                   AS qtd_comprada,
        SUM(m.preco_total)                  AS valor_gasto,
        SUM(m.preco_total) / NULLIF(SUM(m.quantidade), 0) AS preco_unit_medio,
        MIN(m.preco_unitario)               AS preco_unit_min,
        MAX(m.preco_unitario)               AS preco_unit_max,
        AVG(m.tempo_entrega)                AS lead_time_medio,
        MAX(m.data_movimento)               AS ultima_compra
    FROM stock_movements m
    JOIN products p ON p.id = m.product_id
    WHERE m.tenant_id = :tenant_id
      AND m.tipo = 'entrada'
      AND m.fornecedor IS NOT NULL
      AND m.preco_total IS NOT NULL
      AND m.data_movimento BETWEEN :data_inicio AND :data_fim
    GROUP BY m.product_id, p.nome, p.unidade_medida, m.fornecedor
),

comparado AS (
    SELECT
        *,
        -- Melhor preço para ESTE insumo entre todos os fornecedores dele
        MIN(preco_unit_medio) OVER (PARTITION BY product_id) AS melhor_preco,
        COUNT(*)              OVER (PARTITION BY product_id) AS num_fornecedores,
        RANK() OVER (PARTITION BY product_id
                     ORDER BY preco_unit_medio)              AS rank_preco
    FROM compras
)

SELECT
    produto,
    unidade,
    fornecedor,
    num_fornecedores,
    rank_preco,
    num_compras,
    ROUND(qtd_comprada, 2)                       AS qtd_comprada,
    ROUND(valor_gasto, 2)                        AS valor_gasto,
    ROUND(preco_unit_medio, 3)                   AS preco_unit_medio,
    ROUND(preco_unit_min, 3)                     AS preco_unit_min,
    ROUND(preco_unit_max, 3)                     AS preco_unit_max,

    -- Volatilidade do preço: fornecedor com faixa larga é imprevisível
    -- para orçamento, mesmo com média baixa.
    ROUND(100.0 * (preco_unit_max - preco_unit_min)
          / NULLIF(preco_unit_min, 0), 1)        AS variacao_preco_pct,

    ROUND(100.0 * (preco_unit_medio - melhor_preco)
          / NULLIF(melhor_preco, 0), 1)          AS acima_do_melhor_pct,

    -- Custo de oportunidade: o que foi pago a mais em relação ao melhor preço
    ROUND((preco_unit_medio - melhor_preco) * qtd_comprada, 2)
                                                 AS economia_potencial,

    ROUND(lead_time_medio, 1)                    AS lead_time_medio_dias,
    ultima_compra,

    CASE
        WHEN num_fornecedores = 1                THEN 'FORNECEDOR UNICO'
        WHEN rank_preco = 1                      THEN 'MELHOR PRECO'
        WHEN 100.0 * (preco_unit_medio - melhor_preco)
             / NULLIF(melhor_preco, 0) > 15      THEN 'REVISAR CONTRATO'
        ELSE 'COMPETITIVO'
    END                                          AS avaliacao

FROM comparado
ORDER BY economia_potencial DESC, produto, rank_preco;
