# Como usei IA

Utilizei a IA generativa (Gemini) como ferramenta auxiliar durante o desenvolvimento do projeto, principalmente para esclarecer conceitos, discutir alternativas de implementação, revisar código e apoiar a investigação de inconsistências.

A condução do desenvolvimento, entretanto, ficou sob minha responsabilidade. Analisei as sugestões recebidas, avaliei sua adequação aos requisitos do desafio e decidi quais mudanças seriam incorporadas, adaptadas ou descartadas. As implementações e decisões finais foram orientadas pela compreensão da solução, pela necessidade de manter o projeto simples e reproduzível e, principalmente, pelos resultados das validações realizadas.

A seguir, registro as principais contribuições da ferramenta, as decisões que tomei e como verifiquei os resultados.

## Sugestões aceitas

- **Simplificação de comentários e padronização textual (`01_extrair.py` e `02_inspecionar.py`)**
  - **Contexto:** durante a revisão dos scripts, identifiquei oportunidades de melhorar a legibilidade, especialmente na quantidade de comentários e na padronização das mensagens.
  - **Decisão:** optei por remover comentários redundantes, manter explicações apenas para regras não evidentes, utilizar identificadores em `snake_case` e padronizar as mensagens em português com acentuação UTF-8.
  - **Validação:** comparei as saídas de extração e inspeção bruta, confirmando a preservação dos resultados: `1000` clientes, `5100` pedidos, `12` produtos e as contagens das anomalias identificadas.

- **Contadores textuais simples e tratamento de erros na extração (`01_extrair.py`)**
  - **Contexto:** o requisito de apresentar uma saída textual limpa exigia evitar cores e barras de progresso, além de tratar explicitamente possíveis falhas de conexão, respostas HTTP inválidas e páginas inexistentes.
  - **Decisão:** adotei contadores padronizados de páginas e registros por recurso e implementei encerramento com mensagens claras para situações de erro, evitando *tracebacks* não tratados.
  - **Validação:** executei o script contra a API local e conferi os resultados: `clientes_paginas=5`, `clientes_registros=1000`, `pedidos_paginas=26`, `pedidos_registros=5100` e `produtos_csv=ok`.

- **Auditoria pós-carga e reconciliação origem vs. destino (`04_auditar.py`)**
  - **Contexto:** ao avaliar o fluxo completo de dados, identifiquei a necessidade de uma etapa independente para conferir os resultados após a carga no banco e comparar os dados de origem com os armazenados no SQLite.
  - **Decisão:** desenvolvi um script de auditoria somente leitura (`?mode=ro`), responsável por gerar automaticamente o `auditoria_verdejar.md`, com reconciliação de contagens e comparação da soma de `valor_itens`, considerando tolerância de `R$ 0,01`.
  - **Justificativa:** busquei garantir uma conferência independente dos volumes, da integridade referencial e da consistência financeira, sem modificar os dados ou introduzir dependências desnecessárias.
  - **Validação:** executei o `03_transformar.py` e, em seguida, o `04_auditar.py` sobre `verdejar.db` e `brutos/`. Confirmei os seguintes resultados: `1000` clientes, `12` produtos, `5000` pedidos únicos (`100` duplicados descartados), `12455` itens, total de `R$ 311228.75`, diferença de `R$ 0.0000`, nenhuma violação de FK e `238` pedidos divergentes.

- **Contrato de dados, testes automatizados e consultas SQL (`CONTRATO_DE_DADOS.md`, `tests/test_transformar.py` e `consultas_validacao.sql`)**
  - **Contexto:** para tornar as regras de transformação mais claras e verificáveis, identifiquei a necessidade de documentar as regras A1–A6 por tabela e complementar a implementação com testes automatizados e consultas SQL de validação.
  - **Decisão:** estruturei o `CONTRATO_DE_DADOS.md`, a suíte `tests/test_transformar.py` e o arquivo `consultas_validacao.sql`, contemplando vendas mensais com `strftime`, consistência da soma mensal com o total geral, pedidos por UF e pedidos divergentes.
  - **Validação:** executei `pytest -v`, obtendo `7 passed`, e rodei as consultas sobre `verdejar.db`, confirmando a correspondência entre a soma mensal e o total geral de `311228.75`, com diferença de `0.0`.

## Sugestões rejeitadas

- **Considerar explicada a diferença entre 241 e 238 pedidos divergentes sem conferir os registros**
  - **Contexto:** durante a análise, surgiu a hipótese de que a diferença entre a inspeção dos dados brutos e a carga final seria consequência da remoção de pedidos duplicados.
  - **Decisão:** não aceitei essa explicação apenas pela correspondência aritmética. Considerei necessário verificar os registros envolvidos antes de concluir a análise.
  - **Validação:** realizei o cruzamento dos registros de `pedidos_brutos.json` com o banco SQLite e confirmei que os três pedidos duplicados divergentes (`1678`, `989` e `1710`) possuíam cópias idênticas.

- **Utilizar comandos extensos diretamente no PowerShell para verificações recorrentes**
  - **Contexto:** foram avaliadas alternativas para executar consultas e verificações por meio de comandos *inline*.
  - **Decisão:** optei por substituir comandos extensos por scripts Python independentes, tornando as verificações mais organizadas, legíveis e reproduzíveis.
  - **Justificativa:** essa escolha reduziu problemas de interpretação de aspas e codificação no ambiente Windows, além de manter as rotinas de conferência junto aos demais arquivos do projeto.

- **Incluir seção longa de exemplos no `CONTRATO_DE_DADOS.md` e manter nomes/escopos amplos nos testes**
  - **Contexto:** durante a revisão da documentação e dos testes, avaliei o nível de detalhamento necessário para explicar as regras e facilitar a manutenção.
  - **Decisão:** preferi manter o `CONTRATO_DE_DADOS.md` direto e objetivo, adequado ao nível de complexidade do desafio, e refatorei `tests/test_transformar.py` para utilizar nomes mais curtos e testes menores, com responsabilidades específicas.
  - **Justificativa:** busquei evitar documentação excessiva e favorecer a leitura, a compreensão e a manutenção da suíte de testes.

## Falhas e retrabalho

- **Problemas de execução de comandos inline no PowerShell**
  - **Falha encontrada:** durante as verificações, comandos executados por `python -c` e *here-string* apresentaram problemas de *parsing*, *escaping* de aspas e leitura de BOM (`U+FEFF`).
  - **Correção realizada:** adaptei a abordagem e passei a utilizar scripts Python independentes, com leitura explícita dos arquivos e tratamento adequado das codificações (`utf-8` / `utf-8-sig`).
  - **Resultado:** consegui executar as verificações de forma mais estável e reproduzível, incluindo a conferência das cópias dos pedidos duplicados.

- **Execução direta do arquivo de teste pelo Python em vez do `pytest`**
  - **Falha encontrada:** inicialmente, `tests/test_transformar.py` foi executado diretamente pelo lançador/debugger do Python, produzindo uma saída vazia sem efetivamente executar os testes.
  - **Correção realizada:** identifiquei a necessidade de utilizar o executor apropriado e passei a executar `pytest -v` na raiz do projeto, com o ambiente virtual ativo.
  - **Resultado:** confirmei a execução efetiva da suíte, com todos os `7` testes aprovados (`7 passed`).