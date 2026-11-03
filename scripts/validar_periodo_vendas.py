
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            MIN(order_purchase_timestamp) AS primeira_compra,
            MAX(order_purchase_timestamp) AS ultima_compra,
            MIN(order_delivered_customer_date) AS primeira_entrega,
            MAX(order_delivered_customer_date) AS ultima_entrega,
            COUNT(*) FILTER (
                WHERE order_status = 'delivered'
                  AND order_delivered_customer_date IS NOT NULL
            ) AS pedidos_entregues_com_data
        FROM stg_olist_orders
    """)

    resultado = cursor.fetchone()

print("\n=== PERÍODO DOS DADOS ===")
print(f"Primeira compra: {resultado[0]}")
print(f"Última compra: {resultado[1]}")
print(f"Primeira entrega: {resultado[2]}")
print(f"Última entrega: {resultado[3]}")
print(f"Pedidos entregues com data: {resultado[4]:,}")
