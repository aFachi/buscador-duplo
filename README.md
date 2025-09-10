# Buscador Duplo (Somente Desktop)

Aplicativo desktop para busca de autopeças. Removeu-se a parte web para uso local
no Windows, com UI moderna via `ttk` e resultados em tabela.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure as credenciais do Firebird em `config.ini` ou via variáveis de
ambiente (arquivo `.env`). Exemplo:

```ini
[FIREBIRD]
HOST=localhost
DATABASE=/caminho/para/banco.fdb
USER=sysdba
PASSWORD=masterkey
```

## Executando

```bash
python desktop.py
```

Para gerar um executável (Windows), instale o [PyInstaller](https://pyinstaller.org/)
e execute:

```bash
pyinstaller --noconfirm --onefile --windowed --name BuscadorDuplo desktop.py
```
O executável ficará em `dist/BuscadorDuplo.exe`.

### Inspecionar a base

Use o utilitário de inspeção para descobrir tabela/colunas e validar o caminho
do FDB:

```bash
python inspect_firebird.py
```

## Testes

```bash
pytest
```

### Teste de integração com Firebird

Um teste opcional cria um banco Firebird temporário para validar o fluxo de
sincronização e busca. É necessário ter um servidor Firebird local em
`localhost:3050`; caso contrário o teste será ignorado.

```
codex/implement-auto-complete-search-for-products-0tioi7
pytest tests/test_firebird_integration.py
pytest test_firebird_integration.py

```

## Configuração via `.env`

Mínimo:

```
FIREBIRD_HOST=localhost
FIREBIRD_PORT=3050
FIREBIRD_USER=sysdba
FIREBIRD_PASSWORD=masterkey
FIREBIRD_DATABASE=BASESGMASTER1.FDB
```

Mapeamento opcional de colunas (caso a auto-descoberta não acerte a tabela):

```
FIREBIRD_TABLE=ESTOQUE_ITENS
FIREBIRD_COL_CODIGO=CODIGO
FIREBIRD_COL_DESCRICAO=PRODUTO
FIREBIRD_COL_ESTOQUE=QTDE
FIREBIRD_COL_PRECO=PRECOVENDA
FIREBIRD_COL_FORNECEDOR=FORNECEDOR
FIREBIRD_COL_MARCA=MARCA
FIREBIRD_COL_GRUPO=GRUPO
FIREBIRD_COL_SUBGRUPO=SUBGRUPO
```

Ou defina um SELECT completo com JOINs (deve conter `{placeholders}` e aliases
exatos `CODIGO, DESCRICAO, BARRAS, PRECO, ESTOQUE, FORNECEDOR, MARCA, GRUPO, SUBGRUPO`):

```
FIREBIRD_FULL_SQL=SELECT ... WHERE P.CODIGO IN ({placeholders})
```
