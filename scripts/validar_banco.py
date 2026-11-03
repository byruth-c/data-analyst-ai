from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM raw_olist_orders")
    print("Total de pedidos:", cursor.fetchone()[0])

    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name LIKE 'raw_%'
        ORDER BY table_name
    """)

    print("\nTabelas importadas:")
    for row in cursor.fetchall():
        print("-", row[0])