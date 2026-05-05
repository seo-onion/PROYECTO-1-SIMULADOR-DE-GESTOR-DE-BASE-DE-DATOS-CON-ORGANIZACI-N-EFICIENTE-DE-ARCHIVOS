import os
import struct

create = 'w+b'
edit = "rb+"
B = 4


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
		self.address=-1

	#self.father_ptr=-1
	def insert_val(self,val,ptr):

		for i in range(self.fullness+1):
			if i==self.fullness or val<self.values[i] :
				self.values.insert(i,val)
				self.pointers.insert(i,ptr)
				self.fullness+=1
				return
	def divide(self,new_address): #retorna el valor del medio y el hermano
		brother=BTreeNode(0,[],[],self.is_leaf)
		brother.address=new_address

		half=self.fullness//2
		if not self.is_leaf:
			half+=1
		brother.pointers.append(self.pointers.pop())

		while len(self.values)>half :
			brother.pointers.insert(0,self.pointers.pop())
			brother.values.insert(0,self.values.pop())
			brother.fullness+=1

		if self.is_leaf:
			self.fullness=len(self.values)
			self.pointers.append(new_address)
			return self.values[len(self.values)-1],brother

		self.fullness = len(self.values)-1

		return self.values.pop(),brother

	def get_index(self, val)->int:
		for i in range(self.fullness):
			if val<self.values[i] or i==self.fullness:
				return i
		return self.fullness

	def print(self):
		print("fullness: ", self.fullness)
		print("values: ", self.values)
		print("pointers: ", self.pointers)
		print("is_leaf: ", self.is_leaf)
		print("address: ", self.address)


class Btree:
	HEADER_SIZE = struct.calcsize('i') * 3

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
		# node=		self.__read_node(self.HEADER_SIZE)
		# node.address=self.HEADER_SIZE
		# node.print()

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
			is_leaf = struct.unpack('= b', f.read(1))[0]
			f.seek(address)
			fullness = struct.unpack("= i", f.read(4))[0]
			for i in range(fullness):
				pointers.append(struct.unpack("= i", f.read(4))[0])
				if 's' in self.key_type:
					#
					values.append(struct.unpack("= " + self.key_type, f.read(self.key_size))[0].rstrip('\00').decode('utf-8'))
					values.append(struct.unpack("= " + self.key_type, f.read(self.key_size))[0].rstrip(b'\x00').decode('utf-8'))
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

	def __fetch_node_number_and_increment(self):
		nodes=0
		with open(self.btree_file_name,edit) as f :
			f.seek(0)
			nodes=struct.unpack("= i",f.read(4))[0]
			f.seek(0)
			f.write(struct.pack('= i', nodes+1))
		return nodes

	def __update_root(self,new_root:int):
		with open(self.btree_file_name,edit) as f :
			f.seek(8)
			f.write(struct.pack('= i', new_root))

	def __get_root(self)->int:
		with open(self.btree_file_name,edit) as f :
			f.seek(8)
			return struct.unpack("= i",f.read(4))[0]
	def __index_to_address(self,index:int):
		return self.HEADER_SIZE+index*self.node_size  #address

	def __recursive_insert_and_split(self,path:list[BTreeNode],node_index:int,val,ptr:int,changed_nodes:list[BTreeNode]):
		node=path[node_index]
		changed_nodes.append(node)
		node.insert_val(val,ptr)
		if node.fullness>=B:
			new_address=self.__index_to_address(self.__fetch_node_number_and_increment())
			value_up,brother=node.divide(new_address)
			brother.address=new_address
			changed_nodes.append(brother)
			if node_index==0: #el nodo es root
				new_root_ptr=self.__index_to_address(self.__fetch_node_number_and_increment())
				new_root=BTreeNode(1,[value_up],[node.address,new_address],False)
				new_root.address=new_root_ptr
				self.__update_root(new_root_ptr)
				changed_nodes.append(new_root)
			else:
				self.__recursive_insert_and_split(path,node_index-1,value_up,new_address,changed_nodes)


	def insert(self,val,ptr:int):
		path:BTreeNode=[]
		current_node=self.__read_node(self.__get_root())
		current_node.address=self.__get_root()
		path.append(current_node)
		while not current_node.is_leaf:
			new_address=current_node.pointers[current_node.get_index(val)]
			current_node=self.__read_node(new_address)
			current_node.address=new_address
			path.append(current_node)
		#aqui el path tiene todos los ancestros + la rama a la que se va a insertar el valor
		#todos los nodos incluidos aqui tambien tienen su address incorporado para facilitar su manejo

		changed_nodes=[]
		#print((path,path[len(path)-1],val,ptr,changed_nodes))

		self.__recursive_insert_and_split(path,len(path)-1,val,ptr,changed_nodes)
		for node in changed_nodes:
			self.__write_node(node,node.address)



	def __recursive_get_all_nodes(self,address:int,nodes:list[BTreeNode]):
		node=self.__read_node(address)
		nodes.append(node)
		node.address=address

		if not node.is_leaf:
			for ptr in node.pointers:
				self.__recursive_get_all_nodes(ptr,nodes)

	def get_all_nodes(self)->list[BTreeNode]: #for debugging
		root_ptr=self.__get_root()
		nodes=[]
		self.__recursive_get_all_nodes(root_ptr,nodes)
		return nodesb.insert('c',40)



