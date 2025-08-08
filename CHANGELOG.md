2.0.0 8/7/25

Regedits should now work!

Synthesis also has a few fixes (if anyone knows how to fix this process is being used by another application please let me know)

I've now added the ability to auto select proton versions to experimental (credit to STL for having a small portable binary for me to use). It also has a automatic setup where you can go through the entire process of install dependencies as well now.

Cyberpunk and Baldur's Gate 3 no longer need you to add launch options, I believe I have it in a state where everything should work and be automatically added to the winecfg see list below:
```
dwrite(dwrite.dll)
winmm(winmm.dll)
version(version.dll)
ArchiveXL(ArchiveXL.dll)
Codeware(Codeware.dll)
TweakXL(TweakXL.dll)
input_loader(input_loader.dll)
RED4ext(RED4ext.dll)
mod_settings(mod_settings.dll)
scc_lib(scc_lib.dll)
```
For now Hoolamike and Sky Tex Opti are missing until they are updated some more.

Revamped the menus to make them feel less cluttered.

Hopefully that should be all for now, I will be looking into making a gui for users as well (steamdeck).

1.4.0 4/30/25

Here's a changelog as well:
[Sky Text Opti](https://github.com/BenHUET/sky-tex-opti) has been added, it is a native tool that plans to recreate and do what VRAMr does better and faster. Currently it's faster and we only have one mode for right now, planning to have more in the future.

DotNet9 SDK has been added and will install alongside basic dependencies, this is for synthesis (tbh i have no idea if it's actually working correctly, please let me know)

Show dot files has now been added so that way you can access .local/steam or .steam when running mo2 if you don't want to make a separate stock game folder.

[CKPE](https://www.nexusmods.com/skyrimspecialedition/mods/71371)  has now been given support with basic dependencies as well via winhttp, and d3dcompiler_46, I do need to warn you dark mode doesn't work yet as it relies on Windows Aero, which wine/proton can't do yet.

And finally I have provided a fix for Xedit users which now allows you to drag and drop in columns. Said fix can be found/mentioned [here.](https://github.com/TES5Edit/TES5Edit/issues/774)
