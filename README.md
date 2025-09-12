Objetivo
========

MVP simples para buscar produtos em um banco Firebird 2.5 a partir de um executável Windows. Inclui:

- Teste de conexão/diagnóstico com mensagens claras.
- CLI de busca (`fb_search_cli.py`) que consulta o Firebird e mantém cache local em SQLite.
- Empacotamento em `.exe` via PyInstaller.

Pré‑requisitos
--------------

- Firebird 2.5 (servidor ou cliente) acessível e `fbclient.dll` disponível (no PATH ou ao lado do .exe).
- Porta 3050 aberta até o host do banco.
- Usuário/senha válidos no Firebird e permissões de SELECT nas tabelas de produtos.
- Python 3.9+ instalado para desenvolvimento/empacotamento.

Configuração
------------

1) Copie `.env.example` para `.env` e ajuste:

```
FIREBIRD_HOST=127.0.0.1
FIREBIRD_PORT=3050
FIREBIRD_DATABASE=C:\\dados\\SEU_BANCO.fdb   # ou alias configurado
FIREBIRD_USER=SYSDBA
FIREBIRD_PASSWORD=masterkey
FIREBIRD_CHARSET=WIN1252                     # ou UTF8 conforme seu banco
FIREBIRD_ROLE=
SQL_PRODUCT_QUERY=
```

2) (Opcional) Defina `SQL_PRODUCT_QUERY` para sobrepor a query padrão. Use `?` como placeholder.

Instalação e Teste Rápido
-------------------------

Windows (PowerShell):

```
cd 2_buscadores_bc_autopecas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Teste de conexão e diagnóstico
python fb_probe.py

# Busca rápida
python fb_search_cli.py --term "parafuso" --limit 20
python fb_search_cli.py --term 12345 --limit 5
```

Empacotar em .exe
-----------------

```
pyinstaller -F -n buscador_bc.exe fb_search_cli.py
pyinstaller -F -n fb_probe.exe fb_probe.py

# Garanta que fbclient.dll esteja no mesmo diretório do exe ou no PATH do sistema
```

Uso em Produção (MVP)
---------------------

- Distribua `buscador_bc.exe`, `.env` e (se necessário) `fbclient.dll` juntos.
- O executável lê o `.env`, consulta o Firebird e mantém cache local em `cache.db` (SQLite) atualizando a cada pesquisa.

Problemas comuns e soluções
---------------------------

- Sem retorno/erro silencioso: confirme `fbclient.dll` compatível (32/64 bits), PATH e porta 3050.
- Texto com acentuação errada: ajuste `FIREBIRD_CHARSET` (WIN1252 vs UTF8).
- Tabela não encontrada: cuidado com nomes com aspas (sensível a maiúsculas/minúsculas no Firebird). Tente `SELECT FIRST 1 * FROM RDB$RELATIONS` no `fb_probe.py` para validar.
- Sem ver dados novos: outra aplicação pode não ter feito COMMIT; use transação READ COMMITTED no cliente e confirme no servidor.

Desktop (opcional)
------------------

- Requisitos: `firebirdsql` (já incluso em `requirements.txt`) e `tkinter` (vem com Python oficial no Windows).
- Ajuste `config.ini`. São aceitos `[FIREBIRD]` ou `[firebird]` e chaves `HOST`, `PORT`, `USER`, `PASSWORD`, `DATABASE` (ou `DATABASE_PATH`).
- Para rodar a UI:

```
python desktop.py
```

- A UI tenta um sync inicial do cache. Se o Firebird não estiver acessível, ela inicia mesmo assim e você ainda pode pesquisar (vai tentar fallback direto no Firebird ao digitar, se disponível).
