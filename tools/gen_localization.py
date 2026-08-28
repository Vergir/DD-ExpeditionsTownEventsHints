"""
Builds the combined string table for Expeditions Town Events Hints.

The game has no ready-made "what does this town event do" string. It builds one at runtime
by nesting three translated format strings. This script performs the same assembly offline,
so every non-English line is the game's own wording rather than a translation by us:

    buff_stat_tooltip_resolve_xp_bonus_percent    '%+d%% Resolve XP'      <- amount * 100
      wrapped by buff_rule_tooltip_in_dungeon     '%s in %s'              <- buff_rule_data_tooltip_crypts
      = "+33% Resolve XP in Ruins"

English is NOT generated. It comes verbatim from src/strings.english.xml, where the lines
are hand-shortened to fit the notification field without clipping.

    python tools/gen_localization.py                    # preview the assembly
    python tools/gen_localization.py --out <file>       # english only
    python tools/gen_localization.py --out <file> --intl  # english + 11 generated
"""
import json, re, glob, sys, os, io, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GAME = os.path.abspath(os.path.join(REPO, "..", "..", "game", "DarkestDungeon"))
ENGLISH_SRC = os.path.join(REPO, "src", "strings.english.xml")

# The 8 events that can be granted as a quest reward, from
# campaign/town_events/town_events.quest_type_event_guarantees.json
EVENT_IDS = [
    "embark_party_buff_crypts_buff", "embark_party_buff_weald_buff",
    "embark_party_buff_cove_buff",   "embark_party_buff_warrens_buff",
    "free_abbey", "free_sanitarium", "provision_supply_free", "upgrade_tag_free_weapon",
]


def load_strings():
    """{language: {id: text}} across every string table the game ships."""
    langs = {}
    for f in glob.glob(os.path.join(GAME, "localization", "*.string_table.xml")):
        s = open(f, encoding="utf-8", errors="replace").read()
        for lm in re.finditer(r'<language id="([^"]+)">(.*?)</language>', s, re.S):
            d = langs.setdefault(lm.group(1), {})
            for e in re.finditer(r'<entry id="([^"]+)"><!\[CDATA\[(.*?)\]\]></entry>', lm.group(2), re.S):
                d.setdefault(e.group(1), e.group(2))
    return langs


def fmt(template, *args):
    """Apply printf-style args the way the game's formatter does.

    Also strips {?token} hints, which mark a substitution point but are not rendered.
    """
    if template is None:
        return None
    t = re.sub(r'\{\?[^}]*\}', '', template).replace('%%', '\x00')
    out, i = [], 0
    for part in re.split(r'(%[+]?[ds])', t):
        if re.fullmatch(r'%[+]?[ds]', part):
            if i >= len(args):
                return None
            v = args[i]; i += 1
            if part.endswith('d'):
                v = int(round(v))
                out.append(f"{v:+d}" if '+' in part else str(v))
            else:
                out.append(str(v))
        else:
            out.append(part)
    return ''.join(out).replace('\x00', '%')


def effect_lines(event, buffs, S):
    """The effect lines for one event, in the game's own wording, deduplicated."""
    lines = []

    # All Saints Day frees three Abbey activities, which the game would render as three
    # separate "<room> is Free" lines - four lines with the title, one more than the
    # notification field shows in ANY language. List the rooms once and apply the wrapper
    # a single time. Vanilla vocabulary throughout; only the composition changes.
    # Caregivers Convention (two rooms) benefits from the same rule.
    activities = [d["string_data"] for d in event["data"] if d["type"] == "free_activity"]
    if len(activities) > 1:
        names = [S.get("town_activity_name_" + a) for a in activities]
        if all(names):
            joined = fmt(S.get("town_event_info_format_free_activity"), ", ".join(names))
            if joined:
                return [joined]

    for d in event["data"]:
        t, sd, nd = d["type"], d["string_data"], d["number_data"]
        line = None

        if t == "embark_party_buff":
            b = buffs.get(sd)
            if not b:
                continue
            key = "buff_stat_tooltip_" + b["stat_type"] + (("_" + b["stat_sub_type"]) if b.get("stat_sub_type") else "")
            stat = fmt(S.get(key), b["amount"] * 100)
            if stat and b.get("rule_type") == "in_dungeon":
                region = S.get("buff_rule_data_tooltip_" + b["rule_data"]["string"])
                stat = fmt(S.get("buff_rule_tooltip_in_dungeon"), stat, region) if region else stat
            # Deliberately NOT wrapped in town_event_info_format_embark_party_buff
            # ("%s on Next Quest"). That wrapper is what pushes these lines past the 400px
            # field in every language - French 63 chars vs 37 without it - and it is
            # redundant here, since the block already sits under "Rewards" on a quest being
            # embarked upon. English drops the same words by hand.
            #
            # The other three data types keep their wrapper: it carries the meaning
            # ("%s is Free"), not just timing.
            line = stat

        elif t == "free_activity":
            line = fmt(S.get("town_event_info_format_free_activity"), S.get("town_activity_name_" + sd))

        elif t == "provision_item_type_cost_change":
            line = fmt(S.get("town_event_info_format_provision_item_type_cost_change"),
                       S.get("str_inventory_type_name_" + sd), nd * 100)

        elif t == "upgrade_tag_free":
            line = fmt(S.get("town_event_info_format_upgrade_tag_free"),
                       S.get("upgrade_tag_name_" + sd), nd)

        # damage_low and damage_high render identically - show the line once.
        if line and line not in lines:
            lines.append(line)
    return lines


