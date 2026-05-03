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
	b=Btree(db_name,table_format,0)

test_btree()










# f=open('xd.bin',"wb+")
# f.close()
# f=open('xd.bin',"rb+")
#
# f.seek(6)
# f.write(struct.pack("= 3s","000".encode()))