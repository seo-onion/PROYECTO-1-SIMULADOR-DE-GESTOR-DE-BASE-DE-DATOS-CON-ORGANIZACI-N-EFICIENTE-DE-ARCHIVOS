import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'DB_source'))
from Table_file_managment import init_main_db, insert_record, read_db_header

from sequential import SequentialIndex


def _make_demo_db(db_file: str, fmt: str, rows: list):
    """Crea un archivo DB con Table_file_managment e inserta las filas."""
    init_main_db(db_file, fmt)
    for row in rows:
        insert_record(db_file, row)
    return read_db_header(db_file)


def test_sequential():
    db_file = 'demo_seq.bin'
    fmt     = 'i 30s f'   # employee_id (int) | name (30 bytes) | salary (float)

    for p in [db_file, db_file + 'seq_index0.bin']:
        if os.path.exists(p):
            os.remove(p)

    rows = [
        (1001, b'Alice Johnson'.ljust(30),   5000.0),
        (1003, b'Carlos Lima'.ljust(30),     4200.0),
        (1005, b'Diana Reyes'.ljust(30),     6100.0),
        (1007, b'Elena Voss'.ljust(30),      4800.0),
        (1009, b'Frank Muller'.ljust(30),    5300.0),
    ]

    h = _make_demo_db(db_file, fmt, rows)

    idx = SequentialIndex(db_file, fmt, key_index=0, k_threshold=3)
    n = idx.build_from_db(h)
    print(f"Índice construido: {n} entradas | stats: {idx.stats()}\n")

    # Búsqueda puntual
    offsets = idx.search(1005)
    for off in offsets:
        eid, name_b, salary = idx.read_record(off)
        print(f"search(1005): id={eid} nombre={name_b.decode().strip()!r} salario={salary:.2f}")

    # Búsqueda por rango O(log n + m)
    print()
    offsets = idx.range_search(1003, 1007)
    print(f"range_search(1003, 1007): {len(offsets)} resultado(s)")
    for off in offsets:
        eid, name_b, salary = idx.read_record(off)
        print(f"  id={eid} nombre={name_b.decode().strip()!r}")

    # Inserción → área auxiliar; al llegar a k_threshold dispara rebuild
    print()
    new_off = insert_record(db_file, (1006, b'George Park'.ljust(30), 4600.0))
    idx.insert(1006, new_off)
    print(f"Tras insertar 1006: {idx.stats()}")

    # Eliminación
    ok = idx.delete(1003)
    print(f"delete(1003): {'OK' if ok else 'NO ENCONTRADO'}")
    print(f"search(1003) tras delete: {idx.search(1003)}")

    idx.close()
    print("\nTest completado.")


test_sequential()
