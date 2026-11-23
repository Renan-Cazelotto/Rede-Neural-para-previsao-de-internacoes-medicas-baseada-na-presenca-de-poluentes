# Previsão de internações respiratórias com dados de qualidade do ar

Trabalho 2 (projeto final) de Redes Neurais e Aprendizado Profundo (EMA9824), 2026/2.
Grupo: Lucas Silveira, Nívea Batoni e Renan Cazelotto.

**Pergunta:** incluir poluentes do ar (MP10, MP2,5, NO₂, O₃) reduz o erro de previsão das
internações diárias por doenças respiratórias, em relação a um baseline sazonal e à mesma
rede sem poluentes? Municípios: Piracicaba e São Paulo (capital). Período: 2014–2019
(treino 2014–2017, validação 2018, teste 2019; 2020–2021 ficam fora por causa da COVID-19).

## Resumo dos resultados

Teste (2019), horizonte de 1 dia, MAE em internações por dia (GRU: média ± desvio-padrão
entre 3 sementes; média sazonal e Poisson são determinísticos):

| Modelo | Piracicaba | São Paulo |
|---|---|---|
| Média sazonal | 2,06 | 19,61 |
| Poisson sem poluentes | 1,90 | 14,68 |
| Poisson com poluentes | 1,88 | 14,73 |
| GRU sem poluentes | 1,94 ± 0,03 | 14,81 ± 0,35 |
| GRU com poluentes | 1,93 ± 0,02 | 14,80 ± 0,18 |

Pelo critério de empate da proposta (aplicado no horizonte de 1 dia):

- **os poluentes não melhoram a previsão:** em nenhum município a diferença entre o GRU sem e
  com poluentes passou de 2 desvios-padrão entre sementes;
- **a rede não se justifica:** o GRU sem poluentes não superou o melhor Poisson em nenhum
  município.

Os horizontes de 7 e 14 dias são descritivos e estão nas tabelas do notebook final (seção 6) e
em `resultados_finais_agregados.csv`. Os números vêm da execução no Google Colab (CPU). Uma
segunda execução, fora do Colab (CPU, pandas 2.2, torch 2.15), reproduziu as 12 médias e
desvios do GRU com duas casas decimais e as mesmas decisões do critério; ainda assim, o GRU
pode variar um pouco entre máquinas e versões de biblioteca.

## Estrutura do repositório

