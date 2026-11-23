from datetime import datetime
from pathlib import Path
import csv
import json
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
BRUTOS_DIR = BASE_DIR / "brutos"
SCHEMA_PATH = BASE_DIR / "insumos" / "schema_sqlite.sql"
DB_PATH = BASE_DIR / "verdejar.db"


def carregar_json_lista(caminho: Path, rotulo: str) -> list[dict]:
    if not caminho.is_file():
        raise FileNotFoundError(f"arquivo bruto ausente para {rotulo}: {caminho}")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"falha ao ler JSON de {rotulo} em {caminho}: {exc}") from exc
    if not isinstance(dados, list) or not all(isinstance(item, dict) for item in dados):
        raise ValueError(f"estrutura inesperada em {rotulo}: esperada lista de dicionários")
    return dados


def carregar_produtos_csv(caminho: Path) -> list[dict[str, str]]:
    if not caminho.is_file():
        raise FileNotFoundError(f"arquivo CSV de produtos ausente: {caminho}")
    try:
        with caminho.open("r", encoding="utf-8", newline="") as arquivo:
            return list(csv.DictReader(arquivo))
    except (OSError, csv.Error) as exc:
        raise RuntimeError(f"falha ao ler CSV de produtos em {caminho}: {exc}") from exc


def parse_numero(valor, campo: str) -> tuple[float, bool]:
    if valor is None or isinstance(valor, bool):
        raise ValueError(f"valor numérico inválido em '{campo}': {valor!r}")
    if isinstance(valor, (int, float)):
        return float(valor), False
    texto_original = str(valor).strip()
    if not texto_original:
        raise ValueError(f"campo numérico vazio em '{campo}'")
    texto = texto_original.replace("R$", "").replace(" ", "")
    houve_formato_texto = ("R$" in texto_original) or ("," in texto_original)
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto), houve_formato_texto
    except ValueError as exc:
        raise ValueError(f"falha ao converter '{campo}'={valor!r} para número") from exc


def normalizar_data(valor, campo: str) -> tuple[str, bool]:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"data ausente ou inválida em '{campo}': {valor!r}")
    texto = valor.strip()
    for formato, foi_barra in (("%Y-%m-%d", False), ("%d/%m/%Y", True)):
        try:
            data_iso = datetime.strptime(texto, formato).strftime("%Y-%m-%d")
            return data_iso, foi_barra
        except ValueError:
            continue
    raise ValueError(f"formato de data não suportado em '{campo}': {valor!r}")


def transformar_clientes(clientes_brutos: list[dict]) -> tuple[list[tuple], dict[str, int]]:
    vistos: set[int] = set()
    linhas: list[tuple] = []
    stats = {
        "clientes_lidos": len(clientes_brutos),
        "clientes_carregados": 0,
        "emails_nulos": 0,
        "estados_normalizados": 0,
    }
    for c in clientes_brutos:
        cid, _ = parse_numero(c.get("id"), "clientes.id")
        cid_int = int(cid)
        if cid_int in vistos:
            continue
        vistos.add(cid_int)

        email_bruto = c.get("email")
        if isinstance(email_bruto, str) and email_bruto.strip():
            email = email_bruto.strip()
        else:
            email = None
            stats["emails_nulos"] += 1

        estado_bruto = str(c.get("estado") or "").strip()
        estado = estado_bruto.upper()
        if len(estado) != 2:
            raise ValueError(f"UF inválida para cliente {cid_int}: {c.get('estado')!r}")
        if estado_bruto != estado:
            stats["estados_normalizados"] += 1

        cadastro_iso, _ = normalizar_data(c.get("cadastro_em"), "clientes.cadastro_em")
        linhas.append(
            (
                cid_int,
                str(c.get("nome") or "").strip(),
                email,
                str(c.get("cidade") or "").strip(),
                estado,
                cadastro_iso,
            )
        )
    stats["clientes_carregados"] = len(linhas)
    return linhas, stats


