"""Geração de mensalidades a partir das matrículas.

Cada matrícula ativa gera uma mensalidade por mês (competência = dia 1 do mês).
A geração é idempotente: rodar duas vezes no mesmo mês não duplica nada,
porque Mensalidade tem unique_together (matricula, competencia).
"""
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Matricula, Mensalidade


def primeiro_dia(dia):
    return dia.replace(day=1)


def competencia_de_texto(texto):
    """Converte 'AAAA-MM' em date(AAAA, MM, 1). Devolve None se inválido."""
    try:
        ano, mes = texto.split("-")[:2]
        return date(int(ano), int(mes), 1)
    except (AttributeError, ValueError):
        return None


def gerar_mensalidade(matricula, competencia=None):
    """Cria a mensalidade da matrícula para a competência (se ainda não existir).

    Devolve (mensalidade_ou_None, criada: bool).
    """
    competencia = primeiro_dia(competencia or timezone.localdate())

    if not matricula.ativa:
        return None, False
    # Não cobra meses antes do início nem depois do fim da matrícula
    if matricula.data_inicio and competencia < primeiro_dia(matricula.data_inicio):
        return None, False
    if matricula.data_fim and competencia > matricula.data_fim:
        return None, False

    vencimento = competencia.replace(day=matricula.dia_vencimento)
    # Quem entra depois do dia de vencimento não começa "em atraso"
    if matricula.data_inicio and vencimento < matricula.data_inicio:
        vencimento = matricula.data_inicio

    try:
        with transaction.atomic():
            return Mensalidade.objects.get_or_create(
                matricula=matricula,
                competencia=competencia,
                defaults={
                    "valor": matricula.valor_mensalidade,
                    "vencimento": vencimento,
                },
            )
    except IntegrityError:
        # Corrida com outra geração simultânea: já existe
        return Mensalidade.objects.get(matricula=matricula, competencia=competencia), False


def gerar_mensalidades_do_mes(competencia=None, personal=None):
    """Gera as mensalidades de todas as matrículas ativas. Devolve quantas criou."""
    matriculas = Matricula.objects.filter(ativa=True).select_related("turma")
    if personal is not None:
        matriculas = matriculas.filter(turma__personal=personal)

    criadas = 0
    for matricula in matriculas:
        _, criada = gerar_mensalidade(matricula, competencia)
        criadas += int(criada)
    return criadas
