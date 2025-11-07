# Fix Game Registry Key

LostDragonist w/ updates by WilliamImm

## Description

This is a standalone update for LostDragonist's "Fix Game Registry Key" plugin for Mod Organizer 2, to be compatible with the recently released 2.5.0 update. As per their original description:

> When running an application in MO2, this will check to make sure the registry key is correct according to the game being managed by MO2. This is useful when you have moved the game, when you've validated a game with Steam, when the game has updated, or if you have multiple installations of the game with different MO2 instances pointing to different installs.

> Whenever the registry needs to be changed, a User Account Control (UAC) prompt may show up from the Registry Console Tool. You need to accept this for the change to occur!

> For what it's worth, this functionality requires Powershell to be installed. Any modern Windows PC should have Powershell.

## Installation

Download and extract to MO2's plugins directory (<MO2 install>/plugins). It'll just work.

You'll know it's installed if you see "Check Game Registry Key" in the tools menu.

## FAQ

### What games are supported?

Skyrim (all releases), Fallout 3, Fallout New Vegas (including TTW), Fallout 4 (including VR), Oblivion, Morrowind, and Enderal (standalone)

### Why update this?

This actually arose out of a goal to make sure that the Epic Games version of Fallout: New Vegas was supported. It's a weird release but fully moddable thanks to tools like the Epic Games Patcher and the 2.5.0 update of Mod Organizer 2. One hurdle though is that this version of the game *never* updates the registry, something which programs like xEdit depend on to work.

RJ on the ModdingLinked discord alerted (reminded?) me to the existence of LostDragonist's MO2 plugins, one of which happned to be this, a *very specifically* useful plugin for creating the registry key that the Epic version does not create.

Of course, it's useful beyond that, but it just happened to be bacon-saving here.

As LostDragonist has no current intention of updating their plugins, I might as well do so. Familiar territory, eh?

### Linux support?

Untested, unlikely. The original script uses Powershell. The cross section of people who would need this on Linux is very slim.

### Will you update EBQO?

No.

## Credits

Thanks to LostDragonist for creating the original plugin! You can find their plugin collection at https://www.nexusmods.com/site/mods/82

Thanks to the ModdingLinked community, in particular VishVadeva for Viva New Vegas & RJ for assistance with getting the Epic Games Fallout New Vegas working in the first place!