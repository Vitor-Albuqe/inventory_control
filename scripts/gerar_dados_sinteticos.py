"""Gera um dataset sintético de ~6 meses simulando a operação real de uma
cafeteria: catálogo de produtos, compras, aberturas de embalagem, vendas
diárias (com sazonalidade e crescimento), perdas, ajustes de contagem e
gastos operacionais.

Objetivo: ter uma base rica o bastante para smoke test do app e para análise
no Power BI (estoque mínimo por produto, giro de estoque, alertas de
reposição e evolução de consumo por período).

Uso:
    python scripts/gerar_dados_sinteticos.py

Apaga e recria cafeteria_estoque.db do zero (mesmo efeito de
reset_database.py) antes de popular os dados.
"""

from __future__ import annotations

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database.connection import Base, SessionLocal, engine  # noqa: E402
from app.database.init_db import init_db  # noqa: E402
from app.models import Expense, Product, Sale, StockLot, StockMovement  # noqa: E402
from app.services.session_scope import session_scope  # noqa: E402
import app.services.stock_service as stock_service  # noqa: E402
from app.services import (  # noqa: E402
    abertos_proximos_vencimento,
    correcoes_recentes,
    criar_gasto,
    produtos_abaixo_minimo,
    produtos_ativos_opcoes,
    registrar_abertura,
    registrar_ajuste,
    registrar_compra_ui,
    registrar_consumo,
    registrar_perda,
    registrar_venda_com_consumo_ui,
    salvar_produto_com_receita,
)

SEED = 42
random.seed(SEED)
rng = np.random.default_rng(SEED)

DB_PATH = ROOT / "cafeteria_estoque.db"


# ---------------------------------------------------------------------------
# "Hoje" simulado
#
# get_lotes_abertos() (app/services/stock_service.py) filtra lotes vencidos
# usando date.today() do sistema, não a data do movimento sendo registrado.
# Isso funciona bem em uso real (o "hoje" do sistema sempre acompanha o
# usuário), mas quebra ao gerar um histórico retroativo: um lote aberto no
# "dia 40" simulado, com validade de 5 dias, ficaria invisível para o FEFO
# assim que criado, porque o "hoje" real do processo é o dia de execução do
# script. Travamos date.today() nesse módulo para acompanhar o dia simulado.
# ---------------------------------------------------------------------------


class _DataSimulada(date):
    _hoje = date.today()

    @classmethod
    def today(cls):
        return cls._hoje


def set_hoje_simulado(dia: date) -> None:
    _DataSimulada._hoje = dia
    stock_service.date = _DataSimulada


def restaurar_data_real() -> None:
    stock_service.date = date


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

MATERIAS_PRIMAS = [
    dict(nome="Café em Pó", unidade="kg", estoque_minimo=1.5, abertura_validade=60,
         preco=100.0, compra=5.0, abertura=1.0, fechado_validade=180,
         fornecedores=["Torrefação Serra Verde", "Café Bom Dia Distribuidora"]),
    dict(nome="Leite Integral", unidade="L", estoque_minimo=8.0, abertura_validade=5,
         preco=6.00, compra=20.0, abertura=2.0, fechado_validade=15,
         fornecedores=["Laticínios Vale Fresco", "Distribuidora Bom Leite"]),
    dict(nome="Leite de Aveia", unidade="L", estoque_minimo=3.0, abertura_validade=7,
         preco=9.50, compra=10.0, abertura=1.0, fechado_validade=180,
         fornecedores=["NutriPlant Bebidas Vegetais"]),
    dict(nome="Açúcar Refinado", unidade="kg", estoque_minimo=3.0, abertura_validade=180,
         preco=5.20, compra=10.0, abertura=2.0, fechado_validade=365,
         fornecedores=["Atacadão Distribuidora"]),
    dict(nome="Chocolate em Pó", unidade="kg", estoque_minimo=1.0, abertura_validade=90,
         preco=85, compra=3.0, abertura=1.0, fechado_validade=270,
         fornecedores=["Doces & Cia Distribuidora"]),
    dict(nome="Matcha em Pó", unidade="kg", estoque_minimo=0.3, abertura_validade=120,
         preco=150.0, compra=1.0, abertura=0.2, fechado_validade=365,
         fornecedores=["Oriental Import Chá"]),
    dict(nome="Polpa de Fruta Mista", unidade="kg", estoque_minimo=2.0, abertura_validade=60,
         preco=18.0, compra=6.0, abertura=1.0, fechado_validade=180,
         fornecedores=["Frutas do Vale Congelados"]),
]

