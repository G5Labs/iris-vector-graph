//! contract-2 extension (round env2-r1): pure value semantics the modules rely on, decided by observation.
//!
//! X2-JSON  `%DynamicObject` `%Set` / `%ToJSON` / `%FromJSON` / `%Get` / `%GetTypeOf` / `%IsDefined` / `%Remove`:
//!          insertion order kept (a re-`%Set` keeps the key's place); duplicate keys in parsed text: the last value at
//!          the first key's place; a number `%Set` from ObjectScript is written in its canonical form with a leading
//!          zero (`0.5`, `-0.25`, `0.0000001`); a parsed number keeps its JSON text (`1.50`, `1e2`, `-0.0`, `2.0`);
//!          `%Get` of a number answers its ObjectScript value; booleans are written `true`/`false`, read back as 1/0;
//!          null reads as "" with type "null" and is defined; `"`, `\` and code points below 32 are escaped (`\n`,
//!          `\t`, `\b`, `\f`, `\r`, otherwise `\u00xx` in lower-case hex); `/`, DEL and code points above 127 are not.
//! X2-LIST  `$LISTBUILD` / `$LIST` / `$LISTGET` / `$LISTDATA` / `$LISTLENGTH` / `$LISTNEXT` / `$LISTFIND` /
//!          `$LISTSAME` / `$LISTTOSTRING` / `$LISTFROMSTRING`, and the Python driver's `IRISList` decode of a `$LB`
//!          value read through the Native API.
//! The other X2 clauses (TOP / LIMIT, executemany, INSERT OR UPDATE, $QUERY / MERGE / ZKILL) act on engine state
//! and live in lib.rs next to the r6 operations.
use crate::Semantics;

// ------------------------------------------------------------------------------------------------ numbers

/// ObjectScript canonical form of a numeric text (`+"text"`): leading zeros dropped, trailing fraction zeros
/// dropped, `.5` for 0.5, `-.25`, "0" for zero, exponents expanded. None when the text is outside the modelled
/// subset (more than 18 significant digits, or not a number).
pub fn os_canonical(text: &str) -> Option<String> {
    let t = text.trim();
    let (neg, rest) = match t.strip_prefix('-') {
        Some(r) => (true, r),
        None => (false, t.strip_prefix('+').unwrap_or(t)),
    };
    let (mant, exp) = match rest.find(['e', 'E']) {
        Some(i) => (&rest[..i], rest[i + 1..].parse::<i32>().ok()?),
        None => (rest, 0),
    };
    let (ip, fp) = match mant.split_once('.') {
        Some((a, b)) => (a, b),
        None => (mant, ""),
    };
    if (ip.is_empty() && fp.is_empty()) || !ip.chars().all(|c| c.is_ascii_digit()) || !fp.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let digits: String = format!("{ip}{fp}");
    let point = ip.len() as i32 + exp; // position of the decimal point within `digits`
    let lead = digits.len() - digits.trim_start_matches('0').len();
    let digits = digits.trim_start_matches('0').to_string();
    let point = point - lead as i32;
    let digits = digits.trim_end_matches('0').to_string();
    if digits.is_empty() {
        return Some("0".into());
    }
    if digits.len() > 18 {
        return None;
    }
    let n = digits.len() as i32;
    let body = if point <= 0 {
        format!(".{}{}", "0".repeat((-point) as usize), digits)
    } else if point >= n {
        format!("{}{}", digits, "0".repeat((point - n) as usize))
    } else {
        format!("{}.{}", &digits[..point as usize], &digits[point as usize..])
    };
    Some(if neg { format!("-{body}") } else { body })
}

/// The JSON spelling `%ToJSON` gives an ObjectScript number: the canonical form with a leading zero.
fn json_number(canon: &str, sem: &Semantics) -> String {
    if sem.json_number_os_form {
        return canon.to_string();
    }
    if let Some(r) = canon.strip_prefix("-.") {
        format!("-0.{r}")
    } else if let Some(r) = canon.strip_prefix('.') {
        format!("0.{r}")
    } else {
        canon.to_string()
    }
}

// ------------------------------------------------------------------------------------------------ JSON values

#[derive(Clone, Debug, PartialEq)]
pub enum J {
    Null,
    Bool(bool),
    /// the JSON text of the number (parsed) or its JSON spelling (set from ObjectScript)
    Num(String),
    Str(Vec<u32>),
    Arr(Vec<J>),
    Obj(Vec<(Vec<u32>, J)>),
}

fn obj_set(o: &mut Vec<(Vec<u32>, J)>, k: Vec<u32>, v: J, sem: &Semantics) {
    if let Some(i) = o.iter().position(|(kk, _)| *kk == k) {
        if sem.json_set_moves_last {
            o.remove(i);
            o.push((k, v));
        } else {
            o[i].1 = v;
        }
    } else {
        o.push((k, v));
    }
}

