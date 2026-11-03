
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS stg_olist_order_items")

    cursor.execute("""
        CREATE TABLE stg_olist_order_items AS
        SELECT
            NULLIF(TRIM(order_id), '') AS order_id,
            NULLIF(TRIM(order_item_id), '')::INTEGER
                AS order_item_id,
            NULLIF(TRIM(product_id), '') AS product_id,
            NULLIF(TRIM(seller_id), '') AS seller_id,
            NULLIF(TRIM(shipping_limit_date), '')::TIMESTAMP
                AS shipping_limit_date,
            NULLIF(TRIM(price), '')::NUMERIC(12, 2)
                AS price,
            NULLIF(TRIM(freight_value), '')::NUMERIC(12, 2)
                AS freight_value
        FROM raw_olist_order_items
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT order_id),
            COUNT(*) FILTER (WHERE price IS NULL),
            COUNT(*) FILTER (WHERE freight_value IS NULL),
            SUM(price),
            SUM(freight_value)
        FROM stg_olist_order_items
    """)

    total, pedidos, precos_vazios, fretes_vazios, soma_precos, soma_fretes = cursor.fetchone()

print("\n=== STAGING DE ITENS DOS PEDIDOS ===")
print(f"Registros: {total:,}")
print(f"Pedidos distintos: {pedidos:,}")
print(f"Preços vazios: {precos_vazios:,}")
print(f"Fretes vazios: {fretes_vazios:,}")
print(f"Soma dos preços dos itens: R$ {soma_precos:,.2f}")
print(f"Soma dos fretes: R$ {soma_fretes:,.2f}")
print("Tabela criada: stg_olist_order_items")