CONSUMIVEIS = [
    dict(nome="Copo Descartável 300ml", unidade="un", estoque_minimo=150, abertura_validade=None,
         preco=0.35, compra=200, abertura=100, fechado_validade=None,
         fornecedores=["Embalagens Rápidas Ltda"]),
    dict(nome="Copo Descartável 500ml", unidade="un", estoque_minimo=100, abertura_validade=None,
         preco=0.45, compra=150, abertura=100, fechado_validade=None,
         fornecedores=["Embalagens Rápidas Ltda"]),
    dict(nome="Tampa para Copo", unidade="un", estoque_minimo=150, abertura_validade=None,
         preco=0.12, compra=300, abertura=150, fechado_validade=None,
         fornecedores=["Embalagens Rápidas Ltda"]),
    dict(nome="Canudo Biodegradável", unidade="un", estoque_minimo=200, abertura_validade=None,
         preco=0.05, compra=500, abertura=250, fechado_validade=None,
         fornecedores=["EcoPack Descartáveis"]),
    dict(nome="Guardanapo", unidade="un", estoque_minimo=300, abertura_validade=None,
         preco=0.03, compra=1000, abertura=400, fechado_validade=None,
         fornecedores=["Embalagens Rápidas Ltda"]),
]

PRODUTOS_FINAIS = [
    dict(nome="Pão de Queijo", unidade="un", estoque_minimo=15, abertura_validade=3,
         preco=3.00, compra=42, abertura=20, fechado_validade=20, preco_venda=8.00,
         fornecedores=["Padoca da Vila"]),
    dict(nome="Croissant", unidade="un", estoque_minimo=10, abertura_validade=2,
         preco=2.90, compra=40, abertura=12, fechado_validade=10, preco_venda=10.00,
         fornecedores=["Padoca da Vila"]),
    dict(nome="Cookie", unidade="un", estoque_minimo=12, abertura_validade=7,
         preco=7.00, compra=30, abertura=15, fechado_validade=30, preco_venda=15.00,
         fornecedores=["Doceria Doce Encanto"]),
    dict(nome="Brownie", unidade="un", estoque_minimo=10, abertura_validade=5,
         preco=9.00, compra=30, abertura=12, fechado_validade=20, preco_venda=18.00,
         fornecedores=["Doceria Doce Encanto"]),
    dict(nome="Torta de Limão (fatia)", unidade="un", estoque_minimo=8, abertura_validade=3,
         preco=6.15, compra=13, abertura=8, fechado_validade=10, preco_venda=22.50,
         fornecedores=["Doceria Doce Encanto"]),
    dict(nome="Bolo de Chocolate (fatia)", unidade="un", estoque_minimo=8, abertura_validade=3,
         preco=3.65, compra=13, abertura=8, fechado_validade=10, preco_venda=10.00,
         fornecedores=["Doceria Doce Encanto"]),
    dict(nome="Água Mineral 500ml", unidade="un", estoque_minimo=24, abertura_validade=180,
         preco=1.80, compra=48, abertura=24, fechado_validade=365, preco_venda=5.00,
         fornecedores=["Distribuidora Bebidas Sul"]),
    dict(nome="Refrigerante Lata", unidade="un", estoque_minimo=24, abertura_validade=180,
         preco=2.90, compra=48, abertura=24, fechado_validade=270, preco_venda=6.50,
         fornecedores=["Distribuidora Bebidas Sul"]),
]

RECEITAS = [
    dict(nome="Café Passado", preco_venda=8.00, ingredientes=[
        ("Café em Pó", 0.008), ("Copo Descartável 300ml", 1)]),
    dict(nome="Café com Leite", preco_venda=9.00, ingredientes=[
        ("Café em Pó", 0.010), ("Leite Integral", 0.120), ("Açúcar Refinado", 0.006),
        ("Copo Descartável 300ml", 1)]),
    dict(nome="Cappuccino", preco_venda=14.00, ingredientes=[
        ("Café em Pó", 0.012), ("Leite Integral", 0.150), ("Chocolate em Pó", 0.005),
        ("Copo Descartável 300ml", 1)]),
    dict(nome="Café Gelado", preco_venda=11.00, ingredientes=[
        ("Café em Pó", 0.010), ("Leite Integral", 0.100), ("Açúcar Refinado", 0.010),
        ("Copo Descartável 500ml", 1), ("Tampa para Copo", 1), ("Canudo Biodegradável", 1)]),
    dict(nome="Mocha", preco_venda=16.00, ingredientes=[
        ("Café em Pó", 0.010), ("Leite Integral", 0.120), ("Chocolate em Pó", 0.020),
        ("Copo Descartável 500ml", 1), ("Tampa para Copo", 1), ("Canudo Biodegradável", 1)]),
    dict(nome="Suco Natural", preco_venda=8.00, ingredientes=[
        ("Polpa de Fruta Mista", 0.150), ("Açúcar Refinado", 0.015),
        ("Copo Descartável 500ml", 1), ("Tampa para Copo", 1), ("Canudo Biodegradável", 1)]),
    dict(nome="Matcha Latte", preco_venda=16.00, ingredientes=[
        ("Matcha em Pó", 0.006), ("Leite de Aveia", 0.150), ("Açúcar Refinado", 0.008),
        ("Copo Descartável 500ml", 1), ("Tampa para Copo", 1), ("Canudo Biodegradável", 1)]),
]

CATALOGO_ESTOCADO = {item["nome"]: item for item in MATERIAS_PRIMAS + CONSUMIVEIS + PRODUTOS_FINAIS}
RECEITAS_POR_NOME = {item["nome"]: item for item in RECEITAS}

