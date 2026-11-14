//! M-05 Store inventory and removal (axioms AX-10, AX-02, AX-04). Generic machine over `RemovalObject`.
//!
//! Abstract state: for two targets (0 = the tenant being removed, 1 = another tenant), the set of stores (a bitmask
//! over the object's store list) that hold that target's content; per target erased? and redacted?. A write path of
//! a target puts its content into the stores it reaches (a ledger commit reaches rows, adjacency, statement maps and
//! history; a BM25 insert the BM25 index; a snapshot save the archive; ...). Erasure removes the target from the
//! stores in its inventory (Graph.KG.GraphStores, iris_src/src/Graph/KG/GraphStores.cls:26-133, and the eraser's
//! own list); redaction removes it from the history stores it reaches; the receipt names stores that keep content
//! (spec 256 FR-008). `cross` is a store in which removing one target also removes the other's content.
//!
//! Laws: M05-L1 (invariant) redacted(t) => no store outside the receipt holds t; M05-L2 (action) removing t leaves
//! the other target's content as it was; M05-L3 (invariant) no store holds content that neither erasure, redaction
//! nor the receipt reaches (the inventory is complete). Bounds: 3 writes.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub paths: Vec<u8>, pub inventory: u8, pub redact: u8, pub receipt: u8, pub cross: u8 }

pub struct Variant { pub law: &'static str, pub findings: &'static [&'static str] }

pub trait RemovalObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn stores(&self) -> &'static [&'static str];
    fn as_built(&self) -> Cfg;
    fn reviewed(&self) -> Cfg;
    fn departs(&self) -> Vec<Variant>;
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub content: [u8; 2], pub erased: [bool; 2], pub redacted: [bool; 2], pub writes: u8 }

#[derive(Clone, Debug)]
pub enum A { Write(u8, u8), Erase(u8), Redact(u8) }

pub struct Machine<'a, O: RemovalObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M05-L1 removal reaches every store or the receipt names it";
pub const L2: &str = "M05-L2 removal leaves other targets";
pub const L3: &str = "M05-L3 the inventory is complete";

impl<'a, O: RemovalObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { content: [0, 0], erased: [false; 2], redacted: [false; 2], writes: 0 }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Erase(0), A::Redact(0), A::Erase(1), A::Redact(1)];
        for t in 0..2 { for p in 0..self.c.paths.len() as u8 { v.push(A::Write(t, p)); } }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.writes <= 3 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = &self.c;
        let mut u = s.clone();
        match *a {
            A::Write(t, p) => {
                let t = t as usize;
                if s.erased[t] || s.writes >= 3 { return None; }
                let m = c.paths[p as usize];
                if s.content[t] & m == m { return None; }
                u.content[t] |= m; u.writes += 1;
            }
            A::Erase(t) => {
                let t = t as usize;
                if s.erased[t] || s.content[t] == 0 { return None; }
                u.content[t] &= !c.inventory;
                u.content[1 - t] &= !c.cross;
                u.erased[t] = true;
            }
            A::Redact(t) => {
                let t = t as usize;
                if !s.erased[t] || s.redacted[t] { return None; }
                u.content[t] &= !c.redact;
                u.content[1 - t] &= !(c.cross & c.redact);
                u.redacted[t] = true;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        let c1 = self.c.clone();
        let c3 = self.c.clone();
        vec![
            invariant(L1, move |s: &S| (0..2).all(|t| !s.redacted[t] || s.content[t] & !c1.receipt == 0)),
            invariant(L3, move |s: &S| (0..2).all(|t| s.content[t] & !(c3.inventory | c3.redact | c3.receipt) == 0)),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property(L2, |o: &S, a: &A, n: &S| match a {
            A::Erase(t) | A::Redact(t) => n.content[1 - *t as usize] == o.content[1 - *t as usize],
            _ => true,
        })]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], [$($st:expr),*], $ab:expr, $rv:expr, [$($v:expr),*]) => {
        pub struct $t;
        impl RemovalObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn stores(&self) -> &'static [&'static str] { &[$($st),*] }
            fn as_built(&self) -> Cfg { $ab }
            fn reviewed(&self) -> Cfg { $rv }
            fn departs(&self) -> Vec<Variant> { vec![$($v),*] }
        }
    };
}

