import math
import os
import struct

create = 'w+b'
edit = "rb+"
B = 5 #si ponen 2 aqui ya fue ya, el delete la malogra


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
	def insert_child(self,val,ptr):

		for i in range(self.fullness+1):
			if i==self.fullness or val<self.values[i] :
				self.values.insert(i,val)
				self.pointers.insert(i+1,ptr)
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
	def get_child_index(self, val)->int:
		index=-1
		for i in range(self.fullness):
			if val<self.values[i] and index==-1:
				index=i
			if val==self.values[i]:
				return i
		if index==-1:
			return self.fullness
		return index

	def merge(self,brother):
		if self.fullness+brother.fullness>=B:
			raise Exception("no se puede hacer merge porrque los hermanos tienen demasiados valores en conjunto")
		self.fullness+=brother.fullness
		self.values=self.values+brother.values
		self.pointers.pop()
		self.pointers=self.pointers+brother.pointers

	def get_ptr_index(self,ptr:int):
		for i in range(len(self.pointers)):
			if self.pointers[i]==ptr:
				return i
		raise Exception("puntero no se encuentra en el nodo")
	def delete_by_ptr_leaf(self,ptr:int):
		for i in range(len(self.pointers)):
			if self.pointers[i]==ptr:
				self.pointers.pop(i)
				self.values.pop(i)
				self.fullness-=1
				return
		raise Exception("puntero no se encuentra en el nodo")

	def delete_by_ptr(self,ptr:int):
		#self.print()
		#print(ptr)
		for i in range(len(self.pointers)):
			if self.pointers[i]==ptr:
				self.pointers.pop(i)
				self.values.pop(i-1)
				self.fullness-=1
				#self.print()
				return
		raise Exception("puntero no se encuentra en el nodo")
	def search(self,val,ptr:int):
		try:
			v_index = self.values.index(val)
		except ValueError:
			v_index = -1
		try:
			ptr_index = self.pointers.index(ptr)
		except ValueError:
			ptr_index = -1
		if ptr_index<self.fullness and self.values[ptr_index]==val:
			return ptr_index,ptr_index
		if self.pointers[v_index]==ptr:
			return v_index,v_index
		return v_index,ptr_index

	def delete(self,val,ptr:int):
		i=0
		while i<self.fullness and not (self.pointers[i]==ptr and self.values[i]==val):
			i+=1
		if i==self.fullness:
			raise Exception("Elemento a eliminar no se encuentra en el nodo")
		self.fullness-=1
		self.values.pop(i)
		self.pointers.pop(i)

	def print(self):
		print("fullness: ", self.fullness)
		print("values: ", self.values)
		print("pointers: ", self.pointers)
		print("is_leaf: ", self.is_leaf)
		print("address: ", self.address)


