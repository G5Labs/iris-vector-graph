//! Development runner for module 08 alone (a compile error in another module does not block it).
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release --bin dev08 -- [--only ID ...]
#[path = "../m08.rs"]
mod m08;
fn main() { breadth_b::run_all(m08::checks(), false) }
