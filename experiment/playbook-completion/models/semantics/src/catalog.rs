//! M-12 Catalog binding of artifacts to graph and identity (axioms AX-02, AX-01, AX-08). Generic machine over
//! `CatalogObject`.
//!
//! Abstract state: three (graph, identity) pairs, (0,0), (1,0), (0,1); artifact slots named by the object's naming
//! function; each artifact's recorded binding (the pair it was built for, or none recorded); ghosts: a read or write
//! used an artifact bound to another pair (`misused`), a create overwrote another pair's artifact (`clobbered`).
//! Naming: `Full` (distinct pairs, distinct names: the registry row names the table, VEC-I2.3) or `ShortHash`
//! (pairs (0,0) and (0,1) share a name: two plan shapes with one 32-bit checksum, Gen.cls:69-80, F-0901). Recording:
//! the artifact records its graph (or not: an index with no recorded graph is read as the default graph's,
//! BM25Index.cls:608-612, F-0705). Reads: `Checked` (use only an artifact bound to the asked pair) or `NoCheck`
//! (F-0707, F-0609). Writes through the identity check: the registry read may fail; `FailOpen` lets the write through
//! unchecked (schema.py:1033-1061, F-0601; writers that skip the check, F-0602, F-0603, F-0613).
//!
//! Laws: M12-L1 (invariant) every artifact records its binding; M12-L2 (action) a read or write uses only an artifact
//! bound to its pair, and a failed check refuses; M12-L3 (invariant) no create overwrites another pair's artifact.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Naming { Full, ShortHash }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub naming: Naming, pub records: bool, pub read_checked: bool, pub fail_open: bool }

pub const CANON: Cfg = Cfg { naming: Naming::Full, records: true, read_checked: true, fail_open: false };

pub struct Variant { pub cfg: Cfg, pub law: &'static str, pub findings: &'static [&'static str] }

pub trait CatalogObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Vec<Variant>;
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub slots: [Option<(u8, Option<u8>)>; 3], pub misused: bool, pub clobbered: bool, pub n: u8 }

/// Create(pair); Read(pair, slot) and Write(pair, slot, registry read fails): the caller names the artifact (an index
/// name, a table) and asks for its own pair.
#[derive(Clone, Debug)]
pub enum A { Create(u8), Read(u8, u8), Write(u8, u8, bool) }

pub struct Machine<'a, O: CatalogObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M12-L1 every artifact records its binding";
pub const L2: &str = "M12-L2 use only the bound artifact";
pub const L3: &str = "M12-L3 distinct bindings, distinct artifacts";

impl<'a, O: CatalogObject> Machine<'a, O> {
    fn slot(&self, p: u8) -> usize { match (self.c.naming, p) { (Naming::ShortHash, 2) => 0, (_, p) => p as usize } }
    /// whether the access proceeds, and whether it then uses another pair's artifact
    fn access(&self, s: &S, p: u8, k: u8, check_fails: bool) -> Option<(bool, bool)> {
        let (creator, rec) = s.slots[k as usize]?;
        // an artifact with no recorded binding is taken as the default graph's identity-0 artifact (pair 0)
        let seen = rec.unwrap_or(0);
        let go = if check_fails { self.c.fail_open } else if self.c.read_checked { seen == p } else { true };
        Some((go, go && creator != p))
    }
}

impl<'a, O: CatalogObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { slots: [None; 3], misused: false, clobbered: false, n: 0 }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for p in 0..3 {
            v.push(A::Create(p));
            for k in 0..3 { v.push(A::Read(p, k)); v.push(A::Write(p, k, false)); v.push(A::Write(p, k, true)); }
        }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        if s.n >= 4 { return None; }
        let c = self.c;
        let mut u = s.clone();
        u.n += 1;
        match *a {
            A::Create(p) => {
                let k = self.slot(p);
                if let Some((q, _)) = s.slots[k] { if q == p { return None; } u.clobbered = true; }
                u.slots[k] = Some((p, if c.records { Some(p) } else { None }));
            }
            A::Read(p, k) => { let (_, bad) = self.access(s, p, k, false)?; if bad { u.misused = true; } }
            A::Write(p, k, fails) => { let (_, bad) = self.access(s, p, k, fails)?; if bad { u.misused = true; } }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(L1, |s: &S| s.slots.iter().all(|x| !matches!(x, Some((_, None))))),
            invariant(L3, |s: &S| !s.clobbered),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property(L2, |o: &S, _a: &A, n: &S| n.misused == o.misused)]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], [$($v:expr),*]) => {
        pub struct $t;
        impl CatalogObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Vec<Variant> { vec![$($v),*] }
        }
    };
}