class Btree:
	HEADER_SIZE = struct.calcsize('i') * 4

	def __init__(self, filename: str, table_format: str, key_index: int,SILEPONESTRUEAESTAVARIABLEBORRASTODONOSEASWEON=False):

		self.db_name = filename
		self.format = table_format
		self.key_index = key_index
		self.key_type = table_format.split(' ')[key_index]
		self.key_size = struct.calcsize("= " + self.key_type)
		self.btree_file_name = filename + "btree" + "_index" + str(key_index) + ".bin"
		self.node_size = 4 + struct.calcsize("= " + self.key_type) * (B - 1) + (4 * B) + 1
		if os.path.exists(self.btree_file_name) and not SILEPONESTRUEAESTAVARIABLEBORRASTODONOSEASWEON :
			self.__check_header()
		else:
			self.__initialize_header()
			base_node = BTreeNode(0, [], [-1], True)
			self.__write_node(base_node, self.HEADER_SIZE)


	def __check_header(self):
		free_list, k_size, root_ptr, free_list= self.__read_header()
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
			f.write(struct.pack('= i', self.HEADER_SIZE))  # puntero a root
			f.write(struct.pack('= i',-1)) #free_list

	def __read_header(self):
		with open(self.btree_file_name, edit) as f:
			f.seek(0)
			return struct.unpack('= i i i i', f.read(self.HEADER_SIZE))  #cantidad de nodos, tamanho en bytes del valor,root pointer, free list ptr

	def __update_node_cuantity(self,amount:int):
		with open(self.btree_file_name,edit) as f :
			f.seek(0)
			f.write(struct.pack('= i', amount))

	def __next_free_address(self):
		nodes,value_size,root_ptr,free_list=self.__read_header()
		if free_list==-1:
			self.__update_node_cuantity(nodes+1)
			return self.__index_to_address(nodes)
		node=self.__read_node(free_list)
		self.__update_free_list(node.pointers[0])
		return free_list

	def __update_free_list(self,ptr:int):
		with open(self.btree_file_name,edit) as f :
			f.seek(12)
			f.write(struct.pack('= i', ptr))

	def __update_root(self,new_root:int):
		with open(self.btree_file_name,edit) as f :
			f.seek(8)
			f.write(struct.pack('= i', new_root))

	def __get_root(self)->int:
		with open(self.btree_file_name,edit) as f :
			f.seek(8)
			return struct.unpack("= i",f.read(4))[0]
	def __get_free_list(self):
		with open(self.btree_file_name,edit) as f :
			f.seek(12)
			return struct.unpack("= i",f.read(4))[0]
	def __index_to_address(self,index:int):
		return self.HEADER_SIZE+index*self.node_size  #address

	def __recursive_insert_and_split(self,path:list[BTreeNode],node_index:int,val,ptr:int,changed_nodes:list[BTreeNode]):
		node=path[node_index]
		changed_nodes.append(node)
		if node.is_leaf:
			node.insert_val(val,ptr)
		else:
			node.insert_child(val,ptr)

		if node.fullness>=B:
			new_address=self.__next_free_address()
			value_up,brother=node.divide(new_address)
			brother.address=new_address
			changed_nodes.append(brother)
			if node_index==0: #el nodo es root
				new_root_ptr=self.__next_free_address()
				new_root=BTreeNode(1,[value_up],[node.address,new_address],False)
				new_root.address=new_root_ptr
				self.__update_root(new_root_ptr)
				changed_nodes.append(new_root)
			else:
				self.__recursive_insert_and_split(path,node_index-1,value_up,new_address,changed_nodes)


	def insert(self,val,ptr:int):
		path=self.__pathing(val)
		changed_nodes=[]
		#print((path,path[len(path)-1],val,ptr,changed_nodes))
		self.__recursive_insert_and_split(path,len(path)-1,val,ptr,changed_nodes)
		for node in changed_nodes:
			self.__write_node(node,node.address)



	def __recursive_get_all_nodes(self,address:int,nodes:list[BTreeNode]):

		node=self.__read_node(address)
		nodes.append(node)
		node.address=address
		#node.print()
		if not node.is_leaf:
			for ptr in node.pointers:
				self.__recursive_get_all_nodes(ptr,nodes)

	def get_all_nodes(self)->list[BTreeNode]: #for debugging
		root_ptr=self.__get_root()
		nodes=[]
		self.__recursive_get_all_nodes(root_ptr,nodes)
		return nodes
	def __search_pathing(self,val):
		path: list[BTreeNode] = []
		current_node = self.__read_node(self.__get_root())
		current_node.address = self.__get_root()
		path.append(current_node)
		while not current_node.is_leaf:
			#print(current_node.get_child_index(val))
			new_address = current_node.pointers[current_node.get_child_index(val)]
			current_node = self.__read_node(new_address)
			current_node.address = new_address
			path.append(current_node)
		return path
	def __pathing(self,val):
		path: list[BTreeNode] = []
		current_node = self.__read_node(self.__get_root())
		current_node.address = self.__get_root()
		path.append(current_node)
		while not current_node.is_leaf:
			#print(current_node.get_child_index(val))
			new_address = current_node.pointers[current_node.get_index(val)]
			current_node = self.__read_node(new_address)
			current_node.address = new_address
			path.append(current_node)
		return path


	def __delete_node(self, node:BTreeNode):
		address=node.address
		#node.print()
		free_list=self.__get_free_list()
		self.__update_free_list(address)
		self.__write_node(BTreeNode(-1,[],[free_list],False),address)



	def __recursive_delete_and_merge(self,path:list[BTreeNode],node_index:int,ptr:int,changed_nodes:list[BTreeNode]):
		node=path[node_index]
		if node.is_leaf:
			node.delete_by_ptr_leaf(ptr)
		else:
			node.delete_by_ptr(ptr)

		changed_nodes.append(node)
		if node.fullness>=math.ceil(B/2)-1:
			return
		if node_index==0:
			if node.fullness>0:
				return
			self.__delete_node(node.address)
			self.__update_root(node.pointers[0])
			changed_nodes.pop()
			return
		father=path[node_index-1]
		ptr_index=father.get_ptr_index(node.address)

		if ptr_index==0:
			right_brother=self.__read_node(father.pointers[ptr_index+1])
			right_brother.address=father.pointers[ptr_index+1]
			if right_brother.fullness >math.ceil(B/2)-1:
				changed_nodes.append(right_brother)
				changed_nodes.append(father)
				right_brother.fullness-=1
				node.values.insert(node.fullness,right_brother.values.pop(0))
				node.pointers.insert(node.fullness,right_brother.pointers.pop(0))
				node.fullness+=1
				father.values[father.get_ptr_index(node.address)]=node.values[node.fullness-1]
				return
			node.merge(right_brother)
			self.__delete_node(right_brother)
			self.__recursive_delete_and_merge(path,node_index-1,right_brother.address,changed_nodes)
			return

		if ptr_index==father.fullness:
			left_brother=self.__read_node(father.pointers[ptr_index+-1])
			left_brother.address=father.pointers[ptr_index+-1]
			if left_brother.fullness >math.ceil(B/2)-1:
				changed_nodes.append(left_brother)
				changed_nodes.append(father)
				left_brother.fullness-=1
				node.values.insert(0,left_brother.values.pop(left_brother.fullness))
				node.pointers.insert(0,left_brother.pointers.pop(left_brother.fullness))
				node.fullness+=1
				father.values[father.get_ptr_index(left_brother.address)]=left_brother.values[left_brother.fullness-1]
				return
			left_brother.merge(node)
			self.__delete_node(node)
			changed_nodes.pop()
			changed_nodes.append(left_brother)
			self.__recursive_delete_and_merge(path, node_index - 1, node.address, changed_nodes)
			return

		left_brother = self.__read_node(father.pointers[ptr_index - 1])
		left_brother.address = father.pointers[ptr_index - 1]
		right_brother = self.__read_node(father.pointers[ptr_index + 1])
		right_brother.address = father.pointers[ptr_index + 1]

		if left_brother.fullness > math.ceil(B / 2) - 1:
			changed_nodes.append(left_brother)
			changed_nodes.append(father)
			left_brother.fullness -= 1
			node.values.insert(0, left_brother.values.pop(left_brother.fullness ))
			node.pointers.insert(0, left_brother.pointers.pop(left_brother.fullness ))
			node.fullness += 1
			father.values[father.get_ptr_index(left_brother.address)] = left_brother.values[left_brother.fullness - 1]
			return

		if right_brother.fullness > math.ceil(B / 2) - 1:
			changed_nodes.append(right_brother)
			changed_nodes.append(father)
			right_brother.fullness -= 1
			node.values.insert(node.fullness, right_brother.values.pop(0))
			node.pointers.insert(node.fullness, right_brother.pointers.pop(0))
			node.fullness += 1
			father.values[father.get_ptr_index(node.address)] = node.values[node.fullness - 1]
			return

		left_brother.merge(node)
		self.__delete_node(node)
		changed_nodes.pop()
		changed_nodes.append(left_brother)
		#node.print()

		self.__recursive_delete_and_merge(path, node_index - 1, node.address, changed_nodes)


	def delete(self,val,ptr:int)->bool:#el pointer es necesario porque puede haber varias llaves iguales
		path=self.__search_pathing(val)
		current_node=path[len(path)-1]
		original_address=current_node.address
		v_index,ptr_index=current_node.search(val,ptr)
		while_entered=v_index!=ptr_index

		#print(val,ptr)
		while not v_index == ptr_index:
			address = current_node.pointers[current_node.fullness]
			if address == -1:
				break
			current_node = self.__read_node(address)
			current_node.address = address
			v_index, ptr_index = current_node.search(val, ptr)

		if v_index==-1:
			return False
		if while_entered:
			first_leaf=self.__read_node(original_address)
			first_leaf.address=original_address
			first_index=first_leaf.get_index(val)
			first_leaf.pointers[first_index],current_node.pointers[ptr_index]=current_node.pointers[ptr_index],first_leaf.pointers[first_index]
			self.__write_node(first_leaf,first_leaf.address)
			self.__write_node(current_node,current_node.address)
			path[len(path)-1]=first_leaf

		if current_node.address != original_address:
			path[len(path) - 1] = current_node
		changed_nodes=[]
		if val not in path[len(path)-1].values:
			return False
		self.__recursive_delete_and_merge(path,len(path)-1,ptr,changed_nodes)

		for node in changed_nodes:
			#node.print()
			self.__write_node(node,node.address)
		#print("aaaaaa")
		return True

	def range_search(self,low,high)->list:
		#print('xd')
		path=self.__search_pathing(low)
		# for p in path:
		# 	p.print()
		current_node=path[len(path)-1]
		index,_=current_node.search(low,0)
		rango=[]
		#current_node.print()
		while True:
			for i in range(current_node.fullness):
				if current_node.values[i]>high:
					return rango
				if current_node.values[i]>=low:
					rango.append((current_node.values[i],current_node.pointers[i]))
			if current_node.pointers[current_node.fullness]==-1:
				return rango
			current_node=self.__read_node(current_node.pointers[current_node.fullness])
	def search(self,val,ptr):
		path = self.__search_pathing(val)
		current_node = path[len(path) - 1]
		val_index, ptr_index = current_node.search(val, ptr)
		while val_index!=ptr_index:
			if current_node[0]>val_index:
				return None
			if current_node.pointers[current_node.fullness]==-1:
				return None
			val_index, ptr_index = current_node.search(val, ptr)

		if val_index==-1:
			return None

		return (current_node.values[val_index],current_node.pointers[ptr_index])