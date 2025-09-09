# Buscador Duplo

Sistema de busca para autopeças baseado em [FastAPI](https://fastapi.tiangolo.com/).
Permite pesquisar produtos e aplicações de veículos em dois campos que se
complementam. O projeto mantém um cache local em SQLite e consulta um banco
Firebird para preço e estoque.

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
uvicorn app:app --reload
```
A aplicação abre automaticamente o navegador em `http://127.0.0.1:8000`.

### Health-check

Há um endpoint de verificação rápida em `GET /health` que retorna o estado da
conexão com o Firebird (`firebird`) e a data/hora da última sincronização
(`last_sync`).

## Testes

```bash
pytest
```

### Teste de integração com Firebird

Um teste opcional cria um banco Firebird temporário para validar o fluxo de
sincronização e busca. É necessário ter um servidor Firebird local em
`localhost:3050`; caso contrário o teste será ignorado.

```bash
pytest test_firebird_integration.py
```

## Variáveis de ambiente

As seguintes variáveis podem ser usadas no `.env` ou ambiente do sistema:

- `FIREBIRD_HOST`
- `FIREBIRD_PORT`
- `FIREBIRD_USER`
- `FIREBIRD_PASSWORD`
- `FIREBIRD_DATABASE`
- `FIREBIRD_CHARSET`

O parâmetro `app.autosync_minutes` no `config.ini` define o intervalo, em
minutos, para sincronização automática do cache.