POPULARIDADE = {
    "Café Passado": 0.85,
    "Café com Leite": 0.80,
    "Cappuccino": 1.00,
    "Café Gelado": 0.55,
    "Mocha": 0.50,
    "Suco Natural": 0.45,
    "Matcha Latte": 0.35,
    "Pão de Queijo": 0.65,
    "Croissant": 0.45,
    "Cookie": 0.40,
    "Brownie": 0.40,
    "Torta de Limão (fatia)": 0.30,
    "Bolo de Chocolate (fatia)": 0.35,
    "Água Mineral 500ml": 0.30,
    "Refrigerante Lata": 0.30,
}
CARDAPIO = list(POPULARIDADE.keys())
ITENS_FRIOS = {"Café Gelado", "Suco Natural", "Matcha Latte", "Água Mineral 500ml", "Refrigerante Lata"}
ITENS_QUENTES = {"Café Passado", "Café com Leite", "Cappuccino", "Mocha"}

GASTOS_FIXOS = [
    ("Aluguel do ponto comercial", 2600.0),
    ("Energia elétrica", 480.0),
    ("Água e esgoto", 150.0),
    ("Internet e telefonia", 130.0),
    ("Salários da equipe", 4200.0),
    ("Honorários contábeis", 350.0),
]
GASTOS_VARIAVEIS = [
    ("Manutenção de equipamentos", 80, 400),
    ("Material de limpeza", 60, 180),
    ("Gás de cozinha", 120, 220),
    ("Marketing e redes sociais", 100, 350),
    ("Manutenção predial", 100, 600),
    ("Taxas da maquininha de cartão", 150, 500),
]

PRODUTOS_SEM_REPOSICAO_FINAL = {"Leite de Aveia", "Matcha em Pó", "Copo Descartável 500ml"}
PRODUTOS_PERECIVEIS_QUEBRA = [
    "Leite Integral", "Leite de Aveia", "Polpa de Fruta Mista",
    "Pão de Queijo", "Croissant", "Torta de Limão (fatia)", "Bolo de Chocolate (fatia)",
]

DIA_SEMANA_FATOR = {0: 0.75, 1: 0.70, 2: 0.75, 3: 0.85, 4: 1.05, 5: 1.40, 6: 1.20}
LAMBDA_BASE = 45.0

DATA_FIM = date.today()
DATA_INICIO = DATA_FIM - timedelta(days=179)
REFORMA_INICIO = DATA_INICIO + timedelta(days=100)
REFORMA_FIM = REFORMA_INICIO + timedelta(days=4)

# Estado da simulação (preenchido em simular())
PRODUCT_IDS: dict[str, int] = {}
META: dict[int, dict] = {}
FECHADO: dict[int, float] = {}
LOTES: dict[int, list[dict]] = {}
ULTIMA_ENTRADA: dict[int, int] = {}


# ---------------------------------------------------------------------------
# Setup do banco e catálogo
# ---------------------------------------------------------------------------


def resetar_banco() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Banco removido: {DB_PATH}")
    Base.metadata.drop_all(bind=engine)
    init_db()
    print("Schema recriado com tenant padrão.")


def criar_catalogo() -> dict[str, int]:
    print("Criando catálogo de produtos...")

    for item in MATERIAS_PRIMAS:
        salvar_produto_com_receita(
            nome=item["nome"], tipo_produto="materia_prima", unidade_medida=item["unidade"],
            estoque_minimo=item["estoque_minimo"], controla_abertura=True,
            validade_apos_abertura=item["abertura_validade"], preco_venda=None, ingredientes=[],
        )
    for item in CONSUMIVEIS:
        salvar_produto_com_receita(
            nome=item["nome"], tipo_produto="consumivel", unidade_medida=item["unidade"],
            estoque_minimo=item["estoque_minimo"], controla_abertura=True,
            validade_apos_abertura=item["abertura_validade"], preco_venda=None, ingredientes=[],
        )

    ids_ingredientes = produtos_ativos_opcoes()

    # produto_final tem controla_abertura forçado para False por criar_produto,
    # mas a venda ainda consome de lotes abertos (mesmo mecanismo do FEFO das
    # receitas) — por isso abrimos lotes para eles também via registrar_abertura
    # direto, independente da flag.
    for item in PRODUTOS_FINAIS:
        salvar_produto_com_receita(
            nome=item["nome"], tipo_produto="produto_final", unidade_medida=item["unidade"],
            estoque_minimo=item["estoque_minimo"], controla_abertura=True,
            validade_apos_abertura=item["abertura_validade"], preco_venda=item["preco_venda"],
            ingredientes=[],
        )

    for item in RECEITAS:
        ingredientes = [
            {"ingredient_id": ids_ingredientes[nome_ing], "quantidade_estoque": qtd}
            for nome_ing, qtd in item["ingredientes"]
        ]
        salvar_produto_com_receita(
            nome=item["nome"], tipo_produto="receita", unidade_medida="un",
            estoque_minimo=0, controla_abertura=False, validade_apos_abertura=None,
            preco_venda=item["preco_venda"], ingredientes=ingredientes,
        )

    print("Catálogo criado.")
    return produtos_ativos_opcoes()


