from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

MUNICIPALITIES = {"353870": "Piracicaba", "355030": "São Paulo"}
USECOLS = ["DT_INTER", "MUNIC_RES", "DIAG_PRINC", "N_AIH", "IDENT", "ANO_CMPT", "MES_CMPT"]

frames = []
for file in sorted(RAW_DIR.glob("*.csv")):
    df = pd.read_csv(
        file,
        dtype=str,
        encoding="latin1",
        usecols=lambda c: c.strip().upper() in USECOLS,
        low_memory=False,
    )
    df.columns = df.columns.str.strip().str.upper()

    df["MUNIC_RES"] = df["MUNIC_RES"].str.strip().str.zfill(6)
    df = df[df["MUNIC_RES"].isin(MUNICIPALITIES)]

    df["DIAG_PRINC"] = df["DIAG_PRINC"].str.strip().str.upper()
    df = df[df["DIAG_PRINC"].str.match(r"^J\d{2}", na=False)]

    frames.append(df)

data = pd.concat(frames, ignore_index=True)

data["DT_INTER"] = pd.to_datetime(data["DT_INTER"], format="%Y%m%d", errors="coerce")
data["CMPT"] = pd.to_datetime(
    data["ANO_CMPT"] + data["MES_CMPT"].str.zfill(2) + "01",
    format="%Y%m%d",
    errors="coerce",
)

print("Linhas:", len(data))
print("\nTotal por município:")
print(data["MUNIC_RES"].map(MUNICIPALITIES).value_counts())

# 1) Duplicidades
print("\nN_AIH duplicado:", data["N_AIH"].duplicated().sum())
print("\nIDENT:")
print(data["IDENT"].value_counts())

# 2) Defasagem entre internação e competência (em meses)
lag = (data["CMPT"].dt.year - data["DT_INTER"].dt.year) * 12 \
      + (data["CMPT"].dt.month - data["DT_INTER"].dt.month)
print("\nDefasagem (meses):")
print(lag.value_counts().sort_index())

# 3) Internações fora do período
fora = ~data["DT_INTER"].between("2014-01-01", "2019-12-31")
print("\nFora de 2014-2019:", fora.sum())

# 4) Série mensal, para ver a queda no fim de 2019
print("\nÚltimos meses:")
print(data.groupby(data["DT_INTER"].dt.to_period("M")).size().tail(8))