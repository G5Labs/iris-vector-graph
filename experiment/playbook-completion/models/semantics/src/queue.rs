//! M-07 Background job and queue (axioms AX-14, AX-12, AX-11). Three generic machines over `QueueObject`.
//!
//! 1. `Entry` (laws M07-L1, M07-L2): one queue entry and two workers (copied in substance from
//!    models/breadth-a/src/vec_queue.rs, not shared). Worker steps: claim a PENDING entry with its text, make the
//!    result (may fail), write it, mark. `mark`: `Always` marks DONE whenever no exception was thrown, also when no
//!    result was made (EmbedQueue.cls:326-327, F-0604); `IfMade` marks ERROR then. `cas`: the mark applies only if the
//!    text was not re-enqueued meanwhile (without it, F-C0601). `single`: a namespace lock from claim to mark (the
//!    single-consumer premise, HD-0604; unenforced and undocumented at the pin: F-C0670).
//! 2. `Order` (laws M07-L3, M07-L4; F-C0605): three node ids, 0 and 1 low-collating, 2 high. Enqueue puts an id that
//!    is not pending into the queue (a node's text changes again: the same reqId is set PENDING again,
//!    EmbedQueue.cls:35-60, so low ids can arrive forever while the state stays finite). Serve takes one entry by the
//!    policy: `MinId` the first PENDING id in collation order (ClaimPendingBatch / ProcessBatch scan $Order(^EmbedQueue),
//!    EmbedQueue.cls:112-133, 258-268, batch size abstracted to 1), `Fifo` arrival order (the finding's remedy), `Lifo`
//!    (control). Ghost `overtakes`: entries served while id 2 is pending (saturating at 3).
//!    M07-L3 bounded overtaking: overtakes <= N-1 = 2. M07-L4 is checked with `fair_lasso`: no cycle of states in
//!    which id 2 stays pending contains a Serve step (the worker is weakly fair: whenever something is pending it
//!    serves again). AG EF "id 2 can still be served" is also run: it holds as built, which is why the bounded
//!    breadth-a model (finitely many arrivals) drained and could not show the finding.
//! 3. `Resume` (law M07-L4; F-C1303): a redaction run over three target records, each call bounded to one scanned
//!    record (max_batches); `Restart` scans from the first record on every call (as built, live
//!    `live-fc1303-bounded-resume`), `Persist` keeps the cursor (reviewed). AG EF: the run can always still finish.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mark { Always, IfMade }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct EntryCfg { pub mark: Mark, pub cas: bool, pub single: bool }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Order { MinId, Fifo, Lifo }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Cursor { Restart, Persist }

pub trait QueueObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
}

