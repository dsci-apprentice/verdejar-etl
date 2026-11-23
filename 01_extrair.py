from pathlib import Path
import json
import shutil
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
BASE_DIR = Path(__file__).resolve().parent
BRUTOS_DIR = BASE_DIR / "brutos"
PRODUTOS_ORIGEM = BASE_DIR / "insumos" / "dados" / "produtos.csv"


def requisitar_pagina(rota: str, page: int, page_size: int = 200, tentativas: int = 3) -> dict:
    url = f"{BASE_URL}/{rota}?page={page}&page_size={page_size}"
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(url, timeout=10)
            # 404 indica página inexistente ou fim das páginas após a última
            if resp.status_code == 404:
                return {"not_found": True}
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"falha HTTP {resp.status_code} ao consultar {rota} na página {page} ({url})"
                )
            dados = resp.json()
            if not isinstance(dados, dict):
                raise ValueError(f"resposta JSON inesperada em {rota} página {page}: esperado objeto")
            return dados
        except requests.ConnectionError as exc:
            ultimo_erro = f"erro de conexão com a API em {BASE_URL} (verifique se o servidor está ativo): {exc}"
        except requests.Timeout as exc:
            ultimo_erro = f"tempo esgotado ao consultar {url}: {exc}"
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            ultimo_erro = str(exc)

        if tentativa < tentativas:
            time.sleep(0.5 * tentativa)

    raise RuntimeError(
        f"não foi possível obter {rota} (página {page}) após {tentativas} tentativas: {ultimo_erro}"
    )


def salvar_recurso_bruto(rota: str, paginas_salvas: list[dict], todos_itens: list[dict]) -> None:
    destino_dir = BRUTOS_DIR / rota
    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        (destino_dir / "paginas.json").write_text(
            json.dumps(paginas_salvas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (destino_dir / f"{rota}_brutos.json").write_text(
            json.dumps(todos_itens, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"falha ao salvar dados brutos de '{rota}': {exc}") from exc


def extrair_recurso(rota: str, page_size: int = 200) -> tuple[list[dict], int]:
    todos_itens: list[dict] = []
    paginas_salvas: list[dict] = []
    paginas_consumidas = 0
    page = 1

    while True:
        payload = requisitar_pagina(rota, page=page, page_size=page_size)
        if payload.get("not_found"):
            if page == 1:
                raise RuntimeError(
                    f"página inexistente (HTTP 404) na página 1 para '{rota}' em {BASE_URL}"
                )
            break

        itens = payload.get("items")
        if not isinstance(itens, list):
            raise ValueError(f"campo 'items' inválido em {rota} página {page}")

        paginas_consumidas += 1
        paginas_salvas.append(payload)
        todos_itens.extend(itens)

        # encerra quando atinge total_pages ou quando não há mais itens
        total_pages = payload.get("total_pages")
        if isinstance(total_pages, int) and page >= total_pages:
            break
        if not itens:
            break
        page += 1

    salvar_recurso_bruto(rota, paginas_salvas, todos_itens)
    return todos_itens, paginas_consumidas


def copiar_produtos_csv() -> str:
    if not PRODUTOS_ORIGEM.is_file():
        return "ausente"
    try:
        shutil.copy2(PRODUTOS_ORIGEM, BRUTOS_DIR / "produtos.csv")
        return "ok"
    except OSError as exc:
        raise RuntimeError(f"falha ao copiar {PRODUTOS_ORIGEM}: {exc}") from exc


def imprimir_resumo_extracao(
    clientes: list[dict],
    paginas_clientes: int,
    pedidos: list[dict],
    paginas_pedidos: int,
    status_produtos: str,
) -> None:
    linhas = [
        f"clientes_paginas={paginas_clientes}",
        f"clientes_registros={len(clientes)}",
        f"pedidos_paginas={paginas_pedidos}",
        f"pedidos_registros={len(pedidos)}",
        f"produtos_csv={status_produtos}",
    ]
    for linha in linhas:
        print(linha)


def main() -> None:
    try:
        BRUTOS_DIR.mkdir(parents=True, exist_ok=True)
        clientes, paginas_clientes = extrair_recurso("clientes", page_size=200)
        pedidos, paginas_pedidos = extrair_recurso("pedidos", page_size=200)
        status_produtos = copiar_produtos_csv()
    except (RuntimeError, ValueError) as exc:
        print(f"erro na extração: {exc}")
        raise SystemExit(1) from exc

    imprimir_resumo_extracao(
        clientes=clientes,
        paginas_clientes=paginas_clientes,
        pedidos=pedidos,
        paginas_pedidos=paginas_pedidos,
        status_produtos=status_produtos,
    )


if __name__ == "__main__":
    main()