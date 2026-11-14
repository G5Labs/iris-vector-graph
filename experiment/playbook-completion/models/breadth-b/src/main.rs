//! Breadth lane B model checks (modules 07 text search, 08 Cypher SQL, 09 native executor, 10 algorithms, 11 ledger).
//!
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release -- [--only ID|PREFIX* ...] [--list]
//!
//! Each module file `src/mNN.rs` documents its machines: the abstracted real state (globals/tables at pin 3eaa79cf
//! with path:lines), the I-statements kept as invariants, the B/X statements kept as action properties, the as-built
//! design reproducing each modelable finding, the reviewed design (where decisions.md supports or assumes the
//! contract), one negative control per machine (a mutant the checker must catch) and sharpness witnesses (key states
//! reachable; AG EF where progress matters). Results: `RESULTS.json` (rebuilt from `results/*.json`).
mod m07;
mod m08;
mod m09;
mod m10;
mod m11;

fn main() {
    let mut all = Vec::new();
    all.extend(m07::checks());
    all.extend(m08::checks());
    all.extend(m09::checks());
    all.extend(m10::checks());
    all.extend(m11::checks());
    let prune = std::env::args().all(|a| a != "--only");
    breadth_b::run_all(all, prune)
}
