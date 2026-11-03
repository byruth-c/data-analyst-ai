
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            order_status,
            COUNT(*) AS pedidos,
            COUNT(*) FILTER (
                WHERE ABS(diferenca) <= 0.01
            ) AS valores_iguais,
            COUNT(*) FILTER (
                WHERE diferenca > 0.01
            ) AS pagamento_maior,
            COUNT(*) FILTER (
                WHERE diferenca < -0.01
            ) AS pagamento_menor,
            SUM(valor_total_pago) AS total_pago,
            SUM(valor_itens + valor_frete) AS total_itens_frete,
            SUM(diferenca) AS diferenca_total
        FROM reconciliacao_pedidos
        GROUP BY order_status
        ORDER BY ABS(SUM(diferenca)) DESC
    """)

    resultados = cursor.fetchall()

print("\n=== RECONCILIAÇÃO POR STATUS ===")

for linha in resultados:
    (
        status, pedidos, iguais, maior, menor,
        total_pago, total_itens_frete, diferenca
    ) = linha

    print(f"\nStatus: {status}")
    print(f"Pedidos: {pedidos:,}")
    print(f"Valores iguais: {iguais:,}")
    print(f"Pagamento maior: {maior:,}")
    print(f"Pagamento menor: {menor:,}")
    print(f"Total pago: R$ {total_pago:,.2f}")
    print(f"Total itens + frete: R$ {total_itens_frete:,.2f}")
    print(f"Diferença: R$ {diferenca:,.2f}")