pub struct EmbedQueue;
impl QueueObject for EmbedQueue { fn name(&self) -> &'static str { "embed-queue" } fn objects(&self) -> &'static [&'static str] { &["06/queue-entry"] } }
pub struct BoundedRedactionResume;
impl QueueObject for BoundedRedactionResume { fn name(&self) -> &'static str { "bounded-redaction-resume" } fn objects(&self) -> &'static [&'static str] { &["13/redaction-run"] } }

pub const L1: &str = "M07-L1 done means done";
pub const L2: &str = "M07-L2 one worker per entry";
pub const L3: &str = "M07-L3 bounded overtaking";
pub const L4: &str = "M07-L4 every pending entry is served under fairness";
pub const L4R: &str = "M07-L4 a resumed run can always finish";
pub const AGEF: &str = "id 2 can still be served";

// ---------------------------------------------------------------- 1. Entry
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum St { Pending, Done, Error }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Wk { Idle, Claimed(u8), Made(u8, bool), Written(u8, bool) }
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ES { pub status: St, pub text: u8, pub vec: Option<u8>, pub w: [Wk; 2], pub lock: Option<u8>, pub enqueues: u8, pub works: u8 }
#[derive(Clone, Debug)]
pub enum EA { Claim(u8), Make(u8, bool), Write(u8), MarkStep(u8), Enqueue }

pub struct Entry<'a, O: QueueObject> { pub o: &'a O, pub c: EntryCfg }

impl<'a, O: QueueObject> Model for Entry<'a, O> {
    type State = ES;
    type Action = EA;
    fn init_states(&self) -> Vec<ES> { vec![ES { status: St::Pending, text: 0, vec: None, w: [Wk::Idle; 2], lock: None, enqueues: 0, works: 0 }] }
    fn actions(&self, _: &ES) -> Vec<EA> {
        let mut v = vec![EA::Enqueue];
        for i in 0..2 { v.extend([EA::Claim(i), EA::Make(i, true), EA::Make(i, false), EA::Write(i), EA::MarkStep(i)]); }
        v
    }
    fn within_bounds(&self, s: &ES) -> bool { s.works < 4 }
    fn next(&self, s: &ES, a: &EA) -> Option<ES> {
        let c = self.c;
        let mut u = s.clone();
        match *a {
            EA::Claim(i) => {
                if s.w[i as usize] != Wk::Idle || s.status != St::Pending { return None; }
                if c.single { if s.lock.is_some() { return None; } u.lock = Some(i); }
                u.w[i as usize] = Wk::Claimed(s.text); u.works += 1;
            }
            EA::Make(i, ok) => { let Wk::Claimed(t) = s.w[i as usize] else { return None }; u.w[i as usize] = Wk::Made(t, ok); }
            EA::Write(i) => { let Wk::Made(t, ok) = s.w[i as usize] else { return None }; if ok { u.vec = Some(t); } u.w[i as usize] = Wk::Written(t, ok); }
            EA::MarkStep(i) => {
                let Wk::Written(t, ok) = s.w[i as usize] else { return None };
                if !c.cas || s.text == t {
                    u.status = match c.mark { Mark::Always => St::Done, Mark::IfMade => if ok { St::Done } else { St::Error } };
                }
                u.w[i as usize] = Wk::Idle;
                if s.lock == Some(i) { u.lock = None; }
            }
            EA::Enqueue => { if s.enqueues >= 1 { return None; } u.status = St::Pending; u.text += 1; u.enqueues += 1; }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<ES>> {
        vec![
            invariant(L1, |s: &ES| s.status != St::Done || (s.vec.is_some() && (s.w.iter().any(|w| *w != Wk::Idle) || s.vec == Some(s.text)))),
            invariant(L2, |s: &ES| !(s.w[0] != Wk::Idle && s.w[1] != Wk::Idle)),
        ]
    }
}

// ---------------------------------------------------------------- 2. Order
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct OS { pub queue: Vec<u8>, pub high_enqueued: bool, pub overtakes: u8, pub served_high: bool }
#[derive(Clone, Debug)]
pub enum OA { Enqueue(u8), Serve }

pub struct OrderM<'a, O: QueueObject> { pub o: &'a O, pub order: Order }

impl<'a, O: QueueObject> Model for OrderM<'a, O> {
    type State = OS;
    type Action = OA;
    fn init_states(&self) -> Vec<OS> { vec![OS { queue: vec![], high_enqueued: false, overtakes: 0, served_high: false }] }
    fn actions(&self, _: &OS) -> Vec<OA> { vec![OA::Enqueue(0), OA::Enqueue(1), OA::Enqueue(2), OA::Serve] }
    fn next(&self, s: &OS, a: &OA) -> Option<OS> {
        let mut u = s.clone();
        match *a {
            OA::Enqueue(i) => {
                if s.queue.contains(&i) { return None; }
                if i == 2 { if s.high_enqueued { return None; } u.high_enqueued = true; }
                u.queue.push(i);
            }
            OA::Serve => {
                if s.queue.is_empty() { return None; }
                let k = match self.order {
                    Order::MinId => (0..s.queue.len()).min_by_key(|&k| s.queue[k]).unwrap(),
                    Order::Fifo => 0,
                    Order::Lifo => s.queue.len() - 1,
                };
                let id = u.queue.remove(k);
                if id == 2 { u.served_high = true; u.overtakes = 0; }
                else if s.queue.contains(&2) { u.overtakes = (s.overtakes + 1).min(3); }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<OS>> { vec![invariant(L3, |s: &OS| s.overtakes <= 2)] }
    fn always_possibly(&self) -> Vec<Invariant<OS>> { vec![invariant(AGEF, |s: &OS| !s.queue.contains(&2))] }
}

fn high_pending(s: &OS) -> bool { s.queue.contains(&2) }
fn is_serve(a: &OA) -> bool { matches!(a, OA::Serve) }

fn lasso<O: QueueObject>(id: &str, mt: Meta, expect: Expect, m: &OrderM<O>) -> Outcome {
    judge(id, mt, expect, fair_lasso(m, L4, high_pending, is_serve))
}

// ---------------------------------------------------------------- 3. Resume
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct RS { pub tomb: [bool; 3], pub cursor: u8 }
#[derive(Clone, Debug)]
pub enum RA { Call }

pub struct Resume<'a, O: QueueObject> { pub o: &'a O, pub cursor: Cursor }

impl<'a, O: QueueObject> Model for Resume<'a, O> {
    type State = RS;
    type Action = RA;
    fn init_states(&self) -> Vec<RS> { vec![RS { tomb: [false; 3], cursor: 0 }] }
    fn actions(&self, _: &RS) -> Vec<RA> { vec![RA::Call] }
    fn next(&self, s: &RS, _: &RA) -> Option<RS> {
        if s.tomb.iter().all(|t| *t) { return None; }
        let mut u = s.clone();
        let p = match self.cursor { Cursor::Restart => 0, Cursor::Persist => s.cursor } as usize;
        // one call scans one record (its batch budget) from p
        if p < 3 { u.tomb[p] = true; u.cursor = (p + 1) as u8; }
        Some(u)
    }
    fn always_possibly(&self) -> Vec<Invariant<RS>> { vec![invariant(L4R, |s: &RS| s.tomb.iter().all(|t| *t))] }
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    let q = &EmbedQueue;
    let mq = |design: &'static str, kind: &'static str, law: &'static str, f: &[&'static str]| meta("M-07", "queue", "embed-queue", q.objects(), design, kind, law, f, "");
    let rv_entry = EntryCfg { mark: Mark::IfMade, cas: true, single: true };
    // 1. entry
    let e = |c: EntryCfg| Entry { o: q, c };
    out.push(check_keep("queue-embed-queue-as-built-F0604", mq("as-built", "safety", L1, &["F-0604"]), Expect::Violation(L1),
                   &Keep::only(&e(EntryCfg { mark: Mark::Always, cas: true, single: true }), &[L1])));
    out.push(check_keep("queue-embed-queue-as-built-FC0601", mq("as-built", "safety", L1, &["F-C0601"]), Expect::Violation(L1),
                   &Keep::only(&e(EntryCfg { mark: Mark::IfMade, cas: false, single: true }), &[L1])));
    out.push(check_keep("queue-embed-queue-as-built-HD0604", mq("as-built", "safety", L2, &["F-C0670"]), Expect::Violation(L2),
                   &Keep::only(&e(EntryCfg { mark: Mark::Always, cas: false, single: false }), &[L2])));
    out.push(check_keep("queue-embed-queue-reviewed-entry", mq("reviewed", "safety", "all", &[]), Expect::Pass, &Keep::safety(&e(rv_entry))));
    out.push(check_keep("queue-control-C2-two-consumers", mq("control", "safety", L2, &[]), Expect::Violation(L2), &Keep::only(&e(EntryCfg { single: false, ..rv_entry }), &[L2])));
    out.push(check_keep("queue-control-C3-mark-always", mq("control", "safety", L1, &[]), Expect::Violation(L1), &Keep::only(&e(EntryCfg { mark: Mark::Always, ..rv_entry }), &[L1])));
    // 2. order (F-C0605)
    let ab = OrderM { o: q, order: Order::MinId };
    let rv = OrderM { o: q, order: Order::Fifo };
    let ct = OrderM { o: q, order: Order::Lifo };
    out.push(check_keep("queue-embed-queue-as-built-FC0605-overtaking", mq("as-built", "safety", L3, &["F-C0605"]), Expect::Violation(L3), &Keep::only(&ab, &[L3])));
    out.push(lasso("queue-embed-queue-as-built-FC0605-fair-lasso", mq("as-built", "liveness", L4, &["F-C0605"]), Expect::Violation(L4), &ab));
    out.push(check("queue-embed-queue-as-built-FC0605-agef-blind", mq("as-built", "progress", AGEF, &["F-C0605"]), Expect::Pass, &Keep::progress(&ab)));
    out.push(check_keep("queue-embed-queue-reviewed-overtaking", mq("reviewed", "safety", L3, &[]), Expect::Pass, &Keep::only(&rv, &[L3])));
    out.push(lasso("queue-embed-queue-reviewed-fair-lasso", mq("reviewed", "liveness", L4, &[]), Expect::Pass, &rv));
    out.push(check_keep("queue-control-C1-lifo-overtaking", mq("control", "safety", L3, &[]), Expect::Violation(L3), &Keep::only(&ct, &[L3])));
    out.push(lasso("queue-control-C1b-lifo-fair-lasso", mq("control", "liveness", L4, &[]), Expect::Violation(L4), &ct));
    out.push(reach("queue-sharp-fifo-serves-high", mq("reviewed", "sharpness", "", &[]), &rv, "never: id 2 served after waiting behind two others",
                   |s: &OS| s.served_high && s.queue.len() == 2));
    out.push(reach("queue-sharp-fifo-overtake-2", mq("reviewed", "sharpness", "", &[]), &rv, "never: id 2 overtaken twice",
                   |s: &OS| s.overtakes == 2 && s.queue.contains(&2)));
    // 3. bounded resume (F-C1303)
    let b = &BoundedRedactionResume;
    let mb = |design: &'static str, kind: &'static str, law: &'static str, f: &[&'static str]| meta("M-07", "queue", "bounded-redaction-resume", b.objects(), design, kind, law, f, "");
    out.push(check("queue-bounded-redaction-resume-as-built", mb("as-built", "progress", L4R, &["F-C1303"]), Expect::Violation(L4R),
                   &Keep::progress(&Resume { o: b, cursor: Cursor::Restart })));
    out.push(check("queue-bounded-redaction-resume-reviewed", mb("reviewed", "progress", L4R, &[]), Expect::Pass, &Keep::progress(&Resume { o: b, cursor: Cursor::Persist })));
    out.push(check("queue-control-C4-restart-scan", mb("control", "progress", L4R, &[]), Expect::Violation(L4R), &Keep::progress(&Resume { o: b, cursor: Cursor::Restart })));
    out.push(reach("queue-sharp-resume-finishes", mb("reviewed", "sharpness", "", &[]), &Resume { o: b, cursor: Cursor::Persist },
                   "never: all three records tombstoned", |s: &RS| s.tomb.iter().all(|t| *t)));
    out
}
