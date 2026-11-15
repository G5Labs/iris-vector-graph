//! M-12 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with that
//! variant's parameters from the initial state to a violation. Always compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m12_catalog::*;
use crate::i12_catalog::*;

verus! {

/// F-0707: pair 0 builds its index; pair 1 reads it without checking the graph it was built for.
pub proof fn cx_bm25_index_graph_unchecked_l2()
    ensures ({
        let s = run::<CatalogM<Bm25IndexGraphUncheckedAsBuilt>>(catalog_s0(), seq![CA::Create(0)]);
        let a = CA::Read(1, 0);
        s is Some && catalog_step::<Bm25IndexGraphUncheckedAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<Bm25IndexGraphUncheckedAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-0705: an index is built and records no graph.
pub proof fn cx_bm25_index_no_record_l1()
    ensures ({
        let t = run::<CatalogM<Bm25IndexNoRecordAsBuilt>>(catalog_s0(), seq![CA::Create(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let t = run::<CatalogM<Bm25IndexNoRecordAsBuilt>>(catalog_s0(), seq![CA::Create(0)])->0;
    assert(t.slots[0] is Some && t.slots[0]->0.rec is None);
}

/// F-0705: pair 1's index records no graph; a read for pair 0 takes it as the default graph's and uses it.
pub proof fn cx_bm25_index_no_record_l2()
    ensures ({
        let s = run::<CatalogM<Bm25IndexNoRecordAsBuilt>>(catalog_s0(), seq![CA::Create(1)]);
        let a = CA::Read(0, 1);
        s is Some && catalog_step::<Bm25IndexNoRecordAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<Bm25IndexNoRecordAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-0609: the fused search for pair 1 reads pair 0's IVF index.
pub proof fn cx_ivf_index_graph_unchecked_l2()
    ensures ({
        let s = run::<CatalogM<IvfIndexGraphUncheckedAsBuilt>>(catalog_s0(), seq![CA::Create(0)]);
        let a = CA::Read(1, 0);
        s is Some && catalog_step::<IvfIndexGraphUncheckedAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<IvfIndexGraphUncheckedAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-0601: the registry read fails and pair 1's write goes through into pair 0's artifact.
pub proof fn cx_identity_fail_open_l2()
    ensures ({
        let s = run::<CatalogM<IdentityFailOpenAsBuilt>>(catalog_s0(), seq![CA::Create(0)]);
        let a = CA::Write(1, 0, true);
        s is Some && catalog_step::<IdentityFailOpenAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<IdentityFailOpenAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-0901: pairs 0 and 2 share a name; building pair 2's plan overwrites pair 0's.
pub proof fn cx_short_hash_name_l3()
    ensures ({
        let t = run::<CatalogM<ShortHashNameAsBuilt>>(catalog_s0(), seq![CA::Create(0), CA::Create(2)]);
        t is Some && !law_l3(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C1: an unchecked read uses another pair's artifact.
pub proof fn cx_ctl_unchecked_read_l2()
    ensures ({
        let s = run::<CatalogM<CtlUncheckedRead>>(catalog_s0(), seq![CA::Create(0)]);
        let a = CA::Read(1, 0);
        s is Some && catalog_step::<CtlUncheckedRead>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<CtlUncheckedRead>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// C2: a short-hash name collision overwrites another pair's artifact.
pub proof fn cx_ctl_short_hash_l3()
    ensures ({
        let t = run::<CatalogM<CtlShortHash>>(catalog_s0(), seq![CA::Create(0), CA::Create(2)]);
        t is Some && !law_l3(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C3: an artifact without a recorded binding.
pub proof fn cx_ctl_no_record_l1()
    ensures ({
        let t = run::<CatalogM<CtlNoRecord>>(catalog_s0(), seq![CA::Create(0)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 2);
    let t = run::<CatalogM<CtlNoRecord>>(catalog_s0(), seq![CA::Create(0)])->0;
    assert(t.slots[0] is Some && t.slots[0]->0.rec is None);
}

/// C3: an unrecorded artifact of pair 1 is taken as pair 0's and used.
pub proof fn cx_ctl_no_record_l2()
    ensures ({
        let s = run::<CatalogM<CtlNoRecord>>(catalog_s0(), seq![CA::Create(1)]);
        let a = CA::Read(0, 1);
        s is Some && catalog_step::<CtlNoRecord>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<CtlNoRecord>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// C4: a failed check lets another pair's write through.
pub proof fn cx_ctl_fail_open_l2()
    ensures ({
        let s = run::<CatalogM<CtlFailOpen>>(catalog_s0(), seq![CA::Create(0)]);
        let a = CA::Write(1, 0, true);
        s is Some && catalog_step::<CtlFailOpen>(s->0, a) is Some
            && !law_l2(s->0, catalog_step::<CtlFailOpen>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

} // verus!
