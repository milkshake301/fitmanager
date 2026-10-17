import calendar
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...models import Matricula, Mensalidade


class Command(BaseCommand):
    help = (
        "Gera as mensalidades do mês para todas as matrículas ativas. "
        "Pode rodar quantas vezes quiser: não duplica."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mes",
            help="Mês de referência no formato AAAA-MM (padrão: mês atual)",
        )

    def handle(self, *args, **options):
        if options["mes"]:
            try:
                ano, mes = (int(p) for p in options["mes"].split("-"))
                primeiro_dia = date(ano, mes, 1)
            except ValueError:
                raise CommandError("Use o formato AAAA-MM, por exemplo: 2026-11")
        else:
            hoje = timezone.localdate()
            primeiro_dia = date(hoje.year, hoje.month, 1)

        ultimo_dia = date(
            primeiro_dia.year,
            primeiro_dia.month,
            calendar.monthrange(primeiro_dia.year, primeiro_dia.month)[1],
        )

        matriculas = Matricula.objects.filter(
            ativa=True,
            data_inicio__lte=ultimo_dia,
        ).exclude(data_fim__lt=primeiro_dia)

        criadas = 0
        for matricula in matriculas:
            _, nova = Mensalidade.objects.get_or_create(
                matricula=matricula,
                competencia=primeiro_dia,
                defaults={
                    "valor": matricula.valor_mensalidade,
                    # min(): protege contra dia inválido salvo fora do admin/formulário
                    "vencimento": primeiro_dia.replace(
                        day=min(matricula.dia_vencimento, ultimo_dia.day)
                    ),
                },
            )
            criadas += nova

        self.stdout.write(
            self.style.SUCCESS(
                f"{criadas} mensalidade(s) criada(s) para {primeiro_dia:%m/%Y} "
                f"({matriculas.count()} matrícula(s) ativa(s))."
            )
        )
