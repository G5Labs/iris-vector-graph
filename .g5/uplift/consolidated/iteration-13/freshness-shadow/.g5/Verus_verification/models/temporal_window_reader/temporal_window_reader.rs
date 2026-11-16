// IVG paged temporal window reader (spec 255): window_spec, the Python cursor's paging and handle release, and the
// server's source filter and page producer. Verus model, consolidated uplift (2026-11-14).
//
// Product baseline 3eaa79cf. A model and a transcription of the as-built code; it does not verify the product's
// Python or ObjectScript bodies. Bindings (path::symbol, pin lines) are in NOTES.md.
//
//   iris_vector_graph/_engine/temporal_window.py  window_spec :37-58, _server_call :67-71,
//       TemporalWindowCursor.__init__ :82-93, __next__ :102-113, close :115-124, __exit__ :129-130, __del__ :132-136
//   iris_src/src/Graph/KG/TemporalWindow.cls     Open :44-81 (filter mode :54-66), Next :85-91, Close :94-97,
//       Page :128-193 (stop at a full page :185, free at done :187-188), NextKey :196-239
//
// Run:  $VERUS_BIN temporal_window_reader.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

// ============================================================================ part 1: window_spec and the server filter

/// The caller's three source arguments. Python truthiness: a source or prefix that is None or "" is not named;
/// `sources` is named whenever it is not None, even when it is an empty list.
pub struct Args {
    pub source: Seq<char>,
    pub sources: Option<Seq<Seq<char>>>,
    pub prefix: Seq<char>,
}

/// What window_spec sends to Open (only the source keys; the other keys are not decisive here).
pub enum Sent {
    Refused,
    Spec { source: Option<Seq<char>>, sources: Option<Seq<Seq<char>>>, prefix: Option<Seq<char>> },
}

pub open spec fn named_count(a: Args) -> nat {
    (if a.source.len() > 0 { 1nat } else { 0nat }) + (if a.sources is Some { 1nat } else { 0nat })
        + (if a.prefix.len() > 0 { 1nat } else { 0nat })
}

/// temporal_window.py:43-55
pub open spec fn window_spec(a: Args) -> Sent {
    if named_count(a) > 1 {
        Sent::Refused
    } else {
        Sent::Spec {
            source: if a.source.len() > 0 { Some(a.source) } else { None },
            sources: sources_key(a.sources),
            prefix: if a.prefix.len() > 0 { Some(a.prefix) } else { None },
        }
    }
}

/// temporal_window.py:52-53: `if sources is not None: spec["sources"] = ...`
pub open spec fn sources_key(s: Option<Seq<Seq<char>>>) -> Option<Seq<Seq<char>>> {
    s
}

pub open spec fn is_prefix(p: Seq<char>, s: Seq<char>) -> bool {
    p.len() <= s.len() && s.subrange(0, p.len() as int) == p
}

/// TemporalWindow.cls:54-66 with NextKey: mode 1 (one source) when "source" is non-empty; else mode 2 (a list,
/// storing its non-empty names) when "sources" is defined; else a prefix when non-empty; else mode 0, every source.
/// A row's source is a global subscript, so it is never "" (premise of `s.len() > 0`).
pub open spec fn server_admits(sent: Sent, s: Seq<char>) -> bool {
    match sent {
        Sent::Refused => false,
        Sent::Spec { source, sources, prefix } => {
            if source is Some && source->0.len() > 0 {
                s == source->0
            } else if sources is Some {
                list_admits(sources->0, s)
            } else if prefix is Some && prefix->0.len() > 0 {
                is_prefix(prefix->0, s)
            } else {
                true
            }
        }
    }
}

/// Mode 2: ^||IVG.TWin(h, "src", name) is set only for a non-empty name (TemporalWindow.cls:61-63).
pub open spec fn list_admits(l: Seq<Seq<char>>, s: Seq<char>) -> bool {
    s.len() > 0 && l.contains(s)
}

pub open spec fn plain(a_sources: Option<Seq<Seq<char>>>) -> Args {
    Args { source: Seq::empty(), sources: a_sources, prefix: Seq::empty() }
}

