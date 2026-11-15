#!/usr/bin/env python3
"""
baixar_qualar.py
----------------
Faz login no QUALAR (CETESB) e baixa, de forma automática, os dados HORÁRIOS
das estações escolhidas (Piracicaba e as estações do município de São Paulo).
Grava um CSV por estação na pasta dados_brutos, no mesmo formato que o
processar_qualar.py lê. Depois é só rodar, nesta ordem:

    python baixar_qualar.py
    python processar_qualar.py          # valores diários, por estação
    python agregar_municipio.py         # média entre as estações de cada município

Dependências: requests, pandas, numpy   (python -m pip install requests pandas numpy)

Credenciais: defina as variáveis de ambiente QUALAR_USER e QUALAR_PASS, ou
digite quando o script perguntar (a senha não aparece na tela e não é salva).

O script segue o mesmo caminho do pacote qualR (rOpenSci, v0.9.7): login em
/qualar/autenticador e consulta em /qualar/exportaDados.do?method=pesquisar,
uma estação, um parâmetro e um ano por vez. Cada consulta fica guardada em
cache_qualar/, então, se a execução for interrompida, é só rodar de novo.
"""
import getpass
import os
import re
import sys
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

# ----------------------------- CONFIGURAÇÃO ---------------------------------
MUNICIPIOS = {                                          # município -> {código CETESB: nome}
    "Piracicaba": {113: "Piracicaba"},
    "Sao_Paulo": {63: "Santana", 64: "Santo Amaro", 72: "Parque D.Pedro II",
                  73: "Congonhas", 83: "Ibirapuera", 85: "Mooca", 90: "Cambuci",
                  91: "Cerqueira César", 94: "Centro", 95: "Cid.Universitária-USP-Ipen",
                  84: "Lapa", 96: "N.Senhora do Ó", 97: "Itaquera", 98: "Grajaú-Parelheiros",
                  99: "Pinheiros", 236: "S.Miguel Paulista", 262: "Interlagos",
                  266: "Itaim Paulista", 269: "Capão Redondo",
                  270: "Marg.Tietê-Pte Remédios", 284: "Pico do Jaraguá", 293: "Perus"},
}
ESTACOES = {cod: nome for est in MUNICIPIOS.values() for cod, nome in est.items()}
ANOS = list(range(2014, 2020))                          # 2014 a 2019
PARAMETROS = {                                          # nome -> código QUALAR
    "MP10": (12, "µg/m3"),
    "MP2.5": (57, "µg/m3"),
    "NO2": (15, "µg/m3"),
    "O3": (63, "µg/m3"),
    "TEMP": (25, "°C"),
    "UR": (28, "%"),
}
SOMENTE_VALIDOS = True       # como o qualR: descarta linhas cuja coluna de teste != "Sim"
PAUSA_S = 1.0                # pausa entre consultas, para não sobrecarregar o servidor
TENTATIVAS = 3
VERIFICAR_A_CADA = 40        # consultas ao vivo entre verificações de que a sessão continua válida
PASTA_SAIDA = Path("dados_brutos")
PASTA_CACHE = Path("cache_qualar")
# -----------------------------------------------------------------------------

URL_LOGIN = "https://qualar.cetesb.sp.gov.br/qualar/autenticador"
URL_CONSULTA = "https://qualar.cetesb.sp.gov.br/qualar/exportaDados.do?method=pesquisar"
N_COLUNAS = 19   # colunas da tabela HTML de resultados (ordem usada pelo qualR)
I_DIA, I_HORA, I_VALOR, I_TESTE = 4, 5, 10, 12


