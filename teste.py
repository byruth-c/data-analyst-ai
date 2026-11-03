
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    parametros = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=os.getcwd()
    )

    async with stdio_client(parametros) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            resultado = await sessao.list_tools()

            print("Conexão com servidor MCP: OK")
            print("\nFerramentas disponíveis:")

            for ferramenta in resultado.tools:
                print("-", ferramenta.name)


if __name__ == "__main__":
    asyncio.run(main())
