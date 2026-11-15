//! M-08 Install, settings and version gate (axioms AX-09, AX-03). Generic machine over `InstallObject`.
//!
//! Abstract state: the namespace's recorded schema (none, 0 = Graph_KG, 1 = another name), the schemas engines use,
//! a foreign object that shares an unqualified name with one of the product's (another schema's index), the effective
//! value of one setting (0 job, 1 sync, 2 off; 3 is outside the domain), the ledger state, and two processes that
//! may enable the ledger for the first time at once (each checks the state, then takes the head lock and creates the
//! genesis revision, Ledger.cls:252-329).
//! As-built variants: first use accepts a namespace with no schema record (schema_name.py:220-235, F-0103); setup
//! runs an unqualified DROP INDEX (schema.py:655-658, F-0107); a setting outside its domain is read as another value
//! (Gen.cls:41-44, F-0903; rdflib 8 reported as rdflib absent, _rdf_utils.py:125-133, F-1506); the second of two
//! first enables fails instead of returning the genesis (F-1104).
//!
//! Laws: M08-L1 (invariant) at most one schema is recorded or used; M08-L2 (action) repeating setup or enable on a
//! current install answers ok and changes nothing; M08-L3 (action) setup leaves foreign objects; M08-L4 (action) a
//! setting outside its domain is refused and changes nothing. Bounds: 2 setups, 2 first uses, 2 settings.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub first_use_accepts_unrecorded: bool, pub drop_unqualified: bool, pub invalid_setting_accepted: bool, pub enable_race_errors: bool }

pub const CANON: Cfg = Cfg { first_use_accepts_unrecorded: false, drop_unqualified: false, invalid_setting_accepted: false, enable_race_errors: false };

pub trait InstallObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Cfg;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum En { Idle, Checked(bool), Done(bool) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub recorded: Option<u8>,
    pub used: u8,
    pub foreign: bool,
    pub mode: u8,
    pub enabled: bool,
    pub en: [En; 2],
    pub n: [u8; 3],
    pub last_ok: bool,
}

#[derive(Clone, Debug)]
pub enum A { Setup(u8), FirstUse(u8), SetMode(u8), Check(u8), Create(u8) }

pub struct Machine<'a, O: InstallObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M08-L1 one schema";
pub const L2: &str = "M08-L2 repeating setup changes nothing and answers ok";
pub const L3: &str = "M08-L3 setup touches only its schema";
pub const L4: &str = "M08-L4 a setting outside its domain is refused";

impl<'a, O: InstallObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { recorded: None, used: 0, foreign: true, mode: 0, enabled: false, en: [En::Idle; 2], n: [0; 3], last_ok: true }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::Setup(0), A::Setup(1), A::FirstUse(0), A::FirstUse(1), A::SetMode(1), A::SetMode(2), A::SetMode(3), A::Check(0), A::Check(1), A::Create(0), A::Create(1)]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = self.c;
        let mut u = s.clone();
        match *a {
            A::Setup(x) => {
                if s.n[0] >= 2 { return None; }
                u.n[0] += 1;
                match s.recorded {
                    None => { u.recorded = Some(x); u.used |= 1 << x; }
                    Some(r) if r == x => {}
                    Some(_) => { u.last_ok = false; return Some(u); }
                }
                if c.drop_unqualified { u.foreign = false; }
                u.last_ok = true;
            }
            A::FirstUse(x) => {
                if s.n[1] >= 2 { return None; }
                u.n[1] += 1;
                match s.recorded {
                    Some(r) if r == x => { u.used |= 1 << x; }
                    Some(_) => {}
                    None => { if c.first_use_accepts_unrecorded { u.used |= 1 << x; } }
                }
            }
            A::SetMode(v) => {
                if s.n[2] >= 2 { return None; }
                u.n[2] += 1;
                if v <= 2 { u.mode = v; } else if c.invalid_setting_accepted { u.mode = 1; }
            }
            A::Check(i) => { if s.en[i as usize] != En::Idle { return None; } u.en[i as usize] = En::Checked(!s.enabled); }
            A::Create(i) => {
                let En::Checked(saw_never) = s.en[i as usize] else { return None };
                if !s.enabled { u.enabled = true; u.en[i as usize] = En::Done(true); }
                else { u.en[i as usize] = En::Done(!(c.enable_race_errors && saw_never)); }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(L1, |s: &S| (s.used | s.recorded.map(|r| 1u8 << r).unwrap_or(0)).count_ones() <= 1)]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L2, |o: &S, a: &A, n: &S| match a {
                A::Setup(x) if o.recorded == Some(*x) => n.recorded == o.recorded && n.used == o.used && n.last_ok,
                A::Create(i) if o.enabled => n.en[*i as usize] == En::Done(true),
                _ => true,
            }),
            action_property(L3, |o: &S, a: &A, n: &S| !matches!(a, A::Setup(_)) || n.foreign == o.foreign),
            action_property(L4, |o: &S, a: &A, n: &S| !matches!(a, A::SetMode(3)) || n.mode == o.mode),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl InstallObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Cfg { $ab }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

