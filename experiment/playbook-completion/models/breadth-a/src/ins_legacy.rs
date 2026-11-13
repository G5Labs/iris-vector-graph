//! Family ins_legacy (module 01; finding F-0101; statement INS-I7.6).
//!
//! `remove_legacy_objects(conn, iris_obj, dry_run=False)` (iris_vector_graph/_engine/legacy.py:654-686) walks the
//! IVG-owned legacy objects present, in manifest order. Modeled items: a view V (`_drop("DROP VIEW ...")` then
//! `removed = True` whatever `_drop` returned, 668-670; `_drop` answers False and logs at INFO on failure, 689-698),
//! a CREATE FUNCTION function F (DROP FUNCTION, falling back to deleting its class, 671-675), and two SqlProc items
//! P1, P2 projected by one shipped class C (the class is deleted once for P1, 677-681; P2 then gets
//! `removed = True`, 682-683, whether or not that delete succeeded). Each DROP or class delete may succeed or fail.
//!
//! Designs: `AsBuilt`; `Reviewed` — `removed` comes from `_drop`'s result for a view, and every item of a class
//! takes the result of that class's delete (the finding's fix); `FirstOnly` (negative control) — the reviewed view
//! rule, but a later item of a class still reports True.
//!
//! Invariant `INS-I7.6`: legacy removal says an object was removed only when it is gone (the data model's
//! `removed` is "whether it was dropped", specs/262-ivg-owned-sql-schema/data-model.md:50-60).
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, FirstOnly }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub next: u8,
    pub view: bool,
    pub func: bool,
    pub class: bool,
    /// reported `removed` for V, F, P1, P2
    pub removed: [Option<bool>; 4],
    pub class_result: Option<bool>,
}

#[derive(Clone, Debug)]
pub enum A { Step { first_ok: bool, fallback_ok: bool } }

pub struct M { pub design: Design }

pub const INV: &str = "INS-I7.6: legacy removal says an object was removed only when it is gone";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { next: 0, view: true, func: true, class: true, removed: [None; 4], class_result: None }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for f in [true, false] { for b in [true, false] { v.push(A::Step { first_ok: f, fallback_ok: b }); } }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let A::Step { first_ok, fallback_ok } = *a;
        match s.next {
            0 => {
                if !fallback_ok { return None; } // one choice per item: fallback unused for a view
                if first_ok { u.view = false; }
                u.removed[0] = Some(match self.design { Design::AsBuilt => true, _ => first_ok });
            }
            1 => {
                if first_ok { u.func = false; u.removed[1] = Some(true); }
                else { if fallback_ok { u.func = false; } u.removed[1] = Some(fallback_ok); }
            }
            2 => {
                if !fallback_ok { return None; }
                if first_ok { u.class = false; }
                u.class_result = Some(first_ok);
                u.removed[2] = Some(first_ok);
            }
            3 => {
                if !(first_ok && fallback_ok) { return None; } // no operation runs for P2
                u.removed[3] = Some(match self.design { Design::Reviewed => s.class_result.unwrap_or(false), _ => true });
            }
            _ => return None,
        }
        u.next += 1;
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| {
            let gone = [!s.view, !s.func, !s.class, !s.class];
            (0..4).all(|i| s.removed[i] != Some(true) || gone[i])
        })]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("01", "ins_legacy");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::FirstOnly };
    vec![
        check("ins_legacy-as-built-F0101", md, fam, "as-built", "safety", Expect::Violation(INV), &ab),
        check("ins_legacy-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("ins_legacy-control-first-item-only", md, fam, "control", "safety", Expect::Violation(INV), &ct),
        reach("ins_legacy-reviewed-reach-all-removed", md, fam, "reviewed", &rv,
              "never: every object is removed and reported so", |s: &S| s.next == 4 && s.removed == [Some(true); 4]),
        reach("ins_legacy-reviewed-reach-failure-reported", md, fam, "reviewed", &rv,
              "never: a failed class delete is reported for both of its items", |s: &S| s.next == 4 && s.removed[2] == Some(false) && s.removed[3] == Some(false)),
    ]
}