def english_section():
    s = open(ENGLISH_SRC, encoding="utf-8").read()
    i = s.index('<language id="english">')
    return s[i:s.index("</language>", i) + len("</language>")]


def generated_sections(verbose=True):
    events = {e["id"]: e for e in json.load(
        open(os.path.join(GAME, "campaign", "town_events", "base.town_events.events.json"),
             encoding="utf-8-sig"))["events"]}
    raw = json.load(open(os.path.join(GAME, "shared", "buffs", "base.buffs.json"), encoding="utf-8-sig"))
    buffs = {b["id"]: b for b in (raw["buffs"] if isinstance(raw, dict) else raw) if "id" in b}
    langs = load_strings()

    out = []
    for lang in sorted(langs):
        if lang == "english":
            continue
        S = langs[lang]
        entries = []
        for eid in EVENT_IDS:
            title = S.get("town_event_title_" + eid)
            lines = effect_lines(events[eid], buffs, S)
            if not title or not lines:
                print(f"  ! {lang}/{eid}: skipped (missing title or effects)")
                continue
            # The compiler reads % as the start of a format directive and rejects the entry
            # when it is followed by '{' or a newline. Escaping to %% would compile, but
            # these titles are passed as an argument INTO other format strings rather than
            # being formatted themselves, so a %% could reach the screen literally. A
            # trailing space is invisible and keeps a single, safe %.
            body = "\n".join(l + " " if l.endswith("%") else l for l in lines)
            entries.append(
                f'    <entry id="town_event_title_{eid}"><![CDATA[{title}\n'
                f'{{colour_start|neutral}}{body}{{colour_end}}]]></entry>')
        if entries:
            out.append(f'  <language id="{lang}">\n' + "\n".join(entries) + "\n  </language>")
        if verbose:
            print(f"  {lang:10} {len(entries)}/8 events")
    return out


HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<!--
  GENERATED by tools/gen_localization.py - do not edit.
  English source of truth: src/strings.english.xml
-->
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--intl", action="store_true")
    a = ap.parse_args()

    sections = [english_section()]
    if a.intl or not a.out:
        sections += generated_sections(verbose=True)

    if not a.out:
        print("\n--- sample: Silence in the Crypts ---")
        events = {e["id"]: e for e in json.load(
            open(os.path.join(GAME, "campaign", "town_events", "base.town_events.events.json"),
                 encoding="utf-8-sig"))["events"]}
        raw = json.load(open(os.path.join(GAME, "shared", "buffs", "base.buffs.json"), encoding="utf-8-sig"))
        buffs = {b["id"]: b for b in (raw["buffs"] if isinstance(raw, dict) else raw) if "id" in b}
        langs = load_strings()
        for lang in ("russian", "german", "schinese", "french"):
            for l in effect_lines(events["embark_party_buff_crypts_buff"], buffs, langs[lang]):
                print(f"  [{lang:9}] {l}")
        return

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER + "<root>\n" + "\n\n".join(sections) + "\n</root>\n")
    print(f"  wrote {a.out}  ({len(sections)} language sections)")


if __name__ == "__main__":
    main()
