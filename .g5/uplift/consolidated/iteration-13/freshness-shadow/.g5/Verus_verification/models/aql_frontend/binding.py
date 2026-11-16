"""Actual numeric lexer -> typed AST -> translator -> execute_aql consumer.
Cypher execution is a recorder; no query results or SQL semantics are claimed.
"""
import inspect,itertools,json,sys,textwrap
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
from iris_vector_graph.cypher.aql import translate_aql,AQLParseError
from iris_vector_graph.cypher.aql.lexer import AQLLexer
from iris_vector_graph.cypher.aql.parser import AQLParser
from iris_vector_graph.cypher.aql.translator import AQLTranslator
from iris_vector_graph.engine import IRISGraphEngine

def compare(resolve=None,change=False):
    original=AQLTranslator._resolve_binop
    if resolve:AQLTranslator._resolve_binop=resolve
    mism=[];n=0
    try:
        for lo,hi,op,right in itertools.product(range(4),range(4),['==','!='],['null','"null"','1']):
            source=f'FOR v IN {lo}..{hi} OUTBOUND @s g FILTER v.x {op} {right} RETURN v._key'
            tokens=AQLLexer(source).tokenize();ast=AQLParser(tokens).parse()
            cy,params=translate_aql(source,{'s':'a'})
            expr='v.x IS '+('NOT ' if op=='!=' else '')+'NULL' if right=='null' else 'v.x '+('=' if op=='==' else '<>')+' '+right
            if change and n==0:cy='changed'
            if (ast.for_clause.min_depth,ast.for_clause.max_depth)!=(lo,hi) or f'*{lo}..{hi}' not in cy or expr not in cy or params!={'s':'a'}:
                mism.append([source,cy,expr])
            # Real public adapter must hand the exact text and binding to consumer.
            e=IRISGraphEngine.__new__(IRISGraphEngine);seen=[]
            e.execute_cypher=lambda q,parameters:seen.append((q,parameters)) or 'answer'
            if e.execute_aql(source,{'s':'a'})!='answer' or seen!=[(cy,params)]:mism.append(['consumer',source])
            n+=1
        for depth in ['1.5','1..2.5','1.','1.5..2']:
            try:translate_aql(f'FOR v IN {depth} OUTBOUND @s g RETURN v',{'s':'a'});mism.append(['decimal admitted',depth])
            except AQLParseError:pass
            n+=1
    finally:AQLTranslator._resolve_binop=original
    return n,mism

def main():
    n,mism=compare();scope=dict(vars(sys.modules[AQLTranslator.__module__]))
    src=textwrap.dedent(inspect.getsource(AQLTranslator._resolve_binop))
    exec(src.replace('IS NOT NULL','IS NULL'),scope);_,mut=compare(scope['_resolve_binop']);_,changed=compare(change=True)
    # Producer control: treating the first dot of '..' as decimal must refuse a
    # previously admitted integer range. This checks the lexer, not just the AST.
    source=textwrap.dedent(inspect.getsource(AQLLexer._read_number));lscope=dict(vars(sys.modules[AQLLexer.__module__]))
    anchor="(self._pos + 1 >= len(self._src) or self._src[self._pos + 1] != '.')"
    assert anchor in source;exec(source.replace(anchor,'True'),lscope)
    original=AQLLexer._read_number;AQLLexer._read_number=lscope['_read_number']
    try:
        try:translate_aql('FOR v IN 1..2 OUTBOUND @s g RETURN v',{'s':'a'});producer=False
        except AQLParseError:producer=True
    finally:AQLLexer._read_number=original
    detection={'null_operator_mutant':bool(mut),'range_lexer_mutant':producer,'changed_translation':bool(changed)}
    out=bc.write_receipt('aql_frontend',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'mismatch_count':len(mism),'mismatches':mism[:5],'detection':detection,'pin':bc.pin_identity(PIN),
        'domain':'0..3 lower/upper depth x equality/inequality x literal null/text null/1, plus 4 decimal depths; no security inputs',
        'substituted':'execute_cypher final consumer recorder only; actual lexer, parser, AST, translation and execute_aql run; Cypher semantics and SQL unproved'})
    d=json.loads(out.read_text())
    for f in ['iris_vector_graph/cypher/aql/lexer.py','iris_vector_graph/cypher/aql/parser.py','iris_vector_graph/cypher/aql/translator.py','iris_vector_graph/cypher/aql/__init__.py','iris_vector_graph/_engine/query.py']:
        d['inputs'][f]=bc.sha(PIN/f)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(f"aql_frontend: {d['verdict']}; {n} journeys; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