/// Omitted sources: no "sources" key is sent. An explicit empty list: the key is sent with an empty list.
pub proof fn theorem_spec_sources_omitted_vs_empty()
    ensures
        window_spec(plain(None)) == (Sent::Spec { source: None, sources: None, prefix: None }),
        window_spec(plain(Some(Seq::<Seq<char>>::empty())))
            == (Sent::Spec { source: None, sources: Some(Seq::<Seq<char>>::empty()), prefix: None }),
{
}

/// At the server: no key reads every source; an empty list, or a list of empty names, reads none.
pub proof fn theorem_server_filter_sources(s: Seq<char>, l: Seq<Seq<char>>)
    requires
        s.len() > 0,
        forall|i: int| 0 <= i < l.len() ==> (#[trigger] l[i]).len() == 0,
    ensures
        server_admits(window_spec(plain(None)), s),
        !server_admits(window_spec(plain(Some(Seq::<Seq<char>>::empty()))), s),
        !server_admits(window_spec(plain(Some(l))), s),
{
    assert(!Seq::<Seq<char>>::empty().contains(s));
    if l.contains(s) {
        let i = choose|i: int| 0 <= i < l.len() && l[i] == s;
        assert(l[i].len() == 0);
    }
}

/// End to end for public case M06: omitted reads every source, an explicit empty list reads nothing.
pub proof fn theorem_m06_omitted_reads_all_empty_reads_none(s: Seq<char>)
    requires s.len() > 0,
    ensures
        server_admits(window_spec(plain(None)), s),
        !server_admits(window_spec(plain(Some(Seq::<Seq<char>>::empty()))), s),
{
    theorem_server_filter_sources(s, Seq::<Seq<char>>::empty());
}

/// Naming two of source, sources and prefix is refused before any call (temporal_window.py:46-47).
pub proof fn theorem_two_filters_refused(a: Args)
    requires named_count(a) > 1,
    ensures window_spec(a) == Sent::Refused,
{
}

// ============================================================================ part 2: the server's page producer

/// TemporalWindow.Page :141-192 over the rows left after the resume key: it stops after `n` rows (:185), or earlier
/// when the page text passes PAGECHARS after `lim` rows (lim >= 1: the check runs after a row is appended), or when
/// the walk runs out (:144-146, done = 1). Returns (rows on this page, done).
pub open spec fn page(remaining: nat, n: nat, lim: nat) -> (nat, bool) {
    let k = if n < lim { n } else { lim };
    if remaining < k { (remaining, true) } else { (k, false) }
}

/// A page that is not marked done holds at least one row; so the server never sends an empty page that is not
/// the last. (The client does not rely on this: see theorem_yield_is_concat_to_done.)
pub proof fn theorem_server_full_page_nonempty(remaining: nat, n: nat, lim: nat)
    requires n >= 1, lim >= 1,
    ensures !page(remaining, n, lim).1 ==> page(remaining, n, lim).0 >= 1,
{
}

/// When exactly a page's worth is left, that page is not marked done and the next page is empty and done.
pub proof fn witness_exact_multiple_ends_with_empty_done_page()
    ensures page(2, 2, 100) == (2nat, false), page(0, 2, 100) == (0nat, true),
{
}

// ============================================================================ part 3: the Python cursor

/// One scripted server answer: Open's for index 0, then one per Next. `fail` is any exception from the native
/// call (_server_call wraps it as TemporalWindowError).
pub struct Resp {
    pub fail: bool,
    pub rows: Seq<int>,
    pub done: bool,
}

/// The cursor and the one server handle it opened.
///   buf: TemporalWindowCursor._rows      closed: .closed       out: events returned so far
///   srv_open: ^||IVG.TWin(h) exists       closes: Close calls   calls: Open/Next calls (round_trips)
///   pos: index of the next scripted answer      stopped: StopIteration raised      raised: an error raised
pub struct C {
    pub buf: Seq<int>,
    pub closed: bool,
    pub srv_open: bool,
    pub closes: nat,
    pub calls: nat,
    pub pos: nat,
    pub out: Seq<int>,
    pub stopped: bool,
    pub raised: bool,
}

/// __init__ :82-93. A failed Open raises from the constructor: there is no cursor and nothing is open.
pub open spec fn open(script: Seq<Resp>) -> C {
    let r = script[0];
    if r.fail {
        C { buf: Seq::empty(), closed: true, srv_open: false, closes: 0, calls: 1, pos: 1, out: Seq::empty(),
            stopped: false, raised: true }
    } else {
        C { buf: r.rows, closed: r.done, srv_open: !r.done, closes: 0, calls: 1, pos: 1, out: Seq::empty(),
            stopped: false, raised: false }
    }
}

/// close :115-124. Close is called only while the cursor is not closed; the server's Close kills the handle.
pub open spec fn close(c: C) -> C {
    if c.closed {
        C { buf: Seq::empty(), ..c }
    } else {
        C { buf: Seq::empty(), closed: true, srv_open: false, closes: c.closes + 1, ..c }
    }
}

/// The server's state after a Next answer: done frees the handle (Page :187-188).
pub open spec fn after_page(c: C, r: Resp) -> C {
    C { closed: page_ends_read(r), srv_open: c.srv_open && !r.done, buf: c.buf + r.rows, ..c }
}

/// __next__ :111: only the done flag ends the read.
pub open spec fn page_ends_read(r: Resp) -> bool {
    r.done
}

/// One step of __next__ :102-113: return a buffered row; or stop when closed; or ask for the next page (a failure
/// closes the cursor, which frees the handle, then raises). A __next__ call is the steps up to an emit, stop or raise.
pub open spec fn step(c: C, script: Seq<Resp>) -> C {
    if c.stopped || c.raised {
        c
    } else if c.buf.len() > 0 {
        C { buf: c.buf.drop_first(), out: c.out.push(c.buf[0]), ..c }
    } else if c.closed {
        C { stopped: true, ..c }
    } else if c.pos >= script.len() {
        C { stopped: true, ..c }  // outside the premise that the window ends; not reached under it
    } else {
        let r = script[c.pos as int];
        let c1 = C { calls: c.calls + 1, pos: c.pos + 1, ..c };
        if r.fail {
            let c2 = close(c1);
            C { raised: true, ..c2 }
        } else {
            after_page(c1, r)
        }
    }
}

/// Iterating to the end: step until a stop or a raise.
pub open spec fn drain(c: C, script: Seq<Resp>) -> C
    decreases script.len() - c.pos, c.buf.len(),
{
    if c.stopped || c.raised {
        c
    } else if c.buf.len() > 0 {
        drain(step(c, script), script)
    } else if c.closed || c.pos >= script.len() {
        step(c, script)
    } else {
        drain(step(c, script), script)
    }
}

/// The rows of answers 0 .. n-1, in order.
pub open spec fn concat(script: Seq<Resp>, n: nat) -> Seq<int>
    decreases n,
{
    if n == 0 { Seq::empty() } else { concat(script, (n - 1) as nat) + script[n - 1].rows }
}

/// The window ends at answer k: answers 0..k succeed, k is the first answer marked done.
pub open spec fn ends_at(script: Seq<Resp>, k: nat) -> bool {
    &&& k < script.len()
    &&& script[k as int].done
    &&& forall|i: int| 0 <= i <= k ==> !(#[trigger] script[i]).fail
    &&& forall|i: int| 0 <= i < k ==> !(#[trigger] script[i]).done
}

pub open spec fn inv(c: C, script: Seq<Resp>, k: nat) -> bool {
    &&& !c.stopped && !c.raised
    &&& 1 <= c.pos <= k + 1
    &&& c.closed == (c.pos == k + 1)
    &&& c.srv_open == !c.closed
    &&& c.out + c.buf == concat(script, c.pos)
    &&& c.closes == 0
    &&& c.calls == c.pos
}

proof fn lemma_push_drop(out: Seq<int>, b: Seq<int>)
    requires b.len() > 0,
    ensures out.push(b[0]) + b.drop_first() == out + b,
{
    assert(out.push(b[0]) + b.drop_first() =~= out + b);
}

proof fn lemma_drain(c: C, script: Seq<Resp>, k: nat)
    requires ends_at(script, k), inv(c, script, k),
    ensures
        drain(c, script).out == concat(script, k + 1),
        drain(c, script).stopped,
        !drain(c, script).raised,
        drain(c, script).closes == 0,
        !drain(c, script).srv_open,
        drain(c, script).calls == k + 1,
        drain(c, script).closed,
    decreases script.len() - c.pos, c.buf.len(),
{
    if c.buf.len() > 0 {
        let c1 = step(c, script);
        lemma_push_drop(c.out, c.buf);
        assert(inv(c1, script, k));
        lemma_drain(c1, script, k);
    } else if c.closed {
        assert(c.out =~= c.out + c.buf);
    } else {
        let r = script[c.pos as int];
        assert(!r.fail);
        let c1 = step(c, script);
        assert(c.out =~= c.out + c.buf);
        assert(c1.out + c1.buf =~= concat(script, c.pos) + r.rows);
        assert(concat(script, c.pos + 1) == concat(script, c.pos) + script[c.pos as int].rows);
        assert(c1.closed == (c1.pos == k + 1));
        assert(inv(c1, script, k));
        lemma_drain(c1, script, k);
    }
}

/// M07, M08: iterating to the end returns the rows of every page up to and including the page marked done, in order,
/// whatever empty pages come before it; the server freed the handle itself and the cursor called Close zero times.
pub proof fn theorem_yield_is_concat_to_done(script: Seq<Resp>, k: nat)
    requires ends_at(script, k),
    ensures
        drain(open(script), script).out == concat(script, k + 1),
        drain(open(script), script).stopped,
        !drain(open(script), script).raised,
        drain(open(script), script).closes == 0,
        !drain(open(script), script).srv_open,
        drain(open(script), script).calls == k + 1,
        drain(open(script), script).closed,
{
    let c0 = open(script);
    assert(concat(script, 1) == concat(script, 0) + script[0].rows);
    assert(c0.out + c0.buf =~= concat(script, 1));
    assert(inv(c0, script, k));
    lemma_drain(c0, script, k);
}

/// M07: a window that fits the first page costs one round trip and no Close, and closing after the end sends nothing.
pub proof fn theorem_exhaustion_frees_without_close(script: Seq<Resp>, k: nat)
    requires ends_at(script, k),
    ensures
        k == 0 ==> drain(open(script), script).calls == 1,
        close(drain(open(script), script)).closes == 0,
        !close(drain(open(script), script)).srv_open,
{
    theorem_yield_is_concat_to_done(script, k);
}

/// M07: closing mid-read sends one Close and frees the handle; a second close sends nothing; the closed cursor
/// yields nothing more and makes no server call.
pub proof fn theorem_close_mid_read_once(script: Seq<Resp>)
    requires script.len() > 0, !script[0].fail, !script[0].done,
    ensures
        close(open(script)).closes == 1,
        !close(open(script)).srv_open,
        close(close(open(script))).closes == 1,
        step(close(close(open(script))), script).stopped,
        step(close(close(open(script))), script).calls == open(script).calls,
{
}

/// M08: a failed page raises after exactly one Close, which frees the handle.
pub proof fn theorem_failed_page_closes_once(script: Seq<Resp>, c: C, k: nat)
    requires
        inv(c, script, k), c.buf.len() == 0, !c.closed, (c.pos as int) < script.len(), script[c.pos as int].fail,
    ensures
        step(c, script).raised,
        step(c, script).closes == 1,
        !step(c, script).srv_open,
        step(c, script).out == c.out,
{
}

/// A failed Open raises at the call, opens nothing and closes nothing.
pub proof fn theorem_failed_open_raises(script: Seq<Resp>)
    requires script.len() > 0, script[0].fail,
    ensures open(script).raised, !open(script).srv_open, open(script).closes == 0,
{
}

/// The legitimate path is reachable: rows [1], an empty page not marked done, then [2] done: both rows come back.
pub proof fn witness_empty_middle_page()
{
    let p0 = Resp { fail: false, rows: seq![1int], done: false };
    let p1 = Resp { fail: false, rows: Seq::<int>::empty(), done: false };
    let p2 = Resp { fail: false, rows: seq![2int], done: true };
    let script = seq![p0, p1, p2];
    assert(ends_at(script, 2));
    theorem_yield_is_concat_to_done(script, 2);
    reveal_with_fuel(concat, 4);
    assert(concat(script, 3) =~= seq![1int, 2int]);
    assert(drain(open(script), script).out =~= seq![1int, 2int]);
}

} // verus!
