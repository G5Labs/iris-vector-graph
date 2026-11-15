//! M1: one client call through the HTTP client and the Cypher HTTP server, with ambiguous acknowledgements
//! (HD-1603, HD-1702; modules 16 and 17).
//!
//! As built at 3eaa79cf:
//! - `IVGClient._post` (iris_vector_graph/sdk.py:209-228) resends the same POST /api/cypher after a
//!   `ConnectError`, a `TimeoutException` (the request may have been delivered and run) or a 5xx (e.g. a proxy's
//!   502/504 while the server still ran it), up to `max_retries` = 3, whatever the query does;
//! - `_run_cypher` (iris_vector_graph/cypher_api.py:250-268) runs `execute_cypher` again on a fresh connection after
//!   ANY exception of the first attempt, including one raised after IRIS committed (a connection lost between the
//!   commit and its reply: the server cannot tell the two apart).
//! Reviewed (decisions.md HD-1603 / HD-1702, one combined protocol): retry a read, or a write known not to have run
//! (the client's request never left: connect error; the server's statement never reached IRIS); an ambiguous write
//! outcome is reported as unknown, never retried and never reported as a definite failure.
//!
//! Properties:
//! - `at most once`: a write call applies its write at most once;
//! - `a definite failure means nothing was applied`: the caller told "failed" (not "unknown") for a write saw no
//!   effect of it;
//! - always possibly: the call completes (the client returns an answer);
//! - witnesses (sharpness): a read is retried after a timeout and succeeds; a write is applied exactly once and
//!   reported as success.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ControlClientRetriesWriteOnTimeout, ControlServerRetriesWriteAfterSend }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Op { Read, Write }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Outcome { Success, Failed, Unknown }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Client { Ready, Waiting, Done(Outcome) }

/// The server's handling of one delivered request.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Server { Idle, Executing, Replied(bool), Lost }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub op: Op,
    pub client: Client,
    pub client_attempts: u8,
    pub server: Server,
    pub server_attempts: u8,
    /// committed applications of the write (a read applies nothing)
    pub applied: u8,
    /// witness: a retry happened after a timeout
    pub retried_after_timeout: bool,
}

#[derive(Clone, Debug)]
pub enum A {
    /// the client sends; `delivered` false is a connect error (nothing left the client)
    Send { delivered: bool },
    /// one server attempt: `pre_send` the IRIS connection was found dead before the statement left (nothing ran and
    /// the server knows it; `committed`/`ack` are then unused); otherwise the statement ran, `committed` says whether
    /// IRIS committed it, and `ack` whether the server learned the outcome (false: the connection broke after the
    /// statement left, so the server sees an exception and cannot tell a commit from a rollback)
    Exec { pre_send: bool, committed: bool, ack: bool },
    /// the server's reply reaches the client, or is lost (client timeout / proxy 5xx)
    Reply { delivered: bool },
}

pub struct M { pub design: Design, pub client_max: u8, pub server_max: u8 }

impl M {
    pub fn new(design: Design) -> Self { M { design, client_max: 3, server_max: 2 } }