def transformar_produtos(produtos_brutos: list[dict[str, str]]) -> tuple[list[tuple], dict[str, int]]:
    vistos: set[int] = set()
    linhas: list[tuple] = []
    stats = {
        "produtos_lidos": len(produtos_brutos),
        "produtos_carregados": 0,
        "precos_convertidos": 0,
    }
    for p in produtos_brutos:
        pid_num, _ = parse_numero(p.get("produto_id"), "produtos.produto_id")
        pid = int(pid_num)
        if pid in vistos:
            continue
        vistos.add(pid)

        preco_num, convertido = parse_numero(p.get("preco_base"), "produtos.preco_base")
        if convertido:
            stats["precos_convertidos"] += 1

        linhas.append(
            (
                pid,
                str(p.get("nome") or "").strip(),
                str(p.get("categoria") or "").strip(),
                round(preco_num, 2),
            )
        )
    stats["produtos_carregados"] = len(linhas)
    return linhas, stats


def transformar_pedidos_e_itens(
    pedidos_brutos: list[dict],
) -> tuple[list[tuple], list[tuple], dict[str, int]]:
    pedidos_vistos: set[int] = set()
    pedidos_linhas: list[tuple] = []
    itens_linhas: list[tuple] = []
    stats = {
        "pedidos_lidos": len(pedidos_brutos),
        "pedidos_carregados": 0,
        "pedidos_duplicados_descartados": 0,
        "datas_convertidas": 0,
        "valores_convertidos": 0,
        "pedidos_divergentes": 0,
        "itens_carregados": 0,
    }

    for p in pedidos_brutos:
        pid_num, _ = parse_numero(p.get("id"), "pedidos.id")
        pedido_id = int(pid_num)
        # deduplica mantendo a primeira ocorrência da paginação
        if pedido_id in pedidos_vistos:
            stats["pedidos_duplicados_descartados"] += 1
            continue
        pedidos_vistos.add(pedido_id)

        cid_num, _ = parse_numero(p.get("cliente_id"), "pedidos.cliente_id")
        cliente_id = int(cid_num)
        data_pedido, foi_barra = normalizar_data(p.get("data_pedido"), "pedidos.data_pedido")
        if foi_barra:
            stats["datas_convertidas"] += 1

        status = str(p.get("status") or "").strip()
        valor_total_num, valor_convertido = parse_numero(p.get("valor_total"), "pedidos.valor_total")
        if valor_convertido:
            stats["valores_convertidos"] += 1
        valor_total = round(valor_total_num, 2)

        itens_brutos = p.get("itens")
        if not isinstance(itens_brutos, list):
            raise ValueError(f"lista de itens inválida no pedido {pedido_id}")

        soma_itens = 0.0
        for linha_idx, item in enumerate(itens_brutos, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"item inválido no pedido {pedido_id}, linha {linha_idx}")
            prod_num, _ = parse_numero(item.get("produto_id"), "itens_pedido.produto_id")
            qtd_num, _ = parse_numero(item.get("quantidade"), "itens_pedido.quantidade")
            preco_num, preco_convertido = parse_numero(
                item.get("preco_unitario"), "itens_pedido.preco_unitario"
            )
            if preco_convertido:
                stats["valores_convertidos"] += 1
            produto_id = int(prod_num)
            quantidade = int(qtd_num)
            preco_unitario = round(preco_num, 2)
            soma_itens += quantidade * preco_unitario
            itens_linhas.append((pedido_id, linha_idx, produto_id, quantidade, preco_unitario))

        valor_itens = round(soma_itens, 2)
        # tolerância de 1 centavo conforme regra A6
        divergente = 1 if abs(valor_total - valor_itens) > 0.01 else 0
        if divergente == 1:
            stats["pedidos_divergentes"] += 1

        pedidos_linhas.append(
            (pedido_id, cliente_id, data_pedido, status, valor_total, valor_itens, divergente)
        )

    stats["pedidos_carregados"] = len(pedidos_linhas)
    stats["itens_carregados"] = len(itens_linhas)
    return pedidos_linhas, itens_linhas, stats


