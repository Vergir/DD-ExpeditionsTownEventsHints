# Builds both mods into dist/ from src/.
#
#   pwsh -File tools/build.ps1
#
# Output is exactly what a Workshop subscriber needs and nothing else. The game reads only
# the compiled .loc2 and the .darkest layout - Darkest.exe contains zero references to
# *.string_table.xml, so the source XML, this script and the generator are dev-only and are
# deliberately NOT copied into dist/.
#
# Requires the game to be present (localization.exe, colours/, and the pristine layout file
# all come from it). Adjust $game below if your checkout is not next to the game copy.

param(
    # Stamp ModDataPath (an absolute path to this checkout) into dist/*/project.xml.
    # Only steam_workshop_upload.exe needs it - the game does not, and a local mod loads
    # fine with nothing but <Title>. It is left out by default so the committed dist/ does
    # not publish a local filesystem path. Run with -ForUpload immediately before dragging
    # project.xml onto the uploader, then re-run plain to scrub it back out.
    [switch]$ForUpload
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$game = Resolve-Path "$repo\..\..\game\DarkestDungeon"

# How far to lift the town event line, in pixels, for the International build. Longer
# translations need the room; English does not and gets no layout override at all.
# The layout is re-derived from the game's pristine file on every build, so a game patch
# that touches quest_select.layout.darkest is picked up instead of silently reverted.
$LIFT_PX = 15

$variants = @(
    @{ name = 'expeditions_town_events_hints';      intl = $false; project = 'project.english.xml'; icon = 'preview_icon.english.png' }
    @{ name = 'expeditions_town_events_hints_intl'; intl = $true;  project = 'project.intl.xml';    icon = 'preview_icon.intl.png' }
)

function Build-Loc2 {
    # localization.exe scans the tree named by project_paths.txt and needs a colours/ folder
    # to resolve {colour_start|...} tags, so compile in a throwaway sandbox.
    param($xml, $work)
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path "$work\_windows\win32", "$work\localization", "$work\colours" | Out-Null
    Copy-Item "$game\_windows\win32\localization.exe" "$work\_windows\win32\"
    Copy-Item "$game\_windows\win32\*.dll"            "$work\_windows\win32\"   # else exit 0xC0000135
    Copy-Item "$game\colours\*.darkest"               "$work\colours\"
    Copy-Item $xml                                    "$work\localization\"
    Set-Content -Path "$work\localization\project_paths.txt" -Value '..' -NoNewline

    Push-Location "$work\localization"
    try   { $out = & "$work\_windows\win32\localization.exe" 2>&1 | Out-String }
    finally { Pop-Location }
    if ($out -notmatch 'SUCCESS') { Write-Output $out; throw "localization.exe failed" }
    Get-ChildItem "$work\localization\*.loc2"
}

foreach ($v in $variants) {
    $name = $v.name
    $dist = Join-Path "$repo\dist" $name
    Write-Output "=== $name"

    # Rescue PublishedFileId before wiping dist/. The uploader writes it into whichever
    # project.xml it was given - which is dist/'s - and that id IS the Workshop item. Losing
    # it means the next upload publishes a NEW item and orphans every subscriber, so if src/
    # does not have it yet, put it there now rather than trusting anyone to remember.
    $srcProj = "$repo\src\$($v.project)"
    if (Test-Path "$dist\project.xml") {
        $old = Get-Content "$dist\project.xml" -Raw
        if ($old -match '<PublishedFileId>\s*(\d+)\s*</PublishedFileId>') {
            $id = $Matches[1]
            $cur = Get-Content $srcProj -Raw
            if ($cur -notmatch '<PublishedFileId>') {
                $cur = $cur -replace '(?m)^(\s*)</project>', "`$1`t<PublishedFileId>$id</PublishedFileId>`r`n`$1</project>"
                Set-Content -Path $srcProj -Value $cur -NoNewline
                Write-Output "    ! rescued PublishedFileId $id from dist/ into src/$($v.project) - commit this"
            } elseif ($cur -notmatch [regex]::Escape($id)) {
                throw "PublishedFileId mismatch: dist/ has $id but src/$($v.project) has a different one. Resolve by hand."
            }
        }
    }

    Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path "$dist\localization" | Out-Null

    # 1. Assemble the string table (english, plus 11 generated languages for the intl build).
    $work = Join-Path $env:TEMP "eteh_build_$name"
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    $xml = Join-Path $work "$name.string_table.xml"
    $genArgs = @("$repo\tools\gen_localization.py", "--out", $xml)
    if ($v.intl) { $genArgs += "--intl" }
    & python @genArgs
    if ($LASTEXITCODE -ne 0) { throw "gen_localization.py failed" }

    # 2. Compile it. The .loc2 filename prefix MUST match the mod folder name, and both must
    #    be underscore-only: the game's discovery regex is
    #    .*localization/[A-Za-z0-9._]+_<language>.loc2, which has no hyphen in its charset.
    #    A mismatch loads no strings while the mod still appears and enables in the menu.
    foreach ($f in (Build-Loc2 $xml "$work\loc")) {
        Copy-Item $f.FullName (Join-Path "$dist\localization" "${name}_$($f.Name)") -Force
    }

    # 3. project.xml. ModDataPath is an absolute path to wherever this checkout happens to
    #    live, so it is INJECTED here and deliberately kept out of src/ - committing it
    #    would publish a local path that is wrong for everyone who clones the repo.
    #    Everything else - crucially PublishedFileId, which the uploader writes back and
    #    which identifies the Workshop item - is preserved verbatim from src/.
    $proj = Get-Content $srcProj -Raw
    $proj = $proj -replace '[ \t]*<ModDataPath>.*?</ModDataPath>\r?\n', ''
    if ($ForUpload) {
        $path = "<ModDataPath>" + ($dist -replace '\\','/') + "/</ModDataPath>"
        $proj = $proj -replace '(?m)^(\s*)<Title>', "`$1$path`r`n`$1<Title>"
        if ($proj -notmatch '<ModDataPath>') { throw "could not inject ModDataPath into $($v.project) - no <Title> element found" }
    }
    Set-Content -Path "$dist\project.xml" -Value $proj -NoNewline

    Copy-Item "$repo\src\$($v.icon)" "$dist\preview_icon.png" -Force

    # 4. International only: lift the town event line so longer translations fit.
    if ($v.intl) {
        $rel = "campaign\town\quest_select\quest_select.layout.darkest"
        New-Item -ItemType Directory -Force -Path (Split-Path "$dist\$rel") | Out-Null
        $layout = Get-Content "$game\$rel" -Raw
        foreach ($pair in @(@('.town_notification_icon 60 750',        ".town_notification_icon 60 $(750-$LIFT_PX)"),
                            @('.town_notification_title_text 110 750', ".town_notification_title_text 110 $(750-$LIFT_PX)"),
                            @('.town_notification_text 110 774',       ".town_notification_text 110 $(774-$LIFT_PX)"))) {
            $n = ([regex]::Matches($layout, [regex]::Escape($pair[0]))).Count
            if ($n -ne 1) { throw "layout anchor '$($pair[0])' matched $n times - the game file changed, re-check the offsets" }
            $layout = $layout.Replace($pair[0], $pair[1])
        }
        Set-Content -Path "$dist\$rel" -Value $layout -NoNewline
    }

    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
    $files = Get-ChildItem -Recurse -File $dist
    "    {0} files, {1:N0} KB -> dist/{2}" -f $files.Count, (($files | Measure-Object Length -Sum).Sum/1KB), $name
}
