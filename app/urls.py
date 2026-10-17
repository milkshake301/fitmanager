from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

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