"""Deixa o banco igual aos models do app, sem apagar dados.

Uso:  python manage.py consertar_banco

Serve para quando aparece "no such table" ou "has no column named" mesmo
depois de rodar makemigrations/migrate (histórico de migrações fora de sincronia).

O que faz:
1. Gera a migração que estiver faltando (makemigrations app).
2. Cria as tabelas e colunas que faltam no banco (sem mexer no que já existe).
3. Marca as migrações do app como aplicadas, para o Django não tentar
   criar tudo de novo depois.
"""
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

APP = "app"


class Command(BaseCommand):
    help = "Cria as tabelas e colunas que faltam no banco para o app, sem apagar dados."

    def handle(self, *args, **options):
        self.stdout.write("1) Conferindo migrações...")
        call_command("makemigrations", APP, interactive=False, verbosity=1)

        self.stdout.write("2) Conferindo tabelas e colunas...")
        alteracoes = self._completar_esquema()
        if alteracoes:
            for texto in alteracoes:
                self.stdout.write(f"   + {texto}")
        else:
            self.stdout.write("   Nada faltando no banco.")

        self.stdout.write("3) Atualizando o histórico de migrações...")
        call_command("migrate", APP, fake=True, verbosity=1)
        call_command("migrate", verbosity=1)  # outros apps (auth, admin...)

        self.stdout.write(self.style.SUCCESS("Banco corrigido. Reinicie o runserver."))

    def _completar_esquema(self):
        alteracoes = []
        introspection = connection.introspection

        with connection.schema_editor() as editor:
            for model in apps.get_app_config(APP).get_models():
                tabelas = set(introspection.table_names())
                tabela = model._meta.db_table

                if tabela not in tabelas:
                    editor.create_model(model)  # já cria as tabelas de ManyToMany
                    alteracoes.append(f"tabela {tabela}")
                    continue

                with connection.cursor() as cursor:
                    colunas = {
                        c.name for c in introspection.get_table_description(cursor, tabela)
                    }

                for campo in model._meta.local_fields:
                    if campo.column not in colunas:
                        editor.add_field(model, campo)
                        alteracoes.append(f"coluna {tabela}.{campo.column}")

                for campo in model._meta.local_many_to_many:
                    through = campo.remote_field.through
                    if through._meta.auto_created and through._meta.db_table not in tabelas:
                        editor.create_model(through)
                        alteracoes.append(f"tabela {through._meta.db_table}")

        return alteracoes
