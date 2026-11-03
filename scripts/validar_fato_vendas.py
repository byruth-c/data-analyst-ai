
from django.db import connection

consultas = {
    "Status dos pedidos": """
        SELECT order_status, COUNT(DISTINCT order_id) AS pedidos
        FROM fato_vendas
        GROUP BY order_status
        ORDER BY pedidos DESC
    """,
    "Itens sem correspondência de produto": """
        SELECT COUNT(*)
        FROM fato_vendas f
        LEFT JOIN stg_olist_products p
            ON f.product_id = p.product_id
        WHERE p.product_id IS NULL
    """,
    "Itens sem categoria no produto": """
        SELECT COUNT(*)
        FROM fato_vendas f
        JOIN stg_olist_products p
            ON f.product_id = p.product_id
        WHERE p.product_category_name IS NULL
    """,
    "Categorias sem tradução": """
        SELECT COUNT(*)
        FROM fato_vendas f
        JOIN stg_olist_products p
            ON f.product_id = p.product_id
        LEFT JOIN stg_olist_categories c
            ON p.product_category_name = c.product_category_name
        WHERE p.product_category_name IS NOT NULL
          AND c.product_category_name IS NULL
    """
}

with connection.cursor() as cursor:
    for titulo, sql in consultas.items():
        cursor.execute(sql)
        resultado = cursor.fetchall()

        print(f"\n=== {titulo} ===")
        for linha in resultado:
            print(linha)
