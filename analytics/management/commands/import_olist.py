from django.core.management.base import BaseCommand

from scripts.import_olist import main


class Command(BaseCommand):
    help = "Importa os CSVs da Olist (data/raw) para o PostgreSQL"

    def handle(self, *args, **options):
        main()
