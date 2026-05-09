from __future__ import annotations

import csv
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from DB_source.Table_file_managment import (
    delete_record,
    init_main_db,
    insert_record,
    iter_records,
    read_db_header,
    update_index_flags,
)
from DB_source.page_manager import get_global_counters, reset_global_counters
from parser.sql_parser import (
    BetweenCondition,
    ColumnDefinition,
    Command,
    CreateTableCommand,
    DeleteCommand,
    InsertCommand,
    KNNCondition,
    RadiusCondition,
    SelectCommand,
    SimpleCondition,
    parse_sql,
)

INDEX_DIR = Path(__file__).resolve().parents[1] / "Data_structures" / "B+TREE"
if str(INDEX_DIR) not in sys.path:
    sys.path.insert(0, str(INDEX_DIR))

from BPlusTree import Btree  # type: ignore  # noqa: E402
from Rtree import RTree  # type: ignore  # noqa: E402
from extendible_hash import ExtendibleHash  # type: ignore  # noqa: E402
from sequential import SequentialIndex  # type: ignore  # noqa: E402


INDEX_FLAGS = {
    "SEQUENTIAL": "S",
    "HASH": "H",
    "BTREE": "B",
    "RTREE": "R",
}

INDEX_ALIASES = {
    "SEQ": "SEQUENTIAL",
    "SEQUENTIAL": "SEQUENTIAL",
    "SEQUENTIALFILE": "SEQUENTIAL",
    "HASH": "HASH",
    "EXTENDIBLEHASH": "HASH",
    "EXTENDIBLE_HASH": "HASH",
    "B+TREE": "BTREE",
    "BPLUSTREE": "BTREE",
    "BPLUS": "BTREE",
    "BTREE": "BTREE",
    "RTREE": "RTREE",
    "R_TREE": "RTREE",
}


@dataclass
class ColumnSchema:
    name: str
    type_name: str
    index_technique: Optional[str] = None
    struct_tokens: List[str] = field(default_factory=list)
    dimension: int = 1
    length: Optional[int] = None

    @property
    def is_spatial(self) -> bool:
        return self.dimension > 1

    @property
    def normalized_index(self) -> Optional[str]:
        if not self.index_technique:
            return None
        return normalize_index_name(self.index_technique)


@dataclass
class TableSchema:
    name: str
    db_file: str
    struct_format: str
    columns: List[ColumnSchema]
    source_path: Optional[str] = None

    def column(self, name: str) -> ColumnSchema:
        for column in self.columns:
            if column.name.lower() == name.lower():
                return column
        raise KeyError(f"La columna '{name}' no existe en la tabla '{self.name}'")

    def column_index(self, name: str) -> int:
        for idx, column in enumerate(self.columns):
            if column.name.lower() == name.lower():
                return idx
        raise KeyError(f"La columna '{name}' no existe en la tabla '{self.name}'")


@dataclass
class TableRuntime:
    schema: TableSchema
    field_ranges: Dict[str, Tuple[int, int]]
    indexes: Dict[str, Any] = field(default_factory=dict)


