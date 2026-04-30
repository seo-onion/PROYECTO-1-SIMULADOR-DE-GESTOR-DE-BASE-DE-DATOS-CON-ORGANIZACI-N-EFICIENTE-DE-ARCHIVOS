class Btree:
	def __init__(self,filename:str,table_format:str,key_index:int):
		self.db_name=filename
		self.format=table_format
		self.key_index=key_index
		self.btree_file_name=filename+"btree"+"_index"+str(key_index)


