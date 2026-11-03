"""Cálculos de tendências e sazonalidade de vendas do Olist.

Usado pelas ferramentas MCP (server.py) e pelas páginas do Django, para
que o assistente e o site mostrem exatamente os mesmos números. As
funções recebem um cursor de banco (psycopg ou django.db.connection) e
devolvem dados; a formatação em texto ou HTML fica com quem chama.

Este módulo não importa o Django, porque o server.py roda fora dele.
"""

SQL_LIMITES = """
    SELECT
        MIN(data_pedido),
        MAX(data_pedido),
        MIN(data_pedido)
            = DATE_TRUNC('month', MIN(data_pedido))::date,
        MAX(data_pedido)
            = (
                DATE_TRUNC('month', MAX(data_pedido))
                + INTERVAL '1 month - 1 day'
            )::date
    FROM fato_vendas
"""


def mediana(valores):
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / 2


def classificar(variacao):
    """Crescimento, queda ou estável, pela variação arredondada a 0,1%."""
    if round(variacao, 1) > 0:
        return "crescimento"
    if round(variacao, 1) < 0:
        return "queda"
    return "estável"


def limites_meses_completos(meses, primeiro_mes_completo, ultimo_mes_completo):
    """Índices do primeiro e do último mês completo da série.

    O primeiro mês só é completo se a base começa no dia 1, e o último só
    se termina no último dia do mês. Os meses entre eles são sempre
    completos, mesmo sem vendas.
    """
    inicio = 0 if primeiro_mes_completo else 1
    fim = len(meses) - 1 if ultimo_mes_completo else len(meses) - 2
    return inicio, fim


# ---------------------------------------------------------------------------
# Tendências
# ---------------------------------------------------------------------------

def analisar_tendencias(cur):
    """Tendências do faturamento mensal (SUM de valor_item).

    Usa apenas meses completos nas comparações; variações sobre base
    insuficiente (mês anterior abaixo de 1% da média) ficam fora da
    classificação e das anomalias (Modified Z-Score com mediana e MAD).
    """
    cur.execute(SQL_LIMITES)
    (
        primeira_data, ultima_data,
        primeiro_mes_completo, ultimo_mes_completo
    ) = cur.fetchone()

    cur.execute("""
        WITH mensal AS (
            SELECT
                DATE_TRUNC('month', data_pedido)::date AS mes,
                COALESCE(SUM(valor_item), 0) AS faturamento
            FROM fato_vendas
            WHERE data_pedido IS NOT NULL
            GROUP BY 1
        ),
        calendario AS (
            SELECT generate_series(
                MIN(mes), MAX(mes), INTERVAL '1 month'
            )::date AS mes
            FROM mensal
        )
        SELECT
            c.mes,
            COALESCE(m.faturamento, 0) AS faturamento
        FROM calendario c
        LEFT JOIN mensal m ON m.mes = c.mes
        ORDER BY c.mes
    """)
    meses = cur.fetchall()

    if not meses:
        return {"vazio": True}

    inicio, fim = limites_meses_completos(
        meses, primeiro_mes_completo, ultimo_mes_completo
    )

    completos = meses[inicio:fim + 1]
    incompletos = []
    for i, (mes, faturamento) in enumerate(meses):
        if inicio <= i <= fim:
            continue
        # "inicio": falta o começo do mês; "fim": falta o final.
        lado = "inicio" if i == 0 and not primeiro_mes_completo else "fim"
        incompletos.append((mes, faturamento, lado))

    resultado = {
        "vazio": False,
        "primeira_data": primeira_data,
        "ultima_data": ultima_data,
        "meses": meses,
        "completos": completos,
        "incompletos": incompletos,
        "meses_sem_venda": [m[0] for m in completos if m[1] == 0],
        "suficiente": len(completos) >= 2,
    }

    if not resultado["suficiente"]:
        return resultado

    faturamentos = [float(m[1]) for m in completos]
    rotulos = [f"{m[0]:%m/%Y}" for m in completos]

    maior = max(range(len(completos)), key=lambda i: faturamentos[i])
    menor = min(range(len(completos)), key=lambda i: faturamentos[i])
    media = sum(faturamentos) / len(faturamentos)

    medias_moveis = [
        (rotulos[i], sum(faturamentos[i - 2:i + 1]) / 3)
        for i in range(2, len(completos))
    ]

    # Base insuficiente: mês anterior com faturamento abaixo de 1% da
    # média dos meses completos (inclui meses com faturamento zero, o que
    # também protege a divisão por zero).
    limite_base = media * 0.01

    variacoes = []
    insuficientes = []
    for i in range(1, len(completos)):
        anterior = faturamentos[i - 1]
        if anterior <= 0 or anterior < limite_base:
            insuficientes.append((rotulos[i], rotulos[i - 1], anterior))
        else:
            variacoes.append(
                (rotulos[i], (faturamentos[i] - anterior) * 100 / anterior)
            )

    crescimento = sum(
        1 for _, v in variacoes if classificar(v) == "crescimento"
    )
    queda = sum(1 for _, v in variacoes if classificar(v) == "queda")

    anomalias = None
    if len(variacoes) >= 3:
        valores = [v for _, v in variacoes]
        mediana_var = mediana(valores)
        mad = mediana([abs(v - mediana_var) for v in valores])

        # Para cada variação: (rótulo, variação, classificação,
        # pontuação robusta ou None se MAD = 0, é anomalia?)
        itens = []
        for rotulo, v in variacoes:
            if mad == 0:
                itens.append((rotulo, v, classificar(v), None, False))
                continue
            pontuacao = 0.6745 * (v - mediana_var) / mad
            itens.append(
                (rotulo, v, classificar(v), pontuacao, abs(pontuacao) > 3.5)
            )

        anomalias = {"mediana": mediana_var, "mad": mad, "itens": itens}

    resultado.update({
        "faturamentos": faturamentos,
        "rotulos": rotulos,
        "maior": maior,
        "menor": menor,
        "media": media,
        "medias_moveis": medias_moveis,
        "limite_base": limite_base,
        "variacoes": variacoes,
        "insuficientes": insuficientes,
        "crescimento": crescimento,
        "queda": queda,
        "estavel": len(variacoes) - crescimento - queda,
        "anomalias": anomalias,
    })
    return resultado


