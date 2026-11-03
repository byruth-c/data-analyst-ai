/* ==========================================================================
   Data Analyst AI - menu responsivo e gráficos (Chart.js)
   ========================================================================== */

/* Abre e fecha o menu lateral no celular. */
(function configurarMenu() {
    const botao = document.getElementById("botao-menu");
    const menu = document.getElementById("menu-lateral");
    const fundo = document.getElementById("menu-fundo");

    if (!botao || !menu || !fundo) {
        return;
    }

    function alternar(aberto) {
        menu.classList.toggle("aberto", aberto);
        fundo.hidden = !aberto;
        botao.setAttribute("aria-expanded", String(aberto));
        botao.setAttribute("aria-label", aberto ? "Fechar menu" : "Abrir menu");
    }

    botao.addEventListener("click", () => {
        const abrir = !menu.classList.contains("aberto");
        alternar(abrir);
        if (abrir) {
            // Leva o foco para o primeiro link, para quem navega pelo teclado.
            const primeiroLink = menu.querySelector("a");
            if (primeiroLink) {
                primeiroLink.focus();
            }
        }
    });
    fundo.addEventListener("click", () => alternar(false));
    document.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape" && menu.classList.contains("aberto")) {
            alternar(false);
            botao.focus();
        }
    });
})();

/* Gráficos já desenhados na página, para redesenhar ao trocar o tema. */
const graficosDaPagina = [];
let redesenhando = false;

function lembrarGrafico(funcao, argumentos) {
    if (!redesenhando) {
        graficosDaPagina.push([funcao, argumentos]);
    }
}

function redesenharGraficos() {
    if (typeof Chart === "undefined") {
        return;
    }
    Object.values(Chart.instances).forEach((grafico) => grafico.destroy());
    redesenhando = true;
    graficosDaPagina.forEach(([funcao, argumentos]) => funcao(...argumentos));
    redesenhando = false;
}

/* Liga e desliga o modo noturno; a escolha fica salva no navegador. */
(function configurarTema() {
    const botao = document.getElementById("botao-tema");
    if (!botao) {
        return;
    }

    function atualizarBotao() {
        const noturno = document.documentElement.dataset.tema === "noturno";
        botao.setAttribute("aria-pressed", String(noturno));
        botao.setAttribute("aria-label", noturno ? "Desativar modo noturno" : "Ativar modo noturno");
        botao.title = noturno ? "Modo claro" : "Modo noturno";
    }

    botao.addEventListener("click", () => {
        const noturno = document.documentElement.dataset.tema !== "noturno";
        if (noturno) {
            document.documentElement.dataset.tema = "noturno";
        } else {
            delete document.documentElement.dataset.tema;
        }
        try {
            localStorage.setItem("tema", noturno ? "noturno" : "claro");
        } catch (erro) {
            // Sem armazenamento (ex.: janela anônima): o tema vale só nesta página.
        }
        atualizarBotao();
        redesenharGraficos();
    });

    atualizarBotao();
})();

/* Formata números no padrão brasileiro (99.441 e R$ 1.258.681,34). */
const formatoInteiro = new Intl.NumberFormat("pt-BR");
const formatoReais = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
});
const formatoReaisCompacto = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
});

/**
 * Cores dos gráficos, lidas das variáveis do estilo.css. Assim os gráficos
 * acompanham o modo claro/escuro sem duplicar as cores aqui.
 */
function lerCores() {
    const estilo = getComputedStyle(document.documentElement);
    const ler = (nome) => estilo.getPropertyValue(nome).trim();
    return {
        superficie: ler("--cor-superficie"),
        serie1: ler("--grafico-serie-1"),
        serie2: ler("--grafico-serie-2"),
        positivo: ler("--grafico-positivo"),
        negativo: ler("--grafico-negativo"),
        neutro: ler("--grafico-neutro"),
        grade: ler("--grafico-grade"),
        texto: ler("--grafico-texto"),
        referencia: ler("--grafico-referencia"),
        dica: ler("--grafico-dica"),
    };
}

