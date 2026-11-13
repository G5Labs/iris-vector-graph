//! Machine 5: a retried commit with post-commit properties, across erasure and redaction (F-1101, F-1306).
//!
//! A changeset creates tenant A's node n with retry key k and a post-commit property p on n
//! (iris_vector_graph/ledger/client.py:430-435). Post-commit properties are written by plain SQL after the
//! commit, outside the revision (`_apply_post_commit_properties`, client.py:445-487), and rdf_props has no foreign
//! key to nodes. The ledger answers a retry with a bound key and the same fingerprint as a replay
//! (Ledger.cls:457-462); the fingerprint leaves post-commit properties out (changeset.py:370).
//! - `as-built`: the client applies post-commit properties after a replayed commit too (client.py:430-435 has no
//!   `replayed` check).
//! - `reviewed`: a replayed commit applies none.
//!
//! Properties:
//! - after A is erased, nothing but a new recorded commit into A makes A's content live again;
//! - always possibly: A ends erased and redacted (the operator can always finish the erasure).
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Key { Unused, Bound, Redacted }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S5 {
    pub node: bool,
    pub prop: bool,
    pub key: Key,
    /// ghost: A was erased and nothing recorded has written into A since
    pub erased: bool,
    pub redacted: bool,
    pub retries: u8,
    pub erases: u8,
}

#[derive(Clone, Debug)]
pub enum A5 { Commit, Retry, Erase, Redact }

pub struct M5 { pub design: Design }

impl Model for M5 {
    type State = S5;
    type Action = A5;
    fn init_states(&self) -> Vec<S5> {
        vec![S5 { node: false, prop: false, key: Key::Unused, erased: false, redacted: false, retries: 0, erases: 0 }]
    }
    fn actions(&self, _: &S5) -> Vec<A5> { vec![A5::Commit, A5::Retry, A5::Erase, A5::Redact] }
    fn next(&self, s: &S5, a: &A5) -> Option<S5> {
        let mut u = s.clone();
        match a {
            A5::Commit => {
                if s.key != Key::Unused { return None; }
                u.node = true; u.prop = true; u.key = Key::Bound; u.erased = false; u.redacted = false;
            }
            A5::Retry => {
                if s.retries >= 2 { return None; }
                u.retries += 1;
                match s.key {
                    Key::Bound => { if self.design == Design::AsBuilt { u.prop = true; } }
                    Key::Redacted | Key::Unused => return None, // refused (idempotency_redacted) or a first commit
                }
            }
            A5::Erase => {
                if !(s.node || s.prop) || s.erases >= 2 { return None; }
                u.node = false; u.prop = false; u.erased = true; u.erases += 1;
            }
            A5::Redact => {
                if s.node || s.prop || s.key != Key::Bound { return None; } // target_live is refused
                u.key = Key::Redacted; u.redacted = true;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S5>> {
        vec![invariant("after erasure only a recorded commit makes the tenant's content live again",
            |s: &S5| !(s.erased && (s.node || s.prop)))]
    }
    fn always_possibly(&self) -> Vec<Invariant<S5>> {
        vec![invariant("erased and redacted", |s: &S5| s.key == Key::Unused || (s.redacted && !s.node && !s.prop))]
    }
}

pub fn show(c: &Counterexample<S5, A5>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<7} node={} post-commit property={} key={:?} erased={} redacted={}\n", i + 1,
                        format!("{:?}", a), s.node, s.prop, s.key, s.erased, s.redacted);
    }
    out
}
