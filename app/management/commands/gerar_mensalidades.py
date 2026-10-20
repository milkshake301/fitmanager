from django.core.management.base import BaseCommand, CommandError

from app.cobrancas import competencia_de_texto, gerar_mensalidades_do_mes


class Command(BaseCommand):
    help = (
        "Gera as mensalidades do mês para todas as matrículas ativas. "
        "Pode rodar todo dia pelo cron: não duplica mensalidades."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            help="Mês no formato AAAA-MM (padrão: mês atual)",
        )

    def handle(self, *args, **options):
        competencia = None
        if options.get("competencia"):
            competencia = competencia_de_texto(options["competencia"])
            if competencia is None:
                raise CommandError("Use o formato AAAA-MM, por exemplo 2026-11.")

        criadas = gerar_mensalidades_do_mes(competencia)
        self.stdout.write(self.style.SUCCESS(f"{criadas} mensalidade(s) criada(s)."))
