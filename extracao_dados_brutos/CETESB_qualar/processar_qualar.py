#!/usr/bin/env python3
"""
processar_qualar.py
-------------------
Lê os CSVs horários exportados do QUALAR (CETESB), junta todos os arquivos
de cada estação e gera um CSV com valores DIÁRIOS por estação.

Uso:
    python processar_qualar.py [pasta_entrada] [pasta_saida]

Padrões: pasta_entrada = dados_brutos, pasta_saida = dados_diarios

Dependências: pandas, numpy   (pip install pandas numpy)

Regras do valor diário (configuráveis no topo do arquivo):
  MP10, MP2.5 ........ média das horas do dia
  NO2 ................ máxima horária do dia
  O3 ................. máxima da média móvel de 8 h (mín. 6 horas válidas na janela)
  TEMP ............... máxima horária do dia
  UR ................. mínima horária do dia
Um dia só recebe valor se tiver pelo menos MIN_HORAS_VALIDAS leituras válidas
(para o O3: pelo menos MIN_HORAS_VALIDAS médias de 8 h válidas). Caso contrário
o dia fica vazio (NaN), e nada é interpolado aqui.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MIN_HORAS_VALIDAS = 18      # exigência de horas válidas por dia (18 de 24 = 75%)
MIN_HORAS_JANELA_8H = 6     # horas válidas exigidas em cada janela de 8 h do O3

# parâmetro -> (nome da coluna na saída, função de agregação diária)
REGRAS = {
    "MP10": ("mp10", "media"),
    "MP2.5": ("mp25", "media"),
    "NO2": ("no2", "maximo"),
    "O3": ("o3", "max8h"),
    "TEMP": ("temp", "maximo"),
    "UR": ("ur", "minimo"),
}


def _nome_coluna(codigo):
    if codigo in REGRAS:
        return REGRAS[codigo][0]
    return re.sub(r"[^a-z0-9]+", "", codigo.lower())


def ler_exportacao(caminho):
    """Lê um CSV exportado do QUALAR. Devolve (codigo, nome, df_horario)."""
    with open(caminho, encoding="latin-1") as f:
        linhas = f.read().splitlines()

    codigo, nome = None, None
    idx_cab = None
    for i, linha in enumerate(linhas[:30]):
        campos = linha.split(";")
        rotulo = campos[0].lower()
        if "digo da esta" in rotulo and len(campos) > 1:
            codigo = campos[1].strip()
        elif "nome da esta" in rotulo and len(campos) > 1:
            nome = campos[1].strip()
        elif campos[0].strip().lower() == "data" and len(campos) > 1 \
                and campos[1].strip().lower() == "hora":
            idx_cab = i
            break
    if idx_cab is None:
        raise ValueError("cabeçalho 'Data;Hora' não encontrado")

    # a linha seguinte traz "MP10(Partículas Inaláveis) - µg/m3" etc.
    nomes_param = linhas[idx_cab + 1].split(";")[2:]
    codigos_param = []
    for n in nomes_param:
        n = n.strip()
        if not n:
            continue
        codigos_param.append(n.split("(")[0].strip().upper())

    dados = []
    for linha in linhas[idx_cab + 2:]:
        campos = linha.split(";")
        if not re.match(r"\d\d/\d\d/\d{4}$", campos[0].strip()):
            continue
        dados.append(campos[:2 + len(codigos_param)]
                     + [""] * (2 + len(codigos_param) - len(campos)))

    df = pd.DataFrame(dados, columns=["data", "hora"] + codigos_param)
    for c in codigos_param:
        df[c] = pd.to_numeric(df[c].str.strip().str.replace(",", ".", regex=False),
                              errors="coerce")
    # carimbo no FIM da hora: 01:00 ... 24:00 (24:00 = meia-noite do dia seguinte)
    data = pd.to_datetime(df["data"], format="%d/%m/%Y")
    h = pd.to_numeric(df["hora"].str.split(":").str[0], errors="coerce")
    df["ts"] = data + pd.to_timedelta(h, unit="h")
    df = df.drop(columns=["data", "hora"]).dropna(subset=["ts"])
    return codigo, nome, df


def agregar_diario(horario):
    """horario: DataFrame com índice 'ts' (fim da hora) e colunas por parâmetro."""
    idx = pd.date_range(horario.index.min(), horario.index.max(), freq="h")
    h = horario.reindex(idx)
    # o dia de uma leitura é a data do INÍCIO da hora (24:00 pertence ao mesmo dia)
    dia = (h.index - pd.Timedelta(hours=1)).normalize()

    saida = {}
    for p in h.columns:
        nome_col, regra = REGRAS.get(p, (_nome_coluna(p), "media"))
        s = h[p]
        if regra == "max8h":
            mm = s.rolling(8, min_periods=MIN_HORAS_JANELA_8H).mean()
            base = mm
        else:
            base = s
        grupo = base.groupby(dia)
        n = grupo.count()
        if regra in ("media",):
            v = grupo.mean()
        elif regra in ("maximo", "max8h"):
            v = grupo.max()
        elif regra == "minimo":
            v = grupo.min()
        v = v.where(n >= MIN_HORAS_VALIDAS)
        saida[nome_col] = v
        saida["n_" + nome_col] = n
    diario = pd.DataFrame(saida)
    ordem = [v[0] for v in REGRAS.values()]
    valores = [c for c in ordem if c in diario.columns] + \
              [c for c in diario.columns if not c.startswith("n_") and c not in ordem]
    diario = diario[valores + ["n_" + c for c in valores]]
    diario.index.name = "data"
    # calendário completo (dias sem nenhuma leitura entram como NaN / 0)
    cal = pd.date_range(diario.index.min(), diario.index.max(), freq="D", name="data")
    diario = diario.reindex(cal)
    for c in diario.columns:
        if c.startswith("n_"):
            diario[c] = diario[c].fillna(0).astype(int)
    return diario


def relatorio(codigo, nome, diario):
    cols = [c for c in diario.columns if not c.startswith("n_")]
    print(f"\n=== Estação {codigo} - {nome}: {diario.index.min().date()} a "
          f"{diario.index.max().date()} ({len(diario)} dias) ===")
    linhas = []
    for c in cols:
        por_ano = diario[c].isna().groupby(diario.index.year).agg(["sum", "count"])
        for ano, r in por_ano.iterrows():
            linhas.append({"parametro": c, "ano": ano, "dias": int(r["count"]),
                           "dias_sem_valor": int(r["sum"]),
                           "pct_sem_valor": round(100 * r["sum"] / r["count"], 1)})
    rel = pd.DataFrame(linhas)
    if not rel.empty:
        print(rel.pivot(index="ano", columns="parametro",
                        values="dias_sem_valor").to_string())
        print("(valores = nº de dias sem valor diário válido em cada ano)")
    return rel


def main():
    entrada = Path(sys.argv[1] if len(sys.argv) > 1 else "dados_brutos")
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else "dados_diarios")
    saida.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(entrada.glob("*.csv"))
    if not arquivos:
        sys.exit(f"Nenhum .csv encontrado em '{entrada}'.")

    por_estacao = {}   # codigo -> {"nome": ..., "tabelas": [df,...]}
    for a in arquivos:
        try:
            cod, nome, df = ler_exportacao(a)
        except Exception as e:
            print(f"[ignorado] {a.name}: {e}")
            continue
        if df.empty:
            print(f"[vazio] {a.name}: sem linhas de dados")
            continue
        est = por_estacao.setdefault(cod, {"nome": nome, "tabelas": []})
        est["tabelas"].append(df.set_index("ts"))
        print(f"[ok] {a.name}: estação {cod} ({nome}), "
              f"{(df['ts'].min() - pd.Timedelta(hours=1)):%d/%m/%Y} a "
              f"{(df['ts'].max() - pd.Timedelta(hours=1)):%d/%m/%Y}, "
              f"parâmetros: {', '.join(c for c in df.columns if c != 'ts')}")

    todos_rel = []
    for cod, est in por_estacao.items():
        # junta arquivos da mesma estação; se houver sobreposição, mantém o 1º valor
        # não nulo de cada hora/parâmetro
        h = est["tabelas"][0]
        for t in est["tabelas"][1:]:
            comuns_i = h.index.intersection(t.index)
            comuns_c = h.columns.intersection(t.columns)
            if len(comuns_i) and len(comuns_c):
                a, b = h.loc[comuns_i, comuns_c], t.loc[comuns_i, comuns_c]
                conflitos = int(((a != b) & a.notna() & b.notna()).to_numpy().sum())
                if conflitos:
                    print(f"[aviso] estação {cod}: {conflitos} leituras coincidem em "
                          "hora e parâmetro mas têm valores diferentes entre arquivos; "
                          "vale o do arquivo lido primeiro (ordem alfabética).")
            h = h.combine_first(t)
        h = h.sort_index()
        diario = agregar_diario(h)
        nome_arq = re.sub(r"[^A-Za-z0-9]+", "_", est["nome"] or "estacao").strip("_")
        destino = saida / f"diario_{cod}_{nome_arq}.csv"
        diario.reset_index().to_csv(destino, index=False, date_format="%Y-%m-%d")
        print(f"-> salvo {destino}")
        rel = relatorio(cod, est["nome"], diario)
        rel.insert(0, "estacao", f"{cod} {est['nome']}")
        todos_rel.append(rel)

    if todos_rel:
        pd.concat(todos_rel).to_csv(saida / "relatorio_faltantes.csv", index=False)
        print(f"\nRelatório de dias faltantes: {saida / 'relatorio_faltantes.csv'}")


if __name__ == "__main__":
    main()
