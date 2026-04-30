
name='test.bin'

f=open(name,"w+b")
a=200
f.write(a.to_bytes())

f.close()

