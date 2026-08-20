-- =============================================================================
-- Perdas: quanto, de quê e por quê
-- =============================================================================
-- Pergunta de negócio: "quanto dinheiro eu jogo fora por mês, e a causa é
-- compra demais (vencimento) ou operação (quebra no manuseio)?"
--
-- A distinção muda a ação: vencimento se resolve comprando menos e com mais
-- frequência; quebra se resolve com treinamento e processo. Sem separar as
-- causas, o dono só sabe que "some produto".
--
-- Valoriza a perda pelo custo médio de compra do insumo — perda em unidade
-- não convence ninguém; perda em reais, sim.
--
-- Parâmetros: tenant_id, data_inicio, data_fim
-- =============================================================================

WITH custo_insumo AS (
    SELECT
        product_id,
        SUM(preco_total) / NULLIF(SUM(quantidade), 0) AS custo_unitario
    FROM stock_movements
    WHERE tenant_id = :tenant_id
      AND tipo = 'entrada'
      AND preco_total IS NOT NULL
      AND quantidade > 0
    GROUP BY product_id
),

perdas AS (
    SELECT
        STRFTIME('%Y-%m', m.data_movimento) AS ano_mes,
        p.nome                              AS produto,
        p.tipo_produto,
        m.estoque_afetado,
        -- Normaliza o texto livre do motivo em categorias acionáveis
        CASE
            WHEN LOWER(m.motivo) LIKE '%vencim%'
              OR LOWER(m.motivo) LIKE '%validade%'   THEN 'VENCIMENTO'
            WHEN LOWER(m.motivo) LIKE '%quebra%'
              OR LOWER(m.motivo) LIKE '%dano%'
              OR LOWER(m.motivo) LIKE '%amassad%'    THEN 'QUEBRA/MANUSEIO'
            WHEN LOWER(m.motivo) LIKE '%contamin%'
              OR LOWER(m.motivo) LIKE '%queda%'      THEN 'CONTAMINACAO'
            WHEN LOWER(m.motivo) LIKE '%fornecedor%' THEN 'FALHA DE REPOSICAO'
            ELSE 'OUTROS'
        END                                 AS causa,
        m.quantidade,
        m.quantidade * COALESCE(c.custo_unitario, 0) AS valor_perdido
    FROM stock_movements m
    JOIN products p           ON p.id = m.product_id
    LEFT JOIN custo_insumo c  ON c.product_id = m.product_id
    WHERE m.tenant_id = :tenant_id
      AND m.tipo = 'perda'
      AND m.data_movimento BETWEEN :data_inicio AND :data_fim
),

agregado AS (
    SELECT
        ano_mes,
        causa,
        produto,
        tipo_produto,
        COUNT(*)              AS ocorrencias,
        SUM(quantidade)       AS qtd_perdida,
        SUM(valor_perdido)    AS valor_perdido
    FROM perdas
    GROUP BY ano_mes, causa, produto, tipo_produto
)

SELECT
    ano_mes,
    causa,
    produto,
    tipo_produto,
    ocorrencias,
    ROUND(qtd_perdida, 3)                        AS qtd_perdida,
    ROUND(valor_perdido, 2)                      AS valor_perdido,

    -- Peso desta linha dentro do mês: onde o dinheiro do mês foi embora
    ROUND(100.0 * valor_perdido
          / NULLIF(SUM(valor_perdido) OVER (PARTITION BY ano_mes), 0), 1)
                                                 AS perc_perda_do_mes,

    ROUND(SUM(valor_perdido) OVER (PARTITION BY ano_mes), 2)
                                                 AS total_perdido_mes,

    -- Maior ofensor de cada mês fica marcado com 1
    RANK() OVER (PARTITION BY ano_mes ORDER BY valor_perdido DESC)
                                                 AS rank_no_mes

FROM agregado
ORDER BY ano_mes DESC, valor_perdido DESC;
