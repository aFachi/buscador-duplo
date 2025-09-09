from firebird_client import FirebirdClient


class StubFB(FirebirdClient):
    def __init__(self):
        pass

    def _discover_product_table(self):
        return ("T", {"codigo": "COD", "descricao": "DESC"})

    def _connect(self):
        class Cur:
            def execute(self, sql, params=None):
                self.rows = [("1", "Produto", None, None)]

            def fetchall(self):
                return self.rows

        class Con:
            def cursor(self):
                return Cur()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return Con()


def test_search_products_loose_stub():
    fb = StubFB()
    res = fb.search_products_loose(produto="Prod")
    assert res[0]["codigo"] == "1"
    assert res[0]["descricao"] == "Produto"