/** Converte "#2563eb" em "rgba(37, 99, 235, alfa)" para preencher áreas. */
function comTransparencia(hex, alfa) {
    const valor = hex.replace("#", "");
    const r = parseInt(valor.slice(0, 2), 16);
    const g = parseInt(valor.slice(2, 4), 16);
    const b = parseInt(valor.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alfa})`;
}

/* Medidas comuns: barras finas com ponta arredondada e base reta,
   linhas de 2px e marcadores de 8px com anel na cor do fundo. */
const ESPESSURA_MAXIMA_BARRA = 24;
const RAIO_BARRA = 4;
const LARGURA_LINHA = 2;
const RAIO_PONTO = 4;
const RAIO_TOQUE = 12;

/**
 * Aparência comum a todos os gráficos: mesma fonte, cores e dicas do site.
 * Chamada por cada função de gráfico, depois que o Chart.js foi carregado.
 */
function aplicarPadroesGraficos() {
    const cores = lerCores();
    Chart.defaults.font.family = '"Inter", "Segoe UI", system-ui, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = cores.texto;
    Chart.defaults.borderColor = cores.grade;
    Chart.defaults.plugins.tooltip.backgroundColor = cores.dica;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
    Chart.defaults.plugins.tooltip.boxPadding = 4;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    return cores;
}

/**
 * Gráfico de rosca com a distribuição dos pedidos por status.
 * Os dados vêm da view, publicados no HTML com o filtro json_script.
 */
function criarGraficoStatus(idCanvas, idDados) {
    lembrarGrafico(criarGraficoStatus, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);
    const total = dados.valores.reduce((soma, valor) => soma + valor, 0);

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels: dados.rotulos,
            datasets: [{
                data: dados.valores,
                // Entregues, cancelados e demais status.
                backgroundColor: [cores.positivo, cores.negativo, cores.neutro],
                // Separação de 2px na cor do fundo entre as fatias.
                borderColor: cores.superficie,
                borderWidth: 2,
                hoverOffset: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "62%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, padding: 16 },
                },
                tooltip: {
                    callbacks: {
                        label(contexto) {
                            const valor = contexto.parsed;
                            const percentual = total
                                ? ((valor / total) * 100).toLocaleString("pt-BR", {
                                    minimumFractionDigits: 1,
                                    maximumFractionDigits: 1,
                                })
                                : "0,0";
                            return ` ${contexto.label}: ${formatoInteiro.format(valor)} (${percentual}%)`;
                        },
                    },
                },
            },
        },
    });
}

/**
 * Barras horizontais empilhadas das 10 maiores categorias:
 * valor dos produtos + frete, cuja soma é o faturamento com frete.
 */
function criarGraficoCategorias(idCanvas, idDados) {
    lembrarGrafico(criarGraficoCategorias, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: dados.rotulos,
            datasets: [
                {
                    label: "Faturamento (sem frete)",
                    data: dados.faturamento,
                    backgroundColor: cores.serie1,
                    // Segmento interno: cantos retos e 2px de fundo separando do frete.
                    borderRadius: 0,
                    borderColor: cores.superficie,
                    borderWidth: { top: 0, right: 2, bottom: 0, left: 0 },
                    maxBarThickness: ESPESSURA_MAXIMA_BARRA,
                },
                {
                    label: "Frete",
                    data: dados.frete,
                    backgroundColor: cores.serie2,
                    // Ponta da barra arredondada; o lado que encosta no faturamento fica reto.
                    borderRadius: RAIO_BARRA,
                    maxBarThickness: ESPESSURA_MAXIMA_BARRA,
                },
            ],
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            // A dica aparece ao passar em qualquer ponto da linha da categoria.
            interaction: { mode: "index", axis: "y", intersect: false },
            scales: {
                x: {
                    stacked: true,
                    grid: { color: cores.grade },
                    border: { display: false },
                    ticks: { callback: (valor) => formatoReaisCompacto.format(valor) },
                },
                y: {
                    stacked: true,
                    grid: { display: false },
                },
            },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, padding: 16 },
                },
                tooltip: {
                    callbacks: {
                        label: (contexto) =>
                            ` ${contexto.dataset.label}: ${formatoReais.format(contexto.parsed.x)}`,
                        footer: (itens) => {
                            const indice = itens[0].dataIndex;
                            const total = dados.faturamento[indice] + dados.frete[indice];
                            return `Total com frete: ${formatoReais.format(total)}`;
                        },
                    },
                },
            },
        },
    });
}

/**
 * Tendências: faturamento dos meses completos com a média móvel de 3
 * meses; meses com possível anomalia na variação ficam em vermelho.
 */
function criarGraficoTendencias(idCanvas, idDados) {
    lembrarGrafico(criarGraficoTendencias, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);

    new Chart(canvas, {
        type: "line",
        data: {
            labels: dados.rotulos,
            datasets: [
                {
                    label: "Faturamento (sem frete)",
                    data: dados.faturamento,
                    borderColor: cores.serie1,
                    borderWidth: LARGURA_LINHA,
                    backgroundColor: comTransparencia(cores.serie1, 0.1),
                    fill: true,
                    cubicInterpolationMode: "monotone",
                    // Anomalias: ponto maior e vermelho (também indicadas na dica e na tabela).
                    pointRadius: dados.anomalia.map((a) => (a ? 6 : RAIO_PONTO)),
                    pointHoverRadius: dados.anomalia.map((a) => (a ? 7 : 6)),
                    pointBackgroundColor: dados.anomalia.map((a) => (a ? cores.negativo : cores.serie1)),
                    pointBorderColor: cores.superficie,
                    pointBorderWidth: 2,
                    pointHitRadius: RAIO_TOQUE,
                },
                {
                    label: "Média móvel de 3 meses",
                    data: dados.media_movel,
                    borderColor: cores.serie2,
                    borderWidth: LARGURA_LINHA,
                    borderDash: [6, 4],
                    pointRadius: 0,
                    pointHoverRadius: RAIO_PONTO,
                    pointBackgroundColor: cores.serie2,
                    pointBorderColor: cores.superficie,
                    pointBorderWidth: 2,
                    cubicInterpolationMode: "monotone",
                    spanGaps: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 45, autoSkip: true } },
                y: {
                    beginAtZero: true,
                    grid: { color: cores.grade },
                    border: { display: false },
                    ticks: { callback: (valor) => formatoReaisCompacto.format(valor) },
                },
            },
            plugins: {
                legend: { position: "bottom", labels: { usePointStyle: true, padding: 16 } },
                tooltip: {
                    callbacks: {
                        label: (contexto) =>
                            contexto.parsed.y === null
                                ? null
                                : ` ${contexto.dataset.label}: ${formatoReais.format(contexto.parsed.y)}`,
                        footer: (itens) =>
                            dados.anomalia[itens[0].dataIndex] ? "Possível anomalia na variação" : "",
                    },
                },
            },
        },
    });
}

/** Sazonalidade semanal: faturamento médio por dia da semana. */
function criarGraficoSemanal(idCanvas, idDados) {
    lembrarGrafico(criarGraficoSemanal, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);
    const media = dados.faturamento.reduce((soma, v) => soma + v, 0) / dados.faturamento.length;

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: dados.rotulos,
            datasets: [{
                label: "Faturamento médio",
                data: dados.faturamento,
                // Acima da média dos 7 dias em azul, abaixo em cinza.
                backgroundColor: dados.faturamento.map((v) => (v >= media ? cores.serie1 : cores.neutro)),
                borderRadius: RAIO_BARRA,
                maxBarThickness: ESPESSURA_MAXIMA_BARRA,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            // A dica aparece ao passar em qualquer altura da coluna do dia.
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: cores.grade },
                    border: { display: false },
                    ticks: { callback: (valor) => formatoReaisCompacto.format(valor) },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (contexto) => ` Faturamento médio: ${formatoReais.format(contexto.parsed.y)}`,
                        afterLabel: (contexto) =>
                            ` Pedidos por dia: ${dados.pedidos[contexto.dataIndex].toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`,
                    },
                },
            },
        },
    });
}

/**
 * Sazonalidade mensal: índice médio por mês do ano (1,00 = tendência).
 * As barras partem da linha de 1,00: para cima acima da tendência,
 * para baixo abaixo dela.
 */
function criarGraficoIndices(idCanvas, idDados) {
    lembrarGrafico(criarGraficoIndices, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);
    if (!dados.rotulos.length) {
        return;
    }

    // Escala com folga em volta dos índices existentes, sempre incluindo 1,00.
    const validos = dados.indices.filter((v) => v !== null);
    const minimo = Math.min(1, ...validos);
    const maximo = Math.max(1, ...validos);
    const folga = Math.max((maximo - minimo) * 0.15, 0.05);

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: dados.rotulos,
            datasets: [{
                label: "Índice sazonal",
                data: dados.indices,
                base: 1,
                // Meses sem índice chegam como null e ficam sem barra.
                backgroundColor: dados.indices.map((v) =>
                    v === null ? "transparent"
                        : Math.round(v * 100) > 100 ? cores.positivo
                        : Math.round(v * 100) < 100 ? cores.negativo : cores.neutro),
                borderRadius: RAIO_BARRA,
                maxBarThickness: ESPESSURA_MAXIMA_BARRA,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: false,
                    // Arredonda os limites para décimos (0,80 · 1,40), evitando traços como 0,83.
                    min: Math.max(0, Math.floor((minimo - folga) * 10) / 10),
                    max: Math.ceil((maximo + folga) * 10) / 10,
                    grid: { color: (ctx) => (ctx.tick.value === 1 ? cores.referencia : cores.grade) },
                    border: { display: false },
                    ticks: { callback: (valor) => valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
                    // Garante um traço exatamente em 1,00 (a linha de referência).
                    afterBuildTicks: (eixo) => {
                        if (!eixo.ticks.some((t) => t.value === 1)) {
                            eixo.ticks.push({ value: 1 });
                            eixo.ticks.sort((a, b) => a.value - b.value);
                        }
                    },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (contexto) =>
                            contexto.parsed.y === null
                                ? null
                                : ` Índice: ${contexto.parsed.y.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                    },
                },
            },
        },
    });
}

