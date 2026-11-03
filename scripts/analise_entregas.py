
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        WITH pedidos AS (
            SELECT
                order_id,
                NULLIF(
                    TRIM(order_delivered_customer_date), ''
                ) AS data_entrega_texto,
                NULLIF(
                    TRIM(order_estimated_delivery_date), ''
                ) AS data_prevista_texto
            FROM raw_olist_orders
            WHERE order_status = 'delivered'
        ),
        datas_validas AS (
            SELECT
                order_id,
                data_entrega_texto::date AS data_entrega,
                data_prevista_texto::date AS data_prevista
            FROM pedidos
            WHERE data_entrega_texto IS NOT NULL
              AND data_prevista_texto IS NOT NULL
        )
        SELECT
            COUNT(*) AS pedidos_analisados,
            COUNT(*) FILTER (
                WHERE data_entrega <= data_prevista
            ) AS entregues_no_prazo,
            COUNT(*) FILTER (
                WHERE data_entrega > data_prevista
            ) AS entregues_atrasados,
            ROUND(
                AVG(data_entrega - data_prevista),
                2
            ) AS media_diferenca_dias
        FROM datas_validas
    """)

    resultado = cursor.fetchone()

print("\n=== ANÁLISE DE ENTREGAS ===")
print(f"Pedidos analisados: {resultado[0]:,}")
print(f"Entregues no prazo: {resultado[1]:,}")
print(f"Entregues com atraso: {resultado[2]:,}")
print(f"Média de diferença: {resultado[3]} dias")
