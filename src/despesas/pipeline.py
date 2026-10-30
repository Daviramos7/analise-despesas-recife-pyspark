"""Ponto de entrada: python -m despesas.pipeline"""
from despesas.carga import carregar
from despesas.ingestao import executar

if __name__ == "__main__":
    executar()
    carregar()
