from .config import COUNTER_FILE

def interacao_atual():
    valor_atual = 0
    if COUNTER_FILE.exists():
        try:
            valor_atual = int(COUNTER_FILE.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            valor_atual = 0
    return valor_atual

def incrementar_contador(path_arquivo):
    valor_atual = 0
    if path_arquivo.exists():
        try:
            valor_atual = int(path_arquivo.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            valor_atual = 0

    novo_valor = valor_atual + 1
    path_arquivo.write_text(str(novo_valor), encoding="utf-8")
    return novo_valor