def carregar_sqlite(
    clientes: list[tuple],
    produtos: list[tuple],
    pedidos: list[tuple],
    itens: list[tuple],
) -> None:
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"esquema SQLite ausente: {SCHEMA_PATH}")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(schema_sql)
            conn.execute("PRAGMA foreign_keys = ON")
            # limpa na ordem inversa das dependências para recarga limpa e idempotente
            conn.execute("DELETE FROM itens_pedido")
            conn.execute("DELETE FROM pedidos")
            conn.execute("DELETE FROM clientes")
            conn.execute("DELETE FROM produtos")

            conn.executemany(
                "INSERT INTO produtos (produto_id, nome, categoria, preco_base) VALUES (?, ?, ?, ?)",
                produtos,
            )
            conn.executemany(
                "INSERT INTO clientes (id, nome, email, cidade, estado, cadastro_em) VALUES (?, ?, ?, ?, ?, ?)",
                clientes,
            )
            conn.executemany(
                "INSERT INTO pedidos (id, cliente_id, data_pedido, status, valor_total, valor_itens, divergente) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                pedidos,
            )
            conn.executemany(
                "INSERT INTO itens_pedido (pedido_id, linha, produto_id, quantidade, preco_unitario) "
                "VALUES (?, ?, ?, ?, ?)",
                itens,
            )
    except sqlite3.Error as exc:
        raise RuntimeError(f"falha ao carregar dados no SQLite ({DB_PATH}): {exc}") from exc


def imprimir_contadores(stats_clientes: dict[str, int], stats_produtos: dict[str, int], stats_pedidos: dict[str, int]) -> None:
    linhas = [
        f"clientes_lidos={stats_clientes['clientes_lidos']}",
        f"clientes_carregados={stats_clientes['clientes_carregados']}",
        f"emails_nulos={stats_clientes['emails_nulos']}",
        f"estados_normalizados={stats_clientes['estados_normalizados']}",
        f"produtos_lidos={stats_produtos['produtos_lidos']}",
        f"produtos_carregados={stats_produtos['produtos_carregados']}",
        f"precos_produtos_convertidos={stats_produtos['precos_convertidos']}",
        f"pedidos_lidos={stats_pedidos['pedidos_lidos']}",
        f"pedidos_carregados={stats_pedidos['pedidos_carregados']}",
        f"pedidos_duplicados_descartados={stats_pedidos['pedidos_duplicados_descartados']}",
        f"datas_pedidos_convertidas={stats_pedidos['datas_convertidas']}",
        f"valores_convertidos={stats_pedidos['valores_convertidos']}",
        f"pedidos_divergentes={stats_pedidos['pedidos_divergentes']}",
        f"itens_carregados={stats_pedidos['itens_carregados']}",
    ]
    for linha in linhas:
        print(linha)


def main() -> None:
    try:
        clientes_brutos = carregar_json_lista(
            BRUTOS_DIR / "clientes" / "clientes_brutos.json", "clientes"
        )
        pedidos_brutos = carregar_json_lista(
            BRUTOS_DIR / "pedidos" / "pedidos_brutos.json", "pedidos"
        )
        produtos_brutos = carregar_produtos_csv(BRUTOS_DIR / "produtos.csv")

        clientes, stats_clientes = transformar_clientes(clientes_brutos)
        produtos, stats_produtos = transformar_produtos(produtos_brutos)
        pedidos, itens, stats_pedidos = transformar_pedidos_e_itens(pedidos_brutos)
        carregar_sqlite(clientes, produtos, pedidos, itens)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"erro na transformação: {exc}")
        raise SystemExit(1) from exc

    imprimir_contadores(stats_clientes, stats_produtos, stats_pedidos)


if __name__ == "__main__":
    main()