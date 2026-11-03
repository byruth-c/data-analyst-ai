
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            COALESCE(
                NULLIF(TRIM(categoria_ingles), ''),
                'categoria_nao_traduzida'
            ) AS categoria,
            COUNT(*) AS itens_vendidos,
            COUNT(DISTINCT order_id) AS pedidos,
            ROUND(SUM(valor_item)::numeric, 2) AS valor_produtos,
            ROUND(SUM(valor_frete)::numeric, 2) AS valor_frete,
            ROUND(SUM(valor_total_item)::numeric, 2) AS valor_total
        FROM fato_vendas
        WHERE order_status = 'delivered'
        GROUP BY 1
        ORDER BY SUM(valor_item) DESC
        LIMIT 15
    """)

    resultados = cursor.fetchall()

print("\n=== TOP 15 CATEGORIAS POR VALOR DE PRODUTOS ===")

for categoria, itens, pedidos, produtos, frete, total in resultados:
    print(f"\nCategoria: {categoria}")
    print(f"Itens vendidos: {itens:,}")
    print(f"Pedidos: {pedidos:,}")
    print(f"Valor dos produtos: R$ {produtos:,.2f}")
    print(f"Valor do frete: R$ {frete:,.2f}")
    print(f"Total com frete: R$ {total:,.2f}")
