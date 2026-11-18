import runpy, sys
src = open(sys.argv[1]).read().split("create()\ntry:")[0]
g = {}
exec(compile(src, "r1", "exec"), g)
print(g["drop"]().strip()[-60:])
print(g["irs"]('Write ##class(Config.Namespaces).Exists("R1N"),",",##class(Config.Databases).Exists("R1N"),!').strip()[-20:])