/** Desabilita o botão enquanto o assistente responde, evitando envios duplicados. */
function configurarFormularioPergunta(idFormulario, idBotao) {
    const formulario = document.getElementById(idFormulario);
    const botao = document.getElementById(idBotao);

    if (!formulario || !botao) {
        return;
    }

    formulario.addEventListener("submit", () => {
        botao.disabled = true;
        botao.textContent = "Consultando…";
        formulario.setAttribute("aria-busy", "true");
    });
}

/**
 * Linha do faturamento mensal. A dica mostra pedidos e a variação em
 * relação ao mês anterior, com o mesmo texto da tabela (inclusive quando
 * não há base de comparação).
 */
function criarGraficoEvolucao(idCanvas, idDados) {
    lembrarGrafico(criarGraficoEvolucao, [idCanvas, idDados]);
    const canvas = document.getElementById(idCanvas);
    const elementoDados = document.getElementById(idDados);

    if (!canvas || !elementoDados || typeof Chart === "undefined") {
        return;
    }

    const cores = aplicarPadroesGraficos();

    const dados = JSON.parse(elementoDados.textContent);

    new Chart(canvas, {
        type: "line",
        data: {
            labels: dados.rotulos,
            datasets: [{
                label: "Faturamento (sem frete)",
                data: dados.faturamento,
                borderColor: cores.serie1,
                borderWidth: LARGURA_LINHA,
                backgroundColor: comTransparencia(cores.serie1, 0.1),
                fill: true,
                // "monotone" suaviza a linha sem ultrapassar os valores reais.
                cubicInterpolationMode: "monotone",
                pointRadius: RAIO_PONTO,
                pointHoverRadius: 6,
                pointHitRadius: RAIO_TOQUE,
                pointBorderColor: cores.superficie,
                pointBorderWidth: 2,
                // Meses sem vendas ficam destacados em vermelho.
                pointBackgroundColor: dados.pedidos.map((p) => (p === 0 ? cores.negativo : cores.serie1)),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, autoSkip: true },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: cores.grade },
                    border: { display: false },
                    ticks: { callback: (valor) => formatoReaisCompacto.format(valor) },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (contexto) => ` Faturamento: ${formatoReais.format(contexto.parsed.y)}`,
                        afterLabel: (contexto) => {
                            const i = contexto.dataIndex;
                            return [
                                ` Pedidos: ${formatoInteiro.format(dados.pedidos[i])}`,
                                ` Variação: ${dados.variacao[i]}`,
                            ];
                        },
                    },
                },
            },
        },
    });
}