class _Tabelas(HTMLParser):
    """Extrai todas as tabelas HTML (inclusive aninhadas) como listas de linhas."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha, self.tabelas = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.pilha.append({"rows": [], "row": None, "cell": None})
        elif self.pilha:
            t = self.pilha[-1]
            if tag == "tr":
                t["row"] = []
            elif tag in ("td", "th") and t["row"] is not None:
                t["cell"] = []

    def handle_data(self, data):
        if self.pilha and self.pilha[-1]["cell"] is not None:
            self.pilha[-1]["cell"].append(data)

    def handle_endtag(self, tag):
        if not self.pilha:
            return
        t = self.pilha[-1]
        if tag in ("td", "th") and t["cell"] is not None and t["row"] is not None:
            t["row"].append(re.sub(r"\s+", " ", "".join(t["cell"])).strip())
            t["cell"] = None
        elif tag == "tr" and t["row"] is not None:
            t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "table":
            self.tabelas.append(self.pilha.pop()["rows"])


def extrair_horario(html):
    """Devolve DataFrame (ts, valor) com o carimbo no FIM da hora (01:00 ... 24:00)."""
    p = _Tabelas()
    p.feed(html)
    melhor = []
    for linhas in p.tabelas:
        dados = [l for l in linhas
                 if len(l) >= N_COLUNAS and re.match(r"\d\d/\d\d/\d{4}$", l[I_DIA])]
        if len(dados) > len(melhor):
            melhor = dados
    if not melhor:
        return pd.DataFrame(columns=["ts", "valor"])
    df = pd.DataFrame({"dia": [l[I_DIA] for l in melhor],
                       "hora": [l[I_HORA] for l in melhor],
                       "valor": [l[I_VALOR] for l in melhor],
                       "teste": [l[I_TESTE] for l in melhor]})
    if SOMENTE_VALIDOS:
        df = df[df["teste"].str.strip().str.lower() == "sim"]
    # mesmo tratamento do qualR: tira o ponto de milhar e troca vírgula por ponto
    df["valor"] = pd.to_numeric(
        df["valor"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce")
    horas = pd.to_numeric(df["hora"].str.split(":").str[0], errors="coerce")
    df["ts"] = pd.to_datetime(df["dia"], format="%d/%m/%Y") + pd.to_timedelta(horas, unit="h")
    df = df.dropna(subset=["ts"]).drop_duplicates("ts", keep="first")
    return df[["ts", "valor"]]


def consultar(sessao, est, cod_par, ano):
    corpo = {"irede": "A",
             "dataInicialStr": f"01/01/{ano}",
             "dataFinalStr": f"31/12/{ano}",
             "iTipoDado": "P",
             "estacaoVO.nestcaMonto": est,
             "parametroVO.nparmt": cod_par}
    ultimo = None
    for t in range(1, TENTATIVAS + 1):
        try:
            r = sessao.post(URL_CONSULTA, data=corpo, timeout=180)
            r.raise_for_status()
            return r.content.decode("utf-8", errors="replace")
        except requests.RequestException as e:
            ultimo = e
            print(f"   tentativa {t}/{TENTATIVAS} falhou: {e}")
            time.sleep(5 * t)
    raise SystemExit(f"Não consegui consultar o QUALAR: {ultimo}")


def escrever_arquivo(est, nome, tabela):
    """Grava no mesmo layout do arquivo exportado pelo portal."""
    cods = list(PARAMETROS)
    linhas = ["Tipo de Monitoramento:;CETESB", "Tipo de Rede:;Automática",
              "Tipo de Dado:;Primários (baixado por baixar_qualar.py)",
              f"Código da estação:;{est}", f"Nome da estação:;{nome}", "",
              "Data;Hora;" + ";".join(["Média Horária"] * len(cods)),
              ";;" + ";".join(f"{c}(qualR) - {PARAMETROS[c][1]}" for c in cods)]
    for ts, linha in tabela.iterrows():
        if ts.hour == 0:                       # 24:00 pertence ao dia anterior
            d, h = (ts - pd.Timedelta(days=1)), "24:00"
        else:
            d, h = ts, f"{ts.hour:02d}:00"
        vals = ["" if pd.isna(linha.get(c)) else f"{linha[c]:g}" for c in cods]
        linhas.append(f"{d:%d/%m/%Y};{h};" + ";".join(vals))
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    seguro = re.sub(r"[^A-Za-z0-9]+", "_", unicodedata.normalize("NFKD", nome)
                    .encode("ascii", "ignore").decode()).strip("_")
    destino = PASTA_SAIDA / f"qualar_{est}_{seguro}_{ANOS[0]}_{ANOS[-1]}.csv"
    destino.write_text("\n".join(linhas) + "\n", encoding="latin-1", errors="replace")
    return destino


def verificar_login(sessao, sair=True):
    """Consulta conhecida (Piracicaba, MP10, 2014, que tem dados). Se vier vazia, a sessão
    não está autenticada (usuário/senha errados, sessão expirada ou portal mudou)."""
    html = consultar(sessao, 113, 12, 2014)
    if not extrair_horario(html).empty:
        return True
    Path("debug_resposta.html").write_text(html, encoding="utf-8")
    if sair:
        sys.exit("\nA consulta de verificação (Piracicaba, MP10, 2014) veio vazia. Confira "
                 "usuário e senha. Se estiverem certos, o portal pode ter mudado; a resposta "
                 "do servidor foi salva em debug_resposta.html.")
    return False


def main():
    usuario = os.environ.get("QUALAR_USER") or input("Usuário do QUALAR: ").strip()
    senha = os.environ.get("QUALAR_PASS") or getpass.getpass("Senha do QUALAR: ")

    sessao = requests.Session()
    sessao.post(URL_LOGIN, data={"cetesb_login": usuario, "cetesb_password": senha},
                timeout=60)
    verificar_login(sessao)
    print("Login verificado.")
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)

    consultas_vivas = 0
    vazios_pendentes = []      # resultados vazios só vão para o cache depois de a sessão ser reconfirmada

    def confirmar_sessao():
        nonlocal vazios_pendentes
        if not verificar_login(sessao, sair=False):
            sys.exit("\nA sessão deixou de ser válida no meio do download (os resultados vazios "
                     "recentes foram descartados). Rodem de novo: o que já foi baixado está no cache.")
        for caminho in vazios_pendentes:
            pd.DataFrame(columns=["ts", "valor"]).to_csv(caminho, index=False)
        vazios_pendentes = []

    for est, nome in ESTACOES.items():
        print(f"\n=== Estação {est} - {nome} ===")
        colunas = {}
        for par, (cod_par, _) in PARAMETROS.items():
            partes, contagem = [], []
            for ano in ANOS:
                cache = PASTA_CACHE / f"{est}_{par}_{ano}.csv"
                if cache.exists():
                    df = pd.read_csv(cache, parse_dates=["ts"])
                else:
                    html = consultar(sessao, est, cod_par, ano)
                    df = extrair_horario(html)
                    if df.empty:
                        vazios_pendentes.append(cache)
                    else:
                        df.to_csv(cache, index=False)
                    consultas_vivas += 1
                    if consultas_vivas % VERIFICAR_A_CADA == 0:
                        confirmar_sessao()
                    time.sleep(PAUSA_S)
                partes.append(df)
                contagem.append(f"{ano}:{int(df['valor'].notna().sum())}")
            print(f"   {par:6s} horas válidas por ano -> " + "  ".join(contagem))
            serie = pd.concat(partes) if partes else pd.DataFrame(columns=["ts", "valor"])
            if not serie.empty:
                colunas[par] = serie.drop_duplicates("ts").set_index("ts")["valor"]
        if not colunas:
            print("   nenhum dado para esta estação; arquivo não gerado.")
            continue
        tabela = pd.DataFrame(colunas).sort_index()
        destino = escrever_arquivo(est, nome, tabela)
        print(f"-> salvo {destino}")

    confirmar_sessao()
    print("\nPronto. Agora rode: python processar_qualar.py  e depois  python agregar_municipio.py")


if __name__ == "__main__":
    main()
