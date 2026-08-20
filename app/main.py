"""Aplicação Streamlit - MVP de controle de estoque para cafeteria.

Arquitetura escolhida (simples e didática):
- models: define tabelas/classes de domínio.
- database: conexão e inicialização do banco.
- services: regras de negócio.
- pages: interface de cada funcionalidade.

Essa separação facilita manutenção e evolução futura.
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

st.title("☕ Controle de Estoque - Cafeteria (MVP Fase 1)")
st.markdown(
    "Use o menu lateral para cadastrar produtos, registrar compras "
    "e acompanhar o dashboard de estoque."
)
