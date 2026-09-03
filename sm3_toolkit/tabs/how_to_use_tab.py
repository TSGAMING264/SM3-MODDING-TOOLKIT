from __future__ import annotations

from tkinter import scrolledtext, ttk

from sm3_toolkit.i18n import how_to_text, tr
from sm3_toolkit.theme import COLORS


HOW_TO_TEXT = """SM3 MODDING TOOLKIT - HOW TO USE

START HERE
- Keep backups of original game files.
- Work from clean source packs whenever possible.
- The toolkit normally writes extracted folders or NEW output files instead of replacing your source automatically.
- If a validator blocks a file, do not force it. Re-check the target, format, size, or workflow.

BUILT-IN HELP
All user instructions and demonstrations are built directly into this tab.
You do not need a separate README, How-To text file, or EXAMPLES folder.

================================================================================
QUICK START EXAMPLE - REPLACE ONE SPIDER-MAN TEXTURE SAFELY
================================================================================
Example request: "I want to replace one Spider-Man texture without risking my clean game pack."

1. MAKE A BACKUP
   Copy the clean PCPACK somewhere safe before editing anything.
2. FIND / EXTRACT THE RESOURCE IF NEEDED
   Open Pack Extractor, select the clean pack, LIST CONTENTS, then CLASSIC EXTRACT.
3. OPEN TEX SWAPPER
   Select the clean PCPACK, Build Preview, choose the texture, and export the edit-ready DDS.
4. EDIT THE DDS
   Make your visual change while keeping the required dimensions, format, and layout.
5. RETURN TO TEX SWAPPER
   Use SINGLE FILE EDITOR-SAFE PATCH for one edited DDS and write a NEW PCPACK.
6. TEST THE NEW COPY
   Keep the clean original untouched and test only the newly created output.

That clean-input -> new-output -> test flow is the basic safety rule for the whole toolkit.

================================================================================
WHICH TAB DO I USE?
================================================================================
I want to extract a pack                 -> Pack Extractor
I want to replace/edit textures          -> Tex Swapper
I only want to browse texture folders    -> Texture Folder Viewer
I want to edit an extracted .mat         -> MAT Editor
I want to view an extracted .mesh        -> Model Viewer
I want a normal XESM3 animation swap     -> New Animation Swapper
I want the older PC/Xbox pack workflow   -> Old Animation Swapper
I want to replace game audio             -> Sound Editor
I want to rebuild/verify a PCPACK        -> PCPACK Rebuild Lab
I want to inspect bytes/text             -> Hex/Text

================================================================================
PACK EXTRACTOR
================================================================================
Example: "I want to extract CH_SPIDERMAN.PCPACK so I can look through its files."

1. Open Pack Extractor.
2. Choose one supported pack.
3. Choose an output folder.
4. Use LIST CONTENTS if you want to inspect before extracting.
5. Choose CLASSIC EXTRACT for normal editing/browsing folders.
6. Choose MOD LOADER READY when you specifically want the XESM3-ready loose-resource structure.
7. Open the output folder and continue with the tool that matches the resource you want to edit.

Xbox packs use the Xbox extraction route when applicable. Extraction is for getting source resources out; it does not patch an Xbox pack.


================================================================================
TEX SWAPPER
================================================================================
Example: "I exported one Spider-Man DDS, edited it, and now I want a new PCPACK with that texture."

1. Open Tex Swapper -> Classic Workflow.
2. Select the clean PCPACK and Build Preview.
3. Select the texture.
4. Export the selected DDS.
5. Edit the DDS in your image editor.
6. Return to Tex Swapper.
7. Use SINGLE FILE EDITOR-SAFE PATCH for one edited texture.
8. Use MULTIPLE FILE EDITOR-SAFE PATCH for several selected edited files.
9. Use FOLDER FINAL EDITOR-SAFE REIMPORT when you want the toolkit to scan the whole edited DDS folder.
10. Write the NEW PCPACK to your output folder and keep the clean source pack backed up.

For loose native TEX work, use the .TEX page or the quick .TEX actions after selecting a real target texture.


================================================================================
TEXTURE FOLDER VIEWER
================================================================================
Example: "I already have a folder of exported textures and just want to find the one I need."

1. Open Texture Folder Viewer.
2. Choose the texture/image folder.
3. Search by name or browse the list.
4. Click an item to preview it and review its information/category.

This tab is a viewer. Use Tex Swapper when you are ready to build a texture replacement.

================================================================================
MAT EDITOR
================================================================================
Example: "I want to test one material value without changing the MAT layout."

1. Extract the .mat first.
2. Open MAT Editor and click OPEN MAT.
3. Select an editable shader_float row.
4. Change one value at a time.
5. Click APPLY CHANGES.
6. Use RESET PARAMETER / RESET ALL if needed.
7. Use SAVE MODIFIED MAT when you want a separate edited copy.

Raw/reference fields are inspection-only. The editor keeps the MAT file size/layout intact.


================================================================================
MODEL VIEWER
================================================================================
Example: "I extracted ch_spiderman000.mesh and want to see which sections are in it."

1. Open Model Viewer.
2. Click OPEN SM3 MESH.
3. Choose the extracted SM3 .mesh.
4. Left-drag to rotate.
5. Mouse wheel zooms.
6. Use Front / Back / Left / Right / Fit for quick views.
7. Toggle sections to isolate parts of the model.
8. Use Solid / Wireframe / Grid as needed.

Model Viewer is view-only and does not modify/export the mesh.


================================================================================
NEW ANIMATION SWAPPER
================================================================================
Example: "I want sm3idle_tapback to play the motion from rvbatckmultianglefury2."

Normal XESM3 route:
1. Open New Animation Swapper.
2. Browse + Scan ANIMs for your extracted animation folder.
3. Choose the animation identity you want to swap OUT.
4. Choose the donor animation you want to swap IN.
5. Choose an output folder.
6. Build the XESM3 animation mod/output.
7. Install/test that output through XESM3.

Motion Editor is for changing motion data inside an ANIM rather than simply replacing one animation with another.

OPTIONAL CSV BATCH FORMAT
If you use the optional CSV route, the columns are:
enabled,mode,destination,replacement,note

Example disabled row:
0,slot_preserve,sm3idle_tapback.anim,rvbatckmultianglefury2.anim,DEMO ONLY

Replace the example names with your own extracted target/donor and enable the row only when you are ready.

================================================================================
OLD ANIMATION SWAPPER
================================================================================
Example: "I have a PC character pack and an Xbox pack and want to try one selected animation pair."

1. Browse Pack A.
2. Browse Pack B.
3. Click LOAD / VERIFY PACKS.
4. The tool detects PC/Xbox automatically. Either platform can be loaded into A or B.
5. Select the target and replacement animation pair.
6. Preview/check the selected pair.
7. Use PATCH SELECTED PAIR -> NEW PC PACK when one loaded pack is the PC destination.
8. Or use PATCH SELECTED PAIR -> NEW ANIM COPY for a standalone animation copy.

There is no separate Xbox Source Folder anymore. If one side is PC and the other is Xbox, the PC side is automatically used as the PC output destination.


================================================================================
SOUND EDITOR
================================================================================
Example: "I found the sound I want and need to replace it without touching the clean bank."

Direct replacement:
1. Choose a clean .pcssb and LOAD BANK.
2. Select the sound slot.
3. EXTRACT SELECTED or PREVIEW SELECTED if you want to identify it first.
4. Choose replacement audio.
5. VALIDATE REPLACEMENT.
6. Choose an output folder.
7. Build the NEW PCSSB.
8. Back up the game's original bank before installing/testing.

Music Replacement:
1. Select the cinematic slot.
2. Use a dialogue stem from SM3 Audio Separator if you want to keep voices while replacing music.
3. Choose the dialogue stem and new music.
4. Set voice/music volume.
5. Preview the mix.
6. Build the mix or build the mix + new PCSSB.


================================================================================
PCPACK REBUILD LAB
================================================================================
Example: "I extracted a clean pack and want to prove I can rebuild/verify it before doing anything complicated."

1. Select the clean original PCPACK.
2. Select the clean extracted folder from that same pack.
3. Select an output folder.
4. Run CHECK / AUTO-FIND.
5. Run NO-CHANGE CONTROL if you want a baseline rebuild test.
6. Run REBUILD EXTRACTED PACK when ready.
7. Use VERIFY PCPACK on the output.

The rebuild lab writes a new PCPACK; it does not replace the clean source automatically.


================================================================================
HEX / TEXT
================================================================================
Example: "I want to inspect a file but I do not want the original touched."

1. Open Hex/Text.
2. Open the file.
3. Leave View Only enabled for inspection.
4. Search/navigate as needed.
5. If you intentionally edit the viewer copy, export it as a NEW file.
6. Use Text Mode for readable text/code/config/document-style files when supported.


================================================================================
APPEARANCE + LANGUAGE
================================================================================
FULL THEME unchecked:
- Theme uses the original toolkit theme flow.

FULL THEME checked:
- Changing Theme applies the selected palette through the whole toolkit UI.

Language:
- Language changes apply live.
- English is the startup language on every launch. Other languages activate only when you select them.
- Technical file-format names such as PCPACK, TEX, DDS, MAT, ANIM, and XESM3 stay recognizable.

================================================================================
QUICK TROUBLESHOOTING
================================================================================
Pack will not load/extract:
- Re-check that you selected a supported clean pack and a writable output folder.

Texture replacement is blocked:
- Make sure you selected the correct target and that the edited DDS still matches the required target layout.

Animation output is blocked:
- Re-check the target/donor selection and use the preview/validation shown by that animation tool.

Sound replacement is blocked:
- Re-check the selected slot and replacement audio. Use VALIDATE REPLACEMENT before building.

Something looks wrong after a mod is installed:
- Restore your clean backup, then test one change at a time.

================================================================================
ABOUT / INFO
================================================================================
About / Info contains the creator/community credits, release-level safety/disclaimer information, and language information.
"""


class HowToUseTab(ttk.Frame):
    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=16)
        self.app_state = app_state
        self._build()

    def _build(self) -> None:
        self.title_label = ttk.Label(self, text="HOW TO USE", style="SectionTitle.TLabel")
        self.title_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(self, text="", style="Muted.TLabel", wraplength=1200)
        self.subtitle_label.pack(anchor="w", pady=(4, 8))

        self.box = scrolledtext.ScrolledText(
            self, wrap="word", bg=COLORS["field"], fg=COLORS["fg"],
            insertbackground=COLORS["fg"], selectbackground=COLORS["select"],
            relief="flat", font=("Segoe UI", 10),
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
