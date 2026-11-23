-- ============================================================================
-- VENDAS MENSAIS: quantidade de pedidos e valores comercializados.
-- ============================================================================

SELECT
    strftime('%Y-%m', data_pedido) AS mes,
    COUNT(*) AS qtd_pedidos,
    ROUND(SUM(valor_itens), 2) AS total_vendas_itens,
    ROUND(SUM(valor_total), 2) AS total_vendas_informado
FROM pedidos
GROUP BY strftime('%Y-%m', data_pedido)
ORDER BY mes;


-- ============================================================================
-- VALIDAÇÃO: consistência entre a soma mensal e o total geral de vendas.
-- ============================================================================

WITH vendas_por_mes AS (
    SELECT
        strftime('%Y-%m', data_pedido) AS mes,
        SUM(valor_itens) AS soma_mes
    FROM pedidos
    GROUP BY strftime('%Y-%m', data_pedido)
)
SELECT
    ROUND((SELECT SUM(soma_mes) FROM vendas_por_mes), 2) AS soma_mensal_itens,
    ROUND((SELECT SUM(valor_itens) FROM pedidos), 2) AS soma_geral_itens,
    ROUND(
        ABS(
            (SELECT SUM(soma_mes) FROM vendas_por_mes)
            - (SELECT SUM(valor_itens) FROM pedidos)
        ),
        4
    ) AS diferenca_itens;


-- ============================================================================
-- VENDAS POR ESTADO: distribuição dos pedidos conforme a UF dos clientes.
-- ============================================================================

SELECT
    c.estado,
    COUNT(p.id) AS qtd_pedidos,
    ROUND(SUM(p.valor_itens), 2) AS total_itens
FROM pedidos p
JOIN clientes c
    ON c.id = p.cliente_id
GROUP BY c.estado
ORDER BY qtd_pedidos DESC, c.estado ASC;


-- ============================================================================
-- PEDIDOS DIVERGENTES: diferença superior a R$ 0,01 entre valores.
-- ============================================================================

SELECT
    id AS pedido_id,
    cliente_id,
    data_pedido,
    status,
    valor_total,
    valor_itens,
    ROUND(valor_total - valor_itens, 2) AS diferenca
FROM pedidos
WHERE divergente = 1
ORDER BY ABS(valor_total - valor_itens) DESC, id ASC;