# ---------------------------------------------------------------------------
# Sazonalidade
# ---------------------------------------------------------------------------

def _empatados(valores, alvo):
    """Posições (0 = segunda) com o valor alvo, comparando na precisão do
    cálculo e tolerando apenas erro de ponto flutuante."""
    return [
        d for d in range(7)
        if abs(valores[d] - alvo) <= 1e-9 * max(abs(alvo), 1)
    ]


def analisar_sazonalidade(cur):
    """Sazonalidade mensal (índice sobre média móvel centrada de 12 meses),
    variação ano contra ano e padrão por dia da semana."""
    cur.execute(SQL_LIMITES)
    (
        primeira_data, ultima_data,
        primeiro_mes_completo, ultimo_mes_completo
    ) = cur.fetchone()

    cur.execute("""
        WITH mensal AS (
            SELECT
                DATE_TRUNC('month', data_pedido)::date AS mes,
                COALESCE(SUM(valor_item), 0) AS faturamento
            FROM fato_vendas
            WHERE data_pedido IS NOT NULL
            GROUP BY 1
        ),
        calendario AS (
            SELECT generate_series(
                MIN(mes), MAX(mes), INTERVAL '1 month'
            )::date AS mes
            FROM mensal
        )
        SELECT
            c.mes,
            EXTRACT(YEAR FROM c.mes)::int AS ano,
            EXTRACT(MONTH FROM c.mes)::int AS mes_do_ano,
            EXTRACT(
                DAY FROM c.mes + INTERVAL '1 month - 1 day'
            )::int AS dias_no_mes,
            COALESCE(m.faturamento, 0) AS faturamento
        FROM calendario c
        LEFT JOIN mensal m ON m.mes = c.mes
        ORDER BY c.mes
    """)
    meses = cur.fetchall()

    if not meses:
        return {"vazio": True}

    inicio, fim = limites_meses_completos(
        meses, primeiro_mes_completo, ultimo_mes_completo
    )
    completos = meses[inicio:fim + 1]

    dias = []
    if completos:
        # Semanas completas (segunda a domingo) dentro do período de
        # meses completos.
        cur.execute("""
            WITH limites AS (
                SELECT
                    %(inicio)s::date AS inicio,
                    (
                        %(fim)s::date
                        + INTERVAL '1 month - 1 day'
                    )::date AS fim
            ),
            semanas AS (
                SELECT
                    inicio
                    + (8 - EXTRACT(ISODOW FROM inicio)::int) %% 7
                        AS inicio_semanas,
                    fim
                    - EXTRACT(ISODOW FROM fim)::int %% 7
                        AS fim_semanas
                FROM limites
            ),
            calendario AS (
                SELECT generate_series(
                    inicio_semanas, fim_semanas, INTERVAL '1 day'
                )::date AS dia
                FROM semanas
            ),
            vendas AS (
                SELECT
                    data_pedido AS dia,
                    COALESCE(SUM(valor_item), 0) AS faturamento,
                    COUNT(DISTINCT order_id) AS pedidos
                FROM fato_vendas
                WHERE data_pedido IS NOT NULL
                GROUP BY 1
            )
            SELECT
                c.dia,
                COALESCE(v.faturamento, 0) AS faturamento,
                COALESCE(v.pedidos, 0) AS pedidos
            FROM calendario c
            LEFT JOIN vendas v ON v.dia = c.dia
            ORDER BY c.dia
        """, {"inicio": completos[0][0], "fim": completos[-1][0]})
        dias = cur.fetchall()

    resultado = {
        "vazio": False,
        "primeira_data": primeira_data,
        "ultima_data": ultima_data,
        "total_meses": len(meses),
        "meses_completos": len(completos),
    }

    if not completos:
        return resultado

    # Classificação de cada mês: incompleto, base insuficiente ou válido.
    media_mensal = (
        sum(float(m[4]) for m in completos) / len(completos)
    )
    limite_base = media_mensal * 0.01

    # (ano, mês do ano) -> (estado, faturamento por dia, faturamento)
    situacao = {}
    for i, (mes, ano, mes_do_ano, dias_no_mes, faturamento) in enumerate(
        meses
    ):
        faturamento = float(faturamento)
        if not inicio <= i <= fim:
            estado = "incompleto"
        elif faturamento <= 0 or faturamento < limite_base:
            estado = "base insuficiente"
        else:
            estado = "válido"
        situacao[(ano, mes_do_ano)] = (
            estado, faturamento / dias_no_mes, faturamento
        )

    anos = sorted({ano for ano, _ in situacao})
    anos_civis_completos = [
        ano for ano in anos
        if all(
            situacao.get((ano, m), ("ausente",))[0] != "ausente"
            and situacao[(ano, m)][0] != "incompleto"
            for m in range(1, 13)
        )
    ]

    # Tendência: média móvel centrada de 12 meses (2x12) do faturamento
    # por dia. Para o mês t, é a média de duas médias móveis de 12 meses
    # (t-6 a t+5 e t-5 a t+6). Só usa janelas em que os 13 meses são
    # válidos (completos e acima da base mínima).
    serie = [
        (ano, mes_do_ano, situacao[(ano, mes_do_ano)])
        for _, ano, mes_do_ano, _, _ in meses
    ]
    tendencia = {}
    indices = {}
    for t in range(6, len(serie) - 6):
        janela = serie[t - 6:t + 7]
        if any(dados[0] != "válido" for _, _, dados in janela):
            continue
        valores = [dados[1] for _, _, dados in janela]
        media_1 = sum(valores[:12]) / 12
        media_2 = sum(valores[1:]) / 12
        centrada = (media_1 + media_2) / 2
        ano, mes_do_ano, dados = serie[t]
        tendencia[(ano, mes_do_ano)] = centrada
        if centrada > 0:
            indices[(ano, mes_do_ano)] = dados[1] / centrada

    # Mês do ano -> (índice médio, observações, vezes acima de 1,00)
    medias_indice = {}
    for m in range(1, 13):
        observacoes = [
            indices[(ano, m)] for ano in anos if (ano, m) in indices
        ]
        if observacoes:
            medias_indice[m] = (
                sum(observacoes) / len(observacoes),
                len(observacoes),
                sum(1 for v in observacoes if round(v, 2) > 1),
            )

    # Normalização clássica: os 12 índices médios somam 12. Só é possível
    # quando todos os meses do ano têm índice.
    fator = None
    soma_indices = sum(v for v, _, _ in medias_indice.values())
    if len(medias_indice) == 12 and soma_indices > 0:
        fator = 12 / soma_indices

    resumo_indices = None
    if len(medias_indice) >= 2:
        maior = max(medias_indice, key=lambda m: medias_indice[m][0])
        menor = min(medias_indice, key=lambda m: medias_indice[m][0])
        valores_indice = [v for v, _, _ in medias_indice.values()]
        media_indices = sum(valores_indice) / len(valores_indice)
        desvio_indices = (
            sum((v - media_indices) ** 2 for v in valores_indice)
            / len(valores_indice)
        ) ** 0.5
        resumo_indices = {
            "maior": maior,
            "menor": menor,
            "media": media_indices,
            "desvio": desvio_indices,
        }

    # Variação ano contra ano do faturamento por dia do mesmo mês.
    variacoes_anuais = []
    insuficientes_anuais = []
    nao_comparaveis = 0
    for ano in anos[1:]:
        for m in range(1, 13):
            atual = situacao.get((ano, m))
            anterior = situacao.get((ano - 1, m))
            if not atual or not anterior:
                continue
            if atual[0] == "incompleto" or anterior[0] == "incompleto":
                nao_comparaveis += 1
            elif anterior[0] == "base insuficiente":
                insuficientes_anuais.append((ano, m, anterior[2]))
            else:
                variacoes_anuais.append(
                    (ano, m, (atual[1] - anterior[1]) * 100 / anterior[1])
                )

    crescimento_anual = sum(
        1 for *_, v in variacoes_anuais if round(v, 1) > 0
    )
    queda_anual = sum(1 for *_, v in variacoes_anuais if round(v, 1) < 0)

    resultado.update({
        "limite_base": limite_base,
        "situacao": situacao,
        "anos": anos,
        "anos_civis_completos": anos_civis_completos,
        "tendencia": tendencia,
        "indices": indices,
        "medias_indice": medias_indice,
        "fator": fator,
        "resumo_indices": resumo_indices,
        "variacoes_anuais": variacoes_anuais,
        "insuficientes_anuais": insuficientes_anuais,
        "nao_comparaveis": nao_comparaveis,
        "crescimento_anual": crescimento_anual,
        "queda_anual": queda_anual,
        "semanal": _analisar_semanas(dias),
    })
    return resultado


