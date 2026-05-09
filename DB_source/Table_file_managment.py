import os
import struct

try:
	from .page_manager import PageManager, create_empty_file
except ImportError:
	from page_manager import PageManager, create_empty_file

create = "w+b"
edit = "rb+"


class Header_dto:
	"""Representa el header fisico de una tabla binaria."""

	def __init__(self, data: tuple[int, int, int, int, str, int, str]):
		self.header_size = data[0]
		self.reg_number = data[1]
		self.reg_size = data[2]
		self.format_str_size = data[3]
		self.format = data[4]
		self.att_number = data[5]
		self.indexes = data[6]

	def print(self):
		print("tamanho del header en bytes: ", self.header_size)
		print("Numero de regsitros: ", self.reg_number)
		print("tamanho en bytes de cada registro: ", self.reg_size)
		print("tamanho del string de formato: ", self.format_str_size)
		print("formato del registro: ", self.format)
		print("numero de atributos: ", self.att_number)
		print("indeces de los atributos ", list(self.indexes))


def __header_str_format(format: str):
	"""Construye el formato struct usado para serializar el header."""
	return "i " * 4 + str(len(format)) + "s " + "i " + str(len(format.split(" "))) + "s"


def __encode_header(h: tuple[int, int, int, int, str, int, str]) -> tuple[int, int, int, int, bytes, int, bytes]:
	"""Convierte strings del header a bytes para struct.pack."""
	return h[0], h[1], h[2], h[3], h[4].encode(), h[5], h[6].encode()


def __init_header(format: str) -> tuple[int, int, int, int, str, int, str]:
	"""Crea el header inicial para una tabla vacia."""
	reg_number = 0
	reg_size = struct.calcsize("= " + format) + 1
	format_str_size = len(format)
	att_number = len(format.split(" "))
	indexes = str("N" * att_number)
	header_size = 4 + 4 + 4 + 4 + format_str_size + 4 + att_number
	return header_size, reg_number, reg_size, format_str_size, format, att_number, indexes


def __write_header(file_name: str, header: tuple[int, int, int, int, str, int, str]):
	"""Escribe el header en la pagina inicial del archivo de tabla."""
	reg_format = header[4]
	data = struct.pack("= " + __header_str_format(reg_format), *__encode_header(header))
	PageManager(file_name).write_at(0, data)


def __read_header(file_name: str) -> tuple[int, int, int, int, str, int, str]:
	"""Lee y deserializa el header desde el archivo de tabla."""
	pager = PageManager(file_name)
	cursor = 0

	header_size = struct.unpack("i", pager.read_at(cursor, 4))[0]
	cursor += 4
	reg_number = struct.unpack("i", pager.read_at(cursor, 4))[0]
	cursor += 4
	reg_size = struct.unpack("i", pager.read_at(cursor, 4))[0]
	cursor += 4
	format_str_size = struct.unpack("i", pager.read_at(cursor, 4))[0]
	cursor += 4
	format = struct.unpack(str(format_str_size) + "s", pager.read_at(cursor, format_str_size))[0].decode("utf-8")
	cursor += format_str_size
	att_number = struct.unpack("i", pager.read_at(cursor, 4))[0]
	cursor += 4
	indexes = struct.unpack(str(att_number) + "s", pager.read_at(cursor, att_number))[0].decode("utf-8")
	return header_size, reg_number, reg_size, format_str_size, format, att_number, indexes


def insert_record(file_name: str, record: tuple) -> int:
	"""Agrega un registro y devuelve su db_offset fisico."""
	h = Header_dto(__read_header(file_name))
	rec_fmt = "= " + h.format + " ?"
	db_offset = h.header_size + h.reg_number * h.reg_size
	PageManager(file_name).write_at(db_offset, struct.pack(rec_fmt, *record, False))
	raw = list(__read_header(file_name))
	raw[1] += 1
	__write_header(file_name, tuple(raw))
	return db_offset


def delete_record(file_name: str, db_offset: int) -> bool:
	"""Marca un registro como eliminado usando su byte tombstone."""
	h = Header_dto(__read_header(file_name))
	tombstone_pos = db_offset + h.reg_size - 1
	pager = PageManager(file_name)
	already_deleted = struct.unpack("?", pager.read_at(tombstone_pos, 1))[0]
	if already_deleted:
		return False
	pager.write_at(tombstone_pos, struct.pack("?", True))
	return True


def read_db_header(file_name: str) -> Header_dto:
	"""Devuelve el header como DTO para el engine y los indices."""
	return Header_dto(__read_header(file_name))


def read_record_at(file_name: str, db_offset: int):
	"""Lee un registro fisico por offset.

	Retorna `(record, deleted)`, donde `record` excluye el tombstone.
	"""
	h = Header_dto(__read_header(file_name))
	rec_fmt = "= " + h.format + " ?"
	raw = PageManager(file_name).read_at(db_offset, h.reg_size)
	if len(raw) < h.reg_size:
		raise ValueError("Offset fuera del archivo o registro incompleto")
	data = struct.unpack(rec_fmt, raw)
	return data[:-1], bool(data[-1])


def iter_records(file_name: str):
	"""Itera registros fisicos sin cargar todo el archivo DB en memoria."""
	h = Header_dto(__read_header(file_name))
	rec_fmt = "= " + h.format + " ?"
	pager = PageManager(file_name)
	db_offset = h.header_size
	for _ in range(h.reg_number):
		raw = pager.read_at(db_offset, h.reg_size)
		if len(raw) < h.reg_size:
			break
		data = struct.unpack(rec_fmt, raw)
		yield db_offset, data[:-1], bool(data[-1])
		db_offset += h.reg_size


def update_index_flags(file_name: str, indexes: str):
	"""Actualiza los flags de indices guardados en el header."""
	h = list(__read_header(file_name))
	if len(indexes) != h[5]:
		raise ValueError("La cantidad de flags no coincide con el numero de atributos")
	h[6] = indexes
	__write_header(file_name, tuple(h))


def init_main_db(file_name: str, format: str, verbose: bool = False):
	"""Inicializa el archivo fisico de una tabla vacia."""
	if os.path.exists(file_name):
		raise Exception("no se puede inicializar un file que ya existe")

	header = __init_header(format)
	create_empty_file(file_name)
	__write_header(file_name, header)

	if verbose:
		Header_dto(__read_header(file_name)).print()
