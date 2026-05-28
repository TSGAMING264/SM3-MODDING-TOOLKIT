from __future__ import annotations

from tkinter import scrolledtext, ttk

from sm3_toolkit.i18n import how_to_text, tr
from sm3_toolkit.theme import COLORS


HOW_TO_TEXT = """SM3 MODDING TOOLKIT - HOW TO USE
Created by TSGAMING264

This page explains every visible release tab and every main option in the toolkit.
Visible tabs: Home, Pack Extractor, Hex Viewer, Tex Swapper, Texture Folder Viewer, Old Animation Swapper, How To Use, About / Info.
The tool is still beta. Test on copies, back up your original files, and never assume a patch is safe until you test it in-game.

================================================================================
GENERAL SAFETY RULES
================================================================================
- Original game packs should never be edited directly.
- Pack Extractor is extraction/viewing only.
- Tex Swapper should patch a new copy, not the original PCPACK.
- Old Animation Swapper should patch a new copy, not the original PCPACK.
- Back up CH_SPIDERMAN.PCPACK, CH_BLACKSUIT.PCPACK, CH_PETER.PCPACK, CH_PLAYERGOBLIN.PCPACK, MEGACITY.PCPACK, GAME.PCPACK, or any pack before testing.
- If a tool says unsupported, blocked, wrong size, or wrong format, do not force it.

================================================================================
HOME TAB
================================================================================
Home is the start page. It explains what the toolkit is and lists the visible tabs.
It does not patch or extract anything.

Options/content:
- Tool title: shows SM3 MODDING TOOLKIT.
- Created by TSGAMING264: release branding.
- Workflow summary: quick overview of each tab.
- Safety notes: reminder that this is beta and original files should be backed up.

================================================================================
PACK EXTRACTOR TAB
================================================================================
Purpose:
Use this to view/extract Spider-Man 3 PC packs. This is the general pack-viewing tool.
Use Pack Extractor when you want to inspect a PCPACK/PCAPK/APKF route or extract contents.

Important release behavior:
- The visible release extractor should not leave report folders or report zip bundles.
- It uses internal temporary index/browse metadata only so List Contents and Open Pack Folder can work.
- It does not modify original PCPACK files.

Options and buttons:

INPUT PACK / PCPACK
- Choose the pack you want to inspect or extract.
- Common inputs: .PCPACK, .PCAPK, .APKF.

Browse
- Opens a file dialog to choose the input pack.

OUTPUT FOLDER
- Choose where extracted files will be written.
- Use a clean folder for each test.

Browse
- Opens a folder dialog to choose output location.

Force
- If enabled, old extracted output for the same pack can be replaced/backed up.
- Use this when re-running a test to the same output folder.

Quiet
- Reduces live log/status noise while running.
- Useful for large packs.

Index
- Builds a browse/list index so contents can be shown before or after extract.
- Leave enabled for normal release use.

APK
- Includes nested APKF/inner resources in the list/extract workflow when supported.
- Leave enabled for most SM3 packs.

Search
- Filters the visible resource list.
- Use names, extensions, hashes, or resource words.

Clear
- Clears the search filter.

List Contents
- Scans the selected pack and lists resources without doing a full user-facing extraction.
- Good first step before extracting.

EXTRACT PACK
- Extracts the selected pack to the output folder.
- This is the main release extraction button.
- It should not generate public report folders/zips in release mode.

Open Output
- Opens the chosen output folder.

Open Pack Folder
- Opens the extracted pack folder for the selected pack.

================================================================================
HEX VIEWER TAB
================================================================================
Purpose:
Read-only binary/hex viewing for packs and other files. This is for inspection only.
It does not edit or save original files.

Supported files:
- .PCPACK
- .PCAPK
- .APKF
- .TOC
- .DLL
- .EXE
- .HTML
- .TXT
- .BIN
- .DAT
- Any file type if selected manually.

Options and buttons:

Open File
- Choose any file to inspect in hex view.

Reveal Folder
- Opens the folder containing the current file.

Go to offset
- Type an offset and jump to it.
- Supports normal numbers and hex-style offsets if the tool accepts them.

Go
- Jumps to the requested offset.

Previous
- Moves to the previous page of bytes.

Next
- Moves to the next page of bytes.

Page
- Controls how many bytes are shown per page.
- Smaller pages are easier to read; larger pages show more data.

Reload
- Reloads the current file from disk.

Find Hex
- Search for raw hex byte values.
- Example search values: 54 45 58, 41 50 4B 46, 68 73 61 6D.

Find Text
- Search for normal text strings inside the file.

Find TEX
- Quick search for the TEX string/signature.
- Useful when looking for texture markers or texture-related data.

Export Page HTML
- Exports the currently visible hex page to an HTML file.
- This is an export of the view, not an edit to the original file.

Export Page TXT
- Exports the currently visible hex page to a text file.

Open HTML Preview
- Opens the exported/current HTML preview if available.

Clear
- Clears search/status/output selections depending on the viewer state.

Hex pane
- Shows raw bytes in hexadecimal.

ASCII pane
- Shows readable text characters beside the hex bytes.

Byte inspector
- Shows details for selected byte/offset, such as offset, u8, u16LE, u32LE, and character preview when available.

================================================================================
TEX SWAPPER TAB - EXPERIMENTAL TEXTURE TOOL
================================================================================
Purpose:
Tex Swapper is for supported texture/TEX resources and safe DDS replacement workflows.
It is NOT a full general pack browser. Use Pack Extractor for general pack viewing.

Important experimental note:
Tex Swapper may not view every pack in the game because not every pack is a texture-capable pack. Some packs contain only animations, meshes, materials, mission data, compact wrappers, voice/audio, or unsupported/nonstandard resources.

Correct expectation:
- Pack Extractor = view/extract almost every SM3 pack route.
- Tex Swapper = scan/export/replace supported TEX/DDS targets that are safe enough to patch.

Safety rules:
- Patch COPY only; never patch the original pack directly.
- Original-format DDS workflow is recommended.
- Strict DDS validation must remain enabled for real replacement work:
  width must match
  height must match
  format must match
  mip count must match
  payload size must match
- If validation fails, do not force the patch.

Top controls:

Clean SM3 PCPACK / Browse PCPACK
- Select the clean/source PCPACK to scan for textures.
- Use a clean original or a known-good copy.

Build Preview
- Scans the selected PCPACK and builds the texture target list/previews.

Output folder / Choose Output
- Select where exported DDS files, patched copies, and logs will be written.

Open Output
- Opens the output folder.

Replacement DDS folder / Select Repl Folder
- Select a folder containing edited DDS files or replacement texture files.

Open Repl
- Opens the replacement folder.

Search textures
- Filter visible texture targets by name/hash/type.

Clear Search
- Clears the texture search filter.

Force opaque RGB
- If present, forces/assumes opaque RGB for certain preview/conversion paths.
- Use carefully; alpha-sensitive textures can look wrong if forced opaque.

Warn non-diffuse
- If enabled, warns when a texture target may not be a diffuse/albedo texture.

Strict diffuse only
- If enabled, limits certain workflows to diffuse-style targets.
- This prevents accidentally patching normals/spec/reflection/utility textures.

Open Index
- Opens the generated texture index/output list if available.

Reload
- Reloads the current pack/index state.

Dark/Light
- Toggles UI theme if supported by the tab.

TEX Targets list
- Shows texture targets found in the PCPACK.
- Ctrl-click / Shift-click can select multiple rows for batch tools when supported.

Preview Image
- Shows preview of the selected texture when decoding/preview is available.

Actions - clean creator workflow:

EXPORT ALL DDS
- Exports all supported texture targets to DDS.

ONE FILE AUTO: File First -> Patch
- Auto-matches one replacement file to a likely target and patches a copy when safe.
- Use only with strong matching and always test in-game.

SELECTED CONVERT: Image/DDS -> Target Format
- Converts selected source image/DDS into the selected target's required format/size/mips when supported.
- Target decides final format; source supplies pixels.

AUTO Detect Edited DDS + Patch
- Looks for edited DDS files and patches matching safe targets.

Set Replacement Folder
- Sets/changes the replacement folder used by auto and batch workflows.

TEST Safe Edited DDS + Patch
- Creates/tests a safe edited-DDS patch route for the selected texture.

RESTORE: All TEX from Clean Original Pack
- Restores all texture payloads from a clean original pack into a copy.
- Useful as a control test if colors/textures become wrong.

BUGCHECK: Scan Current Targets
- Checks current detected targets for issues, ambiguity, or unsafe conditions.

CONTROL: Original Selected Texture
- Patches a copy using the original selected texture data as a control.
- If this works, patch offsets are likely correct.

Dump Component0/1
- Dumps raw TEX component data for selected target.
- Component0 is usually descriptor/metadata; Component1 is usually payload/image data.

BATCH Export DDS for Selected
- Exports DDS files for selected rows only.

Patch COPY with Replacement
- Patches a new PCPACK copy with the selected replacement.
- Should not modify original pack.

CONTROL: Full Original-Texture Self Test
- Writes every original texture back into a copy to prove patching does not alter content unexpectedly.

MANUAL OPTIONS CHECK
- Shows/checks manual workflow options and safety state.

Main / Recovery / Advanced
- Main: common export/patch workflows.
- Recovery: restore/control/self-test workflows.
- Advanced: dumps, bugcheck, and deeper diagnostic tools.

Preview Files panel
- Shows exported/preview files for selected target/workflow.

Texture/preview display
- Shows the selected texture image if supported.

Status/log panel
- Shows progress, validation messages, and warnings.

Selected target details
- Shows hash/name/format/size/mip/target details for the selected texture.

================================================================================
TEXTURE FOLDER VIEWER TAB
================================================================================
Purpose:
Browse and preview folders of texture/image files. This is the image/texture viewing tool.
It does not patch packs by itself.

Options and buttons:

Choose Folder
- Select a folder of DDS/PNG/JPG/TGA/HDR or other supported images.

Rescan
- Reloads the selected folder.

Stop
- Stops active preload/scan tasks.

Recursive
- Includes subfolders when scanning.

Auto Preview
- Automatically previews the selected file.

Preload ALL Textures
- Loads/previews all textures ahead of time.
- Faster browsing after preload, but can use more memory/time.

Use Disk Cache
- Stores preview/cache data on disk to speed repeated browsing.

Show Unsupported
- Shows files that the viewer may not be able to preview.

Search
- Filters files by name/path.

Clear
- Clears search text.

Reset Filters
- Clears search/size/filter options.

Size Search
- Filters by size/resolution text if supported.

Clear Size
- Clears size filter.

Square
- Filters for square textures.

Power2
- Filters for power-of-two textures.

Common Suit Sizes
- Filters to sizes commonly used by suit textures.

Preview Selected
- Previews the selected file.

Large Preview
- Opens a larger preview view.

Open Externally
- Opens the selected file in the system/default viewer.

Reveal in Explorer
- Opens the selected file location.

Export Contact Sheet
- Exports a contact sheet of visible/selected previews.

Clear Cache
- Clears cached previews.

Texture Name list
- Shows files in the folder.

Preview panel
- Shows the selected texture preview.

Fit
- Fits preview to panel.

100%
- Shows preview at 100% scale.

- / +
- Zoom out / zoom in.

Reset
- Resets preview zoom/pan.

Texture Info
- Shows metadata for selected texture, such as size/format/path if available.

================================================================================
OLD ANIMATION SWAPPER TAB - EXPERIMENTAL ANIMATION TOOL
================================================================================
Purpose:
Old Animation Swapper is for controlled animation-payload swaps into existing PC animation slots.
It is experimental and intentionally restrictive to prevent crashes.

Very important rule:
You cannot patch anything you want. A safe animation swap requires a compatible existing PC destination slot.

Animation safety rules:
- Destination must be an existing PC animation/resource slot.
- Source payload must match the destination slot size.
- Component layout/part sizes must match.
- PC slot identity/name/hash stays the same.
- The source payload is transferred into the existing PC slot.
- The tool patches a new PC copy, not the original.
- Same-name/no-change swaps should be blocked.

Xbox animation rule:
You cannot inject Xbox animations that are not present in the PC resource space as a compatible slot.
If the PC pack has no matching destination slot, the Xbox animation should not be patched.

Why this rule exists:
- Same-size/component checks reduce crashes.
- Existing PC slot requirement makes transfers more successful.
- Arbitrary add-entry animation injection is not the release workflow.

Options and buttons:

Dark Mode
- Toggles the animation swapper theme if supported.

Pack A / PC destination pack
- The PC pack that will receive the patched animation payload.
- This should be a clean or intentionally patched PC pack copy.

Browse PC Pack A
- Select the PC destination pack.

Clear Pack A
- Clears Pack A selection.

Pack B / source pack
- Optional manual source pack.
- Can be a source PC pack or supported source payload pack depending on workflow.

Browse Pack B
- Select manual source pack.

Clear Pack B
- Clears Pack B selection.

Xbox Pack Folder
- Folder containing supported zipped Xbox/source chain packs.
- Leave source packs zipped if that is the expected workflow.

Select Xbox Pack Folder
- Selects the Xbox/source folder.

Clear Xbox Pack Folder
- Clears Xbox/source folder selection.

Use Selected Xbox Source as Pack B
- Uses selected source from Xbox/source folder as Pack B.

Clear All Pack Inputs
- Clears Pack A, Pack B, and source folder selections.

LOAD / VERIFY PACKS
- Loads the selected packs and verifies usable animation candidates.

Strict same component sizes
- Requires source and destination component sizes/layout to match.
- Keep enabled for safer release use.

Preview Selected Pair
- Shows details for the currently selected destination/source pair.

PATCH SELECTED PAIR -> NEW PC COPY
- Patches only the selected compatible pair into a new PC copy.
- Does not patch original Pack A directly.

MULTI SELECTION CENTER
- Opens/uses the multi-selection workflow for multiple verified safe pairs.

ABOUT / INFO
- Shows animation swapper-specific release info.

Search / Clear Search
- Searches animation lists/rows.

Filter / Apply Filter / Clear Filter
- Filters the animation list based on current criteria.

Release Preset Center
- Preset-based workflow for known release-safe or test-safe swap groups.

Release presets
- List of included clean release presets.

Selection box - Pack A destination <- Pack B source payload
- Shows selected swap pairs before applying/patching.

Load Preset
- Loads selected preset into the selection box.

Add Preset
- Adds preset rows to current selection.

Load Red 5-Pack
- Loads known red-suit stable 5-pack preset when available.

Add Current Selection
- Adds current pair to the multi-selection box.

Remove Selected Pair
- Removes selected pair from selection box.

Clear
- Clears current selection box/list depending on panel.

Apply To Main Lists
- Applies selected/preset rows back to main lists.

Apply + Patch Now
- Applies selected rows and immediately patches a new output copy.

v2.2 discovery controls
- Legacy/discovery controls kept for controlled candidate review where present.

Target view
- Changes destination/candidate view mode.

Candidate mode
- Changes how compatible candidates are shown.

Source search
- Searches source candidates.

Same-size/same-layout source candidates for selected PC slot
- Shows candidates that match the selected PC destination slot size/layout.

================================================================================
ABOUT / INFO TAB
================================================================================
Purpose:
Shows release information, credits, links, beta notice, and disclaimer.

Content includes:
- SM3 Modding Toolkit title.
- Created by TSGAMING264.
- Beta/unfinished notice.
- Special thanks/credits.
- TSGAMING264 community links.
- Fan-made/unofficial disclaimer.
- Reminder that no game files are included.
- Reminder to back up original files.

================================================================================
FAST TROUBLESHOOTING
================================================================================
Pack Extractor does not list contents:
- Check that the selected file is a valid SM3 pack.
- Try a different output folder.
- Make sure the file is not locked by another program.

Tex Swapper shows no textures:
- The pack may not contain supported TEX resources.
- Use Pack Extractor for general pack viewing.
- Try a known texture-heavy pack first, such as CH_SPIDERMAN, CH_BLACKSUIT, GAME, or MEGACITY.

Tex Swapper blocks a patch:
- DDS size/format/mips/payload probably do not match.
- Export original DDS, edit while preserving original format/mips, then patch a copy.

Animation Swapper blocks a swap:
- Source and destination size/layout probably do not match.
- Destination PC slot may not exist.
- Xbox-only animations cannot be injected unless a compatible PC slot exists.

Hex Viewer search does not find TEX:
- The current file/page may not contain that string.
- Use Find Text for strings and Find Hex for raw bytes.
- Try searching the full file/page navigation around known offsets.
"""


class HowToUseTab(ttk.Frame):
    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=16)
        self.app_state = app_state
        self._build()

    def _build(self) -> None:
        self.title_label = ttk.Label(self, text="HOW TO USE", style="SectionTitle.TLabel")
        self.title_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(
            self,
            text="",
            style="Muted.TLabel",
            wraplength=1200,
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 10))

        self.box = scrolledtext.ScrolledText(
            self,
            wrap="word",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.box.pack(fill="both", expand=True)
        if self.app_state:
            self.app_state.on_language_change(self._apply_language)
        else:
            self._apply_language("English")

    def _apply_language(self, language: str) -> None:
        self.subtitle_label.configure(text=tr(language, "how_intro"))
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", how_to_text(language, HOW_TO_TEXT))
        self.box.configure(state="disabled")
