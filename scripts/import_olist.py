
import csv
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

load_dotenv(BASE_DIR / ".env")

FILES = {
    "olist_customers_dataset.csv": "raw_olist_customers",
    "olist_geolocation_dataset.csv": "raw_olist_geolocation",
    "olist_orders_dataset.csv": "raw_olist_orders",
    "olist_order_items_dataset.csv": "raw_olist_order_items",
    "olist_order_payments_dataset.csv": "raw_olist_order_payments",
    "olist_order_reviews_dataset.csv": "raw_olist_order_reviews",
    "olist_products_dataset.csv": "raw_olist_products",
    "olist_sellers_dataset.csv": "raw_olist_sellers",
    "product_category_name_translation.csv": "raw_product_category_translation",
}


def main():
    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD não encontrada no arquivo .env"
        )

    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "data_analyst"),
        user=os.getenv("POSTGRES_USER", "analyst"),
        password=password,
    ) as conn:

        for filename, table in FILES.items():
            path = DATA_DIR / filename

            if not path.is_file():
                raise FileNotFoundError(
                    f"Arquivo não encontrado: {path}"
                )

            print(f"\nImportando {filename}...")

            with path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.reader(file)
                headers = next(reader)

                columns = [
                    re.sub(r"[^a-zA-Z0-9_]", "_", header).lower()
                    for header in headers
                ]

                if len(columns) != len(set(columns)):
                    raise ValueError(
                        f"Colunas duplicadas em {filename}"
                    )

                quoted_columns = ", ".join(
                    f'"{column}"' for column in columns
                )

                with conn.cursor() as cur:
                    cur.execute(f'DROP TABLE IF EXISTS "{table}"')

                    definitions = ", ".join(
                        f'"{column}" TEXT' for column in columns
                    )

                    cur.execute(
                        f'CREATE TABLE "{table}" ({definitions})'
                    )

                    copy_sql = (
                        f'COPY "{table}" ({quoted_columns}) FROM STDIN'
                    )

                    count = 0

                    with cur.copy(copy_sql) as copy:
                        for row in reader:
                            if len(row) != len(columns):
                                raise ValueError(
                                    f"Linha inválida em {filename}, "
                                    f"registro {count + 2}"
                                )

                            copy.write_row(row)
                            count += 1

            print(f"OK: {count:,} registros importados.")

    print("\nImportação concluída!")


if __name__ == "__main__":
    main()
