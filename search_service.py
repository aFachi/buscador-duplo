from typing import Any, Dict, List, Set

from firebird_client import FirebirdClient
from sqlite_repo import SqliteRepo


class SearchService:
    def __init__(self, repo: SqliteRepo, fb: FirebirdClient):
        self.repo = repo
        self.fb = fb

    def search(self, produto: str, veiculo: str, detalhe: str = "") -> Dict[str, Any]:
        """Busca independente por cada campo e cruza apenas se ambos estiverem preenchidos.

        Estratégia:
        - Primeiro tenta o cache (SQLite) para rapidez.
        - Se nada for encontrado para um termo, faz fallback para o Firebird (pesquisa solta).
        - Se os dois campos tiverem conteúdo, intersecta os códigos; caso contrário usa o conjunto do campo preenchido.
        """

        def codes_for_term(term: str) -> Set[str]:
            term = term.strip()
            if not term:
                return set()
            # tenta cache
            cached = self.repo.search_products_cache(term, limit=500)
            codes = {p["codigo"] for p in cached}
            if codes:
                return codes
            # fallback: busca direta no Firebird
            fb_items = self.fb.search_products_loose(produto=term, limit=200)
            # alimente o cache com o que achou para acelerar próximas buscas
            if fb_items:
                try:
                    self.repo.upsert_products(
                        [
                            {"codigo": i["codigo"], "descricao": i["descricao"]}
                            for i in fb_items
                        ]
                    )
                except Exception:
                    pass
            return {i["codigo"] for i in fb_items}

        # conjuntos independentes para cada campo
        codigos_prod = codes_for_term(produto)
        codigos_apl = codes_for_term((veiculo + " " + detalhe).strip())

        if codigos_prod and codigos_apl:
            final_codes = list(codigos_prod.intersection(codigos_apl))
        elif codigos_prod:
            final_codes = list(codigos_prod)
        elif codigos_apl:
            final_codes = list(codigos_apl)
        else:
            return {"items": [], "count": 0}

        # enriquecer com descrições do cache (ou vazio se não houver)
        produtos_info = {
            p["codigo"]: p for p in self.repo.get_products_by_codes(final_codes)
        }
        # Buscar dados completos diretamente do Firebird (inclui extras quando disponíveis)
        full = self.fb.fetch_full_by_codes(final_codes)

        items: List[Dict[str, Any]] = []
        for code in final_codes:
            desc = produtos_info.get(code, {}).get(
                "descricao", "(sem descrição no cache)"
            )
            sp = full.get(code, {})
            items.append(
                {
                    "codigo": code,
                    "descricao": sp.get("descricao", desc),
                    "estoque": sp.get("estoque"),
                    "preco": sp.get("preco"),
                    "fornecedor": sp.get("fornecedor"),
                    "marca": sp.get("marca"),
                    "grupo": sp.get("grupo"),
                    "subgrupo": sp.get("subgrupo"),
                }
            )
        items.sort(key=lambda x: (x["descricao"] or "").lower())
        return {"items": items, "count": len(items)}
