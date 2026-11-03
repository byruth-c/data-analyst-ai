
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT order_status, COUNT(*) AS total
        FROM raw_olist_orders
        GROUP BY order_status
        ORDER BY total DESC
    """)

    resultados = cursor.fetchall()

print("\n=== PEDIDOS POR STATUS ===")

for status, total in resultados:
    print(f"{status}: {total:,}")
