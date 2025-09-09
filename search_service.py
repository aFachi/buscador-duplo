from typing import Any, Dict, List, Set

from firebird_client import FirebirdClient
from sqlite_repo import SqliteRepo


class SearchService:
    def __init__(self, repo: SqliteRepo, fb: FirebirdClient):
        self.repo = repo
        self.fb = fb

    def search(self, produto: str, veiculo: str, detalhe: str = "") -> Dict[str, Any]:
        codigos_apl: Set[str] = set()
        codigos_prod: Set[str] = set()

        if veiculo.strip() or detalhe.strip():
            veic_q = (veiculo + " " + detalhe).strip()
            apl = self.repo.search_applications(veic_q)
            codigos_apl = {a["codigo_produto"] for a in apl}

        if produto.strip():
            pc = self.repo.search_products_cache(produto.strip())
            codigos_prod = {p["codigo"] for p in pc}

        if codigos_apl and codigos_prod:
            final_codes = list(codigos_apl.intersection(codigos_prod))
        elif codigos_apl:
            final_codes = list(codigos_apl)
        elif codigos_prod:
            final_codes = list(codigos_prod)
        else:
            return {"items": [], "count": 0}

        produtos_info = {
            p["codigo"]: p for p in self.repo.get_products_by_codes(final_codes)
        }
        estoque_preco = self.fb.fetch_stock_price_by_codes(final_codes)

        items: List[Dict[str, Any]] = []
        for code in final_codes:
            desc = produtos_info.get(code, {}).get(
                "descricao", "(sem descrição no cache)"
            )
            sp = estoque_preco.get(code, {"estoque": None, "preco": None})
            items.append(
                {
                    "codigo": code,
                    "descricao": desc,
                    "estoque": sp.get("estoque"),
                    "preco": sp.get("preco"),
                }
            )
        items.sort(key=lambda x: (x["descricao"] or "").lower())
        return {"items": items, "count": len(items)}