# ---------------------------------------------------------------------------
# Motor de estoque (espelha em Python o que os services fazem no banco, para
# decidir quando comprar/abrir sem precisar reconsultar o banco a cada dia)
# ---------------------------------------------------------------------------


def arredondar_para_unidade(m: dict, valor: float, para_cima: bool = False) -> float:
    """Arredondamento "fino", usado no que está ABERTO (em uso): 'un' só
    existe em números inteiros de unidade; 'kg'/'L' arredondam no máximo em
    gramas/ml (3 casas decimais) — a menor variação real. É por isso que só
    as receitas mexem em quantidades pequenas, e o fazem dentro do que já
    foi aberto."""
    valor = round(valor, 6)
    if valor <= 0:
        return 0.0
    if m["unidade"] == "un":
        return float(math.ceil(valor) if para_cima else round(valor))
    fator = 1000
    if para_cima:
        return math.ceil(valor * fator) / fator
    return round(valor, 3)


def arredondar_pacote_fechado(m: dict, valor: float, para_cima: bool = False) -> float:
    """Estoque FECHADO só existe em pacotes fechados inteiros — nunca sobra
    um resto fracionado de embalagem lacrada. Para 'un' (pão de queijo,
    copo...) o pacote é a própria unidade, igual ao estoque aberto. Para
    'kg'/'L' o tamanho do pacote é o valor cadastrado em 'abertura' (o que se
    abre de cada vez — ex.: café em sacos de 1 kg, matcha em latas de
    200 g); comprar ou abrir sempre movimenta um número inteiro desses
    pacotes."""
    if m["unidade"] == "un":
        return arredondar_para_unidade(m, valor, para_cima=para_cima)
    valor = round(valor, 6)
    if valor <= 0:
        return 0.0
    tamanho_pacote = m["abertura"]
    pacotes = valor / tamanho_pacote
    pacotes = math.ceil(pacotes - 1e-6) if para_cima else math.floor(pacotes + 1e-6)
    return round(tamanho_pacote * max(0, pacotes), 6)


def preco_com_variacao(m: dict, dia: date, urgente: bool = False) -> float:
    meses_decorridos = (dia.year - DATA_INICIO.year) * 12 + (dia.month - DATA_INICIO.month)
    inflacao = 1 + 0.01 * meses_decorridos
    ruido = random.uniform(0.95, 1.07)
    premio_urgencia = 1.15 if urgente else 1.0
    return round(m["preco"] * inflacao * ruido * premio_urgencia, 2)


def comprar(nome: str, dia: date, qtd: float | None = None, urgente: bool = False) -> None:
    pid = PRODUCT_IDS[nome]
    m = META[pid]
    qtd = qtd if qtd is not None else m["compra"]
    qtd = arredondar_pacote_fechado(m, qtd, para_cima=True)
    if qtd <= 0:
        return
    fornecedor = random.choice(m["fornecedores"])
    preco = preco_com_variacao(m, dia, urgente=urgente)
    validade = dia + timedelta(days=m["fechado_validade"]) if m.get("fechado_validade") else None
    tempo_entrega = 0 if urgente else random.randint(1, 4)
    resultado = registrar_compra_ui(pid, qtd, preco, dia, validade, fornecedor, tempo_entrega)
    FECHADO[pid] = arredondar_pacote_fechado(m, FECHADO.get(pid, 0.0) + qtd, para_cima=True)
    ULTIMA_ENTRADA[pid] = resultado.id


def abrir(nome: str, dia: date, qtd: float | None = None, validade="auto") -> int | None:
    pid = PRODUCT_IDS[nome]
    m = META[pid]
    disponivel = FECHADO.get(pid, 0.0)
    qtd = qtd if qtd is not None else m["abertura"]
    qtd = arredondar_pacote_fechado(m, min(qtd, disponivel))
    if qtd <= 0:
        return None

    if validade == "auto":
        validade_calc = dia + timedelta(days=m["abertura_validade"]) if m.get("abertura_validade") else None
    else:
        validade_calc = validade

    def _abrir_no_banco(quantidade: float):
        with session_scope() as session:
            mov = registrar_abertura(
                session, product_id=pid, quantidade=quantidade, data_abertura=dia,
                validade_aberto=validade_calc,
            )
            return (
                session.query(StockLot)
                .filter_by(abertura_movement_id=mov.id)
                .one()
                .id
            )

    try:
        lot_id = _abrir_no_banco(qtd)
    except ValueError:
        # Pedir o último pacote fechado que resta às vezes esbarra em ruído
        # de soma em ponto flutuante no SUM do banco (0.2 vira
        # 0.19999999999999996 depois de somar vários movimentos). Tenta de
        # novo com uma quantidade infinitesimalmente menor antes de desistir.
        qtd_retry = round(qtd - 1e-6, 9) if m["unidade"] != "un" else qtd - 1
        if qtd_retry <= 0:
            print(f"  [aviso] abertura de '{nome}' ignorada: pacote fechado indisponível")
            return None
        try:
            lot_id = _abrir_no_banco(qtd_retry)
            qtd = qtd_retry
        except ValueError as e:
            print(f"  [aviso] abertura de '{nome}' ignorada: {e}")
            return None

    FECHADO[pid] = arredondar_pacote_fechado(m, FECHADO[pid] - qtd)
    LOTES[pid].append({"lot_id": lot_id, "qtd": qtd, "validade": validade_calc})
    return lot_id


