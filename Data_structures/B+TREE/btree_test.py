#import struct
# name='test.bin'
#
# f=open(name,"w+b")
# a=200
# f.write(a.to_bytes())
#
# f.close()
#
from BPlusTree import Btree
def test_btree():
	table_format="i 10s f 15s"
	db_name="db"
	b=Btree(db_name,table_format,1)

	b.insert('c',40)
	b.insert('d',200)
	b.insert('a',10)
	b.insert('b',30)
	b.insert('andre',100)
	b.insert('abeja',400)
	nodes=b.get_all_nodes()
	for node in nodes:
		node.print()
		print('----------------------------')
test_btree()








# f=open('xd.bin',"wb+")
# f.close()
# f=open('xd.bin',"rb+")
#
# f.seek(6)
# f.write(struct.pack("= 3s","000".encode()))