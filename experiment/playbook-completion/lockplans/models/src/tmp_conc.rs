//! Family tmp_conc (module 05; gate 3.5-lockplans): concurrent temporal writers split at their unlocked program points.
//!
//! No temporal class takes a lock (Graph.KG.TemporalIndex; the only lock on these paths is the shared, never
//! excluding ^IVG.AdjW(graph) of the row writers, Adjacency.cls:25, 61-74). Two machines:
//!
//! `Agg` (LP-05-3, TMP-B4.2 / TMP-B8: the bucket aggregate describes the surviving edges). An insert writes tout and
//! the bucket counter (TemporalIndex.cls:97-102), then its row (:111, which may wait at WriterLock), then the
//! aggregate count/sum with $Increment (:117-118). A delete removes its tout entry and rebuilds the bucket's aggregate
//! from tout (:329-358, RebuildBucketAggregate :463-485) in one step.
//!
//! `Row` (LP-05-6, TMP-B2: a temporal edge's triple has its marked row; TMP-B2.4: when the last time of a triple goes,
//! its marked row goes). A delete of the triple's only time checks for another time (:334), removes the tout entry,
//! deletes the row (:337, Adjacency.cls:628-636) and later the ^KG("out") entry (Adjacency.cls:150-153, after its
//! WriterLock). An insert of a new time writes tout, then writes the row only when ^KG("out") is absent
//! (Adjacency.cls:577).
//!
//! Designs: `AsBuilt`; `Reviewed`: a per-(graph, source) lock held across each writer's steps (taken at its first
//! step, released at its last); `Control`: the lock taken only around the aggregate writes (Agg) / around the row and
//! out steps (Row), the explorer must still find the violation.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, Control }

// ------------------------------------------------------------------------------------------------ Agg
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SA {
    /// tout entries in the bucket: (edge id, weight)
    pub tout: Vec<(u8, u8)>,
    pub count: u8,
    pub sum: u8,
    pub ins: u8,  // 0 idle, 1 tout written, 2 row written, 3 done
    pub del: u8,  // 0 idle, 1 done
    pub lock: Option<u8>, // 0 insert, 1 delete
}

#[derive(Clone, Debug)]
pub enum AA { InsTout, InsRow, InsAgg, Del }

pub struct Agg { pub design: Design }

pub const AGG: &str = "TMP-B4.2/B8: at quiescence the bucket aggregate equals f(tout)";

