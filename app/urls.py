from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views, views_personal as personal

urlpatterns = [
    path("", views.home, name="home"),
    path("treinos/", views.lista_treinos, name="lista_treinos"),
    path("treinos/novo/", views.criar_treino, name="criar_treino"),
    path("treinos/<int:id>/", views.detalhe_treino, name="detalhe_treino"),
    path("treinos/<int:id>/editar/", views.editar_treino, name="editar_treino"),
    path("treinos/<int:id>/excluir/", views.excluir_treino, name="excluir_treino"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("mensalidades/", views.minhas_mensalidades, name="minhas_mensalidades"),
    path("mensalidades/<int:id>/pagar/", views.pagar_mensalidade, name="pagar_mensalidade"),
    path("mensalidades/<int:id>/atualizar/", views.atualizar_pagamento, name="atualizar_pagamento"),
    # Área do aluno
    path("minhas-listas/", views.minhas_listas, name="minhas_listas"),
    path("listas/<int:id>/", views.detalhe_lista, name="detalhe_lista"),
    # Área do personal
    path("personal/", personal.painel_personal, name="painel_personal"),
    path("personal/turmas/", personal.lista_turmas, name="lista_turmas"),
    path("personal/turmas/nova/", personal.criar_turma, name="criar_turma"),
    path("personal/turmas/<int:id>/", personal.detalhe_turma, name="detalhe_turma"),
    path("personal/turmas/<int:id>/editar/", personal.editar_turma, name="editar_turma"),
    path("personal/matriculas/<int:id>/remover/", personal.remover_aluno_turma, name="remover_aluno_turma"),
    path("personal/listas/", personal.listas_exercicios, name="listas_exercicios"),
    path("personal/listas/nova/", personal.criar_lista, name="criar_lista"),
    path("personal/listas/<int:id>/editar/", personal.editar_lista, name="editar_lista"),
    path("personal/listas/<int:id>/excluir/", personal.excluir_lista, name="excluir_lista"),
    # O financeiro agora faz parte do painel. A rota antiga só redireciona (links/favoritos antigos).
    path(
        "personal/financeiro/",
        RedirectView.as_view(pattern_name="painel_personal", query_string=True),
        name="financeiro",
    ),
    path("personal/financeiro/gerar/", personal.gerar_mensalidades, name="gerar_mensalidades"),
    path("personal/mensalidades/<int:id>/paga/", personal.marcar_mensalidade_paga, name="marcar_mensalidade_paga"),
    path("personal/mensalidades/<int:id>/cancelar/", personal.cancelar_mensalidade, name="cancelar_mensalidade"),
    path("personal/mensalidades/<int:id>/reabrir/", personal.reabrir_mensalidade, name="reabrir_mensalidade"),
    path("pagamento/retorno/", views.pagamento_retorno, name="pagamento_retorno"),
    path("pagamento/webhook/", views.webhook_mercadopago, name="webhook_mercadopago"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
]