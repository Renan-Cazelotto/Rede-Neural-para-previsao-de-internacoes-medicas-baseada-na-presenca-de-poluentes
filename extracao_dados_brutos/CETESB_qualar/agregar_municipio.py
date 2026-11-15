#!/usr/bin/env python3
"""
agregar_municipio.py
--------------------
Lê os CSVs diários POR ESTAÇÃO gerados pelo processar_qualar.py e calcula, para
cada município, a média diária entre as estações.

Uso:
    python agregar_municipio.py [pasta_diarios] [pasta_saida]
Padrões: pasta_diarios = dados_diarios, pasta_saida = dados_municipio

Regras (configuráveis abaixo):
 * Em municípios com VÁRIAS estações, cada estação só entra na média de uma
   variável se tiver cobertura >= COBERTURA_MIN_POR_ANO em TODOS os anos de
   ANOS_SELECAO. Isso mantém a composição da média constante no tempo, para a
   série não ganhar "degraus" quando uma estação nova começa a medir.
   (Só se usam os anos de treino/validação; 2019 não participa da seleção.)
 * Em municípios com UMA estação, nenhuma estação é excluída (a cobertura
   desigual é tratada depois, no notebook).
 * O dia só recebe valor se pelo menos MIN_ESTACOES_DIA estações incluídas
   tiverem valor válido nesse dia.

Saídas:
  dados_municipio/diario_municipio_<Municipio>.csv  (data, variáveis, nest_<var>,
      n_<var>; n_<var> = 24 quando há valor e 0 quando não há, para o notebook do M2
      continuar aceitando o arquivo)
  dados_municipio/selecao_estacoes.csv  (cobertura por estação, variável e ano)
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MUNICIPIOS = {                         # município -> códigos CETESB das estações
    "Piracicaba": [113],
    "Sao_Paulo": [63, 64, 72, 73, 83, 84, 85, 90, 91, 94, 95, 96, 97, 98, 99,
                  236, 262, 266, 269, 270, 284, 293],
}
VARIAVEIS = ["mp10", "mp25", "no2", "o3", "temp", "ur"]
ANOS_SELECAO = range(2014, 2019)       # 2014–2018: o ano de teste (2019) fica fora da seleção
COBERTURA_MIN_POR_ANO = 0.6            # fração mínima de dias válidos, em cada ano
MIN_ESTACOES_DIA = 1


def carregar_estacoes(pasta):
    est = {}
    for arq in sorted(pasta.glob("diario_*.csv")):
        m = re.match(r"diario_(\d+)_", arq.name)
        if not m:
            continue
        d = pd.read_csv(arq, parse_dates=["data"]).set_index("data")
        est[int(m.group(1))] = d
    return est


def main():
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "dados_diarios")
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else "dados_municipio")
    saida.mkdir(parents=True, exist_ok=True)

    estacoes = carregar_estacoes(pasta)
    if not estacoes:
        sys.exit(f"Nenhum diario_*.csv encontrado em '{pasta}'. Rode antes o processar_qualar.py.")

    registros = []      # tabela de seleção
    for mun, codigos in MUNICIPIOS.items():
        presentes = [c for c in codigos if c in estacoes]
        faltam = [c for c in codigos if c not in estacoes]
        print(f"\n=== {mun}: {len(presentes)} de {len(codigos)} estações com arquivo diário ===")
        if faltam:
            print(f"   sem arquivo (não baixadas ou sem nenhum dado): {faltam}")
        if not presentes:
            continue
        varias = len(codigos) > 1

        # calendário comum
        ini = min(estacoes[c].index.min() for c in presentes)
        fim = max(estacoes[c].index.max() for c in presentes)
        cal = pd.date_range(ini, fim, freq="D", name="data")
        resultado = pd.DataFrame(index=cal)

        for v in VARIAVEIS:
            incluidas = []
            for c in presentes:
                d = estacoes[c]
                if v not in d.columns:
                    continue
                cob = {a: float(d[v].loc[d.index.year == a].notna().sum())
                       / pd.date_range(f"{a}-01-01", f"{a}-12-31").size for a in ANOS_SELECAO}
                passa = (not varias) or all(x >= COBERTURA_MIN_POR_ANO for x in cob.values())
                if (not varias) and sum(cob.values()) == 0:
                    passa = d[v].notna().any()
                registros.append({"municipio": mun, "estacao": c, "variavel": v,
                                  **{f"cob_{a}": round(x, 2) for a, x in cob.items()},
                                  "incluida": bool(passa)})
                if passa:
                    incluidas.append(c)
            if incluidas:
                larga = pd.concat([estacoes[c][v].reindex(cal).rename(c) for c in incluidas], axis=1)
                nest = larga.notna().sum(axis=1)
                media = larga.mean(axis=1, skipna=True).where(nest >= MIN_ESTACOES_DIA)
            else:
                nest = pd.Series(0, index=cal)
                media = pd.Series(np.nan, index=cal)
            resultado[v] = media
            resultado["nest_" + v] = nest.astype(int)
            print(f"   {v:5s}: {len(incluidas):2d} estação(ões) na média"
                  + (f" -> {incluidas}" if incluidas else "  (NENHUMA passou na cobertura mínima)"))

        for v in VARIAVEIS:
            resultado["n_" + v] = np.where(resultado[v].notna(), 24, 0)
        ordem = VARIAVEIS + ["nest_" + v for v in VARIAVEIS] + ["n_" + v for v in VARIAVEIS]
        resultado = resultado[ordem]

        # resumo de dias sem valor por ano (2019 incluído só para informar)
        sem_valor = resultado[VARIAVEIS].isna().groupby(resultado.index.year).sum()
        print("   dias sem valor por ano:")
        print("   " + sem_valor.to_string().replace("\n", "\n   "))

        destino = saida / f"diario_municipio_{mun}.csv"
        resultado.reset_index().to_csv(destino, index=False, date_format="%Y-%m-%d")
        print(f"-> salvo {destino}")

    pd.DataFrame(registros).to_csv(saida / "selecao_estacoes.csv", index=False)
    print(f"\nSeleção de estações: {saida / 'selecao_estacoes.csv'}")


if __name__ == "__main__":
    main()
