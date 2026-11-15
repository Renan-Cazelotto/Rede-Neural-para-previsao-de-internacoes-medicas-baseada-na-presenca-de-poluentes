# Previsão de internações respiratórias com dados de qualidade do ar

Trabalho 2 (projeto final) de Redes Neurais e Aprendizado Profundo (EMA9824), 2026/2.
Grupo: Lucas Silveira, Nívea Batoni e Renan Cazelotto.

**Pergunta:** incluir poluentes do ar (MP10, MP2,5, NO₂, O₃) reduz o erro de previsão das
internações diárias por doenças respiratórias, em relação a um baseline sazonal e à mesma
rede sem poluentes? Municípios: Piracicaba e São Paulo (capital). Período: 2014–2019
(treino 2014–2017, validação 2018, teste 2019; 2020–2021 ficam fora por causa da COVID-19).

## Estrutura do repositório

```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── BASELINE_problemas_respiratorios.ipynb   # baselines (média sazonal e Poisson), figura e tabelas
├── dados_t2.zip                             # os 4 CSVs agregados com que o notebook roda
└── extracao_dados_brutos/
    ├── DATASUS/                             # internações (SIH/SUS)
    │   ├── convert.r                        # .dbc -> .csv
    │   ├── process_datasus.py               # CSVs -> contagem diária por município
    │   ├── diagnostico.py                   # checagens (não grava nada)
    │   └── data/                            # NÃO vai para o git
    │       ├── raw/                         # .dbc baixados e .csv convertidos
    │       └── processed/                   # internacoes_respiratorias-<Município>.csv
    └── CETESB_qualar/                       # poluentes e meteorologia (CETESB)
        ├── baixar_qualar.py                 # login no QUALAR e download horário
        ├── processar_qualar.py              # valores diários por estação
        ├── agregar_municipio.py             # média entre as estações de cada município
        ├── dados_diarios/                   # saída por estação (pequena; está no git)
        ├── dados_municipio/                 # saída por município (pequena; está no git)
        ├── dados_brutos/                    # NÃO vai para o git (CSVs horários)
        └── cache_qualar/                    # NÃO vai para o git (cache do download)
```

Ficam fora do git (`.gitignore`): `extracao_dados_brutos/DATASUS/data/`,
`extracao_dados_brutos/CETESB_qualar/dados_brutos/`,
`extracao_dados_brutos/CETESB_qualar/cache_qualar/` e qualquer arquivo com usuário ou senha.

## Ambiente

- Python 3 com as bibliotecas de `requirements.txt` (`python -m pip install -r requirements.txt`).
- R, só para converter os arquivos do SIH (o `convert.r` instala o pacote `read.dbc` sozinho).
- O notebook foi executado no Google Colab (CPU, sem GPU), com Python 3.13, numpy 2.4,
  pandas 2.2, scikit-learn 1.6 e matplotlib 3.10. Os scripts do QUALAR foram testados com
  pandas 3.0 e numpy 2.5.
- **Semente:** 42 (`SEMENTE` na primeira célula do notebook). Os modelos de Poisson começam
  de pesos iniciais fixos, então não dependem de semente.

## Reproduzir a figura principal

> **TODO:** quando o GRU (M3) estiver pronto, trocar este comando pelo da figura principal
> do artigo. Hoje a figura do notebook é `fig_m2_curvas_poisson.png`.

**Caminho rápido (a partir dos dados já agregados, sem os brutos):**

1. Use o `dados_t2.zip` da raiz do repositório.
2. Abra `BASELINE_problemas_respiratorios.ipynb` no Colab, envie o zip, ajuste `CAMINHO_ZIP`
   e use *Ambiente de execução → Executar tudo* (cerca de 8 s em CPU). O notebook gera
   `fig_m2_curvas_poisson.png` e `resultados_m2.csv`.

O notebook bloqueia o ano de teste (2019): `ULTIMO_DIA_USAVEL = '2018-12-31'`. Só o M3 deve
trocar isso, e uma única vez.

**Caminho completo (a partir das fontes):** seguir as duas seções de dados abaixo, na ordem.

## Dados

### 1. Internações (SIH/SUS, DATASUS): coleta manual

**Por que a coleta é manual e os dados brutos não estão no repositório.** Precisávamos de
contagens **diárias** de internações. Na interface atual do portal do DATASUS, em nossa consulta em
05/11, só encontramos o SIH/SUS agregado **por mês**, o que não serve para
prever dia a dia. A data diária de internação só existe nos microdados (AIH Reduzida), que
obtivemos em um servidor mais antigo do DATASUS (FTP). Esse servidor é limitado: não tem busca
nem filtros por município ou data, só um arquivo por estado e mês (o de São Paulo traz os hospitais
do estado inteiro, mais de 15 milhões de linhas ao todo, cerca de 3 GB em 78 arquivos), e o formato
é próprio, o `.dbc` (arquivo comprimido do DATASUS), que não abre em ferramentas comuns e precisou
ser convertido para CSV em R. Por isso o download foi feito à mão, e não por script.

Os arquivos brutos são grandes demais para um repositório (o enunciado pede que não haja arquivos
grandes) e **não estão aqui**. Em vez deles, o repositório inclui:

- os scripts de conversão e agregação (`extracao_dados_brutos/DATASUS/`), que partem dos arquivos brutos;
- o passo a passo abaixo, com o endereço do servidor e o nome dos arquivos;
- as contagens diárias já agregadas (`dados_t2.zip`, algumas centenas de KB), com as quais o
  notebook roda sem precisar dos brutos.

Passo a passo da coleta (todos os comandos dentro de `extracao_dados_brutos/DATASUS/`):

