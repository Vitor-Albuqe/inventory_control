"""Executa as queries analíticas de `sql/` direto no terminal.

Uso:
    python scripts/consultas_sql.py                  # lista as queries
    python scripts/consultas_sql.py 04_curva_abc     # roda uma
    python scripts/consultas_sql.py --todas          # roda todas
    python scripts/consultas_sql.py 03_giro_estoque --csv saida.csv

Serve para conferir uma query sem subir o Streamlit e para exportar o
resultado — as mesmas queries que a aplicação usa, sem intermediário.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories import analytics_repository as an  # noqa: E402

# Parâmetros exigidos por cada query, além de tenant_id (preenchido sozinho)
PARAMS_PADRAO = {
    "02_alertas_reposicao": lambda: {"dias_validade": 7, "dias_cobertura": 15},
    "03_giro_estoque": lambda: _periodo(),
    "04_curva_abc": lambda: _periodo(),
    "06_margem_por_receita": lambda: _periodo(),
    "07_desempenho_fornecedores": lambda: _periodo(),
    "08_perdas_por_causa": lambda: _periodo(),
}


def _periodo(dias: int = 180) -> dict:
    fim = date.today()
    return {
        "data_inicio": (fim - timedelta(days=dias)).isoformat(),
        "data_fim": fim.isoformat(),
    }


def rodar(nome: str, linhas: int) -> pd.DataFrame:
    params = PARAMS_PADRAO.get(nome, dict)()
    df = an.executar(nome, **params)

    print(f"\n{'=' * 78}")
    print(f"  {nome}   ({len(df)} linhas x {len(df.columns)} colunas)")
    print("=" * 78)
    if df.empty:
        print("  (sem resultados — o banco tem dados? veja scripts/gerar_dados_sinteticos.py)")
    else:
        with pd.option_context(
            "display.max_columns", None,
            "display.width", 200,
            "display.float_format", lambda v: f"{v:,.2f}",
        ):
            print(df.head(linhas).to_string(index=False))
        if len(df) > linhas:
            print(f"  ... mais {len(df) - linhas} linha(s). Use --linhas para ver mais.")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="nome do arquivo .sql sem extensão")
    parser.add_argument("--todas", action="store_true", help="roda todas as queries")
    parser.add_argument("--linhas", type=int, default=15, help="linhas exibidas")
    parser.add_argument("--csv", help="salva o resultado em CSV")
    args = parser.parse_args()

    disponiveis = an.listar_queries()

    if not args.query and not args.todas:
        print("Queries disponíveis em sql/:\n")
        for q in disponiveis:
            print(f"  {q}")
        print("\nRode uma com: python scripts/consultas_sql.py <nome>")
        return

    alvos = disponiveis if args.todas else [args.query]
    for nome in alvos:
        if nome not in disponiveis:
            print(f"Query '{nome}' não existe. Disponíveis: {', '.join(disponiveis)}")
            sys.exit(1)
        df = rodar(nome, args.linhas)
        if args.csv and not args.todas:
            df.to_csv(args.csv, index=False, encoding="utf-8-sig")
            print(f"\nSalvo em {args.csv}")


if __name__ == "__main__":
    main()
