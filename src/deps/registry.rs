//! Dependency definitions and URLs
//!
//! All dependency metadata is defined here for easy updates.

/// DirectX June 2010 redistributable URL (used for xact, d3dx9, d3dcompiler, etc.)
pub const DIRECTX_JUN2010_URL: &str =
    "https://files.holarse-linuxgaming.de/mirrors/microsoft/directx_Jun2010_redist.exe";

/// DirectX June 2010 archive filename
pub const DIRECTX_JUN2010_FILE: &str = "directx_Jun2010_redist.exe";

/// Dependency type
#[derive(Debug, Clone)]
pub enum DepType {
    /// Run .exe installer with Proton
    /// args: installer arguments (e.g., ["/q", "/norestart"])
    ExeInstaller { args: &'static [&'static str] },

    /// Extract DLLs from DirectX redistributable cabs
    /// cab_patterns: patterns to match cab files (e.g., "*_xact_*x86*")
    /// dll_patterns: patterns to extract from cabs (e.g., "xactengine*.dll")
    DirectXCab {
        cab_patterns: &'static [&'static str],
        dll_patterns: &'static [&'static str],
    },

    /// Direct DLL download - copy directly to system32/syswow64
    DirectDll,

    /// GitHub release - skipped (Proton includes vkd3d)
    GitHubRelease,
}

/// URL pair for x86 and optional x64
#[derive(Debug, Clone)]
pub struct DepUrls {
    pub x86: &'static str,
    pub x64: Option<&'static str>,
}

/// Dependency definition
#[derive(Debug, Clone)]
pub struct Dependency {
    pub id: &'static str,
    pub name: &'static str,
    pub dep_type: DepType,
    pub urls: DepUrls,
    pub dll_overrides: &'static [&'static str],
    /// DLLs to register with regsvr32 (COM components like xactengine, xaudio)
    pub register_dlls: &'static [&'static str],
    /// File to check if already installed (relative to system32)
    pub installed_check: &'static str,
}

