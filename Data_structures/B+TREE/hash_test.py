# -*- coding: utf-8 -*-
import os
import sys
import struct

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'DB_source'))
from Table_file_managment import Header_dto

from extendible_hash import ExtendibleHash


def _make_demo_db(db_file: str, fmt: str, rows: list) -> Header_dto:
    """DB mínima: cabecera 4 bytes (reg_count) + registros. Devuelve Header_dto."""
    fmt_tok     = fmt.replace(' ', '')
    header_size = struct.calcsize('= i')
    reg_size    = struct.calcsize('= ' + fmt_tok)
    with open(db_file, 'wb') as f:
        f.write(struct.pack('= i', len(rows)))
        for row in rows:
            f.write(struct.pack('= ' + fmt_tok, *row))
    att_number = len(fmt.split())
    return Header_dto((header_size, len(rows), reg_size,
                       len(fmt), fmt, att_number, 'N' * att_number))


def test_extendible_hash():
    db_file = 'demo_hash.bin'
    fmt     = 'i 30s f'   # employee_id | name (30 bytes) | salary

    for p in [db_file, db_file + 'hash_index0.bin']:
        if os.path.exists(p):
            os.remove(p)

    rows = [
        (1001, b'Alice Johnson'.ljust(30),  5000.0),
        (1003, b'Carlos Lima'.ljust(30),    4200.0),
        (1005, b'Diana Reyes'.ljust(30),    6100.0),
        (1007, b'Elena Voss'.ljust(30),     4800.0),
        (1009, b'Frank Muller'.ljust(30),   5300.0),
        (1011, b'Grace Kim'.ljust(30),      4700.0),
        (1013, b'Henry Wang'.ljust(30),     5800.0),
        (1015, b'Irene Lopez'.ljust(30),    4400.0),
    ]

    h = _make_demo_db(db_file, fmt, rows)

    idx = ExtendibleHash(db_file, fmt, key_index=0)

    # ── build_from_db ─────────────────────────────────────────────────────────
    n = idx.build_from_db(h)
    print(f"build_from_db: {n} entradas indexadas")
    print(f"stats: {idx.stats()}\n")

    # ── search (encontrado) ───────────────────────────────────────────────────
    offsets = idx.search(1005)
    print(f"search(1005): {len(offsets)} resultado(s)")
    for off in offsets:
        eid, name_b, salary = idx.read_record(off)
        print(f"  id={eid} nombre={name_b.decode().strip()!r} salario={salary:.2f}")

    # ── search (no encontrado) ────────────────────────────────────────────────
    offsets = idx.search(9999)
    print(f"\nsearch(9999): {offsets}  ← esperado []")

    # ── insert (nuevo registro en DB + índice) ────────────────────────────────
    print()
    with open(db_file, 'r+b') as f:
        f.seek(0, 2)
        new_off = f.tell()
        f.write(struct.pack('= i 30s f', 1017, b'Jorge Paz'.ljust(30), 5100.0))
    idx.insert(1017, new_off)
    offsets = idx.search(1017)
    print(f"insert(1017) + search: {len(offsets)} resultado(s)")
    for off in offsets:
        eid, name_b, salary = idx.read_record(off)
        print(f"  id={eid} nombre={name_b.decode().strip()!r}")

    # ── insert múltiple para forzar split ─────────────────────────────────────
    print()
    extra = [(2001, b'Split Test 1'.ljust(30), 1.0),
             (2002, b'Split Test 2'.ljust(30), 2.0),
             (2003, b'Split Test 3'.ljust(30), 3.0),
             (2004, b'Split Test 4'.ljust(30), 4.0),
             (2005, b'Split Test 5'.ljust(30), 5.0)]
    with open(db_file, 'r+b') as f:
        f.seek(0, 2)
        for eid, name_b, sal in extra:
            off = f.tell()
            f.write(struct.pack('= i 30s f', eid, name_b, sal))
            idx.insert(eid, off)
    print(f"Tras 5 inserts extra: {idx.stats()}")

    # ── delete (en bucket primario) ───────────────────────────────────────────
    print()
    ok = idx.delete(1003)
    print(f"delete(1003): {'OK' if ok else 'NO ENCONTRADO'}")
    print(f"search(1003) tras delete: {idx.search(1003)}  ← esperado []")

    # ── delete (no existe) ────────────────────────────────────────────────────
    ok = idx.delete(9999)
    print(f"delete(9999): {'OK' if ok else 'NO ENCONTRADO'}  ← esperado NO ENCONTRADO")

    # ── delete + re-insert ────────────────────────────────────────────────────
    print()
    ok = idx.delete(1007)
    print(f"delete(1007): {'OK' if ok else 'NO ENCONTRADO'}")
    with open(db_file, 'r+b') as f:
        f.seek(0, 2)
        reins_off = f.tell()
        f.write(struct.pack('= i 30s f', 1007, b'Elena Voss BACK'.ljust(30), 4900.0))
    idx.insert(1007, reins_off)
    offsets = idx.search(1007)
    print(f"re-insert(1007) + search: {len(offsets)} resultado(s)")
    for off in offsets:
        eid, name_b, salary = idx.read_record(off)
        print(f"  id={eid} nombre={name_b.decode().strip()!r} salario={salary:.2f}")

    print(f"\nstats final: {idx.stats()}")

    idx.close()
    print("\nTest completado.")


test_extendible_hash()
