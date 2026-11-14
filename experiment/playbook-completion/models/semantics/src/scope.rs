//! M-09 Graph key and tenant scope (axiom AX-02). Generic machine over `ScopeObject`.
//!
//! Abstract state: two graphs (0 the default graph, 1 a named graph) and two node ids (0, 1) with overlapping ids
//! (spec 230: nodes unique on (graph_id, node_id)); content[g][i] in 0..2 (0 absent). Names: "" (0), "acme" (1), "0"
//! (2), "\x01" (3). The key of a name (GraphKey.cls:51-77): validated entries refuse "0" and control characters;
//! an unvalidated entry (nodes_edges.py:968-1015, F-0202) maps "0" onto the default graph's key 0. Reads: `Scoped`
//! (the graph's own content), `JoinAny` (an id's data taken from any graph that has it, F-0206, F-1507, F-1701),
//! `Merged` (an all-graphs walk that crosses graphs, F-0818..F-0820, F-1002, F-1008). Deletes: `Scoped`, `EveryGraph`
//! (delete by id in every graph, F-1503). Target predicates for the target "default graph, no prefix": erase and
//! liveness select graph 0's ids; the record match is graph-blind for node records (F-1304, F-1305, F-1105).
//!
//! Laws: M09-L1 (invariant) distinct accepted names have distinct keys; M09-L2 (action) a read answers its graph's
//! own content, an all-graphs read the union of the per-graph answers; M09-L3 (action) a write or delete to g leaves
//! the other graph; M09-L4 (invariant) the three predicates select the same (graph, id) pairs. Bounds: 3 writes.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Key { Validated, Unvalidated, IgnoresName }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Read { Scoped, JoinAny, Merged }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Del { Scoped, EveryGraph }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub key: Key, pub read: Read, pub del: Del, pub match_blind: bool }

pub const CANON: Cfg = Cfg { key: Key::Validated, read: Read::Scoped, del: Del::Scoped, match_blind: false };

pub trait ScopeObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Cfg;
    fn departs(&self) -> (&'static str, &'static [&'static str], &'static str);
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub content: [[u8; 2]; 2], pub accepted: u8, pub keys: [u8; 4], pub writes: u8, pub last_ok: bool }

#[derive(Clone, Debug)]
pub enum A { Write(u8, u8, u8), Delete(u8, u8), Read(u8, u8), AllRead(u8) }

pub struct Machine<'a, O: ScopeObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M09-L1 distinct names, distinct keys";
pub const L2: &str = "M09-L2 a read answers its own graph";
pub const L3: &str = "M09-L3 a write changes only its graph";
pub const L4: &str = "M09-L4 the target predicates agree";

impl<'a, O: ScopeObject> Machine<'a, O> {
    fn key(&self, name: u8) -> Option<u8> {
        match (self.c.key, name) {
            (Key::IgnoresName, _) => Some(0),
            (_, 0) => Some(0),
            (_, 1) => Some(1),
            (Key::Validated, _) => None,
            (Key::Unvalidated, 2) => Some(0),
            (Key::Unvalidated, _) => Some(2),
        }
    }
}

impl<'a, O: ScopeObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { content: [[1, 0], [2, 1]], accepted: 0, keys: [9; 4], writes: 0, last_ok: true }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for n in 0..4 { for i in 0..2 { v.push(A::Write(n, i, 2)); } }
        for g in 0..2 { for i in 0..2 { v.push(A::Delete(g, i)); v.push(A::Read(g, i)); } }
        v.push(A::AllRead(0)); v.push(A::AllRead(1));
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.writes <= 3 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = self.c;
        let mut u = s.clone();
        match *a {
            A::Write(name, i, v) => {
                if s.writes >= 3 { return None; }
                u.writes += 1;
                let Some(k) = self.key(name) else { return Some(u) };
                u.accepted |= 1 << name; u.keys[name as usize] = k;
                if k < 2 { u.content[k as usize][i as usize] = v; }
            }
            A::Delete(g, i) => {
                if s.writes >= 3 || s.content[g as usize][i as usize] == 0 { return None; }
                u.writes += 1;
                u.content[g as usize][i as usize] = 0;
                if c.del == Del::EveryGraph { u.content[1 - g as usize][i as usize] = 0; }
            }
            A::Read(g, i) => {
                let (g, i) = (g as usize, i as usize);
                let ans = match c.read {
                    Read::Scoped => s.content[g][i],
                    Read::JoinAny => if s.content[g][i] != 0 { s.content[g][i] } else { s.content[1 - g][i] },
                    Read::Merged => s.content[0][i].max(s.content[1][i]),
                };
                u.last_ok = ans == s.content[g][i];
            }
            A::AllRead(i) => {
                let i = i as usize;
                let per = [s.content[0][i], s.content[1][i]];
                let ans = match c.read { Read::Merged => { let m = per[0].max(per[1]); [m, m] }, _ => per };
                u.last_ok = ans == per;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        let blind = self.c.match_blind;
        vec![
            invariant(L1, |s: &S| (0..4).all(|a| (0..4).all(|b| a == b || s.accepted & (1 << a) == 0 || s.accepted & (1 << b) == 0 || s.keys[a] != s.keys[b]))),
            invariant(L4, move |_s: &S| (0..2).all(|g| { let erase = g == 0; let live = g == 0; let mtch = blind || g == 0; erase == live && live == mtch })),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L2, |_o: &S, a: &A, n: &S| !matches!(a, A::Read(..) | A::AllRead(_)) || n.last_ok),
            action_property(L3, |o: &S, a: &A, n: &S| match a {
                A::Delete(g, _) => n.content[1 - *g as usize] == o.content[1 - *g as usize],
                A::Write(..) => {
                    // the graph a write's key selects is its only changed graph
                    (0..2).filter(|&g| n.content[g] != o.content[g]).count() <= 1
                }
                _ => true,
            }),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $law:expr, [$($f:expr),*], $exc:expr) => {
        pub struct $t;
        impl ScopeObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Cfg { $ab }
            fn departs(&self) -> (&'static str, &'static [&'static str], &'static str) { ($law, &[$($f),*], $exc) }
        }
    };
}

