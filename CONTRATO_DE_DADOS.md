# Contrato de dados — Projeto Verdejar

Este documento descreve a estrutura, os tipos no SQLite (caminho C, `verdejar.db`), as regras de nulidade/integridade e as transformações aplicadas pelo pipeline antes da carga.

## Diretrizes gerais do destino (SQLite)

- **Chaves estrangeiras:** `PRAGMA foreign_keys = ON` ativo na conexão de carga.
- **Ordem de carga:** `produtos`, `clientes`, `pedidos` e `itens_pedido` (limpeza na ordem inversa das dependências antes da inserção para manter a carga idempotente).
- **Datas:** armazenadas como texto no formato ISO `AAAA-MM-DD` (`%Y-%m-%d`).
- **Indicadores booleanos:** armazenados como inteiro `0` ou `1`.
- **Valores monetários:** convertidos para número decimal arredondado a duas casas decimais (`round(..., 2)`).

---

## 1. Tabela `clientes`

- **Origem bruta:** `brutos/clientes/clientes_brutos.json` (extraído de `/clientes`).
- **Chave primária:** `id`.
- **Chaves estrangeiras:** nenhuma.

| Campo | Tipo SQLite | Nulidade | Regra de transformação e validação |
|---|---|---:|---|
| `id` | `INTEGER` | `NOT NULL` (`PK`) | Convertido para inteiro (`int`); registros com `id` já visto são ignorados. |
| `nome` | `TEXT` | `NOT NULL` | Convertido para `str` com remoção de espaços nas extremidades (`.strip()`). |
| `email` | `TEXT` | Permite `NULL` | **Armadilha A1:** strings vazias ou apenas espaços viram `NULL` (`None` no Python) e são contabilizadas em `emails_nulos`; e-mails não vazios recebem `.strip()`. |
| `cidade` | `TEXT` | `NOT NULL` | Convertido para `str` com `.strip()`. |
| `estado` | `TEXT` | `NOT NULL` | **Armadilha A2:** convertido para maiúsculas (`.upper()`) e `.strip()`; exige exatamente 2 caracteres (`CHECK (length(estado) = 2)`). |
| `cadastro_em` | `TEXT` | `NOT NULL` | **Armadilha A3:** normalizado para `AAAA-MM-DD` a partir de `%Y-%m-%d` ou `%d/%m/%Y`. |

---

## 2. Tabela `produtos`

- **Origem bruta:** `brutos/produtos.csv` (copiado de `insumos/dados/produtos.csv`).
- **Chave primária:** `produto_id`.
- **Chaves estrangeiras:** nenhuma.

| Campo | Tipo SQLite | Nulidade | Regra de transformação e validação |
|---|---|---:|---|
| `produto_id` | `INTEGER` | `NOT NULL` (`PK`) | Convertido para inteiro (`int`); deduplicado por `produto_id`. |
| `nome` | `TEXT` | `NOT NULL` | Convertido para `str` com `.strip()`. |
| `categoria` | `TEXT` | `NOT NULL` | Convertido para `str` com `.strip()`. |
| `preco_base` | `NUMERIC` | `NOT NULL` | **Armadilha A4:** convertido para número (`float`) aceitando vírgula decimal/separadores e arredondado a 2 casas decimais. |

---

## 3. Tabela `pedidos`

- **Origem bruta:** `brutos/pedidos/pedidos_brutos.json` (extraído de `/pedidos`).
- **Chave primária:** `id`.
- **Chaves estrangeiras:** `cliente_id` referencia `clientes(id)`.

| Campo | Tipo SQLite | Nulidade | Regra de transformação e validação |
|---|---|---:|---|
| `id` | `INTEGER` | `NOT NULL` (`PK`) | **Armadilha A5:** convertido para inteiro (`int`); pedidos repetidos pelo mesmo `id` mantêm a primeira ocorrência e os demais são descartados (`pedidos_duplicados_descartados`). |
| `cliente_id` | `INTEGER` | `NOT NULL` (`FK`) | Convertido para inteiro (`int`); deve existir em `clientes(id)`. |
| `data_pedido` | `TEXT` | `NOT NULL` | **Armadilha A3:** convertida de `%Y-%m-%d` ou `%d/%m/%Y` para `AAAA-MM-DD`. |
| `status` | `TEXT` | `NOT NULL` | Convertido para `str` com `.strip()`. |
| `valor_total` | `NUMERIC` | `NOT NULL` | **Armadilha A4:** valor informado na origem convertido para número e arredondado a 2 casas decimais. |
| `valor_itens` | `NUMERIC` | `NOT NULL` | **Armadilha A6:** calculado como a soma de `quantidade * preco_unitario` dos itens do pedido, arredondada a 2 casas decimais. |
| `divergente` | `INTEGER` | `NOT NULL` (`DEFAULT 0`) | **Armadilha A6:** `1` quando `abs(valor_total - valor_itens) > 0.01` e `0` caso contrário (`CHECK (divergente IN (0, 1))`). |

---

## 4. Tabela `itens_pedido`

- **Origem bruta:** array `itens` de cada pedido único em `brutos/pedidos/pedidos_brutos.json`.
- **Chave primária:** composta por `(pedido_id, linha)`.
- **Chaves estrangeiras:** `pedido_id` referencia `pedidos(id)` e `produto_id` referencia `produtos(produto_id)`.

| Campo | Tipo SQLite | Nulidade | Regra de transformação e validação |
|---|---|---:|---|
| `pedido_id` | `INTEGER` | `NOT NULL` (`PK`, `FK`) | Identificador do pedido único ao qual o item pertence; deve existir em `pedidos(id)`. |
| `linha` | `INTEGER` | `NOT NULL` (`PK`) | Sequencial inteiro iniciado em `1` (`1, 2, 3...`) para cada item dentro do pedido. |
| `produto_id` | `INTEGER` | `NOT NULL` (`FK`) | Identificador do produto convertido para inteiro (`int`); deve existir em `produtos(produto_id)`. |
| `quantidade` | `INTEGER` | `NOT NULL` | Quantidade do item convertida para inteiro (`int`). |
| `preco_unitario` | `NUMERIC` | `NOT NULL` | **Armadilha A4:** preço unitário convertido para número e arredondado a 2 casas decimais. |