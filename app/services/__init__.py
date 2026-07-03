from app.services.product_service import (
    _get_product,
    criar_produto,
    desativar_produto,
    delete_product,
    pode_excluir
    )
from app.services.stock_service import (
    get_estoque_total,
    get_lotes_abertos,
    get_estoque_aberto,
    get_estoque_fechado,
    _consumir_de_lotes
    )
from app.services.dashboard_service import (
    get_dashboard_estoque,
    get_produtos_abaixo_minimo,
    get_abertos_proximos_vencimento,
    get_lotes_abertos_detalhados,
    get_historico_produto,
    get_custo_medio,
    get_valor_estoque_total,
    get_total_receita,
    get_total_investido,
    get_total_gastos,
    get_total_vendas,
    get_lucro_estimado,
    )
from app.services.recipe_service import (
    criar_receita_item,
    desativar_receita,
    remover_receita,
    remover_receita_item,
    atualizar_quantidade_receita,
    buscar_ingredientes_receita,
    mudar_preco_receita,
    pode_excluir_receita,
    adicionar_ingrediente_receita,
    obter_receitas_ativas
    )

from app.services.movement_services import (
    registrar_abertura,
    registrar_consumo,
    registrar_ajuste,
    registrar_entrada,
    consumir_lote_completo,
    registrar_perda,
    registrar_estorno,
    )

from app.services.cost_service import (
    calcular_custo_receita,
    get_custo_unitario_receita
    )

from app.services.application_service import(
    adicionar_ingrediente_receita_ui,
    alternar_produto_ui,
    alternar_receita_ui,
    atualizar_quantidade_receita_ui,
    catalogo_produtos,
    copiar_ingredientes_receita,
    custo_receita_ui,
    custo_unitario_produto_ui,
    excluir_produto_ui,
    mudar_preco_receita_ui,
    remover_receita_item_ui,
    remover_receita_ui,
    salvar_produto_com_receita,
    dashboard_estoque,
    historico_produto,
    registrar_ajuste_ui,
    registrar_compra_ui,
    abertos_proximos_vencimento,
    correcoes_recentes,
    produtos_abaixo_minimo,
    criar_gasto,
    dados_dashboard_financeiro,
    excluir_gasto,
    obter_gasto,
    registrar_consumo_ui,
    registrar_perda_ui,
    esgotar_lote,
    lotes_abertos_detalhados,
    produtos_ativos_opcoes,
    abrir_produto,
    listar_produtos_vendaveis,
    registrar_venda_ui,
    registrar_venda_com_consumo_ui,
    listar_vendas_ui,
    resumo_vendas_hoje,
)