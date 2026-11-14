//! M-06 Snapshot save and restore (axioms AX-12, AX-05, AX-10). Generic machine over `SnapshotObject`.
//!
//! Abstract state: four live stores (0 rows, 1 routed node vectors, 2 routed edge vectors, 3 temporal aggregates),
//! each a small value; the ledger head (a commit writes rows and moves the head); at most one archive with the
//! values of the stores it carries and the head it saw; the live state at the save (ghost) and whether anything was
//! written since. Save copies the carried stores (iris_vector_graph/_engine/snapshot.py:299-344, 960-1025). A
//! replacing restore replaces the live stores wholesale (uncarried stores end empty) and, as built, lays the
//! archived ledger over the live one (snapshot.py:1554-1588, F-1801). A merge restore combines rows and, as built,
//! overwrites the temporal aggregates (snapshot.py:1679, F-1805).
//!
//! Laws: M06-L1 (invariant) a replacing restore with nothing written since the save gives the saved state on every
//! store; M06-L2 (action) a restore never lowers the head (it refuses); M06-L3 (action) a merge restore adds the
//! archived aggregates to the live ones. Bounds: 2 writes, 1 save, 2 restores.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Head { Lays, Refuses }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Agg { Overwrite, Combine }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub carried: u8, pub head: Head, pub agg: Agg }

pub trait SnapshotObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Cfg;
    fn reviewed(&self) -> Cfg { Cfg { carried: 0b1111, head: Head::Refuses, agg: Agg::Combine } }
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub live: [u8; 4],
    pub head: u8,
    pub archive: Option<([u8; 4], u8)>,
    pub saved: [u8; 4],
    pub wrote_since: bool,
    pub rt_ok: bool,
    pub refused: u8,
    pub n: [u8; 3],
}

#[derive(Clone, Debug)]
pub enum A { Write(u8), Save, RestoreReplace, RestoreMerge }

pub struct Machine<'a, O: SnapshotObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M06-L1 round trip on every store";
pub const L2: &str = "M06-L2 a restore never lowers the head";
pub const L3: &str = "M06-L3 a merge restore combines aggregates";

impl<'a, O: SnapshotObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { live: [1, 1, 1, 1], head: 1, archive: None, saved: [0; 4], wrote_since: false, rt_ok: true, refused: 0, n: [0; 3] }]
    }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Write(0), A::Write(1), A::Write(2), A::Write(3), A::Save, A::RestoreReplace, A::RestoreMerge] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = self.c;
        let mut u = s.clone();
        match *a {
            A::Write(k) => {
                if s.n[0] >= 2 { return None; }
                u.n[0] += 1;
                u.live[k as usize] = (s.live[k as usize] + 1) % 3;
                if k == 0 { u.head += 1; }
                u.wrote_since = true;
            }
            A::Save => {
                if s.n[1] >= 1 { return None; }
                u.n[1] += 1;
                let mut arch = [255u8; 4];
                for k in 0..4 { if c.carried & (1 << k) != 0 { arch[k] = s.live[k]; } }
                u.archive = Some((arch, s.head)); u.saved = s.live; u.wrote_since = false;
            }
            A::RestoreReplace => {
                let (arch, ah) = s.archive?;
                if s.n[2] >= 2 { return None; }
                u.n[2] += 1;
                if c.head == Head::Refuses && s.head > ah { u.refused += 1; return Some(u); }
                for k in 0..4 { u.live[k] = if arch[k] == 255 { 0 } else { arch[k] }; }
                if c.head == Head::Lays { u.head = ah; }
                if !s.wrote_since { u.rt_ok = u.live == s.saved; }
            }
            A::RestoreMerge => {
                let (arch, _) = s.archive?;
                if s.n[2] >= 2 { return None; }
                u.n[2] += 1;
                for k in 0..3 { if arch[k] != 255 { u.live[k] = s.live[k].max(arch[k]); } }
                if arch[3] != 255 {
                    u.live[3] = match c.agg { Agg::Overwrite => arch[3], Agg::Combine => (s.live[3] + arch[3]).min(9) };
                }
                u.wrote_since = true;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> { vec![invariant(L1, |s: &S| s.rt_ok)] }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L2, |o: &S, a: &A, n: &S| !matches!(a, A::RestoreReplace | A::RestoreMerge) || n.head >= o.head),
            action_property(L3, |o: &S, a: &A, n: &S| match (a, o.archive) {
                (A::RestoreMerge, Some((arch, _))) if arch[3] != 255 => n.live[3] == (o.live[3] + arch[3]).min(9),
                _ => true,
            }),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl SnapshotObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Cfg { $ab }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

// The archive carries no routed edge vectors (F-C1804; also F-1803 graph and metadata lost, F-1804 values as text).
object!(EdgeVectorsMissing, "edge-vectors-missing", ["18/snapshot-archive"],
        Cfg { carried: 0b1011, head: Head::Refuses, agg: Agg::Combine }, L1, ["F-C1804", "F-1803", "F-1804"]);
// A replacing restore lays the archive's ledger over the live one (F-1801).
object!(ReplacingRestore, "replacing-restore", ["18/namespace"],
        Cfg { carried: 0b1111, head: Head::Lays, agg: Agg::Combine }, L2, ["F-1801"]);
// A merge restore overwrites temporal aggregates (F-1805).
object!(MergeAggregates, "merge-aggregates", ["18/namespace"],
        Cfg { carried: 0b1111, head: Head::Refuses, agg: Agg::Overwrite }, L3, ["F-1805"]);

fn instance_checks<O: SnapshotObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, c: o.as_built() };
    let rv = Machine { o, c: o.reviewed() };
    vec![
        check(&format!("snapshot-{n}-as-built"), meta("M-06", "snapshot", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])),
        check(&format!("snapshot-{n}-reviewed"), meta("M-06", "snapshot", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)),
    ]
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&EdgeVectorsMissing));
    out.extend(instance_checks(&ReplacingRestore));
    out.extend(instance_checks(&MergeAggregates));
    let o = &EdgeVectorsMissing;
    let r = o.reviewed();
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check(id, meta("M-06", "snapshot", "edge-vectors-missing", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("snapshot-control-C1-store-left-out", L1, Cfg { carried: 0b0111, ..r }));
    out.push(ctl("snapshot-control-C2-head-laid-over", L2, Cfg { head: Head::Lays, ..r }));
    out.push(ctl("snapshot-control-C3-aggregates-overwritten", L3, Cfg { agg: Agg::Overwrite, ..r }));
    let rv = Machine { o, c: r };
    let sm = || meta("M-06", "snapshot", "edge-vectors-missing", EdgeVectorsMissing.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("snapshot-sharp-restore-refused", sm(), &rv, "never: a replacing restore refused after a later commit", |s: &S| s.refused > 0));
    out.push(reach("snapshot-sharp-round-trip", sm(), &rv, "never: a replacing restore after later writes to non-ledger stores",
                   |s: &S| s.n[2] >= 1 && s.n[1] == 1 && s.refused == 0 && s.live == s.saved && s.n[0] >= 1));
    out
}
