from pathlib import Path
import pandas as pd

# ==================================================
# SETTINGS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "internacoes_respiratorias-Sao_Paulo.csv"

# Municipalities (IBGE codes, 6 digits as in DATASUS)
MUNICIPALITIES = {
    #"353870": "Piracicaba",
    "355030": "São Paulo"
}

# Only the columns we need (saves a lot of memory)
USECOLS = ["DT_INTER", "MUNIC_RES", "DIAG_PRINC", "N_AIH"]

# ==================================================
# LOAD + FILTER, FILE BY FILE
# ==================================================

files = sorted(RAW_DIR.glob("*.csv"))

if not files:
    raise FileNotFoundError(f"No CSV files found in {RAW_DIR}")

print(f"Found {len(files)} CSV files.")

frames = []
total_read = 0

for file in files:
    # Read only the needed columns (header is normalized via callable)
    df = pd.read_csv(
        file,
        dtype=str,
        encoding="latin1",
        usecols=lambda c: c.strip().upper() in USECOLS,
        low_memory=False,
    )

    df.columns = df.columns.str.strip().str.upper()

    missing = set(USECOLS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {file.name}: {missing}")

    total_read += len(df)

    # Normalize municipality code and filter immediately
    df["MUNIC_RES"] = (
        df["MUNIC_RES"]
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )
    df = df[df["MUNIC_RES"].isin(MUNICIPALITIES)]

    # Respiratory diseases (ICD-10 J00-J99)
    df["DIAG_PRINC"] = df["DIAG_PRINC"].str.strip().str.upper()
    df = df[df["DIAG_PRINC"].str.match(r"^J\d{2}", na=False)]

    print(f"{file.name}: kept {len(df)} rows")

    frames.append(df)

data = pd.concat(frames, ignore_index=True)

print(f"\nTotal records read: {total_read}")
print(f"Records kept: {len(data)}")

# ==================================================
# CLEAN
# ==================================================

data["DT_INTER"] = pd.to_datetime(
    data["DT_INTER"],
    format="%Y%m%d",
    errors="coerce",
)

data = data.dropna(subset=["DT_INTER"])

data["MUNICIPIO"] = data["MUNIC_RES"].map(MUNICIPALITIES)

# ==================================================
# DAILY AGGREGATION
# ==================================================

daily = (
    data.groupby(["DT_INTER", "MUNICIPIO"])
    .size()
    .reset_index(name="INTERNACOES")
)

dates = pd.date_range(start="2014-01-01", end="2019-12-31", freq="D")

calendar = pd.MultiIndex.from_product(
    [dates, list(MUNICIPALITIES.values())],
    names=["DT_INTER", "MUNICIPIO"],
).to_frame(index=False)

result = calendar.merge(daily, on=["DT_INTER", "MUNICIPIO"], how="left")

result["INTERNACOES"] = result["INTERNACOES"].fillna(0).astype(int)

# ==================================================
# EXPORT
# ==================================================

result = result.sort_values(["MUNICIPIO", "DT_INTER"])

result.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print("\nProcessing completed!")
print(f"Output: {OUTPUT_FILE}")
print(f"Final records: {len(result)}")
print(result.head(10))