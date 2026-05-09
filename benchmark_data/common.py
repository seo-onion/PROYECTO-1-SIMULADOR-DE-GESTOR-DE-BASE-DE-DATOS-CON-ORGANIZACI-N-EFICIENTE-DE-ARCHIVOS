from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from pathlib import Path
from time import perf_counter
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = Path(__file__).resolve().parent / "generated"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def dataset_path(size: int) -> Path:
    return GENERATED_DIR / f"random_{size}.csv"


def runtime_path(size: int, index: str) -> Path:
    return PROJECT_ROOT / "runtime_benchmark" / f"n_{size}_{index}"


def generate_csv(size: int, seed: int | None = None, overwrite: bool = True) -> Path:
    if seed is None:
        seed = 20260509 + size

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = dataset_path(size)
    if path.exists() and not overwrite:
        return path

    rng = random.Random(seed)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "seq_key", "score", "pos", "name"])
        for row_id in range(1, size + 1):
            seq_key = rng.randint(1, size * 10)
            score = round(rng.uniform(0, 100000), 4)
            x = round(rng.uniform(-180, 180), 6)
            y = round(rng.uniform(-90, 90), 6)
            name = f"name_{row_id:06d}"
            writer.writerow([row_id, seq_key, score, f"({x},{y})", name])
    return path


def ensure_dataset(size: int) -> Path:
    path = dataset_path(size)
    if not path.exists():
        return generate_csv(size, overwrite=True)
    return path


def reset_runtime(size: int, index: str) -> Path:
    path = runtime_path(size, index)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def benchmark_queries(size: int) -> list[tuple[str, str, str]]:
    mid = max(1, size // 2)
    seq_low = size
    seq_high = size * 2
    score_low = 25000.0
    score_high = 75000.0
    return [
        ("bench_hash", "hash_exact_id", f"SELECT * FROM bench_hash_{size} WHERE id = {mid};"),
        ("bench_seq", "sequential_range", f"SELECT * FROM bench_seq_{size} WHERE seq_key BETWEEN {seq_low} AND {seq_high};"),
        ("bench_btree", "btree_score_range", f"SELECT * FROM bench_btree_{size} WHERE score BETWEEN {score_low} AND {score_high};"),
        ("bench_rtree", "rtree_radius", f"SELECT * FROM bench_rtree_{size} WHERE pos IN (POINT(0, 0), RADIUS 10);"),
        ("bench_rtree", "rtree_knn", f"SELECT * FROM bench_rtree_{size} WHERE pos IN (POINT(0, 0), K 10);"),
    ]


def create_table_sql(size: int, csv_path: Path, table_kind: str) -> str:
    table_names = {
        "bench_hash": f"bench_hash_{size}",
        "bench_seq": f"bench_seq_{size}",
        "bench_btree": f"bench_btree_{size}",
        "bench_rtree": f"bench_rtree_{size}",
    }
    index_defs = {
        "bench_hash": "id INT INDEX HASH, seq_key INT, score FLOAT, pos POINT2D, name VARCHAR(24)",
        "bench_seq": "id INT, seq_key INT INDEX SEQUENTIAL, score FLOAT, pos POINT2D, name VARCHAR(24)",
        "bench_btree": "id INT, seq_key INT, score FLOAT INDEX BTREE, pos POINT2D, name VARCHAR(24)",
        "bench_rtree": "id INT, seq_key INT, score FLOAT, pos POINT2D INDEX RTREE, name VARCHAR(24)",
    }
    if table_kind not in table_names:
        raise ValueError(f"Tipo de tabla benchmark no soportado: {table_kind}")
    normalized_path = csv_path.resolve().as_posix()
    return (
        f"CREATE TABLE {table_names[table_kind]} ("
        f"{index_defs[table_kind]}"
        f") FROM FILE '{normalized_path}';"
    )


def write_results(size: int, rows: Iterable[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"benchmark_{size}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(list(rows), file, indent=2, ensure_ascii=False)
    return path


def parse_size_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ejecuta benchmarks de la BD.")
    parser.add_argument("--size", type=int, choices=[1000, 10000, 100000], help="Tamano del dataset.")
    parser.add_argument("--all", action="store_true", help="Ejecuta 1000, 10000 y 100000.")
    parser.add_argument(
        "--index",
        choices=["hash", "sequential", "btree", "rtree", "all"],
        default="hash",
        help="Indice a probar. Por defecto: hash. Usa 'all' para todos.",
    )
    parser.add_argument("--keep-runtime", action="store_true", help="No borra el runtime al terminar.")
    return parser


def timed(label: str, callback):
    started = perf_counter()
    value = callback()
    elapsed_ms = round((perf_counter() - started) * 1000, 3)
    print(f"{label}: {elapsed_ms} ms")
    return value, elapsed_ms
