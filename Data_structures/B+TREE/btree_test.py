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
	b=Btree(db_name,table_format,0,True)

	i=20
	while i>-21:
		b.insert(i,(10*i))
		i-=1
	b.delete(0,0)
	b.delete(1,10)
	b.delete(2,20)
	b.delete(-1,-10)

	b.delete(-34,-17)


def test_2():
	table_format="i 10s f 15s"
	db_name="db"
	b=Btree(db_name,table_format,0)
	nodes = b.get_all_nodes()
	for node in nodes:
		if node.is_leaf:
			node.print()
			print('----------------------------')
def test_3():
	table_format="i 10s f 15s"
	db_name="db"
	b=Btree(db_name,table_format,0)
	for i in range(9):
		b.insert(3,i)
	# nodes = b.get_all_nodes()
	# for node in nodes:
	# 	if node.is_leaf:
	# 		node.print()
	# 		print('----------------------------')
def test_4():
	table_format = "i 10s f 15s"
	db_name = "db"
	b = Btree(db_name, table_format, 0)
	for i in range(7):
		print(b.delete(3, i))

def test_range():
	table_format="i 10s f 15s"
	db_name="db"
	b=Btree(db_name,table_format,0)
	range=b.range_search(-4,8)
	#print(range)
	for p in range:
		print(p)

	print('--------')
	print(b.search(-20,-200))# si ta
	print(b.search(-20,15))# no ta
test_btree()
#test_2()
test_3()
test_range()
test_4()

test_range()
# test_range()








# f=open('xd.bin',"wb+")
# f.close()
# f=open('xd.bin',"rb+")
#
# f.seek(6)
# f.write(struct.pack("= 3s","000".encode()))