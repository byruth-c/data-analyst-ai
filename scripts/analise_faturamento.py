
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            COUNT(DISTINCT o.order_id) AS total_pedidos,
            COUNT(DISTINCT CASE
                WHEN o.order_status = 'delivered'
                THEN o.order_id
            END) AS pedidos_entregues,
            ROUND(SUM(
                CASE
                    WHEN p.payment_value ~ '^[0-9]+([.][0-9]+)?$'
                    THEN p.payment_value::numeric
                    ELSE 0
                END
            ), 2) AS valor_pagamentos
        FROM raw_olist_orders o
        LEFT JOIN raw_olist_order_payments p
            ON o.order_id = p.order_id
    """)

    resultado = cursor.fetchone()

print("\n=== INDICADORES GERAIS DO OLIST ===")
print(f"Total de pedidos: {resultado[0]:,}")
print(f"Pedidos entregues: {resultado[1]:,}")
print(f"Valor total de pagamentos: R$ {resultado[2]:,.2f}")
