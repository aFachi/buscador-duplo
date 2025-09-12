from pprint import pprint

from fb_utils import probe


def main():
    info = probe()
    print("=== Firebird Probe ===")
    pprint(info)
    if not info.get("ok"):
        print("\nDiagnóstico rápido:")
        print(
            "- Verifique se fbclient.dll está disponível (PATH ou ao lado do script/exe)"
        )
        print("- Confirme host/porta 3050 e credenciais no .env")
        print(
            "- Ajuste FIREBIRD_CHARSET (WIN1252 vs UTF8), se acentuação/erro de charset"
        )
        print("- Teste com isql.exe: isql -user SYSDBA -password ****** host:database")


if __name__ == "__main__":
    main()
