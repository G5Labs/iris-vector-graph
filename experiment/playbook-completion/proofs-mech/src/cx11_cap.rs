//! M-11 counterexamples: for each departing variant and each law it breaks, a call from the initial state that
//! violates it (the explorer's shortest counterexample, restated). Always compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m11_cap::*;
use crate::i11_cap::*;

verus! {

/// DemoServerAsBuilt: a caller without a key gets an effect or an answer.
pub proof fn cx_demo_server_l2()
    ensures ({
        let s = run::<CapM<DemoServerAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 0, ro: false, route: 1 };
        CapM::<DemoServerAsBuilt>::init(cap_s0()) && s is Some && cap_step::<DemoServerAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, a, cap_step::<DemoServerAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// AqlAsBuilt: a read-only caller with the valid key changes the store or a file.
pub proof fn cx_aql_l1()
    ensures ({
        let s = run::<CapM<AqlAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: true, route: 1 };
        CapM::<AqlAsBuilt>::init(cap_s0()) && s is Some && cap_step::<AqlAsBuilt>(s->0, a) is Some
            && !law_l1(s->0, a, cap_step::<AqlAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// AqlCodeTextAsBuilt: a keyed read-write caller touches a server file.
pub proof fn cx_aql_code_text_l3()
    ensures ({
        let s = run::<CapM<AqlCodeTextAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: false, route: 1 };
        CapM::<AqlCodeTextAsBuilt>::init(cap_s0()) && s is Some && cap_step::<AqlCodeTextAsBuilt>(s->0, a) is Some
            && !law_l3(s->0, a, cap_step::<AqlCodeTextAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// SnapshotFileHelpersAsBuilt: a read-only caller with the valid key changes the store or a file.
pub proof fn cx_snapshot_file_helpers_l1()
    ensures ({
        let s = run::<CapM<SnapshotFileHelpersAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: true, route: 1 };
        CapM::<SnapshotFileHelpersAsBuilt>::init(cap_s0()) && s is Some && cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a) is Some
            && !law_l1(s->0, a, cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// SnapshotFileHelpersAsBuilt: a caller without a key gets an effect or an answer.
pub proof fn cx_snapshot_file_helpers_l2()
    ensures ({
        let s = run::<CapM<SnapshotFileHelpersAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 0, ro: false, route: 1 };
        CapM::<SnapshotFileHelpersAsBuilt>::init(cap_s0()) && s is Some && cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, a, cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// SnapshotFileHelpersAsBuilt: a keyed read-write caller touches a server file.
pub proof fn cx_snapshot_file_helpers_l3()
    ensures ({
        let s = run::<CapM<SnapshotFileHelpersAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: false, route: 1 };
        CapM::<SnapshotFileHelpersAsBuilt>::init(cap_s0()) && s is Some && cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a) is Some
            && !law_l3(s->0, a, cap_step::<SnapshotFileHelpersAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// PrivilegeInEngineOnlyAsBuilt: a caller without a key gets an effect or an answer.
pub proof fn cx_privilege_in_engine_only_l2()
    ensures ({
        let s = run::<CapM<PrivilegeInEngineOnlyAsBuilt>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 0, ro: false, route: 1 };
        CapM::<PrivilegeInEngineOnlyAsBuilt>::init(cap_s0()) && s is Some && cap_step::<PrivilegeInEngineOnlyAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, a, cap_step::<PrivilegeInEngineOnlyAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// CtlWriteWithoutReadOnlyCheck: a read-only caller with the valid key changes the store or a file.
pub proof fn cx_ctl_write_without_read_only_check_l1()
    ensures ({
        let s = run::<CapM<CtlWriteWithoutReadOnlyCheck>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: true, route: 1 };
        CapM::<CtlWriteWithoutReadOnlyCheck>::init(cap_s0()) && s is Some && cap_step::<CtlWriteWithoutReadOnlyCheck>(s->0, a) is Some
            && !law_l1(s->0, a, cap_step::<CtlWriteWithoutReadOnlyCheck>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// CtlRouteWithoutKeyCheck: a caller without a key gets an effect or an answer.
pub proof fn cx_ctl_route_without_key_check_l2()
    ensures ({
        let s = run::<CapM<CtlRouteWithoutKeyCheck>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 0, ro: false, route: 0 };
        CapM::<CtlRouteWithoutKeyCheck>::init(cap_s0()) && s is Some && cap_step::<CtlRouteWithoutKeyCheck>(s->0, a) is Some
            && !law_l2(s->0, a, cap_step::<CtlRouteWithoutKeyCheck>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

/// CtlFileRoute: a keyed read-write caller touches a server file.
pub proof fn cx_ctl_file_route_l3()
    ensures ({
        let s = run::<CapM<CtlFileRoute>>(cap_s0(), Seq::<CA>::empty());
        let a = CA { key: 2, ro: false, route: 1 };
        CapM::<CtlFileRoute>::init(cap_s0()) && s is Some && cap_step::<CtlFileRoute>(s->0, a) is Some
            && !law_l3(s->0, a, cap_step::<CtlFileRoute>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

} // verus!
