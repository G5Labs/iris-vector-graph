//! The module 01 L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::inst_l1::*;
use crate::inst_l2::*;

verus! {

pub open spec fn i0(unreadable: bool, tables: Set<int>, views: Set<int>, lcls: Set<int>) -> IS2 {
    IS2 { unreadable, rec: None, tables, shaped: Set::empty(), funcs: Set::empty(), cls: false, kg: false, views, lcls,
          done: Map::empty(), run: None }
}
pub open spec fn p_begin(s: IS2, schema: int) -> IS2 {
    IS2 { run: Some(Run2 { schema, failed: false, warnings: false, ph: Ph::Ddl }), ..s }
}
pub open spec fn p_ddl(s: IS2, ok: bool) -> IS2 {
    if ok {
        IS2 { tables: s.tables.insert(s.run->Some_0.schema), shaped: s.shaped.insert(s.run->Some_0.schema),
              run: adv(s, Ph::Funcs), ..s }
    } else {
        IS2 { run: Some(Run2 { failed: true, warnings: s.run->Some_0.warnings || !f0102(), ph: Ph::Funcs, ..s.run->Some_0 }), ..s }
    }
}
pub open spec fn p_funcs(s: IS2) -> IS2 { IS2 { funcs: s.funcs.insert(s.run->Some_0.schema), run: adv(s, Ph::Deploy), ..s } }
pub open spec fn p_deploy(s: IS2, on: bool, ok: bool) -> IS2 {
    IS2 { cls: s.cls || (on && ok), run: Some(Run2 { warnings: s.run->Some_0.warnings || (on && !ok), ph: Ph::Kg, ..s.run->Some_0 }), ..s }
}
pub open spec fn p_kg(s: IS2) -> IS2 { IS2 { kg: s.kg || s.cls, run: adv(s, Ph::Record), ..s } }
pub open spec fn p_record(s: IS2) -> IS2 {
    IS2 { rec: if s.rec is None { Some(s.run->Some_0.schema) } else { s.rec }, run: adv(s, Ph::Replied), ..s }
}
pub open spec fn p_end(s: IS2) -> IS2 { IS2 { run: None, ..s } }
pub open spec fn p_upgrade(s: IS2, arg: int) -> IS2 { IS2 { shaped: up2(s, arg), ..s } }
pub open spec fn p_rmview(s: IS2, v: int, ok: bool) -> IS2 { IS2 { views: if ok { s.views.remove(v) } else { s.views }, ..s } }
pub open spec fn p_rmfirst(s: IS2, c: int, ok: bool) -> IS2 {
    IS2 { lcls: if ok { s.lcls.remove(c) } else { s.lcls }, done: s.done.insert(c, ok), ..s }
}

pub proof fn lemma_i_steps(s: IS2, schema: int, ok: bool, on: bool, arg: int)
    ensures
        s.run is None && (s.rec is None || s.rec == Some(schema)) ==> step2(s, IL2::Begin { schema }, p_begin(s, schema)),
        at(s, Ph::Ddl) ==> step2(s, IL2::Ddl { ok }, p_ddl(s, ok)),
        at(s, Ph::Funcs) ==> step2(s, IL2::Funcs, p_funcs(s)),
        at(s, Ph::Deploy) ==> step2(s, IL2::Deploy { on, ok }, p_deploy(s, on, ok)),
        at(s, Ph::Kg) ==> step2(s, IL2::Kg { ok: true }, p_kg(s)),
        at(s, Ph::Record) ==> step2(s, IL2::Record, p_record(s)),
        at(s, Ph::Replied) ==> step2(s, IL2::Reply { warned: s.run->Some_0.warnings, ready: s.cls }, p_end(s)),
        s.run is Some ==> step2(s, IL2::Stop, p_end(s)),
        step2(s, IL2::Access { schema, adm: access2(s, schema) }, s),
        step2(s, IL2::Feature { rdy: if s.cls { Ready::Done } else { Ready::NotDeployed } }, s),
        step2(s, IL2::Upgrade { arg }, p_upgrade(s, arg)),
        s.views.contains(arg) ==> step2(s, IL2::RmView { v: arg, ok, reported: if f0101() { true } else { ok } }, p_rmview(s, arg, ok)),
        s.lcls.contains(arg) && !s.done.contains_key(arg) ==> step2(s, IL2::RmFirst { c: arg, ok, reported: ok }, p_rmfirst(s, arg, ok)),
        s.done.contains_key(arg) ==> step2(s, IL2::RmLater { c: arg, reported: if f0101() { true } else { s.done[arg] } }, s),
{
}

} // verus!
