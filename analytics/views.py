import re

import anyio
from django.db import DatabaseError, connection
from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import mark_safe

from . import servicos

NOMES_MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]
NOMES_DIAS = [
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
]


def formatar_inteiro(valor):
    """Formata inteiros no padrão brasileiro (99.441)."""
    return f"{valor:,}".replace(",", ".")


def formatar_reais(valor):
    """Formata valores monetários no padrão brasileiro (16.008.872,12)."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor):
    """Percentual com sinal e uma casa (+52,1%), sem "-0,0%"."""
    valor = round(valor, 1)
    if valor == 0:
        valor = abs(valor)
    sinal = "+" if valor > 0 else ""
    return (
        f"{sinal}{valor:,.1f}"
        .replace(",", "X").replace(".", ",").replace("X", ".")
        + "%"
    )


def formatar_indice(valor):
    """Índices e pontuações com duas casas (1,35)."""
    return f"{valor:.2f}".replace(".", ",")


def listar_dias(posicoes):
    """Nomes dos dias da semana, indicando empate quando houver mais de um."""
    nomes = [NOMES_DIAS[d] for d in posicoes]
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1] + " (empate)"


def obter_indicadores():
    """Indicadores gerais dos pedidos e pagamentos do Olist.

    Usa as mesmas consultas da ferramenta MCP consultar_indicadores
    (server.py), para que o dashboard e o assistente mostrem os mesmos
    números.
    """
    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total_pedidos,
                COUNT(*) FILTER (
                    WHERE order_status = 'delivered'
                ) AS pedidos_entregues,
                COUNT(*) FILTER (
                    WHERE order_status = 'canceled'
                ) AS pedidos_cancelados
            FROM stg_olist_orders
        """)
        total, entregues, cancelados = cur.fetchone()

        cur.execute("""
            SELECT ROUND(SUM(valor_total_pago)::numeric, 2)
            FROM fato_pagamentos
        """)
        total_pago = cur.fetchone()[0]

    return {
        "total_pedidos": total,
        "pedidos_entregues": entregues,
        "pedidos_cancelados": cancelados,
        "outros_status": total - entregues - cancelados,
        "total_pago": total_pago,
    }