object!(NameCheckMissing, "name-check-missing", ["02/graph-name"], Cfg { key: Key::Unvalidated, ..CANON }, L1, ["F-0202", "F-0203"], "");
object!(AllGraphsWalk, "all-graphs-walk", ["08/graph-scope"], Cfg { read: Read::Merged, ..CANON }, L2, ["F-0818", "F-0819", "F-0820"], "");
object!(UnscopedRead, "unscoped-read", ["10/default-graph-algorithm-call", "16/graph-a-caller-names", "17/link", "07/fused-search", "06/route", "10/native-route"],
        Cfg { read: Read::JoinAny, ..CANON }, L2,
        ["F-1002", "F-1006", "F-1008", "F-1013", "F-1001", "F-1603", "F-1604", "F-1701", "F-0609", "F-0711", "F-0605", "F-0616"], "");
object!(InternedNoGraph, "interned-no-graph-dimension", ["10/interned-snapshot"], Cfg { read: Read::Merged, ..CANON }, L2, [], "EXC-06");
object!(DeleteEveryGraph, "delete-every-graph", ["15/reifier"], Cfg { del: Del::EveryGraph, ..CANON }, L3, ["F-1503"], "");
object!(ThreePredicates, "three-predicates", ["13/redaction-target", "11/node-id"], Cfg { match_blind: true, ..CANON }, L4, ["F-1304", "F-1305", "F-1105", "F-1401"], "");
object!(Canonical, "canonical", ["03/node-in-one-graph", "03/edge-in-one-graph", "05/temporal-coordinates", "08/cypher-node", "08/cypher-edge", "12/graph-content"], CANON, "", [], "");

fn instance_checks<O: ScopeObject>(o: &O) -> Vec<Outcome> {
    let (law, f, exc) = o.departs();
    let n = o.name();
    let ab = Machine { o, c: o.as_built() };
    let rv = Machine { o, c: CANON };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check(&format!("scope-{n}-as-built"), meta("M-09", "scope", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        let design = if exc.is_empty() { "as-built" } else { "exception" };
        out.push(check(&format!("scope-{n}-as-built"), meta("M-09", "scope", n, o.objects(), design, "safety", law, f, exc), Expect::Violation(law), &Keep::only(&ab, &[law])));
        out.push(check(&format!("scope-{n}-reviewed"), meta("M-09", "scope", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    }
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&NameCheckMissing));
    out.extend(instance_checks(&AllGraphsWalk));
    out.extend(instance_checks(&UnscopedRead));
    out.extend(instance_checks(&InternedNoGraph));
    out.extend(instance_checks(&DeleteEveryGraph));
    out.extend(instance_checks(&ThreePredicates));
    out.extend(instance_checks(&Canonical));
    let o = &Canonical;
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check(id, meta("M-09", "scope", "canonical", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("scope-control-C1-key-ignores-name", L1, Cfg { key: Key::IgnoresName, ..CANON }));
    out.push(ctl("scope-control-C2-join-across-graphs", L2, Cfg { read: Read::JoinAny, ..CANON }));
    out.push(ctl("scope-control-C3-delete-every-graph", L3, Cfg { del: Del::EveryGraph, ..CANON }));
    out.push(ctl("scope-control-C4-graph-blind-match", L4, Cfg { match_blind: true, ..CANON }));
    let rv = Machine { o, c: CANON };
    let sm = || meta("M-09", "scope", "canonical", Canonical.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("scope-sharp-same-id-two-graphs-differ", sm(), &rv, "never: one id live in both graphs with different values",
                   |s: &S| s.content[0][1] != 0 && s.content[1][1] != 0 && s.content[0][1] != s.content[1][1]));
    out.push(reach("scope-sharp-named-write", sm(), &rv, "never: a write accepted under the named graph", |s: &S| s.accepted & 2 != 0));
    out
}
