//! Development runner for module 10 alone (a compile error in another module does not block it).
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release --bin dev10 -- [--only ID ...]
#[path = "../m10.rs"]
mod m10;
fn main() { breadth_b::run_all(m10::checks(), false) }