object!(FirstUseNoRecord, "first-use-no-record", ["01/namespace"], Cfg { first_use_accepts_unrecorded: true, ..CANON }, L1, ["F-0103"]);
object!(UnqualifiedDrop, "unqualified-drop", ["01/setup-routine"], Cfg { drop_unqualified: true, ..CANON }, L3, ["F-0107"]);
object!(UncheckedSetting, "unchecked-setting", ["09/process-mode", "15/rdf-extra"], Cfg { invalid_setting_accepted: true, ..CANON }, L4, ["F-0903", "F-1506"]);
object!(ConcurrentFirstEnable, "concurrent-first-enable", ["11/ledger"], Cfg { enable_race_errors: true, ..CANON }, L2, ["F-1104"]);
object!(Canonical, "canonical", ["01/class-set", "01/legacy-object", "16/rest-web-app-path", "16/mcp-tool-set", "17/namespace", "03/ledger-state", "15/prefix-registry", "15/ivg-fhir-cli"], CANON, "", []);

fn instance_checks<O: InstallObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, c: o.as_built() };
    let rv = Machine { o, c: CANON };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check_keep(&format!("install-{n}-as-built"), meta("M-08", "install", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check_keep(&format!("install-{n}-as-built"), meta("M-08", "install", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
        out.push(check_keep(&format!("install-{n}-reviewed"), meta("M-08", "install", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    }
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&FirstUseNoRecord));
    out.extend(instance_checks(&UnqualifiedDrop));
    out.extend(instance_checks(&UncheckedSetting));
    out.extend(instance_checks(&ConcurrentFirstEnable));
    out.extend(instance_checks(&Canonical));
    let o = &Canonical;
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check_keep(id, meta("M-08", "install", "canonical", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("install-control-C1-first-use-accepts-any", L1, Cfg { first_use_accepts_unrecorded: true, ..CANON }));
    out.push(ctl("install-control-C2-unqualified-drop", L3, Cfg { drop_unqualified: true, ..CANON }));
    out.push(ctl("install-control-C3-setting-unchecked", L4, Cfg { invalid_setting_accepted: true, ..CANON }));
    out.push(ctl("install-control-C4-enable-race-errors", L2, Cfg { enable_race_errors: true, ..CANON }));
    let rv = Machine { o, c: CANON };
    let sm = || meta("M-08", "install", "canonical", Canonical.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("install-sharp-other-schema-refused", sm(), &rv, "never: a setup for another schema refused", |s: &S| !s.last_ok));
    out.push(reach("install-sharp-both-enables-ok", sm(), &rv, "never: both first enables answer ok", |s: &S| s.en == [En::Done(true); 2]));
    out
}
