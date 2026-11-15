//! Development runner for module 09 alone (a compile error in another module does not block it).
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release --bin dev09 -- [--only ID ...]
#[path = "../m09.rs"]
mod m09;
fn main() { breadth_b::run_all(m09::checks(), false) }
