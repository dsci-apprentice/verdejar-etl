from collections import Counter
import csv
import json
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
BRUTOS_DIR = BASE_DIR / "brutos"


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


def valor_vazio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str) and not valor.strip():
        return True
    return False


def assinatura_padrao(valor) -> str:
    if valor is None:
        return "NONE"
    texto = str(valor).strip()
    if not texto:
        return "VAZIO"
    if len(texto) > 30:
        texto = texto[:30]
    comprimida = re.sub(r"[A-Za-zÀ-ÿ]+", "A", texto)
    comprimida = re.sub(r"[0-9]+", "9", comprimida)
    return comprimida


def parse_numero(valor) -> tuple[float | None, bool]:
    if valor is None:
        return None, False
    # bool é subclasse de int em Python e não deve passar como número válido
    if isinstance(valor, bool):
        return None, True
    if isinstance(valor, (int, float)):
        return float(valor), False
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return None, False
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto), False
    except ValueError:
        return None, True


def classificar_data(valor) -> str:
    if valor_vazio(valor):
        return "VAZIA/NULA"
    texto = str(valor).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return "YYYY-MM-DD"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        return "DD/MM/YYYY"
    return f"OUTRO ({assinatura_padrao(texto)})"


def auditar_esquema_e_vazios(registros: list[dict], nome: str) -> None:
    if not registros:
        print(f"[{nome}] sem registros para auditar esquema.")
        return

    contagem_chaves: Counter[str] = Counter()
    vazios_por_campo: Counter[str] = Counter()

    for reg in registros:
        for chave, val in reg.items():
            contagem_chaves[chave] += 1
            if valor_vazio(val):
                vazios_por_campo[chave] += 1

    total = len(registros)
    incompletas = {k: v for k, v in contagem_chaves.items() if v < total}
    print(f"  Esquema {nome} ({total} regs): campos={sorted(contagem_chaves.keys())}")
    if incompletas:
        print(f"    Chaves parciais (presentes/total): {incompletas}")
    if vazios_por_campo:
        print(f"    Campos com valores nulos/vazios: {dict(vazios_por_campo)}")


def auditar_chaves_e_integridade(
    clientes: list[dict], pedidos: list[dict], produtos: list[dict[str, str]]
) -> None:
    ids_clientes = [c.get("id") for c in clientes]
    dup_clientes = sum(1 for _, qtd in Counter(ids_clientes).items() if qtd > 1)
    set_clientes = {cid for cid in ids_clientes if cid is not None}

    ids_produtos = [p.get("produto_id") for p in produtos]
    dup_produtos = sum(1 for _, qtd in Counter(ids_produtos).items() if qtd > 1)
    set_produtos = {pid for pid in ids_produtos if pid is not None}

    ids_pedidos = [p.get("id") for p in pedidos]
    dup_pedidos = sum(1 for _, qtd in Counter(ids_pedidos).items() if qtd > 1)

    clientes_orfaos = Counter(
        p.get("cliente_id") for p in pedidos if p.get("cliente_id") not in set_clientes
    )

    chaves_itens: list[tuple[object, int]] = []
    produtos_orfaos = Counter()
    itens_sem_lista = 0

    for p in pedidos:
        pid_pedido = p.get("id")
        itens = p.get("itens")
        if not isinstance(itens, list):
            itens_sem_lista += 1
            continue
        # linha é posicional (1..N) por não haver campo explícito de linha no JSON bruto
        for idx, item in enumerate(itens, start=1):
            if not isinstance(item, dict):
                continue
            chaves_itens.append((pid_pedido, idx))
            prod_id = item.get("produto_id")
            if str(prod_id) not in set_produtos and prod_id not in set_produtos:
                produtos_orfaos[str(prod_id)] += 1

    dup_itens = sum(1 for _, qtd in Counter(chaves_itens).items() if qtd > 1)
    print(
        f"  Duplicatas de chave -> clientes={dup_clientes}, produtos={dup_produtos}, "
        f"pedidos={dup_pedidos}, itens_pedido={dup_itens}"
    )
    print(
        f"  Integridade -> cliente_id órfão={sum(clientes_orfaos.values())} "
        f"({dict(list(clientes_orfaos.items())[:5])}), "
        f"produto_id órfão={sum(produtos_orfaos.values())} "
        f"({dict(list(produtos_orfaos.items())[:5])}), "
        f"pedidos_sem_lista_itens={itens_sem_lista}"
    )