    fn client_retries_ambiguous(&self, op: Op) -> bool {
        match self.design {
            Design::AsBuilt | Design::ControlClientRetriesWriteOnTimeout => true,
            Design::Reviewed | Design::ControlServerRetriesWriteAfterSend => op == Op::Read,
        }
    }
    fn server_retries_after_send(&self, op: Op) -> bool {
        match self.design {
            Design::AsBuilt | Design::ControlServerRetriesWriteAfterSend => true,
            Design::Reviewed | Design::ControlClientRetriesWriteOnTimeout => op == Op::Read,
        }
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        [Op::Read, Op::Write].into_iter().map(|op| S { op, client: Client::Ready, client_attempts: 0,
            server: Server::Idle, server_attempts: 0, applied: 0, retried_after_timeout: false }).collect()
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Send { delivered: true }, A::Send { delivered: false },
                         A::Reply { delivered: true }, A::Reply { delivered: false }];
        for pre_send in [true, false] {
            for committed in [true, false] {
                for ack in [true, false] {
                    if pre_send && (committed || !ack) { continue; }
                    v.push(A::Exec { pre_send, committed, ack });
                }
            }
        }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        match *a {
            A::Send { delivered } => {
                if s.client != Client::Ready || s.client_attempts >= self.client_max { return None; }
                t.client_attempts += 1;
                if delivered {
                    t.client = Client::Waiting;
                    t.server = Server::Executing;
                    t.server_attempts = 0;
                } else if t.client_attempts >= self.client_max {
                    // nothing left the client on any attempt: a definite failure
                    t.client = Client::Done(Outcome::Failed);
                }
            }
            A::Exec { pre_send, committed, ack } => {
                if s.server != Server::Executing || s.server_attempts >= self.server_max { return None; }
                t.server_attempts += 1;
                let more = t.server_attempts < self.server_max;
                if pre_send {
                    // the IRIS connection was dead before the statement left: nothing ran, and the server knows it.
                    // Both designs may try again on a fresh connection.
                    t.server = if more { Server::Executing } else { Server::Replied(false) };
                    return Some(t);
                }
                if committed && s.op == Op::Write { t.applied += 1; }
                if ack {
                    // the server learned the outcome: rows, or the error of a rolled-back write
                    t.server = Server::Replied(committed || s.op == Op::Read);
                } else if self.server_retries_after_send(s.op) && more {
                    t.server = Server::Executing; // _reset_engine(); run it again
                } else if self.design == Design::AsBuilt || self.design == Design::ControlServerRetriesWriteAfterSend
                    || s.op == Op::Read {
                    // the exception reaches the handler: HTTP 400 with the error text (cypher_api.py:369-376)
                    t.server = Server::Replied(false);
                } else {
                    t.server = Server::Lost; // reviewed: a write whose outcome is unknown is reported as unknown
                }
            }
            A::Reply { delivered } => {
                let answer = match s.server { Server::Replied(ok) => Some(ok), Server::Lost => None, _ => return None };
                if s.client != Client::Waiting { return None; }
                t.server = Server::Idle;
                if delivered {
                    t.client = Client::Done(match answer {
                        Some(true) => Outcome::Success,
                        Some(false) => Outcome::Failed,
                        None => Outcome::Unknown,
                    });
                } else {
                    // timeout or a proxy's 5xx: the request may have run
                    if self.client_retries_ambiguous(s.op) && s.client_attempts < self.client_max {
                        t.client = Client::Ready;
                        t.retried_after_timeout = true;
                    } else if self.client_retries_ambiguous(s.op) {
                        // sdk.py:228 / :219: IVGClientError / IVGServerError after the last attempt
                        t.client = Client::Done(Outcome::Failed);
                    } else {
                        t.client = Client::Done(Outcome::Unknown);
                    }
                }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("at most once", |s: &S| s.applied <= 1),
            invariant("a definite failure means nothing was applied",
                      |s: &S| !(s.client == Client::Done(Outcome::Failed) && s.applied > 0)),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the call completes", |s: &S| matches!(s.client, Client::Done(_)))]
    }
}

/// Witness models: the goal is written as an invariant "goal is never reached"; the checker must find a trace.
pub struct Witness { pub m: M, pub goal: &'static str }

impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        match self.goal {
            "read retried after a timeout succeeds" => vec![invariant("read retried after a timeout succeeds", |s: &S|
                !(s.op == Op::Read && s.retried_after_timeout && s.client == Client::Done(Outcome::Success)))],
            _ => vec![invariant("write applied once and reported", |s: &S|
                !(s.op == Op::Write && s.applied == 1 && s.client == Client::Done(Outcome::Success)))],
        }
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps; init op={:?}\n", c.property, c.kind,
                          c.steps.len(), c.init.op);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<52} client={:?}/{} server={:?}/{} applied={}\n", i + 1, format!("{:?}", a),
                        s.client, s.client_attempts, s.server, s.server_attempts, s.applied);
    }
    out
}
