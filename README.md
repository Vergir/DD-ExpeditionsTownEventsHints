# Expeditions Town Events Hints

A Darkest Dungeon UI mod. Gather and Activate quests reward you with a Town Event, but the
quest screen only ever tells you its **name**. "Silence in the Crypts" doesn't tell
anything. This prints what the event actually does, underneath
the name.

```
Town Event:                      Town Event:
Silence in the Crypts     ->     Silence in the Crypts
                                 Ruins: +33% Resolve XP, +15% DMG
```

It covers the eight events that can appear as a quest reward: **Silence in the Crypts**,
**Sunshine in the Thicket**, **Gentle Tide**, **Fresh Air in the Tunnels** (Activate), and
**All Saints Day**, **Caregivers Convention**, **Lost and Found**, **Bumper Crop** (Gather).

## Installing

Copy one folder out of `dist/` into the game's `mods/` directory:

```
.../steamapps/common/Darkest Dungeon/mods/(one of the dist folders here)
```

Then enable it on the save slot in the in-game mod menu. Safe to add or remove
mid-campaign; it changes no gameplay, balance, or save data.

### Two builds

| | `expeditions_town_events_hints` | `expeditions_town_events_hints_intl` |
|---|---|---|
| Languages | English | All 12 |
| Layout change | none | town event line lifted 15px |
| Clipping | none | some, see below |

**Install one, not both.** English players want the plain build: the lines were written
short specifically to fit, so nothing is clipped and no layout file is touched.

The International build exists because most languages need more room than English does.
It lifts the town event line by 15px to buy back a line, which is enough for most events in
most languages — but in the longest combinations (French, Spanish, Portuguese, Korean) the
bottom of the last line is still clipped by the panel edge. Readable, not pretty.

Non-English text is **not translated by hand**. It's assembled from the game's own
translated strings, so it reads exactly the way the game words the same effects elsewhere, minus minor grammatical mistakes

## Building

```
python tools/build.py
```

`--preview` prints the assembled non-English lines without building anything, and
`--for-upload` stamps in the `ModDataPath` that `steam_workshop_upload.exe` wants. Run a
plain build afterwards to scrub it back out, since it is an absolute path to your own
checkout and should not be committed.

Everything under `dist/` is generated. Edit `src/`, never `dist/`.

Requires the game installed, since the build borrows three things from it: the
`localization.exe` compiler, `colours/base.colours.darkest` (which the compiler needs to
resolve `{colour_start|...}` tags), and the pristine `quest_select.layout.darkest` that the UI lift is applied to. `tools/build.py` resolves the game at `../../game/DarkestDungeon`
relative to the repo — adjust `GAME` if your checkout sits elsewhere.

## License

My code is MIT, Red Hook assets are not. See [LICENSE](LICENSE).

(Next paragraph is obligatory for any Darkest Dungeon mod)

Not an official Red Hook Studios product or product modification, and Red Hook Studios Inc.
is not responsible in any way for changes or damages that may result from using this mod.
Darkest Dungeon and the Darkest Dungeon logo are trademarks of Red Hook Studios Inc.
