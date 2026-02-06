fn main() {
    #[cfg(feature = "full")]
    slint_build::compile("ui/main.slint").unwrap();
}
