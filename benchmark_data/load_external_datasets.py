from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BENCHMARK_DIR / "generated" / "external_imports"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    table_name: str
    create_columns: str
    prepare_csv: Callable[[], Path]


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "null":
        return ""
    return text


def clean_int(value: object) -> str:
    text = clean_text(value)
    if not text:
        return "0"
    return str(int(float(text)))


def clean_float(value: object) -> str:
    text = clean_text(value)
    if not text:
        return "0"
    return str(float(text))


def rewrite_csv(source: Path, output: Path, headers: list[str], transform: Callable[[dict[str, str]], list[object]]) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as src, output.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        writer = csv.writer(dst)
        writer.writerow(headers)
        for row in reader:
            writer.writerow(transform(row))
    return output


def parse_sql_insert_values(path: Path) -> Iterable[list[str]]:
    statement_parts: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for line in file:
            upper_line = line.upper()
            if not statement_parts and "INSERT INTO" not in upper_line:
                continue
            statement_parts.append(line.strip())
            if ";" not in line:
                continue

            statement = " ".join(statement_parts)
            statement_parts = []
            upper = statement.upper()
            values_at = upper.find("VALUES")
            start = statement.find("(", values_at)
            end = statement.rfind(")")
            if values_at == -1 or start == -1 or end == -1 or end <= start:
                continue
            inner = re.sub(r"(?i)(^|,\s*)e'", r"\1'", statement[start + 1 : end])
            yield next(
                csv.reader(
                    [inner],
                    quotechar="'",
                    doublequote=True,
                    escapechar="\\",
                    skipinitialspace=True,
                )
            )


def prepare_pokemon_csv() -> Path:
    source = BENCHMARK_DIR / "pokemon_complete_2025.csv"
    output = GENERATED_DIR / "pokemon_complete_2025_import.csv"
    headers = [
        "pokedex_id",
        "name",
        "genus",
        "generation",
        "type_1",
        "type_2",
        "num_types",
        "hp",
        "attack",
        "defense",
        "sp_attack",
        "sp_defense",
        "speed",
        "base_stat_total",
        "height_m",
        "weight_kg",
        "base_experience",
        "ability_1",
        "ability_2",
        "hidden_ability",
        "color",
        "shape",
        "habitat",
        "growth_rate",
        "egg_groups",
        "is_legendary",
        "is_mythical",
        "is_baby",
        "capture_rate",
        "base_happiness",
        "hatch_counter",
        "gender_rate",
        "description",
        "sprite_url",
        "is_dual_type",
        "bmi",
        "attack_defense_ratio",
        "physical_total",
        "special_total",
        "offensive_total",
        "defensive_total",
        "gender_distribution",
        "stat_tier",
    ]
    int_columns = {
        "pokedex_id",
        "num_types",
        "hp",
        "attack",
        "defense",
        "sp_attack",
        "sp_defense",
        "speed",
        "base_stat_total",
        "base_experience",
        "capture_rate",
        "base_happiness",
        "hatch_counter",
        "gender_rate",
        "physical_total",
        "special_total",
        "offensive_total",
        "defensive_total",
    }
    float_columns = {"height_m", "weight_kg", "bmi", "attack_defense_ratio"}

    def transform(row: dict[str, str]) -> list[object]:
        values: list[object] = []
        for header in headers:
            if header in int_columns:
                values.append(clean_int(row.get(header)))
            elif header in float_columns:
                values.append(clean_float(row.get(header)))
            else:
                values.append(clean_text(row.get(header)))
        return values

    return rewrite_csv(source, output, headers, transform)


def prepare_customers_csv(size: int) -> Path:
    source = BENCHMARK_DIR / f"customers-{size}.csv"
    output = GENERATED_DIR / f"customers_{size}_import.csv"
    headers = [
        "id",
        "Customer_Id",
        "First_Name",
        "Last_Name",
        "Company",
        "City",
        "Country",
        "Phone_1",
        "Phone_2",
        "Email",
        "Subscription_Date",
        "Website",
    ]
    source_headers = {
        "id": "Index",
        "Customer_Id": "Customer Id",
        "First_Name": "First Name",
        "Last_Name": "Last Name",
        "Company": "Company",
        "City": "City",
        "Country": "Country",
        "Phone_1": "Phone 1",
        "Phone_2": "Phone 2",
        "Email": "Email",
        "Subscription_Date": "Subscription Date",
        "Website": "Website",
    }

    def transform(row: dict[str, str]) -> list[object]:
        values: list[object] = []
        for header in headers:
            raw = row.get(source_headers[header])
            values.append(clean_int(raw) if header == "id" else clean_text(raw))
        return values

    return rewrite_csv(source, output, headers, transform)


def prepare_airbnb_csv() -> Path:
    source = BENCHMARK_DIR / "ab_nyc_2019.sql"
    output = GENERATED_DIR / "airbnb_locations_import.csv"
    headers = [
        "id",
        "name",
        "host_id",
        "host_name",
        "neighbourhood_group",
        "neighbourhood",
        "coords",
        "room_type",
        "price",
        "minimum_nights",
        "number_of_reviews",
        "last_review",
        "reviews_per_month",
        "calculated_host_listings_count",
        "availability_365",
    ]
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        for values in parse_sql_insert_values(source):
            latitude = clean_float(values[6])
            longitude = clean_float(values[7])
            writer.writerow(
                [
                    clean_int(values[0]),
                    clean_text(values[1]),
                    clean_text(values[2]),
                    clean_text(values[3]),
                    clean_text(values[4]),
                    clean_text(values[5]),
                    f"({latitude},{longitude})",
                    clean_text(values[8]),
                    clean_int(values[9]),
                    clean_int(values[10]),
                    clean_int(values[11]),
                    clean_text(values[12]),
                    clean_float(values[13]),
                    clean_int(values[14]),
                    clean_int(values[15]),
                ]
            )
    return output


