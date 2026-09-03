# SM3 Modding Toolkit v5.2.182

Created by TSGAMING264

## Toolkit

- Updated the public source to the verified v5.2.182 integrated Toolkit.
- Preserved Home as the first selected tab.
- Includes Pack Extractor, Hex/Text, Tex Swapper, Texture Folder Viewer, MAT Editor, Model Viewer, New Animation Swapper, Old Animation Swapper, Sound Editor, PCPACK Rebuild Lab, How To Use, and About / Info.
- Includes the current theme and multilingual interface system.
- Keeps normal workflows focused on output copies and extracted folders.
- Keeps Send-To-GPT bundles and internal report packages out of normal release workflows.

## Audio Separator

- Added the full source for the separate SM3 Audio Separator v1.0.3 companion application.
- Added local cache detection for `htdemucs`, `htdemucs_ft`, and `mdx_extra_q`.
- Added a visible first-use model download notice and clearer retry messaging.
- Model downloads run through the worker flow so the interface remains responsive.
- Demucs model weights remain excluded from the repository and release ZIP.

## Packaging

- Documents the intentional two-EXE release layout with separate Toolkit and Audio runtimes.
- Documents use of the complete official Microsoft-signed offline x64 Visual C++ Redistributable.
- Keeps compiled EXEs, game files, extracted assets, model weights, caches, and generated outputs out of Git.
