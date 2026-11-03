import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client

BASE_DIR = Path(__file__).resolve().parent.parent


def texto(resultado):
    return "\n".join(getattr(c, "text", repr(c)) for c in resultado.content)


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=str(BASE_DIR),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Conectado: {init.server_info.name} (protocolo {init.protocol_version})")

            tools = await session.list_tools()
            print("Ferramentas:", [t.name for t in tools.tools])

            r = await session.call_tool("somar", {"a": 2, "b": 3})
            print(f"\nsomar(2, 3) -> {texto(r)}  [erro={r.is_error}]")

            r = await session.call_tool("consultar_projeto", {})
            print(f"\nconsultar_projeto -> {texto(r)}  [erro={r.is_error}]")

            r = await session.call_tool("consultar_indicadores", {})
            print(f"\nconsultar_indicadores ->\n{texto(r)}  [erro={r.is_error}]")

            r = await session.call_tool("consultar_faturamento_por_categoria", {})
            print(f"\nconsultar_faturamento_por_categoria ->\n{texto(r)}  [erro={r.is_error}]")


if __name__ == "__main__":
    anyio.run(main)
