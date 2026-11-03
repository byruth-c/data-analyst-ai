
from django.db import connection

with connection.cursor() as cursor:
    # Recria apenas a tabela tratada.
    # As tabelas raw_ não são alteradas.
    cursor.execute("DROP TABLE IF EXISTS stg_olist_orders")

    cursor.execute("""
        CREATE TABLE stg_olist_orders AS
        SELECT
            NULLIF(TRIM(order_id), '') AS order_id,
            NULLIF(TRIM(customer_id), '') AS customer_id,
            NULLIF(TRIM(order_status), '') AS order_status,

            NULLIF(
                TRIM(order_purchase_timestamp), ''
            )::timestamp AS order_purchase_timestamp,

            NULLIF(
                TRIM(order_approved_at), ''
            )::timestamp AS order_approved_at,

            NULLIF(
                TRIM(order_delivered_carrier_date), ''
            )::timestamp AS order_delivered_carrier_date,

            NULLIF(
                TRIM(order_delivered_customer_date), ''
            )::timestamp AS order_delivered_customer_date,

            NULLIF(
                TRIM(order_estimated_delivery_date), ''
            )::timestamp AS order_estimated_delivery_date

        FROM raw_olist_orders
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT order_id),
            COUNT(*) FILTER (
                WHERE order_id IS NULL
            ),
            COUNT(*) FILTER (
                WHERE order_status = 'delivered'
                  AND order_delivered_customer_date IS NULL
            )
        FROM stg_olist_orders
    """)

    total, unicos, ids_vazios, entregues_sem_data = (
        cursor.fetchone()
    )

print("\n=== VALIDAÇÃO DA CAMADA STAGING ===")
print(f"Total de registros: {total:,}")
print(f"Pedidos únicos: {unicos:,}")
print(f"IDs vazios: {ids_vazios:,}")
print(f"Entregues sem data: {entregues_sem_data:,}")
print("Tabela criada: stg_olist_orders")
