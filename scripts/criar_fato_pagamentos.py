
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS fato_pagamentos")

    cursor.execute("""
        CREATE TABLE fato_pagamentos AS
        SELECT
            order_id,
            COUNT(*) AS quantidade_pagamentos,
            SUM(payment_value) AS valor_total_pago,
            MAX(payment_installments) AS maior_numero_parcelas,
            STRING_AGG(
                DISTINCT payment_type,
                ', ' ORDER BY payment_type
            ) AS tipos_pagamento
        FROM stg_olist_order_payments
        WHERE order_id IS NOT NULL
        GROUP BY order_id
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT order_id),
            COUNT(*) FILTER (WHERE valor_total_pago IS NULL),
            SUM(valor_total_pago)
        FROM fato_pagamentos
    """)

    total, pedidos_unicos, valores_vazios, soma_pagamentos = (
        cursor.fetchone()
    )

print("\n=== FATO DE PAGAMENTOS ===")
print(f"Pedidos com pagamentos: {total:,}")
print(f"Pedidos únicos: {pedidos_unicos:,}")
print(f"Totais de pagamento vazios: {valores_vazios:,}")
print(f"Soma dos pagamentos: R$ {soma_pagamentos:,.2f}")
print("Tabela criada: fato_pagamentos")
