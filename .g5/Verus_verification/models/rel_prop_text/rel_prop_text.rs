// IVG relationship property text decoding (Cypher results): booleans, canonical integers and decimals, list or map
// text, everything else unchanged. Verus model, consolidated uplift (2026-11-14). Product baseline 3eaa79cf.
//   iris_vector_graph/prop_values.py  parse_prop_text :129-138, parse_rel_prop_text :141-168,
//       _CANONICAL_INT_RE :90, _CANONICAL_FLOAT_RE :91, decode_json_list_map :234-248
//   iris_vector_graph/_engine/query.py  _decode_rel_prop_text_columns :1200-1216 (columns and the arity guard)
// Two decoders: `decode` is the reviewed rule over ASCII canonical text (the decoder's own docstring); `as_built`
// transcribes Python's re.match semantics, where \d also matches non-ASCII decimal digits and $ also matches before a
// final line break. `theorem_as_built_agrees_on_plain_ascii` says exactly where they coincide.
//
// Run:  $VERUS_BIN rel_prop_text.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

pub enum Val {
    Bool(bool),
    Int,
    Float,
    Container,
    Str(Seq<char>),
}

pub open spec fn ascii_digit(c: char) -> bool {
    '0' <= c && c <= '9'
}

/// Python's \d for str patterns: Unicode decimal digits. Represented here by ASCII and four other Nd blocks
/// (Arabic-Indic, Extended Arabic-Indic, Devanagari, fullwidth); the model needs only that it contains more than ASCII.
pub open spec fn py_digit(c: char) -> bool {
    ascii_digit(c) || ('\u{0660}' <= c && c <= '\u{0669}') || ('\u{06F0}' <= c && c <= '\u{06F9}')
        || ('\u{0966}' <= c && c <= '\u{096F}') || ('\u{FF10}' <= c && c <= '\u{FF19}')
}

