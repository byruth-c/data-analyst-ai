
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            order_id,
            order_status,
            valor_itens,
            valor_frete,
            valor_total_pago,
            diferenca
        FROM reconciliacao_pedidos
        WHERE ABS(diferenca) > 0.01
        ORDER BY ABS(diferenca) DESC
        LIMIT 20
    """)

    resultados = cursor.fetchall()

print("\n=== 20 MAIORES DIVERGÊNCIAS ===")

for pedido, status, itens, frete, pago, diferenca in resultados:
    print(
        f"Pedido: {pedido} | Status: {status} | "
        f"Itens: R$ {itens:,.2f} | "
        f"Frete: R$ {frete:,.2f} | "
        f"Pago: R$ {pago:,.2f} | "
        f"Diferença: R$ {diferenca:,.2f}"
    )
