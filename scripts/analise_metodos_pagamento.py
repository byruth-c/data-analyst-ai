
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            payment_type,
            COUNT(*) AS quantidade_pagamentos,
            COUNT(DISTINCT order_id) AS pedidos,
            ROUND(SUM(payment_value::numeric), 2) AS valor_total,
            ROUND(AVG(payment_value::numeric), 2) AS valor_medio
        FROM raw_olist_order_payments
        WHERE NULLIF(TRIM(payment_value), '') IS NOT NULL
        GROUP BY payment_type
        ORDER BY SUM(payment_value::numeric) DESC
    """)

    resultados = cursor.fetchall()

print("\n=== ANÁLISE DE MÉTODOS DE PAGAMENTO ===")

for metodo, quantidade, pedidos, total, media in resultados:
    print(f"\nMétodo: {metodo}")
    print(f"Registros de pagamento: {quantidade:,}")
    print(f"Pedidos: {pedidos:,}")
    print(f"Valor total: R$ {total:,.2f}")
    print(f"Valor médio por registro: R$ {media:,.2f}")
