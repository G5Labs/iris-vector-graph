// product 3eaa79cf: the install lifecycle (iteration 56, Part B). Each decision is a function of its inputs:
//   N  schema name   iris_vector_graph/schema_name.py validate_schema_name 143-164, resolve_schema_name 167-173,
//                    same_schema 138-140 (case-insensitive), schema_package 133-135.
//   F  first access  check_first_access 220-242, _why_not_current 249-267, read_record 176-181; engine.py
//                    _check_namespace_schema 1847-1867 (installs FirstAccessCheck.guard_methods on every public method
//                    but EXEMPT_METHODS); refuse_other_record 184-191 (class deploy).
//   S  setup record  _engine/schema.py _record_and_initialize 2198-2326: mismatch first, then how = existing / new /
//                    inferred / explicit / refuse (unrecorded_schemas), then refuse_package_clash (foreign_classes),
//                    then dry run (returns, writes nothing) or the width refusal, setup, and write_record only when
//                    nothing was recorded (write_record 194-198).
//   D  class deploy  _engine/class_deploy.py _unchanged 213-226, upload_and_compile 229-297 (marker killed before the
//                    load, set only after a clean compile), plan_packaged_classes 327-338, foreign_schema_classes 193-210.
//   W  vector width  _engine/schema.py _vector_column_action 1517-1537, _refuse_width_change 1564-1599,
//                    _migrate_vector_dimensions 1601-1686, reconcile_recorded_dimensions 1688-1713.
//   I  identity      embedding_identity.py conflicts 180-235; _engine/schema.py set_embedding_identity 1086-1222,
//                    adopt_embedding_identities 1256-1335, enforce_embedding_identity 1354-1397.
//   Q  quarantine    _engine/schema.py place_quarantined 1972-2070, list_quarantine 1913-1970.
// Names are abstracted to their canonical upper-case id (same_schema is equality on it); a name's text shape is the
// input of N. Widths are naturals; None is "no declared width" / "not counted".
use vstd::prelude::*;

