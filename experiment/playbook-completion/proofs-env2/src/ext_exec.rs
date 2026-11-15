//! proofs-env2: the extension's exec functions, each verified equal to its specification (`ext.rs`).
use vstd::prelude::*;
use crate::spec::*;
use crate::ext::*;
use crate::wf::*;
use crate::exec::*;
use crate::effects::*;
use crate::ext_lemmas::*;

verus! {

// ------------------------------------------------------------------------------------------------ X-VEC functions

pub fn e_sqlfn_obs(sem: &Sem, f: u8) -> (o: EObs)
    ensures o@ == sqlfn_obs(*sem, f),
{
    if f == 0 || f == 1 { EObs::FnVal(0) } else if f == 2 {
        if sem.vector_l2_available { EObs::FnVal(1) } else { EObs::SqlError(-359) }
    } else { EObs::Refused(RefK::SqlFnOther) }
}

// ------------------------------------------------------------------------------------------------ X-ZSTRIP

pub fn e_zclass(sem: &Sem, ch: u32, c: u32) -> (b: bool)
    ensures b == zclass(*sem, ch, c),
{
    if ch == 67 {
        if sem.zstrip_c_c1 { c <= 31 || (127 <= c && c <= 159) } else { c <= 31 || c == 127 }
    } else if ch == 87 {
        if sem.zstrip_w_observed { c == 9 || c == 32 || c == 160 } else { c == 32 }
    } else {
        false
    }
}

pub fn e_upper(c: u32) -> (r: u32)
    ensures r == upper(c),
{
    if 97 <= c && c <= 122 { c - 32 } else { c }
}

pub fn e_contains(v: &Vec<u32>, x: u32) -> (b: bool)
    ensures b == v@.contains(x),
{
    let mut i: usize = 0;
    while i < v.len()
        invariant i <= v.len(), forall|j: int| 0 <= j < i ==> v@[j] != x,
        decreases v.len() - i,
    {
        if v[i] == x { return true; }
        i += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_zm(sem: &Sem, a: &EZArg, c: u32) -> (b: bool)
    ensures b == zm(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }, c),
{
    let za = Ghost(ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ });
    if e_contains(&a.rem, c) { return true; }
    let mut i: usize = 0;
    while i < a.mask.len()
        invariant i <= a.mask.len(),
            forall|j: int| 0 <= j < i ==> !(!is_action(#[trigger] a.mask@[j]) && zclass(*sem, upper(a.mask@[j]), c)),
        decreases a.mask.len() - i,
    {
        let m = a.mask[i];
        let act = m == 42 || m == 60 || m == 62 || m == 61;
        if !act && e_zclass(sem, e_upper(m), c) {
            assert(!is_action(za@.mask[i as int]) && zclass(*sem, upper(za@.mask[i as int]), c));
            return true;
        }
        i += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_zfilter(sem: &Sem, a: &EZArg, s: &Vec<u32>) -> (r: Vec<u32>)
    ensures r@ == zfilter(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }, s@),
{
    let ghost za = ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ };
    let mut acc: Vec<u32> = Vec::new();
    let mut i: usize = 0;
    assert(s@.subrange(0, 0) =~= Seq::<u32>::empty());
    while i < s.len()
        invariant i <= s.len(), acc@ == zfilter(*sem, za, s@.subrange(0, i as int)),
        decreases s.len() - i,
    {
        let c = s[i];
        proof {
            let p1 = s@.subrange(0, i as int + 1);
            assert(p1.drop_last() =~= s@.subrange(0, i as int));
            assert(p1.last() == c);
        }
        if !e_zm(sem, a, c) { acc.push(c); }
        i += 1;
    }
    assert(s@.subrange(0, s.len() as int) =~= s@);
    acc
}

#[verifier::loop_isolation(false)]
pub fn e_zlead(sem: &Sem, a: &EZArg, s: &Vec<u32>) -> (k: usize)
    ensures k as nat == zlead(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }, s@, 0), k <= s.len(),
{
    let ghost za = ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ };
    let mut i: usize = 0;
    while i < s.len() && e_zm(sem, a, s[i])
        invariant i <= s.len(), zlead(*sem, za, s@, 0) == zlead(*sem, za, s@, i as nat),
        decreases s.len() - i,
    {
        i += 1;
    }
    i
}

#[verifier::loop_isolation(false)]
pub fn e_ztrail(sem: &Sem, a: &EZArg, s: &Vec<u32>) -> (r: Vec<u32>)
    ensures r@ == ztrail(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }, s@),
{
    let ghost za = ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ };
    let mut k: usize = s.len();
    assert(s@.subrange(0, k as int) =~= s@);
    while k > 0 && e_zm(sem, a, s[k - 1])
        invariant k <= s.len(), ztrail(*sem, za, s@) == ztrail(*sem, za, s@.subrange(0, k as int)),
        decreases k,
    {
        proof {
            let p = s@.subrange(0, k as int);
            assert(p.last() == s@[k - 1]);
            assert(p.drop_last() =~= s@.subrange(0, k - 1));
        }
        k -= 1;
    }
    let mut r: Vec<u32> = Vec::new();
    let mut i: usize = 0;
    while i < k
        invariant i <= k, k <= s.len(), r@ == s@.subrange(0, i as int),
        decreases k - i,
    {
        r.push(s[i]);
        i += 1;
        assert(r@ =~= s@.subrange(0, i as int));
    }
    proof {
        let p = s@.subrange(0, k as int);
        if k > 0 { assert(p.last() == s@[k - 1]); }
    }
    r
}

#[verifier::loop_isolation(false)]
pub fn e_zcollapse(sem: &Sem, a: &EZArg, s: &Vec<u32>) -> (r: Vec<u32>)
    ensures r@ == zcollapse(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }, s@),
{
    let ghost za = ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ };
    let mut acc: Vec<u32> = Vec::new();
    let mut i: usize = 0;
    assert(s@.subrange(0, 0) =~= Seq::<u32>::empty());
    while i < s.len()
        invariant i <= s.len(), acc@ == zcollapse(*sem, za, s@.subrange(0, i as int)),
        decreases s.len() - i,
    {
        let c = s[i];
        proof {
            let p1 = s@.subrange(0, i as int + 1);
            assert(p1.drop_last() =~= s@.subrange(0, i as int));
            assert(p1.last() == c);
        }
        let skip = e_zm(sem, a, c) && acc.len() > 0 && acc[acc.len() - 1] == c;
        if !skip { acc.push(c); }
        i += 1;
    }
    assert(s@.subrange(0, s.len() as int) =~= s@);
    acc
}