struct P<'a> {
    s: &'a [u32],
    i: usize,
}

impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], 0x20 | 0x09 | 0x0a | 0x0d) {
            self.i += 1;
        }
    }
    fn peek(&self) -> Option<u32> {
        self.s.get(self.i).copied()
    }
    fn lit(&mut self, w: &str) -> bool {
        let cs: Vec<u32> = w.chars().map(|c| c as u32).collect();
        if self.s[self.i..].starts_with(&cs) {
            self.i += cs.len();
            true
        } else {
            false
        }
    }
    fn value(&mut self, sem: &Semantics) -> Option<J> {
        self.ws();
        match self.peek()? {
            0x7b => {
                self.i += 1;
                let mut o: Vec<(Vec<u32>, J)> = vec![];
                self.ws();
                if self.peek()? == 0x7d {
                    self.i += 1;
                    return Some(J::Obj(o));
                }
                loop {
                    self.ws();
                    let k = match self.value(sem)? {
                        J::Str(k) => k,
                        _ => return None,
                    };
                    self.ws();
                    if self.peek()? != 0x3a {
                        return None;
                    }
                    self.i += 1;
                    let v = self.value(sem)?;
                    if let Some(i) = o.iter().position(|(kk, _)| *kk == k) {
                        if !sem.json_dup_first_wins {
                            o[i].1 = v;
                        }
                    } else {
                        o.push((k, v));
                    }
                    self.ws();
                    match self.peek()? {
                        0x2c => self.i += 1,
                        0x7d => {
                            self.i += 1;
                            return Some(J::Obj(o));
                        }
                        _ => return None,
                    }
                }
            }
            0x5b => {
                self.i += 1;
                let mut a = vec![];
                self.ws();
                if self.peek()? == 0x5d {
                    self.i += 1;
                    return Some(J::Arr(a));
                }
                loop {
                    a.push(self.value(sem)?);
                    self.ws();
                    match self.peek()? {
                        0x2c => self.i += 1,
                        0x5d => {
                            self.i += 1;
                            return Some(J::Arr(a));
                        }
                        _ => return None,
                    }
                }
            }
            0x22 => {
                self.i += 1;
                let mut out = vec![];
                loop {
                    let c = self.peek()?;
                    self.i += 1;
                    match c {
                        0x22 => return Some(J::Str(out)),
                        0x5c => {
                            let e = self.peek()?;
                            self.i += 1;
                            out.push(match e {
                                0x22 => 0x22,
                                0x5c => 0x5c,
                                0x2f => 0x2f,
                                0x62 => 8,
                                0x66 => 12,
                                0x6e => 10,
                                0x72 => 13,
                                0x74 => 9,
                                0x75 => {
                                    let h: String = self.s.get(self.i..self.i + 4)?.iter().map(|&c| char::from_u32(c).unwrap_or('?')).collect();
                                    self.i += 4;
                                    u32::from_str_radix(&h, 16).ok()?
                                }
                                _ => return None,
                            });
                        }
                        c if c < 0x20 => return None,
                        c => out.push(c),
                    }
                }
            }
            0x74 => self.lit("true").then_some(J::Bool(true)),
            0x66 => self.lit("false").then_some(J::Bool(false)),
            0x6e => self.lit("null").then_some(J::Null),
            _ => {
                let st = self.i;
                while self.i < self.s.len() && matches!(self.s[self.i], 0x30..=0x39 | 0x2d | 0x2b | 0x2e | 0x65 | 0x45) {
                    self.i += 1;
                }
                if self.i == st {
                    return None;
                }
                let t: String = self.s[st..self.i].iter().map(|&c| char::from_u32(c).unwrap()).collect();
                os_canonical(&t)?; // a number IRIS reads (and inside the modelled subset)
                Some(J::Num(t))
            }
        }
    }
}

/// `%FromJSON`: None for invalid text (IRIS throws) or text outside the subset.
pub fn parse(text: &[u32], sem: &Semantics) -> Result<J, ()> {
    let mut p = P { s: text, i: 0 };
    let v = p.value(sem).ok_or(())?;
    p.ws();
    if p.i != text.len() {
        return Err(());
    }
    match v {
        J::Obj(_) | J::Arr(_) => Ok(v),
        _ => Err(()),
    }
}

