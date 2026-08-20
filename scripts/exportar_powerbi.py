"""Exporta o banco para CSVs prontos para Power BI, em modelo estrela.

Gera em powerbi/dados/:
    dim_produtos.csv       — catálogo (atributos estáveis: nome, tipo, unidade,
                              estoque mínimo configurado, preço). NÃO tem estoque
                              atual — isso é medida, não atributo, e mudaria a
                              cada exportação sem deixar rastro.
    dim_calendario.csv     — tabela calendário cobrindo o período dos dados
    fato_vendas.csv        — uma linha por venda
    fato_movimentacoes.csv — ledger de estoque (entrada/abertura/consumo/perda/ajuste/estorno)
    fato_gastos.csv        — gastos operacionais ativos (exclui os com soft-delete)
    fato_estoque.csv       — "periodic snapshot fact table" (padrão Kimball para
                              estoque): 1 linha por produto por DIA do período
                              inteiro (não só "hoje"). O ledger de movimentações
                              já cobre os 6 meses de simulação, então dá pra
                              RECONSTRUIR o saldo de qualquer dia passado sem
                              precisar esperar — é só repassar (replay) as
                              movimentações e os lotes até aquela data.

Uso:
    python scripts/exportar_powerbi.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal  # noqa: E402
from app.models import Expense, Product, Sale, StockLot, StockMovement  # noqa: E402
from app.models.enums import ProductType  # noqa: E402
from app.services import get_dashboard_estoque  # noqa: E402

OUT_DIR = ROOT / "powerbi" / "dados"

DIAS_SEMANA_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _escrever_csv(nome: str, linhas: list[dict]) -> None:
    caminho = OUT_DIR / nome
    if not linhas:
        print(f"  [aviso] {nome}: nenhuma linha, pulei.")
        return
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)
    print(f"  {nome}: {len(linhas)} linhas")


def exportar_dim_produtos(session) -> None:
    """Só atributos que descrevem o produto — nada que varie a cada venda."""
    produtos = session.query(Product).order_by(Product.nome).all()

    linhas = [
        {
            "produto_id": p.id,
            "nome": p.nome,
            "tipo_produto": p.tipo_produto.value,
            "unidade_medida": p.unidade_medida,
            "estoque_minimo": p.estoque_minimo,
            "preco_venda": float(p.preco_venda) if p.preco_venda is not None else None,
            "ativo": p.ativo,
        }
        for p in produtos
    ]
    _escrever_csv("dim_produtos.csv", linhas)


_TIPOS_FECHADO = {"entrada", "estorno", "abertura", "perda", "ajuste"}


def _sinal_fechado(m: StockMovement) -> float:
    """Mesmo critério de get_estoque_fechado (stock_service.py), mas devolve
    o delta pronto em vez de somar direto — para dar num replay dia a dia."""
    if m.tipo in ("entrada", "estorno"):
        return m.quantidade
    if m.tipo == "abertura":
        return -m.quantidade
    if m.tipo == "perda":
        return -m.quantidade if m.estoque_afetado == "fechado" else 0.0
    if m.tipo == "ajuste":
        return m.quantidade if m.direcao == "entrada" else -m.quantidade
    return 0.0


def exportar_fato_estoque(session, datas_calendario: list[date]) -> None:
    """Periodic snapshot fact table: saldo de estoque de cada produto em CADA
    dia do período coberto pelo calendário — reconstruído a partir do ledger
    de movimentações e dos lotes, não só do saldo "de hoje". Ligada a
    dim_produtos (produto_id) e dim_calendario (data)."""
    produtos = (
        session.query(Product)
        .filter(Product.tipo_produto != ProductType.RECEITA)
        .all()
    )

    # Deltas de fechado por produto, ordenados por data — dá pra andar com um
    # ponteiro em vez de re-somar tudo a cada dia.
    deltas_fechado: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for m in (
        session.query(StockMovement)
        .filter(StockMovement.tipo.in_(_TIPOS_FECHADO))
        .order_by(StockMovement.data_movimento)
        .all()
    ):
        delta = _sinal_fechado(m)
        if delta:
            deltas_fechado[m.product_id].append((m.data_movimento, delta))

    # Lotes por produto + as movimentações que consomem cada lote (consumo e
    # perda no estoque aberto), pra reconstruir o saldo de cada lote dia a dia.
    lotes_por_produto: dict[int, list[StockLot]] = defaultdict(list)
    for lote in session.query(StockLot).all():
        lotes_por_produto[lote.product_id].append(lote)

    consumos_por_lote: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for m in (
        session.query(StockMovement)
        .filter(StockMovement.lot_id.isnot(None))
        .filter(StockMovement.tipo.in_(["consumo", "perda"]))
        .order_by(StockMovement.data_movimento)
        .all()
    ):
        consumos_por_lote[m.lot_id].append((m.data_movimento, m.quantidade))

    linhas = []
    for p in produtos:
        deltas = deltas_fechado.get(p.id, [])
        idx_fechado = 0
        saldo_fechado = 0.0

        # Estado de cada lote deste produto: ponteiro no próprio histórico de
        # consumo + saldo corrente — igual ao replay de "abrir/consumir" que
        # o gerador de dados sintéticos faz, só que lendo do banco em vez de
        # simular em memória.
        estado_lotes = [
            {"lote": lote, "idx": 0, "saldo": lote.quantidade_inicial}
            for lote in lotes_por_produto.get(p.id, [])
        ]

        for dia in datas_calendario:
            while idx_fechado < len(deltas) and deltas[idx_fechado][0] <= dia:
                saldo_fechado += deltas[idx_fechado][1]
                idx_fechado += 1

            saldo_aberto = 0.0
            for est in estado_lotes:
                lote = est["lote"]
                if lote.data_abertura > dia:
                    continue
                consumos = consumos_por_lote.get(lote.id, [])
                while est["idx"] < len(consumos) and consumos[est["idx"]][0] <= dia:
                    est["saldo"] -= consumos[est["idx"]][1]
                    est["idx"] += 1
                if lote.validade and lote.validade < dia:
                    continue  # vencido nessa data — FEFO não enxerga mais
                if est["saldo"] > 1e-9:
                    saldo_aberto += est["saldo"]

            total = saldo_fechado + saldo_aberto
            linhas.append({
                "produto_id": p.id,
                "data": dia.isoformat(),
                "estoque_fechado": round(saldo_fechado, 4),
                "estoque_aberto": round(saldo_aberto, 4),
                "estoque_total": round(total, 4),
                "abaixo_minimo": total < p.estoque_minimo,
            })

    _escrever_csv("fato_estoque.csv", linhas)

    # Confere o último dia reconstruído contra o cálculo "ao vivo" do app —
    # se divergir, algo na reconstrução está errado.
    hoje = date.today()
    if datas_calendario and datas_calendario[-1] == hoje:
        ao_vivo = {d["id"]: d for d in get_dashboard_estoque(session)}
        reconstruido_hoje = {l["produto_id"]: l for l in linhas if l["data"] == hoje.isoformat()}
        divergencias = 0
        for pid, real in ao_vivo.items():
            recon = reconstruido_hoje.get(pid)
            if recon and abs(recon["estoque_total"] - real["estoque_total"]) > 0.01:
                divergencias += 1
                print(f"  [aviso] {real['nome']}: reconstruído={recon['estoque_total']} "
                      f"ao vivo={real['estoque_total']}")
        if divergencias == 0:
            print("  (conferido: saldo reconstruído de hoje bate com o cálculo ao vivo do app)")


def exportar_fato_vendas(session) -> None:
    vendas = session.query(Sale).order_by(Sale.data_venda).all()
    linhas = [
        {
            "venda_id": s.id,
            "data": s.data_venda.isoformat(),
            "produto_id": s.product_id,
            "produto_nome": s.produto_nome,
            "quantidade": s.quantidade,
            "valor_unitario": float(s.valor_unitario),
            "valor_total": float(s.valor_total),
        }
        for s in vendas
    ]
    _escrever_csv("fato_vendas.csv", linhas)


def exportar_fato_movimentacoes(session) -> None:
    movs = session.query(StockMovement).order_by(StockMovement.data_movimento).all()
    linhas = [
        {
            "movimento_id": m.id,
            "data": m.data_movimento.isoformat(),
            "produto_id": m.product_id,
            "tipo": m.tipo,
            "quantidade": m.quantidade,
            # Sinal já aplicado: positivo = entrou em estoque, negativo = saiu.
            "quantidade_efetiva": m.get_quantidade_efetiva(),
            "preco_unitario": float(m.preco_unitario) if m.preco_unitario is not None else None,
            "preco_total": float(m.preco_total) if m.preco_total is not None else None,
            "fornecedor": m.fornecedor,
            "estoque_afetado": m.estoque_afetado,
            "motivo": m.motivo,
        }
        for m in movs
    ]
    _escrever_csv("fato_movimentacoes.csv", linhas)


def exportar_fato_gastos(session) -> None:
    gastos = (
        session.query(Expense)
        .filter(Expense.is_deleted.is_(False))
        .order_by(Expense.data)
        .all()
    )
    linhas = [
        {
            "gasto_id": e.id,
            "data": e.data.isoformat(),
            "nome": e.nome,
            "categoria": e.categoria,
            "valor": float(e.valor),
        }
        for e in gastos
    ]
    _escrever_csv("fato_gastos.csv", linhas)


def exportar_dim_calendario(session) -> list[date]:
    hoje = date.today()
    datas = [hoje]  # garante que "hoje" sempre existe no calendário
    datas += [s.data_venda for s in session.query(Sale.data_venda).all()]
    datas += [m.data_movimento for m in session.query(StockMovement.data_movimento).all()]
    datas += [e.data for e in session.query(Expense.data).all()]

    data_min, data_max = min(datas), max(datas)

    linhas = []
    todas_as_datas = []
    dia = data_min
    while dia <= data_max:
        todas_as_datas.append(dia)
        linhas.append({
            "Data": dia.isoformat(),
            "Ano": dia.year,
            "Mes": dia.month,
            "NomeMes": MESES_PT[dia.month - 1],
            "AnoMes": f"{dia.year}-{dia.month:02d}",
            "Trimestre": f"T{(dia.month - 1) // 3 + 1}",
            "DiaSemana": dia.weekday(),
            "NomeDiaSemana": DIAS_SEMANA_PT[dia.weekday()],
            "FimDeSemana": dia.weekday() >= 5,
        })
        dia += timedelta(days=1)
    _escrever_csv("dim_calendario.csv", linhas)
    return todas_as_datas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Exportando para {OUT_DIR}...")
    with SessionLocal() as session:
        exportar_dim_produtos(session)
        datas_calendario = exportar_dim_calendario(session)
        exportar_fato_vendas(session)
        exportar_fato_movimentacoes(session)
        exportar_fato_gastos(session)
        exportar_fato_estoque(session, datas_calendario)
    print("Concluído.")


if __name__ == "__main__":
    main()