1. Baixe do servidor FTP do DATASUS (`ftp://ftp.datasus.gov.br`) os arquivos mensais de AIH
   Reduzida de São Paulo, de janeiro de 2014 a junho de 2020. Os nomes têm o formato
   `RDSP<AA><MM>.dbc` (por exemplo, `RDSP1401.dbc` a `RDSP2006.dbc`, 78 arquivos).
   Os de 2020 servem só para completar o fim de 2019, porque a data de internação
   pode ser anterior à competência em até 6 meses.
2. Coloque os `.dbc` em `data/raw/`.
3. Converta para CSV (o `convert.r` lê e grava em `data/raw/`):
   ```text
   Rscript convert.r
   ```
4. Gere a contagem diária:
   ```text
   python process_datasus.py
   ```
   O script filtra o diagnóstico principal no capítulo J da CID-10 (`^J\d{2}`), o município
   de residência (`MUNIC_RES`) e agrupa pela data de internação, mantendo os dias sem
   internação como zero. Para cada município, ajuste no começo do arquivo o dicionário
   `MUNICIPALITIES` e o nome de `OUTPUT_FILE`:

   | Município | Código no SIH | Arquivo de saída (em `data/processed/`) |
   |---|---|---|
   | Piracicaba | `353870` | `internacoes_respiratorias-Piracicaba.csv` |
   | São Paulo | `355030` | `internacoes_respiratorias-Sao_Paulo.csv` |

5. (Opcional) `python diagnostico.py` mostra duplicidades de `N_AIH`, a defasagem entre
   competência e data de internação e os registros fora de 2014–2019. Nos nossos dados:
   nenhum `N_AIH` duplicado, todas as AIH com `IDENT = 1` e defasagem máxima de 6 meses.

### 2. Poluentes e meteorologia (QUALAR, CETESB)

O QUALAR exige um **cadastro gratuito** (https://qualar.cetesb.sp.gov.br). Cada pessoa usa o
próprio usuário. Defina as variáveis de ambiente `QUALAR_USER` e `QUALAR_PASS` (ou digite
quando o script perguntar);

Dentro de `extracao_dados_brutos/CETESB_qualar/`, nesta ordem:

```text
python baixar_qualar.py            # dados horários -> dados_brutos/ (com cache em cache_qualar/)
python processar_qualar.py         # valores diários por estação -> dados_diarios/
python agregar_municipio.py        # média por município -> dados_municipio/
```

- `baixar_qualar.py` baixa Piracicaba (estação 113) e as 22 estações de São Paulo listadas em
  `MUNICIPIOS`, para 2014–2019 e os parâmetros MP10, MP2,5, NO₂, O₃, temperatura e umidade.
  Se parar no meio, é só rodar de novo: o que já foi baixado fica no cache.
- `processar_qualar.py` calcula o valor diário com as regras do portal: média para MP10 e
  MP2,5, máxima horária para NO₂, máxima da média móvel de 8 h para O₃, máxima para
  temperatura e mínima para umidade. O dia só vale com pelo menos 18 horas válidas. Gera
  também `relatorio_faltantes.csv`.
- `agregar_municipio.py` calcula a média diária entre as estações de cada município. Em São
  Paulo, só entram as estações com pelo menos 60% de dias válidos em cada ano de 2014 a 2018
  (o ano de teste não participa da seleção). O resultado da seleção fica em
  `dados_municipio/selecao_estacoes.csv`.

### 3. Juntar os arquivos para o notebook

O notebook lê o `dados_t2.zip`, que tem quatro arquivos (dentro da pasta `dados_t2/`):

- `internacoes_respiratorias-Piracicaba.csv` e `internacoes_respiratorias-Sao_Paulo.csv`
  (de `extracao_dados_brutos/DATASUS/data/processed/`);
- `diario_municipio_Piracicaba.csv` e `diario_municipio_Sao_Paulo.csv`
  (de `extracao_dados_brutos/CETESB_qualar/dados_municipio/`).

O `dados_t2.zip` **está no repositório**. São arquivos pequenos e agregados (contagens diárias
e médias por município), sem dados individuais, gerados pelos scripts acima. Quem não tem os
brutos pode rodar o notebook só com ele; quem quiser refazer o caminho completo segue as seções 1 e 2.

## Fontes e licenças

| Fonte | Endereço | Acesso em | O que a fonte declara |
|---|---|---|---|
| SIH/SUS (DATASUS) | ftp.datasus.gov.br e datasus.saude.gov.br | 13/11/2026 | Licença explícita não identificada. Dados públicos anonimizados, sob a política de dados abertos do Poder Executivo federal (Decreto 8.777, de 11/05/2016): licença aberta, com citação da fonte. |
| QUALAR (CETESB) | cetesb.sp.gov.br/ar/qualar | 13/11/2026 | Catálogo de dados abertos da CETESB: divulgação pública, sem restrição de uso informando a fonte. Sem licença nomeada. |

Os dados brutos não estão no repositório. Do SIH usamos apenas contagens diárias por
município, sem informação individual dos pacientes.

## Limitações conhecidas dos dados

- Os arquivos `RDSP` trazem só internações em hospitais do estado de São Paulo; moradores que
  se internaram em outro estado não entram na contagem.
- Em Piracicaba há uma única estação, e temperatura e umidade ficaram sem medição válida em
  cerca de 66% e 80% dos dias de validação (2018); foram preenchidas com o último valor ou
  com a média mensal do treino.
- Em São Paulo, a média de cada variável usa entre 3 estações (temperatura e umidade) e 10
  (MP10 e O₃).
- Piracicaba (cerca de 5 internações por dia) e São Paulo (cerca de 150) têm escalas muito
  diferentes: compare os modelos dentro de cada cidade, ou use o MAE relativo.