class Engine:
    def __init__(self, root_dir: str | Path = "runtime"):
        self.root_dir = Path(root_dir)
        self.tables_dir = self.root_dir / "tables"
        self.catalog_path = self.root_dir / "catalog.json"
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._catalog = self._load_catalog()
        self._tables: Dict[str, TableRuntime] = {}
        for table_name, raw_schema in self._catalog.items():
            self._tables[table_name] = self._load_runtime(raw_schema)

    def execute(self, sql: str) -> Dict[str, Any]:
        started = time.perf_counter()
        reset_global_counters()
        commands = parse_sql(sql)
        if not commands:
            raise ValueError("No se encontraron sentencias SQL para ejecutar")

        results = [self._execute_command(command) for command in commands]
        counters = get_global_counters()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "ok": True,
            "results": results,
            "stats": {
                "execution_ms": elapsed_ms,
                "disk_reads": counters.reads,
                "disk_writes": counters.writes,
            },
        }

    def list_tables(self) -> List[Dict[str, Any]]:
        return [self.describe_table(name) for name in sorted(self._tables.keys())]

    def describe_table(self, table_name: str) -> Dict[str, Any]:
        runtime = self._get_runtime(table_name)
        return {
            "name": runtime.schema.name,
            "db_file": runtime.schema.db_file,
            "struct_format": runtime.schema.struct_format,
            "source_path": runtime.schema.source_path,
            "columns": [asdict(column) for column in runtime.schema.columns],
            "indexes": sorted(
                column.name for column in runtime.schema.columns if column.normalized_index
            ),
            "row_count": read_db_header(runtime.schema.db_file).reg_number,
        }

    def close(self) -> None:
        for runtime in self._tables.values():
            for index in runtime.indexes.values():
                close = getattr(index, "close", None)
                if callable(close):
                    close()

    def _execute_command(self, command: Command) -> Dict[str, Any]:
        with self._lock:
            if isinstance(command, CreateTableCommand):
                return self._create_table(command)
            if isinstance(command, InsertCommand):
                return self._insert(command)
            if isinstance(command, SelectCommand):
                return self._select(command)
            if isinstance(command, DeleteCommand):
                return self._delete(command)
        raise TypeError(f"Comando no soportado: {type(command)!r}")

    def _create_table(self, command: CreateTableCommand) -> Dict[str, Any]:
        table_name = command.table_name.lower()
        if table_name in self._tables:
            raise ValueError(f"La tabla '{command.table_name}' ya existe")

        columns = [self._build_column_schema(column) for column in command.columns]
        struct_format = " ".join(token for column in columns for token in column.struct_tokens)
        table_dir = self.tables_dir / table_name
        table_dir.mkdir(parents=True, exist_ok=True)
        db_file = str((table_dir / f"{table_name}.bin").resolve())
        init_main_db(db_file, struct_format)

        schema = TableSchema(
            name=command.table_name,
            db_file=db_file,
            struct_format=struct_format,
            columns=columns,
            source_path=command.source_path,
        )
        runtime = self._runtime_from_schema(schema)
        self._tables[table_name] = runtime
        self._catalog[table_name] = self._serialize_schema(schema)
        self._persist_catalog()
        self._ensure_indexes(runtime)

        imported = 0
        if command.source_path:
            imported = self._import_csv(runtime, command.source_path)

        return {
            "operation": "create_table",
            "table": command.table_name,
            "columns": [asdict(column) for column in columns],
            "imported_rows": imported,
        }

    def _insert(self, command: InsertCommand) -> Dict[str, Any]:
        runtime = self._get_runtime(command.table_name)
        self._ensure_indexes(runtime)
        row = self._normalize_insert_values(runtime, command.values)
        flat_record = self._flatten_row(runtime, row)
        db_offset = insert_record(runtime.schema.db_file, flat_record)
        self._update_indexes_on_insert(runtime, row, db_offset)
        return {
            "operation": "insert",
            "table": runtime.schema.name,
            "db_offset": db_offset,
            "row": row,
        }

    def _select(self, command: SelectCommand) -> Dict[str, Any]:
        runtime = self._get_runtime(command.table_name)
        self._ensure_indexes(runtime)
        offsets = self._resolve_select_offsets(runtime, command.condition)
        rows = [self._row_at_offset(runtime, offset) for offset in offsets]
        return {
            "operation": "select",
            "table": runtime.schema.name,
            "count": len(rows),
            "rows": rows,
        }

    def _delete(self, command: DeleteCommand) -> Dict[str, Any]:
        runtime = self._get_runtime(command.table_name)
        self._ensure_indexes(runtime)
        offsets = self._resolve_exact_offsets(runtime, command.condition.column, command.condition.value)
        deleted_rows: List[Dict[str, Any]] = []
        for offset in offsets:
            row = self._row_at_offset(runtime, offset)
            if delete_record(runtime.schema.db_file, offset):
                self._update_indexes_on_delete(runtime, row, offset)
                deleted_rows.append(row)
        return {
            "operation": "delete",
            "table": runtime.schema.name,
            "deleted_count": len(deleted_rows),
            "rows": deleted_rows,
        }

    def _resolve_select_offsets(
        self,
        runtime: TableRuntime,
        condition: SimpleCondition | BetweenCondition | RadiusCondition | KNNCondition,
    ) -> List[int]:
        if isinstance(condition, SimpleCondition):
            if condition.operator == "=":
                return self._resolve_exact_offsets(runtime, condition.column, condition.value)
            return self._resolve_comparison_offsets(
                runtime,
                condition.column,
                condition.operator,
                condition.value,
            )
        if isinstance(condition, BetweenCondition):
            return self._resolve_range_offsets(runtime, condition.column, condition.low, condition.high)
        if isinstance(condition, RadiusCondition):
            return self._resolve_radius_offsets(runtime, condition.column, condition.point, condition.radius)
        if isinstance(condition, KNNCondition):
            return self._resolve_knn_offsets(runtime, condition.column, condition.point, condition.k)
        raise TypeError(f"Condición no soportada: {type(condition)!r}")

    def _resolve_exact_offsets(self, runtime: TableRuntime, column_name: str, value: Any) -> List[int]:
        column = runtime.schema.column(column_name)
        normalized_value = self._normalize_value(column, value)
        index = runtime.indexes.get(column.name)
        if index:
            technique = column.normalized_index
            if technique == "HASH":
                return sorted(index.search(self._index_key(column, normalized_value)))
            if technique == "SEQUENTIAL":
                return sorted(index.search(self._index_key(column, normalized_value)))
            if technique == "BTREE":
                matches = index.range_search(
                    self._index_key(column, normalized_value),
                    self._index_key(column, normalized_value),
                )
                return sorted(ptr for _, ptr in matches)
            if technique == "RTREE":
                return sorted(index.search(tuple(normalized_value)))

        matched_offsets: List[int] = []
        for db_offset, record, deleted in iter_records(runtime.schema.db_file):
            if deleted:
                continue
            row = self._record_to_row(runtime, record)
            if row[column.name] == normalized_value:
                matched_offsets.append(db_offset)
        return matched_offsets

    def _resolve_range_offsets(
        self,
        runtime: TableRuntime,
        column_name: str,
        low: Any,
        high: Any,
    ) -> List[int]:
        column = runtime.schema.column(column_name)
        low_value = self._normalize_value(column, low)
        high_value = self._normalize_value(column, high)

        index = runtime.indexes.get(column.name)
        if index and column.normalized_index == "BTREE":
            matches = index.range_search(self._index_key(column, low_value), self._index_key(column, high_value))
            return sorted(ptr for _, ptr in matches)
        if index and column.normalized_index == "SEQUENTIAL":
            return sorted(index.range_search(self._index_key(column, low_value), self._index_key(column, high_value)))

        matched_offsets: List[int] = []
        for db_offset, record, deleted in iter_records(runtime.schema.db_file):
            if deleted:
                continue
            row = self._record_to_row(runtime, record)
            current = row[column.name]
            if low_value <= current <= high_value:
                matched_offsets.append(db_offset)
        return matched_offsets

    def _resolve_comparison_offsets(
        self,
        runtime: TableRuntime,
        column_name: str,
        operator: str,
        value: Any,
    ) -> List[int]:
        column = runtime.schema.column(column_name)
        if column.is_spatial:
            raise ValueError(f"La columna espacial '{column_name}' no soporta operador {operator}")

        normalized_value = self._normalize_value(column, value)
        matched_offsets: List[int] = []
        for db_offset, record, deleted in iter_records(runtime.schema.db_file):
            if deleted:
                continue
            current = self._record_to_row(runtime, record)[column.name]
            if self._compare_values(current, operator, normalized_value):
                matched_offsets.append(db_offset)
        return matched_offsets

    def _resolve_radius_offsets(
        self,
        runtime: TableRuntime,
        column_name: str,
        point: Sequence[float],
        radius: float,
    ) -> List[int]:
        column = runtime.schema.column(column_name)
        point_value = tuple(float(value) for value in self._normalize_value(column, point))
        if not column.is_spatial:
            raise ValueError(f"La columna '{column_name}' no es espacial")

        index = runtime.indexes.get(column.name)
        candidates: Iterable[int]
        if index and column.normalized_index == "RTREE":
            candidates = index.range_search(point_value, radius)
        else:
            candidates = [
                db_offset
                for db_offset, record, deleted in iter_records(runtime.schema.db_file)
                if not deleted
                and self._distance(point_value, tuple(self._record_to_row(runtime, record)[column.name])) <= radius
            ]

        unique_offsets: List[int] = []
        seen = set()
        for offset in candidates:
            if offset in seen:
                continue
            seen.add(offset)
            row = self._row_at_offset(runtime, offset)
            if self._distance(point_value, tuple(row[column.name])) <= radius:
                unique_offsets.append(offset)
        return sorted(unique_offsets)

    def _resolve_knn_offsets(
        self,
        runtime: TableRuntime,
        column_name: str,
        point: Sequence[float],
        k: int,
    ) -> List[int]:
        column = runtime.schema.column(column_name)
        point_value = tuple(float(value) for value in self._normalize_value(column, point))
        if not column.is_spatial:
            raise ValueError(f"La columna '{column_name}' no es espacial")

        index = runtime.indexes.get(column.name)
        if index and column.normalized_index == "RTREE":
            return index.knn_search(point_value, int(k))

        ranked: List[Tuple[float, int]] = []
        for db_offset, record, deleted in iter_records(runtime.schema.db_file):
            if deleted:
                continue
            row = self._record_to_row(runtime, record)
            ranked.append((self._distance(point_value, tuple(row[column.name])), db_offset))
        ranked.sort(key=lambda item: item[0])
        return [offset for _, offset in ranked[: max(1, int(k))]]

    def _update_indexes_on_insert(self, runtime: TableRuntime, row: Dict[str, Any], db_offset: int) -> None:
        for column in runtime.schema.columns:
            index = runtime.indexes.get(column.name)
            if not index:
                continue
            key = self._index_key(column, row[column.name])
            index.insert(key, db_offset)

    def _update_indexes_on_delete(
        self,
        runtime: TableRuntime,
        row: Dict[str, Any],
        db_offset: int,
    ) -> None:
        for column in runtime.schema.columns:
            index = runtime.indexes.get(column.name)
            if not index:
                continue
            key = self._index_key(column, row[column.name])
            technique = column.normalized_index
            if technique == "RTREE":
                index.delete(db_offset)
            elif technique == "BTREE":
                index.delete(key, db_offset)
            else:
                index.delete(key)

    def _import_csv(self, runtime: TableRuntime, source_path: str) -> int:
        csv_path = Path(source_path)
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
        if not csv_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path}")

        imported = 0
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for raw_row in reader:
                values = [raw_row.get(column.name) for column in runtime.schema.columns]
                row = self._normalize_insert_values(runtime, values)
                flat_record = self._flatten_row(runtime, row)
                db_offset = insert_record(runtime.schema.db_file, flat_record)
                self._update_indexes_on_insert(runtime, row, db_offset)
                imported += 1
        return imported

    def _normalize_insert_values(self, runtime: TableRuntime, values: Sequence[Any]) -> Dict[str, Any]:
        if len(values) != len(runtime.schema.columns):
            raise ValueError(
                f"La tabla '{runtime.schema.name}' espera {len(runtime.schema.columns)} valores y recibió {len(values)}"
            )
        row: Dict[str, Any] = {}
        for column, value in zip(runtime.schema.columns, values):
            row[column.name] = self._normalize_value(column, value)
        return row

    def _normalize_value(self, column: ColumnSchema, value: Any) -> Any:
        type_name = column.type_name.upper()
        if column.is_spatial:
            if isinstance(value, str):
                cleaned = value.strip().removeprefix("(").removesuffix(")")
                parts = [part.strip() for part in cleaned.split(",") if part.strip()]
                coords = tuple(float(part) for part in parts)
            else:
                coords = tuple(float(part) for part in value)
            if len(coords) != column.dimension:
                raise ValueError(
                    f"La columna '{column.name}' espera {column.dimension} coordenadas y recibió {len(coords)}"
                )
            return coords
        if type_name in {"INT", "INTEGER", "SERIAL"}:
            return int(value)
        if type_name in {"FLOAT", "REAL", "DOUBLE"}:
            return float(value)
        if type_name.startswith(("VARCHAR", "CHAR", "STRING", "TEXT")):
            text = str(value)
            if column.length is not None:
                return text[: column.length]
            return text
        raise ValueError(f"Tipo de dato no soportado: {column.type_name}")

    def _flatten_row(self, runtime: TableRuntime, row: Dict[str, Any]) -> Tuple[Any, ...]:
        flat_values: List[Any] = []
        for column in runtime.schema.columns:
            value = row[column.name]
            if column.is_spatial:
                flat_values.extend(float(part) for part in value)
            elif column.length is not None:
                encoded = str(value).encode("utf-8")
                flat_values.append(encoded.ljust(column.length, b" ")[: column.length])
            else:
                flat_values.append(value)
        return tuple(flat_values)

    def _record_to_row(self, runtime: TableRuntime, record: Sequence[Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for column in runtime.schema.columns:
            start, end = runtime.field_ranges[column.name]
            chunk = record[start:end]
            if column.is_spatial:
                row[column.name] = tuple(float(part) for part in chunk)
            elif column.length is not None:
                raw = chunk[0]
                if isinstance(raw, bytes):
                    row[column.name] = raw.decode("utf-8").rstrip("\x00 ").strip()
                else:
                    row[column.name] = str(raw).strip()
            else:
                row[column.name] = chunk[0]
        return row

    def _row_at_offset(self, runtime: TableRuntime, db_offset: int) -> Dict[str, Any]:
        for offset, record, deleted in iter_records(runtime.schema.db_file):
            if offset == db_offset:
                if deleted:
                    raise ValueError(f"El registro en offset {db_offset} está eliminado")
                row = self._record_to_row(runtime, record)
                row["_db_offset"] = db_offset
                return row
        raise ValueError(f"No se encontró el registro en offset {db_offset}")

    def _build_column_schema(self, column: ColumnDefinition) -> ColumnSchema:
        type_name = column.type_name.strip()
        upper_type = type_name.upper()
        index_technique = normalize_index_name(column.index_technique) if column.index_technique else None

        if upper_type in {"INT", "INTEGER", "SERIAL"}:
            return ColumnSchema(column.name, type_name, index_technique, ["i"])
        if upper_type in {"FLOAT", "REAL", "DOUBLE"}:
            return ColumnSchema(column.name, type_name, index_technique, ["f"])

        length = self._parse_length_type(upper_type)
        if length is not None:
            return ColumnSchema(column.name, type_name, index_technique, [f"{length}s"], length=length)

        spatial_dim = self._parse_spatial_dimension(upper_type)
        if spatial_dim is not None:
            if index_technique and index_technique != "RTREE":
                raise ValueError(f"La columna espacial '{column.name}' solo puede usar índice RTREE")
            return ColumnSchema(
                column.name,
                type_name,
                "RTREE",
                ["f"] * spatial_dim,
                dimension=spatial_dim,
            )

        raise ValueError(f"Tipo de columna no soportado: {column.type_name}")

    def _runtime_from_schema(self, schema: TableSchema) -> TableRuntime:
        field_ranges: Dict[str, Tuple[int, int]] = {}
        cursor = 0
        for column in schema.columns:
            size = len(column.struct_tokens)
            field_ranges[column.name] = (cursor, cursor + size)
            cursor += size
        return TableRuntime(schema=schema, field_ranges=field_ranges)

    def _load_runtime(self, raw_schema: Dict[str, Any]) -> TableRuntime:
        schema = TableSchema(
            name=raw_schema["name"],
            db_file=raw_schema["db_file"],
            struct_format=raw_schema["struct_format"],
            columns=[ColumnSchema(**column) for column in raw_schema["columns"]],
            source_path=raw_schema.get("source_path"),
        )
        return self._runtime_from_schema(schema)

    def _serialize_schema(self, schema: TableSchema) -> Dict[str, Any]:
        return {
            "name": schema.name,
            "db_file": schema.db_file,
            "struct_format": schema.struct_format,
            "source_path": schema.source_path,
            "columns": [asdict(column) for column in schema.columns],
        }

    def _ensure_indexes(self, runtime: TableRuntime) -> None:
        changed = False
        total_fields = sum(len(column.struct_tokens) for column in runtime.schema.columns)
        header_flags: List[str] = ["N"] * total_fields
        for column in runtime.schema.columns:
            technique = column.normalized_index
            if not technique:
                continue
            start, end = runtime.field_ranges[column.name]
            for position in range(start, end):
                header_flags[position] = INDEX_FLAGS[technique]
            if column.name in runtime.indexes:
                continue
            index_file = self._index_file_path(runtime.schema, column)
            should_build = not index_file.exists() and read_db_header(runtime.schema.db_file).reg_number > 0
            runtime.indexes[column.name] = self._instantiate_index(runtime.schema, column)
            build_from_db = getattr(runtime.indexes[column.name], "build_from_db", None)
            if should_build and callable(build_from_db):
                build_from_db(read_db_header(runtime.schema.db_file))
            changed = True
        current_flags = read_db_header(runtime.schema.db_file).indexes
        next_flags = "".join(header_flags)
        if current_flags != next_flags:
            update_index_flags(runtime.schema.db_file, next_flags)
        if changed:
            self._catalog[runtime.schema.name.lower()] = self._serialize_schema(runtime.schema)
            self._persist_catalog()

    def _instantiate_index(self, schema: TableSchema, column: ColumnSchema) -> Any:
        key_index = self._physical_key_index(schema, column)
        technique = column.normalized_index
        if technique == "SEQUENTIAL":
            return SequentialIndex(schema.db_file, schema.struct_format, key_index)
        if technique == "HASH":
            return ExtendibleHash(schema.db_file, schema.struct_format, key_index)
        if technique == "BTREE":
            return Btree(schema.db_file, schema.struct_format, key_index)
        if technique == "RTREE":
            return RTree(
                schema.db_file,
                f"{column.dimension}D",
                key_index,
                dimension=column.dimension,
                table_format=schema.struct_format,
            )
        raise ValueError(f"Técnica de índice no soportada: {column.index_technique}")

    def _physical_key_index(self, schema: TableSchema, column: ColumnSchema) -> int:
        runtime = self._runtime_from_schema(schema)
        return runtime.field_ranges[column.name][0]

    def _index_file_path(self, schema: TableSchema, column: ColumnSchema) -> Path:
        key_index = self._physical_key_index(schema, column)
        technique = column.normalized_index
        if technique == "SEQUENTIAL":
            return Path(schema.db_file + "seq_index" + str(key_index) + ".bin")
        if technique == "HASH":
            return Path(schema.db_file + "hash_index" + str(key_index) + ".bin")
        if technique == "BTREE":
            return Path(schema.db_file + "btree_index" + str(key_index) + ".bin")
        if technique == "RTREE":
            return Path(schema.db_file + "rtree_index" + str(key_index) + ".bin")
        raise ValueError(f"TÃ©cnica de Ã­ndice no soportada: {column.index_technique}")

    def _get_runtime(self, table_name: str) -> TableRuntime:
        runtime = self._tables.get(table_name.lower())
        if not runtime:
            raise ValueError(f"La tabla '{table_name}' no existe")
        return runtime

    def _load_catalog(self) -> Dict[str, Dict[str, Any]]:
        if not self.catalog_path.exists():
            return {}
        with self.catalog_path.open("r", encoding="utf-8") as catalog_file:
            return json.load(catalog_file)

    def _persist_catalog(self) -> None:
        with self.catalog_path.open("w", encoding="utf-8") as catalog_file:
            json.dump(self._catalog, catalog_file, indent=2, ensure_ascii=False)

    def _index_key(self, column: ColumnSchema, value: Any) -> Any:
        if column.is_spatial:
            return tuple(float(part) for part in value)
        return value

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))

    @staticmethod
    def _compare_values(left: Any, operator: str, right: Any) -> bool:
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        raise ValueError(f"Operador no soportado: {operator}")

    @staticmethod
    def _parse_length_type(type_name: str) -> Optional[int]:
        for prefix in ("VARCHAR", "CHAR", "STRING", "TEXT"):
            if type_name.startswith(prefix):
                if "(" in type_name and ")" in type_name:
                    return int(type_name[type_name.find("(") + 1 : type_name.find(")")])
                return 255
        return None

    @staticmethod
    def _parse_spatial_dimension(type_name: str) -> Optional[int]:
        normalized = type_name.replace("_", "")
        if normalized.startswith("POINT") and normalized.endswith("D"):
            dim = normalized.removeprefix("POINT").removesuffix("D")
            return int(dim)
        if normalized.startswith("POINT") and "(" in normalized and ")" in normalized:
            return int(normalized[normalized.find("(") + 1 : normalized.find(")")])
        return None


def normalize_index_name(name: Optional[str]) -> str:
    if not name:
        raise ValueError("La técnica de índice no puede ser vacía")
    key = name.upper().replace(" ", "")
    if key not in INDEX_ALIASES:
        raise ValueError(f"Técnica de índice no soportada: {name}")
    return INDEX_ALIASES[key]
