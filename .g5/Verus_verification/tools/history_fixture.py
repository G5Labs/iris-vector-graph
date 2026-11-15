"""Substituted SQL record provider, never evidence of ObjectScript execution.

Call import_pin before importing this module. Actual get_revision, record paging,
null decoding, reconstruction and export execute against this DB-API fixture.
"""
from types import SimpleNamespace
from iris_vector_graph.ledger.client import GraphLedger


def row(r):
    return (r.seq,r.ordinal,r.op,r.entity_kind,r.entity_id,r.attr,r.prior or "",int(r.prior is None),
            r.new or "",int(r.new is None),r.graph or "",",".join(r.flags),r.digest,r.redacted_op)


class Cursor:
    def __init__(self,records): self.records=records; self.params=None; self.sql=""
    def execute(self,sql,params): self.sql=sql; self.params=params
    def fetchone(self):
        s=self.params[0]
        return (s,str(s),str(s-1),"changeset","fixture","system","fixture",0,None,None,None,None,0)
    def fetchall(self):
        start,end,ordinal,size=self.params
        return [row(r) for r in self.records if start<=r.seq<=end and (r.seq,r.ordinal)>=(start,ordinal)][:size]
    def close(self): pass


def ledger(records,bound=1):
    g=GraphLedger.__new__(GraphLedger)
    g._engine=SimpleNamespace(conn=SimpleNamespace(cursor=lambda:Cursor(records)))
    g._schema=lambda:"Graph_KG"
    g._seq_of=lambda id:int(id)
    g._refuse_while_redacting=lambda:None
    g.meta=lambda:{"recon_bound":bound}
    return g
