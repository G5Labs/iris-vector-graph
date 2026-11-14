//! Development runner for module 11 alone (a compile error in another module does not block it).
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo run --release --bin dev11 -- [--only ID ...]
#[path = "../m11.rs"]
mod m11;
fn main() { breadth_b::run_all(m11::checks(), false) }