def dataset_configs() -> dict[str, DatasetConfig]:
    customer_columns = (
        "id INT INDEX HASH, Customer_Id VARCHAR(20) INDEX SEQUENTIAL, First_Name VARCHAR(60), "
        "Last_Name VARCHAR(60), Company VARCHAR(120), City VARCHAR(80), Country VARCHAR(80), "
        "Phone_1 VARCHAR(40), Phone_2 VARCHAR(40), Email VARCHAR(120), "
        "Subscription_Date VARCHAR(20) INDEX BTREE, Website VARCHAR(160)"
    )
    return {
        "pokemon": DatasetConfig(
            "pokemon",
            "pokemon_complete_2025",
            (
                "pokedex_id INT INDEX HASH, name VARCHAR(50) INDEX SEQUENTIAL, genus VARCHAR(50), generation VARCHAR(10), "
                "type_1 VARCHAR(20), type_2 VARCHAR(20), num_types INT, hp INT, attack INT, "
                "defense INT, sp_attack INT, sp_defense INT, speed INT, base_stat_total INT INDEX BTREE, "
                "height_m FLOAT, weight_kg FLOAT, base_experience INT, ability_1 VARCHAR(50), "
                "ability_2 VARCHAR(50), hidden_ability VARCHAR(50), color VARCHAR(20), "
                "shape VARCHAR(30), habitat VARCHAR(30), growth_rate VARCHAR(30), "
                "egg_groups VARCHAR(50), is_legendary VARCHAR(10), is_mythical VARCHAR(10), "
                "is_baby VARCHAR(10), capture_rate INT, base_happiness INT, hatch_counter INT, "
                "gender_rate INT, description VARCHAR(255), sprite_url VARCHAR(150), "
                "is_dual_type VARCHAR(10), bmi FLOAT, attack_defense_ratio FLOAT, "
                "physical_total INT, special_total INT, offensive_total INT, defensive_total INT, "
                "gender_distribution VARCHAR(50), stat_tier VARCHAR(50)"
            ),
            prepare_pokemon_csv,
        ),
        "customers_10000": DatasetConfig(
            "customers_10000",
            "customers_10000",
            customer_columns,
            lambda: prepare_customers_csv(10000),
        ),
        "customers_100000": DatasetConfig(
            "customers_100000",
            "customers_100000",
            customer_columns.replace("First_Name VARCHAR(60)", "First_Name VARCHAR(60) INDEX HASH"),
            lambda: prepare_customers_csv(100000),
        ),
        "airbnb": DatasetConfig(
            "airbnb",
            "airbnb_locations",
            (
                "id INT INDEX HASH, name VARCHAR(160), host_id VARCHAR(40), host_name VARCHAR(80), "
                "neighbourhood_group VARCHAR(80), neighbourhood VARCHAR(100), "
                "coords POINT2D INDEX RTREE, room_type VARCHAR(40), price INT INDEX BTREE, "
                "minimum_nights INT, number_of_reviews INT, last_review VARCHAR(20), "
                "reviews_per_month FLOAT, calculated_host_listings_count INT, availability_365 INT"
            ),
            prepare_airbnb_csv,
        ),
    }


def create_table_sql(config: DatasetConfig, csv_path: Path) -> str:
    normalized_path = csv_path.resolve().as_posix()
    return f"CREATE TABLE {config.table_name} ({config.create_columns}) FROM FILE '{normalized_path}';"


def execute_local(sql: str, runtime: Path) -> dict:
    from engine import Engine

    engine = Engine(runtime)
    try:
        return engine.execute(sql)
    finally:
        engine.close()


def execute_backend(sql: str, api_url: str) -> dict:
    payload = json.dumps({"sql": sql}).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Backend respondio {exc.code}: {body}") from exc


def load_dataset(config: DatasetConfig, args: argparse.Namespace) -> dict:
    csv_path = config.prepare_csv()
    sql = create_table_sql(config, csv_path)
    if args.print_sql:
        print(sql)
    if args.csv_only:
        return {"ok": True, "dataset": config.name, "csv": str(csv_path), "loaded": False}
    if args.mode == "backend":
        result = execute_backend(sql, args.api_url)
    else:
        result = execute_local(sql, Path(args.runtime))
    return {"ok": True, "dataset": config.name, "csv": str(csv_path), "loaded": True, "result": result}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga datasets externos en la BD del proyecto.")
    parser.add_argument(
        "--dataset",
        choices=["pokemon", "customers_10000", "customers_100000", "airbnb", "all"],
        default="pokemon",
        help="Dataset a preparar/cargar.",
    )
    parser.add_argument(
        "--mode",
        choices=["local", "backend"],
        default="local",
        help="local usa Engine directo; backend envia la sentencia a /query.",
    )
    parser.add_argument("--runtime", default=str(PROJECT_ROOT / "runtime"), help="Runtime para modo local.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/query", help="Endpoint para modo backend.")
    parser.add_argument("--reset-runtime", action="store_true", help="Borra el runtime antes de cargar en modo local.")
    parser.add_argument("--csv-only", action="store_true", help="Solo genera CSVs compatibles, sin cargar tablas.")
    parser.add_argument("--print-sql", action="store_true", help="Muestra el CREATE TABLE usado.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configs = dataset_configs()
    selected = list(configs.values()) if args.dataset == "all" else [configs[args.dataset]]

    runtime = Path(args.runtime)
    if args.reset_runtime and args.mode == "local" and runtime.exists():
        shutil.rmtree(runtime)

    results = [load_dataset(config, args) for config in selected]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
