//! Family vec_queue (module 06; finding F-0604, statement VEC-I7.18; decision HD-0604, assumption, statement
//! VEC-Q7.24).
//!
//! The embed queue ^EmbedQueue(reqId, ...) (iris_src/src/Graph/KG/EmbedQueue.cls:1-25), node-keyed: one entry per
//! node id (reqId = node id). Two workers run independently (HD-0604: "model both workers as independently
//! schedulable"): the IRIS worker `ProcessBatch` (EmbedQueue.cls:258-338; run by Graph.KG.EmbedQueueTask) and the
//! Python worker `process_embed_queue` (iris_vector_graph/_engine/embeddings.py:1900-1990: ClaimPendingBatch, embed,
//! SetResult). Neither claims an entry: ClaimPendingBatch is a scan of PENDING entries (EmbedQueue.cls:112-134), and
//! ProcessBatch tests status PENDING then works the entry (268).
//!
//! Worker steps per entry: `Claim` reads a PENDING entry with its text; `Embed` asks for the vector (it may fail:
//! no EMBEDDING() on the server, a failed %Prepare, SQLCODE <> 0, no row — EmbedQueue.cls:307-316); `Write`
//! INSERT OR UPDATE the vector (318-325) when one was made; `Mark` sets the status: as built "DONE" whenever no
//! exception was thrown, including when no vector was made (326-327; F-0604).
//! `Enqueue` (EmbedQueue.cls:35-60) sets the entry PENDING with new text (an overwrite); at most one re-enqueue.
//!
//! Designs:
//! - `AsBuilt`.
//! - `Reviewed` (HD-0604's minimal reviewed policy plus the finding's fix): a single active consumer (a namespace
//!   lock held from claim to mark), ERROR when no vector was made, and the mark is conditional on the entry's text
//!   not having been re-enqueued meanwhile (compare-and-set on a request version).
//! - `TwoConsumers` (negative control): the reviewed design without the single-consumer lock.
//!
//! Properties:
//! - `VEC-I7.18`: an entry is DONE only when its vector was made.
//! - `VEC-Q7.24/HD-0604`: no entry is worked by two workers at once.
//! - `VEC re-enqueue` (new candidate, no decision covers it): an entry marked DONE with a vector has one made from
//!   its current text (an overwrite enqueued while a worker held the old text is not lost).
//! - AG EF: the queue can always drain (no PENDING entry, no worker in flight).
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, TwoConsumers }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum St { Pending, Done, Error }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum W { Idle, Claimed(u8), Embedded(u8, bool), Written(u8, bool) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub status: St,
    pub text: u8,
    /// the text version the stored vector was made from
    pub vec: Option<u8>,
    pub w: [W; 2],
    pub lock: Option<u8>,
    pub enqueues: u8,
    pub works: u8,
}

#[derive(Clone, Debug)]
pub enum A { Claim(u8), Embed(u8, bool), Write(u8), Mark(u8), Enqueue }

pub struct M { pub design: Design }

pub const DONE: &str = "VEC-I7.18: an entry is DONE only when its vector was made";
pub const ONE: &str = "VEC-Q7.24/HD-0604: no entry is worked by two workers at once";
pub const LOST: &str = "VEC re-enqueue: a DONE entry's vector was made from its current text";
pub const DRAIN: &str = "the queue can drain";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { status: St::Pending, text: 0, vec: None, w: [W::Idle; 2], lock: None, enqueues: 0, works: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Enqueue];
        for i in 0..2 { v.extend([A::Claim(i), A::Embed(i, true), A::Embed(i, false), A::Write(i), A::Mark(i)]); }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.works < 4 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let single = self.design == Design::Reviewed;
        match *a {
            A::Claim(i) => {
                if s.w[i as usize] != W::Idle || s.status != St::Pending { return None; }
                if single { if s.lock.is_some() { return None; } u.lock = Some(i); }
                u.w[i as usize] = W::Claimed(s.text); u.works += 1;
            }
            A::Embed(i, ok) => {
                let W::Claimed(t) = s.w[i as usize] else { return None };
                u.w[i as usize] = W::Embedded(t, ok);
            }
            A::Write(i) => {
                let W::Embedded(t, ok) = s.w[i as usize] else { return None };
                if ok { u.vec = Some(t); }
                u.w[i as usize] = W::Written(t, ok);
            }
            A::Mark(i) => {
                let W::Written(t, ok) = s.w[i as usize] else { return None };
                match self.design {
                    Design::AsBuilt => u.status = St::Done,
                    Design::Reviewed | Design::TwoConsumers => {
                        if s.text == t { u.status = if ok { St::Done } else { St::Error }; }
                    }
                }
                u.w[i as usize] = W::Idle;
                if s.lock == Some(i) { u.lock = None; }
            }
            A::Enqueue => {
                if s.enqueues >= 1 { return None; }
                u.status = St::Pending; u.text += 1; u.enqueues += 1;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(DONE, |s: &S| s.status != St::Done || s.vec.is_some()),
            invariant(ONE, |s: &S| !(s.w[0] != W::Idle && s.w[1] != W::Idle)),
            invariant(LOST, |s: &S| s.status != St::Done || s.w.iter().any(|w| *w != W::Idle) || s.vec.is_none() || s.vec == Some(s.text)),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant(DRAIN, |s: &S| s.status != St::Pending && s.w == [W::Idle; 2])]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("06", "vec_queue");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::TwoConsumers };
    vec![
        check("vec_queue-as-built-F0604", md, fam, "as-built", "safety", Expect::Violation(DONE), &Keep::invariants(&ab, &[DONE])),
        check("vec_queue-as-built-HD0604", md, fam, "as-built", "safety", Expect::Violation(ONE), &Keep::invariants(&ab, &[ONE])),
        check("vec_queue-as-built-reenqueue", md, fam, "as-built", "safety", Expect::Violation(LOST), &Keep::invariants(&ab, &[LOST])),
        check("vec_queue-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&rv)),
        check("vec_queue-control-two-consumers", md, fam, "control", "safety", Expect::Violation(ONE), &Keep::safety(&ct)),
        check("vec_queue-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&rv)),
        check("vec_queue-as-built-progress", md, fam, "as-built", "progress", Expect::Pass, &Keep::progress(&ab)),
        reach("vec_queue-reviewed-reach-done", md, fam, "reviewed", &rv, "never: an entry is DONE with its vector",
              |s: &S| s.status == St::Done && s.vec == Some(s.text)),
        reach("vec_queue-reviewed-reach-error", md, fam, "reviewed", &rv, "never: an entry ends in ERROR",
              |s: &S| s.status == St::Error),
    ]
}
