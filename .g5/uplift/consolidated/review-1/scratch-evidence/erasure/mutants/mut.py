import sys
src, dst, find, repl = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
t = open(src).read()
n = t.count(find)
assert n == 1, (n, find)
open(dst, "w").write(t.replace(find, repl))
