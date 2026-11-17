// product 3eaa79cf: the PROV-O readers (iris_vector_graph/_engine/prov.py). Each reads the default graph's temporal
//   edges with one TemporalIndex.QueryWindow call over a window: prov_export over [ts_start, ts_end] (both inclusive),
//   prov_as_dict and prov_export_from_cypher over all time, then filter in Python. No call catches a failed read.
//   Provider premise (observed on IRIS 2026.1): QueryWindow builds one string and raises <MAXSTRING> when the window holds
//   more edges than fit (about 35,000 of these sizes).
use vstd::prelude::*;
verus! {

pub enum Out { Answer, Raised, EmptyWithWarning }

/// The read: an answer when the window's edge count fits, else the read raises.
pub open spec fn read(window_edges: nat, cap: nat) -> Out { if window_edges <= cap { Out::Answer } else { Out::Raised } }

/// The documented limit (SEMANTIC_LAYER.md): an over-large window is logged and exported empty, not raised.
pub open spec fn documented(window_edges: nat, cap: nat) -> Out { if window_edges <= cap { Out::Answer } else { Out::EmptyWithWarning } }

/// prov_export reads only its window; prov_as_dict reads the whole default graph's history.
pub open spec fn export_out(in_window: nat, cap: nat) -> Out { read(in_window, cap) }
pub open spec fn as_dict_out(total_default: nat, cap: nat) -> Out { read(total_default, cap) }

/// Inclusive window bounds.
pub open spec fn in_window(ts: int, lo: int, hi: int) -> bool { lo <= ts && ts <= hi }

/// P2/P3: both ends are included.
pub proof fn theorem_bounds_inclusive(t: int)
    ensures in_window(t, t, t), !in_window(t, t + 1, t + 2),
{}

/// P8 (bug-plt-109): an over-large window raises, where the guide says it is exported empty with a warning.
pub proof fn theorem_large_window_raises(n: nat, cap: nat)
    requires n > cap,
    ensures export_out(n, cap) == Out::Raised, documented(n, cap) == Out::EmptyWithWarning,
{}

/// P9 (bug-plt-110): once the default graph's whole history exceeds the cap, prov_as_dict fails for any edge, while
/// prov_export of a small window still answers.
pub proof fn theorem_as_dict_fails_on_large_history(small: nat, total: nat, cap: nat)
    requires small <= cap, total > cap,
    ensures as_dict_out(total, cap) == Out::Raised, export_out(small, cap) == Out::Answer,
{}

}
