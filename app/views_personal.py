"""Área do personal: painel, turmas, listas de exercícios e financeiro."""
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import cobrancas
from .forms import AdicionarAlunoForm, ItemListaFormSet, ListaExerciciosForm, TurmaForm
from .models import ListaExercicios, Matricula, Mensalidade, Professor, Turma


def personal_required(view):
    """Só deixa passar quem tem conta de personal. Coloca o perfil em request.personal."""

    @wraps(view)
    @login_required
    def _view(request, *args, **kwargs):
        personal = Professor.objects.filter(usuario=request.user).first()
        if personal is None:
            messages.error(request, "Essa área é exclusiva para contas de personal.")
            return redirect("home")
        request.personal = personal
        return view(request, *args, **kwargs)

    return _view


def _mensalidades_do_personal(personal):
    return Mensalidade.objects.filter(matricula__turma__personal=personal)


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------

@personal_required
def painel_personal(request):
    personal = request.personal
    hoje = timezone.localdate()
    mes_atual = hoje.replace(day=1)

    turmas = (
        personal.turmas.filter(ativa=True)
        .annotate(total_alunos=Count("matriculas", filter=Q(matriculas__ativa=True)))
    )
    mensalidades_mes = _mensalidades_do_personal(personal).filter(competencia=mes_atual)
    em_atraso = _mensalidades_do_personal(personal).filter(status="Pendente", vencimento__lt=hoje)

    contexto = {
        "personal": personal,
        "turmas": turmas,
        "total_alunos": personal.alunos.count(),
        "recebido_mes": mensalidades_mes.filter(status="Paga").aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "a_receber_mes": mensalidades_mes.filter(status="Pendente").aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "qtd_atraso": em_atraso.count(),
        "listas_recentes": personal.listas.select_related("aluno__usuario")[:5],
        "mes_atual": mes_atual,
    }
    return render(request, "personal/painel.html", contexto)


# ---------------------------------------------------------------------------
# Turmas
# ---------------------------------------------------------------------------

@personal_required
def lista_turmas(request):
    turmas = request.personal.turmas.annotate(
        total_alunos=Count("matriculas", filter=Q(matriculas__ativa=True))
    )
    return render(request, "personal/turmas.html", {"turmas": turmas})


@personal_required
def criar_turma(request):
    form = TurmaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        turma = form.save(commit=False)
        turma.personal = request.personal
        turma.save()
        messages.success(request, f"Turma “{turma.nome}” criada. Agora adicione os alunos.")
        return redirect("detalhe_turma", id=turma.id)

    return render(request, "personal/turma_form.html", {"form": form, "titulo": "Nova turma"})


@personal_required
def editar_turma(request, id):
    turma = get_object_or_404(Turma, id=id, personal=request.personal)
    form = TurmaForm(request.POST or None, instance=turma)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Turma atualizada.")
        return redirect("detalhe_turma", id=turma.id)

    return render(
        request,
        "personal/turma_form.html",
        {"form": form, "titulo": "Editar turma", "turma": turma},
    )