fn esc(s: &[u32], sem: &Semantics, out: &mut Vec<u32>) {
    out.push(0x22);
    for &c in s {
        match c {
            0x22 => out.extend([0x5c, 0x22]),
            0x5c => out.extend([0x5c, 0x5c]),
            0x2f if sem.json_escape_slash => out.extend([0x5c, 0x2f]),
            10 => out.extend([0x5c, 0x6e]),
            9 => out.extend([0x5c, 0x74]),
            8 => out.extend([0x5c, 0x62]),
            12 => out.extend([0x5c, 0x66]),
            13 => out.extend([0x5c, 0x72]),
            c if c < 0x20 || (sem.json_escape_nonascii && c > 0x7e) => {
                out.extend(format!("\\u{:04x}", c).chars().map(|c| c as u32));
            }
            c => out.push(c),
        }
    }
    out.push(0x22);
}

/// `%ToJSON`
pub fn write(v: &J, sem: &Semantics, out: &mut Vec<u32>) {
    let push = |out: &mut Vec<u32>, s: &str| out.extend(s.chars().map(|c| c as u32));
    match v {
        J::Null => push(out, "null"),
        J::Bool(b) => push(out, if sem.json_bool_as_number { if *b { "1" } else { "0" } } else if *b { "true" } else { "false" }),
        J::Num(t) => {
            let t = if sem.json_reparse_canonical { json_number(&os_canonical(t).unwrap_or_default(), sem) } else { t.clone() };
            push(out, &t)
        }
        J::Str(s) => esc(s, sem, out),
        J::Arr(a) => {
            out.push(0x5b);
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push(0x2c);
                }
                write(x, sem, out);
            }
            out.push(0x5d);
        }
        J::Obj(o) => {
            out.push(0x7b);
            let mut items: Vec<&(Vec<u32>, J)> = o.iter().collect();
            if sem.json_sorted_keys {
                items.sort_by(|a, b| a.0.cmp(&b.0));
            }
            for (i, (k, x)) in items.into_iter().enumerate() {
                if i > 0 {
                    out.push(0x2c);
                }
                esc(k, sem, out);
                out.push(0x3a);
                write(x, sem, out);
            }
            out.push(0x7d);
        }
    }
}

/// One `%Set(key, value, type)` of a JsonBuild case: value given as text (numbers: an ObjectScript numeric text,
/// converted with `+`; strings: code points as text; booleans: truth of the number; null: ignored).
pub fn build(sets: &[(Vec<u32>, String, String)], sem: &Semantics) -> Option<Vec<u32>> {
    let mut o: Vec<(Vec<u32>, J)> = vec![];
    for (k, v, ty) in sets {
        let val = match ty.as_str() {
            "string" => J::Str(v.chars().map(|c| c as u32).collect()),
            "number" => J::Num(json_number(&os_canonical(v)?, sem)),
            "boolean" => J::Bool(os_canonical(if v.is_empty() { "0" } else { v })? != "0"),
            "null" => J::Null,
            _ => return None,
        };
        obj_set(&mut o, k.clone(), val, sem);
    }
    let mut out = vec![];
    write(&J::Obj(o), sem, &mut out);
    Some(out)
}

/// `%Get(key)`, `%GetTypeOf(key)`, `%IsDefined(key)` of an object parsed from `text`, as "get|type|defined" (the
/// get value as code points joined by ","), or "error" when the text does not parse.
pub fn get(text: &[u32], key: &[u32], sem: &Semantics) -> Option<String> {
    let v = match parse(text, sem) {
        Ok(J::Obj(o)) => o.into_iter().find(|(k, _)| k == key).map(|(_, v)| v),
        Ok(_) => return None,
        Err(_) => return Some("error".into()),
    };
    let codes = |s: &str| s.chars().map(|c| (c as u32).to_string()).collect::<Vec<_>>().join(",");
    Some(match v {
        None => "|unassigned|0".into(),
        Some(J::Null) => format!("{}|null|1", if sem.json_null_get_text { codes("null") } else { String::new() }),
        Some(J::Bool(b)) => format!("{}|boolean|1", if b { "49" } else { "48" }),
        Some(J::Num(t)) => format!("{}|number|1", codes(&os_canonical(&t)?)),
        Some(J::Str(s)) => format!("{}|string|1", s.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(",")),
        Some(J::Arr(_)) => "<obj>|array|1".into(),
        Some(J::Obj(_)) => "<obj>|object|1".into(),
    })
}

/// `%FromJSON` then `%ToJSON` (or `%Remove(key)` first): "error" when the text does not parse.
pub fn roundtrip(text: &[u32], remove: Option<&[u32]>, sem: &Semantics) -> Option<Vec<u32>> {
    match parse(text, sem) {
        Ok(mut v) => {
            if let (Some(k), J::Obj(o)) = (remove, &mut v) {
                o.retain(|(kk, _)| kk.as_slice() != k);
            }
            let mut out = vec![];
            write(&v, sem, &mut out);
            Some(out)
        }
        Err(_) => Some("error".chars().map(|c| c as u32).collect()),
    }
}