```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── FINAL_problemas_respiratorios.ipynb      # projeto final: baselines + GRU, teste, critério de empate, figuras
├── BASELINE_problemas_respiratorios.ipynb   # M2: só os baselines (média sazonal e Poisson), figura e tabelas
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
`extracao_dados_brutos/CETESB_qualar/cache_qualar/`, qualquer arquivo com usuário ou senha e
as pastas que os notebooks criam ao rodar (`dados_extraidos/`, `checkpoints_gru/` e
`checkpoints_exploracao/`).

## Ambiente

- Python 3 com as bibliotecas de `requirements.txt` (`python -m pip install -r requirements.txt`).
  O `torch` só é usado pelo notebook final, e a versão para CPU basta.
- R, só para converter os arquivos do SIH (o `convert.r` instala o pacote `read.dbc` sozinho).
- Os notebooks foram executados no Google Colab (CPU com 2 vCPUs, sem GPU), com Python 3.13,
  numpy 2.4, pandas 2.2, scipy 1.16, scikit-learn 1.6, matplotlib 3.10 e torch 2.14 (CPU). Os
  scripts do QUALAR foram testados com pandas 3.0 e numpy 2.5.
- **Sementes:** a global é 42 (`SEMENTE` na primeira célula do notebook final) e as do GRU são
  42, 43 e 44 (`SEMENTES_GRU`). A média sazonal e os modelos de Poisson não dependem de
  semente: o Poisson começa de pesos iniciais fixos.
- **Número de execuções:** 36 treinos de GRU (2 municípios × 3 horizontes × 2 versões ×
  3 sementes). Os baselines são determinísticos e rodam uma vez. O notebook imprime o número de
  treinos, o ambiente e as versões das bibliotecas.

## Reproduzir a figura principal

A figura principal do artigo é `fig_final_mae_teste.png` (MAE de teste por município, horizonte e
modelo, com barras de erro de ±1 desvio-padrão entre sementes no GRU). Ela é gerada pelo
`FINAL_problemas_respiratorios.ipynb`.

**Caminho rápido (a partir dos dados já agregados, sem os brutos):**

1. Abra `FINAL_problemas_respiratorios.ipynb` no Google Colab (*Arquivo → Abrir notebook →
   GitHub*, ou envie o arquivo).
2. Use *Ambiente de execução → Executar tudo*. Não é preciso ajustar nada: se o `dados_t2.zip`
   não estiver no ambiente, a célula de dados o baixa da raiz deste repositório. Para usar uma
   cópia sua (no Drive ou enviada ao Colab), ajuste `CAMINHO_ZIP`; o Drive é montado sozinho
   quando o caminho está nele. Como último recurso, o notebook pede o upload do zip.
3. Aguarde cerca de 7 minutos (6,8 minutos medidos no Colab, em CPU): a maior parte é o treino
   dos 36 GRUs.

Fora do Colab, a partir da raiz do repositório (o notebook usa o `dados_t2.zip` da raiz):

```text
python -m pip install -r requirements.txt
jupyter nbconvert --to notebook --execute FINAL_problemas_respiratorios.ipynb
```

**O que o notebook final faz:** lê os dados, mede os baselines (média sazonal e Poisson sem e
com poluentes), treina o GRU (janela de 28 dias) sem e com poluentes, mostra a validação (2018)
e só então avalia tudo no teste (2019), uma única vez, com os modelos congelados. Em seguida
aplica o critério de empate da proposta e gera as figuras e tabelas.

**Arquivos que ele gera** (na pasta de trabalho; no Colab, baixe-os pelo painel *Arquivos* ou
copie-os para o Drive, porque a sessão é descartável):

| Arquivo | Conteúdo |
|---|---|
| `fig_final_mae_teste.png` | **figura principal**: MAE de teste por modelo e horizonte |
| `fig_final_ganho_poluentes.png` | ganho dos poluentes no GRU contra o limiar de 2 desvios-padrão |
| `fig_final_curvas_gru.png` | curvas de treino e validação do GRU (semente 42) |
| `resultados_finais_agregados.csv` | MAE de validação e de teste, média e desvio entre sementes |
| `resultados_validacao_por_execucao.csv` | uma linha por modelo e semente, na validação |
| `resultados_teste_por_execucao.csv` | uma linha por modelo e semente, no teste |
| `criterio_de_empate_h1.csv` | a decisão do critério de empate, por município |
| `checkpoints_gru/` | checkpoint de cada treino de GRU, gravado a cada época |

**Checkpoints e retomada.** Se a sessão cair no meio do treino, basta executar o notebook de
novo: cada treino retoma do último ponto salvo em `checkpoints_gru/` (os checkpoints são
identificados pelos hiperparâmetros e pelos dados, então não se misturam com outra
configuração). Para treinar tudo do zero, apague a pasta ou use `RETOMAR = False`. A parada
antecipada interrompe o treino quando a validação não melhora por 15 épocas e guarda o melhor
estado.

**Teste (2019).** O notebook final só lê o ano de teste na seção 6, depois de congelar os
modelos, os hiperparâmetros e o critério na validação. Os hiperparâmetros do GRU (tamanho e taxa
de aprendizado) foram escolhidos só na validação; a grade pode ser refeita com
`EXPLORAR_HIPERPARAMETROS = True`. O critério de empate foi interpretado assim: o desvio de
referência é o maior dos dois desvios entre sementes (`ddof = 1`) e o "melhor Poisson" é o de
menor MAE de teste entre as versões sem e com poluentes; com 2 municípios, "a maioria" exige
os dois.

**Só os baselines (M2).** O `BASELINE_problemas_respiratorios.ipynb` roda em cerca de 8 s em
CPU e gera `fig_m2_curvas_poisson.png` e `resultados_m2.csv`. Ele bloqueia o ano de teste
(`ULTIMO_DIA_USAVEL = '2018-12-31'`) e foi mantido como registro do marco M2.

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
quando o script perguntar).

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

## Limitações do estudo

Os detalhes e a discussão estão no artigo. Em resumo:

- O teste é um único ano (2019), com dois municípios e três sementes por configuração do GRU: o
  desvio-padrão estimado com três valores é impreciso, e o critério de empate exige que os dois
  municípios passem.
- Com cerca de 5 internações por dia em Piracicaba, o ruído de contagem já deixa pouco espaço
  para qualquer modelo reduzir o MAE; em São Paulo, as contagens são 11 a 17 vezes mais dispersas
  que um Poisson puro.
- Os poluentes são valores diários médios entre as estações de cada município, o que não
  representa a exposição individual.
- O GRU é uma única arquitetura, com poucos hiperparâmetros ajustados, e os modelos não foram
  retreinados com a validação.