def saldo_aberto(nome: str) -> float:
    pid = PRODUCT_IDS[nome]
    return sum(l["qtd"] for l in LOTES[pid])


def _consumir_localmente(pid: int, quantidade: float) -> None:
    """Espelha em Python o consumo FEFO (mais antigo primeiro) feito no banco."""
    restante = quantidade
    novas = []
    for lote in LOTES[pid]:
        if restante > 1e-9 and lote["qtd"] > 1e-9:
            usar = min(lote["qtd"], restante)
            lote["qtd"] = round(lote["qtd"] - usar, 6)
            restante -= usar
        if lote["qtd"] > 1e-6:
            novas.append(lote)
    LOTES[pid] = novas


def descartar_vencidos(dia: date) -> None:
    """Lotes cuja validade já passou ficam invisíveis ao FEFO real; baixamos
    o saldo remanescente como perda para fechar o lote e registrar a quebra.

    Usa o saldo REAL do lote no banco (não o `lote["qtd"]` espelhado em
    Python) — uma venda pode fazer um split de FEFO entre dois lotes que não
    bate 1:1 com a simulação local (ex.: a venda mistura café + leite; o
    espelho local decide "qual lote" de forma independente do FEFO real do
    banco), o que deixava um resto preso num lote "fantasma": fechado para o
    FEFO (por estar vencido), mas ainda somado no total de estoque aberto."""
    for nome in CATALOGO_ESTOCADO:
        pid = PRODUCT_IDS[nome]
        for lote in list(LOTES[pid]):
            if lote["validade"] and lote["validade"] < dia and lote["qtd"] > 1e-6:
                try:
                    with session_scope() as session:
                        lot_db = session.get(StockLot, lote["lot_id"])
                        saldo_real = lot_db.quantidade_atual if lot_db else 0.0
                        if saldo_real > 1e-9:
                            registrar_perda(
                                session, product_id=pid,
                                quantidade=round(saldo_real, 6),
                                motivo="Vencimento - produto fora do prazo de validade",
                                data_perda=dia, estoque_afetado="aberto", lot_id=lote["lot_id"],
                                observacao="Descarte automático (lote expirado antes do consumo).",
                            )
                except ValueError as e:
                    print(f"  [aviso] descarte de '{nome}' ignorado: {e}")
                LOTES[pid] = [l for l in LOTES[pid] if l["lot_id"] != lote["lot_id"]]


def repor_se_necessario(nome: str, dia: date, prob_atraso: float = 0.04) -> None:
    pid = PRODUCT_IDS[nome]
    m = META[pid]
    limiar = m["abertura"] * 0.25
    if saldo_aberto(nome) >= limiar:
        return
    if random.random() < prob_atraso:
        return  # reposição atrasada de propósito — gera alerta real por alguns dias
    if FECHADO.get(pid, 0.0) < m["abertura"]:
        comprar(nome, dia)
    abrir(nome, dia)


def garantir_quantidade(nome: str, dia: date, necessario: float, prob_falta: float = 0.03) -> float:
    """Garante estoque aberto suficiente pouco antes do consumo, abrindo
    sempre em múltiplos inteiros do tamanho de pacote/embalagem cadastrado —
    ex.: café sempre abre de 1 em 1 kg, pão de queijo sempre de 20 em 20
    unidades — nunca uma quantidade calculada arbitrária. Devolve quanto
    ficará de fato disponível: pode ser menor que o necessário, o que gera
    um aviso real na venda."""
    pid = PRODUCT_IDS[nome]
    m = META[pid]
    disponivel = saldo_aberto(nome)
    if disponivel < necessario and random.random() > prob_falta:
        faltante = necessario - disponivel
        pacotes = max(1, math.ceil(round(faltante / m["abertura"], 6) - 1e-9))
        qtd_abrir = m["abertura"] * pacotes
        if FECHADO.get(pid, 0.0) < qtd_abrir:
            faltante_fechado = qtd_abrir - FECHADO.get(pid, 0.0)
            pacotes_compra = max(1, math.ceil(round(faltante_fechado / m["compra"], 6) - 1e-9))
            comprar(nome, dia, qtd=m["compra"] * pacotes_compra, urgente=True)
        abrir(nome, dia, qtd=qtd_abrir)
        disponivel = saldo_aberto(nome)
    efetivo = min(necessario, disponivel)
    _consumir_localmente(pid, efetivo)
    return efetivo


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------


