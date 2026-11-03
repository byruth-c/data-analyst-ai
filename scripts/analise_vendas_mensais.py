
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            DATE_TRUNC(
                'month',
                o.order_delivered_customer_date
            )::date AS mes,
            COUNT(DISTINCT o.order_id) AS pedidos_entregues,
            COUNT(*) AS itens_vendidos,
            ROUND(SUM(i.price)::numeric, 2) AS valor_produtos,
            ROUND(SUM(i.freight_value)::numeric, 2) AS valor_frete,
            ROUND(
                SUM(i.price + i.freight_value)::numeric, 2
            ) AS valor_total
        FROM stg_olist_orders o
        INNER JOIN stg_olist_order_items i
            ON o.order_id = i.order_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """)

    resultados = cursor.fetchall()

print("\n=== VENDAS MENSAIS ===")

for mes, pedidos, itens, produtos, frete, total in resultados:
    print(f"\nMês: {mes}")
    print(f"Pedidos entregues: {pedidos:,}")
    print(f"Itens vendidos: {itens:,}")
    print(f"Valor dos produtos: R$ {produtos:,.2f}")
    print(f"Valor do frete: R$ {frete:,.2f}")
    print(f"Total: R$ {total:,.2f}")