// ------------------------------------------------------------------------------------------------ $LIST

/// A `$LB` element: None = undefined; Some((kind, text)) with kind 's' string (text), 'i' integer, 'd' decimal
/// (canonical ObjectScript text).
pub type El = Option<(char, String)>;

fn el_value(e: &El) -> Option<String> {
    e.as_ref().map(|(_, t)| t.clone())
}

/// One `$LIST` expression over the list `l`: the answer text, or "<NULL VALUE>" for the error.
pub fn list_eval(l: &[El], what: &str, sem: &Semantics) -> Option<String> {
    let parts: Vec<&str> = what.split(':').collect();
    let idx = |s: &str| s.parse::<usize>().ok();
    let at = |i: usize| if i >= 1 && i <= l.len() { l[i - 1].clone() } else { None };
    Some(match parts[0] {
        "len" => l.len().to_string(),
        "data" => (if at(idx(parts[1])?).is_some() { "1" } else { "0" }).into(),
        "get" => {
            let d = parts.get(2).copied().unwrap_or("");
            match at(idx(parts[1])?) {
                Some((_, t)) if !(sem.list_get_default_on_empty && t.is_empty()) => t,
                _ => d.to_string(),
            }
        }
        "item" => match at(idx(parts[1])?) {
            Some((_, t)) => t,
            None if sem.list_undefined_item_empty && idx(parts[1])? <= l.len() => String::new(),
            None => "<NULL VALUE>".into(),
        },
        "walk" => l.iter().filter(|e| !(sem.list_walk_skips_undefined && e.is_none()))
            .map(|e| match e { Some((_, t)) => format!("<{t}>"), None => "U".into() }).collect::<Vec<_>>().join(";"),
        "find" => {
            let x = parts[1];
            let start = parts.get(2).and_then(|s| idx(s)).unwrap_or(0);
            let mut found = 0;
            for (i, e) in l.iter().enumerate() {
                if i + 1 <= start {
                    continue;
                }
                if let Some((k, t)) = e {
                    let typed_mismatch = sem.list_find_typed && *k != 's';
                    if t == x && !typed_mismatch {
                        found = i + 1;
                        break;
                    }
                }
            }
            found.to_string()
        }
        "tostring" => {
            let d = parts[1];
            let flag = parts.get(2).copied().unwrap_or("0") == "1";
            if l.iter().any(|e| e.is_none()) && !flag && !sem.list_tostring_skips_undefined {
                "<NULL VALUE>".into()
            } else {
                l.iter().map(|e| el_value(e).unwrap_or_default()).collect::<Vec<_>>().join(d)
            }
        }
        _ => return None,
    })
}

/// `$LISTSAME(a, b)` and `a = b` (the encodings), as "same|eq".
pub fn list_same(a: &[El], b: &[El], sem: &Semantics) -> String {
    let same = a.len() == b.len() && a.iter().zip(b).all(|(x, y)| match (x, y) {
        (None, None) => true,
        (Some((kx, tx)), Some((ky, ty))) => tx == ty && !(sem.list_same_typed && (*kx == 's') != (*ky == 's')),
        _ => false,
    });
    let eq = a.len() == b.len() && a.iter().zip(b).all(|(x, y)| match (x, y) {
        (None, None) => true,
        (Some((kx, tx)), Some((ky, ty))) => tx == ty && (*kx == 's') == (*ky == 's'),
        _ => false,
    });
    format!("{}|{}", same as u8, eq as u8)
}

/// `$LISTFROMSTRING(s, d)` then length and walk.
pub fn list_fromstring(s: &str, d: &str) -> String {
    let l: Vec<El> = s.split(d).map(|x| Some(('s', x.to_string()))).collect();
    format!("{}|{}", l.len(), l.iter().map(|e| format!("<{}>", el_value(e).unwrap_or_default())).collect::<Vec<_>>().join(";"))
}

/// The Python driver's `iris.IRISList` decode of the `$LB` value read through the Native API: "type:value" per
/// element (`str`, `int`, `Decimal`, `None`).
pub fn irislist(l: &[El], sem: &Semantics) -> String {
    l.iter().map(|e| match e {
        None => "None".to_string(),
        Some(('s', t)) => format!("str:{t}"),
        Some(('i', t)) => if sem.irislist_int_as_str { format!("str:{t}") } else { format!("int:{t}") },
        Some((_, t)) => {
            let t = if let Some(r) = t.strip_prefix("-.") { format!("-0.{r}") } else if let Some(r) = t.strip_prefix('.') { format!("0.{r}") } else { t.clone() };
            format!("Decimal:{t}")
        }
    }).collect::<Vec<_>>().join(";")
}