#[verifier::loop_isolation(false)]
pub fn e_zstrip(sem: &Sem, a: &EZArg) -> (r: Vec<u32>)
    ensures r@ == zstrip(*sem, ZArg { s: a.s@, mask: a.mask@, rem: a.rem@ }),
{
    if e_contains(&a.mask, 42) {
        e_zfilter(sem, a, &a.s)
    } else {
        let v1 = if e_contains(&a.mask, 60) {
            let k = e_zlead(sem, a, &a.s);
            let mut v: Vec<u32> = Vec::new();
            let mut i: usize = k;
            while i < a.s.len()
                invariant k <= i <= a.s.len(), v@ == a.s@.subrange(k as int, i as int),
                decreases a.s.len() - i,
            {
                v.push(a.s[i]);
                i += 1;
                assert(v@ =~= a.s@.subrange(k as int, i as int));
            }
            v
        } else { a.s.clone() };
        let v2 = if e_contains(&a.mask, 62) { e_ztrail(sem, a, &v1) } else { v1 };
        if e_contains(&a.mask, 61) { e_zcollapse(sem, a, &v2) } else { v2 }
    }
}

pub fn e_zranges(sem: &Sem, ch: u32) -> (r: Vec<(u32, u32)>)
    ensures r@ == zranges(*sem, ch, 0, None),
{
    let mut acc: Vec<(u32, u32)> = Vec::new();
    let mut start: Option<u32> = None;
    let mut c: u32 = 0;
    assert(acc@ + zranges(*sem, ch, 0, None) =~= zranges(*sem, ch, 0, None));
    loop
        invariant c <= 65536, acc@ + zranges(*sem, ch, c as nat, start) == zranges(*sem, ch, 0, None),
            start matches Some(x) ==> x < c,
        decreases 65536 - c,
    {
        let inc = c <= 65535 && e_zclass(sem, ch, c);
        let ghost before = acc@;
        let ghost st = start;
        match start {
            None => if inc { start = Some(c); },
            Some(s0) => if !inc {
                proof {
                    let rest = zranges(*sem, ch, c as nat + 1, None);
                    assert(before.push((s0, (c - 1) as u32)) + rest =~= before + (seq![(s0, (c - 1) as u32)] + rest));
                }
                acc.push((s0, c - 1));
                start = None;
            },
        }
        if c == 65536 {
            proof { assert(zranges(*sem, ch, 65537, start) == Seq::<(u32, u32)>::empty()); }
            assert(acc@ =~= acc@ + Seq::<(u32, u32)>::empty());
            return acc;
        }
        c += 1;
    }
}

// ------------------------------------------------------------------------------------------------ X-ORDER

pub fn e_lexcmp(a: &Vec<u32>, b: &Vec<u32>) -> (r: i8)
    ensures r as int == lexcmp(a@, b@),
{
    let mut i: usize = 0;
    assert(a@.subrange(0, a.len() as int) =~= a@);
    assert(a@.subrange(0, a@.len() as int) =~= a@ && b@.subrange(0, b@.len() as int) =~= b@);
    assert(a@ =~= a@.subrange(0, a@.len() as int));
    loop
        invariant i <= a.len(), i <= b.len(),
            lexcmp(a@, b@) == lexcmp(a@.subrange(i as int, a@.len() as int), b@.subrange(i as int, b@.len() as int)),
        decreases a.len() - i,
    {
        let ghost sa = a@.subrange(i as int, a@.len() as int);
        let ghost sb = b@.subrange(i as int, b@.len() as int);
        if i == a.len() {
            assert(sa.len() == 0);
            return if i == b.len() { 0 } else { -1 };
        }
        if i == b.len() {
            assert(sb.len() == 0);
            return 1;
        }
        assert(sa[0] == a@[i as int] && sb[0] == b@[i as int]);
        if a[i] < b[i] { return -1; }
        if a[i] > b[i] { return 1; }
        assert(sa.drop_first() =~= a@.subrange(i as int + 1, a@.len() as int));
        assert(sb.drop_first() =~= b@.subrange(i as int + 1, b@.len() as int));
        i += 1;
    }
}

pub fn e_find_cp(s: &Vec<u32>, x: u32) -> (r: Option<usize>)
    ensures r matches Some(i) ==> find_cp(s@, x, 0) == Some(i as nat), r is None ==> find_cp(s@, x, 0) is None,
        r matches Some(i) ==> i < s.len(),
{
    let mut i: usize = 0;
    while i < s.len()
        invariant i <= s.len(), find_cp(s@, x, 0) == find_cp(s@, x, i as nat),
        decreases s.len() - i,
    {
        if s[i] == x { return Some(i); }
        i += 1;
    }
    None
}

pub fn e_all_digits(s: &Vec<u32>) -> (b: bool)
    ensures b == all_digits(s@),
{
    let mut i: usize = 0;
    while i < s.len()
        invariant i <= s.len(), forall|j: int| 0 <= j < i ==> 48 <= #[trigger] s@[j] <= 57,
        decreases s.len() - i,
    {
        if !(48 <= s[i] && s[i] <= 57) { return false; }
        i += 1;
    }
    true
}

pub fn e_slice(s: &Vec<u32>, a: usize, b: usize) -> (r: Vec<u32>)
    requires a <= b <= s.len(),
    ensures r@ == s@.subrange(a as int, b as int),
{
    let mut r: Vec<u32> = Vec::new();
    let mut i: usize = a;
    while i < b
        invariant a <= i <= b, b <= s.len(), r@ == s@.subrange(a as int, i as int),
        decreases b - i,
    {
        r.push(s[i]);
        i += 1;
        assert(r@ =~= s@.subrange(a as int, i as int));
    }
    r
}

pub fn e_canonical(s: &Vec<u32>) -> (r: Option<(bool, Vec<u32>, Vec<u32>)>)
    ensures r matches Some(t) ==> canonical(s@) == Some((t.0, t.1@, t.2@)), r is None ==> canonical(s@) is None,
{
    let neg = s.len() > 0 && s[0] == 45;
    let body = if neg { e_slice(s, 1, s.len()) } else { s.clone() };
    assert(neg ==> body@ =~= s@.drop_first());
    let dot = e_find_cp(&body, 46);
    let ip = match dot { Some(i) => e_slice(&body, 0, i), None => body.clone() };
    let frac = match dot { Some(i) => e_slice(&body, i + 1, body.len()), None => Vec::new() };
    assert(dot is None ==> frac@ =~= Seq::<u32>::empty());
    if dot.is_some() && (frac.len() == 0 || frac[frac.len() - 1] == 48) { return None; }
    if !e_all_digits(&ip) || !e_all_digits(&frac) { return None; }
    if ip.len() == 0 && frac.len() == 0 { return None; }
    let ip_zero = ip.len() == 1 && ip[0] == 48;
    assert(ip_zero == (ip@ == seq![48u32])) by {
        if ip@ == seq![48u32] { assert(ip@.len() == 1 && ip@[0] == 48); }
        if ip_zero { assert(ip@ =~= seq![48u32]); }
    }
    if frac.len() > 0 && ip_zero { return None; }
    if ip.len() > 1 && ip[0] == 48 { return None; }
    if neg && ip_zero && frac.len() == 0 { return None; }
    Some((neg, ip, frac))
}

