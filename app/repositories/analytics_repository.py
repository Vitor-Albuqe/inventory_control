"""Camada analítica em SQL puro.

As queries vivem em arquivos `.sql` na pasta `sql/` da raiz do projeto, não
embutidas em strings Python. A separação é deliberada:

- a mesma query roda no DBeaver, no Power BI e na aplicação, sem reescrever;
- o `git diff` de uma mudança de regra analítica é legível;
- o SQL fica revisável por quem entende de dados e não de Python.

O resto do sistema (cadastro, venda, baixa de estoque) continua no ORM, que é
a ferramenta certa para escrita transacional. Leitura analítica — janelas,
acumulados, ABC, ranking particionado — é onde o ORM atrapalha mais do que
ajuda, então aqui é SQL.

Segurança: nenhuma query é montada por concatenação. Os parâmetros são sempre
ligados via `text()` + dicionário (`:tenant_id`), que o driver envia
separadamente da instrução — o mesmo motivo pelo qual o resto do app usa ORM.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.database.connection import engine
from app.database.seed import DEFAULT_TENANT_ID


def _sql_dir() -> Path:
    """Pasta das queries, funcionando também dentro do .exe.

    PyInstaller extrai os `datas` do bundle para uma pasta temporária apontada
    por `sys._MEIPASS`; em desenvolvimento, `sql/` é irmã de `app/`.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "sql"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "sql"


@lru_cache(maxsize=None)
def carregar_query(nome: str) -> str:
    """Lê o arquivo .sql pelo nome (sem extensão).

    Cacheado: em produção o arquivo não muda entre execuções, e o Streamlit
    reexecuta o script inteiro a cada interação do usuário.
    """
    caminho = _sql_dir() / f"{nome}.sql"
    if not caminho.exists():
        disponiveis = ", ".join(sorted(q.stem for q in _sql_dir().glob("*.sql")))
        raise FileNotFoundError(
            f"Query '{nome}' não encontrada em {_sql_dir()}. Disponíveis: {disponiveis}"
        )
    return caminho.read_text(encoding="utf-8")


def listar_queries() -> list[str]:
    return sorted(q.stem for q in _sql_dir().glob("*.sql"))


def executar(nome: str, **params) -> pd.DataFrame:
    """Executa uma query nomeada com parâmetros ligados e devolve um DataFrame."""
    params.setdefault("tenant_id", DEFAULT_TENANT_ID)
    with engine.connect() as conn:
        return pd.read_sql_query(text(carregar_query(nome)), conn, params=params)


# ---------------------------------------------------------------------------
# Atalhos nomeados — a UI e os scripts chamam estes, não `executar` cru
# ---------------------------------------------------------------------------

def _periodo_padrao(
    data_inicio: date | None, data_fim: date | None, dias: int = 180
) -> tuple[str, str]:
    fim = data_fim or date.today()
    inicio = data_inicio or (fim - timedelta(days=dias))
    return inicio.isoformat(), fim.isoformat()


def posicao_estoque() -> pd.DataFrame:
    return executar("01_posicao_estoque")


def alertas_reposicao(dias_validade: int = 7, dias_cobertura: int = 15) -> pd.DataFrame:
    return executar(
        "02_alertas_reposicao",
        dias_validade=dias_validade,
        dias_cobertura=dias_cobertura,
    )


def giro_estoque(
    data_inicio: date | None = None, data_fim: date | None = None
) -> pd.DataFrame:
    inicio, fim = _periodo_padrao(data_inicio, data_fim)
    return executar("03_giro_estoque", data_inicio=inicio, data_fim=fim)


def curva_abc(
    data_inicio: date | None = None, data_fim: date | None = None
) -> pd.DataFrame:
    inicio, fim = _periodo_padrao(data_inicio, data_fim)
    return executar("04_curva_abc", data_inicio=inicio, data_fim=fim)


def evolucao_mensal() -> pd.DataFrame:
    return executar("05_evolucao_mensal")


def margem_por_receita(
    data_inicio: date | None = None, data_fim: date | None = None
) -> pd.DataFrame:
    inicio, fim = _periodo_padrao(data_inicio, data_fim)
    return executar("06_margem_por_receita", data_inicio=inicio, data_fim=fim)


def desempenho_fornecedores(
    data_inicio: date | None = None, data_fim: date | None = None
) -> pd.DataFrame:
    inicio, fim = _periodo_padrao(data_inicio, data_fim)
    return executar("07_desempenho_fornecedores", data_inicio=inicio, data_fim=fim)


def perdas_por_causa(
    data_inicio: date | None = None, data_fim: date | None = None
) -> pd.DataFrame:
    inicio, fim = _periodo_padrao(data_inicio, data_fim)
    return executar("08_perdas_por_causa", data_inicio=inicio, data_fim=fim)
