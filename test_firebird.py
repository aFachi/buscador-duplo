import configparser

from firebird_client import FirebirdClient


def main():
    config = configparser.ConfigParser()
    config.read("config.ini", encoding="utf-8")
    fb = FirebirdClient(config)
    items = fb.fetch_products_basic()
    print(f"OK: {len(items)} produtos.")
    for it in items[:5]:
        print(it)


if __name__ == "__main__":
    main()
