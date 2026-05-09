from __future__ import annotations

from common import (
    benchmark_queries,
    create_table_sql,
    ensure_dataset,
    parse_size_args,
    reset_runtime,
    timed,
    write_results,
)
from engine import Engine


INDEX_TO_TABLE = {
    "hash": ["bench_hash"],
    "sequential": ["bench_seq"],
    "btree": ["bench_btree"],
    "rtree": ["bench_rtree"],
    "all": ["bench_hash", "bench_seq", "bench_btree", "bench_rtree"],
}


def run_for_size(size: int, index: str, keep_runtime: bool = False) -> None:
    csv_path = ensure_dataset(size)
    runtime = reset_runtime(size, index)
    engine = Engine(runtime)
    rows: list[dict] = []

    try:
        table_kinds = INDEX_TO_TABLE[index]
        for table_kind in table_kinds:
            create_sql = create_table_sql(size, csv_path, table_kind)
            create_result, load_elapsed_ms = timed(
                f"carga_{table_kind}_{size}",
                lambda sql=create_sql: engine.execute(sql),
            )
            rows.append({
                "size": size,
                "table_kind": table_kind,
                "query_name": "create_from_csv",
                "sql": create_sql,
                "count": create_result["results"][0].get("imported_rows", 0),
                "stats": create_result["stats"],
                "wall_ms": load_elapsed_ms,
            })

        for table_kind, query_name, sql in benchmark_queries(size):
            if table_kind not in table_kinds:
                continue
            result = engine.execute(sql)
            first_result = result["results"][0]
            count = first_result.get("count", 0)
            print(
                f"{query_name}: count={count} "
                f"reads={result['stats']['disk_reads']} "
                f"writes={result['stats']['disk_writes']} "
                f"ms={result['stats']['execution_ms']}"
            )
            rows.append({
                "size": size,
                "table_kind": table_kind,
                "query_name": query_name,
                "sql": sql,
                "count": count,
                "stats": result["stats"],
            })
    finally:
        engine.close()
        if not keep_runtime:
            import shutil

            shutil.rmtree(runtime, ignore_errors=True)

    result_path = write_results(size, rows)
    print(f"resultados: {result_path}")


def main() -> None:
    parser = parse_size_args()
    args = parser.parse_args()
    if args.all:
        sizes = [1000, 10000, 100000]
    elif args.size:
        sizes = [args.size]
    else:
        parser.error("usa --size {1000,10000,100000} o --all")

    for size in sizes:
        run_for_size(size, index=args.index, keep_runtime=args.keep_runtime)


if __name__ == "__main__":
    main()