def _analisar_semanas(dias):
    """Padrão por dia da semana em semanas completas, excluindo semanas
    com faturamento abaixo de 1% da média semanal."""
    semanas = [dias[i:i + 7] for i in range(0, len(dias) - 6, 7)]
    totais = [sum(float(d[1]) for d in s) for s in semanas]
    media_semanal = sum(totais) / len(totais) if totais else 0
    limite_semana = media_semanal * 0.01
    semanas_validas = [
        s for s, total in zip(semanas, totais)
        if total > 0 and total >= limite_semana
    ]

    resultado = {
        "semanas": len(semanas),
        "semanas_validas": len(semanas_validas),
        "suficiente": len(semanas_validas) >= 8,
    }
    if not resultado["suficiente"]:
        return resultado

    por_dia = {d: [] for d in range(7)}
    pedidos_dia = {d: [] for d in range(7)}
    acima_media = {d: 0 for d in range(7)}
    for semana in semanas_validas:
        media_da_semana = sum(float(d[1]) for d in semana) / 7
        for posicao, (_, faturamento, pedidos) in enumerate(semana):
            por_dia[posicao].append(float(faturamento))
            pedidos_dia[posicao].append(pedidos)
            if float(faturamento) > media_da_semana:
                acima_media[posicao] += 1

    medias_dia = {d: sum(v) / len(v) for d, v in por_dia.items()}
    media_geral = sum(medias_dia.values()) / 7
    total_semanas = len(semanas_validas)

    # Uma entrada por dia da semana (0 = segunda).
    detalhes = []
    for d in range(7):
        mediana_dia = mediana(por_dia[d])
        detalhes.append({
            "media": medias_dia[d],
            "mediana": mediana_dia,
            "mad": mediana([abs(v - mediana_dia) for v in por_dia[d]]),
            "pedidos": sum(pedidos_dia[d]) / total_semanas,
            "indice": medias_dia[d] / media_geral,
            "acima_media": acima_media[d],
        })

    maior_valor = max(medias_dia.values())
    menor_valor = min(medias_dia.values())
    pedidos_medios = {
        d: sum(v) / total_semanas for d, v in pedidos_dia.items()
    }
    mais_pedidos_valor = max(pedidos_medios.values())
    menos_pedidos_valor = min(pedidos_medios.values())

    resultado.update({
        "total_semanas": total_semanas,
        "dias": detalhes,
        "faturamento": {
            "maior": maior_valor,
            "menor": menor_valor,
            "dias_maior": _empatados(medias_dia, maior_valor),
            "dias_menor": _empatados(medias_dia, menor_valor),
            "diferenca": maior_valor - menor_valor,
            "tolerancia": media_geral * 0.01,
        },
        "pedidos": {
            "maior": mais_pedidos_valor,
            "menor": menos_pedidos_valor,
            "dias_maior": _empatados(pedidos_medios, mais_pedidos_valor),
            "dias_menor": _empatados(pedidos_medios, menos_pedidos_valor),
            "diferenca": mais_pedidos_valor - menos_pedidos_valor,
            "tolerancia": sum(pedidos_medios.values()) / 7 * 0.01,
        },
    })
    return resultado