def fator_sazonal(nome: str, mes: int) -> float:
    if nome in ITENS_FRIOS:
        if mes in (1, 2, 3):
            return 1.5
        if mes in (6, 7):
            return 0.6
    if nome in ITENS_QUENTES:
        if mes in (6, 7):
            return 1.3
        if mes in (1, 2, 3):
            return 0.8
    return 1.0


def registrar_venda_item(nome: str, quantidade: float, dia: date, desconto: bool) -> None:
    pid = PRODUCT_IDS[nome]
    if nome in RECEITAS_POR_NOME:
        for ing_nome, qtd_unitaria in RECEITAS_POR_NOME[nome]["ingredientes"]:
            garantir_quantidade(ing_nome, dia, qtd_unitaria * quantidade)
        preco_venda = RECEITAS_POR_NOME[nome]["preco_venda"]
    else:
        garantir_quantidade(nome, dia, quantidade)
        preco_venda = CATALOGO_ESTOCADO[nome]["preco_venda"]

    valor_unitario = round(preco_venda * 0.9, 2) if desconto else preco_venda
    registrar_venda_com_consumo_ui(pid, quantidade, valor_unitario, dia)


def gerar_vendas_do_dia(dia: date, lam: float) -> int:
    n_transacoes = int(rng.poisson(lam))
    for _ in range(n_transacoes):
        n_itens = random.choices([1, 2, 3], weights=[0.62, 0.30, 0.08])[0]
        pesos = [POPULARIDADE[nome] * fator_sazonal(nome, dia.month) for nome in CARDAPIO]
        itens = random.choices(CARDAPIO, weights=pesos, k=n_itens)
        desconto = random.random() < 0.04
        for nome in itens:
            qtd = random.choices([1, 2], weights=[0.85, 0.15])[0]
            registrar_venda_item(nome, qtd, dia, desconto)
    return n_transacoes


def consumir_guardanapos(dia: date, transacoes_semana: int) -> None:
    necessario = max(1, int(transacoes_semana * random.uniform(1.0, 1.8)))
    garantir_quantidade("Guardanapo", dia, necessario, prob_falta=0.0)
    pid = PRODUCT_IDS["Guardanapo"]
    try:
        with session_scope() as session:
            registrar_consumo(
                session, product_id=pid, quantidade=necessario, data_consumo=dia,
                observacao="Consumo semanal estimado de guardanapos no balcão.",
            )
    except ValueError as e:
        print(f"  [aviso] consumo de guardanapos ignorado: {e}")


# ---------------------------------------------------------------------------
# Perdas e ajustes
# ---------------------------------------------------------------------------


def talvez_registrar_perda_avaria(dia: date) -> None:
    if random.random() > 0.12:
        return
    nome = random.choice(PRODUTOS_PERECIVEIS_QUEBRA)
    pid = PRODUCT_IDS[nome]
    m = META[pid]
    disponivel = saldo_aberto(nome)
    if disponivel < 0.05:
        return
    qtd = arredondar_para_unidade(m, min(disponivel * random.uniform(0.05, 0.2), disponivel))
    if qtd <= 0:
        return
    motivo = random.choice([
        "Quebra/dano no manuseio", "Contaminação/queda no balcão", "Produto amassado na entrega",
    ])
    try:
        with session_scope() as session:
            registrar_perda(
                session, product_id=pid, quantidade=qtd, motivo=motivo,
                data_perda=dia, estoque_afetado="aberto",
            )
    except ValueError as e:
        print(f"  [aviso] perda de '{nome}' ignorada: {e}")
        return
    _consumir_localmente(pid, qtd)


def registrar_ajustes_mensais(dia: date) -> None:
    candidatos = [n for n in CATALOGO_ESTOCADO if FECHADO.get(PRODUCT_IDS[n], 0.0) > 0]
    if not candidatos:
        return
    for nome in random.sample(candidatos, k=min(3, len(candidatos))):
        pid = PRODUCT_IDS[nome]
        m = META[pid]
        fechado_atual = FECHADO.get(pid, 0.0)
        direcao = random.choices(["saida", "entrada"], weights=[0.7, 0.3])[0]
        if m["unidade"] == "un":
            qtd = float(random.randint(1, max(1, int(fechado_atual * 0.05))))
        else:
            # Correção de contagem em estoque FECHADO só pode achar/perder
            # pacotes lacrados inteiros (ex.: "faltou 1 saco de café"), nunca
            # uma fração de pacote.
            pacotes_fechados = int(round(fechado_atual / m["abertura"]))
            pacotes_ajuste = random.choices([1, 2], weights=[0.8, 0.2])[0]
            if direcao == "saida":
                pacotes_ajuste = min(pacotes_ajuste, max(1, pacotes_fechados))
            qtd = m["abertura"] * pacotes_ajuste
        if qtd <= 0:
            continue
        motivo = (
            "Contagem mensal de estoque - diferença encontrada"
            if direcao == "saida" else
            "Contagem mensal de estoque - sobra encontrada"
        )
        try:
            with session_scope() as session:
                registrar_ajuste(
                    session, product_id=pid, quantidade=qtd, direcao=direcao, motivo=motivo,
                    data_ajuste=dia, movimento_referencia_id=ULTIMA_ENTRADA.get(pid),
                    observacao="Ajuste gerado na conferência mensal de estoque.",
                )
        except ValueError as e:
            print(f"  [aviso] ajuste de '{nome}' ignorado: {e}")
            continue
        if direcao == "saida":
            FECHADO[pid] = arredondar_pacote_fechado(m, FECHADO[pid] - qtd)
        else:
            FECHADO[pid] = arredondar_pacote_fechado(m, FECHADO.get(pid, 0.0) + qtd, para_cima=True)


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------


