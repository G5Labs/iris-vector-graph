//! Development runner for module 07 alone (a compile error in another module does not block it).
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release --bin dev07 -- [--only ID ...]
#[path = "../m07.rs"]
mod m07;
fn main() { breadth_b::run_all(m07::checks(), false) }
