-- =============================================================================
-- Alertas de reposição — a lista de compras de hoje
-- =============================================================================
-- Pergunta de negócio: "o que eu preciso comprar agora, e quanto?"
--
-- Une dois motivos distintos de alerta que o operador trata do mesmo jeito
-- (ir ao fornecedor), mas que têm causas diferentes:
--   RUPTURA/MINIMO -> acabou ou está acabando
--   VALIDADE       -> tem no estoque, mas vai virar perda em poucos dias
--
-- Sugere quantidade de compra a partir do consumo médio diário observado nos
-- últimos 30 dias, não de um chute fixo.
--
-- Parâmetros: tenant_id, dias_validade (janela do alerta de vencimento),
--             dias_cobertura (para quantos dias comprar)
-- =============================================================================

WITH saldo AS (
    SELECT
        p.id,
        p.nome,
        p.unidade_medida,
        p.estoque_minimo,
        COALESCE((
            SELECT SUM(
                CASE
                    WHEN m.tipo IN ('entrada', 'estorno')           THEN  m.quantidade
                    WHEN m.tipo = 'abertura'                         THEN -m.quantidade
                    WHEN m.tipo = 'perda'
                         AND m.estoque_afetado = 'fechado'           THEN -m.quantidade
                    WHEN m.tipo = 'ajuste' AND m.direcao = 'entrada' THEN  m.quantidade
                    WHEN m.tipo = 'ajuste'                           THEN -m.quantidade
                    ELSE 0
                END)
            FROM stock_movements m
            WHERE m.product_id = p.id AND m.tipo <> 'consumo'
        ), 0)
        + COALESCE((
            SELECT SUM(l.quantidade_atual)
            FROM stock_lots l
            WHERE l.product_id = p.id
              AND l.status = 'open'
              AND l.quantidade_atual > 1e-9
              AND (l.validade IS NULL OR l.validade >= DATE('now', 'localtime'))
        ), 0) AS estoque_total
    FROM products p
    WHERE p.tenant_id = :tenant_id
      AND p.ativo = 1
      AND p.tipo_produto <> 'RECEITA'
),

-- Velocidade real de saída: consumo + perda dos últimos 30 dias
consumo_recente AS (
    SELECT
        m.product_id,
        SUM(m.quantidade) / 30.0 AS consumo_dia
    FROM stock_movements m
    WHERE m.tenant_id = :tenant_id
      AND m.tipo IN ('consumo', 'perda')
      AND m.data_movimento >= DATE('now', 'localtime', '-30 days')
    GROUP BY m.product_id
),

alertas_estoque AS (
    SELECT
        s.id                            AS produto_id,
        s.nome                          AS produto,
        s.unidade_medida                AS unidade,
        CASE WHEN s.estoque_total <= 0 THEN 'RUPTURA'
             ELSE 'ABAIXO DO MINIMO' END AS motivo,
        ROUND(s.estoque_total, 3)       AS estoque_atual,
        s.estoque_minimo                AS referencia,
        NULL                            AS dias_restantes,
        ROUND(COALESCE(c.consumo_dia, 0), 3) AS consumo_dia
    FROM saldo s
    LEFT JOIN consumo_recente c ON c.product_id = s.id
    WHERE s.estoque_total < s.estoque_minimo
),

alertas_validade AS (
    SELECT
        l.product_id                    AS produto_id,
        p.nome                          AS produto,
        p.unidade_medida                AS unidade,
        'VENCE EM BREVE'                AS motivo,
        ROUND(SUM(l.quantidade_atual), 3) AS estoque_atual,
        NULL                            AS referencia,
        CAST(JULIANDAY(MIN(l.validade))
             - JULIANDAY(DATE('now', 'localtime')) AS INTEGER) AS dias_restantes,
        NULL                            AS consumo_dia
    FROM stock_lots l
    JOIN products p ON p.id = l.product_id
    WHERE l.tenant_id = :tenant_id
      AND l.status = 'open'
      AND l.quantidade_atual > 1e-9
      AND l.validade IS NOT NULL
      AND l.validade BETWEEN DATE('now', 'localtime')
                         AND DATE('now', 'localtime', '+' || :dias_validade || ' days')
    GROUP BY l.product_id, p.nome, p.unidade_medida
)

SELECT
    produto_id,
    produto,
    unidade,
    motivo,
    estoque_atual,
    referencia,
    dias_restantes,
    consumo_dia,
    -- Quanto comprar: cobrir dias_cobertura dias de consumo observado,
    -- descontando o que já existe. Sem histórico de consumo, cai no mínimo.
    CASE
        WHEN motivo = 'VENCE EM BREVE' THEN NULL
        WHEN COALESCE(consumo_dia, 0) > 0
            THEN ROUND(MAX(consumo_dia * :dias_cobertura - estoque_atual, 0), 2)
        ELSE ROUND(MAX(COALESCE(referencia, 0) - estoque_atual, 0), 2)
    END AS sugestao_compra
FROM (
    SELECT * FROM alertas_estoque
    UNION ALL
    SELECT * FROM alertas_validade
)
ORDER BY
    CASE motivo
        WHEN 'RUPTURA'          THEN 1
        WHEN 'VENCE EM BREVE'   THEN 2
        WHEN 'ABAIXO DO MINIMO' THEN 3
    END,
    COALESCE(dias_restantes, 0),
    produto;