def registrar_gastos_fixos(dia: date) -> None:
    for nome, valor_base in GASTOS_FIXOS:
        valor = round(valor_base * random.uniform(0.96, 1.06), 2)
        criar_gasto(nome, "fixo", valor, dia)


def talvez_registrar_gasto_variavel(dia: date) -> None:
    if random.random() > 0.18:
        return
    nome, minimo, maximo = random.choice(GASTOS_VARIAVEIS)
    valor = round(random.uniform(minimo, maximo), 2)
    criar_gasto(nome, "variavel", valor, dia)


# ---------------------------------------------------------------------------
# Simulação principal
# ---------------------------------------------------------------------------


def simular() -> None:
    global PRODUCT_IDS, META

    ids = criar_catalogo()
    PRODUCT_IDS = ids
    META = {ids[nome]: item for nome, item in CATALOGO_ESTOCADO.items()}
    for nome in CATALOGO_ESTOCADO:
        pid = ids[nome]
        FECHADO[pid] = 0.0
        LOTES[pid] = []

    set_hoje_simulado(DATA_INICIO)

    print(f"Estoque inicial em {DATA_INICIO.isoformat()}...")
    for nome in CATALOGO_ESTOCADO:
        comprar(nome, DATA_INICIO, qtd=META[PRODUCT_IDS[nome]]["compra"] * random.choice([1, 2]))
        abrir(nome, DATA_INICIO)

    total_dias = (DATA_FIM - DATA_INICIO).days + 1
    total_transacoes = 0
    transacoes_semana = 0

    print(f"Simulando {total_dias} dias, de {DATA_INICIO.isoformat()} a {DATA_FIM.isoformat()}...")
    print(f"Reforma (loja fechada): {REFORMA_INICIO.isoformat()} a {REFORMA_FIM.isoformat()}")

    for dia_idx in range(total_dias):
        dia = DATA_INICIO + timedelta(days=dia_idx)
        set_hoje_simulado(dia)

        if dia.day == 5:
            registrar_gastos_fixos(dia)

        if REFORMA_INICIO <= dia <= REFORMA_FIM:
            if dia == REFORMA_INICIO:
                criar_gasto("Reforma - pintura e manutenção do salão", "variavel", 3500.0, dia)
            continue

        descartar_vencidos(dia)

        dias_restantes = total_dias - dia_idx
        for nome in CATALOGO_ESTOCADO:
            if nome in PRODUTOS_SEM_REPOSICAO_FINAL and dias_restantes <= 7:
                continue
            repor_se_necessario(nome, dia)

        talvez_registrar_gasto_variavel(dia)

        if dia.day in (10, 25):
            registrar_ajustes_mensais(dia)

        talvez_registrar_perda_avaria(dia)

        crescimento = 0.85 + 0.35 * (dia_idx / total_dias)
        lam = LAMBDA_BASE * DIA_SEMANA_FATOR[dia.weekday()] * crescimento
        n_transacoes = gerar_vendas_do_dia(dia, lam)
        total_transacoes += n_transacoes
        transacoes_semana += n_transacoes

        if dia.weekday() == 6:
            consumir_guardanapos(dia, transacoes_semana)
            transacoes_semana = 0

        if dia_idx % 30 == 0:
            print(f"  ... dia {dia_idx + 1}/{total_dias} ({dia.isoformat()}) "
                  f"— {total_transacoes} transações até aqui")

    print(f"Simulação concluída: {total_transacoes} transações de venda em {total_dias} dias.")

    _finalizar_estado_atual()


