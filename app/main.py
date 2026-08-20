"""Ponto de entrada da aplicação Streamlit.

Camadas: pages (UI) → services (regras de negócio) → repositories (acesso a
dados) → models. A UI nunca consulta o banco diretamente; cada função de
`application_service` é a fronteira que vira endpoint na migração para API.
"""

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no início do sys.path ANTES de
# qualquer "import app.*". Sem isso, rodar `streamlit run app/main.py` de
# fora da raiz do projeto (ou ter outro projeto com um pacote TAMBÉM chamado
# "app" instalado em modo editável no Python global — `pip install -e .`
# registra isso via .pth em site-packages, e vale pra qualquer script
# rodando nesse Python) faz o Python resolver "app" para o pacote errado, e
# os imports abaixo falham com ModuleNotFoundError.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

from app.database.init_db import init_db



st.set_page_config(page_title="Controle de Estoque - Cafeteria", layout="wide")
init_db()

st.title("☕ Cafezinho — Controle de Estoque")
st.markdown(
    "Use o menu lateral para cadastrar produtos, registrar compras e vendas, "
    "acompanhar alertas de reposição e abrir o dashboard gerencial."
)
