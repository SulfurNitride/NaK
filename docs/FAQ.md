# NaK Modding Helper - FAQ & Troubleshooting

Before I start yapping, I do this in my free time. If you like my work feel free to donate please :) [Ko-Fi](https://ko-fi.com/sulfurnitride)

So this is my first ever FAQ, so please if there are any issues let me know!

## Table of Contents

- [About NaK](#about-nak)
  - [What is the goal?](#what-is-the-goal)
  - [How does NaK work?](#how-does-nak-work)
  - [What dependencies does NaK use?](#what-dependencies-does-nak-use)
- [Known Issues](#known-issues)
  - [Synthesis NuGet Certificate Error](#synthesis-nuget-certificate-error)
  - [D.I.P. Closes in MO2](#dip-closes-in-mo2)
  - [Fallout 3/NV/Enderal Installation Prompts](#fallout-3nvenderal-installation-prompts)
  - [Mods Not Detected in xEdit/LOOT/BodySlide](#mods-not-detected-in-xeditlootbodyslide)
- [Getting Support](#getting-support)

---

## About NaK

### What is the goal?

The goal itself is pretty simple: to create a unified modding experience on Linux. By removing tedious steps like manually installing VCRUN2022 or setting WINEDLLOVERRIDES. Also by making quality of life improvements, like removing window decorations from Pandora or Vortex.

### How does NaK work?

NaK works by using Proton, whether that be from Steam or via the built-in [Proton-GE](https://github.com/GloriousEggroll/proton-ge-custom) downloader. It then creates a prefix inside of `~/NaK/Prefixes`, and installs dependencies and custom registry edits via [winetricks](https://github.com/Winetricks/winetricks) from GitHub.

### What dependencies does NaK use?

For the standard winetricks/protontricks dependencies, NaK installs the following in every prefix:

```
dotnet48 xact xact_x64 vcrun2022 dotnet6 dotnet7 dotnet8 dotnet9
dotnetdesktop6 d3dcompiler_47 d3dx11_43 d3dcompiler_43 d3dx9_43
d3dx9 vkd3d
```

Additionally, the DotNet 9 SDK is installed for Synthesis support.

---

## Known Issues

### Synthesis NuGet Certificate Error

**Problem:** Synthesis fails with the error:

```
'https://api.nuget.org/v3/index.json': The author primary signature's
timestamping certificate is not trusted by the trust provider.
```

**Solution:** Run these two commands, then restart the wine prefix:

```
wget https://cacerts.digicert.com/universal-root.crt.pem
sudo trust anchor --store universal-root.crt.pem
```

If this doesn't work, please make a report on the [GitHub Issues](https://github.com/SulfurNitride/NaK/issues) or in the [Discord](https://discord.gg/9JWQzSeUWt) inside the support threads.

### D.I.P. Closes in MO2

**Problem:** D.I.P. (Dynamic Item Patcher) closes immediately when opened in MO2.

**Solution:** Unfortunately, as far as I know, D.I.P. will not work on Linux as stated by the mod author :(

### Fallout 3/NV/Enderal Installation Prompts

**Problem:** Fallout 3, Fallout New Vegas, or Enderal prompts you to install/reinstall the game.

<img width="794" height="390" alt="image" src="https://github.com/user-attachments/assets/85980fc9-1453-49c5-b37e-4b33e5e841f4" />


**Solution:** This is a known issue with an easy fix. Inside of your mod folder (MO2 or Vortex), you will find a file called `Fix Game Registry`. You need to run this file in your terminal:

```
./Fix\ Game\ Registry
# or
./"Fix Game Registry"
```

Then:
1. Select your game from the menu
2. Provide the **Linux path** (not Windows path) to your game installation

Examples:
- `/home/luke/.steam/steam/steamapps/common/Fallout New Vegas`
- `/home/luke/Games/Fallout New Vegas Modding/Stock Game`

The script will apply the necessary registry fixes.

### Mods Not Detected in xEdit/LOOT/BodySlide

**Problem:** Tools like xEdit, LOOT, BodySlide, etc. don't detect your installed mods.

<img width="3718" height="1481" alt="image" src="https://github.com/user-attachments/assets/acd6b546-cd9f-49c5-be6d-84f24e98a00d" />


**Solution:** This is an issue with the Wine registry. Run the `Fix Game Registry` file and provide the Linux path of your game folder that you are modding. This should resolve the issue.

```
./"Fix Game Registry"
```

Then provide your game's Linux installation path when prompted.

---

## Getting Support

If you encounter issues not covered in this FAQ:

- **GitHub Issues:** [https://github.com/SulfurNitride/NaK/issues](https://github.com/SulfurNitride/NaK/issues)
- **Discord:** [https://discord.gg/9JWQzSeUWt](https://discord.gg/9JWQzSeUWt) (use support threads)

When reporting issues, please include:
- The game you're trying to mod
- Any error messages or logs
- Steps to reproduce the issue