pub fn e_trim0(s: &Vec<u32>) -> (r: Vec<u32>)
    ensures r@ == trim0(s@),
{
    let mut i: usize = 0;
    assert(s@.subrange(0, s@.len() as int) =~= s@);
    while i < s.len() && s[i] == 48
        invariant i <= s.len(), trim0(s@) == trim0(s@.subrange(i as int, s@.len() as int)),
        decreases s.len() - i,
    {
        proof {
            let t = s@.subrange(i as int, s@.len() as int);
            assert(t[0] == s@[i as int]);
            assert(t.drop_first() =~= s@.subrange(i as int + 1, s@.len() as int));
        }
        i += 1;
    }
    let r = e_slice(s, i, s.len());
    proof {
        let t = s@.subrange(i as int, s@.len() as int);
        if t.len() > 0 { assert(t[0] == s@[i as int]); }
    }
    r
}

pub fn e_cmp_abs(x: &(bool, Vec<u32>, Vec<u32>), y: &(bool, Vec<u32>, Vec<u32>)) -> (r: i8)
    ensures r as int == cmp_abs((x.0, x.1@, x.2@), (y.0, y.1@, y.2@)),
{
    let a = e_trim0(&x.1);
    let b = e_trim0(&y.1);
    if a.len() < b.len() { -1 } else if a.len() > b.len() { 1 } else {
        let c = e_lexcmp(&a, &b);
        if c != 0 { c } else { e_lexcmp(&x.2, &y.2) }
    }
}

pub fn e_collate(a: &Vec<u32>, b: &Vec<u32>) -> (r: i8)
    ensures r as int == collate(a@, b@),
{
    match (e_canonical(a), e_canonical(b)) {
        (Some(x), Some(y)) => if !x.0 && !y.0 { e_cmp_abs(&x, &y) } else if x.0 && y.0 { e_cmp_abs(&y, &x) } else if x.0 { -1 } else { 1 },
        (Some(_), None) => -1,
        (None, Some(_)) => 1,
        (None, None) => e_lexcmp(a, b),
    }
}

pub fn e_sub_lt(sem: &Sem, u: &Univ, x: u64, y: u64) -> (b: bool)
    ensures b == sub_lt(*sem, u@, x, y),
{
    let empty: Vec<u32> = Vec::new();
    let nx = if (x as u128) < (u.names.len() as u128) { &u.names[x as usize] } else { &empty };
    let ny = if (y as u128) < (u.names.len() as u128) { &u.names[y as usize] } else { &empty };
    assert(nx@ == name_of(u@, x) && ny@ == name_of(u@, y));
    if sem.numeric_collation { e_collate(nx, ny) < 0 } else { e_lexcmp(nx, ny) < 0 }
}

