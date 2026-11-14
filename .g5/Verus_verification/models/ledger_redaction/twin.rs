// Executable twin of the redaction model's matching definitions.
//
// The functions inside verus! are verified to return exactly the spec functions of redaction.rs
// (match_string, has_prefix, matches). `main` and the hex/line adapter outside verus! are NOT
// verified: they parse the probe's observation lines and resolve each qualifier record's statement
// knowledge (in the redacting set? endpoints known?) from the observed ledger. That adapter is in the
// trust inventory (coverage.md).
//
// Build: $VERUS_BIN twin.rs --compile -o $RUN_DIR/verus/twin   (redaction.rs is a module of this crate)
// Input (stdin), one line each, strings hex-encoded UTF-8:
//   T <graph> <prefix> <separator>
//   R <seq> <ord> <op> <graph> <entity_id> <stmt> <has_ends 0|1> <s> <o> <redacting 0|1> <known 0|1> <ks> <ko>
// Output: <seq> <ord> Yes|No|Unknown, and first a line "M <match string hex>".
#![allow(unused_imports)]
use vstd::prelude::*;

mod redaction;
use redaction::*;

verus! {

pub struct ExecLive {
    pub op: u8,
    pub id: Vec<char>,
    pub stmt: u64,
    pub ends: Option<(Vec<char>, Vec<char>)>,
    pub graph: Vec<char>,
}

pub open spec fn op_of(code: u8) -> Op {
    if code == 0 { Op::CreateNode }
    else if code == 1 { Op::DeleteNode }
    else if code == 2 { Op::AddLabel }
    else if code == 3 { Op::RemoveLabel }
    else if code == 4 { Op::SetProp }
    else if code == 5 { Op::RemoveProp }
    else if code == 6 { Op::CreateRel }
    else if code == 7 { Op::DeleteRel }
    else if code == 8 { Op::SetQual }
    else if code == 9 { Op::RemoveQual }
    else if code == 10 { Op::CreateTemporal }
    else { Op::Redact }
}

pub open spec fn ends_view(e: Option<(Vec<char>, Vec<char>)>) -> Option<(Seq<char>, Seq<char>)> {
    match e {
        Some(p) => Some((p.0@, p.1@)),
        None => None,
    }
}

impl ExecLive {
    pub open spec fn view_live(&self) -> Live {
        Live { op: op_of(self.op), id: self.id@, stmt: self.stmt as nat, ends: ends_view(self.ends), graph: self.graph@, payload: 0, flags: 0 }
    }
}

/// The knowledge LedgerRedact.Matches would have about this one record's statement.
pub open spec fn know_for(stmt: nat, redacting: bool, known: Option<(Seq<char>, Seq<char>)>) -> Know {
    Know {
        redacting: if redacting { Set::empty().insert(stmt) } else { Set::empty() },
        ends: match known { Some(e) => Map::empty().insert(stmt, e), None => Map::empty() },
    }
}

pub fn exec_has_prefix(id: &Vec<char>, m: &Vec<char>) -> (r: bool)
    ensures r == has_prefix(id@, m@),
{
    if m.len() > id.len() {
        return false;
    }
    let mut i: usize = 0;
    while i < m.len()
        invariant
            m.len() <= id.len(),
            i <= m.len(),
            forall|j: int| 0 <= j < i ==> id@[j] == m@[j],
        decreases m.len() - i,
    {
        if id[i] != m[i] {
            assert(id@.subrange(0, m@.len() as int)[i as int] != m@[i as int]);
            return false;
        }
        i = i + 1;
    }
    assert(id@.subrange(0, m@.len() as int) =~= m@);
    true
}

pub fn exec_ends_with(p: &Vec<char>, sep: &Vec<char>) -> (r: bool)
    ensures r == ends_with(p@, sep@),
{
    if sep.len() > p.len() {
        return false;
    }
    let off = p.len() - sep.len();
    let mut i: usize = 0;
    while i < sep.len()
        invariant
            sep.len() <= p.len(),
            off == p.len() - sep.len(),
            i <= sep.len(),
            forall|j: int| 0 <= j < i ==> p@[off + j] == sep@[j],
        decreases sep.len() - i,
    {
        if p[off + i] != sep[i] {
            assert(p@.subrange(off as int, p@.len() as int)[i as int] != sep@[i as int]);
            return false;
        }
        i = i + 1;
    }
    assert(p@.subrange(off as int, p@.len() as int) =~= sep@);
    true
}

pub fn exec_match_string(prefix: &Vec<char>, sep: &Vec<char>) -> (r: Vec<char>)
    ensures r@ == match_string(prefix@, sep@),
{
    if prefix.len() == 0 {
        return Vec::new();
    }
    if exec_ends_with(prefix, sep) {
        return prefix.clone();
    }
    let mut out = prefix.clone();
    let mut i: usize = 0;
    while i < sep.len()
        invariant
            i <= sep.len(),
            out@ == prefix@ + sep@.subrange(0, i as int),
        decreases sep.len() - i,
    {
        out.push(sep[i]);
        i = i + 1;
        assert(out@ =~= prefix@ + sep@.subrange(0, i as int));
    }
    assert(sep@.subrange(0, sep@.len() as int) =~= sep@);
    out
}

fn vec_eq(a: &Vec<char>, b: &Vec<char>) -> (r: bool)
    ensures r == (a@ == b@),
{
    if a.len() != b.len() {
        return false;
    }
    let mut i: usize = 0;
    while i < a.len()
        invariant
            a.len() == b.len(),
            i <= a.len(),
            forall|j: int| 0 <= j < i ==> a@[j] == b@[j],
        decreases a.len() - i,
    {
        if a[i] != b[i] {
            return false;
        }
        i = i + 1;
    }
    assert(a@ =~= b@);
    true
}

pub fn exec_ends_hit(s: &Vec<char>, o: &Vec<char>, m: &Vec<char>) -> (r: bool)
    ensures r == ends_hit((s@, o@), m@),
{
    exec_has_prefix(s, m) || exec_has_prefix(o, m)
}

/// LedgerRedact.Matches for one record, given the knowledge the adapter resolved for its statement.
/// Tombstones are answered No by the adapter before this is called (matches(Tomb) == No).
pub fn exec_matches(
    r: &ExecLive,
    tg: &Vec<char>,
    tm: &Vec<char>,
    redacting: bool,
    known: &Option<(Vec<char>, Vec<char>)>,
) -> (out: u8)
    requires r.op <= 11,
    ensures
        out == 0 <==> matches(Rec::Live(r.view_live()), Target { g: tg@, m: tm@ }, know_for(r.stmt as nat, redacting, ends_view(*known))) == Tri::Yes,
        out == 1 <==> matches(Rec::Live(r.view_live()), Target { g: tg@, m: tm@ }, know_for(r.stmt as nat, redacting, ends_view(*known))) == Tri::No,
        out == 2 <==> matches(Rec::Live(r.view_live()), Target { g: tg@, m: tm@ }, know_for(r.stmt as nat, redacting, ends_view(*known))) == Tri::Unknown,
{
    let ghost k = know_for(r.stmt as nat, redacting, ends_view(*known));
    if r.op == 11 {
        return 1;
    }
    if !vec_eq(&r.graph, tg) {
        return 1;
    }
    if tm.len() == 0 {
        return 0;
    }
    if r.op <= 5 {
        return if exec_has_prefix(&r.id, tm) { 0 } else { 1 };
    }
    if r.op == 6 || r.op == 7 || r.op == 10 {
        return match &r.ends {
            Some(e) => if exec_ends_hit(&e.0, &e.1, tm) { 0 } else { 1 },
            None => 2,
        };
    }
    if redacting {
        assert(k.redacting.contains(r.stmt as nat));
        return 0;
    }
    match known {
        Some(e) => {
            assert(k.ends.contains_key(r.stmt as nat) && k.ends[r.stmt as nat] == (e.0@, e.1@));
            if exec_ends_hit(&e.0, &e.1, tm) { 0 } else { 1 }
        },
        None => {
            assert(!k.ends.contains_key(r.stmt as nat));
            2
        },
    }
}

} // verus!

