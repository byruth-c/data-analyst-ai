
from mcp.server import MCPServer
import os
import psycopg
from dotenv import load_dotenv

from analytics.servicos import analisar_sazonalidade, analisar_tendencias

load_dotenv()

mcp = MCPServer("meu-servidor-mcp")


@mcp.tool()
def somar(a: float, b: float) -> float:
    """Soma dois números."""
    return a + b


@mcp.tool()
def consultar_projeto() -> str:
    """Retorna informações sobre o projeto."""
    return (
        "Data Analyst AI: projeto de análise de dados com Python, "
        "Django, PostgreSQL, Docker e MCP, usando dados públicos do Olist."
    )


@mcp.tool()
def consultar_indicadores() -> str:
    """Retorna indicadores gerais dos pedidos e pagamentos do Olist."""
    load_dotenv(override=True)

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "data_analyst"),
            user=os.getenv("POSTGRES_USER", "analyst"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
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
                pedidos = cur.fetchone()

                cur.execute("""
                    SELECT ROUND(SUM(valor_total_pago)::numeric, 2)
                    FROM fato_pagamentos
                """)
                total_pago = cur.fetchone()[0]

        return (
            f"Total de pedidos: {pedidos[0]:,}\n"
            f"Pedidos entregues: {pedidos[1]:,}\n"
            f"Pedidos cancelados: {pedidos[2]:,}\n"
            f"Total registrado em pagamentos: R$ {total_pago:,.2f}"
        )

    except Exception as erro:
        return f"Não foi possível consultar o banco: {erro}"


@mcp.tool()
def consultar_faturamento_por_categoria() -> str:
    """Retorna as 10 categorias de produto com maior faturamento no Olist,
    com faturamento, frete, total com frete, itens e pedidos, consultados
    no PostgreSQL."""
    load_dotenv(override=True)

    def brl(valor):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def inteiro(valor):
        return f"{valor:,}".replace(",", ".")

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "data_analyst"),
            user=os.getenv("POSTGRES_USER", "analyst"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """)
                categorias = cur.fetchall()

        if not categorias:
            return "Nenhum registro encontrado na tabela fato_vendas."

        linhas = ["Top 10 categorias por faturamento:"]
        for posicao, (
            categoria, faturamento, frete, total, itens, pedidos
        ) in enumerate(categorias, start=1):
            linhas.append(
                f"\n{posicao}. {categoria}\n"
                f"   Faturamento: R$ {brl(faturamento)}\n"
                f"   Frete: R$ {brl(frete)}\n"
                f"   Total com frete: R$ {brl(total)}\n"
                f"   Itens: {inteiro(itens)}\n"
                f"   Pedidos: {inteiro(pedidos)}"
            )

        return "\n".join(linhas)

    except Exception as erro:
        return f"Não foi possível consultar o banco: {erro}"


@mcp.tool()
def consultar_evolucao_mensal() -> str:
    """Retorna a evolução mensal das vendas do Olist: faturamento, frete,
    total com frete, pedidos, itens, ticket médio por pedido e variação
    percentual do faturamento em relação ao mês anterior, consultados no
    PostgreSQL."""
    load_dotenv(override=True)

    def brl(valor):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def inteiro(valor):
        return f"{valor:,}".replace(",", ".")

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "data_analyst"),
            user=os.getenv("POSTGRES_USER", "analyst"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
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
                meses = cur.fetchall()

        if not meses:
            return "Nenhum registro encontrado na tabela fato_vendas."

        linhas = ["Evolução mensal das vendas:"]
        for (
            mes, faturamento, frete, total, pedidos, itens,
            ticket_medio, faturamento_anterior
        ) in meses:
            if faturamento_anterior is None:
                texto_variacao = "sem mês anterior para comparar"
            elif faturamento_anterior == 0:
                texto_variacao = "sem faturamento no mês anterior"
            else:
                variacao = round(
                    (faturamento - faturamento_anterior)
                    * 100 / faturamento_anterior,
                    1,
                )
                if variacao == 0:
                    variacao = abs(variacao)
                sinal = "+" if variacao > 0 else ""
                texto_variacao = (
                    f"{sinal}{variacao:,.1f}"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                    + "%"
                )

            texto_ticket = (
                f"R$ {brl(ticket_medio)}" if ticket_medio is not None
                else "não disponível"
            )

            linhas.append(
                f"\n{mes:%m/%Y}\n"
                f"   Faturamento: R$ {brl(faturamento)}\n"
                f"   Frete: R$ {brl(frete)}\n"
                f"   Total com frete: R$ {brl(total)}\n"
                f"   Pedidos: {inteiro(pedidos)}\n"
                f"   Itens: {inteiro(itens)}\n"
                f"   Ticket médio por pedido: {texto_ticket}\n"
                f"   Variação do faturamento: {texto_variacao}"
            )

        return "\n".join(linhas)

    except Exception as erro:
        return f"Não foi possível consultar o banco: {erro}"


@mcp.tool()
def analisar_tendencias_vendas() -> str:
    """Analisa as tendências do faturamento mensal do Olist (SUM de
    valor_item): maior, menor e média mensal, média móvel de 3 meses,
    meses com crescimento e queda e possíveis anomalias. Sinaliza os meses
    incompletos nas extremidades da base e usa apenas meses completos nas
    comparações de desempenho."""
    load_dotenv(override=True)

    def brl(valor):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def pct(valor):
        valor = round(valor, 1)
        if valor == 0:
            valor = abs(valor)
        sinal = "+" if valor > 0 else ""
        return (
            f"{sinal}{valor:,.1f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
            + "%"
        )

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "data_analyst"),
            user=os.getenv("POSTGRES_USER", "analyst"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                dados = analisar_tendencias(cur)

        if dados["vazio"]:
            return "Nenhum registro encontrado na tabela fato_vendas."

        primeira_data = dados["primeira_data"]
        ultima_data = dados["ultima_data"]
        meses = dados["meses"]
        completos = dados["completos"]
        incompletos = dados["incompletos"]

        linhas = [
            "ANÁLISE DE TENDÊNCIAS DE VENDAS",
            "Faturamento = soma de valor_item (sem frete), "
            "todos os status de pedido.",
            "",
            "== DADOS DA BASE ==",
            f"Primeira data com venda: {primeira_data:%d/%m/%Y}",
            f"Última data com venda: {ultima_data:%d/%m/%Y}",
            f"Primeiro mês: {meses[0][0]:%m/%Y} | "
            f"Último mês: {meses[-1][0]:%m/%Y} | "
            f"Total de meses: {len(meses)}",
            f"Meses completos: {len(completos)} | "
            f"Meses incompletos: {len(incompletos)}",
            "",
            "Meses incompletos nas extremidades (fora das comparações):",
        ]

        if incompletos:
            for mes, faturamento, lado in incompletos:
                if lado == "inicio":
                    motivo = f"dados a partir de {primeira_data:%d/%m/%Y}"
                else:
                    motivo = f"dados até {ultima_data:%d/%m/%Y}"
                linhas.append(
                    f"- {mes:%m/%Y}: {motivo}, "
                    f"faturamento R$ {brl(faturamento)}"
                )
        else:
            linhas.append("- Nenhum")

        if dados["meses_sem_venda"]:
            linhas.append(
                "Meses completos sem vendas (faturamento zero): "
                + ", ".join(f"{m:%m/%Y}" for m in dados["meses_sem_venda"])
            )

        if not dados["suficiente"]:
            linhas.append(
                "\nMeses completos insuficientes para analisar tendências."
            )
            return "\n".join(linhas)

        faturamentos = dados["faturamentos"]
        rotulos = dados["rotulos"]
        maior = dados["maior"]
        menor = dados["menor"]
        limite_base = dados["limite_base"]

        linhas += [
            "",
            f"== CÁLCULOS (somente os {len(completos)} meses completos: "
            f"{rotulos[0]} a {rotulos[-1]}) ==",
            f"Maior faturamento mensal: {rotulos[maior]} - "
            f"R$ {brl(faturamentos[maior])}",
            f"Menor faturamento mensal: {rotulos[menor]} - "
            f"R$ {brl(faturamentos[menor])}",
            f"Média mensal de faturamento: R$ {brl(dados['media'])}",
        ]

        if len(completos) <= 3:
            linhas.append(
                f"ATENÇÃO: apenas {len(completos)} meses completos. A "
                "quantidade de meses é pequena; as tendências abaixo são "
                "apenas descritivas e não devem ser consideradas "
                "conclusões confiáveis."
            )

        if len(completos) >= 3:
            linhas += [
                "",
                "Média móvel de 3 meses (mês atual + 2 anteriores):",
            ]
            for rotulo, media_movel in dados["medias_moveis"]:
                linhas.append(f"- {rotulo}: R$ {brl(media_movel)}")

        linhas += [
            "",
            "Variação em relação ao mês anterior:",
            f"- Variações válidas: {len(dados['variacoes'])}",
            f"   Crescimento: {dados['crescimento']}",
            f"   Queda: {dados['queda']}",
            f"   Estáveis (0,0%): {dados['estavel']}",
            f"- Variações com base insuficiente: {len(dados['insuficientes'])}",
        ]

        for rotulo, rotulo_anterior, anterior in dados["insuficientes"]:
            if anterior <= 0:
                motivo = (
                    f"mês anterior sem faturamento ({rotulo_anterior}: "
                    f"R$ {brl(anterior)})"
                )
            else:
                motivo = (
                    "faturamento do mês anterior abaixo do limite de base "
                    f"mínima ({rotulo_anterior}: R$ {brl(anterior)}; "
                    f"limite: R$ {brl(limite_base)}, 1% da média mensal)"
                )
            linhas.append(
                f"   {rotulo}: base insuficiente - {motivo}; variação "
                "não classificada e fora do cálculo de anomalias"
            )

        linhas += [
            "",
            "== POSSÍVEIS ANOMALIAS ==",
            "Critério: Modified Z-Score = 0,6745 × (variação - mediana) "
            "÷ MAD; possível anomalia quando o valor absoluto é maior "
            "que 3,5. Usa apenas variações válidas.",
        ]

        anomalias = dados["anomalias"]
        if anomalias is None:
            linhas.append("Variações válidas insuficientes para o cálculo.")
        else:
            mad = anomalias["mad"]
            linhas.append(
                f"Mediana das variações: {pct(anomalias['mediana'])} | "
                f"MAD: {brl(mad)} p.p."
            )

            if mad == 0:
                linhas.append(
                    "MAD igual a zero: não foi possível calcular a "
                    "pontuação robusta."
                )

            linhas.append("Classificação das variações válidas:")
            encontradas = []
            for rotulo, v, classe, pontuacao, e_anomalia in anomalias["itens"]:
                if pontuacao is None:
                    linhas.append(f"- {rotulo}: {pct(v)} ({classe})")
                    continue

                texto_pontuacao = f"{pontuacao:.2f}".replace(".", ",")
                marcador = ""
                if e_anomalia:
                    encontradas.append((rotulo, v, texto_pontuacao))
                    marcador = " -> POSSÍVEL ANOMALIA"
                linhas.append(
                    f"- {rotulo}: {pct(v)} ({classe}, "
                    f"pontuação robusta {texto_pontuacao}){marcador}"
                )

            if mad > 0:
                if encontradas:
                    linhas.append("Possíveis anomalias:")
                    for rotulo, v, texto_pontuacao in encontradas:
                        linhas.append(
                            f"- {rotulo}: variação de {pct(v)} "
                            f"(pontuação robusta {texto_pontuacao})"
                        )
                else:
                    linhas.append(
                        "Nenhuma variação com pontuação robusta acima de 3,5."
                    )

        linhas += [
            "",
            "== OBSERVAÇÕES PARA INTERPRETAÇÃO ==",
            "- As anomalias acima são estatísticas: indicam variações "
            "atípicas, não suas causas.",
            "- A base não contém informações sobre campanhas, sazonalidade "
            "ou eventos externos; qualquer explicação para as variações "
            "deve ser tratada como hipótese e confirmada com outras fontes.",
            "- Os meses incompletos não representam o desempenho real do "
            "mês e não devem ser comparados com os demais.",
        ]

        return "\n".join(linhas)

    except Exception as erro:
        return f"Não foi possível consultar o banco: {erro}"


@mcp.tool()
def analisar_sazonalidade_vendas() -> str:
    """Analisa a sazonalidade do faturamento do Olist (SUM de valor_item,
    por data de compra): matriz mês do ano x ano com faturamento por dia,
    índices sazonais mensais, variação ano contra ano e sazonalidade por
    dia da semana. Usa apenas meses completos e sinaliza bases
    insuficientes e amostras pequenas."""
    load_dotenv(override=True)

    nomes_meses = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez",
    ]
    nomes_dias = [
        "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
    ]

    def brl(valor):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def pct(valor):
        valor = round(valor, 1)
        if valor == 0:
            valor = abs(valor)
        sinal = "+" if valor > 0 else ""
        return (
            f"{sinal}{valor:,.1f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
            + "%"
        )

    def indice(valor):
        return f"{valor:.2f}".replace(".", ",")

    def listar(posicoes):
        dias_empatados = [nomes_dias[d] for d in posicoes]
        if len(dias_empatados) == 1:
            return dias_empatados[0]
        return (
            ", ".join(dias_empatados[:-1])
            + " e " + dias_empatados[-1]
            + " (empate)"
        )

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "data_analyst"),
            user=os.getenv("POSTGRES_USER", "analyst"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                dados = analisar_sazonalidade(cur)

        if dados["vazio"]:
            return "Nenhum registro encontrado na tabela fato_vendas."

        linhas = [
            "ANÁLISE DE SAZONALIDADE DE VENDAS",
            "Faturamento = soma de valor_item (sem frete), todos os status "
            "de pedido, pela data de compra.",
            "",
            "== DADOS DA BASE ==",
            f"Primeira data com venda: {dados['primeira_data']:%d/%m/%Y}",
            f"Última data com venda: {dados['ultima_data']:%d/%m/%Y}",
            f"Meses completos: {dados['meses_completos']} | "
            f"Meses incompletos: "
            f"{dados['total_meses'] - dados['meses_completos']}",
        ]

        if not dados["meses_completos"]:
            linhas.append(
                "\nNenhum mês completo: não é possível analisar sazonalidade."
            )
            return "\n".join(linhas)

        situacao = dados["situacao"]
        anos = dados["anos"]
        anos_civis_completos = dados["anos_civis_completos"]
        indices = dados["indices"]
        medias_indice = dados["medias_indice"]
        fator = dados["fator"]

        linhas += [
            "Anos civis completos: "
            + (", ".join(str(a) for a in anos_civis_completos) or "nenhum")
            + f" ({len(anos_civis_completos)})",
            f"Limite de base mínima: R$ {brl(dados['limite_base'])} "
            "(1% da média mensal dos meses completos)",
        ]

        if indices:
            chaves = sorted(indices)
            linhas.append(
                f"Meses com índice sazonal calculado: {len(indices)} "
                f"({chaves[0][1]:02d}/{chaves[0][0]} a "
                f"{chaves[-1][1]:02d}/{chaves[-1][0]})"
            )
        else:
            linhas.append(
                "Meses com índice sazonal calculado: 0 (não há 13 meses "
                "válidos consecutivos para estimar a tendência)"
            )

        if len(anos_civis_completos) < 2:
            linhas.append(
                "ATENÇÃO: menos de 2 ciclos anuais completos. Os índices "
                "sazonais mensais são indicativos e não comprovam "
                "estatisticamente a existência de sazonalidade."
            )

        linhas += [
            "",
            "== MATRIZ MÊS x ANO (faturamento médio por dia) ==",
        ]
        for m in range(1, 13):
            partes = []
            for ano in anos:
                if (ano, m) not in situacao:
                    continue
                estado, por_dia, _ = situacao[(ano, m)]
                if estado == "válido":
                    texto = f"R$ {brl(por_dia)}"
                    if (ano, m) in indices:
                        texto += f" (índice {indice(indices[(ano, m)])})"
                    else:
                        texto += " (sem tendência estimada)"
                elif estado == "base insuficiente":
                    texto = f"base insuficiente (R$ {brl(por_dia)})"
                else:
                    texto = "incompleto"
                partes.append(f"{ano}: {texto}")
            linhas.append(
                f"{nomes_meses[m - 1]} | "
                + (" | ".join(partes) if partes else "sem dados")
            )

        linhas += [
            "",
            "== CÁLCULOS: ÍNDICE SAZONAL MENSAL ==",
            "Tendência = média móvel centrada de 12 meses do faturamento por "
            "dia (média de duas médias móveis de 12 meses consecutivas); "
            "exige 6 meses válidos antes e 6 depois do mês.",
            "Índice = faturamento por dia do mês ÷ tendência estimada no "
            "mês (1,00 = em linha com a tendência).",
        ]

        for m in range(1, 13):
            nome = nomes_meses[m - 1]
            if m not in medias_indice:
                linhas.append(
                    f"- {nome}: sem índice (nenhum mês com tendência estimada)"
                )
                continue

            media_m, quantidade, acima = medias_indice[m]
            if quantidade == 1:
                confianca = "1 observação: sem comparação"
            elif quantidade == 2:
                confianca = "2 observações: indicativo"
            else:
                confianca = f"{quantidade} observações: comparável"

            texto = f"- {nome}: índice médio {indice(media_m)}"
            if fator is not None:
                texto += f" (normalizado {indice(media_m * fator)})"
            linhas.append(
                f"{texto} | {confianca} | acima de 1,00 em {acima} de "
                f"{quantidade}"
            )

        if fator is None:
            linhas.append(
                f"Índices não normalizados: apenas {len(medias_indice)} de 12 "
                "meses do ano têm índice."
            )
        else:
            linhas.append("Índices normalizados para somar 12.")

        resumo = dados["resumo_indices"]
        if resumo is not None:
            maior = resumo["maior"]
            menor = resumo["menor"]
            linhas += [
                f"Maior índice: {nomes_meses[maior - 1]} "
                f"({indice(medias_indice[maior][0])}, "
                f"{medias_indice[maior][1]} observação(ões))",
                f"Menor índice: {nomes_meses[menor - 1]} "
                f"({indice(medias_indice[menor][0])}, "
                f"{medias_indice[menor][1]} observação(ões))",
            ]
            if len(medias_indice) < 12:
                linhas.append(
                    f"Comparação feita entre {len(medias_indice)} de 12 meses "
                    "do ano; os demais não têm índice."
                )
            if medias_indice[menor][0] > 0:
                linhas.append(
                    "Amplitude sazonal (maior ÷ menor índice): "
                    f"{indice(medias_indice[maior][0] / medias_indice[menor][0])}"
                )
            if resumo["media"] > 0:
                coeficiente = f"{resumo['desvio'] / resumo['media'] * 100:.1f}"
                linhas.append(
                    "Coeficiente de variação dos índices: "
                    f"{coeficiente.replace('.', ',')}%"
                )

        variacoes_anuais = dados["variacoes_anuais"]
        crescimento = dados["crescimento_anual"]
        queda = dados["queda_anual"]

        linhas += [
            "",
            "== CÁLCULOS: VARIAÇÃO ANO CONTRA ANO (faturamento por dia) ==",
            f"- Variações válidas: {len(variacoes_anuais)} "
            f"(crescimento: {crescimento}, queda: {queda}, "
            f"estáveis: {len(variacoes_anuais) - crescimento - queda})",
            "- Variações com base insuficiente: "
            f"{len(dados['insuficientes_anuais'])}",
            f"- Não comparáveis (mês incompleto): {dados['nao_comparaveis']}",
        ]
        for ano, m, v in variacoes_anuais:
            linhas.append(
                f"   {nomes_meses[m - 1]} {ano} vs {ano - 1}: {pct(v)}"
            )
        for ano, m, faturamento_anterior in dados["insuficientes_anuais"]:
            if faturamento_anterior <= 0:
                motivo = "mesmo mês do ano anterior sem faturamento"
            else:
                motivo = (
                    "faturamento do mesmo mês do ano anterior abaixo do "
                    f"limite de base mínima (R$ {brl(faturamento_anterior)})"
                )
            linhas.append(
                f"   {nomes_meses[m - 1]} {ano} vs {ano - 1}: base "
                f"insuficiente - {motivo}"
            )

        semanal = dados["semanal"]
        linhas += ["", "== CÁLCULOS: SAZONALIDADE SEMANAL =="]
        linhas.append(
            f"Semanas completas (segunda a domingo): {semanal['semanas']} | "
            f"válidas: {semanal['semanas_validas']} | com base insuficiente: "
            f"{semanal['semanas'] - semanal['semanas_validas']}"
        )

        if not semanal["suficiente"]:
            linhas.append(
                "Semanas válidas insuficientes para analisar o padrão "
                "semanal (mínimo 8)."
            )
        else:
            total_semanas = semanal["total_semanas"]
            linhas.append(
                "Índice = faturamento médio do dia ÷ média dos 7 dias "
                "(1,00 = dia médio)."
            )
            for d, dia in enumerate(semanal["dias"]):
                linhas.append(
                    f"- {nomes_dias[d]}: média R$ {brl(dia['media'])} | "
                    f"mediana R$ {brl(dia['mediana'])} | "
                    f"MAD R$ {brl(dia['mad'])} | "
                    f"pedidos/dia {brl(dia['pedidos'])} | "
                    f"índice {indice(dia['indice'])} | "
                    f"acima da média da semana em {dia['acima_media']} de "
                    f"{total_semanas} semanas"
                )

            fat = semanal["faturamento"]
            linhas.append(
                "Diferença entre o maior e o menor faturamento médio: "
                f"R$ {brl(fat['diferenca'])} | limite de tolerância: "
                f"R$ {brl(fat['tolerancia'])} (1% da média dos 7 dias)"
            )

            if round(fat["diferenca"], 2) == 0:
                linhas.append(
                    "Todos os dias da semana têm o mesmo faturamento médio: "
                    "não há diferença entre eles."
                )
            elif fat["diferenca"] < fat["tolerancia"]:
                linhas.append(
                    "Diferença inferior ao limite de 1%: nenhum dia é "
                    "destacado como de maior ou menor faturamento."
                )
            else:
                linhas += [
                    "Maior faturamento médio: "
                    f"{listar(fat['dias_maior'])} "
                    f"(R$ {brl(fat['maior'])})",
                    "Menor faturamento médio: "
                    f"{listar(fat['dias_menor'])} "
                    f"(R$ {brl(fat['menor'])})",
                ]
                if fat["menor"] > 0:
                    linhas.append(
                        f"Diferença entre o maior e o menor dia: "
                        f"{pct((fat['maior'] / fat['menor'] - 1) * 100)}"
                    )

            ped = semanal["pedidos"]
            linhas.append(
                "Diferença entre a maior e a menor quantidade média de "
                f"pedidos: {brl(ped['diferenca'])} | limite de tolerância: "
                f"{brl(ped['tolerancia'])} (1% da média dos 7 dias)"
            )

            if round(ped["diferenca"], 2) == 0:
                linhas.append(
                    "Todos os dias da semana têm a mesma quantidade média de "
                    "pedidos: não há diferença entre eles."
                )
            elif ped["diferenca"] < ped["tolerancia"]:
                linhas.append(
                    "Diferença inferior ao limite de 1%: nenhum dia é "
                    "destacado como de mais ou menos pedidos."
                )
            else:
                linhas += [
                    "Mais pedidos por dia: "
                    f"{listar(ped['dias_maior'])} "
                    f"({brl(ped['maior'])})",
                    "Menos pedidos por dia: "
                    f"{listar(ped['dias_menor'])} "
                    f"({brl(ped['menor'])})",
                ]

            linhas.append(
                "Os limites de 1% são critérios descritivos para não "
                "destacar diferenças desprezíveis; não são testes de "
                "significância estatística."
            )

        linhas += [
            "",
            "== OBSERVAÇÕES PARA INTERPRETAÇÃO ==",
            "- Os índices mensais comparam cada mês com a tendência estimada "
            "pela média móvel centrada de 12 meses, o que separa o "
            "crescimento da sazonalidade; com poucas observações por mês "
            "do ano, são indicativos e não uma comprovação estatística.",
            "- Meses do ano com apenas 1 observação não permitem comparar "
            "anos; o padrão pode não se repetir.",
            "- O padrão semanal se baseia em muito mais observações e é "
            "mais confiável que o mensal.",
            "- A base não contém informações sobre datas comemorativas, "
            "campanhas ou eventos externos; qualquer explicação para picos "
            "e quedas deve ser tratada como hipótese e confirmada com "
            "outras fontes.",
        ]

        return "\n".join(linhas)

    except Exception as erro:
        return f"Não foi possível consultar o banco: {erro}"


if __name__ == "__main__":
    mcp.run()
