from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_PAGE_SIZE = 4096


@dataclass
class DiskCounters:
    reads: int = 0
    writes: int = 0


_GLOBAL_COUNTERS = DiskCounters()


def reset_global_counters() -> None:
    _GLOBAL_COUNTERS.reads = 0
    _GLOBAL_COUNTERS.writes = 0


def get_global_counters() -> DiskCounters:
    return DiskCounters(_GLOBAL_COUNTERS.reads, _GLOBAL_COUNTERS.writes)


class PageManager:
    """Envoltorio de E/S por paginas de tamano fijo.

    Los llamadores pueden leer o escribir rangos arbitrarios de bytes, pero esta
    clase realiza el acceso fisico al archivo por paginas y cuenta cada pagina
    tocada.
    """

    def __init__(self, filename: str, page_size: int = DEFAULT_PAGE_SIZE):
        self.filename = filename
        self.page_size = page_size
        self.disk_reads = 0
        self.disk_writes = 0

    def reset_counters(self) -> None:
        self.disk_reads = 0
        self.disk_writes = 0

    def read_page(self, page_id: int) -> bytes:
        if page_id < 0:
            raise ValueError("page_id no puede ser negativo")
        offset = page_id * self.page_size
        with open(self.filename, "rb") as file:
            file.seek(offset)
            data = file.read(self.page_size)
        self._count_read()
        return data.ljust(self.page_size, b"\x00")

    def write_page(self, page_id: int, data: bytes) -> None:
        if page_id < 0:
            raise ValueError("page_id no puede ser negativo")
        if len(data) != self.page_size:
            raise ValueError(f"write_page requiere exactamente {self.page_size} bytes")
        offset = page_id * self.page_size
        with open(self.filename, "r+b") as file:
            file.seek(offset)
            file.write(data)
        self._count_write()

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0:
            raise ValueError("offset y size deben ser no negativos")
        if size == 0:
            return b""

        file_size = os.path.getsize(self.filename)
        if offset >= file_size:
            return b""

        remaining = min(size, file_size - offset)
        cursor = offset
        chunks: list[bytes] = []
        while remaining > 0:
            page_id = cursor // self.page_size
            page_offset = cursor % self.page_size
            page = self.read_page(page_id)
            take = min(remaining, self.page_size - page_offset)
            chunks.append(page[page_offset: page_offset + take])
            cursor += take
            remaining -= take
        return b"".join(chunks)

    def write_at(self, offset: int, data: bytes) -> None:
        if offset < 0:
            raise ValueError("offset debe ser no negativo")
        if not data:
            return

        self._ensure_file_exists()
        cursor = offset
        written = 0
        while written < len(data):
            page_id = cursor // self.page_size
            page_offset = cursor % self.page_size
            take = min(len(data) - written, self.page_size - page_offset)
            if page_offset == 0 and take == self.page_size:
                page = data[written: written + take]
            else:
                page = bytearray(self._read_page_for_write(page_id))
                page[page_offset: page_offset + take] = data[written: written + take]
                page = bytes(page)
            self.write_page(page_id, page)
            cursor += take
            written += take

    def _read_page_for_write(self, page_id: int) -> bytes:
        file_size = os.path.getsize(self.filename)
        page_start = page_id * self.page_size
        if page_start >= file_size:
            return b"\x00" * self.page_size
        return self.read_page(page_id)

    def _ensure_file_exists(self) -> None:
        if not os.path.exists(self.filename):
            with open(self.filename, "wb"):
                pass

    def _count_read(self) -> None:
        self.disk_reads += 1
        _GLOBAL_COUNTERS.reads += 1

    def _count_write(self) -> None:
        self.disk_writes += 1
        _GLOBAL_COUNTERS.writes += 1


def create_empty_file(filename: str) -> None:
    with open(filename, "wb"):
        pass


class PagedFile:
    """Adaptador pequeno de archivo binario respaldado por PageManager.

    Soporta el subconjunto de metodos de archivo que usan los indices.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.pager = PageManager(filename)
        self._offset = 0
        if not os.path.exists(filename):
            create_empty_file(filename)

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._offset = offset
        elif whence == 1:
            self._offset += offset
        elif whence == 2:
            self._offset = os.path.getsize(self.filename) + offset
        else:
            raise ValueError(f"whence no soportado: {whence}")
        if self._offset < 0:
            raise ValueError("offset resultante negativo")
        return self._offset

    def tell(self) -> int:
        return self._offset

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = max(0, os.path.getsize(self.filename) - self._offset)
        data = self.pager.read_at(self._offset, size)
        self._offset += len(data)
        return data

    def write(self, data: bytes) -> int:
        self.pager.write_at(self._offset, data)
        self._offset += len(data)
        return len(data)

    def truncate(self, size: int | None = None) -> int:
        if size is None:
            size = self._offset
        with open(self.filename, "r+b") as file:
            file.truncate(size)
        return size

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None
