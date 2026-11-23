# Projeto Verdejar — Pipeline ETL e Auditoria de Dados

Pipeline de extração, transformação, carga e auditoria de dados desenvolvido em Python 3.12 e SQLite para o desafio técnico Verdejar, utilizando o **Caminho C** (contingência SQLite local).

## Objetivo

Implementar um fluxo ETL capaz de extrair dados de uma API local e de um arquivo CSV, realizar limpeza, padronização e validação das informações, carregar os dados em um banco SQLite e verificar a consistência entre os dados de origem e destino.

O projeto contempla regras de transformação, tratamento de duplicidades, integridade referencial, reconciliação financeira e testes automatizados.

## Arquitetura e Decisões Técnicas

- **Banco de dados (Caminho C):** utilização do SQLite (`verdejar.db`), seguindo o esquema definido em `insumos/schema_sqlite.sql`. As conexões habilitam `PRAGMA foreign_keys = ON` para impor integridade referencial entre `clientes`, `produtos`, `pedidos` e `itens_pedido`.
- **Idempotência:** o `03_transformar.py` limpa os dados anteriores na ordem inversa das dependências antes de realizar uma nova carga, garantindo resultados consistentes em execuções repetidas.
- **Transformações (A1–A6):** padronização de datas para `AAAA-MM-DD`, normalização de UFs em duas letras maiúsculas, conversão de e-mails vazios ou compostos apenas por espaços em `NULL` e tratamento de valores numéricos e monetários.
- **Tratamento de duplicidades:** deduplicação de pedidos, mantendo a primeira ocorrência.
- **Consistência financeira:** identificação de pedidos divergentes quando `abs(valor_total - valor_itens) > 0.01`, com registro do indicador `divergente = 1`.
- **Auditoria:** comparação dos dados tratados na origem com os registros carregados no SQLite, incluindo contagens, integridade referencial e reconciliação financeira.

## Estrutura do Repositório

| Arquivo / Pasta | Responsabilidade |
|---|---|
| `01_extrair.py` | Extração paginada da API local (`/clientes` e `/pedidos`) e cópia de `produtos.csv` para `brutos/`. |
| `02_inspecionar.py` | Inspeção exploratória dos dados brutos e contagem de anomalias. |
| `03_transformar.py` | Aplicação das regras de transformação, reconciliação e carga idempotente no SQLite. |
| `04_auditar.py` | Auditoria somente leitura e geração de `auditoria_verdejar.md`. |
| `tests/test_transformar.py` | Testes automatizados das regras de transformação e reconciliação com `pytest`. |
| `consultas_validacao.sql` | Consultas de vendas mensais, consistência financeira, pedidos por UF e pedidos divergentes. |
| `CONTRATO_DE_DADOS.md` | Documentação dos campos, tipos, nulidade e regras de transformação por tabela. |
| `auditoria_verdejar.md` | Relatório de auditoria gerado automaticamente. |
| `COMO_USEI_IA.md` | Registro do uso de IA como ferramenta auxiliar, incluindo decisões, validações, sugestões rejeitadas e correções realizadas. |

## Requisitos

- Python 3.12
- SQLite (disponível na biblioteca padrão do Python)
- Ambiente virtual Python (`venv`)
- `pytest` para execução dos testes automatizados

## Instalação e Configuração

Clone o repositório e acesse a pasta do projeto.

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências de desenvolvimento:

```powershell
pip install pytest
```

## Como Executar

Os comandos abaixo devem ser executados na raiz do projeto, com o ambiente virtual ativo.

### 1. Iniciar a API local

Em um terminal separado, execute:

```powershell
python .\insumos\api_verdejar.py --dados .\insumos\dados
```

Mantenha a API em execução durante a etapa de extração.

### 2. Extrair os dados brutos

Em outro terminal, na raiz do projeto:

```powershell
python .\01_extrair.py
```

O script consulta os endpoints de clientes e pedidos e copia o arquivo de produtos para a pasta `brutos/`.

### 3. Inspecionar os dados extraídos

```powershell
python .\02_inspecionar.py
```

Essa etapa apresenta informações sobre os dados brutos e as anomalias identificadas.

### 4. Transformar e carregar os dados

```powershell
python .\03_transformar.py
```

O script aplica as regras A1–A6, trata duplicidades e realiza a carga idempotente no banco `verdejar.db`.

### 5. Executar a auditoria

```powershell
python .\04_auditar.py
```

A auditoria compara os dados de origem com o banco SQLite, verifica a integridade referencial e a consistência financeira, gerando o relatório `auditoria_verdejar.md`.

### 6. Executar as consultas SQL de validação

As consultas disponíveis em `consultas_validacao.sql` podem ser executadas no SQLite por meio de uma ferramenta compatível, como o DB Browser for SQLite, ou via `sqlite3` / Python sobre `verdejar.db`.

### 7. Executar os testes automatizados

```powershell
pytest -v
```

A suíte verifica as regras de transformação e a reconciliação dos dados.

## Resultados e Validações

Após a execução do pipeline, foram obtidos os seguintes resultados:

### Extração

| Recurso | Páginas | Registros |
|---|---:|---:|
| Clientes | 5 | 1.000 |
| Pedidos | 26 | 5.100 |
| Produtos CSV | — | OK |

### Carga e auditoria

| Indicador | Resultado |
|---|---:|
| Clientes carregados | 1.000 |
| Produtos carregados | 12 |
| Pedidos únicos | 5.000 |
| Pedidos duplicados descartados | 100 |
| Itens de pedido | 12.455 |
| Pedidos divergentes | 238 |
| Violações de chave estrangeira | 0 |
| Total financeiro (`valor_itens`) | R$ 311.228,75 |
| Diferença na reconciliação | R$ 0,0000 |

A reconciliação financeira apresentou correspondência entre a origem tratada e o banco SQLite, com diferença de `R$ 0,0000`, dentro da tolerância estabelecida de `R$ 0,01`.

### Consultas SQL

A soma das vendas mensais apresentou correspondência com o total geral de `valor_itens`:

- **Soma mensal:** `311228.75`
- **Total geral:** `311228.75`
- **Diferença:** `0.0`

### Testes automatizados

Execução de `pytest -v`:

```text
7 passed
```

Todos os sete testes automatizados foram aprovados.

## Documentação Complementar

- `CONTRATO_DE_DADOS.md`: detalhamento das regras de transformação e estrutura dos dados.
- `auditoria_verdejar.md`: relatório gerado após a carga e execução da auditoria.
- `COMO_USEI_IA.md`: documentação transparente sobre o uso de IA como ferramenta auxiliar durante o desenvolvimento.

Projeto desenvolvido para o desafio técnico Verdejar.