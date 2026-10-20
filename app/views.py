import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import pagamentos
from .forms import CadastroForm, TreinoForm
from .models import Aluno, ListaExercicios, Matricula, Mensalidade, Professor, Treino
from django.apps import AppConfig as BaseAppConfig


class AppConfig(BaseAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"


def home(request):
    todos = Treino.objects.order_by("-criado_em")

    return render(
        request,
        "home.html",
        {
            # Os 6 mais recentes (o grid da home tem 3 colunas x 2 linhas)
            "treinos": todos[:6],
            # Total real: o template não consegue contar a lista fatiada
            "total_treinos": todos.count(),
        },
    )


def lista_treinos(request):
    treinos = Treino.objects.all().order_by("-criado_em")
    return render(request, "treinos/lista.html", {"treinos": treinos})


def detalhe_treino(request, id):
    treino = get_object_or_404(Treino, id=id)
    return render(request, "treinos/detalhe.html", {"treino": treino})


@login_required
def criar_treino(request):
    form = TreinoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        treino = form.save(commit=False)
        # Se quem cadastrou é personal, o treino fica no nome dele
        treino.professor = Professor.objects.filter(usuario=request.user).first()
        treino.save()
        messages.success(request, f"Treino “{treino.nome}” cadastrado com sucesso.")
        return redirect("lista_treinos")

    return render(
        request,
        "treinos/form.html",
        {"form": form, "titulo": "Novo treino"},
    )


@login_required
def editar_treino(request, id):
    treino = get_object_or_404(Treino, id=id)
    form = TreinoForm(request.POST or None, instance=treino)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Treino atualizado com sucesso.")
        return redirect("detalhe_treino", id=treino.id)

    return render(
        request,
        "treinos/form.html",
        {"form": form, "titulo": "Editar treino"},
    )


@login_required
def excluir_treino(request, id):
    treino = get_object_or_404(Treino, id=id)

    if request.method == "POST":
        nome = treino.nome
        treino.delete()
        messages.success(request, f"Treino “{nome}” excluído.")
        return redirect("lista_treinos")

    return render(request, "treinos/excluir.html", {"treino": treino})


def cadastro(request):
    # Quem já está logado não precisa ver a tela de cadastro
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = CadastroForm(request.POST)

        if form.is_valid():
            # O form cria o perfil certo (Aluno ou Personal) junto com o usuário
            user = form.save()

            if form.eh_personal:
                proximo_passo = "Agora é só entrar, criar suas turmas e adicionar seus alunos."
            else:
                proximo_passo = "Agora é só entrar e acompanhar seus treinos e mensalidades."

            # fail_silently: um problema no envio não deve impedir o cadastro
            send_mail(
                subject="Bem-vindo ao FitManager",
                message=(
                    f"Olá, {user.first_name or user.username}!\n\n"
                    f"Sua conta no FitManager foi criada com sucesso. {proximo_passo}\n"
                ),
                from_email=None,  # usa DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
                fail_silently=True,
            )

            messages.success(
                request,
                "Conta criada com sucesso! Enviamos um e-mail de boas-vindas.",
            )
            return redirect("login")
    else:
        form = CadastroForm()

    return render(request, "treinos/cadastro.html", {"form": form})


@login_required
def minhas_mensalidades(request):
    aluno = Aluno.objects.filter(usuario=request.user).first()
    mensalidades = (
        Mensalidade.objects.filter(matricula__aluno=aluno)
        .select_related("matricula")
        if aluno
        else Mensalidade.objects.none()
    )
    return render(
        request,
        "treinos/mensalidades.html",
        {"mensalidades": mensalidades},
    )


@login_required
def minhas_listas(request):
    """Área do aluno: turmas em que está e listas que o personal montou."""
    aluno = Aluno.objects.filter(usuario=request.user).first()
    if aluno is None:
        # Personal não tem "minhas listas": vai para o painel dele
        return redirect("painel_personal")

    listas = (
        ListaExercicios.objects.filter(aluno=aluno)
        .select_related("personal")
        .prefetch_related("itens")
    )
    matriculas = (
        Matricula.objects.filter(aluno=aluno, ativa=True, turma__isnull=False)
        .select_related("turma__personal")
    )
    return render(
        request,
        "aluno/minhas_listas.html",
        {
            "listas_ativas": [l for l in listas if l.ativa],
            "listas_arquivadas": [l for l in listas if not l.ativa],
            "matriculas": matriculas,
        },
    )


@login_required
def detalhe_lista(request, id):
    lista = get_object_or_404(
        ListaExercicios.objects.select_related("personal", "aluno__usuario"),
        id=id,
    )
    # Só o aluno dono da lista ou o personal que a criou podem ver
    eh_aluno = lista.aluno.usuario_id == request.user.id
    eh_personal = lista.personal.usuario_id == request.user.id
    if not (eh_aluno or eh_personal):
        raise Http404

    return render(
        request,
        "aluno/detalhe_lista.html",
        {"lista": lista, "itens": lista.itens.all(), "eh_personal": eh_personal},
    )


def _mensalidade_do_usuario(request, id):
    # Só o dono da mensalidade consegue pagar ou atualizar
    return get_object_or_404(
        Mensalidade,
        id=id,
        matricula__aluno__usuario=request.user,
    )


@login_required
@require_POST
def pagar_mensalidade(request, id):
    mensalidade = _mensalidade_do_usuario(request, id)

    if mensalidade.status != "Pendente":
        messages.info(request, "Esta mensalidade não está pendente.")
        return redirect("minhas_mensalidades")

    try:
        url_pagamento = pagamentos.criar_preferencia(mensalidade)
    except pagamentos.PagamentoErro:
        messages.error(
            request,
            "Não foi possível iniciar o pagamento agora. Tente novamente em instantes.",
        )
        return redirect("minhas_mensalidades")

    # Leva o aluno para o checkout do Mercado Pago (Pix, cartão ou boleto)
    return redirect(url_pagamento)


@login_required
def pagamento_retorno(request):
    """Página para onde o Mercado Pago devolve o aluno depois do checkout."""
    payment_id = request.GET.get("payment_id") or request.GET.get("collection_id")
    status_url = request.GET.get("status") or request.GET.get("collection_status")

    mensalidade = None
    if payment_id and payment_id != "null":
        try:
            # Não confiamos no status da URL: reconsultamos na API
            mensalidade = pagamentos.sincronizar(pagamentos.buscar_pagamento(payment_id))
        except pagamentos.PagamentoErro:
            pass

    if mensalidade and mensalidade.status == "Paga":
        messages.success(request, "Pagamento confirmado! Obrigado.")
    elif status_url in ("pending", "in_process"):
        messages.info(
            request,
            "Pagamento em análise. Assim que for confirmado, a mensalidade será atualizada.",
        )
    else:
        messages.warning(request, "O pagamento não foi concluído. Você pode tentar novamente.")

    return redirect("minhas_mensalidades")


@login_required
@require_POST
def atualizar_pagamento(request, id):
    """Botão "Já paguei? Atualizar": busca o pagamento e atualiza o status."""
    mensalidade = _mensalidade_do_usuario(request, id)

    try:
        for pagamento in pagamentos.buscar_pagamentos_da_mensalidade(mensalidade):
            if pagamento.get("status") == "approved":
                pagamentos.sincronizar(pagamento)
                break
    except pagamentos.PagamentoErro:
        messages.error(request, "Não foi possível consultar o pagamento agora.")
        return redirect("minhas_mensalidades")

    mensalidade.refresh_from_db()
    if mensalidade.status == "Paga":
        messages.success(request, "Pagamento confirmado! Obrigado.")
    else:
        messages.info(request, "Ainda não encontramos um pagamento aprovado para esta mensalidade.")
    return redirect("minhas_mensalidades")


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """Recebe os avisos do Mercado Pago (não usa login nem CSRF)."""
    if not pagamentos.assinatura_valida(request):
        return HttpResponse(status=401)

    tipo = request.GET.get("type") or request.GET.get("topic")
    payment_id = request.GET.get("data.id") or request.GET.get("id")

    if not tipo or not payment_id:
        try:
            corpo = json.loads(request.body or b"{}")
        except ValueError:
            corpo = {}
        tipo = tipo or corpo.get("type")
        payment_id = payment_id or (corpo.get("data") or {}).get("id")

    # Outros tipos de evento são ignorados (respondemos 200 para não reenviar)
    if tipo != "payment" or not payment_id:
        return HttpResponse(status=200)

    try:
        pagamentos.sincronizar(pagamentos.buscar_pagamento(payment_id))
    except pagamentos.PagamentoErro:
        # 500 faz o Mercado Pago tentar de novo mais tarde
        return HttpResponse(status=500)

    return HttpResponse(status=200)
