import os
import struct

create = 'w+b'
edit = "rb+"
B = 6


# node
#fullness int
#values [b-1]
# B punteros (si es leaf cada puntero apunta al registro asociado con ese valor y el ultimo puntero apunta al siguiente leaf, sino es leaf cada puntero apunta a un hijo)
#isleaf bool
class BTreeNode:
	def __init__(self, fullness: int, values: list, pointers: list[int], is_leaf: bool):
		self.fullness = fullness
		self.values = values
		self.pointers = pointers
		self.is_leaf = is_leaf

	#self.father_ptr=-1

	def print(self):
		print("fullness: ", self.fullness)
		print("values: ", self.values)
		print("pointers: ", self.pointers)
		print("is_leaf: ", self.is_leaf)


class Btree:
	HEADER_SIZE = struct.calcsize('i') * 4

	def __init__(self, filename: str, table_format: str, key_index: int):

		self.db_name = filename
		self.format = table_format
		self.key_index = key_index
		self.key_type = table_format.split(' ')[key_index]
		self.key_size = struct.calcsize("= " + self.key_type)
		self.btree_file_name = filename + "btree" + "_index" + str(key_index) + ".bin"
		self.node_size = 4 + struct.calcsize("= " + self.key_type) * (B - 1) + (4 * B) + 1
		if os.path.exists(self.btree_file_name) and False :
			self.__check_header()
		else:
			self.__initialize_header()
			base_node = BTreeNode(0, [], [-1], True)
			self.__write_node(base_node, self.HEADER_SIZE)
		self.__read_node(self.HEADER_SIZE).print()

	def __check_header(self):
		nodes, k_size, root_ptr = self.__read_header()
		if k_size != self.key_size:
			raise Exception("EL archivo del b+tree tenia una key diferente")

	def __swap(self, offset1: int, offset2: int, size: int):
		with open(self.btree_file_name, edit) as f:
			f.seek(offset1)
			v1: bytes = f.read(size)
			f.seek(offset2)
			v2: bytes = f.read(size)
			f.seek(offset1)
			f.write(v2)
			f.seek(offset2)
			f.write(v1)

	def __write_node(self, node: BTreeNode, address: int):
		with open(self.btree_file_name, edit) as f:
			f.seek(address)
			f.write(struct.pack('= i', node.fullness))
			for i in range(node.fullness):
				f.write(struct.pack('= i', node.pointers[i]))
				if 's' in self.key_type:
					f.write(struct.pack("= " + self.key_type, node.values[i].encode()))
				else:
					f.write(struct.pack("= " + self.key_type, node.values[i]))
			if node.is_leaf:
				f.seek(address + self.node_size - (1 + 4))

			f.write(struct.pack("= i", node.pointers[node.fullness]))

			f.seek(address + self.node_size - 1)
			f.write(struct.pack('= b', node.is_leaf))

	def __read_node(self, address: int):
		fullness: int
		values: list = []
		pointers: list = []
		is_leaf: bool
		with open(self.btree_file_name, edit) as f:
			f.seek(address + self.node_size - 1)
			is_leaf = struct.unpack('=b ', f.read(1))[0]
			f.seek(address)
			fullness = struct.unpack("= i", f.read(4))[0]
			for i in range(fullness):
				pointers.append(struct.unpack("= i", f.read(4))[0])
				if 's' in self.key_type:
					values.append(struct.unpack("= " + self.key_type, f.read(self.key_size))[0].decode('utf-8'))
				else:
					values.append(struct.unpack("= " + self.key_type, f.read(self.key_size))[0])
			if is_leaf:
				f.seek(address + self.node_size - (1 + 4))

			pointers.append(struct.unpack("= i", f.read(4))[0])

		return BTreeNode(fullness, values, pointers, is_leaf)

	def __initialize_header(self):
		with open(self.btree_file_name, create) as f:
			f.seek(0)
			f.write(struct.pack('= i', 1))  #cantidad de nodos
			f.write(struct.pack('= i', struct.calcsize(self.key_type)))  #tamanho en bytes del valor
			f.write(struct.pack('= i', struct.calcsize("i i i")))  # puntero a root

	def __read_header(self):
		with open(self.btree_file_name, create) as f:
			f.seek(0)
			return struct.unpack('= i i i', f.read(12))  #cantidad de nodos, tamanho en bytes del valor,root pointer
