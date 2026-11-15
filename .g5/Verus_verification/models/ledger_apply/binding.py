"""Python builder/revision/error-reader binding only. No ObjectScript execution.

Reference producer is an unverified hand translation of ledger_apply.rs; its
rollback is a fixture result, never native evidence of server atomicity.
"""
import copy,inspect,itertools,json,sys,textwrap
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
import binding_common as bc
PIN_DIR=bc.import_pin()
import history_fixture as hf
from iris_vector_graph.ledger import client as CL,replay as R
from iris_vector_graph.ledger.changeset import Changeset
from iris_vector_graph.ledger.errors import NodeNotFoundError


def produce(ops):
    nodes={};records=[]
    for index,op in enumerate(ops):
        if op['op']=='create_node':
            nodes[op['id']]={};kind='create_node';attr='';prior=new=None;id=op['id']
        elif op['op']=='set_prop':
            id=op['id'];attr=op['key'];new=op['value'];prior=nodes[id].get(attr)
            if prior==new:continue
            nodes[id][attr]=new;kind='set_prop'
        else:raise AssertionError(op)
        records.append(R.MutationRecord(1,len(records)+1,kind,'node',id,attr,prior,new,None))
    return nodes,records


def compare(fn=None,changed=False):
    mism=[];n=0
    for first,second in itertools.product(['','1','2'],repeat=2):
        cs=Changeset(actor='fixture',actor_type='system');cs.create_node('n');cs.set_property('n','k',first);cs.set_property('n','k',second)
        # Real builder and wire conversion feed the reference producer.
        wire=json.loads(cs.canonical_json());nodes,records=produce(wire['ops']);g=hf.ledger(records)
        got=(fn or CL.GraphLedger.get_revision)(g,'1')
        pairs=[(r.prior,r.new) for r in got.records if r.op=='set_prop']
        want=[(None,first)]+([] if first==second else [(first,second)])
        if changed and n==0:pairs=[('wrong','wrong')]
        final=R.reconstruct(got.records,None).nodes['n'].props
        if pairs!=want or final!=nodes['n']:mism.append({'first':first,'second':second,'got':pairs,'want':want,'final':final})
        n+=1
    return n,mism


def main():
    n,mism=compare();_,changed=compare(changed=True)
    src=textwrap.dedent(inspect.getsource(CL.GraphLedger.get_revision));scope=dict(vars(CL))
    needle='records = list(iter_records_sql(self._engine.conn, self._schema(), seq, seq))'
    assert src.count(needle)==1
    exec(src.replace(needle,needle+'[::-1]'),scope);_,mut=compare(scope['get_revision'])
    # Actual client failure consumer, injected server failure at the real exposed
    # index. This tests mapping only, not whether the server rolled back.
    g=CL.GraphLedger.__new__(CL.GraphLedger);g._emit=lambda *a,**kw:None
    error={'ok':False,'error':'failed_op','reason':"node_not_found: '99'",'op_index':4}
    g._send_changeset=lambda *a,**kw:CL._CommitWireResult(ok=False,revision_id=None,replayed=False,stmt_ids={},error_code='failed_op',reason=error['reason'],raw_resp=error)
    cs=Changeset(actor='fixture',actor_type='system');cs.create_node('c')
    try:g._commit(cs,'changeset',None);raise AssertionError('missing failure')
    except NodeNotFoundError as e:assert e.op_index==4
    detection={'reversed_actual_reader_mutant':bool(mut),'changed_prior_observation':bool(changed)}
    out=bc.write_receipt('ledger_apply',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'mismatch_count':len(mism),'mismatches':mism,'detection':detection,'pin':bc.pin_identity(PIN_DIR),
        'substituted':'ObjectScript writer, IRIS transaction, SQL and revision provider; reference producer is NOT a product observation',
        'observed':'real Changeset canonical JSON, GraphLedger.get_revision -> iter_records_sql -> MutationRecord.from_row -> GraphState; actual _commit error mapping preserves index 4',
        'not_observed':'ApplyAll, SetProp, NodeExists, CommitInTxn and database rollback; these are inspected ObjectScript bindings only'})
    d=json.loads(out.read_text());d['inputs'][str(Path(hf.__file__).relative_to(bc.REPO))]=bc.sha(Path(hf.__file__))
    for p in ['iris_vector_graph/ledger/changeset.py','iris_vector_graph/ledger/errors.py']:
        d['inputs'][p]=bc.sha(PIN_DIR/p);assert d['inputs'][p]==bc.sha(bc.REPO/p)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(f"ledger_apply: {d['verdict']}; {n} reader cases; {detection}; ObjectScript inspected only; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
