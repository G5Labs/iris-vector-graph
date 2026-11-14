//! M-11 Capability gate (axioms AX-13, AX-03). Generic machine over `CapObject`.
//!
//! Abstract state: the store's value, whether a server file was read or written, how many calls were made. A call
//! names a caller (credential: none, wrong, ok; role: read-write or read-only) and a route of the object's entry
//! point: `Read`, `Write`, `File` (reads, writes or deletes a server file, or runs caller text as code). A route may
//! check the credential (key or privilege) and the read-only role before its effect (docs/ADMIN_GUIDE.md:824-840;
//! spec 253 FR-011).
//!
//! Laws: M11-L1 (action) a read-only caller changes nothing; M11-L2 (action) with credentials on, a caller without
//! a valid credential is refused before any effect or answer; M11-L3 (action) no route touches server files or runs caller
//! text. Bounds: 2 calls.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Kind { Read, Write, File }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Route { pub kind: Kind, pub key_check: bool, pub ro_check: bool }

pub const R_READ: Route = Route { kind: Kind::Read, key_check: true, ro_check: true };
pub const R_WRITE: Route = Route { kind: Kind::Write, key_check: true, ro_check: true };

pub trait CapObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Vec<Route>;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub store: u8, pub files: bool, pub calls: u8, pub unauth_answer: bool }

#[derive(Clone, Debug)]
pub struct A { pub key: u8, pub ro: bool, pub route: u8 }

pub struct Machine<'a, O: CapObject> { pub o: &'a O, pub routes: Vec<Route> }

pub const L1: &str = "M11-L1 a read-only caller changes nothing";
pub const L2: &str = "M11-L2 no valid credential, no effect";
pub const L3: &str = "M11-L3 no server-file or code capability";

impl<'a, O: CapObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { store: 0, files: false, calls: 0, unauth_answer: false }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for key in 0..3 { for ro in [false, true] { for r in 0..self.routes.len() as u8 { v.push(A { key, ro, route: r }); } } }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        if s.calls >= 2 { return None; }
        let r = self.routes[a.route as usize];
        let mut u = s.clone();
        u.calls += 1;
        if r.key_check && a.key != 2 { return Some(u); }
        if r.ro_check && a.ro && r.kind != Kind::Read { return Some(u); }
        if a.key != 2 { u.unauth_answer = true; }
        match r.kind { Kind::Read => {}, Kind::Write => { u.store = (s.store + 1) % 3; }, Kind::File => { u.files = true; } }
        Some(u)
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L1, |o: &S, a: &A, n: &S| !a.ro || (n.store == o.store && n.files == o.files)),
            action_property(L2, |o: &S, a: &A, n: &S| a.key == 2 || (n.store == o.store && n.files == o.files && n.unauth_answer == o.unauth_answer)),
            action_property(L3, |o: &S, _a: &A, n: &S| n.files == o.files),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], [$($r:expr),*], $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl CapObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Vec<Route> { vec![$($r),*] }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

// The HTTP server with IVG_API_KEY and IVG_READ_ONLY set: every route checks both (ADMIN_GUIDE.md:824-840).
object!(HttpServer, "http-server", ["16/cypher-http-call", "16/bolt-session-with-a-key-set", "17/client-request", "17/namespace", "17/link"], [R_READ, R_WRITE], "", []);
// The demo server's write routes need no key (src/iris_demo_server/app.py:1-22, F-1614).
object!(DemoServer, "demo-server", ["16/rest-web-app-path"], [R_READ, Route { key_check: false, ..R_WRITE }], L2, ["F-1614"]);
// execute_aql ignores read-only (aql/translator.py:50-58, 154-168, F-0814).
object!(Aql, "aql", ["08/cypher-call"], [R_READ, Route { ro_check: false, ..R_WRITE }], L1, ["F-0814"]);
// AQL text and a dotted function name pasted into Cypher / SQL text: caller text runs as code (F-0815).
object!(AqlCodeText, "aql-code-text", ["08/cypher-call"], [R_READ, Route { kind: Kind::File, ..R_READ }], L3, ["F-0815", "F-0814"]);
// Graph.KG.Snapshot's file helpers reachable by any Native API caller (Snapshot.cls:4-73, F-C1803; F-1806).
object!(SnapshotFileHelpers, "snapshot-file-helpers", ["18/snapshot-archive"], [R_READ, Route { kind: Kind::File, key_check: false, ro_check: false }], L3, ["F-C1803", "F-1806"]);
// The native executor's privilege check lives in the engine only (Exec.cls:32-72, F-0908).
object!(PrivilegeInEngineOnly, "privilege-in-engine-only", ["09/engine-native-path"], [R_READ, Route { kind: Kind::Read, key_check: false, ro_check: true }], L2, ["F-0908"]);

fn instance_checks<O: CapObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, routes: o.as_built() };
    let rv = Machine { o, routes: vec![R_READ, R_WRITE] };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check(&format!("cap-{n}-as-built"), meta("M-11", "cap", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check(&format!("cap-{n}-as-built"), meta("M-11", "cap", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
        out.push(check(&format!("cap-{n}-reviewed"), meta("M-11", "cap", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    }
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&HttpServer));
    out.extend(instance_checks(&DemoServer));
    out.extend(instance_checks(&Aql));
    out.extend(instance_checks(&AqlCodeText));
    out.extend(instance_checks(&SnapshotFileHelpers));
    out.extend(instance_checks(&PrivilegeInEngineOnly));
    let o = &HttpServer;
    let ctl = |id: &str, law: &'static str, routes: Vec<Route>| {
        let m = Machine { o, routes };
        check(id, meta("M-11", "cap", "http-server", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("cap-control-C1-write-without-read-only-check", L1, vec![R_READ, Route { ro_check: false, ..R_WRITE }]));
    out.push(ctl("cap-control-C2-route-without-key-check", L2, vec![Route { key_check: false, ..R_WRITE }]));
    out.push(ctl("cap-control-C3-file-route", L3, vec![R_READ, Route { kind: Kind::File, ..R_WRITE }]));
    let rv = Machine { o, routes: vec![R_READ, R_WRITE] };
    let sm = || meta("M-11", "cap", "http-server", HttpServer.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("cap-sharp-keyed-write", sm(), &rv, "never: a keyed read-write caller writes", |s: &S| s.store != 0));
    out
}