@personal_required
def detalhe_turma(request, id):
    turma = get_object_or_404(Turma, id=id, personal=request.personal)

    form = AdicionarAlunoForm(
        request.POST or None,
        turma=turma,
        initial={
            "valor_mensalidade": turma.valor_mensalidade,
            "dia_vencimento": turma.dia_vencimento,
            "data_inicio": timezone.localdate(),
        },
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            matricula = Matricula.objects.create(
                aluno=form.cleaned_data["aluno"],
                turma=turma,
                plano="Mensal",
                data_inicio=form.cleaned_data["data_inicio"],
                valor_mensalidade=form.cleaned_data["valor_mensalidade"],
                dia_vencimento=form.cleaned_data["dia_vencimento"],
            )
            # Já deixa a primeira mensalidade gerada
            cobrancas.gerar_mensalidade(matricula, form.cleaned_data["data_inicio"])

        messages.success(request, f"{matricula.aluno} entrou na turma.")
        return redirect("detalhe_turma", id=turma.id)

    matriculas = turma.matriculas_ativas
    hoje = timezone.localdate()
    pendencias = {
        m["matricula_id"]: m["total"]
        for m in Mensalidade.objects.filter(
            matricula__in=matriculas, status="Pendente", vencimento__lt=hoje
        )
        .values("matricula_id")
        .annotate(total=Count("id"))
    }
    for matricula in matriculas:
        matricula.qtd_atraso = pendencias.get(matricula.id, 0)

    return render(
        request,
        "personal/turma_detalhe.html",
        {"turma": turma, "matriculas": matriculas, "form": form},
    )


@personal_required
@require_POST
def remover_aluno_turma(request, id):
    matricula = get_object_or_404(
        Matricula, id=id, turma__personal=request.personal, ativa=True
    )
    hoje = timezone.localdate()

    with transaction.atomic():
        matricula.ativa = False
        matricula.data_fim = hoje
        matricula.save(update_fields=["ativa", "data_fim"])
        # Cobranças de meses futuros deixam de valer
        matricula.mensalidades.filter(
            status="Pendente", competencia__gt=hoje.replace(day=1)
        ).update(status="Cancelada")

    messages.success(request, f"{matricula.aluno} saiu da turma {matricula.turma}.")
    return redirect("detalhe_turma", id=matricula.turma_id)


# ---------------------------------------------------------------------------
# Listas de exercícios
# ---------------------------------------------------------------------------

@personal_required
def listas_exercicios(request):
    personal = request.personal
    listas = personal.listas.select_related("aluno__usuario").annotate(total_itens=Count("itens"))

    aluno_id = request.GET.get("aluno")
    aluno_filtro = None
    if aluno_id and aluno_id.isdigit():
        aluno_filtro = personal.alunos.filter(id=aluno_id).select_related("usuario").first()
        if aluno_filtro:
            listas = listas.filter(aluno=aluno_filtro)

    return render(
        request,
        "personal/listas.html",
        {
            "listas": listas,
            "alunos": personal.alunos.select_related("usuario").order_by("usuario__username"),
            "aluno_filtro": aluno_filtro,
        },
    )


def _salvar_lista(request, lista, titulo):
    personal = request.personal
    eh_nova = lista.pk is None

    inicial = {}
    if eh_nova and request.GET.get("aluno", "").isdigit():
        inicial["aluno"] = request.GET["aluno"]

    form = ListaExerciciosForm(
        request.POST or None, instance=lista, personal=personal, initial=inicial
    )
    formset = ItemListaFormSet(request.POST or None, instance=lista, prefix="itens")

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            lista = form.save(commit=False)
            lista.personal = personal
            lista.save()
            formset.instance = lista
            formset.save(commit=False)  # preenche formset.deleted_objects
            for item in formset.deleted_objects:
                item.delete()

            # Salva na ordem em que os exercícios aparecem na tela
            ordem = 0
            for f in formset.forms:
                if f.cleaned_data.get("DELETE") or (not f.instance.pk and not f.has_changed()):
                    continue
                ordem += 1
                item = f.save(commit=False)
                item.lista = lista
                item.ordem = ordem
                item.save()

        messages.success(
            request,
            f"Lista “{lista.titulo}” {'criada' if eh_nova else 'atualizada'} para {lista.aluno}.",
        )
        return redirect("detalhe_lista", id=lista.id)

    if eh_nova and not form.fields["aluno"].queryset.exists():
        messages.info(request, "Você ainda não tem alunos. Crie uma turma e adicione alunos primeiro.")
        return redirect("lista_turmas")

    return render(
        request,
        "personal/lista_form.html",
        {"form": form, "formset": formset, "titulo": titulo, "lista": lista},
    )


@personal_required
def criar_lista(request):
    return _salvar_lista(request, ListaExercicios(), "Nova lista de exercícios")


@personal_required
def editar_lista(request, id):
    lista = get_object_or_404(ListaExercicios, id=id, personal=request.personal)
    return _salvar_lista(request, lista, "Editar lista de exercícios")


@personal_required
@require_POST
def excluir_lista(request, id):
    lista = get_object_or_404(ListaExercicios, id=id, personal=request.personal)
    titulo = lista.titulo
    lista.delete()
    messages.success(request, f"Lista “{titulo}” excluída.")
    return redirect("listas_exercicios")


# ---------------------------------------------------------------------------
# Financeiro (mensalidades)
# ---------------------------------------------------------------------------

@personal_required
def financeiro(request):
    personal = request.personal
    hoje = timezone.localdate()

    competencia = cobrancas.competencia_de_texto(request.GET.get("mes", "")) or hoje.replace(day=1)
    status = request.GET.get("status", "")
    turma_id = request.GET.get("turma", "")

    mensalidades = (
        _mensalidades_do_personal(personal)
        .filter(competencia=competencia)
        .select_related("matricula__aluno__usuario", "matricula__turma")
        .order_by("matricula__turma__nome", "matricula__aluno__usuario__username")
    )
    if turma_id.isdigit():
        mensalidades = mensalidades.filter(matricula__turma_id=turma_id)

    # Totais antes do filtro de status, para o resumo sempre mostrar o mês todo
    totais = {
        "pago": mensalidades.filter(status="Paga").aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "pendente": mensalidades.filter(status="Pendente").aggregate(t=Sum("valor"))["t"] or Decimal("0"),
        "atraso": mensalidades.filter(status="Pendente", vencimento__lt=hoje).count(),
    }

    if status == "atraso":
        mensalidades = mensalidades.filter(status="Pendente", vencimento__lt=hoje)
    elif status in ("Pendente", "Paga", "Cancelada"):
        mensalidades = mensalidades.filter(status=status)

    return render(
        request,
        "personal/financeiro.html",
        {
            "mensalidades": mensalidades,
            "totais": totais,
            "competencia": competencia,
            "status": status,
            "turma_id": turma_id,
            "turmas": personal.turmas.all(),
        },
    )


@personal_required
@require_POST
def gerar_mensalidades(request):
    competencia = cobrancas.competencia_de_texto(request.POST.get("mes", "")) or timezone.localdate()
    criadas = cobrancas.gerar_mensalidades_do_mes(competencia, personal=request.personal)

    if criadas:
        messages.success(request, f"{criadas} mensalidade(s) gerada(s) para {competencia:%m/%Y}.")
    else:
        messages.info(request, f"Todas as mensalidades de {competencia:%m/%Y} já estavam geradas.")
    return redirect(f"{_url_financeiro()}?mes={competencia:%Y-%m}")


def _url_financeiro():
    return reverse("financeiro")


def _mensalidade_do_personal(request, id):
    return get_object_or_404(Mensalidade, id=id, matricula__turma__personal=request.personal)


def _voltar_financeiro(request, mensalidade):
    return redirect(f"{_url_financeiro()}?mes={mensalidade.competencia:%Y-%m}")


@personal_required
@require_POST
def marcar_mensalidade_paga(request, id):
    """Para quem pagou por fora (dinheiro, Pix direto ao personal etc.)."""
    mensalidade = _mensalidade_do_personal(request, id)
    if mensalidade.status != "Pendente":
        messages.info(request, "Só mensalidades pendentes podem ser marcadas como pagas.")
    else:
        mensalidade.status = "Paga"
        mensalidade.data_pagamento = timezone.localdate()
        mensalidade.save(update_fields=["status", "data_pagamento"])
        messages.success(request, f"Mensalidade de {mensalidade.matricula.aluno} marcada como paga.")
    return _voltar_financeiro(request, mensalidade)


@personal_required
@require_POST
def cancelar_mensalidade(request, id):
    mensalidade = _mensalidade_do_personal(request, id)
    if mensalidade.status != "Pendente":
        messages.info(request, "Só mensalidades pendentes podem ser canceladas.")
    else:
        mensalidade.status = "Cancelada"
        mensalidade.save(update_fields=["status"])
        messages.success(request, f"Mensalidade de {mensalidade.matricula.aluno} cancelada.")
    return _voltar_financeiro(request, mensalidade)


@personal_required
@require_POST
def reabrir_mensalidade(request, id):
    """Desfaz um cancelamento ou uma baixa manual (não mexe em pagamentos do Mercado Pago)."""
    mensalidade = _mensalidade_do_personal(request, id)
    if mensalidade.status == "Paga" and mensalidade.mp_payment_id:
        messages.error(request, "Esta mensalidade foi paga pelo Mercado Pago e não pode ser reaberta aqui.")
    elif mensalidade.status == "Pendente":
        messages.info(request, "Esta mensalidade já está pendente.")
    else:
        mensalidade.status = "Pendente"
        mensalidade.data_pagamento = None
        mensalidade.save(update_fields=["status", "data_pagamento"])
        messages.success(request, "Mensalidade reaberta.")
    return _voltar_financeiro(request, mensalidade)
