
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS stg_olist_categories")

    cursor.execute("""
        CREATE TABLE stg_olist_categories AS
        SELECT
            NULLIF(TRIM(product_category_name), '')
                AS product_category_name,
            NULLIF(
                TRIM(product_category_name_english), ''
            ) AS product_category_name_english
        FROM raw_product_category_translation
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT product_category_name),
            COUNT(*) FILTER (
                WHERE product_category_name IS NULL
            ),
            COUNT(*) FILTER (
                WHERE product_category_name_english IS NULL
            )
        FROM stg_olist_categories
    """)

    total, categorias, nomes_vazios, traducoes_vazias = (
        cursor.fetchone()
    )

print("\n=== STAGING DE CATEGORIAS ===")
print(f"Registros: {total:,}")
print(f"Categorias distintas: {categorias:,}")
print(f"Nomes vazios: {nomes_vazios:,}")
print(f"Traduções vazias: {traducoes_vazias:,}")
print("Tabela criada: stg_olist_categories")
