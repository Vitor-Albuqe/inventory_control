from datetime import date, timedelta
from collections import Counter
import numpy as np
import random

# =======================
#   Simulação de Vendas
# =======================

rng = np.random.default_rng(42)

um_dia = timedelta(days=1)

hoje = date.today()

dia = hoje - timedelta(days=30)

semana_d = dia.weekday()

fator_dia = {0: 0.6, 1: 0.5, 2: 0.6, 3: 0.7, 4: 0.8, 5: 1.0, 6: 1.2}

dia_da_semana = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}



catalogo = { "Café_passado": 0.9, "Cappuccino": 0.7, "Pão de Queijo": 0.7, "Mocha": 0.6, "Café Gelado": 0.5, "Croissant": 0.5, "Torta": 0.4, "Cookie": 0.4, "Brownie": 0.4, "Bolo de Chocolate": 0.3, "Matcha": 0.3 }

produtos = list(catalogo.keys())
pesos    = list(catalogo.values())
prob     = [p / sum(pesos) for p in pesos]    



random.seed(42)


inicio_reforma = date(2026, 1, 11)
fim_reforma    = date(2026, 1, 17)

contagem = Counter()


for i in range(7):
    lambida = 5 * fator_dia[semana_d]
    vendas = rng.poisson(lam=lambida)
    if inicio_reforma <= dia <= fim_reforma:
        vendas = 0
    print(f"{dia} ({dia_da_semana[semana_d]} - {vendas})")
    for v in range(vendas):
        print(f" venda {v+1}")
        qtd = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05])[0]
        produtos_vendidos = Counter()
        for item in range(qtd):
            escolhido = rng.choice(produtos, p=prob)
            quantidade = random.choices([1, 2], weights=[0.9, 0.1])[0]
            
            produtos_vendidos[escolhido] += quantidade
            
            contagem[escolhido] += quantidade

        for produto in produtos_vendidos:
            print(f"  -  {produtos_vendidos[produto]} x {produto}")
        
            
    dia += um_dia
    semana_d = dia.weekday()

for produto in produtos_vendidos:
    print(f"{produto}: {produtos_vendidos[produto]} unidades vendidas")

total = sum(contagem.values())
soma_pesos = sum(pesos)
for produto, vezes in contagem.most_common():
    teórico = catalogo[produto] / soma_pesos
    print(f"{produto}: {vezes/total:.1%} (teórico: {teórico:.1%})")

