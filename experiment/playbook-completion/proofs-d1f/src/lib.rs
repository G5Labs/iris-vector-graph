//! Completion audit, PROOFS-D1F lane (proof debt D-1, playbook §3.3). See PROOFS.md.
//!
//! Each family is an L1 business contract, an L2 machine over the stored or protocol state, `Refines<L1>` for every
//! L2 step, both levels' `SafeContract` invariants, `theorem_raw_executions_refine`, its broken-implementation
//! controls and a non-vacuity witness:
//! - `fhir_*`: module 15, a FHIR graph's sync against erase and durable removal, its sync task and its registration;
//!   `fhir_progress`: the watermark advances under explicit fairness (actors::fairness).
//! - `call_*`: modules 16 and 17, one HTTP call through IVGClient and the Cypher HTTP server (retries after
//!   ambiguous outcomes on both sides, the server's status map).
//! - `unit_*`: module 16, a unit of work over a Bolt explicit transaction and the Neo4j HTTP commit route.
//! - `auth_*`: modules 16 and 17, the authorization boundary of a running server (key gate, read-only, listener
//!   addresses, graph names) and the SDK's mapping of refusals.
//! - `sqla_*`: module 17, the SQL adapter's pass-through (read_only, error answers) and node reads (graph scope).
//! - `opsc_*`: module 17, the status report's unknown parts, capability claims and the driver pin.
//! - `cx_*` (only with their control feature): proved counterexamples, a run of the L2 step relation (as the control
//!   changes it) from its initial state to a step that is not an L1 step (for the progress-only control, a fair
//!   infinite execution whose rank never reaches 0).
//! - `witness_*` (only without their family's controls): non-vacuity runs of the reviewed L2 machines.
pub mod fhir_l1;
pub mod fhir_l2;
pub mod fhir_runs;
pub mod fhir_progress;
#[cfg(feature = "control_hd1503_erase_ignores_sync_lock")]
pub mod cx_hd1503;
#[cfg(feature = "control_fc1501_schedule_untransacted")]
pub mod cx_fc1501;
#[cfg(feature = "control_f1511_upsert_before_load")]
pub mod cx_f1511;
#[cfg(feature = "control_progress_rederive_restart")]
pub mod cx_progress;
#[cfg(not(any(feature = "control_hd1503_erase_ignores_sync_lock", feature = "control_fc1501_schedule_untransacted",
              feature = "control_f1511_upsert_before_load", feature = "control_progress_rederive_restart")))]
pub mod witness_fhir;
pub mod call_l1;
pub mod call_l2;
pub mod call_runs;
#[cfg(feature = "control_fc1604_server_reruns_write")]
pub mod cx_fc1604;
#[cfg(feature = "control_fc1602_unknown_as_client_error")]
pub mod cx_fc1602;
#[cfg(feature = "control_fc1703_client_resends_write")]
pub mod cx_fc1703;
#[cfg(not(any(feature = "control_fc1604_server_reruns_write", feature = "control_fc1602_unknown_as_client_error",
              feature = "control_fc1703_client_resends_write")))]
pub mod witness_call;
pub mod unit_l1;
pub mod unit_l2;
pub mod unit_runs;
#[cfg(feature = "control_f1601_bolt_run_commits")]
pub mod cx_f1601;
#[cfg(feature = "control_f1610_tx_commit_per_statement")]
pub mod cx_f1610;
#[cfg(not(any(feature = "control_f1601_bolt_run_commits", feature = "control_f1610_tx_commit_per_statement")))]
pub mod witness_unit;
pub mod auth_l1;
pub mod auth_l2;
#[cfg(feature = "control_f1614_app_without_key_gate")]
pub mod cx_f1614;
#[cfg(feature = "control_fc1603_bolt_binds_every_interface")]
pub mod cx_fc1603;
#[cfg(feature = "control_f1714_unmapped_refusal")]
pub mod cx_f1714;
#[cfg(not(any(feature = "control_f1614_app_without_key_gate", feature = "control_fc1603_bolt_binds_every_interface",
              feature = "control_f1714_unmapped_refusal")))]
pub mod witness_auth;
pub mod sqla_l1;
pub mod sqla_l2;
pub mod sqla_runs;
#[cfg(any(feature = "control_hd1701_read_only_ignored", feature = "control_hd1701_write_reported_failed"))]
pub mod cx_hd1701;
#[cfg(feature = "control_f1701_unscoped_merge")]
pub mod cx_f1701;
#[cfg(not(any(feature = "control_hd1701_read_only_ignored", feature = "control_hd1701_write_reported_failed",
              feature = "control_f1701_unscoped_merge")))]
pub mod witness_sqla;
pub mod opsc_l1;
pub mod opsc_l2;
#[cfg(feature = "control_f1713_status_parts_short")]
pub mod cx_f1713;
#[cfg(feature = "control_fc1706_driver_floor")]
pub mod cx_fc1706;
#[cfg(not(any(feature = "control_f1713_status_parts_short", feature = "control_fc1706_driver_floor")))]
pub mod witness_opsc;
