
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            order_id,
            order_status,
            order_purchase_timestamp,
            order_approved_at,
            order_delivered_carrier_date,
            order_delivered_customer_date,
            order_estimated_delivery_date
        FROM raw_olist_orders
        WHERE order_status = 'delivered'
          AND (
              order_delivered_customer_date IS NULL
              OR TRIM(order_delivered_customer_date) = ''
          )
        ORDER BY order_purchase_timestamp
    """)

    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]

print(f"\nPedidos entregues sem data de entrega: {len(rows)}")

for row in rows:
    print("\n" + "-" * 60)
    for column, value in zip(columns, row):
        print(f"{column}: {value}")
