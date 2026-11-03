
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS stg_olist_products")

    cursor.execute("""
        CREATE TABLE stg_olist_products AS
        SELECT
            NULLIF(TRIM(product_id), '') AS product_id,
            NULLIF(TRIM(product_category_name), '')
                AS product_category_name,
            NULLIF(TRIM(product_name_lenght), '')::INTEGER
                AS product_name_length,
            NULLIF(TRIM(product_description_lenght), '')::INTEGER
                AS product_description_length,
            NULLIF(TRIM(product_photos_qty), '')::INTEGER
                AS product_photos_qty,
            NULLIF(TRIM(product_weight_g), '')::NUMERIC(12, 2)
                AS product_weight_g,
            NULLIF(TRIM(product_length_cm), '')::NUMERIC(12, 2)
                AS product_length_cm,
            NULLIF(TRIM(product_height_cm), '')::NUMERIC(12, 2)
                AS product_height_cm,
            NULLIF(TRIM(product_width_cm), '')::NUMERIC(12, 2)
                AS product_width_cm
        FROM raw_olist_products
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT product_id),
            COUNT(*) FILTER (WHERE product_id IS NULL),
            COUNT(*) FILTER (WHERE product_category_name IS NULL),
            COUNT(*) FILTER (WHERE product_weight_g IS NULL)
        FROM stg_olist_products
    """)

    total, unicos, ids_vazios, categorias_vazias, pesos_vazios = (
        cursor.fetchone()
    )

print("\n=== STAGING DE PRODUTOS ===")
print(f"Registros: {total:,}")
print(f"Produtos distintos: {unicos:,}")
print(f"IDs vazios: {ids_vazios:,}")
print(f"Categorias vazias: {categorias_vazias:,}")
print(f"Pesos vazios: {pesos_vazios:,}")
print("Tabela criada: stg_olist_products")