verus! {

// =============================================================== N: schema name
pub struct NameShape { pub empty: bool, pub pct: bool, pub pattern_ok: bool, pub sqluser: bool, pub is_default: bool, pub under_code_pkg: bool }
pub enum NameRule { Empty, Percent, Pattern, SqlUser, CodePackage }
pub enum NameOut { Default, Accepted, Refused(NameRule) }

/// validate_schema_name: the checks in source order; the default name in any case is accepted before the package test.
pub open spec fn validate(n: NameShape) -> NameOut {
    if n.empty { NameOut::Refused(NameRule::Empty) }
    else if n.pct { NameOut::Refused(NameRule::Percent) }
    else if !n.pattern_ok { NameOut::Refused(NameRule::Pattern) }
    else if n.sqluser { NameOut::Refused(NameRule::SqlUser) }
    else if n.is_default { NameOut::Default }
    else if n.under_code_pkg { NameOut::Refused(NameRule::CodePackage) }
    else { NameOut::Accepted }
}
pub enum Src { Arg, Env, Default }
/// resolve_schema_name: the argument if given, else a non-empty IVG_SCHEMA_PREFIX, else Graph_KG (IRIS_SCHEMA_PREFIX never read).
pub open spec fn resolve(arg_given: bool, env_nonempty: bool) -> Src {
    if arg_given { Src::Arg } else if env_nonempty { Src::Env } else { Src::Default }
}

pub proof fn theorem_name_rules_refuse_before_default(n: NameShape)
    ensures
        (n.empty || n.pct || !n.pattern_ok || n.sqluser) ==> validate(n) is Refused,
        (!n.empty && !n.pct && n.pattern_ok && !n.sqluser && n.is_default) ==> validate(n) == NameOut::Default,
        (!n.empty && !n.pct && n.pattern_ok && !n.sqluser && !n.is_default && n.under_code_pkg) ==> validate(n) == NameOut::Refused(NameRule::CodePackage),
        validate(n) == NameOut::Accepted <==> (!n.empty && !n.pct && n.pattern_ok && !n.sqluser && !n.is_default && !n.under_code_pkg),
{}
pub proof fn theorem_arg_wins(env_nonempty: bool)
    ensures resolve(true, env_nonempty) == Src::Arg, resolve(false, true) == Src::Env, resolve(false, false) == Src::Default,
{}

// =============================================================== F: first access
/// A namespace as the first-access check sees it (Native API only).
pub struct Ns { pub record: Option<nat>, pub marker: Set<nat>, pub legacy: bool, pub traces: bool }
pub enum Access { Ok, Mismatch, NotUpgraded, Unfinished, NeverSetUp }

pub open spec fn first_access(ns: Ns, s: nat) -> Access {
    match ns.record {
        Some(r) => if r == s { Access::Ok } else { Access::Mismatch },
        None => if ns.marker.contains(s) { Access::Ok }
                else if ns.legacy { Access::NotUpgraded }
                else if ns.traces { Access::Unfinished }
                else { Access::NeverSetUp },
    }
}
/// An engine method call: exempt calls (setup, status, legacy removal, close) always run; others run only after an Ok check.
pub open spec fn call_runs(ns: Ns, s: nat, exempt: bool) -> bool { exempt || first_access(ns, s) == Access::Ok }

pub proof fn theorem_other_record_refused(ns: Ns, s: nat)
    requires ns.record is Some, ns.record.unwrap() != s,
    ensures first_access(ns, s) == Access::Mismatch, !call_runs(ns, s, false), call_runs(ns, s, true),
{}
pub proof fn theorem_unrecorded_reason_order(ns: Ns, s: nat)
    requires ns.record is None, !ns.marker.contains(s),
    ensures
        ns.legacy ==> first_access(ns, s) == Access::NotUpgraded,
        (!ns.legacy && ns.traces) ==> first_access(ns, s) == Access::Unfinished,
        (!ns.legacy && !ns.traces) ==> first_access(ns, s) == Access::NeverSetUp,
{}
/// As built: a namespace with no record whose IVG Schema holds this release's marker function is admitted (an
/// interrupted setup after its DDL, or a record removed), against install.schema.not_ready; KNOWN_ISSUES documents it
/// (bug-plt-133).
pub proof fn theorem_unrecorded_with_marker_admitted(ns: Ns, s: nat)
    requires ns.record is None, ns.marker.contains(s),
    ensures first_access(ns, s) == Access::Ok, call_runs(ns, s, false),
{}
/// As built: a recorded namespace is admitted whatever objects it lacks (the marker is not read once a record exists).
pub proof fn theorem_record_admits_without_objects(ns: Ns, s: nat)
    requires ns.record == Some(s),
    ensures first_access(ns, s) == Access::Ok,
{}

// =============================================================== S: setup's record decision
pub enum How { New, Existing, Inferred, Explicit }
pub enum SetupOut { Mismatch, Unrecorded, Clash, Plan(How), Ran(How) }
/// held_self: IVG's base tables in the engine's schema; held_other: in some other schema. explicit: schema_prefix
/// given or IVG_SCHEMA_PREFIX set. clash: the schema's package holds a class IVG did not create.
pub struct SetupIn { pub record: Option<nat>, pub s: nat, pub held_self: bool, pub held_other: bool, pub explicit: bool, pub clash: bool, pub dry: bool }
pub open spec fn how(i: SetupIn) -> Option<How> {
    if i.record is Some { Some(How::Existing) }
    else if !i.held_self && !i.held_other { Some(How::New) }
    else if !i.held_other { Some(How::Inferred) }
    else if i.explicit { Some(How::Explicit) }
    else { None }
}
pub open spec fn setup(i: SetupIn) -> SetupOut {
    if i.record is Some && i.record.unwrap() != i.s { SetupOut::Mismatch }
    else if how(i) is None { SetupOut::Unrecorded }
    else if i.clash { SetupOut::Clash }
    else if i.dry { SetupOut::Plan(how(i).unwrap()) }
    else { SetupOut::Ran(how(i).unwrap()) }
}
/// The record after setup (width refusal and DDL privilege errors aside, which come before write_record).
pub open spec fn record_after(i: SetupIn) -> Option<nat> {
    match setup(i) { SetupOut::Ran(h) => if h == How::Existing { i.record } else { Some(i.s) }, _ => i.record }
}

pub proof fn theorem_dry_run_and_refusals_keep_record(i: SetupIn)
    requires i.dry || setup(i) is Mismatch || setup(i) is Unrecorded || setup(i) is Clash,
    ensures record_after(i) == i.record,
{}
pub proof fn theorem_record_never_changes_once_written(i: SetupIn)
    requires i.record is Some,
    ensures record_after(i) == i.record,
{}
pub proof fn theorem_first_setup_records_engine_schema(i: SetupIn)
    requires i.record is None, !i.dry, !i.clash, !i.held_other || i.explicit,
    ensures record_after(i) == Some(i.s),
{}
/// As built: tables in another schema only are refused without a name and recorded "explicit" with one (as ADMIN_GUIDE
/// and the error's own advice describe), against spec FR-009 and install.schema.existing, which refuse even a named
/// schema in that case (bug-plt-026).
pub proof fn theorem_other_schema_needs_a_name(i: SetupIn)
    requires i.record is None, !i.held_self, i.held_other, !i.clash,
    ensures !i.explicit ==> setup(i) == SetupOut::Unrecorded,
            (i.explicit && !i.dry) ==> setup(i) == SetupOut::Ran(How::Explicit) && record_after(i) == Some(i.s),
{}
pub proof fn theorem_existing_after_first_run(i: SetupIn)
    requires i.record is None, !i.dry, !i.clash, !i.held_other,
    ensures ({ let j = SetupIn { record: record_after(i), held_self: true, ..i }; setup(j) == SetupOut::Ran(How::Existing) && record_after(j) == Some(i.s) }),
{}
/// After a setup records the schema, the first-access check admits that engine (the record branch).
pub proof fn theorem_setup_then_access(i: SetupIn, ns: Ns)
    requires ns.record == i.record, i.record is None, !i.dry, !i.clash, !i.held_other || i.explicit,
    ensures first_access(Ns { record: record_after(i), ..ns }, i.s) == Access::Ok,
{}

/// refuse_package_clash: a package holding someone else's classes refuses setup and its dry run before any DDL.
pub proof fn theorem_clash_refused_before_anything(i: SetupIn)
    requires i.record is None, i.clash, how(i) is Some,
    ensures setup(i) == SetupOut::Clash, record_after(i) == i.record,
{}

// =============================================================== D: class deploy
pub struct DeployIn { pub marker: Option<nat>, pub fp: nat, pub all_compiled: bool, pub force: bool, pub taken: bool, pub compile_ok: bool }
pub enum DeployOut { Unchanged, Refused, Deployed }
pub open spec fn unchanged(d: DeployIn) -> bool { d.marker == Some(d.fp) && d.all_compiled }
pub open spec fn deploy(d: DeployIn) -> DeployOut {
    if !d.force && unchanged(d) { DeployOut::Unchanged }
    else if d.taken { DeployOut::Refused }
    else { DeployOut::Deployed }
}
pub open spec fn marker_after(d: DeployIn) -> Option<nat> {
    match deploy(d) {
        DeployOut::Unchanged => d.marker,
        DeployOut::Refused => d.marker,
        DeployOut::Deployed => if d.compile_ok { Some(d.fp) } else { None },
    }
}
/// The dry run's "objectscript_compiled" is non-empty exactly when a deploy would load and compile.
pub open spec fn plan_compiles(d: DeployIn) -> bool { !(!d.force && unchanged(d)) }

/// deploy_packaged_classes calls refuse_other_record first: a namespace recorded under another schema gets nothing.
pub open spec fn deploy_admitted(record: Option<nat>, s: nat) -> bool { record is None || record == Some(s) }
pub proof fn theorem_deploy_refuses_other_record(record: Option<nat>, s: nat, ns: Ns)
    requires ns.record == record,
    ensures deploy_admitted(record, s) <==> !(first_access(ns, s) is Mismatch),
{}
pub proof fn theorem_skip_iff_same_fingerprint_and_all_compiled(d: DeployIn)
    requires !d.force,
    ensures (deploy(d) == DeployOut::Unchanged) <==> (d.marker == Some(d.fp) && d.all_compiled),
            plan_compiles(d) <==> !(deploy(d) == DeployOut::Unchanged),
{}
pub proof fn theorem_failed_deploy_retried(d: DeployIn)
    requires deploy(d) == DeployOut::Deployed, !d.compile_ok,
    ensures ({ let n = DeployIn { marker: marker_after(d), force: false, ..d }; deploy(n) != DeployOut::Unchanged }),
{}
pub proof fn theorem_clean_deploy_then_skip(d: DeployIn)
    requires deploy(d) == DeployOut::Deployed, d.compile_ok,
    ensures ({ let n = DeployIn { marker: marker_after(d), all_compiled: true, force: false, ..d }; deploy(n) == DeployOut::Unchanged }),
{}
pub proof fn theorem_missing_class_redeploys(d: DeployIn)
    requires !d.all_compiled, !d.taken,
    ensures deploy(d) == DeployOut::Deployed,
{}

// =============================================================== W: vector width
pub enum ColAction { Unchanged, Alter, Rewidth, Manual }
/// _vector_column_action: db None = no declared width; rows None = not counted.
pub open spec fn col_action(db: Option<nat>, dim: nat, rows: Option<nat>, rewidth: bool) -> ColAction {
    if db == Some(dim) { ColAction::Unchanged }
    else if db is None { ColAction::Alter }
    else if rows != Some(0nat) { ColAction::Manual }
    else if rewidth { ColAction::Alter } else { ColAction::Rewidth }
}
/// _refuse_width_change for one column: an empty column at another width without rewidth, or a populated one with it.
pub open spec fn width_refused(a: ColAction, rewidth: bool) -> bool { a == ColAction::Rewidth || (rewidth && a == ColAction::Manual) }
/// The declared width after a setup that was not refused.
pub open spec fn width_after(db: Option<nat>, dim: nat, rows: Option<nat>, rewidth: bool) -> Option<nat> {
    match col_action(db, dim, rows, rewidth) { ColAction::Alter => Some(dim), _ => db }
}
/// reconcile_recorded_dimensions: the registry width copies the declared one when there is one.
pub open spec fn reg_width_after(reg: Option<nat>, declared: Option<nat>) -> Option<nat> {
    if declared is Some { declared } else { reg }
}

pub proof fn theorem_populated_never_rewidened(db: nat, dim: nat, rows: Option<nat>, rewidth: bool)
    requires db != dim, rows != Some(0nat),
    ensures col_action(Some(db), dim, rows, rewidth) == ColAction::Manual,
            !width_refused(ColAction::Manual, rewidth) ==> width_after(Some(db), dim, rows, rewidth) == Some(db),
            rewidth ==> width_refused(col_action(Some(db), dim, rows, rewidth), rewidth),
{}
pub proof fn theorem_empty_other_width_needs_rewidth(db: nat, dim: nat)
    requires db != dim,
    ensures width_refused(col_action(Some(db), dim, Some(0nat), false), false),
            !width_refused(col_action(Some(db), dim, Some(0nat), true), true),
            width_after(Some(db), dim, Some(0nat), true) == Some(dim),
            reg_width_after(Some(db), width_after(Some(db), dim, Some(0nat), true)) == Some(dim),
{}
/// As built: when the declared-width lookup finds nothing (as for a schema named in another letter case than the one
/// first created: the catalog lookup is case-sensitive, provider premise P-CASE-LOOKUP), the column is altered to the
/// engine's width whatever it holds and without rewidth, and nothing is refused or listed for manual migration
/// (bug-plt-015). IRIS itself then refuses the ALTER of a populated column (P-ALTER-POPULATED), so only empty columns move.
pub proof fn theorem_unknown_width_altered_unasked(dim: nat, rows: Option<nat>, rewidth: bool)
    ensures col_action(None, dim, rows, rewidth) == ColAction::Alter, !width_refused(col_action(None, dim, rows, rewidth), rewidth),
            reg_width_after(Some(8nat), None) == Some(8nat),
{}
pub proof fn theorem_same_width_untouched(dim: nat, rows: Option<nat>, rewidth: bool)
    ensures col_action(Some(dim), dim, rows, rewidth) == ColAction::Unchanged, !width_refused(ColAction::Unchanged, rewidth),
{}

// =============================================================== I: embedding identity
pub struct Ident { pub model: Option<nat>, pub mech: Option<nat>, pub dim: Option<nat>, pub dtype: nat }
pub enum Conflict { None, Model, Mechanism, Width, Dtype }
/// conflicts(recorded, offered) on normalized identities: model, then mechanism (both known), then width, then dtype.
pub open spec fn conflicts(r: Ident, o: Ident) -> Conflict {
    if r.model is Some && o.model is Some && r.model != o.model { Conflict::Model }
    else if r.model is Some && o.model is Some && r.mech != o.mech { Conflict::Mechanism }
    else if r.dim is Some && o.dim is Some && r.dim != o.dim { Conflict::Width }
    else if r.dtype != o.dtype { Conflict::Dtype }
    else { Conflict::None }
}
pub enum SetBy { Adopted, Claimed, Forced }
pub struct Row { pub id: Ident, pub by: SetBy }
pub enum SetOut { Wrote(Row), Kept(Row), Refused(Conflict), BadArg }
/// set_embedding_identity: undeclared model refused; force overwrites; none recorded -> insert claimed; an unknown
/// recorded model with a compatible width is claimed (width kept when recorded); otherwise conflicts decide.
pub open spec fn set_identity(rec: Option<Row>, o: Ident, force: bool) -> SetOut {
    if o.model is None { SetOut::BadArg }
    else if force { SetOut::Wrote(Row { id: o, by: SetBy::Forced }) }
    else {
        match rec {
            None => SetOut::Wrote(Row { id: o, by: SetBy::Claimed }),
            Some(r) => if r.id.model is None && (r.id.dim is None || r.id.dim == o.dim) {
                    SetOut::Wrote(Row { id: Ident { model: o.model, mech: o.mech, dim: if r.id.dim is Some { r.id.dim } else { o.dim }, dtype: r.id.dtype }, by: SetBy::Claimed })
                } else if conflicts(r.id, o) != Conflict::None { SetOut::Refused(conflicts(r.id, o)) }
                else { SetOut::Kept(r) },
        }
    }
}
/// adopt_embedding_identities for one existing table: never overwrites; a new row records the declared width, model unknown.
pub open spec fn adopt(rec: Option<Row>, declared: Option<nat>, dtype: nat) -> Row {
    match rec { Some(r) => r, None => Row { id: Ident { model: None, mech: None, dim: declared, dtype }, by: SetBy::Adopted } }
}
/// enforce_embedding_identity: nothing recorded passes; otherwise the write is refused on any conflict.
pub open spec fn enforce_ok(rec: Option<Row>, o: Ident) -> bool {
    match rec { None => true, Some(r) => conflicts(r.id, o) == Conflict::None }
}

pub proof fn theorem_adopt_never_overwrites(r: Row, declared: Option<nat>, dtype: nat)
    ensures adopt(Some(r), declared, dtype) == r,
            adopt(None, declared, dtype).id.model is None && adopt(None, declared, dtype).id.dim == declared && adopt(None, declared, dtype).by == SetBy::Adopted,
{}
pub proof fn theorem_width_enforced_whatever_the_model(r: Row, o: Ident)
    requires r.id.dim is Some, o.dim is Some, r.id.dim != o.dim,
             !(r.id.model is Some && o.model is Some && (r.id.model != o.model || r.id.mech != o.mech)),
    ensures !enforce_ok(Some(r), o), conflicts(r.id, o) == Conflict::Width,
{}
pub proof fn theorem_claim_only_unknown(r: Row, o: Ident)
    requires o.model is Some, r.id.model is Some, r.id.model != o.model,
    ensures set_identity(Some(r), o, false) == SetOut::Refused(Conflict::Model),
            set_identity(Some(r), o, true) == SetOut::Wrote(Row { id: o, by: SetBy::Forced }),
{}
pub proof fn theorem_adopted_row_claimed_keeps_width(r: Row, o: Ident)
    requires o.model is Some, r.id.model is None, r.id.dim is Some, r.id.dim == o.dim,
    ensures set_identity(Some(r), o, false) is Wrote,
            set_identity(Some(r), o, false)->Wrote_0.by == SetBy::Claimed,
            set_identity(Some(r), o, false)->Wrote_0.id.dim == r.id.dim,
{}
pub proof fn theorem_same_model_kept(r: Row, o: Ident)
    requires r.id.model is Some, o.model == r.id.model, o.mech == r.id.mech, o.dim == r.id.dim, o.dtype == r.id.dtype,
    ensures set_identity(Some(r), o, false) == SetOut::Kept(r),
{}
pub proof fn theorem_undeclared_set_refused(rec: Option<Row>, o: Ident, force: bool)
    requires o.model is None,
    ensures set_identity(rec, o, force) == SetOut::BadArg,
{}

// =============================================================== Q: quarantine placement
pub struct Route { pub dim: Option<nat>, pub dtype: nat }
pub enum PlaceOut { NoRow, RowReadFails, NoRoute, Width, Dtype, NoNode, RouteRefused, Placed }
/// row: a quarantine row with that q_rowid exists. row_read_ok: _quarantined_row can read the fetched row; it reads the
/// DataRow after closing its cursor, which the IRIS DB-API driver refuses ("Cursor closed", provider premise
/// P-DATAROW-CLOSED, bug-srch-116), so over that driver it is false for every existing row. row_dim None is read as
/// width 0 (int(None or 0)). insert_ok: the route accepts the copy (its primary key holds no vector for that node).
pub open spec fn place(row: bool, row_read_ok: bool, route: Option<Route>, row_dim: Option<nat>, row_dtype: nat, node_in_graph: bool, insert_ok: bool) -> PlaceOut {
    if !row { PlaceOut::NoRow }
    else if !row_read_ok { PlaceOut::RowReadFails }
    else if route is None { PlaceOut::NoRoute }
    else if route.unwrap().dim is None || route.unwrap().dim.unwrap() != (if row_dim is Some { row_dim.unwrap() } else { 0nat }) { PlaceOut::Width }
    else if row_dtype != route.unwrap().dtype { PlaceOut::Dtype }
    else if !node_in_graph { PlaceOut::NoNode }
    else if !insert_ok { PlaceOut::RouteRefused }
    else { PlaceOut::Placed }
}
/// (quarantined rows, route rows, routes) after a placement: one transaction, insert then delete.
pub open spec fn place_effect(q: nat, r: nat, routes: nat, out: PlaceOut) -> (nat, nat, nat) {
    if out == PlaceOut::Placed && q > 0 { ((q - 1) as nat, r + 1, routes) } else { (q, r, routes) }
}

pub proof fn theorem_placement_conserves_and_never_creates_route(q: nat, r: nat, routes: nat, row: bool, row_read_ok: bool, route: Option<Route>,
        row_dim: Option<nat>, row_dtype: nat, node_in_graph: bool, insert_ok: bool)
    requires q > 0,
    ensures ({ let e = place_effect(q, r, routes, place(row, row_read_ok, route, row_dim, row_dtype, node_in_graph, insert_ok));
               e.0 + e.1 == q + r && e.2 == routes }),
{}
pub proof fn theorem_placed_only_when_every_check_passes(row: bool, row_read_ok: bool, route: Option<Route>, row_dim: Option<nat>, row_dtype: nat,
        node_in_graph: bool, insert_ok: bool)
    ensures place(row, row_read_ok, route, row_dim, row_dtype, node_in_graph, insert_ok) == PlaceOut::Placed <==>
        (row && row_read_ok && route is Some && route.unwrap().dim is Some
         && (if row_dim is Some { row_dim.unwrap() } else { 0nat }) == route.unwrap().dim.unwrap() && row_dtype == route.unwrap().dtype
         && node_in_graph && insert_ok),
{}
pub proof fn theorem_refused_row_stays(q: nat, r: nat, routes: nat, route: Option<Route>, row_dim: Option<nat>, row_dtype: nat, insert_ok: bool)
    requires q > 0,
    ensures place_effect(q, r, routes, place(true, true, route, row_dim, row_dtype, false, insert_ok)) == (q, r, routes),
            place_effect(q, r, routes, place(true, true, None, row_dim, row_dtype, true, insert_ok)) == (q, r, routes),
{}
/// As built over the IRIS DB-API driver: no existing quarantined row can be placed, whatever the route and node; the
/// row stays (bug-srch-116). The neighbor: a q_rowid with no row is refused as documented.
pub proof fn theorem_unreadable_row_never_placed(q: nat, r: nat, routes: nat, route: Option<Route>, row_dim: Option<nat>, row_dtype: nat,
        node_in_graph: bool, insert_ok: bool)
    requires q > 0,
    ensures place(true, false, route, row_dim, row_dtype, node_in_graph, insert_ok) == PlaceOut::RowReadFails,
            place_effect(q, r, routes, place(true, false, route, row_dim, row_dtype, node_in_graph, insert_ok)) == (q, r, routes),
            place(false, false, route, row_dim, row_dtype, node_in_graph, insert_ok) == PlaceOut::NoRow,
{}

} // verus!
