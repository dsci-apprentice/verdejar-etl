# Relatório de Auditoria Pós-Carga — Verdejar

## 1. Reconciliação Origem (Brutos) vs. Destino (SQLite)

| Métrica | Origem (Tratada) | Destino (SQLite) | Status |
|---|---:|---:|:---:|
| Clientes únicos | 1000 | 1000 | OK |
| Produtos únicos | 12 | 12 | OK |
| Pedidos únicos (`5100` lidos, `100` duplicados descartados) | 5000 | 5000 | OK |
| Itens de pedido | 12455 | 12455 | OK |
| Soma total de `valor_itens` (R$) | 311228.75 | 311228.75 | OK |

- Diferença absoluta na soma de `valor_itens`: **R$ 0.0000** (tolerância máxima: `R$ 0.01`).

## 2. Integridade Referencial e Formatação

| Verificação | Ocorrências | Status |
|---|---:|:---:|
| Violações de chave estrangeira (`PRAGMA foreign_key_check`) | 0 | OK |
| Estados fora do padrão `XX` maiúsculo | 0 | OK |
| Datas `cadastro_em` fora de `YYYY-MM-DD` | 0 | OK |
| Datas `data_pedido` fora de `YYYY-MM-DD` | 0 | OK |
| Clientes com e-mail ausente/nulo | 81 | Informativo |

## 3. Consistência Financeira e Pedidos Divergentes

- Total geral de vendas (`SUM(valor_itens)`): **R$ 311228.75**
- Pedidos conformes (`divergente = 0`): **4762**
- Pedidos divergentes (`divergente = 1`): **238**
- Inconsistências entre `pedidos.valor_itens` e soma de `itens_pedido`: **0**

### Amostra de Pedidos Divergentes (até 10 registros)

| Pedido ID | Data | Status | Valor Total | Valor Itens | Diferença | Qtd. Itens |
|---:|:---:|:---|---:|---:|---:|---:|
| 1 | 2026-02-19 | entregue | 125.84 | 130.84 | -5.00 | 3 |
| 51 | 2026-04-27 | cancelado | 26.58 | 23.58 | 3.00 | 1 |
| 71 | 2026-05-27 | cancelado | 144.35 | 134.35 | 10.00 | 3 |
| 81 | 2026-09-05 | entregue | -1.84 | 3.16 | -5.00 | 1 |
| 106 | 2026-05-02 | em_transporte | 47.78 | 44.78 | 3.00 | 2 |
| 176 | 2026-03-20 | em_transporte | 137.69 | 134.69 | 3.00 | 3 |
| 186 | 2026-09-16 | em_transporte | 143.51 | 133.51 | 10.00 | 4 |
| 289 | 2026-04-12 | cancelado | 79.40 | 76.40 | 3.00 | 4 |
| 303 | 2026-06-28 | em_transporte | 120.25 | 110.25 | 10.00 | 3 |
| 326 | 2026-02-18 | entregue | 10.58 | 7.58 | 3.00 | 1 |
