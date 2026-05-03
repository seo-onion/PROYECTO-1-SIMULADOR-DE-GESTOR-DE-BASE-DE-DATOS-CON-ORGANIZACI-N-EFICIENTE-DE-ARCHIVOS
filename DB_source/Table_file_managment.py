import struct
import os

create='w+b'
edit="rb+"

class Header_dto:  # esto es lo que hay que pasarle a caada estructura de datos ya que
	# Solo este archivo debe poder editar su propio header lo hice una clase porque pensaba
	# que le podemos poner funciones para abstraer algunas cosas como ver los indices y cosas asi
	def __init__(self,data:tuple[int,int,int,int,str,int,str]):

		self.header_size=data[0]
		self.reg_number=data[1]
		self.reg_size=data[2]
		self.format_str_size=data[3]
		self.format=data[4]
		self.att_number=data[5]
		self.indexes=data[6]

	def print(self):
		print("tamanho del header en bytes: ",self.header_size)
		print("Numero de regsitros: " ,self.reg_number)
		print("tamanho en bytes de cada registro: ",self.reg_size)
		print("tamanho del string de formato: ",self.format_str_size)
		print("formato del registro: ",self.format)
		print("numero de atributos: ",self.att_number)
		print("indeces de los atributos ",list(self.indexes))

def __header_str_format(format:str):
	return 'i '*4+str(len(format))+'s '+'i '+str(len(format.split(' ')))+'s'


def __encode_header(h:tuple[int,int,int,int,str,int,str])->tuple[int,int,int,int,bytes,int,bytes]:
	return h[0],h[1],h[2],h[3],h[4].encode(),h[5],h[6].encode()


def __init_header(format:str)->tuple[int,int,int,int,str,int,str]:
	reg_number = 0
	reg_size = struct.calcsize(format)
	format_str_size = len(format)
	att_number = len(format.split(' '))
	indexes = str('N' * att_number ) # le puse N de nada pero hay que ponernos de acuerdo para que haya un caracter por cada estructura de datos
	header_size = 4 + 4 + 4 + 4 + format_str_size + 4 + att_number
	return header_size, reg_number, reg_size, format_str_size, format, att_number, indexes

def __write_header(file_name:str,header:tuple[int,int,int,int,str,int,str]):
	reg_format=header[4]
	with open(file_name,edit) as f:
		f.seek(0)
		f.write(struct.pack('= ' +__header_str_format(reg_format),*__encode_header(header)))

def __read_header(file_name:str)->tuple[int,int,int,int,str,int,str]:

	header:tuple[int,int,int,int,str,int,str]
	with open(file_name,edit) as f:
		f.seek(0)
		header_size=struct.unpack('i',f.read(4))[0]
		reg_number=struct.unpack('i',f.read(4))[0]
		reg_size =struct.unpack('i',f.read(4))[0]
		format_str_size = struct.unpack('i',f.read(4))[0]
		format = struct.unpack(str(format_str_size)+'s',f.read(format_str_size))[0].decode('utf-8')
		att_number = struct.unpack('i',f.read(4))[0]
		indexes = struct.unpack(str(att_number)+'s',f.read(att_number))[0].decode('utf-8')
		header=(header_size, reg_number, reg_size, format_str_size, format, att_number, indexes)
	return header

def init_main_db(file_name:str,format:str):
	if os.path.exists(file_name):
		raise Exception("no se puede inicializar un file que ya existe")

	header=__init_header(format)
	with open(file_name,create) as f:
		f.write(struct.pack('= ' +__header_str_format(format),*__encode_header(header)))

	Header_dto(__read_header(file_name)).print()

