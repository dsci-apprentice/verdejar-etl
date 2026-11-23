from datetime import datetime
from pathlib import Path
import csv
import importlib.util
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "verdejar.db"
BRUTOS_DIR = BASE_DIR / "brutos"
TRANSFORMAR_PATH = BASE_DIR / "03_transformar.py"
RELATORIO_PATH = BASE_DIR / "auditoria_verdejar.md"
QUALIDADE_CSV_PATH = BASE_DIR / "relatorio_qualidade.csv"

COLUNAS_QUALIDADE = [
    "executado_em",
    "pedidos_duplicados_descartados",
    "violacoes_fk",
    "estados_invalidos",
    "datas_clientes_invalidas",
    "datas_pedidos_invalidas",
    "emails_nulos",
    "pedidos_divergentes",
    "divergencias_soma",
]


def carregar_modulo_transformar():
    if not TRANSFORMAR_PATH.is_file():
        raise FileNotFoundError(f"script de transformação não encontrado: {TRANSFORMAR_PATH}")
    spec = importlib.util.spec_from_file_location("transformar_mod", TRANSFORMAR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"não foi possível carregar {TRANSFORMAR_PATH}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def abrir_conexao_somente_leitura(caminho_db: Path) -> sqlite3.Connection:
    if not caminho_db.is_file():
        raise FileNotFoundError(f"banco SQLite não encontrado: {caminho_db}")
    try:
        uri = f"{caminho_db.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as exc:
        raise RuntimeError(f"falha ao abrir banco em modo leitura: {exc}") from exc


def consultar_contagens(conn: sqlite3.Connection) -> dict[str, int]:
    tabelas = ("clientes", "produtos", "pedidos", "itens_pedido")
    contagens: dict[str, int] = {}
    for tabela in tabelas:
        # nomes de tabelas vêm de tupla fixa interna, fora do controle do usuário
        linha = conn.execute(f"SELECT COUNT(*) AS total FROM {tabela}").fetchone()
        contagens[tabela] = int(linha["total"])
    return contagens


def consultar_integridade(conn: sqlite3.Connection) -> dict[str, int]:
    violacoes_fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    estados_invalidos = conn.execute(
        "SELECT COUNT(*) AS total FROM clientes "
        "WHERE length(estado) != 2 OR estado != UPPER(estado)"
    ).fetchone()["total"]
    datas_clientes_invalidas = conn.execute(
        "SELECT COUNT(*) AS total FROM clientes "
        "WHERE cadastro_em NOT LIKE '____-__-__'"
    ).fetchone()["total"]
    datas_pedidos_invalidas = conn.execute(
        "SELECT COUNT(*) AS total FROM pedidos "
        "WHERE data_pedido NOT LIKE '____-__-__'"
    ).fetchone()["total"]
    emails_nulos = conn.execute(
        "SELECT COUNT(*) AS total FROM clientes WHERE email IS NULL OR trim(email) = ''"
    ).fetchone()["total"]

    return {
        "violacoes_fk": len(violacoes_fk),
        "estados_invalidos": int(estados_invalidos),
        "datas_clientes_invalidas": int(datas_clientes_invalidas),
        "datas_pedidos_invalidas": int(datas_pedidos_invalidas),
        "emails_nulos": int(emails_nulos),
    }


def consultar_consistencia_financeira(conn: sqlite3.Connection) -> dict:
    resumo_div = conn.execute(
        "SELECT divergente, COUNT(*) AS total FROM pedidos GROUP BY divergente"
    ).fetchall()
    mapa_div = {int(r["divergente"]): int(r["total"]) for r in resumo_div}

    total_geral_itens = conn.execute(
        "SELECT ROUND(COALESCE(SUM(valor_itens), 0.0), 2) AS total FROM pedidos"
    ).fetchone()["total"]

    # compara valor_itens persistido com a soma calculada diretamente em itens_pedido
    divergencias_soma = conn.execute(
        "WITH totais_itens AS ("
        "  SELECT pedido_id, ROUND(SUM(quantidade * preco_unitario), 2) AS soma_calc "
        "  FROM itens_pedido GROUP BY pedido_id"
        ") "
        "SELECT COUNT(*) AS total FROM pedidos p "
        "LEFT JOIN totais_itens t ON t.pedido_id = p.id "
        "WHERE ROUND(p.valor_itens, 2) != ROUND(COALESCE(t.soma_calc, 0.0), 2)"
    ).fetchone()["total"]

    exemplos = conn.execute(
        "SELECT p.id, p.data_pedido, p.status, p.valor_total, p.valor_itens, "
        "ROUND(p.valor_total - p.valor_itens, 2) AS diferenca, "
        "COUNT(i.linha) AS qtd_itens "
        "FROM pedidos p "
        "LEFT JOIN itens_pedido i ON i.pedido_id = p.id "
        "WHERE p.divergente = 1 "
        "GROUP BY p.id, p.data_pedido, p.status, p.valor_total, p.valor_itens "
        "ORDER BY p.id ASC "
        "LIMIT 10"
    ).fetchall()

    return {
        "pedidos_conformes": mapa_div.get(0, 0),
        "pedidos_divergentes": mapa_div.get(1, 0),
        "total_geral_itens": round(float(total_geral_itens), 2),
        "divergencias_soma": int(divergencias_soma),
        "exemplos": [dict(r) for r in exemplos],
    }


def consultar_reconciliacao_origem(conn: sqlite3.Connection) -> dict:
    mod = carregar_modulo_transformar()

    clientes_brutos = mod.carregar_json_lista(
        BRUTOS_DIR / "clientes" / "clientes_brutos.json", "clientes"
    )
    clientes_tratados, _ = mod.transformar_clientes(clientes_brutos)

    produtos_csv = BRUTOS_DIR / "produtos.csv"
    if not produtos_csv.is_file():
        raise FileNotFoundError(f"arquivo bruto ausente: {produtos_csv}")
    with produtos_csv.open("r", encoding="utf-8", newline="") as arq:
        produtos_brutos = list(csv.DictReader(arq))
    produtos_tratados, _ = mod.transformar_produtos(produtos_brutos)

    pedidos_brutos = mod.carregar_json_lista(
        BRUTOS_DIR / "pedidos" / "pedidos_brutos.json", "pedidos"
    )
    pedidos_tratados, itens_tratados, stats_pedidos = mod.transformar_pedidos_e_itens(
        pedidos_brutos
    )

    soma_origem_itens = round(sum(float(p[5]) for p in pedidos_tratados), 2)
    soma_destino_itens = round(
        float(
            conn.execute(
                "SELECT COALESCE(SUM(valor_itens), 0.0) AS total FROM pedidos"
            ).fetchone()["total"]
        ),
        2,
    )
    diferenca_valor_itens = round(abs(soma_origem_itens - soma_destino_itens), 4)

    return {
        "clientes_origem": len(clientes_tratados),
        "produtos_origem": len(produtos_tratados),
        "pedidos_lidos_brutos": len(pedidos_brutos),
        "pedidos_duplicados_descartados": stats_pedidos["pedidos_duplicados_descartados"],
        "pedidos_origem_unicos": len(pedidos_tratados),
        "itens_origem": len(itens_tratados),
        "soma_origem_itens": soma_origem_itens,
        "soma_destino_itens": soma_destino_itens,
        "diferenca_valor_itens": diferenca_valor_itens,
        "dentro_tolerancia": diferenca_valor_itens <= 0.01,
    }


def montar_relatorio_markdown(
    contagens: dict[str, int],
    integridade: dict[str, int],
    financeiro: dict,
    reconciliacao: dict,
) -> str:
    linhas = [
        "# Relatório de Auditoria Pós-Carga — Verdejar",
        "",
        "## 1. Reconciliação Origem (Brutos) vs. Destino (SQLite)",
        "",
        "| Métrica | Origem (Tratada) | Destino (SQLite) | Status |",
        "|---|---:|---:|:---:|",
        f"| Clientes únicos | {reconciliacao['clientes_origem']} | {contagens['clientes']} | {'OK' if reconciliacao['clientes_origem'] == contagens['clientes'] else 'ATENÇÃO'} |",
        f"| Produtos únicos | {reconciliacao['produtos_origem']} | {contagens['produtos']} | {'OK' if reconciliacao['produtos_origem'] == contagens['produtos'] else 'ATENÇÃO'} |",
        f"| Pedidos únicos (`{reconciliacao['pedidos_lidos_brutos']}` lidos, `{reconciliacao['pedidos_duplicados_descartados']}` duplicados descartados) | {reconciliacao['pedidos_origem_unicos']} | {contagens['pedidos']} | {'OK' if reconciliacao['pedidos_origem_unicos'] == contagens['pedidos'] else 'ATENÇÃO'} |",
        f"| Itens de pedido | {reconciliacao['itens_origem']} | {contagens['itens_pedido']} | {'OK' if reconciliacao['itens_origem'] == contagens['itens_pedido'] else 'ATENÇÃO'} |",
        f"| Soma total de `valor_itens` (R$) | {reconciliacao['soma_origem_itens']:.2f} | {reconciliacao['soma_destino_itens']:.2f} | {'OK' if reconciliacao['dentro_tolerancia'] else 'ATENÇÃO'} |",
        "",
        f"- Diferença absoluta na soma de `valor_itens`: **R$ {reconciliacao['diferenca_valor_itens']:.4f}** (tolerância máxima: `R$ 0.01`).",
        "",
        "## 2. Integridade Referencial e Formatação",
        "",
        "| Verificação | Ocorrências | Status |",
        "|---|---:|:---:|",
        f"| Violações de chave estrangeira (`PRAGMA foreign_key_check`) | {integridade['violacoes_fk']} | {'OK' if integridade['violacoes_fk'] == 0 else 'ATENÇÃO'} |",
        f"| Estados fora do padrão `XX` maiúsculo | {integridade['estados_invalidos']} | {'OK' if integridade['estados_invalidos'] == 0 else 'ATENÇÃO'} |",
        f"| Datas `cadastro_em` fora de `YYYY-MM-DD` | {integridade['datas_clientes_invalidas']} | {'OK' if integridade['datas_clientes_invalidas'] == 0 else 'ATENÇÃO'} |",
        f"| Datas `data_pedido` fora de `YYYY-MM-DD` | {integridade['datas_pedidos_invalidas']} | {'OK' if integridade['datas_pedidos_invalidas'] == 0 else 'ATENÇÃO'} |",
        f"| Clientes com e-mail ausente/nulo | {integridade['emails_nulos']} | Informativo |",
        "",
        "## 3. Consistência Financeira e Pedidos Divergentes",
        "",
        f"- Total geral de vendas (`SUM(valor_itens)`): **R$ {financeiro['total_geral_itens']:.2f}**",
        f"- Pedidos conformes (`divergente = 0`): **{financeiro['pedidos_conformes']}**",
        f"- Pedidos divergentes (`divergente = 1`): **{financeiro['pedidos_divergentes']}**",
        f"- Inconsistências entre `pedidos.valor_itens` e soma de `itens_pedido`: **{financeiro['divergencias_soma']}**",
        "",
        "### Amostra de Pedidos Divergentes (até 10 registros)",
        "",
    ]

    if not financeiro["exemplos"]:
        linhas.append("Nenhum pedido divergente encontrado.")
    else:
        linhas.extend(
            [
                "| Pedido ID | Data | Status | Valor Total | Valor Itens | Diferença | Qtd. Itens |",
                "|---:|:---:|:---|---:|---:|---:|---:|",
            ]
        )
        for ex in financeiro["exemplos"]:
            linhas.append(
                f"| {ex['id']} | {ex['data_pedido']} | {ex['status']} | "
                f"{ex['valor_total']:.2f} | {ex['valor_itens']:.2f} | "
                f"{ex['diferenca']:.2f} | {ex['qtd_itens']} |"
            )

    linhas.append("")
    return "\n".join(linhas)


def anexar_relatorio_qualidade_csv(
    caminho_csv: Path,
    integridade: dict[str, int],
    financeiro: dict,
    reconciliacao: dict,
) -> None:
    escrever_cabecalho = (not caminho_csv.exists()) or caminho_csv.stat().st_size == 0
    executado_em = datetime.now().astimezone().isoformat()

    linha = {
        "executado_em": executado_em,
        "pedidos_duplicados_descartados": int(reconciliacao["pedidos_duplicados_descartados"]),
        "violacoes_fk": int(integridade["violacoes_fk"]),
        "estados_invalidos": int(integridade["estados_invalidos"]),
        "datas_clientes_invalidas": int(integridade["datas_clientes_invalidas"]),
        "datas_pedidos_invalidas": int(integridade["datas_pedidos_invalidas"]),
        "emails_nulos": int(integridade["emails_nulos"]),
        "pedidos_divergentes": int(financeiro["pedidos_divergentes"]),
        "divergencias_soma": int(financeiro["divergencias_soma"]),
    }

    with caminho_csv.open("a", encoding="utf-8", newline="") as arq:
        escritor = csv.DictWriter(arq, fieldnames=COLUNAS_QUALIDADE)
        if escrever_cabecalho:
            escritor.writeheader()
        escritor.writerow(linha)


def main() -> None:
    try:
        conn = abrir_conexao_somente_leitura(DB_PATH)
        try:
            contagens = consultar_contagens(conn)
            integridade = consultar_integridade(conn)
            financeiro = consultar_consistencia_financeira(conn)
            reconciliacao = consultar_reconciliacao_origem(conn)
        finally:
            conn.close()

        conteudo = montar_relatorio_markdown(
            contagens, integridade, financeiro, reconciliacao
        )
        RELATORIO_PATH.write_text(conteudo, encoding="utf-8")
        anexar_relatorio_qualidade_csv(
            QUALIDADE_CSV_PATH, integridade, financeiro, reconciliacao
        )
    except (FileNotFoundError, RuntimeError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"erro na auditoria: {exc}")
        raise SystemExit(1) from exc

    print(
        f"Auditoria concluída. Relatório gerado em: {RELATORIO_PATH} | "
        f"Qualidade CSV atualizado em: {QUALIDADE_CSV_PATH}"
    )


if __name__ == "__main__":
    main()