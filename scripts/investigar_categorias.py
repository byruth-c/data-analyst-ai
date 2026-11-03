
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            p.product_category_name,
            COUNT(*) AS quantidade_itens,
            COUNT(DISTINCT p.product_id) AS produtos
        FROM stg_olist_products p
        LEFT JOIN stg_olist_categories c
            ON p.product_category_name = c.product_category_name
        JOIN stg_olist_order_items i
            ON p.product_id = i.product_id
        WHERE p.product_category_name IS NOT NULL
          AND c.product_category_name IS NULL
        GROUP BY p.product_category_name
        ORDER BY quantidade_itens DESC
    """)

    resultados = cursor.fetchall()

print("\n=== CATEGORIAS SEM TRADUÇÃO ===")

if not resultados:
    print("Nenhuma categoria sem tradução encontrada.")
else:
    for categoria, itens, produtos in resultados:
        print(
            f"Categoria: {categoria} | "
            f"Itens vendidos: {itens} | "
            f"Produtos: {produtos}"
        )

    print(f"\nTotal de categorias distintas: {len(resultados)}")