fn v(cfg: Cfg, law: &'static str, findings: &'static [&'static str]) -> Variant { Variant { cfg, law, findings } }

// BM25 indexes (and the index handle over them): read under USE GRAPH without checking the graph they were built for
// (F-0707); an index with no recorded graph is read as the default graph's (F-0705).
object!(Bm25IndexGraphUnchecked, "bm25-index-graph-unchecked", ["07/bm25-index", "17/index-handle"],
        [v(Cfg { read_checked: false, ..CANON }, L2, &["F-0707"]), v(Cfg { records: false, ..CANON }, L1, &["F-0705"]),
         v(Cfg { records: false, ..CANON }, L2, &["F-0705"])]);
// IVF indexes: the fused search may read an IVF index built for another graph (F-0609).
object!(IvfIndexGraphUnchecked, "ivf-index-graph-unchecked", ["06/ivf-index"], [v(Cfg { read_checked: false, ..CANON }, L2, &["F-0609"])]);
object!(IdentityFailOpen, "identity-fail-open", ["06/registry-row"], [v(Cfg { fail_open: true, ..CANON }, L2, &["F-0601", "F-0602", "F-0603", "F-0613"])]);
object!(ShortHashName, "short-hash-name", ["09/compiled-shape"], [v(Cfg { naming: Naming::ShortHash, ..CANON }, L3, &["F-0901", "F-C0901"])]);
object!(Canonical, "canonical", ["06/route", "15/table-mapping", "10/native-route", "15/code-crosswalk"], [v(CANON, "", &[])]);

fn instance_checks<O: CatalogObject>(o: &O) -> Vec<Outcome> {
    let n = o.name();
    let mut out = vec![];
    for (k, var) in o.as_built().into_iter().enumerate() {
        let m = Machine { o, c: var.cfg };
        let id = if k == 0 { format!("catalog-{n}-as-built") } else { format!("catalog-{n}-as-built-{}-{}", &var.law[..6], var.findings[0]) };
        if var.law.is_empty() {
            out.push(check_keep(&id, meta("M-12", "catalog", n, o.objects(), "as-built", "safety", "all", var.findings, ""), Expect::Pass, &Keep::safety(&m)));
        } else {
            out.push(check_keep(&id, meta("M-12", "catalog", n, o.objects(), "as-built", "safety", var.law, var.findings, ""), Expect::Violation(var.law), &Keep::only(&m, &[var.law])));
        }
    }
    let rv = Machine { o, c: CANON };
    out.push(check_keep(&format!("catalog-{n}-reviewed"), meta("M-12", "catalog", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&Bm25IndexGraphUnchecked));
    out.extend(instance_checks(&IvfIndexGraphUnchecked));
    out.extend(instance_checks(&IdentityFailOpen));
    out.extend(instance_checks(&ShortHashName));
    out.extend(instance_checks(&Canonical));
    let o = &Canonical;
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check_keep(id, meta("M-12", "catalog", "canonical", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("catalog-control-C1-unchecked-read", L2, Cfg { read_checked: false, ..CANON }));
    out.push(ctl("catalog-control-C2-short-hash", L3, Cfg { naming: Naming::ShortHash, ..CANON }));
    out.push(ctl("catalog-control-C3-no-record", L1, Cfg { records: false, ..CANON }));
    out.push(ctl("catalog-control-C4-fail-open", L2, Cfg { fail_open: true, ..CANON }));
    let rv = Machine { o, c: CANON };
    let sm = || meta("M-12", "catalog", "canonical", Canonical.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("catalog-sharp-three-artifacts", sm(), &rv, "never: three artifacts bound", |s: &S| s.slots.iter().all(|x| x.is_some())));
    out
}
