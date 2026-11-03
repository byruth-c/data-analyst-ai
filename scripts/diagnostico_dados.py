
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            order_status,
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE order_delivered_customer_date IS NULL
                   OR TRIM(order_delivered_customer_date) = ''
            ) AS entregas_sem_data
        FROM raw_olist_orders
        GROUP BY order_status
        ORDER BY total DESC
    """)

    resultados = cursor.fetchall()

print("\n=== QUALIDADE DAS DATAS POR STATUS ===")

for status, total, sem_data in resultados:
    print(
        f"Status: {status} | "
        f"Total: {total:,} | "
        f"Sem data de entrega: {sem_data:,}"
    )