pub open spec fn digits(s: Seq<char>, uni: bool) -> bool {
    forall|i: int| 0 <= i < s.len() ==> if uni { py_digit(#[trigger] s[i]) } else { ascii_digit(s[i]) }
}

pub open spec fn unsigned(u: Seq<char>) -> Seq<char> {
    if u.len() > 0 && u[0] == '-' { u.drop_first() } else { u }
}

/// (0|[1-9]\d*) over the whole text
pub open spec fn int_digits(s: Seq<char>, uni: bool) -> bool {
    s.len() >= 1 && ((s.len() == 1 && s[0] == '0') || ('1' <= s[0] && s[0] <= '9' && digits(s.drop_first(), uni)))
}

/// -?(0|[1-9]\d*)
pub open spec fn int_text(u: Seq<char>, uni: bool) -> bool {
    int_digits(unsigned(u), uni)
}

/// -?(0|[1-9]\d*)\.\d+
pub open spec fn float_text(u: Seq<char>, uni: bool) -> bool {
    exists|k: int| 0 < k < unsigned(u).len() - 1 && #[trigger] unsigned(u)[k] == '.'
        && int_digits(unsigned(u).subrange(0, k), uni) && digits(unsigned(u).subrange(k + 1, unsigned(u).len() as int), uni)
        && unsigned(u).subrange(k + 1, unsigned(u).len() as int).len() >= 1
}

pub open spec fn shaped(t: Seq<char>) -> bool {
    t.len() >= 2 && ((t[0] == '[' && t.last() == ']') || (t[0] == '{' && t.last() == '}'))
}

pub open spec fn tru() -> Seq<char> { seq!['t', 'r', 'u', 'e'] }
pub open spec fn fals() -> Seq<char> { seq!['f', 'a', 'l', 's', 'e'] }

/// The reviewed rule. `parses`: the text parses as JSON to a list or map (json.loads in decode_json_list_map).
pub open spec fn decode(t: Seq<char>, parses: bool) -> Val {
    if t == tru() { Val::Bool(true) }
    else if t == fals() { Val::Bool(false) }
    else if shaped(t) && parses { Val::Container }
    else if int_text(t, false) { Val::Int }
    else if float_text(t, false) { Val::Float }
    else { Val::Str(t) }
}

/// re.match(r"^...$", t): the body matches all of t, or all of t but one final "\n".
pub open spec fn py_match_int(t: Seq<char>) -> bool {
    int_text(t, true) || (t.len() >= 1 && t.last() == '\n' && int_text(t.drop_last(), true))
}

pub open spec fn py_match_float(t: Seq<char>) -> bool {
    float_text(t, true) || (t.len() >= 1 && t.last() == '\n' && float_text(t.drop_last(), true))
}

/// As built (parse_rel_prop_text :161-168).
pub open spec fn as_built(t: Seq<char>, parses: bool) -> Val {
    if t == tru() { Val::Bool(true) }
    else if t == fals() { Val::Bool(false) }
    else if shaped(t) && parses { Val::Container }
    else if py_match_int(t) { Val::Int }
    else if py_match_float(t) { Val::Float }
    else { Val::Str(t) }
}

pub open spec fn plain_ascii(t: Seq<char>) -> bool {
    (forall|i: int| 0 <= i < t.len() ==> (#[trigger] t[i]) < '\u{80}') && (t.len() == 0 || t.last() != '\n')
}

proof fn lemma_digits_ascii(s: Seq<char>)
    requires forall|i: int| 0 <= i < s.len() ==> (#[trigger] s[i]) < '\u{80}',
    ensures digits(s, true) == digits(s, false),
{
}

proof fn lemma_unsigned_ascii(t: Seq<char>)
    requires forall|i: int| 0 <= i < t.len() ==> (#[trigger] t[i]) < '\u{80}',
    ensures forall|i: int| 0 <= i < unsigned(t).len() ==> (#[trigger] unsigned(t)[i]) < '\u{80}',
{
    if t.len() > 0 && t[0] == '-' {
        assert forall|i: int| 0 <= i < unsigned(t).len() implies (#[trigger] unsigned(t)[i]) < '\u{80}' by {
            assert(unsigned(t)[i] == t[i + 1]);
        }
    }
}

proof fn lemma_int_ascii(t: Seq<char>)
    requires forall|i: int| 0 <= i < t.len() ==> (#[trigger] t[i]) < '\u{80}',
    ensures int_text(t, true) == int_text(t, false),
{
    lemma_unsigned_ascii(t);
    let s = unsigned(t);
    if s.len() >= 1 {
        assert forall|i: int| 0 <= i < s.drop_first().len() implies (#[trigger] s.drop_first()[i]) < '\u{80}' by {
            assert(s.drop_first()[i] == s[i + 1]);
        }
        lemma_digits_ascii(s.drop_first());
    }
}

proof fn lemma_float_ascii(t: Seq<char>)
    requires forall|i: int| 0 <= i < t.len() ==> (#[trigger] t[i]) < '\u{80}',
    ensures float_text(t, true) == float_text(t, false),
{
    lemma_unsigned_ascii(t);
    let s = unsigned(t);
    assert forall|k: int| 0 < k < s.len() - 1 && #[trigger] s[k] == '.' implies
        (int_digits(s.subrange(0, k), true) == int_digits(s.subrange(0, k), false))
        && (digits(s.subrange(k + 1, s.len() as int), true) == digits(s.subrange(k + 1, s.len() as int), false)) by {
        let a = s.subrange(0, k);
        let b = s.subrange(k + 1, s.len() as int);
        assert forall|i: int| 0 <= i < a.len() implies (#[trigger] a[i]) < '\u{80}' by { assert(a[i] == s[i]); }
        assert forall|i: int| 0 <= i < b.len() implies (#[trigger] b[i]) < '\u{80}' by { assert(b[i] == s[i + k + 1]); }
        lemma_digits_ascii(b);
        if a.len() >= 1 {
            assert forall|i: int| 0 <= i < a.drop_first().len() implies (#[trigger] a.drop_first()[i]) < '\u{80}' by {
                assert(a.drop_first()[i] == a[i + 1]);
            }
            lemma_digits_ascii(a.drop_first());
        }
    }
}

/// The as-built decoder and the reviewed rule agree on every ASCII text that does not end in a line break.
pub proof fn theorem_as_built_agrees_on_plain_ascii(t: Seq<char>, parses: bool)
    requires plain_ascii(t),
    ensures as_built(t, parses) == decode(t, parses),
{
    lemma_int_ascii(t);
    lemma_float_ascii(t);
}

/// M18, first outcome: the classes the reviewed rule decodes.
pub proof fn theorem_decode_classes()
    ensures
        decode(tru(), false) == Val::Bool(true),
        decode(fals(), false) == Val::Bool(false),
        decode(seq!['1'], false) == Val::Int,
        decode(seq!['0'], false) == Val::Int,
        decode(seq!['-', '7'], false) == Val::Int,
        decode(seq!['1', '.', '5', '0'], false) == Val::Float,
        decode(seq!['[', '1', ']'], true) == Val::Container,
        decode(seq!['T', 'r', 'u', 'e'], false) == Val::Str(seq!['T', 'r', 'u', 'e']),
{
    assert(seq!['1'] != tru());
    assert(seq!['0'] != tru() && seq!['0'] != fals());
    assert(seq!['-', '7'] != tru() && seq!['-', '7'] != fals());
    assert(unsigned(seq!['-', '7']) =~= seq!['7']);
    assert(seq!['1'].drop_first() =~= Seq::<char>::empty());
    assert(seq!['7'].drop_first() =~= Seq::<char>::empty());
    let f = seq!['1', '.', '5', '0'];
    assert(f != tru() && f != fals());
    assert(f[0] != '-');
    assert(unsigned(f) == f);
    assert(f.drop_first()[0] == '.');
    assert(!int_text(f, false));
    assert(f.subrange(0, 1) =~= seq!['1']);
    assert(f.subrange(2, 4) =~= seq!['5', '0']);
    assert(f[1] == '.');
    assert(seq!['T', 'r', 'u', 'e'] != tru());
    assert(seq!['T', 'r', 'u', 'e'] != fals());
    assert(seq!['[', '1', ']'] != tru() && seq!['[', '1', ']'] != fals());
}

/// A character outside [0-9.-] anywhere in the text: neither an integer nor a decimal.
proof fn lemma_foreign_char_not_number(t: Seq<char>, i: int, uni: bool)
    requires 0 <= i < t.len(), !py_digit(t[i]), t[i] != '-', t[i] != '.',
    ensures !int_text(t, uni), !float_text(t, uni),
{
    let s = unsigned(t);
    let j = if t.len() > 0 && t[0] == '-' { i - 1 } else { i };
    assert(j >= 0) by { if t.len() > 0 && t[0] == '-' { assert(i != 0); } }
    assert(s[j] == t[i]);
    if int_text(t, uni) {
        if j > 0 { assert(s.drop_first()[j - 1] == s[j]); }
    }
    if float_text(t, uni) {
        let k = choose|k: int| 0 < k < s.len() - 1 && #[trigger] s[k] == '.'
            && int_digits(s.subrange(0, k), uni) && digits(s.subrange(k + 1, s.len() as int), uni)
            && s.subrange(k + 1, s.len() as int).len() >= 1;
        if j < k {
            assert(s.subrange(0, k)[j] == s[j]);
            if j > 0 { assert(s.subrange(0, k).drop_first()[j - 1] == s[j]); }
        } else if j > k {
            assert(s.subrange(k + 1, s.len() as int)[j - k - 1] == s[j]);
        }
    }
}

/// M18, second outcome: numeric-looking text that is not canonical stays the text it is: any character outside
/// [0-9.-] (a plus sign, an exponent, a space, a line break, a non-ASCII digit), or a leading zero before a digit.
pub proof fn theorem_noncanonical_stays_text(t: Seq<char>, i: int)
    requires
        t != tru(), t != fals(), !shaped(t),
        (0 <= i < t.len() && !ascii_digit(t[i]) && t[i] != '-' && t[i] != '.')
            || (t.len() >= 2 && t[0] == '0' && ascii_digit(t[1])),
    ensures decode(t, false) == Val::Str(t), decode(t, true) == Val::Str(t),
{
    if 0 <= i < t.len() && !ascii_digit(t[i]) && t[i] != '-' && t[i] != '.' {
        // the reviewed rule reads digits as ASCII: a non-ASCII digit is foreign to it
        let s = unsigned(t);
        let j = if t.len() > 0 && t[0] == '-' { i - 1 } else { i };
        assert(j >= 0) by { if t.len() > 0 && t[0] == '-' { assert(i != 0); } }
        assert(s[j] == t[i]);
        if int_text(t, false) { if j > 0 { assert(s.drop_first()[j - 1] == s[j]); } }
        if float_text(t, false) {
            let k = choose|k: int| 0 < k < s.len() - 1 && #[trigger] s[k] == '.'
                && int_digits(s.subrange(0, k), false) && digits(s.subrange(k + 1, s.len() as int), false)
                && s.subrange(k + 1, s.len() as int).len() >= 1;
            if j < k {
                assert(s.subrange(0, k)[j] == s[j]);
                if j > 0 { assert(s.subrange(0, k).drop_first()[j - 1] == s[j]); }
            } else if j > k {
                assert(s.subrange(k + 1, s.len() as int)[j - k - 1] == s[j]);
            }
        }
    } else {
        let s = unsigned(t);
        assert(s == t);
        if float_text(t, false) {
            let k = choose|k: int| 0 < k < s.len() - 1 && #[trigger] s[k] == '.'
                && int_digits(s.subrange(0, k), false) && digits(s.subrange(k + 1, s.len() as int), false)
                && s.subrange(k + 1, s.len() as int).len() >= 1;
            if k == 1 { assert(t[1] == '.'); } else { assert(s.subrange(0, k)[0] == '0'); assert(s.subrange(0, k).len() > 1); }
        }
    }
}

/// As built, a canonical integer followed by one line break is read as an integer (finding bug-cyp-101).
pub proof fn witness_as_built_trailing_newline_promoted()
{
    let t = seq!['1', '2', '\n'];
    assert(t.drop_last() =~= seq!['1', '2']);
    assert(seq!['1', '2'].drop_first() =~= seq!['2']);
    assert(t != tru() && t != fals());
    assert(as_built(t, false) == Val::Int);
    assert(!int_text(t, false)) by { assert(t.drop_first()[1] == '\n'); }
    assert(!float_text(t, false));
    assert(decode(t, false) == Val::Str(t));
}

/// As built, a non-ASCII decimal digit after the first digit is read as part of an integer (finding bug-cyp-101).
pub proof fn witness_as_built_unicode_digit_promoted()
{
    let t = seq!['1', '\u{0662}'];
    assert(t.drop_first() =~= seq!['\u{0662}']);
    assert(t[0] != '-');
    assert(unsigned(t) == t);
    assert(t.drop_first()[0] == '\u{0662}');
    assert(t != tru() && t != fals());
    assert(as_built(t, false) == Val::Int);
    assert(!int_text(t, false));
    assert(!float_text(t, false));
    assert(decode(t, false) == Val::Str(t));
}

} // verus!
