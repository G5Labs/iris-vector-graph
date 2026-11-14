//! Completion audit, PROOFS-D1E lane (proof debt D-1, playbook §3.3). See PROOFS.md.
pub mod inst_l1;
pub mod inst_l2;
pub mod inst_runs;
#[cfg(feature = "control_f0103_marker_admits")]
pub mod cx_f0103;
#[cfg(feature = "control_f0102_failure_only_logged")]
pub mod cx_f0102;
#[cfg(feature = "control_f0109_upgrade_default_schema")]
pub mod cx_f0109;
#[cfg(feature = "control_f0101_removed_unchecked")]
pub mod cx_f0101;
#[cfg(not(any(feature = "control_f0103_marker_admits", feature = "control_f0102_failure_only_logged",
              feature = "control_f0109_upgrade_default_schema", feature = "control_f0101_removed_unchecked")))]
pub mod witness_inst;
pub mod gid_l1;
pub mod gid_l2;
pub mod gid_runs;
#[cfg(feature = "control_f0202_writer_skips_name_check")]
pub mod cx_f0202;
#[cfg(feature = "control_f0206_hydrate_from_default")]
pub mod cx_f0206;
#[cfg(feature = "control_f0106_keys_join_on_id")]
pub mod cx_f0106;
#[cfg(not(any(feature = "control_f0202_writer_skips_name_check", feature = "control_f0206_hydrate_from_default",
              feature = "control_f0106_keys_join_on_id")))]
pub mod witness_gid;
pub mod gmode_l1;
pub mod gmode_l2;
pub mod gmode_runs;
#[cfg(feature = "control_f0201_ekey0_guard")]
pub mod cx_f0201;
#[cfg(feature = "control_f0208_mode_cached_forever")]
pub mod cx_f0208;
#[cfg(feature = "control_f0207_set_off_unlocked")]
pub mod cx_f0207;
#[cfg(not(any(feature = "control_f0201_ekey0_guard", feature = "control_f0208_mode_cached_forever",
              feature = "control_f0207_set_off_unlocked")))]
pub mod witness_gmode;
pub mod acache_l1;
pub mod acache_l2;
pub mod acache_runs;
#[cfg(feature = "control_f1004_create_moves_no_token")]
pub mod cx_f1004;
#[cfg(feature = "control_f1003_owner_cap")]
pub mod cx_f1003;
#[cfg(feature = "control_fc1001_read_creates_routines")]
pub mod cx_fc1001;
#[cfg(not(any(feature = "control_f1004_create_moves_no_token", feature = "control_f1003_owner_cap",
              feature = "control_fc1001_read_creates_routines")))]
pub mod witness_acache;
pub mod atrav_l1;
pub mod atrav_l2;
pub mod atrav_runs;
#[cfg(feature = "control_hd1003_direction_unchecked")]
pub mod cx_hd1003;
#[cfg(feature = "control_f1008_every_graph_mixed")]
pub mod cx_f1008;
#[cfg(not(any(feature = "control_hd1003_direction_unchecked", feature = "control_f1008_every_graph_mixed")))]
pub mod witness_atrav;
