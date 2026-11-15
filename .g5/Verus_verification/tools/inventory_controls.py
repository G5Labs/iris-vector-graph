"""Targeted control for definitions nested under non-scope AST statements."""
import ast,importlib.util,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def module(path):
    s=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
inv=module(HERE/'inventory.py');gate=module(HERE/'check_consolidated.py')
source='''
if True:
    def guarded(): pass
class C:
    if True:
        def method(self):
            try:
                async def local(): pass
            except Exception: pass
def outer():
    with context():
        def nested(): pass
VALUE=1
'''
want=['guarded','C.method','C.method.local','outer','outer.nested']
got=inv.py_defs(source);resolved=gate.py_defs(source)
assert got==want,(got,want)
assert all(resolved[x]==1 for x in want) and resolved['VALUE']==1 and 'VALUE' not in got
# Re-run the same fixture with the sealed before-image walker: it must miss them.
old=subprocess.check_output(['git','-C',str(inv.REPO),'show','d087503:.g5/Verus_verification/tools/inventory.py'],text=True)
scope={'__file__':str(HERE/'inventory.py'),'__name__':'inventory_before'};exec(old,scope)
before=scope['py_defs'](source)
assert before!=want and before==['outer']
# Independent whole-AST count at the same pin, with no qualified-name algorithm.
total=0
for f in inv.files('iris_vector_graph/','.py'):
    src=inv.git('show',f'{inv.PIN}:{f}');tree=ast.parse(src)
    expected=sum(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) for x in ast.walk(tree))
    actual=len(inv.py_defs(src));assert actual==expected,(f,actual,expected)
    total+=actual
out={'before_fixture':before,'after_fixture':got,'expected':want,'constant_excluded':True,
     'whole_ast_pin_definitions':total,'verdict':'AGREES','scope':'definition inventory only; semantic coverage unchanged'}
p=inv.REPO/'.g5/uplift/consolidated/iteration-2/inventory-control.json';p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
