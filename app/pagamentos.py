"""Integração com o Mercado Pago (Checkout Pro) para cobrar mensalidades.

Fluxo:
1. criar_preferencia() cria a cobrança e devolve a URL de pagamento (init_point).
2. O aluno paga no site do Mercado Pago.
3. O status chega de duas formas: pelo webhook e pela página de retorno.
   Nas duas, o pagamento é sempre reconsultado na API do Mercado Pago
   (buscar_pagamento) antes de marcar a mensalidade como paga, então
   ninguém consegue "forjar" um pagamento só chamando as nossas URLs.
"""
import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Mensalidade

logger = logging.getLogger(__name__)

API_URL = "https://api.mercadopago.com"
TIMEOUT = 15  # segundos


class PagamentoErro(Exception):
    """Falha ao falar com o Mercado Pago."""


def _headers():
    token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        raise PagamentoErro("MERCADOPAGO_ACCESS_TOKEN não está configurado.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _url_publica(url):
    """O Mercado Pago recusa back_urls/notification_url locais (localhost)."""
    partes = urlparse(url)
    host = (partes.hostname or "").lower()
    return partes.scheme in ("http", "https") and host not in (
        "",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
    )


def criar_preferencia(mensalidade):
    """Cria a cobrança no Mercado Pago e devolve a URL para o aluno pagar."""
    base = settings.SITE_URL.rstrip("/")

    dados = {
        "items": [
            {
                "id": str(mensalidade.pk),
                "title": f"Mensalidade {mensalidade.competencia:%m/%Y} - FitManager",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(mensalidade.valor),
            }
        ],
        # É por aqui que descobrimos qual mensalidade foi paga
        "external_reference": str(mensalidade.pk),
    }

    if _url_publica(base):
        retorno = base + reverse("pagamento_retorno")
        dados["back_urls"] = {
            "success": retorno,
            "failure": retorno,
            "pending": retorno,
        }
        dados["auto_return"] = "approved"
        dados["notification_url"] = base + reverse("webhook_mercadopago")
    else:
        logger.warning(
            "SITE_URL (%s) não é pública: criando a cobrança sem back_urls e "
            "sem webhook. Use um túnel (ngrok) para testar o retorno automático.",
            base,
        )

    try:
        resp = requests.post(
            f"{API_URL}/checkout/preferences",
            json=dados,
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PagamentoErro(f"Erro de rede ao criar a cobrança: {exc}") from exc

    if resp.status_code not in (200, 201):
        logger.error("Mercado Pago recusou a preferência: %s %s", resp.status_code, resp.text)
        raise PagamentoErro("O Mercado Pago recusou a criação da cobrança.")

    # Mesmo em testes, o link recomendado é o init_point
    return resp.json()["init_point"]


def buscar_pagamento(payment_id):
    """Consulta um pagamento pelo ID direto na API (fonte da verdade)."""
    try:
        resp = requests.get(
            f"{API_URL}/v1/payments/{payment_id}",
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PagamentoErro(f"Erro de rede ao consultar o pagamento: {exc}") from exc

    if resp.status_code != 200:
        logger.error("Falha ao consultar pagamento %s: %s %s", payment_id, resp.status_code, resp.text)
        raise PagamentoErro("Não foi possível consultar o pagamento.")
    return resp.json()


def buscar_pagamentos_da_mensalidade(mensalidade):
    """Lista os pagamentos ligados à mensalidade (mais recentes primeiro).

    Serve para o botão "Já paguei? Atualizar", que funciona até em ambiente
    local, onde o Mercado Pago não consegue chamar o webhook.
    """
    try:
        resp = requests.get(
            f"{API_URL}/v1/payments/search",
            params={
                "external_reference": str(mensalidade.pk),
                "sort": "date_created",
                "criteria": "desc",
            },
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PagamentoErro(f"Erro de rede ao buscar pagamentos: {exc}") from exc

    if resp.status_code != 200:
        logger.error("Falha na busca de pagamentos: %s %s", resp.status_code, resp.text)
        raise PagamentoErro("Não foi possível buscar os pagamentos.")
    return resp.json().get("results", [])


def sincronizar(pagamento):
    """Aplica um pagamento (dict da API) na mensalidade correspondente.

    Só marca como paga se o pagamento estiver aprovado, em reais e com valor
    igual ou maior que o da mensalidade. Devolve a mensalidade (ou None).
    """
    referencia = str(pagamento.get("external_reference") or "")
    if not referencia.isdigit():
        return None

    acabou_de_pagar = False

    with transaction.atomic():
        mensalidade = Mensalidade.objects.select_for_update().filter(pk=int(referencia)).first()
        if mensalidade is None:
            return None

        if pagamento.get("status") == "approved" and mensalidade.status == "Pendente":
            try:
                valor_pago = Decimal(str(pagamento.get("transaction_amount")))
            except (InvalidOperation, TypeError):
                valor_pago = Decimal("0")

            if pagamento.get("currency_id") == "BRL" and valor_pago >= mensalidade.valor:
                mensalidade.status = "Paga"
                mensalidade.data_pagamento = timezone.localdate()
                mensalidade.mp_payment_id = str(pagamento.get("id", ""))
                mensalidade.save(update_fields=["status", "data_pagamento", "mp_payment_id"])
                acabou_de_pagar = True
            else:
                logger.warning(
                    "Pagamento %s aprovado, mas moeda/valor não conferem com a mensalidade %s.",
                    pagamento.get("id"),
                    mensalidade.pk,
                )

    if acabou_de_pagar:
        _enviar_comprovante(mensalidade)

    return mensalidade


def _enviar_comprovante(mensalidade):
    usuario = mensalidade.matricula.aluno.usuario
    if not usuario.email:
        return

    send_mail(
        subject=f"Pagamento confirmado - mensalidade {mensalidade.competencia:%m/%Y}",
        message=(
            f"Olá, {usuario.username}!\n\n"
            f"Recebemos o pagamento da sua mensalidade de {mensalidade.competencia:%m/%Y} "
            f"(R$ {mensalidade.valor}).\n"
            "Obrigado por treinar com a gente!\n"
        ),
        from_email=None,  # usa DEFAULT_FROM_EMAIL
        recipient_list=[usuario.email],
        fail_silently=True,
    )


def assinatura_valida(request):
    """Valida o cabeçalho x-signature do webhook.

    Só é exigida se MERCADOPAGO_WEBHOOK_SECRET estiver configurado (a chave
    secreta fica em "Suas integrações > Webhooks" no painel do Mercado Pago).
    """
    segredo = getattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", "")
    if not segredo:
        return True

    assinatura = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    data_id = request.GET.get("data.id", "")

    partes = {}
    for trecho in assinatura.split(","):
        if "=" in trecho:
            chave, valor = trecho.split("=", 1)
            partes[chave.strip()] = valor.strip()

    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1 or not data_id:
        return False

    # IDs alfanuméricos devem ir em minúsculas no manifesto
    manifesto = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