pub proof fn lemma_ins_sorted_split(sem: Sem, u: U, x: u64, l: Seq<u64>, k: nat)
    requires k <= l.len(), forall|j: int| 0 <= j < k ==> !sub_lt(sem, u, x, #[trigger] l[j]),
        k == l.len() || sub_lt(sem, u, x, l[k as int]),
    ensures ins_sorted(sem, u, x, l) == l.subrange(0, k as int) + seq![x] + l.subrange(k as int, l.len() as int),
    decreases l.len(),
{
    if l.len() == 0 {
        assert(l.subrange(0, 0) + seq![x] + l.subrange(0, 0) =~= seq![x]);
    } else if k == 0 {
        assert(l.subrange(0, 0) + seq![x] + l.subrange(0, l.len() as int) =~= seq![x] + l);
    } else {
        let t = l.drop_first();
        assert forall|j: int| 0 <= j < k - 1 implies !sub_lt(sem, u, x, #[trigger] t[j]) by { assert(t[j] == l[j + 1]); }
        if k - 1 < t.len() { assert(t[k - 1] == l[k as int]); }
        lemma_ins_sorted_split(sem, u, x, t, (k - 1) as nat);
        assert(seq![l[0]] + (t.subrange(0, k - 1) + seq![x] + t.subrange(k - 1, t.len() as int))
            =~= l.subrange(0, k as int) + seq![x] + l.subrange(k as int, l.len() as int));
    }
}

pub fn e_ins_sorted(sem: &Sem, u: &Univ, x: u64, l: &Vec<u64>) -> (r: Vec<u64>)
    ensures r@ == ins_sorted(*sem, u@, x, l@),
{
    let mut k: usize = 0;
    while k < l.len() && !e_sub_lt(sem, u, x, l[k])
        invariant k <= l.len(), forall|j: int| 0 <= j < k ==> !sub_lt(*sem, u@, x, #[trigger] l@[j]),
        decreases l.len() - k,
    {
        k += 1;
    }
    proof { lemma_ins_sorted_split(*sem, u@, x, l@, k as nat); }
    let mut r: Vec<u64> = Vec::new();
    let mut i: usize = 0;
    while i < k
        invariant i <= k, k <= l.len(), r@ == l@.subrange(0, i as int),
        decreases k - i,
    {
        r.push(l[i]);
        i += 1;
        assert(r@ =~= l@.subrange(0, i as int));
    }
    r.push(x);
    let mut i: usize = k;
    while i < l.len()
        invariant k <= i <= l.len(), r@ == l@.subrange(0, k as int) + seq![x] + l@.subrange(k as int, i as int),
        decreases l.len() - i,
    {
        r.push(l[i]);
        i += 1;
        assert(r@ =~= l@.subrange(0, k as int) + seq![x] + l@.subrange(k as int, i as int));
    }
    r
}

pub fn e_isort(sem: &Sem, u: &Univ, l: &Vec<u64>) -> (r: Vec<u64>)
    ensures r@ == isort(*sem, u@, l@),
{
    let mut acc: Vec<u64> = Vec::new();
    let mut i: usize = 0;
    assert(l@.subrange(0, 0) =~= Seq::<u64>::empty());
    while i < l.len()
        invariant i <= l.len(), acc@ == isort(*sem, u@, l@.subrange(0, i as int)),
        decreases l.len() - i,
    {
        proof {
            let p1 = l@.subrange(0, i as int + 1);
            assert(p1.drop_last() =~= l@.subrange(0, i as int));
            assert(p1.last() == l@[i as int]);
        }
        acc = e_ins_sorted(sem, u, l[i], &acc);
        i += 1;
    }
    assert(l@.subrange(0, l.len() as int) =~= l@);
    acc
}

pub fn e_contains_u64(v: &Vec<u64>, x: u64) -> (b: bool)
    ensures b == v@.contains(x),
{
    let mut i: usize = 0;
    while i < v.len()
        invariant i <= v.len(), forall|j: int| 0 <= j < i ==> v@[j] != x,
        decreases v.len() - i,
    {
        if v[i] == x { return true; }
        i += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_subs(u: &Univ, g: &Vec<Option<Val>>, node: usize) -> (r: Vec<u64>)
    requires wf_univ(u@), g.len() == u@.n(), (node as int) < u@.n(), u.paths.len() == u.is_row.len(),
    ensures r@ == subs_from(u@, g@, node as int, 0, Seq::empty()),
{
    let n = u.paths.len();
    let mut acc: Vec<u64> = Vec::new();
    let mut j: usize = 0;
    let dn = u.paths[node].len();
    assert(u@.paths[node as int] == u.paths@[node as int]@);
    while j < n
        invariant j <= n, n == u@.n(), dn == u@.paths[node as int].len(),
            subs_from(u@, g@, node as int, 0, Seq::empty()) == subs_from(u@, g@, node as int, j as nat, acc@),
        decreases n - j,
    {
        assert(u@.paths[j as int] == u.paths@[j as int]@);
        if e_covers(u, node, j) && u.paths[j].len() > dn && g[j].is_some() {
            let x = u.paths[j][dn];
            assert(x == sub_of(u@, node as int, j as int));
            if !e_contains_u64(&acc, x) { acc.push(x); }
        }
        j += 1;
    }
    acc
}

pub fn e_too_long_number(u: &Univ, x: u64) -> (b: bool)
    ensures b == too_long_number(u@, x),
{
    let empty: Vec<u32> = Vec::new();
    let nx = if (x as u128) < (u.names.len() as u128) { &u.names[x as usize] } else { &empty };
    assert(nx@ == name_of(u@, x));
    e_canonical(nx).is_some() && nx.len() > 41
}

#[verifier::loop_isolation(false)]
pub fn e_order_obs(sem: &Sem, u: &Univ, g: &Vec<Option<Val>>, c: usize) -> (o: EObs)
    requires wf_univ(u@), g.len() == u@.n(), (c as int) < u@.n(), u.paths.len() == u.is_row.len(),
    ensures o@ == order_obs(*sem, u@, g@, c),
{
    let l = e_subs(u, g, c);
    let mut i: usize = 0;
    while i < l.len()
        invariant i <= l.len(), forall|j: int| 0 <= j < i ==> !too_long_number(u@, #[trigger] l@[j]),
        decreases l.len() - i,
    {
        if e_too_long_number(u, l[i]) {
            assert(too_long_number(u@, l@[i as int]));
            assert(exists|j: int| 0 <= j < l@.len() && too_long_number(u@, #[trigger] l@[j]));
            return EObs::Refused(RefK::OrderTooLong);
        }
        i += 1;
    }
    EObs::Subs(e_isort(sem, u, &l))
}

// ------------------------------------------------------------------------------------------------ X-NULL

pub fn e_stored(sem: &Sem, kind: Kind, v: Param, literal: bool) -> (r: Val)
    ensures r == stored(*sem, kind, v, literal),
{
    match v {
        Param::PNull => Val::Null,
        Param::PEmpty => {
            let term = match kind { Kind::Term => true, Kind::Dbapi => false };
            if literal { Val::Empty } else if (term && sem.os_empty_param_null) || (!term && sem.dbapi_empty_param_null) { Val::Null } else { Val::Empty }
        },
        Param::PNul => Val::Empty,
        Param::PV(x) => x,
    }
}

pub fn e_gete_obs(sem: &Sem, kind: Kind, c: Option<Val>) -> (o: EObs)
    ensures o@ == gete_obs(*sem, kind, c),
{
    match c {
        None => { let v: Vec<(usize, Val)> = Vec::new(); assert(v@ =~= Seq::<(usize, Val)>::empty()); EObs::Rows(v) },
        Some(v) => {
            let null = match v { Val::Null => true, _ => false };
            let empty = match v { Val::Empty => true, _ => false };
            match kind {
                Kind::Term => EObs::Cell(Some(if null { Val::Empty } else if empty && sem.os_reads_empty_as_c0 { Val::Nul } else { v }), null),
                Kind::Dbapi => EObs::Cell(if null { None } else { Some(v) }, null),
            }
        },
    }
}

pub fn e_matches_e(sem: &Sem, c: Val, param: Val) -> (b: bool)
    ensures b == matches_e(*sem, c, param),
{
    let bp = match param { Val::Null | Val::Empty => true, _ => false };
    let bc = match c { Val::Null | Val::Empty => true, _ => false };
    if sem.coalesce_folds_null_empty && bp { bc } else { eq_oval(Some(c), Some(param)) }
}

#[verifier::loop_isolation(false)]
pub fn e_match_count(sem: &Sem, u: &Univ, g: &Vec<Option<Val>>, t: usize, param: Val) -> (o: EObs)
    requires wf_univ(u@), g.len() == u@.n(),
    ensures o@ == count_obs(match_from(*sem, u@, g@, t, param, 0)),
{
    let n = u.paths.len();
    let mut cnt: usize = 0;
    let mut j: usize = 0;
    while j < n
        invariant j <= n, n == u@.n(), cnt <= j,
            match_from(*sem, u@, g@, t, param, 0) == cnt as nat + match_from(*sem, u@, g@, t, param, j as nat),
        decreases n - j,
    {
        let hit = u.is_row[j] && u.table[j] == t && match g[j] { Some(v) => e_matches_e(sem, v, param), None => false };
        if hit { cnt += 1; }
        j += 1;
    }
    if (cnt as u128) <= (i64::MAX as u128) { EObs::Count(cnt as i64) } else { EObs::Err(ErrK::Overflow) }
}

// ------------------------------------------------------------------------------------------------ X-STMT: INSERT ... SELECT

pub fn e_others_hold_rows(s: &EState, p: usize) -> (b: bool)
    ensures b == others_hold_rows(s@, p),
{
    let mut q: usize = 0;
    while q < s.procs.len()
        invariant q <= s.procs.len(),
            forall|qq: int, r: int| 0 <= qq < q && qq != p && 0 <= r < s@.procs[qq].rlocks.len() ==> !(#[trigger] s@.procs[qq].rlocks[r]),
        decreases s.procs.len() - q,
    {
        assert(s@.procs[q as int] == s.procs@[q as int]@);
        if q != p {
            let mut r: usize = 0;
            while r < s.procs[q].rlocks.len()
                invariant r <= s.procs@[q as int].rlocks.len(), q < s.procs.len(), q != p,
                    s@.procs[q as int] == s.procs@[q as int]@,
                    forall|qq: int, rr: int| 0 <= qq < q && qq != p && 0 <= rr < s@.procs[qq].rlocks.len() ==> !(#[trigger] s@.procs[qq].rlocks[rr]),
                    forall|rr: int| 0 <= rr < r ==> !(#[trigger] s@.procs[q as int].rlocks[rr]),
                decreases s.procs@[q as int].rlocks.len() - r,
            {
                if s.procs[q].rlocks[r] {
                    assert(s@.procs[q as int].rlocks[r as int]);
                    return true;
                }
                r += 1;
            }
        }
        q += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_find_twin(u: &Univ, t: usize, k: usize) -> (r: Option<usize>)
    requires wf_univ(u@),
    ensures r matches Some(j) ==> find_twin(u@, t, k, 0) == Some(j), r is None ==> find_twin(u@, t, k, 0) is None,
{
    let n = u.paths.len();
    let mut j: usize = 0;
    while j < n
        invariant j <= n, n == u@.n(), find_twin(u@, t, k, 0) == find_twin(u@, t, k, j as nat),
        decreases n - j,
    {
        if u.is_row[j] && u.table[j] == t && u.key[j] == k { return Some(j); }
        j += 1;
    }
    None
}

pub fn e_twin(u: &Univ, to: usize, r: usize) -> (j: usize)
    requires wf_univ(u@), (r as int) < u@.n(),
    ensures j == twin(u@, to, r),
{
    match e_find_twin(u, to, u.key[r]) { Some(j) => j, None => 0 }
}

#[verifier::loop_isolation(false)]
pub fn e_insert_select(sem: &Sem, u: &Univ, s: &mut EState, p: usize, from: usize, to: usize) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), old(s)@.procs[p as int].alive,
        (from as int) < u@.texists.len(), (to as int) < u@.texists.len(),
    ensures (final(s)@, o@) == insert_select(*sem, u@, old(s)@, p, from, to), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let ghost s0 = s@;
    let w = Ghost(|c: int| 0 <= c < u@.n() && u@.is_row[c] && u@.table[c] == to);
    let rf = Ghost(|c: int| false);
    proof { lemma_insert_select_xok(*sem, u@, s@, p, from, to, w@, rf@); }
    if e_others_hold_rows(s, p) { return EObs::Refused(RefK::InsertSelectBusy); }
    if !u.texists[from] || !u.texists[to] { return EObs::SqlError(-30); }
    let src = e_rows(u, &s.g, from);
    proof { lemma_rows_from(u@, s@.g, from, 0); }
    // twins and the first failing source row
    let mut i: usize = 0;
    let mut fail: Option<usize> = None;
    let mut twins: Vec<usize> = Vec::new();
    while i < src.len()
        invariant i <= src.len(), twins.len() == i, src@ == rows_from(u@, s0.g, from, 0), s@ == s0, wf(u@, s@),
            forall|j: int| 0 <= j < i ==> find_twin(u@, to, u@.key[(#[trigger] src@[j]).0 as int], 0) is Some,
            forall|j: int| 0 <= j < i ==> #[trigger] twins@[j] == twin(u@, to, src@[j].0),
            forall|j: int| 0 <= j < src.len() ==> ((#[trigger] src@[j]).0 as int) < u@.n(),
            fail is None ==> first_fail(u@, s0.g, to, src@, 0) == first_fail(u@, s0.g, to, src@, i as nat),
            fail matches Some(f) ==> f < i && first_fail(u@, s0.g, to, src@, 0) == Some(f as nat),
        decreases src.len() - i,
    {
        let (r, _v) = src[i];
        match e_find_twin(u, to, u.key[r]) {
            None => {
                assert(!twins_ok(u@, to, src@));
                return EObs::Refused(RefK::InsertSelectNoTwin);
            },
            Some(tw) => {
                twins.push(tw);
                proof { lemma_find_twin(u@, to, u@.key[r as int], 0); }
                if fail.is_none() && s.g[tw].is_some() { fail = Some(i); }
            },
        }
        i += 1;
    }
    assert(twins_ok(u@, to, src@));
    assert(fail is None ==> first_fail(u@, s0.g, to, src@, 0) is None);
    let atomic_fail = match fail { Some(f) => sem.statement_atomic || f == 0, None => false };
    if atomic_fail {
        proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
        e_failed_stmt(sem, s, p);
        return EObs::SqlError(-119);
    }
    let n: usize = match fail { Some(f) => f, None => src.len() };
    proof { lemma_stmt_begin_wf(u@, s@, p); }
    let implicit = e_stmt_begin(s, p);
    let ghost sb = s@;
    let mut k: usize = 0;
    proof { lemma_src_ok(u@, s0.g, from, to); }
    while k < n
        invariant k <= n, n <= src.len(), wf(u@, s@), s.procs.len() == s0.procs.len(), src@ == rows_from(u@, s0.g, from, 0),
            forall|j: int| 0 <= j < src.len() ==> #[trigger] twins@[j] == twin(u@, to, src@[j].0),
            twins.len() == src.len(), src_ok(u@, to, src@),
            is_write(u@, sb, p, to, src@, 0, n as nat) == is_write(u@, s@, p, to, src@, k as nat, n as nat),
        decreases n - k,
    {
        let tw = twins[k];
        let v = src[k].1;
        assert((tw as int) < u@.n());
        proof { lemma_write_wf(u@, s@, p, tw, Some(v), true); }
        e_write(s, p, tw, Some(v), true);
        k += 1;
    }
    let ghost sw = s@;
    assert(sw == is_write(u@, sb, p, to, src@, 0, n as nat));
    if implicit {
        proof { lemma_commit_top_wf(u@, s@, p); }
        e_commit_top(s, p);
    } else if sem.row_lock_held {
        let mut k: usize = 0;
        while k < n
            invariant k <= n, n <= src.len(), wf(u@, s@), s.procs.len() == s0.procs.len(),
                forall|j: int| 0 <= j < src.len() ==> #[trigger] twins@[j] == twin(u@, to, src@[j].0),
                twins.len() == src.len(), src_ok(u@, to, src@),
                is_lock(u@, sw, p, to, src@, 0, n as nat) == is_lock(u@, s@, p, to, src@, k as nat, n as nat),
            decreases n - k,
        {
            let tw = twins[k];
            assert(s@.procs[p as int] == s.procs@[p as int]@);
            assert(wf_proc(u@, s@.procs[p as int]));
            proof { lemma_set_rlock_wf(u@, s@, p, tw, true); }
            e_set_rlock(s, p, tw, true);
            k += 1;
        }
    }
    match fail {
        Some(_) => EObs::SqlError(-119),
        None => if (n as u128) <= (i64::MAX as u128) { EObs::Count(n as i64) } else { EObs::Err(ErrK::Overflow) },
    }
}

// ------------------------------------------------------------------------------------------------ E-1

pub fn e_set_autocommit(s: &mut EState, p: usize, on: bool)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == set_autocommit(old(s)@, p, on), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    pr.autocommit = on;
    put_proc(s, p, pr);
}

pub fn e_own_dml(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, ins: Option<Val>) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures (final(s)@, o@) == own_dml(*sem, u@, old(s)@, p, r, ins), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let t = u.table[r];
    if !u.texists[t] { return EObs::SqlError(-30); }
    proof { lemma_failed_stmt_wf(*sem, u@, s@, p); lemma_write_wf(u@, s@, p, r, ins, false); }
    match ins {
        Some(v) => if s.g[r].is_some() {
            e_failed_stmt(sem, s, p);
            EObs::SqlError(-119)
        } else {
            e_write(s, p, r, Some(v), false);
            EObs::Count(1)
        },
        None => if s.g[r].is_none() {
            if sem.empty_dml_opens_txn { e_failed_stmt(sem, s, p); }
            EObs::Count(0)
        } else {
            e_write(s, p, r, None, false);
            EObs::Count(1)
        },
    }
}

pub fn e_plain_dml(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, ins: Option<Val>) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures (final(s)@, o@) == plain_dml(*sem, u@, old(s)@, p, r, ins), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    match ins {
        Some(v) => e_dml(sem, u, s, p, r, Some(v), true),
        None => e_dml(sem, u, s, p, r, None, false),
    }
}

pub fn e_emb_dml(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, ins: Option<Val>) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures (final(s)@, o@) == emb_dml(*sem, u@, old(s)@, p, r, ins), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    if sem.emb_own_txn {
        e_own_dml(sem, u, s, p, r, ins)
    } else if sem.emb_ignores_autocommit && s.procs[p].marks.len() == 0 {
        assert(s@.procs[p as int] == s.procs@[p as int]@);
        let ac = s.procs[p].autocommit;
        assert(wf_proc(u@, s@.procs[p as int]));
        proof { lemma_upd_wf(u@, s@, p, Proc { autocommit: true, ..s@.procs[p as int] }); }
        e_set_autocommit(s, p, true);
        let o = e_plain_dml(sem, u, s, p, r, ins);
        assert(s@.procs[p as int] == s.procs@[p as int]@);
        assert(wf_proc(u@, s@.procs[p as int]));
        proof { lemma_upd_wf(u@, s@, p, Proc { autocommit: ac, ..s@.procs[p as int] }); }
        e_set_autocommit(s, p, ac);
        o
    } else {
        e_plain_dml(sem, u, s, p, r, ins)
    }
}

pub fn e_emb_visible(sem: &Sem, u: &Univ, s: &EState, p: usize, r: usize) -> (b: bool)
    requires wf_univ(u@), wf(u@, s@), (r as int) < u@.n(),
    ensures b == emb_visible(*sem, s@, p, r),
{
    if sem.emb_select_committed_only { let g = e_cv(sem, u, s, p); g[r].is_some() } else { s.g[r].is_some() }
}

pub fn e_reg_obs(o: EObs) -> (r: EObs)
    ensures r@ == reg_obs(o@),
{
    match o {
        EObs::Count(_) => EObs::Value(Some(Val::Num(0))),
        EObs::SqlError(c) => if c == -119 { EObs::Value(Some(Val::Num(0))) } else { EObs::Value(Some(Val::Num(c))) },
        other => other,
    }
}

pub fn e_retract_obs(o: EObs) -> (r: EObs)
    ensures r@ == retract_obs(o@),
{
    match o {
        EObs::Count(_) => EObs::Value(Some(Val::Num(1))),
        EObs::SqlError(c) => EObs::ErrText(c),
        other => other,
    }
}

pub fn e_emb_register(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures (final(s)@, o@) == emb_register(*sem, u@, old(s)@, p, r, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    if e_emb_visible(sem, u, s, p, r) { return EObs::Value(Some(Val::Num(0))); }
    if sem.maxlen_enforced && u.long[r] {
        proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
        e_failed_stmt(sem, s, p);
        return EObs::Value(Some(Val::Num(-104)));
    }
    if !sem.emb_ignores_row_locks && e_freedom_cond(sem, u, s, p, r) {
        let goes = match sem.freedom { FreedomSem::Both => choice, FreedomSem::WaitOnly => false, FreedomSem::GoOnly => true };
        if goes {
            let o = e_emb_dml(sem, u, s, p, r, Some(Val::Empty));
            assert(s@.procs[p as int] == s.procs@[p as int]@);
            assert(wf_proc(u@, s@.procs[p as int]));
            proof { lemma_set_rlock_wf(u@, s@, p, r, false); }
            e_set_rlock(s, p, r, false);
            e_reg_obs(o)
        } else {
            proof { lemma_set_pending_wf(u@, s@, p, Some(Op::EmbRegister { r })); }
            e_set_pending(s, p, Some(Op::EmbRegister { r }));
            EObs::Pending
        }
    } else {
        let o = e_emb_dml(sem, u, s, p, r, Some(Val::Empty));
        e_reg_obs(o)
    }
}

pub fn e_emb_assert(sem: &Sem, u: &Univ, s: &mut EState, p: usize, rn: usize, rr: usize, empty: bool, vt: Val) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (rn as int) < u@.n(), u@.is_row[rn as int],
        (rr as int) < u@.n(), u@.is_row[rr as int],
    ensures (final(s)@, o@) == emb_assert(*sem, u@, old(s)@, p, rn, rr, empty, vt), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    proof {
        assert forall|q: int| 0 <= q < s.procs.len() implies u@.n() == (#[trigger] s.procs@[q]).rlocks.len() by {
            assert(s@.procs[q] == s.procs@[q]@);
            assert(wf_proc(u@, s@.procs[q]));
        }
    }
    if e_row_held(s, p, rn) || e_row_held(s, p, rr) { return EObs::Refused(RefK::EmbAssertHeld); }
    if empty && sem.emb_empty_host_null {
        proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
        e_failed_stmt(sem, s, p);
        return EObs::ErrText(-108);
    }
    let o1 = if !e_emb_visible(sem, u, s, p, rn) { e_emb_dml(sem, u, s, p, rn, Some(Val::Empty)) } else { EObs::Ok };
    match o1 {
        EObs::SqlError(c) => EObs::ErrText(c),
        _ => {
            let o2 = if !e_emb_visible(sem, u, s, p, rr) { e_emb_dml(sem, u, s, p, rr, Some(vt)) } else { EObs::Ok };
            match o2 {
                EObs::SqlError(c) => EObs::ErrText(c),
                _ => EObs::Value(Some(Val::Num(1))),
            }
        },
    }
}

pub fn e_rows_count_obs(u: &Univ, g: &Vec<Option<Val>>, t: usize) -> (o: EObs)
    requires wf_univ(u@), g.len() == u@.n(),
    ensures o@ == num_obs(rows_count(u@, g@, t)),
{
    let rows = e_rows(u, g, t);
    e_num_obs(rows.len())
}

pub fn e_route_obs(u: &Univ, g: &Vec<Option<Val>>, t: usize) -> (o: EObs)
    requires wf_univ(u@), g.len() == u@.n(),
    ensures o@ == (if rows_count(u@, g@, t) > 0 { Obs::RouteRefused } else { Obs::Value(Some(Val::Num(0))) }),
{
    let rows = e_rows(u, g, t);
    if rows.len() > 0 { EObs::RouteRefused } else { EObs::Value(Some(Val::Num(0))) }
}

// ------------------------------------------------------------------------------------------------ one operation

// ------------------------------------------------------------------------------------------------ X2-BATCH, X2-IOU

pub fn e_batch_ok(u: &Univ, t: usize, rows: &Vec<(usize, Val)>) -> (b: bool)
    requires wf_univ(u@),
    ensures b == batch_ok(u@, t, rows@),
{
    assert(u@.paths.len() == u.paths@.len());
    assert(u.is_row.len() == u.paths.len() && u.table.len() == u.paths.len());
    let mut i: usize = 0;
    while i < rows.len()
        invariant i <= rows.len(), u.is_row.len() == u.paths.len(), u.table.len() == u.paths.len(), u@.n() == u.paths.len(),
            forall|j: int| 0 <= j < i ==> ((#[trigger] rows@[j]).0 as int) < u@.n() && u@.is_row[rows@[j].0 as int]
                && u@.table[rows@[j].0 as int] == t,
        decreases rows.len() - i,
    {
        let r = rows[i].0;
        if !(r < u.paths.len()) || !u.is_row[r] || u.table[r] != t {
            assert(!(((rows@[i as int]).0 as int) < u@.n() && u@.is_row[rows@[i as int].0 as int] && u@.table[rows@[i as int].0 as int] == t));
            return false;
        }
        i += 1;
    }
    true
}

#[verifier::loop_isolation(false)]
pub fn e_batch_held(u: &Univ, s: &EState, p: usize, t: usize, rows: &Vec<(usize, Val)>) -> (b: bool)
    requires wf(u@, s@), batch_ok(u@, t, rows@),
    ensures b == batch_held(s@, p, rows@, 0),
{
    proof {
        assert forall|q: int| 0 <= q < s.procs.len() implies (#[trigger] s.procs@[q]).rlocks.len() == u@.n() by {
            assert(s@.procs[q] == s.procs@[q]@);
            assert(wf_proc(u@, s@.procs[q]));
        }
    }
    let mut i: usize = 0;
    while i < rows.len()
        invariant i <= rows.len(), batch_held(s@, p, rows@, 0) == batch_held(s@, p, rows@, i as nat),
        decreases rows.len() - i,
    {
        let r = rows[i].0;
        assert((r as int) < u@.n());
        if e_row_held(s, p, r) { return true; }
        i += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_batch_probe(u: &Univ, g: &Vec<Option<Val>>, t: usize, rows: &Vec<(usize, Val)>) -> (r: Option<i64>)
    requires wf_univ(u@), g@.len() == u@.n(), batch_ok(u@, t, rows@),
    ensures r == batch_probe(u@, g@, rows@, 0),
{
    let mut g2: Vec<Option<Val>> = Vec::new();
    let mut j: usize = 0;
    while j < g.len()
        invariant j <= g.len(), g2@ == g@.subrange(0, j as int),
        decreases g.len() - j,
    {
        g2.push(g[j]);
        j += 1;
    }
    assert(g2@ =~= g@);
    let mut i: usize = 0;
    while i < rows.len()
        invariant i <= rows.len(), g2@.len() == u@.n(), batch_probe(u@, g@, rows@, 0) == batch_probe(u@, g2@, rows@, i as nat),
        decreases rows.len() - i,
    {
        let (r, v) = rows[i];
        assert((r as int) < u@.n() && u@.is_row[r as int]);
        if !u.texists[u.table[r]] { return Some(-30); }
        if g2[r].is_some() { return Some(-119); }
        g2.set(r, Some(v));
        i += 1;
    }
    None
}

#[verifier::loop_isolation(false)]
pub fn e_batch_run(sem: &Sem, u: &Univ, s: &mut EState, p: usize, t: usize, rows: &Vec<(usize, Val)>) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), batch_ok(u@, t, rows@),
    ensures (final(s)@, o@) == batch_run(*sem, u@, old(s)@, p, rows@, 0, 0), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let ghost s0 = s@;
    let mut i: usize = 0;
    let mut n: usize = 0;
    while i < rows.len()
        invariant i <= rows.len(), n <= i, wf(u@, s@), s.procs.len() == s0.procs.len(),
            batch_run(*sem, u@, s0, p, rows@, 0, 0) == batch_run(*sem, u@, s@, p, rows@, i as nat, n as nat),
        decreases rows.len() - i,
    {
        let (r, v) = rows[i];
        assert((r as int) < u@.n() && u@.is_row[r as int]);
        let o = e_dml(sem, u, s, p, r, Some(v), true);
        match o {
            EObs::Count(_) => { n += 1; },
            EObs::SqlError(c) => { if sem.batch_raises_on_dup { return EObs::SqlError(c); } },
            _ => { return o; },
        }
        i += 1;
    }
    if (n as u128) <= (i64::MAX as u128) { EObs::Count(n as i64) } else { EObs::Err(ErrK::Overflow) }
}

pub fn e_insert_many(sem: &Sem, u: &Univ, s: &mut EState, p: usize, t: usize, rows: &Vec<(usize, Val)>) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), batch_ok(u@, t, rows@),
    ensures (final(s)@, o@) == insert_many(*sem, u@, old(s)@, p, rows@), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    if e_batch_held(u, s, p, t, rows) { return EObs::Refused(RefK::BatchHeld); }
    if rows.len() == 1 && !sem.batch_single_row_skips {
        let (r, v) = rows[0];
        assert((r as int) < u@.n() && u@.is_row[r as int]);
        return e_dml(sem, u, s, p, r, Some(v), true);
    }
    if sem.batch_atomic {
        if let Some(c) = e_batch_probe(u, &s.g, t, rows) {
            proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
            e_failed_stmt(sem, s, p);
            return EObs::SqlError(c);
        }
    }
    e_batch_run(sem, u, s, p, t, rows)
}

pub fn e_upsert_run(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, v: Val, after_wait: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures (final(s)@, o@) == upsert_run(*sem, u@, old(s)@, p, r, v, after_wait), wf(u@, final(s)@),
        final(s).procs.len() == old(s).procs.len(),
{
    if s.g[r].is_some() {
        e_dml(sem, u, s, p, r, Some(v), false)
    } else if after_wait && !sem.iou_retries_insert {
        proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
        e_failed_stmt(sem, s, p);
        EObs::SqlError(-109)
    } else if e_freedom_cond(sem, u, s, p, r) {
        EObs::Refused(RefK::UpsertFreedom)
    } else {
        e_dml(sem, u, s, p, r, Some(v), true)
    }
}

pub fn e_e1_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), wf_op(u@, op), (p as int) < old(s).procs.len(), old(s)@.procs[p as int].alive,
        op is EmbRegister || op is EmbRetract || op is EmbCount || op is EmbRoute || op is EmbAssert,
    ensures (final(s)@, o@) == ext_step(*sem, u@, old(s)@, p, op, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    proof { lemma_select_txn_wf(*sem, u@, s@, p); }
    match op {
        Op::EmbRegister { r } => e_emb_register(sem, u, s, p, r, choice),
        Op::EmbRetract { r } => {
            if e_blocked(sem, u, s, p, op) {
                proof { lemma_set_pending_wf(u@, s@, p, Some(op)); }
                e_set_pending(s, p, Some(op));
                EObs::Pending
            } else {
                let o = e_emb_dml(sem, u, s, p, r, None);
                e_retract_obs(o)
            }
        },
        Op::EmbCount { t } => {
            e_select_txn(sem, s, p);
            if sem.emb_select_committed_only { let g = e_cv(sem, u, s, p); e_rows_count_obs(u, &g, t) } else { e_rows_count_obs(u, &s.g, t) }
        },
        Op::EmbRoute { t } => {
            e_select_txn(sem, s, p);
            if sem.emb_select_committed_only { let g = e_cv(sem, u, s, p); e_route_obs(u, &g, t) } else { e_route_obs(u, &s.g, t) }
        },
        Op::EmbAssert { rn, rr, empty, vt } => e_emb_assert(sem, u, s, p, rn, rr, empty, vt),
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_x2_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), wf_op(u@, op), op is Upsert || op is InsertMany, (p as int) < old(s).procs.len(),
    ensures (final(s)@, o@) == ext_step(*sem, u@, old(s)@, p, op, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    match op {
        Op::Upsert { r, v } => {
            if e_blocked(sem, u, s, p, op) {
                proof { lemma_set_pending_wf(u@, s@, p, Some(op)); }
                e_set_pending(s, p, Some(op));
                EObs::Pending
            } else {
                e_upsert_run(sem, u, s, p, r, v, false)
            }
        },
        Op::InsertMany { t, b } => {
            assert(u@.batches[b as int] == u.batches@[b as int]@);
            e_insert_many(sem, u, s, p, t, &u.batches[b])
        },
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_is_ext_op(op: Op) -> (b: bool)
    ensures b == is_ext_op(op),
{
    match op {
        Op::SqlTLevel | Op::SqlFn { .. } | Op::ZStrip { .. } | Op::ZClass { .. } | Op::Order { .. } | Op::PutE { .. }
        | Op::GetE { .. } | Op::MatchE { .. } | Op::InsertSelect { .. } | Op::EmbRegister { .. } | Op::EmbRetract { .. }
        | Op::EmbCount { .. } | Op::EmbRoute { .. } | Op::EmbAssert { .. } | Op::Upsert { .. } | Op::InsertMany { .. } => true,
        _ => false,
    }
}

pub fn e_ext_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), wf_op(u@, op), is_ext_op(op), (p as int) < old(s).procs.len(),
        old(s)@.procs[p as int].alive, u.paths.len() == u.is_row.len(),
    ensures (final(s)@, o@) == ext_step(*sem, u@, old(s)@, p, op, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    let kind = s.procs[p].kind;
    proof { lemma_select_txn_wf(*sem, u@, s@, p); }
    match op {
        Op::SqlTLevel => {
            e_select_txn(sem, s, p);
            assert(s@.procs[p as int] == s.procs@[p as int]@);
            EObs::Level(s.procs[p].marks.len())
        },
        Op::SqlFn { f } => e_sqlfn_obs(sem, f),
        Op::ZStrip { a } => {
            let z = &u.zargs[a];
            assert(u@.zargs[a as int] == ZArg { s: z.s@, mask: z.mask@, rem: z.rem@ });
            EObs::Codes(e_zstrip(sem, z))
        },
        Op::ZClass { ch } => EObs::Ranges(e_zranges(sem, ch)),
        Op::Order { c } => e_order_obs(sem, u, &s.g, c),
        Op::PutE { r, v, literal } => {
            proof {
                assert forall|q: int| 0 <= q < s.procs.len() implies (r as int) < (#[trigger] s.procs@[q]).rlocks.len() by {
                    assert(s@.procs[q] == s.procs@[q]@);
                    assert(wf_proc(u@, s@.procs[q]));
                }
            }
            if e_row_held(s, p, r) { EObs::Refused(RefK::PutELocked) } else {
                let val = e_stored(sem, kind, v, literal);
                e_dml(sem, u, s, p, r, Some(val), true)
            }
        },
        Op::GetE { r } => {
            e_select_txn(sem, s, p);
            e_gete_obs(sem, kind, s.g[r])
        },
        Op::MatchE { t, v } => {
            e_select_txn(sem, s, p);
            let param = e_stored(sem, kind, v, false);
            e_match_count(sem, u, &s.g, t, param)
        },
        Op::InsertSelect { from, to } => e_insert_select(sem, u, s, p, from, to),
        Op::EmbRegister { .. } | Op::EmbRetract { .. } | Op::EmbCount { .. } | Op::EmbRoute { .. } | Op::EmbAssert { .. } =>
            e_e1_step(sem, u, s, p, op, choice),
        Op::Upsert { .. } | Op::InsertMany { .. } => e_x2_step(sem, u, s, p, op, choice),
        _ => EObs::Err(ErrK::BadPending),
    }
}

} // verus!