def _finalizar_estado_atual() -> None:
    """Garante que 'hoje' (data real) mostre alertas de verdade na página
    Alertas: produtos abaixo do mínimo, lote perto do vencimento e uma
    correção recente — sem isso, o histórico simulado terminaria sempre bem
    estocado e a tela de alertas ficaria vazia na demonstração ao vivo."""
    hoje = date.today()
    set_hoje_simulado(hoje)

    def _perda_com_retry(pid: int, quantidade: float, estoque_afetado: str, unidade: str) -> float | None:
        """Registra a perda; se o banco recusar por ruído de soma em ponto
        flutuante (pedir "tudo que tem" raramente bate na última casa
        decimal), tenta de novo com uma quantidade infinitesimalmente
        menor antes de desistir."""
        for tentativa_qtd in (
            quantidade,
            round(quantidade - 1e-6, 9) if unidade != "un" else quantidade - 1,
        ):
            if tentativa_qtd <= 0:
                continue
            try:
                with session_scope() as session:
                    registrar_perda(
                        session, product_id=pid, quantidade=tentativa_qtd,
                        motivo="Fornecedor atrasou reposição — estoque não normalizado a tempo",
                        data_perda=hoje, estoque_afetado=estoque_afetado,
                    )
                return tentativa_qtd
            except ValueError:
                continue
        return None

    for nome in PRODUTOS_SEM_REPOSICAO_FINAL:
        pid = PRODUCT_IDS[nome]
        m = META[pid]
        total_atual = FECHADO.get(pid, 0.0) + saldo_aberto(nome)
        alvo = m["estoque_minimo"] * random.uniform(0.4, 0.75)
        excedente = arredondar_para_unidade(m, total_atual - alvo)
        if excedente <= 0:
            continue

        tirar_aberto = arredondar_para_unidade(m, min(excedente, saldo_aberto(nome)))
        if tirar_aberto > 0:
            usado = _perda_com_retry(pid, tirar_aberto, "aberto", m["unidade"])
            if usado is not None:
                _consumir_localmente(pid, usado)
                excedente = arredondar_para_unidade(m, excedente - usado)
            else:
                print(f"  [aviso] ajuste final de '{nome}' (aberto) ignorado")

        # O que resta força pacotes FECHADOS inteiros — não sobra fração de
        # embalagem lacrada.
        if excedente > 0 and FECHADO.get(pid, 0.0) > 0:
            tirar_fechado = arredondar_pacote_fechado(m, min(excedente, FECHADO[pid]))
            if tirar_fechado > 0:
                usado = _perda_com_retry(pid, tirar_fechado, "fechado", m["unidade"])
                if usado is not None:
                    FECHADO[pid] = arredondar_pacote_fechado(m, FECHADO[pid] - usado)
                else:
                    print(f"  [aviso] ajuste final de '{nome}' (fechado) ignorado")

    # Lote de leite vencendo em 2 dias, para aparecer em "vencendo em breve"
    # (abre um pacote fechado inteiro, igual a qualquer outra abertura)
    pid_leite = PRODUCT_IDS["Leite Integral"]
    pacote_leite = META[pid_leite]["abertura"]
    if FECHADO.get(pid_leite, 0.0) < pacote_leite:
        comprar("Leite Integral", hoje, qtd=META[pid_leite]["compra"])
    abrir("Leite Integral", hoje, qtd=pacote_leite, validade=hoje + timedelta(days=2))

    # Correção recente para aparecer em "Correções recentes" — 1 pacote
    # fechado inteiro de café (nunca fração de pacote lacrado).
    pid_cafe = PRODUCT_IDS["Café em Pó"]
    m_cafe = META[pid_cafe]
    qtd_correcao = m_cafe["abertura"]
    if FECHADO.get(pid_cafe, 0.0) >= qtd_correcao:
        try:
            with session_scope() as session:
                registrar_ajuste(
                    session, product_id=pid_cafe, quantidade=qtd_correcao, direcao="saida",
                    motivo="Contagem mensal de estoque - diferença encontrada",
                    data_ajuste=hoje - timedelta(days=1),
                    movimento_referencia_id=ULTIMA_ENTRADA.get(pid_cafe),
                    observacao="Ajuste gerado na conferência mensal de estoque.",
                )
            FECHADO[pid_cafe] = arredondar_pacote_fechado(m_cafe, FECHADO[pid_cafe] - qtd_correcao)
        except ValueError as e:
            print(f"  [aviso] correção final ignorada: {e}")

    restaurar_data_real()


def imprimir_resumo() -> None:
    with SessionLocal() as s:
        print("\n=== Resumo do dataset gerado ===")
        print(f"Produtos: {s.query(Product).count()}")
        print(f"Movimentações de estoque: {s.query(StockMovement).count()}")
        print(f"Vendas: {s.query(Sale).count()}")
        print(f"Lotes (abertos + fechados): {s.query(StockLot).count()}")
        print(f"Gastos: {s.query(Expense).count()}")

    print("\n=== Alertas ativos hoje ===")
    baixos = produtos_abaixo_minimo()
    if baixos:
        for p in baixos:
            print(f"  - {p['nome']}: {p['estoque_total']:.2f} {p['unidade_medida']} "
                  f"(mínimo {p['estoque_minimo']})")
    else:
        print("  (nenhum)")

    print("\n=== Lotes vencendo em breve ===")
    vencendo = abertos_proximos_vencimento(dias=3)
    if vencendo:
        for lote in vencendo:
            print(f"  - {lote['produto']}: vence em {lote['dias_restantes']} dia(s)")
    else:
        print("  (nenhum)")

    print("\n=== Correções recentes ===")
    correcoes = correcoes_recentes(limit=5)
    if correcoes:
        for c in correcoes:
            print(f"  - {c['produto']}: {c['direcao']} {c['quantidade']} ({c['motivo']})")
    else:
        print("  (nenhuma)")


if __name__ == "__main__":
    resetar_banco()
    simular()
    imprimir_resumo()
