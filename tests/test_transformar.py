from pathlib import Path
import importlib.util
import sqlite3


def carregar_modulo_transformar():
    raiz = Path(__file__).resolve().parent.parent
    caminho_script = raiz / "03_transformar.py"
    spec = importlib.util.spec_from_file_location("transformar_mod", caminho_script)
    modulo = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def test_normalizar_data():
    mod = carregar_modulo_transformar()
    data_iso, foi_barra = mod.normalizar_data("25/11/2026", "pedidos.data_pedido")
    assert data_iso == "2026-11-25"
    assert foi_barra is True

    data_iso_iso, foi_barra_iso = mod.normalizar_data("2026-11-25", "pedidos.data_pedido")
    assert data_iso_iso == "2026-11-25"
    assert foi_barra_iso is False


def test_parse_numero():
    mod = carregar_modulo_transformar()
    valor, convertido = mod.parse_numero("R$ 1.234,56", "pedidos.valor_total")
    assert round(valor, 2) == 1234.56
    assert convertido is True


def test_email_vazio_vira_nulo():
    mod = carregar_modulo_transformar()
    clientes_brutos = [
        {
            "id": 1,
            "nome": "Ana",
            "email": "   ",
            "cidade": "Manaus",
            "estado": "AM",
            "cadastro_em": "2026-02-01",
        }
    ]
    linhas, stats = mod.transformar_clientes(clientes_brutos)
    assert linhas[0][2] is None
    assert stats["emails_nulos"] == 1


def test_normalizar_estado_uf():
    mod = carregar_modulo_transformar()
    clientes_brutos = [
        {
            "id": 1,
            "nome": "Ana",
            "email": "ana@exemplo.com",
            "cidade": "Manaus",
            "estado": "am",
            "cadastro_em": "2026-02-01",
        }
    ]
    linhas, stats = mod.transformar_clientes(clientes_brutos)
    assert linhas[0][4] == "AM"
    assert stats["estados_normalizados"] == 1


def test_deduplicar_pedidos():
    mod = carregar_modulo_transformar()
    pedidos_brutos = [
        {
            "id": 100,
            "cliente_id": 1,
            "data_pedido": "2026-05-10",
            "status": "pago",
            "valor_total": 100.00,
            "itens": [{"produto_id": 10, "quantidade": 2, "preco_unitario": 50.00}],
        },
        {
            "id": 100,
            "cliente_id": 1,
            "data_pedido": "2026-05-10",
            "status": "cancelado",
            "valor_total": 999.00,
            "itens": [{"produto_id": 10, "quantidade": 1, "preco_unitario": 999.00}],
        },
    ]
    pedidos, itens, stats = mod.transformar_pedidos_e_itens(pedidos_brutos)
    assert len(pedidos) == 1
    assert pedidos[0][3] == "pago"
    assert stats["pedidos_duplicados_descartados"] == 1
    assert len(itens) == 1


def test_marcar_pedido_divergente():
    mod = carregar_modulo_transformar()
    pedidos_brutos = [
        {
            "id": 101,
            "cliente_id": 1,
            "data_pedido": "2026-05-11",
            "status": "pago",
            "valor_total": 80.00,
            "itens": [{"produto_id": 10, "quantidade": 1, "preco_unitario": 50.00}],
        }
    ]
    pedidos, _, stats = mod.transformar_pedidos_e_itens(pedidos_brutos)
    assert pedidos[0][6] == 1
    assert stats["pedidos_divergentes"] == 1


def test_reconciliacao_dados():
    mod = carregar_modulo_transformar()
    raiz = Path(__file__).resolve().parent.parent
    db_path = raiz / "verdejar.db"
    assert db_path.is_file(), "verdejar.db não encontrado; rode 03_transformar.py antes"

    pedidos_brutos = mod.carregar_json_lista(
        raiz / "brutos" / "pedidos" / "pedidos_brutos.json",
        "pedidos",
    )
    pedidos_calc, _, _ = mod.transformar_pedidos_e_itens(pedidos_brutos)
    soma_origem_valor_itens = round(sum(p[5] for p in pedidos_calc), 2)
    qtd_origem_unicos = len(pedidos_calc)

    with sqlite3.connect(db_path) as conn:
        qtd_destino, soma_destino = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(valor_itens), 0) FROM pedidos"
        ).fetchone()

    assert qtd_destino == qtd_origem_unicos
    assert abs(float(soma_destino) - soma_origem_valor_itens) <= 0.01