// As-built NativeRoute held-call state machine, 3eaa79cf. Trial timing medians and drift remain open.
use vstd::prelude::*;
verus! {
pub enum Path { Native, Sql }
pub struct Route { pub trial: bool, pub held: Path, pub failed: bool, pub since: nat,
    pub native_ms: nat, pub sql_runs: nat, pub last: Option<Path> }
pub open spec fn start_trial(r: Route) -> Route {
    Route { trial: true, native_ms: 0, sql_runs: 0, last: None, ..r }
}
pub open spec fn next_path(r: Route) -> Path {
    if !r.trial { r.held }
    else if r.native_ms < 2 { Path::Native }
    else if r.sql_runs == 0 { Path::Sql }
    else if r.last == Some(Path::Sql) { Path::Native } else { Path::Sql }
}
pub open spec fn held_run(r: Route, path: Path, recheck: Option<nat>) -> Route {
    if path != r.held || r.failed { r }
    else {
        let t = Route { since: r.since+1, ..r };
        match recheck {
            Some(n) => if n > 0 && t.since >= n { start_trial(t) } else { t },
            None => t,
        }
    }
}
pub open spec fn sql_failed(r: Route) -> Route {
    Route { trial: false, held: Path::Native, failed: true, since: 0, ..r }
}
pub proof fn theorem_before_and_at_threshold(r: Route,n: nat)
    requires !r.trial,!r.failed,n>1,r.since==n-2,
    ensures !held_run(r,r.held,Some(n)).trial,
        held_run(held_run(r,r.held,Some(n)),r.held,Some(n)).trial,
        next_path(held_run(held_run(r,r.held,Some(n)),r.held,Some(n)))==Path::Native,
{}
pub proof fn theorem_reset_derives_native_first(r: Route)
    ensures next_path(start_trial(r))==Path::Native,
        start_trial(r).native_ms==0,start_trial(r).sql_runs==0,start_trial(r).last==None,
{}
pub proof fn theorem_disabled_recheck_stays_held(r: Route)
    requires !r.trial,!r.failed,
    ensures !held_run(r,r.held,None).trial,!held_run(r,r.held,Some(0)).trial,
{}
pub proof fn theorem_other_path_does_not_advance(r: Route,p: Path,n: nat)
    requires p!=r.held,
    ensures held_run(r,p,Some(n))==r,
{}
pub proof fn theorem_sql_failure_survives_rechecks(r: Route,n: nat)
    ensures held_run(sql_failed(r),Path::Native,Some(n))==sql_failed(r),
        next_path(held_run(sql_failed(r),Path::Native,Some(n)))==Path::Native,
{}
pub proof fn theorem_trial_neighbor_routes(r: Route)
    requires r.trial,r.native_ms>=2,
    ensures r.sql_runs==0 ==> next_path(r)==Path::Sql,
        r.sql_runs>0 && r.last==Some(Path::Sql) ==> next_path(r)==Path::Native,
        r.sql_runs>0 && r.last!=Some(Path::Sql) ==> next_path(r)==Path::Sql,
{}
}
