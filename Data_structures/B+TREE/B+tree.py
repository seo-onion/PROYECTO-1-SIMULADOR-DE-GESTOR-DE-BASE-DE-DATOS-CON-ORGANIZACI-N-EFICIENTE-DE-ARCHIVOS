



import os

create='w+b'
edit='a+b'


class Btree:
	def __init__(self,filename:str,table_format:str,key_index:int):
		self.db_name=filename
		self.format=table_format
		self.key_index=key_index
		self.key_type=table_format.split(' ')[key_index]
		self.btree_file_name=filename+"btree"+"_index"+str(key_index)
		# falta la logica de revisar si el
		# file del btree existe o no y en caso no exista inicializarlo


	def swap(self,offset1:int,offset2:int,size:int):
		with open(self.btree_file_name,edit) as f:
			f.seek(offset1)
			v1:bytes=f.read(size)
			f.seek(offset2)
			v2:bytes=f.read(size)
			f.seek(offset1)
			f.write(v2)
			f.seek(offset2)
			f.write(v1)

	def initialize_btree(self):
		pass


