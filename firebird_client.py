# firebird_client.py
import contextlib
import os
import re
from typing import Dict, List, Optional, Tuple
import configparser

try:
    import firebirdsql  # driver puro Python compatível com FB 2.5
except Exception:  # pacote pode não estar instalado ainda
    firebirdsql = None


# --------- Helpers de log ----------
def _log(*args):
    print("[FB]", *args)


def _norm(s: Optional[str]) -> Optional[str]:
    return s.strip() if isinstance(s, str) else s


class FirebirdClient:
    """
    Cliente Firebird com descoberta dinâmica de tabela/colunas de produto.
    Padroniza o output em chaves: codigo, descricao, barras, preco.
    """

    # nomes "prováveis" para tabela de produtos
    _likely_product_tables = [
        "TPRODUTO",
        "TPRODUTOS",
        "PRODUTO",
        "PRODUTOS",
        "ESTOQUE",
        "TESTOQUE",
        "T_ESTOQUE",
    ]

    # Tabelas a evitar (itens de venda/comanda/pedido/movimentação etc.)
    _exclude_table_patterns = [
        r"COMANDA",
        r"PEDID",
        r"ORCAMENT",
        r"CUPOM",
        r"VENDA",
        r"NF",
        r"NOTA",
        r"MOV",
        r"MOVIMENT",
        r"GRADE",  # evita tabelas de grade como catálogo principal
        r"_ITENS?\b",
        r"\bITENS?\b",
        r"\bITEM\b",
    ]

    # mapeamento de aliases possíveis -> chave padronizada
    _candidate_cols = {
        "codigo": ["CODPRODUTO", "CODIGO", "COD", "IDPRODUTO", "ID", "C_PRODUTO"],
        "descricao": [
            "DESCRICAO",
            "DESCRICAOAPLICACAO",
            "PRODUTO",
            "NOME",
            "DESCR",
            "DESCRI",
        ],
        "barras": ["BARRAS", "CODBARRAS", "CODIGOBARRAS", "EAN", "GTIN"],
        "preco": ["PRECO", "PRECOVENDA", "VALOR", "PRECO1", "VLRVENDA"],
    }
    _candidate_stock_cols = [
        "ESTOQUE",
        "SALDO",
        "QTDESTOQUE",
        "QTD",
        "QTDE",
        "QUANTIDADE",
        "QTD_TOTAL",
        "QTD_DISPONIVEL",
        "QTESTOQUE",
    ]

    def __init__(self, cfg: configparser.ConfigParser):
        # Aceita [FIREBIRD] ou [firebird]
        fb_section: Optional[str] = None
        for s in ("FIREBIRD", "firebird"):
            if cfg.has_section(s):
                fb_section = s
                break

        def opt(name: str, default: Optional[str] = None) -> Optional[str]:
            if fb_section and cfg.has_option(fb_section, name):
                # ConfigParser é case-insensitive para opções
                return cfg.get(fb_section, name)
            return default

        def opt_int(name: str, default: Optional[int] = None) -> Optional[int]:
            if fb_section and cfg.has_option(fb_section, name):
                try:
                    return cfg.getint(fb_section, name)
                except Exception:
                    pass
            return default

        # 1) tenta pegar do config.ini (se houver)
        host = opt("HOST")
        port = opt_int("PORT")
        user = opt("USER")
        password = opt("PASSWORD")
        # aceitar DATABASE ou DATABASE_PATH
        database = opt("DATABASE") or opt("DATABASE_PATH")
        charset = opt("CHARSET")

        # 2) senão, cai pro .env
        self.host = host or os.environ.get("FIREBIRD_HOST", "localhost")
        self.port = port or int(os.environ.get("FIREBIRD_PORT", "3050"))
        self.user = user or os.environ.get("FIREBIRD_USER", "sysdba")
        self.password = password or os.environ.get("FIREBIRD_PASSWORD", "masterkey")
        self.database = database or os.environ.get("FIREBIRD_DATABASE")
        self.charset = (
            charset or os.environ.get("FIREBIRD_CHARSET") or "WIN1252"
        ).upper()

        # permitir caminho relativo ao diretório do projeto
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if self.database and not os.path.isabs(self.database):
            rel = os.path.join(base_dir, self.database)
            if os.path.exists(rel):
                self.database = rel
        # se apontaram caminho absoluto antigo que não existe,
        # mas o arquivo com o mesmo nome está no projeto, usa-o
        if self.database and not os.path.exists(self.database):
            candidate = os.path.join(base_dir, os.path.basename(self.database))
            if os.path.exists(candidate):
                self.database = candidate

        if not self.database:
            raise RuntimeError(
                "Caminho do banco Firebird não encontrado (FIREBIRD.DATABASE no config.ini ou FIREBIRD_DATABASE no .env)."
            )

        # overrides opcionais de mapeamento/tabela
        self._override_table = opt("TABLE") or os.environ.get("FIREBIRD_TABLE")
        self._override_cols: Dict[str, Optional[str]] = {
            "codigo": opt("COL_CODIGO") or os.environ.get("FIREBIRD_COL_CODIGO"),
            "descricao": opt("COL_DESCRICAO")
            or os.environ.get("FIREBIRD_COL_DESCRICAO"),
            "barras": opt("COL_BARRAS") or os.environ.get("FIREBIRD_COL_BARRAS"),
            "preco": opt("COL_PRECO") or os.environ.get("FIREBIRD_COL_PRECO"),
            # extras
            "estoque": opt("COL_ESTOQUE") or os.environ.get("FIREBIRD_COL_ESTOQUE"),
            "fornecedor": opt("COL_FORNECEDOR")
            or os.environ.get("FIREBIRD_COL_FORNECEDOR"),
            "marca": opt("COL_MARCA") or os.environ.get("FIREBIRD_COL_MARCA"),
            "grupo": opt("COL_GRUPO") or os.environ.get("FIREBIRD_COL_GRUPO"),
            "subgrupo": opt("COL_SUBGRUPO") or os.environ.get("FIREBIRD_COL_SUBGRUPO"),
        }
        # SQL completo opcional (para permitir JOINs). Deve selecionar colunas
        # com aliases: CODIGO, DESCRICAO, BARRAS, PRECO, ESTOQUE, FORNECEDOR, MARCA, GRUPO, SUBGRUPO
        # e conter o token {placeholders} em um IN (...) que iremos preencher.
        self._override_full_sql = opt("FULL_SQL") or os.environ.get("FIREBIRD_FULL_SQL")

        # cache de metadados
        self._columns_cache: Dict[str, List[str]] = {}
        self._product_table_signature: Optional[Tuple[str, Dict[str, str]]] = None

    # ---------- Conexão ----------
    def _connect(self):
        # Nada de auth_method e nada de timeout que quebraram antes
        if firebirdsql is None:
            raise RuntimeError(
                "Dependência ausente: instale 'firebirdsql' (pip install -r requirements.txt)"
            )
        return firebirdsql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset=self.charset,
        )

    # ---------- Metadata ----------
    def _list_tables(self) -> List[str]:
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT TRIM(RDB$RELATION_NAME)
                FROM RDB$RELATIONS
                WHERE RDB$VIEW_BLR IS NULL
                  AND (RDB$SYSTEM_FLAG IS NULL OR RDB$SYSTEM_FLAG = 0)
            """
            )
            return [r[0] for r in cur.fetchall()]

    def _table_columns(self, table: str) -> List[str]:
        t = table.upper()
        if t in self._columns_cache:
            return self._columns_cache[t]
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT TRIM(rf.RDB$FIELD_NAME)
                FROM RDB$RELATION_FIELDS rf
                JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
                WHERE rf.RDB$RELATION_NAME = ?
                ORDER BY rf.RDB$FIELD_POSITION
            """,
                (t,),
            )
            cols = [r[0] for r in cur.fetchall()]
            self._columns_cache[t] = cols
            return cols

    def _find_first_existing(
        self, cols: List[str], candidates: List[str]
    ) -> Optional[str]:
        setcols = {c.upper(): c for c in cols}
        for cand in candidates:
            if cand.upper() in setcols:
                return setcols[cand.upper()]
        return None

    def _looks_like_product_table(self, table: str, cols: List[str]) -> bool:
        up = table.upper()
        # heurística: nome forte + existência de ao menos 1 campo "descricao"
        # primeiro filtra padrões que certamente não são catálogo (itens de pedido/comanda, etc.)
        for pat in self._exclude_table_patterns:
            if re.search(pat, up):
                return False
        if any(up == c for c in self._likely_product_tables):
            return True
        # nomes que "sugiram" produto/estoque
        if re.search(r"(PROD|ESTOQ)", up):
            # precisa ter pelo menos uma coluna que pareça descrição
            if self._find_first_existing(cols, self._candidate_cols["descricao"]):
                return True
        return False

    def _has_rows(self, table: str, mapping: Dict[str, str]) -> bool:
        try:
            with self._connect() as con:
                cur = con.cursor()
                cur.execute(f"SELECT FIRST 1 {mapping.get('codigo','1')} FROM {table}")
                return cur.fetchone() is not None
        except Exception:
            return False

    def _discover_product_candidates(
        self, max_candidates: int = 10, *, lenient: bool = False
    ) -> List[Tuple[str, Dict[str, str]]]:
        """Lista candidatos de tabela de produto com mapeamento válido e amostra>0.

        Quando lenient=True, ignora o filtro de nome/tipo (não usa _looks_like_product_table)
        e considera qualquer tabela que tenha combinações plausíveis de código+descrição.
        """
        tables = self._list_tables()
        candidates: List[Tuple[str, Dict[str, str], int]] = []  # (t, mapping, score)
        for t in tables:
            cols = self._table_columns(t)
            if not lenient:
                if not self._looks_like_product_table(t, cols):
                    continue
            m: Dict[str, str] = {}
            score = 0
            for key in ["codigo", "descricao", "barras", "preco"]:
                hit = self._find_first_existing(cols, self._candidate_cols[key])
                if hit:
                    m[key] = hit
                    if key in ("codigo", "descricao"):
                        score += 10
                    elif key == "preco":
                        score += 2
                    elif key == "barras":
                        score += 1
            if "codigo" in m and "descricao" in m and self._has_rows(t, m):
                # bônus por nome forte
                if t.upper() in self._likely_product_tables:
                    score += 2
                candidates.append((t, m, score))
        candidates.sort(key=lambda x: x[2], reverse=True)
        return [(t, m) for (t, m, _s) in candidates[:max_candidates]]

    def _discover_product_table(self) -> Optional[Tuple[str, Dict[str, str]]]:
        """
        Retorna (nome_tabela, mapping_colunas), onde mapping_colunas mapeia
        'codigo'|'descricao'|'barras'|'preco' -> nome real da coluna.
        """
        if self._product_table_signature is not None:
            return self._product_table_signature

        # se houver override explícito, usa-o
        if (
            self._override_table
            and self._override_cols.get("codigo")
            and self._override_cols.get("descricao")
        ):
            table = self._override_table
            m = {k: v for k, v in self._override_cols.items() if v}
            # valida se a tabela e as colunas existem
            try:
                tables = self._list_tables()
                if table.upper() in {t.upper() for t in tables}:
                    cols = self._table_columns(table)
                    missing = [
                        c
                        for c in (m.get("codigo"), m.get("descricao"))
                        if c and c.upper() not in {x.upper() for x in cols}
                    ]
                    if not missing:
                        # também exige ao menos 1 linha
                        if self._has_rows(table, m):
                            self._product_table_signature = (table, m)  # inclui extras
                            _log(f"Tabela de produto (override): {table} -> {m}")
                            return self._product_table_signature
                        else:
                            _log(f"Override ignorado: {table} não tem linhas.")
                    else:
                        _log(
                            f"Override inválido: colunas ausentes em {table}: {missing}. Ignorando override."
                        )
                else:
                    _log(
                        f"Override inválido: tabela {table} não existe. Ignorando override."
                    )
            except Exception as e:
                _log(f"Falha ao validar override {table}: {e}. Ignorando override.")

        cands = self._discover_product_candidates()
        if cands:
            t, m = cands[0]
            self._product_table_signature = (t, m)
            _log(f"Tabela de produto descoberta: {t} -> {m}")
            return self._product_table_signature

        _log("Não foi possível descobrir automaticamente a tabela de produtos.")
        self._product_table_signature = None
        return None

    # ---------- API pública ----------
    def ping(self) -> bool:
        try:
            with self._connect() as con:
                cur = con.cursor()
                cur.execute("SELECT 1 FROM RDB$DATABASE")
                cur.fetchone()
            return True
        except Exception as e:
            _log("ping falhou:", e)
            return False

    def fetch_products_basic(self, limit: int = 200) -> List[Dict]:
        """
        Usado pelo SyncService: obtém um snapshot básico de produtos.
        Retorna lista de dicts com: codigo, descricao, barras, preco
        """
        sig = self._discover_product_table()
        if not sig:
            return []  # deixa o autosync passar em branco sem quebrar
        table, mapping = sig
        parts = []
        parts.append(f"{mapping['codigo']} AS CODIGO")
        parts.append(f"{mapping['descricao']} AS DESCRICAO")
        if "barras" in mapping:
            parts.append(f"{mapping['barras']} AS BARRAS")
        else:
            parts.append("CAST(NULL AS VARCHAR(40)) AS BARRAS")
        if "preco" in mapping:
            parts.append(f"{mapping['preco']} AS PRECO")
        else:
            parts.append("CAST(NULL AS DECIMAL(18,4)) AS PRECO")

        select_cols = ", ".join(parts)
        sql = f"SELECT FIRST {int(limit)} {select_cols} FROM {table}"

        with self._connect() as con:
            cur = con.cursor()
            cur.execute(sql)
            rows = cur.fetchall()

        out: List[Dict] = []
        for r in rows:
            codigo, descricao, barras, preco = r
            out.append(
                {
                    "codigo": _norm(codigo),
                    "descricao": _norm(descricao),
                    "barras": _norm(barras),
                    "preco": float(preco) if preco is not None else None,
                }
            )
        return out

    def fetch_stock_price_by_codes(
        self, codes: List[str]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """Busca estoque e preço para uma lista de códigos."""
        if not codes:
            return {}
        sig = self._discover_product_table()
        if not sig:
            return {}
        table, mapping = sig
        cols = self._table_columns(table)
        estoque_col = mapping.get("estoque") or self._find_first_existing(
            cols, self._candidate_stock_cols
        )
        preco_col = mapping.get("preco")
        codigo_col = mapping["codigo"]
        select_parts = [f"{codigo_col} AS CODIGO"]
        if estoque_col:
            select_parts.append(f"{estoque_col} AS ESTOQUE")
        else:
            select_parts.append("CAST(NULL AS DECIMAL(18,4)) AS ESTOQUE")
        if preco_col:
            select_parts.append(f"{preco_col} AS PRECO")
        else:
            select_parts.append("CAST(NULL AS DECIMAL(18,4)) AS PRECO")
        select_cols = ", ".join(select_parts)
        placeholders = ",".join(["?"] * len(codes))
        sql = (
            f"SELECT {select_cols} FROM {table} WHERE {codigo_col} IN ({placeholders})"
        )
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(sql, codes)
            rows = cur.fetchall()
        out: Dict[str, Dict[str, Optional[float]]] = {}
        for r in rows:
            codigo, estoque, preco = r
            out[_norm(codigo) or ""] = {
                "estoque": float(estoque) if estoque is not None else None,
                "preco": float(preco) if preco is not None else None,
            }
        return out

    def fetch_full_by_codes(
        self, codes: List[str]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """Retorna info completa dos códigos: descricao, barras, preco, estoque e extras."""
        if not codes:
            return {}
        # Caso o usuário tenha fornecido um SELECT completo para JOINs, usa-o aqui
        if self._override_full_sql:
            placeholders = ",".join(["?"] * len(codes))
            sql = self._override_full_sql.replace("{placeholders}", placeholders)
            with self._connect() as con:
                cur = con.cursor()
                cur.execute(sql, codes)
                rows = cur.fetchall()
            out: Dict[str, Dict[str, Optional[float]]] = {}
            for r in rows:
                (
                    codigo,
                    descricao,
                    barras,
                    preco,
                    estoque,
                    fornecedor,
                    marca,
                    grupo,
                    subgrupo,
                ) = r
                out[_norm(codigo) or ""] = {
                    "descricao": _norm(descricao),
                    "barras": _norm(barras),
                    "preco": float(preco) if preco is not None else None,
                    "estoque": float(estoque) if estoque is not None else None,
                    "fornecedor": _norm(fornecedor),
                    "marca": _norm(marca),
                    "grupo": _norm(grupo),
                    "subgrupo": _norm(subgrupo),
                }
            return out

        sig = self._discover_product_table()
        if not sig:
            return {}
        table, mapping = sig
        cols = self._table_columns(table)

        def col_or_null(colname: Optional[str], cast: str, alias: str) -> str:
            return (
                f"{colname} AS {alias}"
                if colname
                else f"CAST(NULL AS {cast}) AS {alias}"
            )

        codigo_col = mapping["codigo"]
        descricao_col = mapping.get("descricao")
        barras_col = mapping.get("barras")
        preco_col = mapping.get("preco")
        estoque_col = mapping.get("estoque") or self._find_first_existing(
            cols, self._candidate_stock_cols
        )
        fornecedor_col = mapping.get("fornecedor")
        marca_col = mapping.get("marca")
        grupo_col = mapping.get("grupo")
        subgrupo_col = mapping.get("subgrupo")

        select_parts = [
            f"{codigo_col} AS CODIGO",
            col_or_null(descricao_col, "VARCHAR(200)", "DESCRICAO"),
            col_or_null(barras_col, "VARCHAR(50)", "BARRAS"),
            col_or_null(preco_col, "DECIMAL(18,4)", "PRECO"),
            col_or_null(estoque_col, "DECIMAL(18,4)", "ESTOQUE"),
            col_or_null(fornecedor_col, "VARCHAR(200)", "FORNECEDOR"),
            col_or_null(marca_col, "VARCHAR(200)", "MARCA"),
            col_or_null(grupo_col, "VARCHAR(200)", "GRUPO"),
            col_or_null(subgrupo_col, "VARCHAR(200)", "SUBGRUPO"),
        ]
        select_cols = ", ".join(select_parts)
        placeholders = ",".join(["?"] * len(codes))
        sql = (
            f"SELECT {select_cols} FROM {table} WHERE {codigo_col} IN ({placeholders})"
        )
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(sql, codes)
            rows = cur.fetchall()
        out: Dict[str, Dict[str, Optional[float]]] = {}
        for r in rows:
            (
                codigo,
                descricao,
                barras,
                preco,
                estoque,
                fornecedor,
                marca,
                grupo,
                subgrupo,
            ) = r
            out[_norm(codigo) or ""] = {
                "descricao": _norm(descricao),
                "barras": _norm(barras),
                "preco": float(preco) if preco is not None else None,
                "estoque": float(estoque) if estoque is not None else None,
                "fornecedor": _norm(fornecedor),
                "marca": _norm(marca),
                "grupo": _norm(grupo),
                "subgrupo": _norm(subgrupo),
            }
        return out

    def search_products_loose(
        self,
        produto: str = "",
        veiculo: str = "",
        detalhe: str = "",
        limit: int = 50,
    ) -> List[Dict]:
        """
        Pesquisa "solta" no Firebird com base nas colunas que existirem.
        O SearchService usa o SQLite; isto aqui serve de fallback se você quiser.
        """
        terms = [t for t in [produto, veiculo, detalhe] if t]
        if not terms:
            return []

        # tenta tabela principal, depois candidatos adicionais até preencher o limite
        tried: List[str] = []
        results: Dict[str, Dict] = {}

        def run_on(table: str, mapping: Dict[str, str], remaining: int):
            where_clauses: List[str] = []
            params: List[str] = []
            if mapping.get("descricao"):
                for t in terms:
                    where_clauses.append(f"{mapping['descricao']} CONTAINING ?")
                    params.append(t)
            if mapping.get("codigo"):
                for t in terms:
                    where_clauses.append(
                        f"CAST({mapping['codigo']} AS VARCHAR(50)) LIKE ?"
                    )
                    params.append(f"%{t}%")
            if mapping.get("barras"):
                for t in terms:
                    where_clauses.append(f"{mapping['barras']} LIKE ?")
                    params.append(f"%{t}%")
            if not where_clauses:
                return 0
            parts = [
                f"{mapping['codigo']} AS CODIGO",
                f"{mapping['descricao']} AS DESCRICAO",
                f"{mapping.get('barras', 'CAST(NULL AS VARCHAR(40))')} AS BARRAS",
                f"{mapping.get('preco', 'CAST(NULL AS DECIMAL(18,4))')} AS PRECO",
            ]
            select_cols = ", ".join(parts)
            sql = (
                f"SELECT FIRST {int(remaining)} {select_cols} FROM {table} "
                f"WHERE {' OR '.join(where_clauses)}"
            )
            try:
                with self._connect() as con:
                    cur = con.cursor()
                    cur.execute(sql, params)
                    for codigo, descricao, barras, preco in cur.fetchall():
                        code = _norm(codigo) or ""
                        if not code or code in results:
                            continue
                        results[code] = {
                            "codigo": code,
                            "descricao": _norm(descricao),
                            "barras": _norm(barras),
                            "preco": float(preco) if preco is not None else None,
                        }
                        if len(results) >= limit:
                            break
            except Exception as e:
                _log(f"Falha ao buscar em {table}: {e}")
            return len(results)

        # 1) principal
        sig = self._discover_product_table()
        if sig:
            table, mapping = sig
            tried.append(table.upper())
            run_on(table, mapping, limit)

        # 2) candidatos adicionais
        if len(results) < limit:
            # primeiro candidatos "fortes"; depois, em modo leniente (qualquer tabela com codigo+descricao)
            for t, m in self._discover_product_candidates(max_candidates=20):
                if t.upper() in tried:
                    continue
                run_on(t, m, limit - len(results))
                if len(results) >= limit:
                    break
        if len(results) < limit:
            for t, m in self._discover_product_candidates(
                max_candidates=30, lenient=True
            ):
                if t.upper() in tried:
                    continue
                run_on(t, m, limit - len(results))
                if len(results) >= limit:
                    break

        return list(results.values())
