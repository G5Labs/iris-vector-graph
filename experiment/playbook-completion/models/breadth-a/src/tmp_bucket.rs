//! Family tmp_bucket (module 05; finding F-0501; statement TMP-B1.7; read path TMP-T8.1).
//!
//! One graph, one source, one predicate, one time bucket holding two coordinates (two timestamps of the same
//! triple). State: ^KG("tout", g, ts, s, p, o) = weight per coordinate, the source's bucket counter
//! ^KG("bucket", g, b, s) (read by FindBursts and GetVelocity), and the bucket aggregate ^KG("tagg", g, b, s, p)
//! count and sum (read for whole buckets, TemporalIndex.cls:1455-1486).
//!
//! Operations:
//! - `Insert(c, w, mode)`: InsertEdge -> WriteStores (TemporalIndex.cls:46-130). Mode "update" kills edgeprop and
//!   skips the collision check (82-83); "insert"/"skip" return at an occupied coordinate (84-86). Every write that
//!   reaches line 97 sets tout, $Increments the bucket counter (100), and $Increments tagg count and sum (117-118).
//! - `Delete(c)`: DeleteTemporalEdge -> RemoveTemporalRow (TemporalIndex.cls:325-360): kills tout, decrements the
//!   bucket counter (killing it at <= 0), and rebuilds the tagg aggregate of the bucket from tout
//!   (RebuildBucketAggregate).
//! Weights 1 or 2; at most four operations.
//!
//! Designs: `AsBuilt`; `Reviewed` — an update at an occupied coordinate replaces the weight: it adds (new - old) to
//! the sum and changes neither count nor the bucket counter (CONTEXT.md:173-177: an upsert "replaces the edge");
//! `BucketCounted` (negative control) — the reviewed design whose update still $Increments the bucket counter.
//!
//! Invariant `TMP-B1.7`: the bucket aggregate and the bucket counter describe exactly the edges tout holds (count
//! equals the number of edges, sum equals their weights). The docstring's weaker contract ("aggregates remain
//! based on the original value", temporal.py:273-278; TemporalIndex.cls:77-79) also requires count = 1 after an
//! update, which the as-built design breaks too.
use explorer::*;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, BucketCounted }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mode { Insert, Update, Skip }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub tout: BTreeMap<u8, i8>, pub bucket: i8, pub count: i8, pub sum: i8, pub ops: u8 }

#[derive(Clone, Debug)]
pub enum A { Insert(u8, i8, Mode), Delete(u8) }

pub struct M { pub design: Design }

pub const INV: &str = "TMP-B1.7: the bucket aggregate and counter describe exactly the edges the bucket holds";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { tout: BTreeMap::new(), bucket: 0, count: 0, sum: 0, ops: 0 }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for c in 0..2 {
            for w in 1..=2 {
                for m in [Mode::Insert, Mode::Update, Mode::Skip] { v.push(A::Insert(c, w, m)); }
            }
            v.push(A::Delete(c));
        }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.ops < 4 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        u.ops += 1;
        match *a {
            A::Insert(c, w, m) => {
                let old = s.tout.get(&c).copied();
                if m != Mode::Update && old.is_some() { return Some(u); } // collision or skip: nothing written
                match (self.design, old) {
                    (Design::Reviewed, Some(o)) => { u.sum += w - o; }
                    (Design::BucketCounted, Some(o)) => { u.sum += w - o; u.bucket += 1; }
                    _ => { u.bucket += 1; u.count += 1; u.sum += w; }
                }
                u.tout.insert(c, w);
            }
            A::Delete(c) => {
                if !s.tout.contains_key(&c) { return None; }
                u.tout.remove(&c);
                u.bucket -= 1;
                if u.bucket <= 0 { u.bucket = 0; }
                u.count = u.tout.len() as i8;
                u.sum = u.tout.values().sum();
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| {
            let n = s.tout.len() as i8;
            s.count == n && s.bucket == n && s.sum == s.tout.values().sum::<i8>()
        })]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("05", "tmp_bucket");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::BucketCounted };
    vec![
        check("tmp_bucket-as-built-F0501", md, fam, "as-built", "safety", Expect::Violation(INV), &ab),
        check("tmp_bucket-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("tmp_bucket-control-bucket-counted", md, fam, "control", "safety", Expect::Violation(INV), &ct),
        reach("tmp_bucket-reviewed-reach-update", md, fam, "reviewed", &rv,
              "never: an update replaces the weight of an edge in a bucket holding two edges",
              |s: &S| s.tout.len() == 2 && s.sum == 3 && s.ops >= 3),
    ]
}
