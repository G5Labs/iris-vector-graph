//! Family conn_mutex (module 16; premise P-1605; gate 3.5-lockplans): request threads sharing one IRIS DB-API
//! connection.
//!
//! P-1605 (experiment/playbook-uplift/trust/16.md:31-35): the driver declares `iris.dbapi.threadsafety = 1`; PEP 249
//! reads that as "threads may share the module, but not connections", where sharing means use "without wrapping it
//! using a mutex semaphore". The product's own statement of the rule: CHANGELOG.md:304-310 (4.6.5: "The driver does
//! not allow that ... Every endpoint now takes the lock").
//!
//! Abstraction: two request threads; each serves up to two requests on the one connection. A request is
//! `Acquire` (the route's mutex, if it takes one), `Exec` (a driver call is in flight: execute), `Fetch` (a second
//! driver call: the rows are read), `Release`, `Done`. The connection is "in use by t" from Exec to the end of Fetch.
//!
//! Designs:
//! - `HttpAsBuilt`: iris_vector_graph/cypher_api.py: every route reaches the engine through `_engine()` or
//!   `_run_cypher`, both holding `_engine_lock` (a threading.RLock) around the whole call, rows materialised inside
//!   (cypher_api.py:150-153, 220-224, 239-250, 268-283, 469-735).
//! - `SampleAsBuilt`: api/main.py:100-113 (`/health`, a plain def on the thread pool) and api/routers/cypher.py:89-97
//!   (`async def` on the event loop thread) use `app.state.engine.conn` with no mutex.
//! - `SampleReviewed`: the sample API with the HTTP server's discipline (one mutex around every use of
//!   `app.state.engine`, rows read inside it), the remedy F-1608 names.
//! - `ControlHealthUnlocked` (negative control): HttpAsBuilt with one route that skips the lock (4.6.4's /health).
//! - `ControlFetchAfterRelease` (negative control): HttpAsBuilt but the rows are fetched after the lock is released (a
//!   cursor that outlives the mutex).
//!
//! Properties: `MUTEX` no two threads use the connection at once (P-1605 / API-B4.5 / API-T8.2);
//! AG EF `DRAIN` every request can finish.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { HttpAsBuilt, SampleAsBuilt, SampleReviewed, ControlHealthUnlocked, ControlFetchAfterRelease }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum T { Idle, Locked, Exec, Fetch, Released }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub t: [T; 2],
    pub lock: Option<u8>,
    pub served: [u8; 2],
}

#[derive(Clone, Debug)]
pub enum A { Acquire(u8), Exec(u8), Fetch(u8), Release(u8), Done(u8) }

pub struct M { pub design: Design }

pub const MUTEX: &str = "MUTEX: no two threads use the one connection at once (P-1605, API-B4.5)";
pub const DRAIN: &str = "every request can finish";

impl M {
    /// whether thread i's route takes the mutex
    fn locks(&self, i: u8) -> bool {
        match self.design {
            Design::HttpAsBuilt | Design::SampleReviewed | Design::ControlFetchAfterRelease => true,
            Design::SampleAsBuilt => false,
            Design::ControlHealthUnlocked => i == 1,
        }
    }
    fn in_use(t: T) -> bool { matches!(t, T::Exec | T::Fetch) }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { t: [T::Idle; 2], lock: None, served: [0; 2] }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for i in 0..2 { v.extend([A::Acquire(i), A::Exec(i), A::Fetch(i), A::Release(i), A::Done(i)]); }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.served.iter().all(|n| *n <= 2) }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let late = self.design == Design::ControlFetchAfterRelease;
        match *a {
            A::Acquire(i) => {
                let k = i as usize;
                if s.t[k] != T::Idle || s.served[k] >= 2 { return None; }
                if self.locks(i) {
                    if s.lock.is_some() { return None; }
                    u.lock = Some(i);
                }
                u.t[k] = T::Locked;
            }
            A::Exec(i) => {
                let k = i as usize;
                if s.t[k] != T::Locked { return None; }
                u.t[k] = T::Exec;
            }
            A::Fetch(i) => {
                let k = i as usize;
                // as built the rows are read before the lock goes; the control releases first
                if late { if s.t[k] != T::Released { return None; } } else if s.t[k] != T::Exec { return None; }
                u.t[k] = T::Fetch;
            }
            A::Release(i) => {
                let k = i as usize;
                if late { if s.t[k] != T::Exec { return None; } } else if s.t[k] != T::Fetch { return None; }
                if s.lock == Some(i) { u.lock = None; }
                u.t[k] = T::Released;
            }
            A::Done(i) => {
                let k = i as usize;
                let ready = if late { s.t[k] == T::Fetch } else { s.t[k] == T::Released };
                if !ready { return None; }
                if late && s.lock == Some(i) { u.lock = None; }
                u.t[k] = T::Idle;
                u.served[k] += 1;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(MUTEX, |s: &S| !(M::in_use(s.t[0]) && M::in_use(s.t[1])))]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant(DRAIN, |s: &S| s.t == [T::Idle; 2])]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("16", "conn_mutex");
    let http = M { design: Design::HttpAsBuilt };
    let sample = M { design: Design::SampleAsBuilt };
    let sample_rv = M { design: Design::SampleReviewed };
    let c1 = M { design: Design::ControlHealthUnlocked };
    let c2 = M { design: Design::ControlFetchAfterRelease };
    vec![
        check("conn_mutex-http-as-built", md, fam, "as-built", "safety", Expect::Pass, &Keep::safety(&http)),
        check("conn_mutex-http-as-built-progress", md, fam, "as-built", "progress", Expect::Pass, &Keep::progress(&http)),
        check("conn_mutex-sample-as-built", md, fam, "as-built", "safety", Expect::Violation(MUTEX), &Keep::safety(&sample)),
        check("conn_mutex-sample-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&sample_rv)),
        check("conn_mutex-sample-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&sample_rv)),
        check("conn_mutex-control-health-unlocked", md, fam, "control", "safety", Expect::Violation(MUTEX), &Keep::safety(&c1)),
        check("conn_mutex-control-fetch-after-release", md, fam, "control", "safety", Expect::Violation(MUTEX), &Keep::safety(&c2)),
        reach("conn_mutex-http-reach-both-served", md, fam, "as-built", &http, "never: both threads served two requests",
              |s: &S| s.served == [2, 2]),
        reach("conn_mutex-http-reach-wait", md, fam, "as-built", &http, "never: a thread waits while the other uses the connection",
              |s: &S| s.lock.is_some() && s.t.contains(&T::Idle) && s.t.iter().any(|t| M::in_use(*t))),
    ]
}