fn c(paths: Vec<u8>, inventory: u8, redact: u8, receipt: u8, cross: u8) -> Cfg { Cfg { paths, inventory, redact, receipt, cross } }
fn v(law: &'static str, findings: &'static [&'static str]) -> Variant { Variant { law, findings } }

// stores: 1 rows, 2 adjacency, 4 temporal, 8 statement maps, 16 history (records)
object!(RowsAdjacencyTemporal, "rows-adjacency-temporal", ["12/graph-content"], ["rows", "adjacency", "temporal", "stmt", "history"],
        c(vec![1 | 2 | 8 | 16, 4 | 1 | 16], 1 | 2 | 4 | 8, 16, 0, 0), c(vec![1 | 2 | 8 | 16, 4 | 1 | 16], 1 | 2 | 4 | 8, 16, 0, 0), []);
// stores: 1 rows, 2 BM25 index, 4 history. Erasure does not reach BM25 indexes (Eraser.cls:138-147; F-0702).
object!(Bm25, "bm25", ["07/bm25-index"], ["rows", "bm25", "history"],
        c(vec![1 | 4, 2], 1, 4, 0, 0), c(vec![1 | 4, 2], 1 | 2, 4, 0, 0), [v(L1, &["F-0702"]), v(L3, &["F-0702"])]);
// stores: 1 rows, 2 route table, 4 IVF/tree/PLAID index (F-0606).
object!(VectorIndexes, "vector-indexes", ["06/ivf-index"], ["rows", "route", "ivf"],
        c(vec![1, 2, 4], 1 | 2, 0, 0, 0), c(vec![1, 2, 4], 1 | 2 | 4, 0, 0, 0), [v(L1, &["F-0606"]), v(L3, &["F-0606"])]);
// stores: 1 rows, 2 embedding quarantine (F-C1305).
object!(Quarantine, "quarantine", ["06/quarantined-row"], ["rows", "quarantine"],
        c(vec![1, 2], 1, 0, 0, 0), c(vec![1, 2], 1 | 2, 0, 0, 0), [v(L1, &["F-C1305"])]);
// stores: 1 rows, 2 history, 4 snapshot archive; the receipt does not name archives (F-C1304).
object!(SnapshotArchives, "snapshot-archives", ["18/snapshot-archive"], ["rows", "history", "archive"],
        c(vec![1 | 2, 4], 1, 2, 0, 0), c(vec![1 | 2, 4], 1, 2, 4, 0), [v(L1, &["F-C1304"])]);
// stores: 1 the target graph's rows, 2 the reifier node, which lands in the default graph (F-1502).
object!(ReifierDefaultGraph, "reifier-default-graph", ["15/reifier"], ["rows", "reifier in default graph"],
        c(vec![1 | 2], 1, 0, 0, 0), c(vec![1 | 2], 1 | 2, 0, 0, 0), [v(L1, &["F-1502"])]);
// stores: 1 rows, 2 marked rows of temporal edges, 4 temporal-only edges: a prefix erase and the redaction's
// liveness check do not reach them (F-C1203, F-C1308).
object!(TemporalOnlyPrefix, "temporal-only-prefix", ["05/edge-type-in-a-graph"], ["rows", "temporal shadow rows", "temporal-only edges"],
        c(vec![1 | 2, 4], 1 | 2, 0, 0, 0), c(vec![1 | 2, 4], 1 | 2 | 4, 0, 0, 0), [v(L1, &["F-C1203", "F-C1308"])]);
// stores: 1 rows, 2 records, 4 revision free text, 8 legacy revision rows (4.5.x upgrade, F-C1306), 16 the text of a
// zero-record revision (F-CS01), 32 the audit revision's unsalted digest of the tenant name (F-C1309).
object!(HistoryText, "history-text", ["13/redaction-target"], ["rows", "records", "revision text", "legacy rows", "zero-record text", "name digest"],
        c(vec![1 | 2 | 4, 8, 16, 32], 1, 2 | 4, 0, 0), c(vec![1 | 2 | 4, 8, 16, 32], 1, 2 | 4 | 8 | 16 | 32, 0, 0),
        [v(L1, &["F-C1306", "F-CS01", "F-C1309"])]);
// The ledger's node delete: 1 rows, 2 legacy vector table, 4 routed vector tables of the default graph (F-0618).
object!(DefaultRoutedVectors, "default-routed-vectors", ["06/route"], ["rows", "legacy vectors", "routed vectors"],
        c(vec![1 | 4], 1 | 2, 0, 0, 0), c(vec![1 | 4], 1 | 2 | 4, 0, 0, 0), [v(L1, &["F-0618"])]);
// TemporalIndex.Purge wipes every graph's temporal index (F-0507): 1 rows, 2 temporal index.
object!(TemporalPurgeAllGraphs, "temporal-purge-all-graphs", ["05/temporal-coordinates"], ["rows", "temporal index"],
        c(vec![1 | 2], 1 | 2, 0, 0, 2), c(vec![1 | 2], 1 | 2, 0, 0, 0), [v(L2, &["F-0507"])]);

fn instance_checks<O: RemovalObject>(o: &O) -> Vec<Outcome> {
    let n = o.name();
    let ab = Machine { o, c: o.as_built() };
    let rv = Machine { o, c: o.reviewed() };
    let mut out = vec![];
    let ds = o.departs();
    if ds.is_empty() {
        out.push(check(&format!("removal-{n}-as-built"), meta("M-05", "removal", n, o.objects(), "as-built", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&ab)));
    }
    for (k, d) in ds.iter().enumerate() {
        let id = if k == 0 { format!("removal-{n}-as-built") } else { format!("removal-{n}-as-built-{}", &d.law[..6]) };
        out.push(check(&id, meta("M-05", "removal", n, o.objects(), "as-built", "safety", d.law, d.findings, ""), Expect::Violation(d.law), &Keep::only(&ab, &[d.law])));
    }
    out.push(check(&format!("removal-{n}-reviewed"), meta("M-05", "removal", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&RowsAdjacencyTemporal));
    out.extend(instance_checks(&Bm25));
    out.extend(instance_checks(&VectorIndexes));
    out.extend(instance_checks(&Quarantine));
    out.extend(instance_checks(&SnapshotArchives));
    out.extend(instance_checks(&ReifierDefaultGraph));
    out.extend(instance_checks(&TemporalOnlyPrefix));
    out.extend(instance_checks(&HistoryText));
    out.extend(instance_checks(&DefaultRoutedVectors));
    out.extend(instance_checks(&TemporalPurgeAllGraphs));
    let o = &RowsAdjacencyTemporal;
    let r = o.reviewed();
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check(id, meta("M-05", "removal", "rows-adjacency-temporal", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("removal-control-C1-store-dropped", L1, Cfg { inventory: r.inventory & !2, ..r.clone() }));
    out.push(ctl("removal-control-C1b-store-dropped-inventory", L3, Cfg { inventory: r.inventory & !2, ..r.clone() }));
    out.push(ctl("removal-control-C2-cross-target", L2, Cfg { cross: 4, ..r.clone() }));
    let rv = Machine { o, c: r };
    let sm = || meta("M-05", "removal", "rows-adjacency-temporal", RowsAdjacencyTemporal.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("removal-sharp-removed-other-kept", sm(), &rv, "never: target 0 removed while target 1 keeps content",
                   |s: &S| s.redacted[0] && s.content[0] == 0 && s.content[1] != 0));
    out.push(reach("removal-sharp-erased-history-kept", sm(), &rv, "never: erased with history kept (before redaction)",
                   |s: &S| s.erased[0] && !s.redacted[0] && s.content[0] == 16));
    out
}
