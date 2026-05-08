import os
import struct
from typing import Any, List, Tuple


class SequentialIndex:
    """Índice de archivo secuencial con búsqueda binaria y área auxiliar.

    Interfaz idéntica a BPlusTree en construcción:
        SequentialIndex(db_filename, table_format, key_index)
    """

    HEADER_FORMAT = '= i i'
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, db_filename: str, table_format: str, key_index: int,
                 k_threshold: int = 100):
        """
        db_filename  : ruta al archivo principal de BD.
        table_format : formato struct del registro con espacios entre tokens.
                       Ej.: "i 10s f 15s"  →  struct '=i10sf15s'
        key_index    : índice (0-based) del atributo clave en table_format.
        k_threshold  : entradas máximas en el área auxiliar antes de rebuild.
        """
        self.db_filename  = db_filename
        self.table_format = table_format
        self.key_index    = key_index
        self.k_threshold  = k_threshold

        fmt_parts = table_format.split()
        self.full_fmt   = '= ' + ' '.join(fmt_parts)
        self.key_token  = fmt_parts[key_index]     # ej. 'i', '10s', 'f'
        self.is_str_key = 's' in self.key_token
        if self.is_str_key:
            self.key_str_len = int(self.key_token.replace('s', ''))

        self.entry_fmt  = '= ' + self.key_token + ' i ?'
        self.entry_size = struct.calcsize(self.entry_fmt)
        self.db_rec_size = struct.calcsize(self.full_fmt)

        self.index_filename = db_filename + 'seq_index' + str(key_index) + '.bin'

        if not os.path.exists(self.index_filename):
            with open(self.index_filename, 'wb') as f:
                f.write(struct.pack(self.HEADER_FORMAT, 0, 0))

        self.file = open(self.index_filename, 'r+b')

    # ── Cabecera ─────────────────────────────────────────────────────────────

    def _read_header(self) -> Tuple[int, int]:
        self.file.seek(0)
        return struct.unpack(self.HEADER_FORMAT, self.file.read(self.HEADER_SIZE))

    def _write_header(self, ordered: int, aux: int) -> None:
        self.file.seek(0)
        self.file.write(struct.pack(self.HEADER_FORMAT, ordered, aux))

    # ── Serialización de claves ───────────────────────────────────────────────

    def _encode_key(self, key) -> Any:
        if self.is_str_key:
            if isinstance(key, str):
                return key[:self.key_str_len].ljust(self.key_str_len).encode('utf-8')
            return key
        return key

    def _decode_key(self, raw) -> Any:
        """Convierte bytes a str (para claves string) o devuelve el valor sin cambios."""
        if self.is_str_key and isinstance(raw, bytes):
            return raw.decode('utf-8').strip()
        return raw

    # ── Empaquetado de entradas ───────────────────────────────────────────────

    def _pack(self, key, offset: int, deleted: bool = False) -> bytes:
        return struct.pack(self.entry_fmt, self._encode_key(key), offset, deleted)

    def _unpack(self, data: bytes) -> Tuple[Any, int, bool]:
        raw, offset, deleted = struct.unpack(self.entry_fmt, data)
        return self._decode_key(raw), offset, bool(deleted)

    # ── Acceso posicional ─────────────────────────────────────────────────────

    def _seek(self, idx: int) -> None:
        self.file.seek(self.HEADER_SIZE + idx * self.entry_size)

    def _read_at(self, idx: int) -> Tuple[Any, int, bool]:
        self._seek(idx)
        return self._unpack(self.file.read(self.entry_size))

    def _write_at(self, idx: int, key, offset: int, deleted: bool = False) -> None:
        self._seek(idx)
        self.file.write(self._pack(key, offset, deleted))

    # ── Búsqueda binaria base ─────────────────────────────────────────────────

    def _leftmost_ge(self, key, ordered: int) -> int:
        """Posición del primer elemento ≥ key en la sección ordenada. O(log n).

        Invariante del loop:
          - todo índice < lo  tiene clave < key
          - todo índice > hi  tiene clave ≥ key  (candidato a `result`)
        Al terminar, `result` es la posición más pequeña con clave ≥ key,
        o `ordered` si todos los elementos son estrictamente menores.
        """
        lo, hi = 0, ordered - 1
        result = ordered
        while lo <= hi:
            mid = (lo + hi) // 2
            k, _, _ = self._read_at(mid)
            if k >= key:
                result = mid
                hi = mid - 1   # podría haber uno igual o mayor más a la izquierda
            else:
                lo = mid + 1
        return result

    # ── Búsqueda puntual ──────────────────────────────────────────────────────

    def search(self, key) -> List[int]:
        """Devuelve lista de offsets en el archivo DB para la clave dada.
        Complejidad: O(log n) sección ordenada + O(k) área auxiliar.
        """
        key = self._decode_key(key)
        ordered, aux = self._read_header()
        results: List[int] = []

        # Búsqueda binaria en la sección ordenada
        lo, hi = 0, ordered - 1
        found = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            k, _, _ = self._read_at(mid)
            if k == key:
                found = mid
                break
            elif k < key:
                lo = mid + 1
            else:
                hi = mid - 1

        if found >= 0:
            for j in range(found, -1, -1):       # expandir hacia la izquierda
                k, off, del_ = self._read_at(j)
                if k != key:
                    break
                if not del_:
                    results.append(off)
            for j in range(found + 1, ordered):  # expandir hacia la derecha
                k, off, del_ = self._read_at(j)
                if k != key:
                    break
                if not del_:
                    results.append(off)

        # Escaneo lineal en área auxiliar (k ≤ k_threshold)
        for i in range(ordered, ordered + aux):
            k, off, del_ = self._read_at(i)
            if k == key and not del_:
                results.append(off)

        return results

    # ── Búsqueda por rango ────────────────────────────────────────────────────

    def range_search(self, min_key, max_key) -> List[int]:
        """Devuelve offsets en el archivo DB para claves en [min_key, max_key].

        Complejidad: O(log n + m)
          Paso 1 – _leftmost_ge localiza la primera posición ≥ min_key : O(log n)
          Paso 2 – escaneo lineal hasta superar max_key                 : O(m₁)
          Paso 3 – escaneo del área auxiliar, acotado por k_threshold   : O(k)
          Total  : O(log n + m₁ + k) = O(log n + m)
        """
        min_key = self._decode_key(min_key)
        max_key = self._decode_key(max_key)
        if min_key > max_key:
            min_key, max_key = max_key, min_key

        ordered, aux = self._read_header()
        results: List[int] = []

        # Paso 1: hallar inicio con búsqueda binaria → O(log n)
        start = self._leftmost_ge(min_key, ordered)

        # Paso 2: escaneo lineal desde start hasta > max_key → O(m₁)
        for i in range(start, ordered):
            k, off, del_ = self._read_at(i)
            if k > max_key:
                break
            if not del_:
                results.append(off)

        # Paso 3: escaneo del área auxiliar → O(k) ≤ O(k_threshold)
        for i in range(ordered, ordered + aux):
            k, off, del_ = self._read_at(i)
            if min_key <= k <= max_key and not del_:
                results.append(off)

        return results

    # ── Inserción ─────────────────────────────────────────────────────────────

    def insert(self, key, db_offset: int) -> None:
        """Inserta (clave, offset_db) en el área auxiliar.
        Dispara _rebuild() automáticamente si aux_count supera k_threshold.
        """
        key = self._decode_key(key)
        ordered, aux = self._read_header()
        self._seek(ordered + aux)
        self.file.write(self._pack(key, db_offset))
        aux += 1
        self._write_header(ordered, aux)
        self.file.flush()
        if aux > self.k_threshold:
            self._rebuild()

    # ── Eliminación ───────────────────────────────────────────────────────────

    def delete(self, key) -> bool:
        """Marca la primera coincidencia como eliminada (tombstone).
        Devuelve True si encontró y marcó la entrada.
        """
        key = self._decode_key(key)
        ordered, aux = self._read_header()

        # Búsqueda binaria en sección ordenada
        lo, hi = 0, ordered - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            k, off, del_ = self._read_at(mid)
            if k == key:
                if del_:
                    return False
                self._write_at(mid, k, off, deleted=True)
                self.file.flush()
                return True
            elif k < key:
                lo = mid + 1
            else:
                hi = mid - 1

        # Escaneo lineal en área auxiliar
        for i in range(ordered, ordered + aux):
            k, off, del_ = self._read_at(i)
            if k == key and not del_:
                self._write_at(i, k, off, deleted=True)
                self.file.flush()
                return True

        return False

    # ── Reconstrucción ────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        """Mezcla sección ordenada + auxiliar, descarta tombstones, reescribe ordenado.
        Complejidad: O((n + k) log(n + k)).
        """
        ordered, aux = self._read_header()

        live = []
        for i in range(ordered + aux):
            k, off, del_ = self._read_at(i)
            if not del_:
                live.append((k, off))

        live.sort(key=lambda x: x[0])

        self.file.seek(self.HEADER_SIZE)
        for k, off in live:
            self.file.write(self._pack(k, off))

        self.file.truncate(self.HEADER_SIZE + len(live) * self.entry_size)
        self._write_header(len(live), 0)
        self.file.flush()

    # ── Construcción desde archivo DB ─────────────────────────────────────────

    def build_from_db(self, header) -> int:
        """Construye el índice completo leyendo el archivo DB.

        Recibe el Header_dto devuelto por read_db_header() de Table_file_managment:
            from DB_source.Table_file_managment import read_db_header
            idx.build_from_db(read_db_header("tabla.bin"))

        Retorna el número de entradas indexadas.
        """
        header_size   = header.header_size
        reg_number    = header.reg_number
        disk_rec_size = header.reg_size   # incluye el byte de tombstone
        live = []
        with open(self.db_filename, 'rb') as f:
            f.seek(header_size)
            for _ in range(reg_number):
                db_offset = f.tell()
                raw = f.read(disk_rec_size)
                if len(raw) < disk_rec_size:
                    break
                deleted = struct.unpack('?', raw[-1:])[0]
                if deleted:
                    continue
                record = struct.unpack(self.full_fmt, raw[:-1])
                key = self._decode_key(record[self.key_index])
                live.append((key, db_offset))

        live.sort(key=lambda x: x[0])

        self.file.seek(self.HEADER_SIZE)
        for k, off in live:
            self.file.write(self._pack(k, off))

        self.file.truncate(self.HEADER_SIZE + len(live) * self.entry_size)
        self._write_header(len(live), 0)
        self.file.flush()

        return len(live)

    # ── Acceso al registro completo en DB ─────────────────────────────────────

    def read_record(self, db_offset: int) -> tuple:
        """Lee el registro completo del archivo DB en la posición dada (bytes)."""
        with open(self.db_filename, 'rb') as f:
            f.seek(db_offset)
            raw = f.read(self.db_rec_size)
        return struct.unpack(self.full_fmt, raw)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Número de entradas vivas (no eliminadas)."""
        ordered, aux = self._read_header()
        return sum(1 for i in range(ordered + aux) if not self._read_at(i)[2])

    def stats(self) -> dict:
        ordered, aux = self._read_header()
        return {
            'index_file':    self.index_filename,
            'ordered_count': ordered,
            'aux_count':     aux,
            'k_threshold':   self.k_threshold,
            'entry_size_b':  self.entry_size,
            'key_token':     self.key_token,
        }

    def close(self) -> None:
        self.file.flush()
        self.file.close()
