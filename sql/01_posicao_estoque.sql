-- =============================================================================
-- Posição de estoque por produto
-- =============================================================================
-- Pergunta de negócio: "quanto eu tenho de cada item agora, e quem está
-- abaixo do mínimo que eu mesmo defini?"
--
-- O estoque nunca é armazenado como coluna — é derivado de duas fontes:
--   fechado : soma com sinal do ledger imutável (stock_movements)
--   aberto  : saldo dos lotes em uso e dentro da validade (stock_lots)
--
-- A regra de sinal do ledger é a mesma implementada em
-- app/services/stock_service.py:get_estoque_fechado. Duplicar a regra aqui é
-- intencional: esta query é o contrato de leitura analítica, independente da
-- aplicação — o Power BI e qualquer cliente SQL leem daqui, sem subir Python.
--
-- Parâmetro: tenant_id
-- =============================================================================

WITH fechado AS (
    SELECT
        m.product_id,
        SUM(
            CASE
                -- Compra e estorno entram no estoque lacrado
                WHEN m.tipo IN ('entrada', 'estorno')            THEN  m.quantidade
                -- Abrir uma embalagem tira do lacrado e cria um lote
                WHEN m.tipo = 'abertura'                          THEN -m.quantidade
                -- Perda só desconta do lacrado quando foi o lacrado que se perdeu
                WHEN m.tipo = 'perda'
                     AND m.estoque_afetado = 'fechado'            THEN -m.quantidade
                -- Correção de contagem: o sinal vem da direção
                WHEN m.tipo = 'ajuste' AND m.direcao = 'entrada'  THEN  m.quantidade
                WHEN m.tipo = 'ajuste'                            THEN -m.quantidade
                ELSE 0
            END
        ) AS qtd_fechado
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.tipo <> 'consumo'   -- consumo sai do aberto, nunca do lacrado
    GROUP BY m.product_id
),

aberto AS (
    SELECT
        l.product_id,
        SUM(l.quantidade_atual) AS qtd_aberto,
        COUNT(*)                AS lotes_em_uso,
        MIN(l.validade)         AS validade_mais_proxima
    FROM stock_lots l
    WHERE l.tenant_id = :tenant_id
      AND l.status = 'open'
      AND l.quantidade_atual > 1e-9
      -- Lote vencido some do FEFO, logo não conta como estoque disponível
      AND (l.validade IS NULL OR l.validade >= DATE('now', 'localtime'))
    GROUP BY l.product_id
)

SELECT
    p.id                                        AS produto_id,
    p.nome                                      AS produto,
    p.tipo_produto,
    p.unidade_medida                            AS unidade,
    ROUND(COALESCE(f.qtd_fechado, 0), 3)        AS estoque_fechado,
    ROUND(COALESCE(a.qtd_aberto, 0), 3)         AS estoque_aberto,
    ROUND(COALESCE(f.qtd_fechado, 0)
        + COALESCE(a.qtd_aberto, 0), 3)         AS estoque_total,
    p.estoque_minimo,
    COALESCE(a.lotes_em_uso, 0)                 AS lotes_em_uso,
    a.validade_mais_proxima,

    -- Cobertura: quantos "mínimos" cabem no que eu tenho. < 1.0 = ruptura.
    CASE
        WHEN p.estoque_minimo > 0
        THEN ROUND((COALESCE(f.qtd_fechado, 0) + COALESCE(a.qtd_aberto, 0))
                   / p.estoque_minimo, 2)
    END                                         AS indice_cobertura,

    CASE
        WHEN COALESCE(f.qtd_fechado, 0) + COALESCE(a.qtd_aberto, 0) <= 0
            THEN 'RUPTURA'
        WHEN COALESCE(f.qtd_fechado, 0) + COALESCE(a.qtd_aberto, 0) < p.estoque_minimo
            THEN 'ABAIXO DO MINIMO'
        WHEN COALESCE(f.qtd_fechado, 0) + COALESCE(a.qtd_aberto, 0) < p.estoque_minimo * 1.5
            THEN 'ATENCAO'
        ELSE 'OK'
    END                                         AS status_estoque

FROM products p
LEFT JOIN fechado f ON f.product_id = p.id
LEFT JOIN aberto  a ON a.product_id = p.id
WHERE p.tenant_id = :tenant_id
  AND p.ativo = 1
  -- Receita não é estocada: seu "estoque" são os ingredientes da ficha técnica
  AND p.tipo_produto <> 'RECEITA'
ORDER BY
    CASE status_estoque
        WHEN 'RUPTURA'          THEN 1
        WHEN 'ABAIXO DO MINIMO' THEN 2
        WHEN 'ATENCAO'          THEN 3
        ELSE 4
    END,
    indice_cobertura;