def inspecionar_armadilhas_desafio(clientes: list[dict], pedidos: list[dict]) -> None:
    emails_ausentes = sum(1 for c in clientes if valor_vazio(c.get("email")))
    estados = Counter(c.get("estado") for c in clientes)
    estados_nao_padrao = {
        k: v
        for k, v in estados.items()
        if not isinstance(k, str) or k != k.upper() or len(k) != 2
    }
    datas_cadastro = Counter(classificar_data(c.get("cadastro_em")) for c in clientes)

    ids_pedidos = [p.get("id") for p in pedidos]
    duplicados_paginacao = len(ids_pedidos) - len(set(ids_pedidos))
    datas_pedido = Counter(classificar_data(p.get("data_pedido")) for p in pedidos)

    virgulas_total = 0
    falhas_parse_total = 0
    falhas_parse_itens = 0
    totais_ausentes = 0
    divergencias = 0
    exemplos_divergencia: list[tuple[object, object, float]] = []

    for p in pedidos:
        bruto_total = p.get("valor_total")
        if isinstance(bruto_total, str) and "," in bruto_total:
            virgulas_total += 1

        total_num, erro_total = parse_numero(bruto_total)
        if erro_total:
            falhas_parse_total += 1
        elif total_num is None:
            totais_ausentes += 1

        soma_itens = 0.0
        for item in p.get("itens") or []:
            if not isinstance(item, dict):
                continue
            qtd_num, erro_qtd = parse_numero(item.get("quantidade"))
            preco_num, erro_preco = parse_numero(item.get("preco_unitario"))
            if erro_qtd or erro_preco:
                falhas_parse_itens += 1
            soma_itens += (qtd_num or 0.0) * (preco_num or 0.0)

        soma_itens = round(soma_itens, 2)
        if total_num is not None and not erro_total and round(total_num, 2) != soma_itens:
            divergencias += 1
            if len(exemplos_divergencia) < 3:
                exemplos_divergencia.append((p.get("id"), bruto_total, soma_itens))

    print(f"  1. E-mails ausentes/vazios em clientes: {emails_ausentes}")
    print(f"  2. Estados fora do padrão 'XX' maiúsculo: {estados_nao_padrao} | todos={dict(estados)}")
    print(f"  3. Formatos cadastro_em={dict(datas_cadastro)} | data_pedido={dict(datas_pedido)}")
    print(
        f"  4. valor_total com vírgula={virgulas_total} | "
        f"falhas_parse_total={falhas_parse_total} | "
        f"falhas_parse_itens={falhas_parse_itens} | totais_ausentes={totais_ausentes}"
    )
    print(f"  5. Pedidos duplicados (total - únicos): {duplicados_paginacao}")
    print(
        f"  6. Divergências valor_total vs soma itens: {divergencias} "
        f"(exemplos id, bruto, soma_itens={exemplos_divergencia})"
    )


def main() -> None:
    try:
        clientes = carregar_json_lista(BRUTOS_DIR / "clientes" / "clientes_brutos.json", "clientes")
        pedidos = carregar_json_lista(BRUTOS_DIR / "pedidos" / "pedidos_brutos.json", "pedidos")
        produtos = carregar_produtos_csv(BRUTOS_DIR / "produtos.csv")
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"erro na inspeção: {exc}")
        raise SystemExit(1) from exc

    print("=== CAMADA 1: VERIFICAÇÕES GENÉRICAS (ESQUEMA, VAZIOS, CHAVES E INTEGRIDADE) ===")
    auditar_esquema_e_vazios(clientes, "clientes")
    auditar_esquema_e_vazios(pedidos, "pedidos")
    auditar_esquema_e_vazios(produtos, "produtos.csv")
    auditar_chaves_e_integridade(clientes, pedidos, produtos)

    print("\n=== CAMADA 2: VERIFICAÇÕES ESPECÍFICAS DO DESAFIO (6 ARMADILHAS) ===")
    inspecionar_armadilhas_desafio(clientes, pedidos)


if __name__ == "__main__":
    main()