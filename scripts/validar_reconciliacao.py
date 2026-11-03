
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS reconciliacao_pedidos")

    cursor.execute("""
        CREATE TABLE reconciliacao_pedidos AS
        WITH valores_itens AS (
            SELECT
                order_id,
                SUM(price) AS valor_itens,
                SUM(freight_value) AS valor_frete
            FROM stg_olist_order_items
            GROUP BY order_id
        )
        SELECT
            p.order_id,
            o.order_status,
            COALESCE(i.valor_itens, 0) AS valor_itens,
            COALESCE(i.valor_frete, 0) AS valor_frete,
            p.valor_total_pago,
            p.valor_total_pago
                - COALESCE(i.valor_itens, 0)
                - COALESCE(i.valor_frete, 0) AS diferenca
        FROM fato_pagamentos p
        LEFT JOIN valores_itens i
            ON p.order_id = i.order_id
        LEFT JOIN stg_olist_orders o
            ON p.order_id = o.order_id
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (
                WHERE ABS(diferenca) <= 0.01
            ),
            COUNT(*) FILTER (
                WHERE diferenca > 0.01
            ),
            COUNT(*) FILTER (
                WHERE diferenca < -0.01
            ),
            SUM(valor_total_pago),
            SUM(valor_itens + valor_frete),
            SUM(diferenca)
        FROM reconciliacao_pedidos
    """)

    (
        total,
        iguais,
        pagamento_maior,
        pagamento_menor,
        soma_pago,
        soma_itens_frete,
        diferenca_total,
    ) = cursor.fetchone()

print("\n=== RECONCILIAÇÃO FINANCEIRA ===")
print(f"Pedidos analisados: {total:,}")
print(f"Valores iguais: {iguais:,}")
print(f"Pagamento maior: {pagamento_maior:,}")
print(f"Pagamento menor: {pagamento_menor:,}")
print(f"Total pago: R$ {soma_pago:,.2f}")
print(f"Total de itens + frete: R$ {soma_itens_frete:,.2f}")
print(f"Diferença total: R$ {diferenca_total:,.2f}")
print("Tabela criada: reconciliacao_pedidos")
