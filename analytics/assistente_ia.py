
import os
import sys
from pathlib import Path

import anyio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters, stdio_client


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MODEL = "gemini-3.6-flash"

INSTRUCOES = """
Você é o Data Analyst AI, um analista de dados do e-commerce Olist.

Regras:
- Todo número que você citar deve vir de uma ferramenta chamada nesta
  conversa. Nunca use valores do seu conhecimento geral.
- Se nenhuma ferramenta fornecer o dado pedido, diga claramente que não
  há ferramenta para essa consulta e não estime valores.
- Não mude valores retornados pelas ferramentas; arredondamentos devem
  ser indicados.

Organize sempre a resposta em três seções, nesta ordem:

## Dados
Apenas informações retornadas pelas ferramentas, citando o nome da
ferramenta utilizada.

## Cálculos
Indicadores derivados dos dados (percentuais, médias, diferenças,
participações). Mostre a fórmula e os valores usados em cada cálculo.
Se não houver cálculos, escreva "Nenhum cálculo realizado".

## Interpretações
Hipóteses e possíveis explicações, sempre identificadas como hipóteses
(por exemplo: "Hipótese: ..."). Não apresente interpretações como fatos
e indique quais dados seriam necessários para confirmá-las.

Responda em português do Brasil.
""".strip()


def texto(resultado):
    return "\n".join(
        getattr(c, "text", repr(c))
        for c in resultado.content
    )


async def responder(pergunta):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não encontrada no .env")

    cliente = genai.Client(api_key=api_key)

    params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=str(BASE_DIR),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            ferramentas_mcp = await session.list_tools()

            declaracoes = [
                types.FunctionDeclaration(
                    name=ferramenta.name,
                    description=ferramenta.description or ferramenta.name,
                    parameters_json_schema=ferramenta.input_schema,
                )
                for ferramenta in ferramentas_mcp.tools
            ]

            ferramenta_gemini = types.Tool(
                function_declarations=declaracoes
            )

            config = types.GenerateContentConfig(
                system_instruction=INSTRUCOES,
                tools=[ferramenta_gemini],
            )

            conteudo = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=pergunta)],
                )
            ]

            resposta = cliente.models.generate_content(
                model=MODEL,
                contents=conteudo,
                config=config,
            )

            for _ in range(5):
                candidato = resposta.candidates[0].content
                chamadas = [
                    parte.function_call
                    for parte in candidato.parts
                    if parte.function_call
                ]

                if not chamadas:
                    return resposta.text or "Não foi possível gerar uma resposta."

                conteudo.append(candidato)

                for chamada in chamadas:
                    resultado = await session.call_tool(
                        chamada.name,
                        dict(chamada.args or {}),
                    )

                    conteudo.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_function_response(
                                    name=chamada.name,
                                    response={
                                        "resultado": texto(resultado)
                                    },
                                )
                            ],
                        )
                    )

                resposta = cliente.models.generate_content(
                    model=MODEL,
                    contents=conteudo,
                    config=config,
                )

            return resposta.text or "Limite de chamadas de ferramentas atingido."


async def main():
    pergunta = input("Faça sua pergunta sobre os dados da Olist: ")

    resultado = await responder(pergunta)

    print("\nResposta do Data Analyst AI:")
    print(resultado)


if __name__ == "__main__":
    anyio.run(main)
