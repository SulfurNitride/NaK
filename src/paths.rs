use std::{path::PathBuf, sync::LazyLock};

pub static DEFAULT_NAK_PATH: LazyLock<PathBuf> = LazyLock::new(|| {
    let mut path = std::env::home_dir().unwrap_or_default();
    
    if std::env::var("NAK_XDG_PATH").is_ok() {
        path.push(".config")
    }
    
    path.push("NaK");
    path
});

/// Computes the path from the NaK config directory based on the arguments.
///
/// Returns a `&Path` referencing the config directory itself if no arguments are passed in, or a
/// `PathBuf` created by joining all of the arguments to the base config directory if at least
/// one argument is passed in.
///
/// # Examples
///
/// ```
/// // Assuming `NAK_XDG_PATH` is not set specified, the default config path is ~/NaK
/// assert_eq!(Some(nak_path!()), std::env::home_dir().join("Nak"));
/// assert_eq!(Some(nak_path!("foo", "bar")), std::env::home_dir().join("Nak").join("foo").join("bar"));
/// ```
#[macro_export]
macro_rules! nak_path {
    () => {
        $crate::paths::DEFAULT_NAK_PATH.as_path()
    };

    ( $( $path:expr ),+ $(,)? ) => {
        [
            $crate::paths::DEFAULT_NAK_PATH.as_path(),
            $( std::path::Path::new(&$path) ),+
        ].into_iter().collect::<std::path::PathBuf>()
    };
}
