
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS fato_vendas")

    cursor.execute("""
        CREATE TABLE fato_vendas AS
        SELECT
            o.order_id,
            o.customer_id,
            o.order_status,
            o.order_purchase_timestamp::DATE AS data_pedido,
            i.order_item_id,
            i.product_id,
            i.seller_id,
            p.product_category_name,
            c.product_category_name_english AS categoria_ingles,
            i.price AS valor_item,
            i.freight_value AS valor_frete,
            (i.price + i.freight_value) AS valor_total_item
        FROM stg_olist_orders o
        INNER JOIN stg_olist_order_items i
            ON o.order_id = i.order_id
        LEFT JOIN stg_olist_products p
            ON i.product_id = p.product_id
        LEFT JOIN stg_olist_categories c
            ON p.product_category_name = c.product_category_name
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT order_id),
            COUNT(*) FILTER (
                WHERE product_category_name IS NULL
            ),
            SUM(valor_item),
            SUM(valor_frete),
            SUM(valor_total_item)
        FROM fato_vendas
    """)

    total_itens, pedidos, categorias_vazias, soma_itens, soma_fretes, soma_total = (
        cursor.fetchone()
    )

print("\n=== FATO DE VENDAS ===")
print(f"Linhas: {total_itens:,}")
print(f"Pedidos distintos com itens: {pedidos:,}")
print(f"Itens sem categoria: {categorias_vazias:,}")
print(f"Valor dos itens: R$ {soma_itens:,.2f}")
print(f"Fretes: R$ {soma_fretes:,.2f}")
print(f"Valor dos itens + fretes: R$ {soma_total:,.2f}")
print("Tabela criada: fato_vendas")