/// Standard dependencies for mod managers
pub const STANDARD_DEPS: &[Dependency] = &[
    // Visual C++ 2015-2022 Runtime
    Dependency {
        id: "vcrun2022",
        name: "Visual C++ 2015-2022 Runtime",
        dep_type: DepType::ExeInstaller {
            args: &["/q", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://aka.ms/vs/17/release/vc_redist.x86.exe",
            x64: Some("https://aka.ms/vs/17/release/vc_redist.x64.exe"),
        },
        dll_overrides: &[
            "concrt140",
            "msvcp140",
            "msvcp140_1",
            "msvcp140_2",
            "msvcp140_atomic_wait",
            "msvcp140_codecvt_ids",
            "vcamp140",
            "vccorlib140",
            "vcomp140",
            "vcruntime140",
            "vcruntime140_1",
        ],
        register_dlls: &[],
        installed_check: "vcruntime140.dll",
    },
    // DirectX XACT Audio (32-bit)
    Dependency {
        id: "xact",
        name: "DirectX XACT Audio (32-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*_xact_*x86*", "*_x3daudio_*x86*", "*_xaudio_*x86*"],
            dll_patterns: &[
                "xactengine*.dll",
                "xaudio*.dll",
                "x3daudio*.dll",
                "xapofx*.dll",
            ],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[
            "xaudio2_0", "xaudio2_1", "xaudio2_2", "xaudio2_3",
            "xaudio2_4", "xaudio2_5", "xaudio2_6", "xaudio2_7",
            "x3daudio1_0", "x3daudio1_1", "x3daudio1_2", "x3daudio1_3",
            "x3daudio1_4", "x3daudio1_5", "x3daudio1_6", "x3daudio1_7",
            "xapofx1_1", "xapofx1_2", "xapofx1_3", "xapofx1_4", "xapofx1_5",
            "xactengine2_0", "xactengine2_1", "xactengine2_2", "xactengine2_3",
            "xactengine2_4", "xactengine2_5", "xactengine2_6", "xactengine2_7",
            "xactengine2_8", "xactengine2_9", "xactengine2_10",
            "xactengine3_0", "xactengine3_1", "xactengine3_2", "xactengine3_3",
            "xactengine3_4", "xactengine3_5", "xactengine3_6", "xactengine3_7",
        ],
        // Register xactengine and xaudio DLLs (same as winetricks)
        // Note: xaudio2_8+ is not supported, only register 0-7
        register_dlls: &[
            "xactengine2_0.dll", "xactengine2_1.dll", "xactengine2_2.dll", "xactengine2_3.dll",
            "xactengine2_4.dll", "xactengine2_5.dll", "xactengine2_6.dll", "xactengine2_7.dll",
            "xactengine2_8.dll", "xactengine2_9.dll", "xactengine2_10.dll",
            "xactengine3_0.dll", "xactengine3_1.dll", "xactengine3_2.dll", "xactengine3_3.dll",
            "xactengine3_4.dll", "xactengine3_5.dll", "xactengine3_6.dll", "xactengine3_7.dll",
            "xaudio2_0.dll", "xaudio2_1.dll", "xaudio2_2.dll", "xaudio2_3.dll",
            "xaudio2_4.dll", "xaudio2_5.dll", "xaudio2_6.dll", "xaudio2_7.dll",
        ],
        installed_check: "xactengine3_7.dll",
    },
    // DirectX XACT Audio (64-bit)
    // Note: On 64-bit prefix, this goes to system32 (which holds 64-bit DLLs)
    Dependency {
        id: "xact_x64",
        name: "DirectX XACT Audio (64-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*_xact_*x64*", "*_x3daudio_*x64*", "*_xaudio_*x64*"],
            dll_patterns: &[
                "xactengine*.dll",
                "xaudio*.dll",
                "x3daudio*.dll",
                "xapofx*.dll",
            ],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[], // Same overrides as xact, already set
        // Register 64-bit xactengine and xaudio DLLs too
        register_dlls: &[
            "xactengine2_0.dll", "xactengine2_1.dll", "xactengine2_2.dll", "xactengine2_3.dll",
            "xactengine2_4.dll", "xactengine2_5.dll", "xactengine2_6.dll", "xactengine2_7.dll",
            "xactengine2_8.dll", "xactengine2_9.dll", "xactengine2_10.dll",
            "xactengine3_0.dll", "xactengine3_1.dll", "xactengine3_2.dll", "xactengine3_3.dll",
            "xactengine3_4.dll", "xactengine3_5.dll", "xactengine3_6.dll", "xactengine3_7.dll",
            "xaudio2_0.dll", "xaudio2_1.dll", "xaudio2_2.dll", "xaudio2_3.dll",
            "xaudio2_4.dll", "xaudio2_5.dll", "xaudio2_6.dll", "xaudio2_7.dll",
        ],
        installed_check: "xactengine3_7.dll",
    },
    // D3DCompiler 47 (direct DLL download - from Mozilla fxc2, same as winetricks)
    Dependency {
        id: "d3dcompiler_47",
        name: "DirectX Compiler 47",
        dep_type: DepType::DirectDll,
        urls: DepUrls {
            // Note: 32-bit file is named d3dcompiler_47_32.dll but installed as d3dcompiler_47.dll
            x86: "https://raw.githubusercontent.com/mozilla/fxc2/master/dll/d3dcompiler_47_32.dll",
            x64: Some("https://raw.githubusercontent.com/mozilla/fxc2/master/dll/d3dcompiler_47.dll"),
        },
        dll_overrides: &["d3dcompiler_47"],
        register_dlls: &[],
        installed_check: "d3dcompiler_47.dll",
    },
    // D3DCompiler 43 (32-bit)
    Dependency {
        id: "d3dcompiler_43",
        name: "DirectX Compiler 43 (32-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dcompiler_43*x86*"],
            dll_patterns: &["d3dcompiler_43.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &["d3dcompiler_43"],
        register_dlls: &[],
        installed_check: "d3dcompiler_43.dll",
    },
    // D3DCompiler 43 (64-bit)
    Dependency {
        id: "d3dcompiler_43_x64",
        name: "DirectX Compiler 43 (64-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dcompiler_43*x64*"],
            dll_patterns: &["d3dcompiler_43.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[], // Already set by 32-bit version
        register_dlls: &[],
        installed_check: "d3dcompiler_43.dll",
    },
    // D3DX9 (all versions, 32-bit)
    Dependency {
        id: "d3dx9",
        name: "DirectX 9 (32-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dx9*x86*"],
            dll_patterns: &["d3dx9*.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[
            "d3dx9_24", "d3dx9_25", "d3dx9_26", "d3dx9_27", "d3dx9_28",
            "d3dx9_29", "d3dx9_30", "d3dx9_31", "d3dx9_32", "d3dx9_33",
            "d3dx9_34", "d3dx9_35", "d3dx9_36", "d3dx9_37", "d3dx9_38",
            "d3dx9_39", "d3dx9_40", "d3dx9_41", "d3dx9_42", "d3dx9_43",
        ],
        register_dlls: &[],
        installed_check: "d3dx9_43.dll",
    },
    // D3DX9_43 (single version, for 64-bit)
    Dependency {
        id: "d3dx9_43_x64",
        name: "DirectX 9.43 (64-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dx9_43*x64*"],
            dll_patterns: &["d3dx9_43.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[], // Already set by d3dx9
        register_dlls: &[],
        installed_check: "d3dx9_43.dll",
    },
    // D3DX11_43 (32-bit)
    Dependency {
        id: "d3dx11_43",
        name: "DirectX 11 (32-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dx11_43*x86*"],
            dll_patterns: &["d3dx11_43.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &["d3dx11_43"],
        register_dlls: &[],
        installed_check: "d3dx11_43.dll",
    },
    // D3DX11_43 (64-bit)
    Dependency {
        id: "d3dx11_43_x64",
        name: "DirectX 11 (64-bit)",
        dep_type: DepType::DirectXCab {
            cab_patterns: &["*d3dx11_43*x64*"],
            dll_patterns: &["d3dx11_43.dll"],
        },
        urls: DepUrls {
            x86: DIRECTX_JUN2010_URL,
            x64: None,
        },
        dll_overrides: &[], // Already set by 32-bit version
        register_dlls: &[],
        installed_check: "d3dx11_43.dll",
    },
    // .NET Runtime 6.0
    Dependency {
        id: "dotnet6",
        name: ".NET Runtime 6.0",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://download.visualstudio.microsoft.com/download/pr/727d79cb-6a4c-4a6b-bd9e-af99ad62de0b/5cd3550f1589a2f1b3a240c745dd1023/dotnet-runtime-6.0.36-win-x86.exe",
            x64: Some("https://download.visualstudio.microsoft.com/download/pr/1a5fc50a-9222-4f33-8f73-3c78485a55c7/1cb55899b68fcb9d98d206ba56f28b66/dotnet-runtime-6.0.36-win-x64.exe"),
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe", // In Program Files
    },
    // .NET Runtime 7.0
    Dependency {
        id: "dotnet7",
        name: ".NET Runtime 7.0",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://download.visualstudio.microsoft.com/download/pr/b2e820bd-b591-43df-ab10-1eeb7998cc18/661ca79db4934c6247f5c7a809a62238/dotnet-runtime-7.0.20-win-x86.exe",
            x64: Some("https://download.visualstudio.microsoft.com/download/pr/be7eaed0-4e32-472b-b53e-b08ac3433a22/fc99a5977c57cbfb93b4afb401953818/dotnet-runtime-7.0.20-win-x64.exe"),
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe",
    },
    // .NET Runtime 8.0
    Dependency {
        id: "dotnet8",
        name: ".NET Runtime 8.0",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://download.visualstudio.microsoft.com/download/pr/3210417e-ab32-4d14-a152-1ad9a2fcfdd2/da097cee5aa85bd79b6d593e3866fb7f/dotnet-runtime-8.0.12-win-x86.exe",
            x64: Some("https://download.visualstudio.microsoft.com/download/pr/136f4593-e3cd-4d52-bc25-579cdf46e80c/8b98c1347293b48c56c3a68d72f586a1/dotnet-runtime-8.0.12-win-x64.exe"),
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe",
    },
    // .NET Runtime 9.0
    Dependency {
        id: "dotnet9",
        name: ".NET Runtime 9.0",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://builds.dotnet.microsoft.com/dotnet/Runtime/9.0.7/dotnet-runtime-9.0.7-win-x86.exe",
            x64: Some("https://builds.dotnet.microsoft.com/dotnet/Runtime/9.0.7/dotnet-runtime-9.0.7-win-x64.exe"),
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe",
    },
    // .NET Desktop Runtime 6.0
    Dependency {
        id: "dotnetdesktop6",
        name: ".NET Desktop Runtime 6.0",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://download.visualstudio.microsoft.com/download/pr/cdc314df-4a4c-4709-868d-b974f336f77f/acd5ab7637e456c8a3aa667661324f6d/windowsdesktop-runtime-6.0.36-win-x86.exe",
            x64: Some("https://download.visualstudio.microsoft.com/download/pr/f6b6c5dc-e02d-4738-9559-296e938dabcb/b66d365729359df8e8ea131197715076/windowsdesktop-runtime-6.0.36-win-x64.exe"),
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe",
    },
    // VKD3D-Proton (Vulkan D3D12) - Skipped, Proton includes vkd3d
    Dependency {
        id: "vkd3d",
        name: "VKD3D-Proton",
        dep_type: DepType::GitHubRelease,
        urls: DepUrls {
            x86: "",
            x64: None,
        },
        dll_overrides: &["d3d12", "d3d12core"],
        register_dlls: &[],
        installed_check: "d3d12.dll",
    },
    // .NET 9 SDK (for MO2/Vortex plugin development)
    Dependency {
        id: "dotnet9sdk",
        name: ".NET 9 SDK",
        dep_type: DepType::ExeInstaller {
            args: &["/quiet", "/norestart"],
        },
        urls: DepUrls {
            x86: "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe",
            x64: None, // SDK is x64 only, x86 URL used as primary
        },
        dll_overrides: &[],
        register_dlls: &[],
        installed_check: "dotnet.exe",
    },
];