impl Model for Agg {
    type State = SA;
    type Action = AA;
    fn init_states(&self) -> Vec<SA> {
        // edge 1 (weight 1) at ts 1000 is stored, its triple kept alive by ts 2000 in another bucket
        vec![SA { tout: vec![(1, 1)], count: 1, sum: 1, ins: 0, del: 0, lock: None }]
    }
    fn actions(&self, _: &SA) -> Vec<AA> { vec![AA::InsTout, AA::InsRow, AA::InsAgg, AA::Del] }
    fn next(&self, s: &SA, a: &AA) -> Option<SA> {
        let mut u = s.clone();
        let rv = self.design == Design::Reviewed;
        let ct = self.design == Design::Control;
        match a {
            AA::InsTout => {
                if s.ins != 0 { return None; }
                if rv { if s.lock.is_some() { return None; } u.lock = Some(0); }
                u.tout.push((2, 5)); u.ins = 1;
            }
            AA::InsRow => { if s.ins != 1 { return None; } u.ins = 2; }
            AA::InsAgg => {
                if s.ins != 2 { return None; }
                if ct && s.lock.is_some() && s.lock != Some(0) { return None; }
                u.count += 1; u.sum += 5; u.ins = 3;
                if s.lock == Some(0) { u.lock = None; }
            }
            AA::Del => {
                if s.del != 0 { return None; }
                if (rv || ct) && s.lock.is_some() { return None; }
                u.tout.retain(|e| e.0 != 1);
                u.count = u.tout.len() as u8;
                u.sum = u.tout.iter().map(|e| e.1).sum();
                u.del = 1;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<SA>> {
        vec![invariant(AGG, |s: &SA| {
            !(s.ins == 3 && s.del == 1) || (s.count as usize == s.tout.len() && s.sum == s.tout.iter().map(|e| e.1).sum::<u8>())
        })]
    }
}

// ------------------------------------------------------------------------------------------------ Row
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SR {
    /// the triple's times in tout (bit 0: ts 1000, bit 1: ts 5000)
    pub times: u8,
    pub row: bool,
    pub out: bool,
    pub del: u8, // 0 idle, 1 decided last (tout removed), 2 row deleted, 3 out removed / done
    pub ins: u8, // 0 idle, 1 tout written, 2 done
    pub lock: Option<u8>,
}

#[derive(Clone, Debug)]
pub enum AR { DelCheck, DelRow, DelOut, InsTout, InsRow }

pub struct Row { pub design: Design }

pub const ROW: &str = "TMP-B2/B2.4: at quiescence the triple has its row (and ^KG out) iff it has a time";

impl Model for Row {
    type State = SR;
    type Action = AR;
    fn init_states(&self) -> Vec<SR> { vec![SR { times: 1, row: true, out: true, del: 0, ins: 0, lock: None }] }
    fn actions(&self, _: &SR) -> Vec<AR> { vec![AR::DelCheck, AR::DelRow, AR::DelOut, AR::InsTout, AR::InsRow] }
    fn next(&self, s: &SR, a: &AR) -> Option<SR> {
        let mut u = s.clone();
        let rv = self.design == Design::Reviewed;
        let ct = self.design == Design::Control;
        let free_for = |me: u8| s.lock.is_none() || s.lock == Some(me);
        match a {
            AR::DelCheck => {
                if s.del != 0 { return None; }
                if rv { if !free_for(0) { return None; } u.lock = Some(0); }
                // TI:334: another time of the triple? remove this time either way
                let last = s.times & !1 == 0;
                u.times &= !1;
                u.del = if last { 1 } else { 3 };
                if !last && u.lock == Some(0) { u.lock = None; }
            }
            AR::DelRow => {
                if s.del != 1 { return None; }
                if ct { if !free_for(0) { return None; } u.lock = Some(0); }
                u.row = false; u.del = 2;
            }
            AR::DelOut => {
                if s.del != 2 { return None; }
                u.out = false; u.del = 3;
                if u.lock == Some(0) { u.lock = None; }
            }
            AR::InsTout => {
                if s.ins != 0 { return None; }
                if rv { if !free_for(1) { return None; } u.lock = Some(1); }
                u.times |= 2; u.ins = 1;
            }
            AR::InsRow => {
                if s.ins != 1 { return None; }
                if ct { if !free_for(1) { return None; } }
                if !s.out { u.row = true; u.out = true; } // Adjacency.cls:577: trusts ^KG("out")
                u.ins = 2;
                if u.lock == Some(1) { u.lock = None; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<SR>> {
        vec![invariant(ROW, |s: &SR| {
            !(s.del == 3 && s.ins == 2) || ((s.times != 0) == s.row && s.row == s.out)
        })]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("05", "tmp_conc");
    let (aa, ar) = (Agg { design: Design::AsBuilt }, Row { design: Design::AsBuilt });
    let (ra, rr) = (Agg { design: Design::Reviewed }, Row { design: Design::Reviewed });
    let (ca, cr) = (Agg { design: Design::Control }, Row { design: Design::Control });
    vec![
        check("tmp_conc-agg-as-built", md, fam, "as-built", "safety", Expect::Violation(AGG), &aa),
        check("tmp_conc-agg-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &ra),
        check("tmp_conc-agg-control-lock-around-agg-only", md, fam, "control", "safety", Expect::Violation(AGG), &ca),
        reach("tmp_conc-agg-reviewed-reach-both-done", md, fam, "reviewed", &ra, "never: insert and delete both done",
              |s: &SA| s.ins == 3 && s.del == 1),
        check("tmp_conc-row-as-built", md, fam, "as-built", "safety", Expect::Violation(ROW), &ar),
        check("tmp_conc-row-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rr),
        check("tmp_conc-row-control-lock-around-row-only", md, fam, "control", "safety", Expect::Violation(ROW), &cr),
        reach("tmp_conc-row-reviewed-reach-reinserted", md, fam, "reviewed", &rr, "never: the triple keeps ts 5000 with its row after the delete",
              |s: &SR| s.del == 3 && s.ins == 2 && s.times == 2 && s.row),
    ]
}
