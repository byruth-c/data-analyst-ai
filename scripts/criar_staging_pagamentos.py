from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS stg_olist_order_payments")

    cursor.execute("""
        CREATE TABLE stg_olist_order_payments AS
        SELECT
            NULLIF(TRIM(order_id), '') AS order_id,
            NULLIF(TRIM(payment_sequential), '')::INTEGER
                AS payment_sequential,
            NULLIF(TRIM(payment_type), '') AS payment_type,
            NULLIF(TRIM(payment_installments), '')::INTEGER
                AS payment_installments,
            NULLIF(TRIM(payment_value), '')::NUMERIC(12, 2)
                AS payment_value
        FROM raw_olist_order_payments
    """)

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE order_id IS NULL),
            COUNT(*) FILTER (WHERE payment_value IS NULL),
            SUM(payment_value)
        FROM stg_olist_order_payments
    """)

    total, ids_vazios, valores_vazios, soma = cursor.fetchone()

print("\n=== STAGING DE PAGAMENTOS ===")
print(f"Registros: {total:,}")
print(f"IDs vazios: {ids_vazios:,}")
print(f"Valores vazios: {valores_vazios:,}")
print(f"Total dos pagamentos: R$ {soma:,.2f}")
print("Tabela criada: stg_olist_order_payments")