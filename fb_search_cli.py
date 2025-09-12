import argparse
from pprint import pprint

from fb_utils import cache_upsert, search_products


def main():
    p = argparse.ArgumentParser(
        description="Busca produtos no Firebird com cache local"
    )
    p.add_argument(
        "--term", required=True, help="Termo de busca (código ou parte da descrição)"
    )
    p.add_argument(
        "--limit", type=int, default=50, help="Limite de registros (padrão: 50)"
    )
    p.add_argument("--no-cache", action="store_true", help="Não atualizar cache local")
    args = p.parse_args()

    rows = search_products(args.term, args.limit)
    if not args.no_cache:
        cache_upsert(rows)

    print(f"Encontrados {len(rows)} registros:")
    for r in rows:
        pprint(r)


if __name__ == "__main__":
    main()
