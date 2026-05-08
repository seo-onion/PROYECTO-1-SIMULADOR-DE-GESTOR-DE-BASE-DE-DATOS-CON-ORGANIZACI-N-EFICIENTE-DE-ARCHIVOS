import os
import struct
from typing import Any, List, Tuple

MAX_DEPTH  = 8        # profundidad máxima global → 256 entradas en directorio
BUCKET_CAP = 4        # entradas por bucket

_HDR_FMT       = '= i i i'
_HDR_SIZE      = struct.calcsize(_HDR_FMT)          # 12 bytes
_DIR_ENTRIES   = 1 << MAX_DEPTH                      # 256
_DIR_SIZE      = _DIR_ENTRIES * 4                    # 1024 bytes
_BUCKETS_START = _HDR_SIZE + _DIR_SIZE               # 1036 bytes

_BUCKET_META_FMT  = '= i i i i'
_BUCKET_META_SIZE = struct.calcsize(_BUCKET_META_FMT)  # 16 bytes


class ExtendibleHash:
    """Índice de hashing extensible con overflow y splitting."""

    def __init__(self, db_filename: str, table_format: str, key_index: int):
        """
        db_filename  : ruta al archivo principal de BD.
        table_format : formato struct del registro con espacios. Ej: "i 10s f"
        key_index    : índice (0-based) del atributo clave.
        """
        self.db_filename  = db_filename
        self.table_format = table_format
        self.key_index    = key_index

        fmt_parts        = table_format.split()
        self.full_fmt    = '= ' + ' '.join(fmt_parts)
        self.key_token   = fmt_parts[key_index]
        self.is_str_key  = 's' in self.key_token
        if self.is_str_key:
            self.key_str_len = int(self.key_token.replace('s', ''))

        self.db_rec_size  = struct.calcsize(self.full_fmt)
        self._entry_fmt   = '= ' + self.key_token + ' i ?'
        self._entry_size  = struct.calcsize(self._entry_fmt)
        self._bucket_size = _BUCKET_META_SIZE + BUCKET_CAP * self._entry_size

        self.index_filename = db_filename + 'hash_index' + str(key_index) + '.bin'

        if not os.path.exists(self.index_filename):
            self._initialize()
        self.file = open(self.index_filename, 'r+b')

    # ── Inicialización ────────────────────────────────────────────────────────

    def _initialize(self):
        """Crea el archivo con D=1 y dos buckets vacíos."""
        b0 = _BUCKETS_START
        b1 = _BUCKETS_START + self._bucket_size
        with open(self.index_filename, 'wb') as f:
            # Header: depth=1, num_buckets=2, free_head=-1
            f.write(struct.pack(_HDR_FMT, 1, 2, -1))
            # Directorio: entradas 0..127 → b0, entradas 128..255 → b1
            dir_data = [b0 if i < 128 else b1 for i in range(_DIR_ENTRIES)]
            f.write(struct.pack('= ' + 'i' * _DIR_ENTRIES, *dir_data))
            # Bucket 0: local_depth=1, fullness=0, overflow=-1, next_free=-1
            f.write(struct.pack(_BUCKET_META_FMT, 1, 0, -1, -1))
            f.write(b'\x00' * (BUCKET_CAP * self._entry_size))
            # Bucket 1: idem
            f.write(struct.pack(_BUCKET_META_FMT, 1, 0, -1, -1))
            f.write(b'\x00' * (BUCKET_CAP * self._entry_size))

    # ── Header ────────────────────────────────────────────────────────────────

    def _read_header(self) -> Tuple[int, int, int]:
        self.file.seek(0)
        return struct.unpack(_HDR_FMT, self.file.read(_HDR_SIZE))

    def _write_header(self, depth: int, num_buckets: int, free_head: int):
        self.file.seek(0)
        self.file.write(struct.pack(_HDR_FMT, depth, num_buckets, free_head))

    # ── Directorio ────────────────────────────────────────────────────────────

    def _read_dir(self, idx: int) -> int:
        self.file.seek(_HDR_SIZE + idx * 4)
        return struct.unpack('= i', self.file.read(4))[0]

    def _write_dir(self, idx: int, bucket_off: int):
        self.file.seek(_HDR_SIZE + idx * 4)
        self.file.write(struct.pack('= i', bucket_off))

    # ── Bucket meta ───────────────────────────────────────────────────────────

    def _read_meta(self, off: int) -> Tuple[int, int, int, int]:
        """Devuelve (local_depth, fullness, overflow_ptr, next_free)."""
        self.file.seek(off)
        return struct.unpack(_BUCKET_META_FMT, self.file.read(_BUCKET_META_SIZE))

    def _write_meta(self, off: int, ld: int, full: int, ovf: int, nf: int):
        self.file.seek(off)
        self.file.write(struct.pack(_BUCKET_META_FMT, ld, full, ovf, nf))

    # ── Entries ───────────────────────────────────────────────────────────────

    def _entry_off(self, bucket_off: int, slot: int) -> int:
        return bucket_off + _BUCKET_META_SIZE + slot * self._entry_size

    def _read_entry(self, bucket_off: int, slot: int) -> Tuple[Any, int, bool]:
        self.file.seek(self._entry_off(bucket_off, slot))
        raw_key, db_off, valid = struct.unpack(self._entry_fmt,
                                                self.file.read(self._entry_size))
        return self._decode_key(raw_key), db_off, bool(valid)

    def _write_entry(self, bucket_off: int, slot: int,
                     key, db_off: int, valid: bool):
        self.file.seek(self._entry_off(bucket_off, slot))
        self.file.write(struct.pack(self._entry_fmt,
                                    self._encode_key(key), db_off, valid))

    def _free_slot(self, bucket_off: int) -> int:
        """Primer slot inválido, o -1 si el bucket está lleno."""
        for s in range(BUCKET_CAP):
            _, _, valid = self._read_entry(bucket_off, s)
            if not valid:
                return s
        return -1

    def _live_entries(self, bucket_off: int) -> List[Tuple[Any, int, int]]:
        """Lista de (key, db_off, slot) de entradas válidas."""
        result = []
        for s in range(BUCKET_CAP):
            k, off, valid = self._read_entry(bucket_off, s)
            if valid:
                result.append((k, off, s))
        return result

    # ── Serialización de claves ───────────────────────────────────────────────

    def _encode_key(self, key) -> Any:
        if self.is_str_key:
            if isinstance(key, str):
                return key[:self.key_str_len].ljust(self.key_str_len).encode('utf-8')
            return key
        return key

    def _decode_key(self, raw) -> Any:
        if self.is_str_key and isinstance(raw, bytes):
            return raw.decode('utf-8').strip()
        return raw

    # ── Hash determinista ─────────────────────────────────────────────────────

    def _hash(self, key) -> int:
        key = self._decode_key(key)
        if self.is_str_key:
            h = 0
            for c in str(key):
                h = (h * 31 + ord(c)) & 0x7FFFFFFF
            return h
        if isinstance(key, float):
            return struct.unpack('= I', struct.pack('= f', key))[0] & 0x7FFFFFFF
        return abs(int(key)) & 0x7FFFFFFF

    def _idx(self, key, depth: int) -> int:
        """Índice de directorio: los D bits bajos del hash."""
        return self._hash(key) % (1 << depth)

    # ── Gestión de buckets libres ─────────────────────────────────────────────

    def _alloc_bucket(self, local_depth: int) -> int:
        """Devuelve offset de un bucket limpio (reutilizado o nuevo)."""
        depth, num_buckets, free_head = self._read_header()
        if free_head != -1:
            off = free_head
            _, _, _, nf = self._read_meta(off)
            self._write_meta(off, local_depth, 0, -1, -1)
            self.file.seek(off + _BUCKET_META_SIZE)
            self.file.write(b'\x00' * (BUCKET_CAP * self._entry_size))
            self._write_header(depth, num_buckets, nf)
            return off
        # Adjuntar al final
        self.file.seek(0, 2)
        off = self.file.tell()
        self.file.write(struct.pack(_BUCKET_META_FMT, local_depth, 0, -1, -1))
        self.file.write(b'\x00' * (BUCKET_CAP * self._entry_size))
        self._write_header(depth, num_buckets + 1, free_head)
        return off

    def _release_bucket(self, off: int):
        """Devuelve bucket a la lista libre."""
        depth, num_buckets, free_head = self._read_header()
        ld, _, _, _ = self._read_meta(off)
        self._write_meta(off, ld, 0, -1, free_head)
        self._write_header(depth, num_buckets, off)

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    def search(self, key) -> List[int]:
        """Devuelve lista de db_offsets para la clave dada. O(1) esperado."""
        key   = self._decode_key(key)
        depth, _, _ = self._read_header()

        # h ← hash(k); idx ← h mod 2^D; bucket ← directorio[idx]
        bucket  = self._read_dir(self._idx(key, depth))
        results = []

        # Buscar en bucket primario
        for s in range(BUCKET_CAP):
            k, off, valid = self._read_entry(bucket, s)
            if valid and k == key:
                results.append(off)

        # Buscar en overflow si existe
        _, _, overflow, _ = self._read_meta(bucket)
        if overflow != -1:
            for s in range(BUCKET_CAP):
                k, off, valid = self._read_entry(overflow, s)
                if valid and k == key:
                    results.append(off)

        return results

    # ── Inserción ─────────────────────────────────────────────────────────────

    def insert(self, key, db_offset: int):
        """Inserta (clave, db_offset) en el índice."""
        key = self._decode_key(key)
        self._insert_rec(key, db_offset, 0)
        self.file.flush()

    def _insert_rec(self, key, db_offset: int, depth_guard: int):
        if depth_guard > MAX_DEPTH + 2:
            raise RuntimeError(f"insert: demasiadas divisiones para clave {key!r}")

        depth, num_buckets, free_head = self._read_header()
        idx       = self._idx(key, depth)
        bucket    = self._read_dir(idx)
        ld, full, overflow, nf = self._read_meta(bucket)

        # Caso 1: bucket primario tiene espacio
        slot = self._free_slot(bucket)
        if slot != -1:
            self._write_entry(bucket, slot, key, db_offset, True)
            self._write_meta(bucket, ld, full + 1, overflow, nf)
            return

        # Caso 2: overflow existe y tiene espacio
        if overflow != -1:
            ov_ld, ov_full, ov_ovf, ov_nf = self._read_meta(overflow)
            ov_slot = self._free_slot(overflow)
            if ov_slot != -1:
                self._write_entry(overflow, ov_slot, key, db_offset, True)
                self._write_meta(overflow, ov_ld, ov_full + 1, ov_ovf, ov_nf)
                return

        # Caso 3: necesita dividir
        if ld < depth:
            self._split(idx, bucket, ld, depth)
        elif depth < MAX_DEPTH:
            self._double_dir()
            depth, _, _ = self._read_header()
            new_idx = self._idx(key, depth)
            new_bkt = self._read_dir(new_idx)
            new_ld, _, _, _ = self._read_meta(new_bkt)
            self._split(new_idx, new_bkt, new_ld, depth)
        else:
            # MAX_DEPTH alcanzado: forzar overflow
            if overflow == -1:
                ov = self._alloc_bucket(ld)
                self._write_meta(bucket, ld, full, ov, nf)
            # Reintentar — la próxima iteración usará el overflow recién creado

        self._insert_rec(key, db_offset, depth_guard + 1)

    def _double_dir(self):
        """Duplica el directorio incrementando D en 1."""
        depth, num_buckets, free_head = self._read_header()
        assert depth < MAX_DEPTH, "No se puede superar MAX_DEPTH"
        old_size = 1 << depth
        # Entrada i del directorio nuevo (i + old_size) copia la entrada i
        for i in range(old_size):
            ptr = self._read_dir(i)
            self._write_dir(i + old_size, ptr)
        self._write_header(depth + 1, num_buckets, free_head)

    def _split(self, idx: int, bucket_off: int, ld: int, depth: int):
        """Divide bucket_off incrementando su profundidad local."""
        new_ld = ld + 1

        # Recolectar todas las entradas (primario + overflow)
        _, _, overflow, _ = self._read_meta(bucket_off)
        entries = [(k, off) for k, off, _ in self._live_entries(bucket_off)]
        if overflow != -1:
            entries += [(k, off) for k, off, _ in self._live_entries(overflow)]
            self._release_bucket(overflow)

        # Bucket hermano nuevo
        sibling_off = self._alloc_bucket(new_ld)

        # Limpiar bucket original
        self._write_meta(bucket_off, new_ld, 0, -1, -1)
        self.file.seek(bucket_off + _BUCKET_META_SIZE)
        self.file.write(b'\x00' * (BUCKET_CAP * self._entry_size))

        # Redirigir entradas del directorio
        # Patrón antiguo: los bajos ld bits de idx
        orig_pat    = idx & ((1 << ld) - 1)
        sibling_pat = orig_pat | (1 << ld)
        mask        = (1 << new_ld) - 1
        dir_size    = 1 << depth

        for i in range(dir_size):
            low = i & mask
            if low == orig_pat:
                self._write_dir(i, bucket_off)
            elif low == sibling_pat:
                self._write_dir(i, sibling_off)

        # Reinsertar entradas redistribuidas
        for k, off in entries:
            dest   = self._read_dir(self._idx(k, depth))
            d_ld, d_full, d_ovf, d_nf = self._read_meta(dest)
            slot   = self._free_slot(dest)
            if slot != -1:
                self._write_entry(dest, slot, k, off, True)
                self._write_meta(dest, d_ld, d_full + 1, d_ovf, d_nf)
            else:
                # Edge case: colisión total de hash → overflow temporal
                if d_ovf == -1:
                    ov = self._alloc_bucket(d_ld)
                    self._write_meta(dest, d_ld, d_full, ov, d_nf)
                    d_ovf = ov
                ov_ld, ov_full, ov_ovf, ov_nf = self._read_meta(d_ovf)
                ov_slot = self._free_slot(d_ovf)
                if ov_slot != -1:
                    self._write_entry(d_ovf, ov_slot, k, off, True)
                    self._write_meta(d_ovf, ov_ld, ov_full + 1, ov_ovf, ov_nf)

    # ── Eliminación ───────────────────────────────────────────────────────────

    def delete(self, key) -> bool:
        """Elimina la entrada con la clave dada. Devuelve True si existía."""
        key   = self._decode_key(key)
        depth, _, _ = self._read_header()

        # h ← hash(k); idx ← h mod 2^D; bucket ← directorio[idx]
        idx    = self._idx(key, depth)
        bucket = self._read_dir(idx)
        ld, full, overflow, nf = self._read_meta(bucket)

        # ── Buscar en bucket primario ─────────────────────────────────────────
        for s in range(BUCKET_CAP):
            k, off, valid = self._read_entry(bucket, s)
            if valid and k == key:
                # Eliminar registro del bucket
                self._write_entry(bucket, s, k, off, False)
                full -= 1

                if overflow != -1:
                    ov_ld, ov_full, ov_ovf, ov_nf = self._read_meta(overflow)
                    ov_entries = self._live_entries(overflow)
                    if ov_entries:
                        # Extraer un registro de overflow e insertarlo en bucket
                        mk, moff, ms = ov_entries[0]
                        self._write_entry(overflow, ms, mk, moff, False)
                        ov_full -= 1
                        self._write_entry(bucket, s, mk, moff, True)
                        full += 1
                        self._write_meta(overflow, ov_ld, ov_full, ov_ovf, ov_nf)

                    if ov_full == 0:
                        self._release_bucket(overflow)
                        overflow = -1

                self._write_meta(bucket, ld, full, overflow, nf)
                self.file.flush()
                return True

        # ── Buscar en overflow si existe ──────────────────────────────────────
        if overflow != -1:
            ov_ld, ov_full, ov_ovf, ov_nf = self._read_meta(overflow)
            for s in range(BUCKET_CAP):
                k, off, valid = self._read_entry(overflow, s)
                if valid and k == key:
                    self._write_entry(overflow, s, k, off, False)
                    ov_full -= 1
                    if ov_full == 0:
                        self._release_bucket(overflow)
                        self._write_meta(bucket, ld, full, -1, nf)
                    else:
                        self._write_meta(overflow, ov_ld, ov_full, ov_ovf, ov_nf)
                    self.file.flush()
                    return True

        return False

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
        count = 0
        with open(self.db_filename, 'rb') as f:
            f.seek(header_size)
            for _ in range(reg_number):
                db_off = f.tell()
                raw    = f.read(disk_rec_size)
                if len(raw) < disk_rec_size:
                    break
                deleted = struct.unpack('?', raw[-1:])[0]
                if deleted:
                    continue
                record = struct.unpack(self.full_fmt, raw[:-1])
                key    = self._decode_key(record[self.key_index])
                self.insert(key, db_off)
                count += 1
        return count

    # ── Acceso al registro completo ───────────────────────────────────────────

    def read_record(self, db_offset: int) -> tuple:
        """Lee el registro completo del archivo DB en la posición dada."""
        with open(self.db_filename, 'rb') as f:
            f.seek(db_offset)
            return struct.unpack(self.full_fmt, f.read(self.db_rec_size))

    # ── Utilidades ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        depth, num_buckets, free_head = self._read_header()
        return {
            'index_file':   self.index_filename,
            'global_depth': depth,
            'num_buckets':  num_buckets,
            'bucket_cap':   BUCKET_CAP,
            'entry_size_b': self._entry_size,
            'bucket_size_b': self._bucket_size,
            'key_token':    self.key_token,
        }

    def close(self):
        self.file.flush()
        self.file.close()