def obter_faturamento_por_categoria():
    """Top 10 categorias por faturamento (soma de valor_item).

    O ranking (subconsulta) é a mesma consulta da ferramenta MCP
    consultar_faturamento_por_categoria (server.py): agrupa pela
    categoria em inglês, com o nome em português como alternativa, todos
    os status de pedido. Depois, só para exibição, busca o nome original
    em português na tabela de tradução; sem tradução, mantém o nome do
    ranking.
    """
    with connection.cursor() as cur:
        cur.execute("""
            WITH ranking AS (
                SELECT
                    COALESCE(
                        categoria_ingles,
                        product_category_name,
                        'Sem categoria'
                    ) AS categoria,
                    ROUND(SUM(valor_item)::numeric, 2) AS faturamento,
                    ROUND(SUM(valor_frete)::numeric, 2) AS frete,
                    ROUND(SUM(valor_total_item)::numeric, 2) AS total,
                    COUNT(*) AS itens,
                    COUNT(DISTINCT order_id) AS pedidos
                FROM fato_vendas
                GROUP BY 1
                ORDER BY faturamento DESC
                LIMIT 10
            )
            SELECT
                r.categoria,
                COALESCE(t.product_category_name, r.categoria)
                    AS categoria_portugues,
                r.faturamento,
                r.frete,
                r.total,
                r.itens,
                r.pedidos
            FROM ranking r
            LEFT JOIN stg_olist_categories t
                ON t.product_category_name_english = r.categoria
            ORDER BY r.faturamento DESC
        """)
        colunas = [coluna.name for coluna in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def obter_evolucao_mensal():
    """Série mensal de vendas, incluindo meses sem vendas (com zero).

    Mesma consulta da ferramenta MCP consultar_evolucao_mensal (server.py).
    """
    with connection.cursor() as cur:
        cur.execute("""
            WITH mensal AS (
                SELECT
                    DATE_TRUNC('month', data_pedido)::date AS mes,
                    COALESCE(SUM(valor_item), 0) AS faturamento,
                    COALESCE(SUM(valor_frete), 0) AS frete,
                    COALESCE(SUM(valor_total_item), 0) AS total,
                    COUNT(DISTINCT order_id) AS pedidos,
                    COUNT(order_item_id) AS itens
                FROM fato_vendas
                WHERE data_pedido IS NOT NULL
                GROUP BY 1
            ),
            calendario AS (
                SELECT generate_series(
                    MIN(mes), MAX(mes), INTERVAL '1 month'
                )::date AS mes
                FROM mensal
            ),
            completo AS (
                SELECT
                    c.mes,
                    COALESCE(m.faturamento, 0) AS faturamento,
                    COALESCE(m.frete, 0) AS frete,
                    COALESCE(m.total, 0) AS total,
                    COALESCE(m.pedidos, 0) AS pedidos,
                    COALESCE(m.itens, 0) AS itens
                FROM calendario c
                LEFT JOIN mensal m ON m.mes = c.mes
            )
            SELECT
                mes,
                faturamento,
                frete,
                total,
                pedidos,
                itens,
                faturamento / NULLIF(pedidos, 0) AS ticket_medio,
                LAG(faturamento) OVER (ORDER BY mes)
                    AS faturamento_anterior
            FROM completo
            ORDER BY mes
        """)
        colunas = [coluna.name for coluna in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def calcular_variacao(faturamento, faturamento_anterior):
    """Variação em relação ao mês anterior, com as mesmas regras da
    ferramenta MCP consultar_evolucao_mensal.

    Retorna (valor, texto). O valor é None quando não há base válida
    para comparação, e o texto explica o motivo.
    """
    if faturamento_anterior is None:
        return None, "sem mês anterior para comparar"
    if faturamento_anterior == 0:
        return None, "sem faturamento no mês anterior"

    variacao = round(
        (faturamento - faturamento_anterior) * 100 / faturamento_anterior, 1
    )
    if variacao == 0:
        variacao = abs(variacao)
    sinal = "+" if variacao > 0 else ""
    texto = (
        f"{sinal}{variacao:,.1f}"
        .replace(",", "X").replace(".", ",").replace("X", ".")
        + "%"
    )
    return variacao, texto


def inicio(request):
    """Página inicial: cards de indicadores e gráfico de status."""
    contexto = {"indicadores": None, "erro": None}

    try:
        dados = obter_indicadores()
    except DatabaseError as erro:
        contexto["erro"] = str(erro)
        return render(request, "analytics/inicio.html", contexto)

    total = dados["total_pedidos"]

    def percentual(parte):
        if not total:
            return "0,0%"
        return f"{parte * 100 / total:.1f}%".replace(".", ",")

    contexto["indicadores"] = {
        "total_pedidos": formatar_inteiro(total),
        "pedidos_entregues": formatar_inteiro(dados["pedidos_entregues"]),
        "pedidos_cancelados": formatar_inteiro(dados["pedidos_cancelados"]),
        "percentual_entregues": percentual(dados["pedidos_entregues"]),
        "percentual_cancelados": percentual(dados["pedidos_cancelados"]),
        "total_pago": (
            formatar_reais(dados["total_pago"])
            if dados["total_pago"] is not None else None
        ),
    }

    # Dados do gráfico enviados ao JavaScript com json_script.
    contexto["grafico_status"] = {
        "rotulos": ["Entregues", "Cancelados", "Outros status"],
        "valores": [
            dados["pedidos_entregues"],
            dados["pedidos_cancelados"],
            dados["outros_status"],
        ],
    }

    return render(request, "analytics/inicio.html", contexto)


def categorias(request):
    """Ranking das 10 categorias com maior faturamento."""
    contexto = {"ranking": None, "erro": None}

    try:
        dados = obter_faturamento_por_categoria()
    except DatabaseError as erro:
        contexto["erro"] = str(erro)
        return render(request, "analytics/categorias.html", contexto)

    contexto["ranking"] = [
        {
            "posicao": posicao,
            "categoria": linha["categoria_portugues"],
            # Nome usado pela ferramenta MCP, exibido como referência.
            "categoria_mcp": (
                linha["categoria"]
                if linha["categoria"] != linha["categoria_portugues"] else None
            ),
            "faturamento": formatar_reais(linha["faturamento"]),
            "frete": formatar_reais(linha["frete"]),
            "total": formatar_reais(linha["total"]),
            "itens": formatar_inteiro(linha["itens"]),
            "pedidos": formatar_inteiro(linha["pedidos"]),
        }
        for posicao, linha in enumerate(dados, start=1)
    ]

    # Valores numéricos para o gráfico (Decimal vira float para o JSON).
    contexto["grafico_categorias"] = {
        "rotulos": [linha["categoria_portugues"] for linha in dados],
        "faturamento": [float(linha["faturamento"]) for linha in dados],
        "frete": [float(linha["frete"]) for linha in dados],
    }

    return render(request, "analytics/categorias.html", contexto)


def evolucao(request):
    """Evolução mensal: gráfico de linha, resumo do período e histórico."""
    contexto = {"meses": None, "erro": None}

    try:
        dados = obter_evolucao_mensal()
    except DatabaseError as erro:
        contexto["erro"] = str(erro)
        return render(request, "analytics/evolucao.html", contexto)

    meses = []
    for linha in dados:
        variacao, texto_variacao = calcular_variacao(
            linha["faturamento"], linha["faturamento_anterior"]
        )
        if variacao is None:
            classe_variacao = "neutra"
        elif variacao > 0:
            classe_variacao = "positiva"
        elif variacao < 0:
            classe_variacao = "negativa"
        else:
            classe_variacao = "neutra"

        meses.append({
            "mes": f"{linha['mes']:%m/%Y}",
            "faturamento": formatar_reais(linha["faturamento"]),
            "frete": formatar_reais(linha["frete"]),
            "total": formatar_reais(linha["total"]),
            "pedidos": formatar_inteiro(linha["pedidos"]),
            "itens": formatar_inteiro(linha["itens"]),
            "ticket_medio": (
                f"R$ {formatar_reais(linha['ticket_medio'])}"
                if linha["ticket_medio"] is not None else "não disponível"
            ),
            "sem_vendas": linha["pedidos"] == 0,
            "variacao": texto_variacao,
            "classe_variacao": classe_variacao,
        })
    contexto["meses"] = meses

    if dados:
        faturamento_periodo = sum(linha["faturamento"] for linha in dados)
        pedidos_periodo = sum(linha["pedidos"] for linha in dados)
        contexto["resumo"] = {
            "periodo": f"{meses[0]['mes']} a {meses[-1]['mes']}",
            "quantidade_meses": len(dados),
            "meses_sem_vendas": sum(1 for m in meses if m["sem_vendas"]),
            "faturamento": formatar_reais(faturamento_periodo),
            "pedidos": formatar_inteiro(pedidos_periodo),
            "ticket_medio": (
                formatar_reais(faturamento_periodo / pedidos_periodo)
                if pedidos_periodo else None
            ),
        }

        # Valores numéricos para o gráfico; a variação vai junto para a
        # dica (null quando não há base de comparação).
        contexto["grafico_evolucao"] = {
            "rotulos": [m["mes"] for m in meses],
            "faturamento": [float(linha["faturamento"]) for linha in dados],
            "pedidos": [linha["pedidos"] for linha in dados],
            "variacao": [m["variacao"] for m in meses],
        }

    return render(request, "analytics/evolucao.html", contexto)


def tendencias(request):
    """Tendências: mesmos cálculos da ferramenta analisar_tendencias_vendas
    (analytics/servicos.py)."""
    contexto = {"dados": None, "erro": None}

    try:
        with connection.cursor() as cur:
            dados = servicos.analisar_tendencias(cur)
    except DatabaseError as erro:
        contexto["erro"] = str(erro)
        return render(request, "analytics/tendencias.html", contexto)

    contexto["dados"] = dados
    if dados["vazio"]:
        return render(request, "analytics/tendencias.html", contexto)

    contexto["incompletos"] = [
        {
            "mes": f"{mes:%m/%Y}",
            "motivo": (
                f"dados a partir de {dados['primeira_data']:%d/%m/%Y}"
                if lado == "inicio"
                else f"dados até {dados['ultima_data']:%d/%m/%Y}"
            ),
            "faturamento": formatar_reais(faturamento),
        }
        for mes, faturamento, lado in dados["incompletos"]
    ]
    contexto["base"] = {
        "primeira_data": f"{dados['primeira_data']:%d/%m/%Y}",
        "ultima_data": f"{dados['ultima_data']:%d/%m/%Y}",
        "total_meses": len(dados["meses"]),
        "completos": len(dados["completos"]),
        "sem_venda": ", ".join(f"{m:%m/%Y}" for m in dados["meses_sem_venda"]),
    }

    if not dados["suficiente"]:
        return render(request, "analytics/tendencias.html", contexto)

    rotulos = dados["rotulos"]
    faturamentos = dados["faturamentos"]
    medias_moveis = dict(dados["medias_moveis"])
    anomalias = dados["anomalias"]

    # Informações da variação de cada mês, indexadas pelo rótulo.
    variacao_por_mes = {}
    if anomalias:
        for rotulo, v, classe, pontuacao, e_anomalia in anomalias["itens"]:
            variacao_por_mes[rotulo] = (v, classe, pontuacao, e_anomalia)
    else:
        for rotulo, v in dados["variacoes"]:
            variacao_por_mes[rotulo] = (v, servicos.classificar(v), None, False)

    insuficiente_por_mes = {}
    for rotulo, rotulo_anterior, anterior in dados["insuficientes"]:
        if anterior <= 0:
            insuficiente_por_mes[rotulo] = (
                f"mês anterior sem faturamento ({rotulo_anterior}: "
                f"R$ {formatar_reais(anterior)})"
            )
        else:
            insuficiente_por_mes[rotulo] = (
                "faturamento do mês anterior abaixo do limite de base "
                f"mínima ({rotulo_anterior}: R$ {formatar_reais(anterior)}; "
                f"limite: R$ {formatar_reais(dados['limite_base'])})"
            )

    linhas = []
    for i, rotulo in enumerate(rotulos):
        linha = {
            "mes": rotulo,
            "faturamento": formatar_reais(faturamentos[i]),
            "media_movel": (
                formatar_reais(medias_moveis[rotulo])
                if rotulo in medias_moveis else None
            ),
            "situacao": "primeiro",
        }
        if rotulo in variacao_por_mes:
            v, classe, pontuacao, e_anomalia = variacao_por_mes[rotulo]
            linha.update({
                "situacao": "valida",
                "variacao": formatar_percentual(v),
                "classe": classe,
                "pontuacao": (
                    formatar_indice(pontuacao) if pontuacao is not None else None
                ),
                "anomalia": e_anomalia,
            })
        elif rotulo in insuficiente_por_mes:
            linha.update({
                "situacao": "insuficiente",
                "motivo": insuficiente_por_mes[rotulo],
            })
        linhas.append(linha)

    contexto.update({
        "resumo": {
            "periodo": f"{rotulos[0]} a {rotulos[-1]}",
            "maior_mes": rotulos[dados["maior"]],
            "maior_valor": formatar_reais(faturamentos[dados["maior"]]),
            "menor_mes": rotulos[dados["menor"]],
            "menor_valor": formatar_reais(faturamentos[dados["menor"]]),
            "media": formatar_reais(dados["media"]),
            "amostra_pequena": len(dados["completos"]) <= 3,
        },
        "contagens": {
            "validas": len(dados["variacoes"]),
            "crescimento": dados["crescimento"],
            "queda": dados["queda"],
            "estavel": dados["estavel"],
            "insuficientes": len(dados["insuficientes"]),
        },
        "anomalias": (
            {
                "mediana": formatar_percentual(anomalias["mediana"]),
                "mad": formatar_reais(anomalias["mad"]),
                "mad_zero": anomalias["mad"] == 0,
                "lista": [l for l in linhas if l.get("anomalia")],
            }
            if anomalias else None
        ),
        "linhas": linhas,
        "grafico_tendencias": {
            "rotulos": rotulos,
            "faturamento": faturamentos,
            "media_movel": [medias_moveis.get(r) for r in rotulos],
            "anomalia": [bool(l.get("anomalia")) for l in linhas],
        },
    })
    return render(request, "analytics/tendencias.html", contexto)


def sazonalidade(request):
    """Sazonalidade: mesmos cálculos da ferramenta
    analisar_sazonalidade_vendas (analytics/servicos.py)."""
    contexto = {"dados": None, "erro": None}

    try:
        with connection.cursor() as cur:
            dados = servicos.analisar_sazonalidade(cur)
    except DatabaseError as erro:
        contexto["erro"] = str(erro)
        return render(request, "analytics/sazonalidade.html", contexto)

    contexto["dados"] = dados
    if dados["vazio"] or not dados["meses_completos"]:
        return render(request, "analytics/sazonalidade.html", contexto)

    situacao = dados["situacao"]
    anos = dados["anos"]
    indices = dados["indices"]
    medias_indice = dados["medias_indice"]
    fator = dados["fator"]

    # Matriz mês do ano x ano (faturamento médio por dia).
    matriz = []
    for m in range(1, 13):
        celulas = []
        for ano in anos:
            if (ano, m) not in situacao:
                celulas.append({"texto": "—", "classe": "vazia"})
                continue
            estado, por_dia, _ = situacao[(ano, m)]
            if estado == "válido":
                celulas.append({
                    "texto": f"R$ {formatar_reais(por_dia)}",
                    "indice": (
                        formatar_indice(indices[(ano, m)])
                        if (ano, m) in indices else None
                    ),
                    "classe": "valida",
                })
            elif estado == "base insuficiente":
                celulas.append({
                    "texto": f"R$ {formatar_reais(por_dia)}",
                    "nota": "base insuficiente",
                    "classe": "insuficiente",
                })
            else:
                celulas.append({"texto": "incompleto", "classe": "incompleta"})
        matriz.append({"mes": NOMES_MESES[m - 1], "celulas": celulas})

    indices_mensais = []
    for m in range(1, 13):
        if m not in medias_indice:
            indices_mensais.append({"mes": NOMES_MESES[m - 1], "sem_indice": True})
            continue
        media_m, quantidade, acima = medias_indice[m]
        if quantidade == 1:
            confianca = "1 observação: sem comparação"
        elif quantidade == 2:
            confianca = "2 observações: indicativo"
        else:
            confianca = f"{quantidade} observações: comparável"
        indices_mensais.append({
            "mes": NOMES_MESES[m - 1],
            "indice": formatar_indice(media_m),
            "normalizado": (
                formatar_indice(media_m * fator) if fator is not None else None
            ),
            "confianca": confianca,
            "acima": f"{acima} de {quantidade}",
            "classe": "acima" if round(media_m, 2) > 1 else (
                "abaixo" if round(media_m, 2) < 1 else "neutro"
            ),
        })

    resumo = dados["resumo_indices"]
    resumo_indices = None
    if resumo:
        maior, menor = resumo["maior"], resumo["menor"]
        resumo_indices = {
            "maior": f"{NOMES_MESES[maior - 1]} ({formatar_indice(medias_indice[maior][0])})",
            "menor": f"{NOMES_MESES[menor - 1]} ({formatar_indice(medias_indice[menor][0])})",
            "amplitude": (
                formatar_indice(medias_indice[maior][0] / medias_indice[menor][0])
                if medias_indice[menor][0] > 0 else None
            ),
            "coeficiente": (
                f"{resumo['desvio'] / resumo['media'] * 100:.1f}".replace(".", ",") + "%"
                if resumo["media"] > 0 else None
            ),
            "parcial": len(medias_indice) < 12,
            "quantidade": len(medias_indice),
        }

    chaves = sorted(indices)
    variacoes_anuais = [
        {
            "rotulo": f"{NOMES_MESES[m - 1]} {ano} vs {ano - 1}",
            "variacao": formatar_percentual(v),
            "classe": servicos.classificar(v),
        }
        for ano, m, v in dados["variacoes_anuais"]
    ]
    insuficientes_anuais = [
        {
            "rotulo": f"{NOMES_MESES[m - 1]} {ano} vs {ano - 1}",
            "motivo": (
                "mesmo mês do ano anterior sem faturamento"
                if anterior <= 0
                else "faturamento do mesmo mês do ano anterior abaixo do "
                f"limite de base mínima (R$ {formatar_reais(anterior)})"
            ),
        }
        for ano, m, anterior in dados["insuficientes_anuais"]
    ]

    # Padrão semanal, com as mesmas regras de tolerância e empate da
    # ferramenta MCP.
    semanal = dados["semanal"]
    contexto_semanal = {
        "semanas": semanal["semanas"],
        "validas": semanal["semanas_validas"],
        "insuficientes": semanal["semanas"] - semanal["semanas_validas"],
        "suficiente": semanal["suficiente"],
    }
    if semanal["suficiente"]:
        total = semanal["total_semanas"]
        contexto_semanal["dias"] = [
            {
                "nome": NOMES_DIAS[d],
                "media": formatar_reais(dia["media"]),
                "mediana": formatar_reais(dia["mediana"]),
                "mad": formatar_reais(dia["mad"]),
                "pedidos": formatar_reais(dia["pedidos"]),
                "indice": formatar_indice(dia["indice"]),
                "acima": f"{dia['acima_media']} de {total}",
                "classe": "acima" if round(dia["indice"], 2) > 1 else (
                    "abaixo" if round(dia["indice"], 2) < 1 else "neutro"
                ),
            }
            for d, dia in enumerate(semanal["dias"])
        ]
        contexto_semanal["conclusoes"] = [
            _conclusao_semanal(
                semanal["faturamento"], "faturamento médio",
                "de maior ou menor faturamento", "R$ ",
                "Maior faturamento médio", "Menor faturamento médio",
            ),
            _conclusao_semanal(
                semanal["pedidos"], "quantidade média de pedidos",
                "de mais ou menos pedidos", "",
                "Mais pedidos por dia", "Menos pedidos por dia",
            ),
        ]
        contexto_semanal["grafico"] = {
            "rotulos": NOMES_DIAS,
            "faturamento": [dia["media"] for dia in semanal["dias"]],
            "pedidos": [dia["pedidos"] for dia in semanal["dias"]],
        }

    contexto.update({
        "base": {
            "primeira_data": f"{dados['primeira_data']:%d/%m/%Y}",
            "ultima_data": f"{dados['ultima_data']:%d/%m/%Y}",
            "completos": dados["meses_completos"],
            "incompletos": dados["total_meses"] - dados["meses_completos"],
            "anos_civis": ", ".join(str(a) for a in dados["anos_civis_completos"]) or "nenhum",
            "quantidade_anos_civis": len(dados["anos_civis_completos"]),
            "limite_base": formatar_reais(dados["limite_base"]),
            "meses_com_indice": len(indices),
            "periodo_indices": (
                f"{chaves[0][1]:02d}/{chaves[0][0]} a {chaves[-1][1]:02d}/{chaves[-1][0]}"
                if chaves else None
            ),
        },
        "anos": anos,
        "matriz": matriz,
        "indices_mensais": indices_mensais,
        "normalizado": fator is not None,
        "resumo_indices": resumo_indices,
        "variacoes_anuais": variacoes_anuais,
        "insuficientes_anuais": insuficientes_anuais,
        "nao_comparaveis": dados["nao_comparaveis"],
        "crescimento_anual": dados["crescimento_anual"],
        "queda_anual": dados["queda_anual"],
        "semanal": contexto_semanal,
        # Os 12 meses aparecem no gráfico; meses sem índice ficam vazios
        # (null) para não esconder a lacuna.
        "grafico_indices": {
            "rotulos": NOMES_MESES if medias_indice else [],
            "indices": [
                medias_indice[m][0] if m in medias_indice else None
                for m in range(1, 13)
            ] if medias_indice else [],
        },
    })
    return render(request, "analytics/sazonalidade.html", contexto)


def _conclusao_semanal(dados, medida, destaque, prefixo, rotulo_maior, rotulo_menor):
    """Texto da comparação entre dias com a tolerância de 1%."""
    diferenca = (
        f"Diferença entre o maior e o menor valor de {medida}: "
        f"{prefixo}{formatar_reais(dados['diferenca'])} · limite de "
        f"tolerância: {prefixo}{formatar_reais(dados['tolerancia'])} "
        "(1% da média dos 7 dias)"
    )
    if round(dados["diferenca"], 2) == 0:
        return {
            "diferenca": diferenca,
            "texto": f"Todos os dias da semana têm a mesma {medida}: "
                     "não há diferença entre eles.",
        }
    if dados["diferenca"] < dados["tolerancia"]:
        return {
            "diferenca": diferenca,
            "texto": "Diferença inferior ao limite de 1%: nenhum dia é "
                     f"destacado como {destaque}.",
        }
    conclusao = {
        "diferenca": diferenca,
        "maior": f"{rotulo_maior}: {listar_dias(dados['dias_maior'])} "
                 f"({prefixo}{formatar_reais(dados['maior'])})",
        "menor": f"{rotulo_menor}: {listar_dias(dados['dias_menor'])} "
                 f"({prefixo}{formatar_reais(dados['menor'])})",
    }
    if prefixo and dados["menor"] > 0:
        conclusao["percentual"] = formatar_percentual(
            (dados["maior"] / dados["menor"] - 1) * 100
        )
    return conclusao


def formatar_resposta(texto):
    """Converte o markdown simples da resposta do Gemini em HTML seguro.

    O texto é escapado antes; só títulos (#), listas (- ou *) e negrito
    (**) viram HTML.
    """
    html = []
    em_lista = False
    for linha in texto.splitlines():
        linha = escape(linha.strip())
        linha = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", linha)

        item = re.match(r"^[-*]\s+(.*)", linha)
        if item and not em_lista:
            html.append("<ul>")
            em_lista = True
        elif not item and em_lista:
            html.append("</ul>")
            em_lista = False

        titulo = re.match(r"^#{1,6}\s+(.*)", linha)
        if titulo:
            html.append(f"<h3>{titulo.group(1)}</h3>")
        elif item:
            html.append(f"<li>{item.group(1)}</li>")
        elif linha:
            html.append(f"<p>{linha}</p>")
    if em_lista:
        html.append("</ul>")
    return mark_safe("\n".join(html))


def assistente(request):
    """Pergunta e resposta com o assistente (Gemini + ferramentas MCP).

    Cada pergunta é independente. A chamada ao Gemini só acontece no envio
    do formulário (POST).
    """
    contexto = {"pergunta": "", "resposta": None, "erro": None}

    if request.method == "POST":
        pergunta = request.POST.get("pergunta", "").strip()
        contexto["pergunta"] = pergunta

        if not pergunta:
            contexto["erro"] = "Digite uma pergunta antes de enviar."
        elif len(pergunta) > 500:
            contexto["erro"] = "A pergunta deve ter no máximo 500 caracteres."
        else:
            # Importado aqui para não carregar o cliente do Gemini nas
            # demais páginas.
            from .assistente_ia import responder

            try:
                resposta = anyio.run(responder, pergunta)
                contexto["resposta"] = formatar_resposta(resposta)
            except Exception as erro:
                mensagem = str(erro)
                if "429" in mensagem or "RESOURCE_EXHAUSTED" in mensagem:
                    contexto["erro"] = (
                        "A cota diária gratuita do Gemini foi atingida. "
                        "Tente novamente mais tarde."
                    )
                else:
                    contexto["erro"] = f"Não foi possível obter a resposta: {mensagem}"

    return render(request, "analytics/assistente.html", contexto)