// ------------------------------------------------------------------ unverified adapter (trusted)

fn unhex(s: &str) -> Vec<char> {
    if s == "-" {
        return Vec::new();
    }
    let bytes: Vec<u8> = (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap()).collect();
    String::from_utf8(bytes).unwrap().chars().collect()
}

fn hex(v: &Vec<char>) -> String {
    let s: String = v.iter().collect();
    s.as_bytes().iter().map(|b| format!("{:02x}", b)).collect()
}

fn main() {
    use std::io::BufRead;
    let stdin = std::io::stdin();
    let mut tg: Vec<char> = Vec::new();
    let mut tm: Vec<char> = Vec::new();
    for line in stdin.lock().lines() {
        let line = line.unwrap();
        let f: Vec<&str> = line.split('\t').collect();
        if f[0] == "T" {
            tg = unhex(f[1]);
            let prefix = unhex(f[2]);
            let sep = unhex(f[3]);
            tm = exec_match_string(&prefix, &sep);
            println!("M\t{}", if tm.is_empty() { "-".to_string() } else { hex(&tm) });
        } else if f[0] == "R" {
            let op: u8 = f[3].parse().unwrap();
            let ends = if f[7] == "1" { Some((unhex(f[8]), unhex(f[9]))) } else { None };
            let r = ExecLive { op, graph: unhex(f[4]), id: unhex(f[5]), stmt: f[6].parse().unwrap(), ends };
            let redacting = f[10] == "1";
            let known = if f[11] == "1" { Some((unhex(f[12]), unhex(f[13]))) } else { None };
            let out = if op > 11 { 1 } else { exec_matches(&r, &tg, &tm, redacting, &known) };
            println!("{}\t{}\t{}", f[1], f[2], ["Yes", "No", "Unknown"][out as usize]);
        }
    }
}
