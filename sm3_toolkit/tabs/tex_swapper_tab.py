#!/usr/bin/env python3
"""
THE TEX SWAPPER - Made by TSGAMING264
=====================================

This is the v1.6 PCPACK browser upgraded so the user can select
an original Spider-Man 3 PC .PCPACK directly.

What it does:
  - Scans SM3 PC hsam/APKF PCPACKs directly.
  - Extracts TEX component0/component1 to a temporary chain folder.
  - Builds the same v1.4 DDS/PNG previews.
  - Shows a scrollable browser/list of textures.
  - Lets the user dump selected component0/component1.
  - Lets the user insert a replacement into a NEW PCPACK COPY only.
  - Main v2.0 workflow is ORIGINAL DDS FORMAT: export the game's original DDS, edit that DDS externally, then patch back only if width/height/mips/format/payload match the selected TEX exactly.
  - Keeps image conversion as experimental, but v2.0 warns that PNG/JPG conversion is NOT the clean/original final format route.
  - Adds original-texture self-replace tests so you can patch a copy with the exact extracted bytes.
  - Adds strict DDS validation to prove the replacement DDS matches the target texture descriptor before writing a new PCPACK copy.
  - v2.3 adds dark mode and makes the original DDS workflow the final/base route.
  - v2.4 adds auto-detect edited DDS import: after exporting a DDS, edit/overwrite it in Paint.NET, then use AUTO: Detect Edited DDS + Patch COPY to find it automatically.
  - v2.5 adds multi-select/batch DDS workflow: export multiple selected DDS files, auto-detect multiple edited DDS files, and patch them into ONE new PCPACK copy.
  - v2.5 adds visible scrollbars and mouse-wheel scrolling for the texture list, info panel, and preview-file list.
  - v2.7 adds a dedicated Replacement DDS Folder selector so AUTO/BATCH AUTO can scan the exact folder where edited DDS replacements are saved.
  - v2.9 adds Previous Folder Auto Replace: after Build Preview, select a previous edited-DDS folder and auto-patch every valid matching texture into one new PCPACK copy.
  - v3.0 adds Manual Old Folder Texture Picker: load every DDS from an old/replacement folder, manually choose which DDS maps to which current TEX target, then export one patched PCPACK copy.
  - v3.1 adds one-file manual replacement and one-file auto-select patching.
  - v3.2 adds multi-file manual replacement: select multiple DDS files at once, auto-map them to current/selected TEX targets, review, and patch them into one PCPACK copy.
  - v3.4 adds an explicit OLD legacy one-file auto option that uses the original v3.1 one-DDS auto-select workflow.
  - v3.6 fixes false 'No texture selected' errors.
  - v3.7 cleans up the UI by removing the extra SAME FILE(S) select button and making the old selected one-file direct export the primary one-file workflow.
  - v3.8 fixes the selected one-file workflow by offering Target-Format Convert when the chosen DDS/image does not match the selected slot.
  - v3.9 restores file-first legacy one-file auto so selecting a texture first is not required.
  - v4.0 Stable Final separates exact DDS patching, selected-target conversion, and file-first auto replacement so each workflow behaves consistently.
  - v4.7 Manual Options Audit adds clearer selection display, Clear Search, stronger selection resolving, improved exact/convert fallback, and a sanity check report.
  - v4.8 Preview Output Safety Fix stops PREVIEW_OUTPUT nesting, avoids deleting user-selected folders, improves manual DDS preview fallback, and normalizes hash logging.
  - v4.9 Multi-Select Single-Patch Parity Fix makes selected multi-file patching use the same exact-or-convert path as the working single selected patch route.
  - v5.0 Reimport-All Single-Patch Parity Fix makes folder reimport trust exact hash/asset filenames and use exact-or-convert instead of skipping name-locked files as ambiguous.
  - THE TEX SWAPPER build adds visible TSGAMING264 branding and a refreshed header/status interface.
  - This base tool does NOT include red-suit-to-black-suit swap/comparison logic; that remains separate.

WOS toolkit dev clue added in v5.2.14:
  - Texture repacking/patching must preserve the game-expected format and structure.
  - If a texture preview becomes black/white, gray-only, or channel-wrong, treat it as a format interpretation problem, not a safe patch result.
  - Some numeric formats may need DXT candidate review before trusting the preview.

Insert safety rules:
  - Exact same-size replacement only.
  - Original PCPACK is never modified.

  - v5.2.33 adds EDIT-READY DDS export/reimport: the DDS header must match the target/export header, not just width/height/format/payload.
  - v5.2.34 adds Paint.NET/GIMP overwrite recovery: if an edited DDS still has the right target name, dimensions, mips, format, and payload size but its DDS header changed, the tool can rebuild a GAME-FORMAT DDS by writing the original SM3 target header plus the edited payload.
  - v5.2.36 fixes FINAL SAFE REIMPORT folder handling: GAME_FORMAT_NORMALIZED_DDS/AUTO_NORMALIZED_DDS folders can be selected directly, while nested reports/work folders are still skipped.
  - v5.2.37 makes FINAL SAFE REIMPORT auto-write the patched .PCPACK into FINAL_PATCHED_PCPACK_OUTPUT so the final pack is obvious and the route cannot end at only DDS files.
  - v5.2.38 adds Editor-safe source-pixel rebuild: if Paint.NET/GIMP overwrites a suit DDS into the wrong header/format/mips/payload, FINAL EDITOR-SAFE REIMPORT can decode its visible pixels and rebuild a game-format DDS using the selected SM3 target shell before writing the patched PCPACK.
  - v5.2.38 also cleans the main action panel by hiding old duplicate routes that were replaced by the new export/final-write workflow.
  - v5.2.39 removes remaining old/research buttons from the visible Tex Swapper UI and adds a single-file editor-safe patch button that writes one patched PCPACK from one edited DDS/image.
  - v5.2.40 renames the final routes to Paint.NET/GIMP editor-safe wording and verifies Paint.NET-style DDS outputs: header rewrite, wrong format/no-mip BGRA32, and normal image source rebuilds.
  - v5.2.107 adds a visible SINGLE SELECTED DDS EXPORT button to the Classic workflow.
  - v5.2.107 adds a dedicated .Tex workflow tab for RaimiHook Stage 2B loose native .tex files.
  - v5.2.108 fixes the .Tex workflow by reusing the selected texture's REAL extractor component0 shell from the PCPACK, patching only width/height/depth/mips/format, then appending the DDS PHYS payload.
  - v5.2.108 also adds EXPORT SELECTED ORIGINAL .TEX so the tool can prove the exact extractor layout before making edited loose files.
  - v5.2.111 adds a native .TEX folder browser: choose any folder of loose SM3 .tex files, click a texture, and preview the image directly in the Tex Swapper.
  - v5.2.111 upgrades DDS -> .TEX to a universal SM3 2D target route. Any selected SM3 TEX target can be wrapped even when the old extractor-shell path is unavailable; valid target shells are preserved when possible and a safe 0x44 IMG shell is used as fallback.
  - v5.2.111 writes the confirmed loose NativeTEX separator [IMG 0x44][PHYS][mip payload], matching the working RaimiHook files seen in game logs.
  - v5.2.135 adds EXPORT TO DDS beside EXPORT SELECTED .TEX and OPEN OUTPUT in the Browse .TEX Folder image-preview window. TEX export stays byte-for-byte; DDS export wraps the selected native mip payload in a DDS header without re-encoding.
  - v5.2.136 fixes universal PCPACK viewing in Tex Swapper by sharing the Pack Extractor's multi-route SM3/APKF discovery instead of requiring one rigid hsam/table layout. Special packs such as startup/logo, compact-header, nonstandard APKF, and direct APKF routes are accepted; valid packs with no TEX show 0 textures instead of a false wrong-game error.
  - v5.2.143 reworks Tex Swapper into full Classic Workflow, .TEX, and Browse + Image pages. The native .TEX folder reviewer is embedded directly in the Toolkit instead of opening a second window.
  - v5.2.144 finishes the Classic workflow pass: adds MULTIPLE FILE EDITOR-SAFE PATCH, restores the two loose .TEX actions to Classic for quick use, and removes the redundant Open Browse + Image action because Browse + Image is already a full page.
  - v5.2.145 simplifies the Tex Swapper layout to two tabs only: Classic Workflow and Browse + Image. The loose .TEX actions remain part of Classic Workflow.
  - v5.2.146 keeps the v5.2.145 Tex Swapper UI/backend unchanged and regression-verifies Classic, Browse + Image, NativeTEX preview/export, PHYS/no-PHYS, and mip preservation while Folder Viewer is upgraded.
  - v5.2.162 adds direct SM3 Xbox/XE pack viewing in Tex Swapper: XEPACK/XEAPK -> read-only TEX extraction -> Xenos endian correction + untile -> Browse + Image preview and base-mip DDS export. PC editing/reimport is unchanged; Xbox reimport stays blocked until reverse retile/repack is proven.
  - Best replacement input is a raw component1 .bin or a DDS whose payload
    after the DDS header exactly matches the selected component1 size.
  - PNG insertion is intentionally limited to uncompressed exact-size cases.
    DXT PNG -> DXT compression is not included.
"""
from __future__ import annotations
import os, sys, csv, json, struct, tempfile, shutil, webbrowser, traceback, re, hashlib
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception as e:
    print('Tkinter required:', e)
    raise

try:
    from PIL import Image, ImageTk
    HAS_PIL=True
except Exception:
    HAS_PIL=False

from sm3_toolkit.services import tex_preview_core as core
from sm3_toolkit.services import pack_extract_service as pack_route_backend
from sm3_toolkit.services import xbox_pack_extract_service as xbox_pack_backend
from sm3_toolkit.sm3_pack_guard import (
    WRONG_GAME_GUARD_MESSAGE,
    exception_suggests_wrong_game,
    looks_like_wrong_game_or_unsupported_sm3_path,
    wrong_game_detail,
)
from sm3_toolkit.theme import COLORS
CORE_IMPORT_ERROR = None

SM3_MAGIC_OFF=0x30
SM3_COUNT_OFF=0x54
SM3_TABLE_START_CANDIDATES=[0x36C,0x368,0x364,0x370,0x360,0x35C,0x374]
SM3_MAGIC=b'hsam'
NCH_MAGIC=b'NCH\x00'
FOURCC_OK={b'DXT1',b'DXT3',b'DXT5'}
IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp'}

# v5.2.108 - RaimiHook Stage 2B loose native .TEX support.
# IMPORTANT: selected-target conversion now uses the REAL SM3 extractor shell.
# Exact loose file layout used by the SM3 Pack Extractor: [component0 IMG descriptor][component1/PHYS payload].
# For normal SM3 TEX resources component0 is 0x44 bytes.
NATIVE_TEX_HEADER_SIZE=0x44
DDS_MAGIC=b'DDS '
DDS_HEADER_SIZE=124
DDS_PIXELFORMAT_SIZE=32
NATIVE_TEX_LEGACY_FOURCC={
    b'DXT1':0x31545844,
    b'DXT2':0x32545844,
    b'DXT3':0x33545844,
    b'DXT4':0x34545844,
    b'DXT5':0x35545844,
}
NATIVE_TEX_DXGI_TO_FOURCC={
    71:0x31545844, 72:0x31545844,  # BC1 UNORM / SRGB -> DXT1
    74:0x33545844, 75:0x33545844,  # BC2 UNORM / SRGB -> DXT3
    77:0x35545844, 78:0x35545844,  # BC3 UNORM / SRGB -> DXT5
}
DDSCAPS2_CUBEMAP=0x00000200
DDSCAPS2_VOLUME=0x00200000
DDS_PF_ALPHAPIXELS=0x00000001
DDS_PF_FOURCC=0x00000004
DDS_PF_RGB=0x00000040
DDS_PF_LUMINANCE=0x00020000
NATIVE_TEX_PHYS_MAGIC=b'PHYS'
NATIVE_TEX_FMT_BGRA32=21   # SM3 numeric 0x15 / A8R8G8B8-style
NATIVE_TEX_FMT_L8=50       # SM3 numeric 0x32 / L8-style


def sm3_resource_hash(name:str)->int:
    """Spider-Man 3 case-insensitive x33 resource-name hash."""
    h=0
    for ch in str(name or ''):
        c=ord(ch)
        if 0x41 <= c <= 0x5A:
            c += 0x20
        h=((h*33)+c)&0xFFFFFFFF
    return h


def parse_sm3_hash_value(value, fallback_name='')->int:
    """Accept int, 0x12345678, or plain 8-digit hexadecimal target hash values."""
    if isinstance(value,int):
        return value & 0xFFFFFFFF
    text=str(value or '').strip()
    if text:
        try:
            if text.lower().startswith('0x'):
                return int(text,16)&0xFFFFFFFF
            if re.fullmatch(r'[0-9A-Fa-f]{8}',text):
                return int(text,16)&0xFFFFFFFF
            return int(text,0)&0xFFFFFFFF
        except Exception:
            pass
    if fallback_name:
        return sm3_resource_hash(fallback_name)
    raise ValueError(f'Could not parse SM3 resource hash from {value!r}.')


def native_tex_fourcc_text(fmt:int)->str:
    fmt=int(fmt)&0xFFFFFFFF
    if fmt==NATIVE_TEX_FMT_BGRA32:
        return 'BGRA32/A8R8G8B8 (21)'
    if fmt==NATIVE_TEX_FMT_L8:
        return 'L8 (50)'
    try:
        raw=struct.pack('<I',fmt)
        if all(32 <= b < 127 for b in raw):
            return raw.decode('ascii',errors='replace')
    except Exception:
        pass
    return f'0x{fmt:08X}'


def native_tex_mip_size(fmt:int,width:int,height:int)->int:
    """Payload size for the SM3 2D formats supported by the loose NativeTEX route."""
    fmt=int(fmt)&0xFFFFFFFF
    w=max(1,int(width)); h=max(1,int(height))
    bx=max(1,(w+3)//4)
    by=max(1,(h+3)//4)
    if fmt==0x31545844:                         # DXT1 / BC1
        return bx*by*8
    if fmt in (0x32545844,0x33545844,0x34545844,0x35545844): # DXT2/3/4/5
        return bx*by*16
    if fmt==NATIVE_TEX_FMT_BGRA32:
        return w*h*4
    if fmt==NATIVE_TEX_FMT_L8:
        return w*h
    raise ValueError(f'Unsupported native .TEX DDS format: {native_tex_fourcc_text(fmt)}')


def native_tex_total_payload_size(fmt:int,width:int,height:int,mips:int)->int:
    total=0
    w=max(1,int(width)); h=max(1,int(height)); m=max(1,int(mips))
    for _ in range(m):
        total += native_tex_mip_size(fmt,w,h)
        w=max(1,w>>1); h=max(1,h>>1)
    return total


def parse_dds_for_native_tex(path:Path)->dict:
    """Read a 2D DDS and return sequential bytes suitable for SM3 NativeTEX.

    Supported source encodings:
      - legacy DXT1/DXT2/DXT3/DXT4/DXT5
      - DX10 BC1/BC2/BC3
      - native-style 32-bit BGRA/A8R8G8B8 DDS -> SM3 numeric format 21
      - 8-bit luminance/R8 DDS -> SM3 numeric format 50

    This expands the old converter without pretending BC4/BC5/BC7 or arrays/cubes
    are confirmed SM3 NativeTEX formats.
    """
    path=Path(path)
    data=path.read_bytes()
    if len(data)<128 or data[:4]!=DDS_MAGIC:
        raise ValueError('Not a valid DDS file (DDS magic/header missing).')
    header_size=read_u32le(data,4)
    if header_size!=DDS_HEADER_SIZE:
        raise ValueError(f'Unexpected DDS header size {header_size}; expected 124.')
    height=read_u32le(data,12)
    width=read_u32le(data,16)
    depth=read_u32le(data,24) or 1
    mips=read_u32le(data,28) or 1
    pf_size=read_u32le(data,76)
    if pf_size!=DDS_PIXELFORMAT_SIZE:
        raise ValueError(f'Unexpected DDS pixel-format size {pf_size}; expected 32.')
    pf_flags=read_u32le(data,80)
    fourcc=data[84:88]
    rgb_bits=read_u32le(data,88)
    rmask=read_u32le(data,92); gmask=read_u32le(data,96)
    bmask=read_u32le(data,100); amask=read_u32le(data,104)
    caps2=read_u32le(data,112)
    if caps2 & DDSCAPS2_CUBEMAP:
        raise ValueError('Cubemap DDS is not supported by the loose .TEX 2D route.')
    if caps2 & DDSCAPS2_VOLUME or depth>1:
        raise ValueError('Volume DDS is not supported by the loose .TEX 2D route.')

    payload_offset=128
    fmt=None
    source_kind=''
    if fourcc==b'DX10':
        if len(data)<148:
            raise ValueError('DDS uses DX10 but the DX10 extension header is missing.')
        dxgi_format,resource_dimension,misc_flag,array_size,_misc2=struct.unpack_from('<IIIII',data,128)
        payload_offset=148
        if resource_dimension!=3:
            raise ValueError(f'DX10 DDS is not a 2D texture (resource dimension {resource_dimension}).')
        if array_size!=1:
            raise ValueError(f'DX10 texture arrays are not supported (array size {array_size}).')
        if misc_flag & 0x4:
            raise ValueError('DX10 cubemap DDS is not supported by the loose .TEX route.')
        fmt=NATIVE_TEX_DXGI_TO_FOURCC.get(dxgi_format)
        if fmt is not None:
            source_kind=f'DX10 BC -> {native_tex_fourcc_text(fmt)}'
        elif dxgi_format in (87,88):  # B8G8R8A8/B8G8R8X8
            fmt=NATIVE_TEX_FMT_BGRA32
            source_kind='DX10 BGRA32 -> SM3 format 21'
        elif dxgi_format==61:         # R8_UNORM
            fmt=NATIVE_TEX_FMT_L8
            source_kind='DX10 R8 -> SM3 format 50'
        else:
            raise ValueError(
                f'Unsupported DXGI format {dxgi_format}. Confirmed loose .TEX input supports '
                'BC1/BC2/BC3, B8G8R8A8/B8G8R8X8, and R8.'
            )
    elif (pf_flags & DDS_PF_FOURCC) or fourcc.strip(b'\x00 '):
        fmt=NATIVE_TEX_LEGACY_FOURCC.get(fourcc)
        if fmt is None:
            shown=fourcc.decode('ascii',errors='replace')
            raise ValueError(
                f'Unsupported DDS FourCC {shown!r}. Save as DXT1/DXT3/DXT5, BGRA32, or L8 '
                'for the universal SM3 loose .TEX route.'
            )
        source_kind=f'legacy {fourcc.decode("ascii",errors="replace")}'
    elif (pf_flags & DDS_PF_LUMINANCE) and rgb_bits==8:
        fmt=NATIVE_TEX_FMT_L8
        source_kind='DDS L8 -> SM3 format 50'
    elif (pf_flags & DDS_PF_RGB) and rgb_bits==32:
        # SM3 numeric format 21 is the A8R8G8B8/BGRA byte layout. Only accept
        # the common matching masks so bytes can be copied without a hidden swizzle.
        if (rmask,gmask,bmask) != (0x00FF0000,0x0000FF00,0x000000FF):
            raise ValueError(
                '32-bit DDS channel masks are not BGRA/A8R8G8B8-compatible. '
                'Save the DDS as BGRA8/A8R8G8B8 or DXT5 before converting to .TEX.'
            )
        if amask not in (0,0xFF000000):
            raise ValueError('Unsupported 32-bit DDS alpha mask for SM3 format 21.')
        fmt=NATIVE_TEX_FMT_BGRA32
        source_kind='DDS BGRA32/A8R8G8B8 -> SM3 format 21'
    else:
        raise ValueError(
            'Unsupported DDS pixel format. Use DXT1/DXT3/DXT5, BGRA32/A8R8G8B8, or L8/R8.'
        )

    if width<=0 or height<=0:
        raise ValueError(f'Invalid DDS dimensions: {width}x{height}.')
    expected=native_tex_total_payload_size(fmt,width,height,mips)
    available=len(data)-payload_offset
    if available<expected:
        raise ValueError(
            f'DDS payload is too short. Expected {expected} bytes for {width}x{height}, '
            f'{mips} mip(s), {native_tex_fourcc_text(fmt)}; found {available}.'
        )
    payload=data[payload_offset:payload_offset+expected]
    return {
        'path':str(path),'width':width,'height':height,'depth':1,'mips':mips,
        'format':fmt,'format_text':native_tex_fourcc_text(fmt),
        'payload':payload,'payload_size':expected,'source_payload_size':available,
        'payload_offset':payload_offset,'source_kind':source_kind,
    }


def build_native_tex_header(resource_hash:int,dds_info:dict)->bytes:
    """Create a conservative 0x44 SM3 IMG shell for a 2D loose NativeTEX.

    Depth is serialized as 0, matching known working SM3 loose files. RaimiHook's
    DEPTH0-COMPAT route promotes it to runtime depth 1 for 2D textures.
    """
    words=[
        0,0,0,int(resource_hash)&0xFFFFFFFF,
        0,0,
        int(dds_info['width']),int(dds_info['height']),0,
        int(dds_info['mips']),int(dds_info['format']),
        0,0,0,0,0,0,
    ]
    return struct.pack('<17I',*words)


def assemble_native_tex_blob(component0:bytes,payload:bytes,include_phys:bool=True)->bytes:
    """Build a loose SM3 .tex while preserving whether the payload uses PHYS.

    Some valid SM3 loose textures are laid out as [0x44 IMG][payload] with no PHYS.
    Others use [0x44 IMG][PHYS][payload]. When a real SM3 target/source shell exists,
    we preserve that original contract instead of forcing PHYS on every output.
    """
    blob=bytes(component0)
    if include_phys:
        blob += NATIVE_TEX_PHYS_MAGIC
    blob += bytes(payload)
    return blob


def native_tex_trim_payload_for_mips(payload:bytes, fmt:int, width:int, height:int, mips:int)->bytes:
    """Return exactly the prefix needed for the requested mip chain."""
    need=native_tex_total_payload_size(fmt,width,height,mips)
    if len(payload) < need:
        raise ValueError(
            f'Payload is too short for {width}x{height}, {mips} mip(s), {native_tex_fourcc_text(fmt)}: '
            f'need {need} bytes, found {len(payload)}.'
        )
    return bytes(payload[:need])


def resolve_native_tex_output_contract(source_mips:int, source_has_phys:bool, dds_info:dict)->dict:
    """Preserve the original loose-TEX contract when converting from a real SM3 target/source.

    - mip count follows the real source/target shell when available
    - PHYS vs no-PHYS follows the real source/target shell when available
    - DDS may contain extra mip levels; they are safely trimmed to the preserved count
    - DDS may not contain fewer mip levels than the preserved source contract
    """
    preserved_mips=max(1,int(source_mips or 1))
    available_mips=max(1,int(dds_info.get('mips') or 1))
    if available_mips < preserved_mips:
        raise ValueError(
            f'The edited DDS only has {available_mips} mip(s), but the selected SM3 texture '
            f'expects {preserved_mips}. Save the DDS with at least {preserved_mips} mip(s), '
            f'or edit a target that uses fewer mips.'
        )
    payload=native_tex_trim_payload_for_mips(
        dds_info['payload'], int(dds_info['format']), int(dds_info['width']), int(dds_info['height']), preserved_mips
    )
    patched_info=dict(dds_info)
    patched_info['mips']=preserved_mips
    patched_info['payload']=payload
    patched_info['payload_size']=len(payload)
    return {
        'dds_info':patched_info,
        'include_phys':bool(source_has_phys),
        'preserved_mips':preserved_mips,
        'dds_available_mips':available_mips,
        'trimmed_extra_mips':max(0, available_mips-preserved_mips),
    }


def write_native_tex_from_dds(dds_path:Path,output_path:Path,resource_name:str,resource_hash:int)->dict:
    """Universal 2D DDS -> loose SM3 .tex using a conservative generated shell.

    There is no original SM3 source contract in this route, so the generated fallback still
    uses the DDS mip count and the generic PHYS loose layout.
    """
    info=parse_dds_for_native_tex(Path(dds_path))
    output_path=Path(output_path)
    if output_path.suffix.lower()!='.tex':
        output_path=output_path.with_suffix('.tex')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    header=build_native_tex_header(resource_hash,info)
    blob=assemble_native_tex_blob(header,info['payload'],include_phys=True)
    output_path.write_bytes(blob)
    return {
        'dds':str(dds_path),'tex':str(output_path),'asset':resource_name,
        'hash':f'0x{int(resource_hash)&0xFFFFFFFF:08X}',
        'width':info['width'],'height':info['height'],'depth_serialized':0,
        'mips':info['mips'],'format':info['format_text'],
        'phys_bytes':info['payload_size'],'tex_bytes':len(blob),
        'phys_marker_bytes':4,'source_dds_kind':info.get('source_kind',''),
        'layout':'GENERATED fallback: 0x44 IMG + ASCII PHYS + sequential mip payload',
        'shell_mode':'GENERATED_SAFE_0x44',
        'size_rule':'No original PCPACK/component1 same-size restriction; intended for RaimiHook loose NativeTEX.',
        'contract_rule':'No original SM3 target was selected, so DDS mip count and PHYS layout were kept.',
    }

def extract_selected_tex_components_like_pack_extractor(pcpack_path:Path,target:dict)->tuple[bytes,bytes]:
    """Extract the selected TEX exactly the same way the SM3 Pack Extractor does.

    Pack Extractor output for a TEX resource is the raw concatenation of its APKF
    components. For normal textures that is component0 (IMG descriptor) followed
    by component1 (PHYS image/mip payload).
    """
    pcpack_path=Path(pcpack_path)
    if not pcpack_path.exists():
        raise ValueError(f'Original PCPACK not found: {pcpack_path}')
    data=pcpack_path.read_bytes()
    required=(
        'component0_absolute_start_dec','component0_absolute_end_dec',
        'component1_absolute_start_dec','component1_absolute_end_dec',
    )
    missing=[k for k in required if target.get(k) in (None,'')]
    if missing:
        raise ValueError('Selected target is missing extractor offsets: ' + ', '.join(missing) + '. Build Preview again.')
    c0s=int(target['component0_absolute_start_dec']); c0e=int(target['component0_absolute_end_dec'])
    c1s=int(target['component1_absolute_start_dec']); c1e=int(target['component1_absolute_end_dec'])
    if not (0 <= c0s < c0e <= len(data) and 0 <= c1s < c1e <= len(data)):
        raise ValueError(
            f'Selected target component range is outside the PCPACK. '
            f'component0={c0s:#x}-{c0e:#x}, component1={c1s:#x}-{c1e:#x}, pack={len(data):#x}'
        )
    return data[c0s:c0e], data[c1s:c1e]


def patch_extractor_component0_for_dds(component0:bytes,dds_info:dict,resource_hash:int|None=None)->tuple[bytes,str]:
    """Patch a real SM3 IMG shell when available; fall back to a safe 0x44 shell.

    v5.2.111 deliberately no longer rejects a target merely because its extracted
    component0 is not exactly 0x44 bytes. For known IMG shells, the first 0x44
    descriptor bytes are preserved and patched. If a usable shell cannot be read,
    the selected target identity is still enough to build a valid loose 2D shell.
    """
    raw=bytes(component0 or b'')
    if len(raw)>=NATIVE_TEX_HEADER_SIZE:
        shell=bytearray(raw[:NATIVE_TEX_HEADER_SIZE])
        mode='PRESERVED_FIRST_0x44_FROM_TARGET'
    else:
        if resource_hash is None:
            raise ValueError('Target shell is shorter than 0x44 and no resource hash was supplied for fallback.')
        shell=bytearray(build_native_tex_header(resource_hash,dds_info))
        mode='GENERATED_SAFE_0x44_FALLBACK'
    if resource_hash is not None:
        struct.pack_into('<I',shell,0x0C,int(resource_hash)&0xFFFFFFFF)
    struct.pack_into('<I',shell,0x18,int(dds_info['width']))
    struct.pack_into('<I',shell,0x1C,int(dds_info['height']))
    # Preserve the real target's depth field for a real shell. Generated shells use 0.
    if mode.startswith('GENERATED'):
        struct.pack_into('<I',shell,0x20,0)
    struct.pack_into('<I',shell,0x24,int(dds_info['mips']))
    struct.pack_into('<I',shell,0x28,int(dds_info['format']))
    return bytes(shell),mode

def write_selected_original_tex_from_pcpack(pcpack_path:Path,target:dict,output_path:Path)->dict:
    """Export one selected original .tex using the same component concatenation as Pack Extractor."""
    c0,c1=extract_selected_tex_components_like_pack_extractor(Path(pcpack_path),target)
    output_path=Path(output_path)
    if output_path.suffix.lower() != '.tex':
        output_path=output_path.with_suffix('.tex')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    blob=c0+c1
    output_path.write_bytes(blob)
    if not output_path.exists() or output_path.stat().st_size != len(blob):
        raise IOError('The selected original .TEX was not written correctly.')
    return {
        'tex':str(output_path),
        'asset':str(target.get('asset') or 'texture'),
        'hash':str(target.get('filename_hash') or ''),
        'component0_bytes':len(c0),'component1_bytes':len(c1),'tex_bytes':len(blob),
        'layout':'SM3 Pack Extractor exact component0 + component1 concatenation',
        'component0_sha256':hashlib.sha256(c0).hexdigest(),
        'component1_sha256':hashlib.sha256(c1).hexdigest(),
        'tex_sha256':hashlib.sha256(blob).hexdigest(),
    }


def write_native_tex_from_dds_using_extractor_shell(pcpack_path:Path,target:dict,dds_path:Path,output_path:Path)->dict:
    """Universal selected-SM3-target DDS -> loose .tex.

    Preferred path: preserve the selected target's real first 0x44 IMG descriptor.
    When a real target shell exists, this route now also preserves that texture's
    mip-count contract and whether the loose layout uses PHYS or not.

    Fallback path: if extractor offsets/shell are unavailable, build a conservative
    0x44 IMG shell from the selected target hash. In that fallback case PHYS remains
    the default because there is no provable original loose-layout contract to preserve.
    """
    asset=str(target.get('asset') or 'texture')
    resource_hash=parse_sm3_hash_value(target.get('filename_hash'),asset)
    info=parse_dds_for_native_tex(Path(dds_path))
    original_c1=b''
    extractor_error=''
    include_phys=True
    preserved_contract='GENERATED_FALLBACK_DDS_MIPS_PLUS_PHYS'
    preserved_mips=max(1,int(info.get('mips') or 1))
    trimmed_extra_mips=0
    try:
        c0,original_c1=extract_selected_tex_components_like_pack_extractor(Path(pcpack_path),target)
    except Exception as exc:
        c0=b''
        extractor_error=str(exc)
    if len(c0) >= NATIVE_TEX_HEADER_SIZE:
        source_has_phys=(len(original_c1)>=4 and original_c1[:4]==NATIVE_TEX_PHYS_MAGIC)
        source_mips=read_u32le(c0,0x24) or int(str(target.get('tex_mips') or target.get('mips') or '1') or '1')
        contract=resolve_native_tex_output_contract(source_mips, source_has_phys, info)
        info=contract['dds_info']
        include_phys=contract['include_phys']
        preserved_mips=contract['preserved_mips']
        trimmed_extra_mips=contract['trimmed_extra_mips']
        preserved_contract='PRESERVED_SELECTED_TARGET_TEX_CONTRACT'
    patched_c0,shell_mode=patch_extractor_component0_for_dds(c0,info,resource_hash)
    output_path=Path(output_path)
    if output_path.suffix.lower() != '.tex':
        output_path=output_path.with_suffix('.tex')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    blob=assemble_native_tex_blob(patched_c0,info['payload'],include_phys=include_phys)
    output_path.write_bytes(blob)
    if not output_path.exists() or output_path.stat().st_size != len(blob):
        raise IOError('The universal loose .TEX was not written correctly.')
    return {
        'dds':str(dds_path),'tex':str(output_path),'asset':asset,
        'hash':f'0x{resource_hash:08X}',
        'width':info['width'],'height':info['height'],'depth_runtime':1,
        'mips':info['mips'],'format':info['format_text'],
        'phys_bytes':info['payload_size'],'phys_marker_bytes':(4 if include_phys else 0),'tex_bytes':len(blob),
        'original_component0_bytes':len(c0),'original_component1_bytes':len(original_c1),
        'component0_source':shell_mode,
        'extractor_shell_error':extractor_error,
        'component0_preserved_except':'hash + width + height + mips + format; real target depth preserved',
        'patched_component0_sha256':hashlib.sha256(patched_c0).hexdigest(),
        'new_phys_sha256':hashlib.sha256(info['payload']).hexdigest(),
        'layout':('SM3 loose NativeTEX: 0x44 IMG + ASCII PHYS + sequential DDS mip payload' if include_phys else 'SM3 loose NativeTEX: 0x44 IMG + sequential DDS mip payload (no PHYS)'),
        'source_dds_kind':info.get('source_kind',''),
        'size_rule':'No original component1 same-size restriction; intended for RaimiHook NativeTEX.',
        'contract_rule':preserved_contract,
        'preserved_target_mips':preserved_mips,
        'trimmed_extra_dds_mips':trimmed_extra_mips,
        'preserved_phys_layout':('PHYS' if include_phys else 'NO_PHYS'),
    }


# Xbox 360 / Xenos loose TEX support (Texture Lab v2).
# The all-resource Xbox extractor writes [0x84 Xenos TEX descriptor][component1 GPU bytes].
# This decoder is read-only: it endian-corrects + untile/unswizzles the BASE mip for preview/DDS export.
XBOX_TEX_HEADER_SIZE=0x84
XBOX_XENOS_FORMATS={
    2: ('L8', NATIVE_TEX_FMT_L8, 1),
    6: ('8_8_8_8', NATIVE_TEX_FMT_BGRA32, 4),
    18: ('DXT1', 0x31545844, 8),
    19: ('DXT3', 0x33545844, 16),
    20: ('DXT5', 0x35545844, 16),
}


def _read_u32be(data:bytes, off:int)->int:
    return struct.unpack_from('>I', data, off)[0]


def _xbox_swap_endian(data:bytes, mode:int)->bytes:
    """Apply the Xenos texture fetch endian mode to a byte stream."""
    raw=bytes(data)
    mode=int(mode)&3
    if mode==0:
        return raw
    out=bytearray(raw)
    if mode==1:  # 8-in-16
        n=len(out)&~1
        for i in range(0,n,2):
            out[i],out[i+1]=out[i+1],out[i]
    elif mode==2:  # 8-in-32
        n=len(out)&~3
        for i in range(0,n,4):
            out[i:i+4]=out[i:i+4][::-1]
    else:  # 16-in-32
        n=len(out)&~3
        for i in range(0,n,4):
            a,b,c,d=out[i:i+4]
            out[i:i+4]=bytes((c,d,a,b))
    return bytes(out)


def _xg_address_2d_tiled_x(offset:int, width_units:int, texel_pitch:int)->int:
    """XGAddress2DTiledX: tiled-memory unit offset -> linear X."""
    aligned_width=(int(width_units)+31)&~31
    texel_pitch=int(texel_pitch)
    log_bpp=(texel_pitch>>2)+((texel_pitch>>1)>>(texel_pitch>>2))
    offset_b=int(offset)<<log_bpp
    offset_t=((offset_b & ~4095)>>3)+((offset_b & 1792)>>2)+(offset_b & 63)
    offset_m=offset_t>>(7+log_bpp)
    macro_x=(offset_m % (aligned_width>>5))<<2
    tile=((((offset_t>>(5+log_bpp)) & 2)+(offset_b>>6)) & 3)
    macro=(macro_x+tile)<<3
    micro=((((offset_t>>1)&~15)+(offset_t&15)) & ((texel_pitch<<3)-1))>>log_bpp
    return macro+micro


def _xg_address_2d_tiled_y(offset:int, width_units:int, texel_pitch:int)->int:
    """XGAddress2DTiledY: tiled-memory unit offset -> linear Y."""
    aligned_width=(int(width_units)+31)&~31
    texel_pitch=int(texel_pitch)
    log_bpp=(texel_pitch>>2)+((texel_pitch>>1)>>(texel_pitch>>2))
    offset_b=int(offset)<<log_bpp
    offset_t=((offset_b & ~4095)>>3)+((offset_b & 1792)>>2)+(offset_b & 63)
    offset_m=offset_t>>(7+log_bpp)
    macro_y=(offset_m // (aligned_width>>5))<<2
    tile=((offset_t>>(6+log_bpp))&1)+((offset_b&2048)>>10)
    macro=(macro_y+tile)<<3
    micro=((((offset_t & (((texel_pitch<<6)-1)&~31))+((offset_t&15)<<1))>>(3+log_bpp))&~1)
    return macro+micro+((offset_t&16)>>4)


def _xbox_untile_surface(src:bytes, padded_width_units:int, padded_height_units:int, texel_pitch:int)->bytes:
    """Convert a Xenos 2D tiled surface to padded linear order.

    IMPORTANT: XGAddress2DTiledX/Y maps each sequential *tiled source* unit to
    its linear destination X/Y.  Old experiments accidentally used this backwards.
    """
    pw=int(padded_width_units); ph=int(padded_height_units); tp=int(texel_pitch)
    need=pw*ph*tp
    if pw<=0 or ph<=0 or tp<=0:
        raise ValueError('Invalid Xbox tiled surface dimensions.')
    if len(src)<need:
        raise ValueError(f'Xbox base surface is short ({len(src)} < {need} bytes).')
    out=bytearray(need)
    for off in range(pw*ph):
        x=_xg_address_2d_tiled_x(off,pw,tp)
        y=_xg_address_2d_tiled_y(off,pw,tp)
        so=off*tp
        do=(y*pw+x)*tp
        if 0 <= do <= need-tp:
            out[do:do+tp]=src[so:so+tp]
    return bytes(out)


def _xbox_crop_linear_surface(padded:bytes, padded_width_units:int, logical_width_units:int, logical_height_units:int, texel_pitch:int)->bytes:
    pw=int(padded_width_units); lw=int(logical_width_units); lh=int(logical_height_units); tp=int(texel_pitch)
    row_in=pw*tp; row_out=lw*tp
    out=bytearray(row_out*lh)
    for y in range(lh):
        so=y*row_in; do=y*row_out
        out[do:do+row_out]=padded[so:so+row_out]
    return bytes(out)


def _looks_like_xbox_tex(data:bytes)->bool:
    if len(data)<XBOX_TEX_HEADER_SIZE:
        return False
    try:
        d0,d1,d2,d3,d4,d5=(_read_u32be(data,off) for off in range(0x30,0x48,4))
        fmt=d1&0x3F
        width=(d2&0x1FFF)+1
        height=((d2>>13)&0x1FFF)+1
        dimension=(d5>>9)&3
        pitch_field=(d0>>22)&0x1FF
        return (
            (d0&3)==2 and fmt in XBOX_XENOS_FORMATS and
            0<width<=8192 and 0<height<=8192 and pitch_field>0 and
            dimension in (0,1,2,3)
        )
    except Exception:
        return False


def _parse_xbox_tex_file(path:Path, data:bytes)->dict:
    header=data[:XBOX_TEX_HEADER_SIZE]
    payload=data[XBOX_TEX_HEADER_SIZE:]
    d0,d1,d2,d3,d4,d5=(_read_u32be(header,off) for off in range(0x30,0x48,4))
    xfmt=d1&0x3F
    endian=(d1>>6)&3
    tiled=(d0>>31)&1
    pitch_pixels=((d0>>22)&0x1FF)*32
    width=(d2&0x1FFF)+1
    height=((d2>>13)&0x1FFF)+1
    mip_min=(d4>>2)&0xF
    mip_max=(d4>>6)&0xF
    mips=max(1,mip_max-mip_min+1)
    dimension=(d5>>9)&3
    packed_mips=(d5>>11)&1
    mip_offset=((d5>>12)&0xFFFFF)<<12
    xname,pc_fmt,texel_pitch=XBOX_XENOS_FORMATS[xfmt]

    if xfmt in (18,19,20):
        logical_w=max(1,(width+3)//4)
        logical_h=max(1,(height+3)//4)
        padded_w=max(logical_w,max(1,pitch_pixels//4))
    else:
        logical_w=width; logical_h=height
        padded_w=max(logical_w,pitch_pixels)

    # Fetch mip address is the byte start of the separate/packed mip area, and
    # therefore also the allocated byte length of base level in these extracted TEXes.
    if mip_offset>0 and mip_offset<=len(payload):
        base_alloc=mip_offset
    else:
        # No separate mip address: derive the Xenos tiled base allocation.  Tiled
        # surfaces are macro-tile padded to 32 units vertically.
        padded_h=(logical_h+31)&~31 if tiled else logical_h
        base_alloc=padded_w*padded_h*texel_pitch
        if base_alloc>len(payload):
            base_alloc=len(payload)
    row_bytes=padded_w*texel_pitch
    if row_bytes<=0 or base_alloc<row_bytes:
        raise ValueError('Xbox TEX base allocation is invalid.')
    padded_h=max(logical_h,base_alloc//row_bytes)
    tiled_bytes=payload[:padded_w*padded_h*texel_pitch]
    if len(tiled_bytes)<padded_w*padded_h*texel_pitch:
        raise ValueError('Xbox TEX component1 is shorter than the Xenos base surface allocation.')
    corrected=_xbox_swap_endian(tiled_bytes,endian)
    if tiled:
        padded_linear=_xbox_untile_surface(corrected,padded_w,padded_h,texel_pitch)
    else:
        padded_linear=corrected
    first_mip=_xbox_crop_linear_surface(padded_linear,padded_w,logical_w,logical_h,texel_pitch)

    resource_hash=_read_u32be(header,0x0C)
    stem=path.stem
    m=re.match(r'^(?:\d+_)?0x[0-9A-Fa-f]{8}\.(.+)$',stem)
    asset=m.group(1) if m else (stem.split('.',1)[-1] if '.' in stem else stem)
    logical_expected=native_tex_mip_size(pc_fmt,width,height)
    status='X360_BASE_MIP_READY' if len(first_mip)==logical_expected else 'X360_BASE_MIP_SIZE_MISMATCH'
    return {
        'platform':'X360','path':str(path),'name':path.name,'asset':asset,
        'hash_int':resource_hash,'filename_hash':f'0x{resource_hash:08X}',
        'width':width,'height':height,'depth':1,'mips':mips,
        'format_raw':pc_fmt,'format_kind':f'X360 {xname}',
        'header':header,'payload':payload,'payload_offset':XBOX_TEX_HEADER_SIZE,
        'has_phys_marker':False,'payload_bytes':len(payload),
        'expected_payload_bytes':logical_expected,'payload_status':status,'file_bytes':len(data),
        'linear_first_mip':first_mip,'first_mip_bytes':len(first_mip),
        'xbox_xenos_format':xfmt,'xbox_xenos_format_name':xname,'xbox_endian':endian,
        'xbox_tiled':bool(tiled),'xbox_pitch_pixels':pitch_pixels,
        'xbox_padded_width_units':padded_w,'xbox_padded_height_units':padded_h,
        'xbox_texel_pitch':texel_pitch,'xbox_mip_min':mip_min,'xbox_mip_max':mip_max,
        'xbox_packed_mips':bool(packed_mips),'xbox_mip_offset':mip_offset,
        'xbox_dimension':dimension,'xbox_base_alloc_bytes':base_alloc,
    }

def parse_native_tex_file(path:Path)->dict:
    """Parse a loose/extracted SM3 PC or Xbox 360 .tex for folder browsing.

    PC: historical [0x44 IMG][payload] and [0x44 IMG][PHYS][payload].
    X360 Texture Lab v2: [0x84 Xenos descriptor][tiled component1].
    """
    path=Path(path)
    data=path.read_bytes()
    if _looks_like_xbox_tex(data):
        return _parse_xbox_tex_file(path,data)
    if len(data)<NATIVE_TEX_HEADER_SIZE:
        raise ValueError('File is smaller than the 0x44 SM3 IMG descriptor.')
    header=data[:NATIVE_TEX_HEADER_SIZE]
    resource_hash=read_u32le(header,0x0C)
    width=read_u32le(header,0x18)
    height=read_u32le(header,0x1C)
    depth=read_u32le(header,0x20)
    mips=read_u32le(header,0x24) or 1
    fmt=read_u32le(header,0x28)
    if not (0 < width <= 16384 and 0 < height <= 16384):
        raise ValueError(f'Invalid SM3 TEX dimensions {width}x{height}.')
    has_phys=(len(data)>=NATIVE_TEX_HEADER_SIZE+4 and data[NATIVE_TEX_HEADER_SIZE:NATIVE_TEX_HEADER_SIZE+4]==NATIVE_TEX_PHYS_MAGIC)
    payload_offset=NATIVE_TEX_HEADER_SIZE+(4 if has_phys else 0)
    payload=data[payload_offset:]
    try:
        expected=native_tex_total_payload_size(fmt,width,height,mips)
        payload_status='EXACT' if len(payload)==expected else ('EXTRA_BYTES' if len(payload)>expected else 'SHORT_PAYLOAD')
    except Exception:
        expected=None
        payload_status='UNKNOWN_FORMAT'
    stem=path.stem
    asset=stem
    m=re.match(r'^0x([0-9A-Fa-f]{8})\.(.+)$',stem)
    if m:
        asset=m.group(2)
    elif '.' in stem:
        asset=stem.split('.',1)[-1]
    fmt_text=native_tex_fourcc_text(fmt)
    return {
        'platform':'PC','path':str(path),'name':path.name,'asset':asset,'hash_int':resource_hash,
        'filename_hash':f'0x{resource_hash:08X}','width':width,'height':height,
        'depth':depth,'mips':mips,'format_raw':fmt,'format_kind':fmt_text,
        'header':header,'payload':payload,'payload_offset':payload_offset,
        'has_phys_marker':has_phys,'payload_bytes':len(payload),'expected_payload_bytes':expected,
        'payload_status':payload_status,'file_bytes':len(data),
    }

def native_tex_preview_pil(record:dict):
    """Decode the first mip of a parsed SM3 PC/X360 .tex to a Pillow RGBA image."""
    if not HAS_PIL:
        raise RuntimeError('Pillow is required for .TEX image preview.')
    w=int(record['width']); h=int(record['height']); fmt=int(record['format_raw'])
    if str(record.get('platform','PC')).upper()=='X360':
        payload=bytes(record.get('linear_first_mip') or b'')
    else:
        payload=bytes(record['payload'])
    if fmt in (0x31545844,0x32545844,0x33545844,0x34545844,0x35545844):
        if fmt==0x31545844:
            need=native_tex_mip_size(fmt,w,h); pix=core.decode_dxt1(payload[:need],w,h)
        elif fmt in (0x32545844,0x33545844):
            need=native_tex_mip_size(fmt,w,h); pix=core.decode_dxt3(payload[:need],w,h)
        else:
            need=native_tex_mip_size(fmt,w,h); pix=core.decode_dxt5(payload[:need],w,h)
        img=Image.new('RGBA',(w,h)); img.putdata(pix); return img
    if fmt==NATIVE_TEX_FMT_BGRA32:
        need=w*h*4
        if len(payload)<need: raise ValueError(f'BGRA32 payload too short ({len(payload)} < {need}).')
        raw=payload[:need]
        pix=[(raw[i+2],raw[i+1],raw[i],raw[i+3]) for i in range(0,need,4)]
        img=Image.new('RGBA',(w,h)); img.putdata(pix); return img
    if fmt==NATIVE_TEX_FMT_L8:
        need=w*h
        if len(payload)<need: raise ValueError(f'L8 payload too short ({len(payload)} < {need}).')
        return Image.frombytes('L',(w,h),payload[:need]).convert('RGBA')
    raise ValueError(f'Preview decoder does not yet support {native_tex_fourcc_text(fmt)}.')

def export_native_tex_record_to_dds(record:dict, output_path:Path)->dict:
    """Export a parsed loose SM3 .tex to DDS.

    PC copies the native mip payload unchanged. X360 exports the confirmed
    endian-corrected + untiled BASE mip only; packed Xenos mip tails are left untouched.
    """
    w=int(record['width']); h=int(record['height'])
    is_xbox=str(record.get('platform','PC')).upper()=='X360'
    fmt_raw=int(record['format_raw']) & 0xFFFFFFFF
    if is_xbox:
        mips=1
        payload=bytes(record.get('linear_first_mip') or b'')
        expected=native_tex_mip_size(fmt_raw,w,h)
        if len(payload)!=expected:
            raise ValueError(f'Xbox base mip size mismatch: {len(payload)} bytes found, {expected} expected.')
    else:
        mips=max(1,int(record.get('mips') or 1))
        payload=bytes(record['payload'])
        expected=record.get('expected_payload_bytes')
        if expected is None:
            expected=native_tex_total_payload_size(fmt_raw,w,h,mips)
        expected=int(expected)
        if len(payload) < expected:
            raise ValueError(
                f'Selected .TEX payload is too short for DDS export: {len(payload)} bytes found, '
                f'{expected} required for {w}x{h}, {mips} mip(s), {native_tex_fourcc_text(fmt_raw)}.'
            )
        payload=payload[:expected]
    if fmt_raw==NATIVE_TEX_FMT_BGRA32:
        dds_fmt='BGRA32'
    elif fmt_raw==NATIVE_TEX_FMT_L8:
        dds_fmt='L8'
    else:
        raw=struct.pack('<I',fmt_raw)
        try: fourcc=raw.decode('ascii')
        except Exception: fourcc=''
        if fourcc not in ('DXT1','DXT2','DXT3','DXT4','DXT5'):
            raise ValueError(f'EXPORT TO DDS does not support native format {native_tex_fourcc_text(fmt_raw)} yet.')
        dds_fmt=fourcc
    output_path=Path(output_path)
    if output_path.suffix.lower()!='.dds': output_path=output_path.with_suffix('.dds')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    blob=build_dds_header(w,h,mips,dds_fmt,len(payload))+payload
    output_path.write_bytes(blob)
    if not output_path.is_file() or output_path.stat().st_size != len(blob):
        raise IOError('DDS export was not written correctly.')
    method=(
        'Xbox 360 base mip: Xenos endian corrected + tiled surface untiled; DDS header added; mip tail not exported'
        if is_xbox else 'Native SM3 mip payload copied unchanged; DDS header added only'
    )
    return {
        'dds':str(output_path),'source_tex':str(record.get('path') or ''),
        'asset':str(record.get('asset') or 'texture'),'hash':str(record.get('filename_hash') or ''),
        'platform':'X360' if is_xbox else 'PC','width':w,'height':h,'mips':mips,'format':dds_fmt,
        'payload_bytes':len(payload),'dds_bytes':len(blob),'method':method,
    }

def write_native_tex_from_dds_using_native_tex_shell(source_tex_path:Path,dds_path:Path,output_path:Path)->dict:
    """Wrap DDS using the identity/header of any loose or extracted SM3 .tex file.

    This route now preserves the real source .tex contract:
    - source mip count stays the same
    - source PHYS vs no-PHYS layout stays the same
    - extra DDS mips are trimmed instead of silently changing the target contract
    """
    rec=parse_native_tex_file(Path(source_tex_path))
    if str(rec.get('platform','PC')).upper()=='X360':
        raise ValueError('Xbox 360 TEX reimport is read-only for now. Preview and base-mip DDS export are supported; reverse Xenos retile/repack is not enabled yet.')
    info=parse_dds_for_native_tex(Path(dds_path))
    contract=resolve_native_tex_output_contract(rec['mips'], rec['has_phys_marker'], info)
    info=contract['dds_info']
    shell,mode=patch_extractor_component0_for_dds(rec['header'],info,rec['hash_int'])
    output_path=Path(output_path)
    if output_path.suffix.lower()!='.tex':
        output_path=output_path.with_suffix('.tex')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    blob=assemble_native_tex_blob(shell,info['payload'],include_phys=contract['include_phys'])
    output_path.write_bytes(blob)
    return {
        'source_tex':str(source_tex_path),'dds':str(dds_path),'tex':str(output_path),
        'asset':rec['asset'],'hash':rec['filename_hash'],'width':info['width'],'height':info['height'],
        'mips':info['mips'],'format':info['format_text'],'source_dds_kind':info.get('source_kind',''),
        'phys_bytes':info['payload_size'],'phys_marker_bytes':(4 if contract['include_phys'] else 0),'tex_bytes':len(blob),
        'shell_mode':mode,
        'layout':('0x44 IMG + ASCII PHYS + sequential mip payload' if contract['include_phys'] else '0x44 IMG + sequential mip payload (no PHYS)'),
        'contract_rule':'PRESERVED_SOURCE_TEX_CONTRACT',
        'preserved_source_mips':contract['preserved_mips'],
        'trimmed_extra_dds_mips':contract['trimmed_extra_mips'],
        'preserved_phys_layout':('PHYS' if contract['include_phys'] else 'NO_PHYS'),
    }

def native_tex_identity_from_dds_filename(path:Path)->tuple[str,int]:
    """Recover 0xHASH.asset from Toolkit exported DDS names when no row is selected."""
    stem=Path(path).stem
    explicit_hash=None
    resource=stem
    m=re.match(r'^0x([0-9A-Fa-f]{8})\.(.+)$',stem)
    if m:
        explicit_hash=int(m.group(1),16)
        resource=m.group(2)
    for suffix in (
        '.ORIGINAL_EDIT_THIS','_ORIGINAL_EDIT_THIS',
        '.EDIT_READY','_EDIT_READY','.EDITED','_EDITED',
    ):
        if resource.upper().endswith(suffix.upper()):
            resource=resource[:-len(suffix)]
            break
    resource=resource.strip().strip('.') or 'texture'
    h=explicit_hash if explicit_hash is not None else sm3_resource_hash(resource)
    return resource,h

APP_NAME='THE TEX SWAPPER'
APP_AUTHOR='TSGAMING264'
APP_BUILD='v5.2.162 PC + Xbox TEX Preview'
APP_TITLE=f'{APP_NAME} - Made by {APP_AUTHOR}'
DEFAULT_OUTPUT_DIR='THE_TEX_SWAPPER_Output'
PREVIEW_DIR_NAME='PREVIEW_OUTPUT'
GENERATED_BUILD_DIR='__TEX_SWAPPER_BUILD_v4_8'


def resolve_user_output_base(path:Path)->Path:
    """Return the user's real chosen output folder, even after a previous preview build.

    v4.7 changed output_var to PREVIEW_OUTPUT after Build Preview. Pressing Build Preview again
    could create PREVIEW_OUTPUT/PREVIEW_OUTPUT nesting. v4.8 resolves the original base folder
    before creating a fresh generated workspace.
    """
    p=Path(path or DEFAULT_OUTPUT_DIR)
    # v4.8 normal route: <base>/__TEX_SWAPPER_BUILD_v4_8/PREVIEW_OUTPUT
    if p.name == PREVIEW_DIR_NAME and p.parent.name == GENERATED_BUILD_DIR:
        return p.parent.parent
    if p.name == GENERATED_BUILD_DIR:
        return p.parent
    # v4.7 compatibility route: <base>/PREVIEW_OUTPUT
    if p.name == PREVIEW_DIR_NAME:
        return p.parent
    return p


def reset_generated_build_workspace(base_out:Path)->Path:
    """Clear only the tool-owned generated workspace, never the user-selected folder itself."""
    base_out=Path(base_out or DEFAULT_OUTPUT_DIR)
    work=base_out/GENERATED_BUILD_DIR
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    return work


def hex32(v:int)->str:
    return f'0x{v:08X}'

def ensure_dir(p:Path)->Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_u32le(b:bytes, off:int)->int:
    if off+4>len(b): return 0
    return struct.unpack_from('<I', b, off)[0]

def clean_name(s:str, fallback='unknown')->str:
    s=(s or fallback).replace('\x00','')
    s=re.sub(r'[^A-Za-z0-9_.\-]+','_',s).strip('._')
    return (s[:150] or fallback)

def read_cstr(data:bytes, off:int, max_len:int=512)->str:
    if off<0 or off>=len(data): return ''
    end=off; lim=min(len(data), off+max_len)
    while end<lim and data[end]!=0:
        end+=1
    return data[off:end].decode('utf-8', errors='replace')

def open_path(path:Path):
    try:
        path=Path(path)
        if sys.platform.startswith('win'):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception:
        try:
            webbrowser.open(Path(path).as_uri())
        except Exception as e:
            messagebox.showerror('Open failed', str(e))

def write_csv(path:Path, rows:list[dict], fieldnames=None):
    if fieldnames is None:
        keys=[]
        for r in rows:
            for k in r.keys():
                if k not in keys: keys.append(k)
        fieldnames=keys or ['empty']
    with path.open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for r in rows: w.writerow(r)

class OuterEntry:
    def __init__(self, index, h, t, off, size, pack_size):
        self.index=index; self.hash=h; self.type_id=t; self.offset=off; self.size=size
        self.end=off+size; self.valid=size>0 and 0<=off<=self.end<=pack_size

class ComponentHeader:
    def __init__(self, index, offset, type_id, external, field2, field3, data_size, data_offset):
        self.index=index; self.offset=offset; self.type_id=type_id; self.external=external
        self.field2=field2; self.field3=field3; self.data_size=data_size; self.data_offset=data_offset
        self.base_data_address=offset+20+data_offset
        self.cursor_pos=0

class APKFFileEntry:
    def __init__(self, global_index, file_type, local_index, filename, filename_hash, file_header_offset, comp_sizes, comp_offsets):
        self.global_index=global_index; self.file_type=file_type; self.local_index=local_index
        self.filename=filename; self.filename_hash=filename_hash; self.file_header_offset=file_header_offset
        self.component_sizes=comp_sizes; self.component_offsets=comp_offsets

class SM3PCPack:
    def __init__(self, path:Path):
        self.path=Path(path); self.data=self.path.read_bytes(); self.size=len(self.data)
        self.table_start=None; self.entries=[]; self.detect_info={}
        self.parse_outer()
    def _score_table_start(self, start:int, count:int):
        if count<=0 or start+count*16>self.size:
            return {'table_start':hex(start),'score':-1,'valid_entries':0,'apfk_entries':0,'hsam_entries':0}
        valid=apkf=hsam=known=0
        for i in range(count):
            o=start+i*16
            h,t,do,ds=struct.unpack_from('<IIII', self.data, o)
            end=do+ds
            ok=ds>0 and 0<=do<=end<=self.size
            if not ok: continue
            valid+=1
            sig=self.data[do:do+4]
            if sig==b'APKF': apkf+=1; known+=1
            elif sig==b'hsam': hsam+=1; known+=1
            elif sig in (b'ElmS',b'NumW',b'CVXL') or sig.startswith(b'__Id') or sig.startswith(b'\xe8\x03'):
                known+=1
        score=valid*10+known*30+apkf*500+hsam*3
        return {'table_start':hex(start),'score':score,'valid_entries':valid,'apfk_entries':apkf,'hsam_entries':hsam,'known_signature_entries':known}
    def parse_outer(self):
        first4=self.data[:4]
        if first4==NCH_MAGIC:
            raise ValueError('This file starts with NCH. That is Web of Shadows format, not SM3 PC hsam/APKF.')
        magic=self.data[SM3_MAGIC_OFF:SM3_MAGIC_OFF+4] if self.size>=SM3_MAGIC_OFF+4 else b''
        count=read_u32le(self.data, SM3_COUNT_OFF) if self.size>=SM3_COUNT_OFF+4 else 0
        scores=[self._score_table_start(s,count) for s in SM3_TABLE_START_CANDIDATES]
        best=max(scores, key=lambda x:x.get('score',-1))
        self.detect_info={'file_name':self.path.name,'size':self.size,'magic_at_0x30':magic.decode('ascii',errors='replace'),'entry_count_at_0x54':count,'table_start_selected':best['table_start'],'table_start_candidates':scores,'looks_like_sm3':magic==SM3_MAGIC and count>0 and best.get('valid_entries',0)>0}
        if not self.detect_info['looks_like_sm3']:
            raise ValueError('Not recognized as SM3 PC PCPACK. Detection: '+json.dumps(self.detect_info, indent=2))
        self.table_start=int(best['table_start'],16)
        for i in range(count):
            o=self.table_start+i*16
            h,t,do,ds=struct.unpack_from('<IIII', self.data, o)
            self.entries.append(OuterEntry(i,h,t,do,ds,self.size))
    def apkf_entries(self):
        return [e for e in self.entries if e.valid and self.data[e.offset:e.offset+4]==b'APKF']

class APKFArchive:
    def __init__(self, data:bytes, label:str):
        self.data=data; self.label=label; self.files=[]; self.component_headers=[]; self.file_type_headers=[]
        self.parse()
    @staticmethod
    def align(pos:int, align:int)->int:
        return pos if align<=0 else (pos+align-1)&~(align-1)
    def parse(self):
        if self.data[:4]!=b'APKF':
            raise ValueError('payload not APKF')
        if len(self.data)<28:
            return
        magic,version,flag_field,bool_field,comp_count,comp_table_ptr_raw,file_table_ptr=struct.unpack_from('<4s6I', self.data,0)
        comp_off=comp_table_ptr_raw+20
        for i in range(comp_count):
            o=comp_off+i*24
            if o+24>len(self.data): break
            typeb,external,field2,field3,data_size,data_offset=struct.unpack_from('<4s5I', self.data,o)
            type_id=typeb.decode('ascii',errors='replace').replace('\x00','')
            self.component_headers.append(ComponentHeader(i,o,type_id,external,field2,field3,data_size,data_offset))
        off=struct.calcsize('<4s6I'); global_i=0
        while off+4<=len(self.data) and read_u32le(self.data, off)!=0:
            base=off
            if off+20>len(self.data): break
            type_int,unk0,n_active,p_file_header_table,n_file_headers=struct.unpack_from('<5I', self.data, off); off+=20
            if n_active>len(self.component_headers): break
            if off+4*len(self.component_headers)>len(self.data): break
            aligns=list(struct.unpack_from('<'+'I'*len(self.component_headers), self.data, off)); off+=4*len(self.component_headers)
            type_id=type_int.to_bytes(4,'little').decode('ascii',errors='replace').replace('\x00','')
            p_headers=base+12+p_file_header_table
            foff=p_headers
            for local_i in range(n_file_headers):
                if foff+8>len(self.data): break
                fh_base=foff
                p_filename,fname_hash=struct.unpack_from('<II', self.data, foff); foff+=8
                sizes=[]
                if n_active:
                    if foff+4*n_active>len(self.data): break
                    sizes=list(struct.unpack_from('<'+'I'*n_active, self.data, foff)); foff+=4*n_active
                filename=read_cstr(self.data, fh_base+p_filename)
                offsets=[]
                for ci,comp_size in enumerate(sizes):
                    ch=self.component_headers[ci]
                    alignment=aligns[ci]&0xFFFFFF
                    read_pos=self.align(max(0,ch.cursor_pos-1), alignment)
                    start=ch.base_data_address+read_pos; end=start+comp_size
                    offsets.append((start,end)); ch.cursor_pos=read_pos+comp_size
                self.files.append(APKFFileEntry(global_i,type_id,local_i,filename,fname_hash,fh_base,sizes,offsets))
                global_i+=1


def parse_tex_desc(c0:bytes):
    if len(c0)<44: return None
    width=read_u32le(c0,0x18); height=read_u32le(c0,0x1C); mips=read_u32le(c0,0x24); fmt=read_u32le(c0,0x28)
    if width<=0 or height<=0 or width>8192 or height>8192: return None
    if mips<=0 or mips>32: mips=1
    raw=struct.pack('<I',fmt)
    if raw in FOURCC_OK: kind=raw.decode('ascii')
    elif fmt==50: kind='L8'
    elif fmt==21: kind='BGRA32'
    else: kind=str(fmt)
    return {'width':width,'height':height,'mips':mips,'format_raw':fmt,'format_kind':kind}


def asset_group(name:str)->str:
    low=(name or '').lower()
    if any(x in low for x in ['_dif','_ao','diftile']): return 'DIFFUSE/AO'
    if '_nor' in low: return 'NORMAL'
    if any(x in low for x in ['_spe','_spx','_rfl','_env']): return 'SPEC/REFLECT'
    if any(x in low for x in ['_ppi','_ppp']): return 'PPI/PPP SPECIAL'
    return 'OTHER'


def scan_pcpack_textures_to_chain(pcpack_path:Path, out_root:Path):
    """Universal SM3 pack -> TEX chain scanner.

    v5.2.136: use the Pack Extractor's proven multi-route probe/APKF discovery
    instead of requiring one rigid hsam header/table layout. This keeps the
    Tex Swapper and Pack Extractor in agreement for special/small SM3 packs
    such as logo/front-end/compact/nonstandard archive routes.

    The patcher still receives exact absolute component offsets into the
    ORIGINAL selected pack, so the working replacement/write core is unchanged.
    """
    pcpack_path=Path(pcpack_path)
    data=pcpack_path.read_bytes()
    if data[:3] == b'NCH':
        raise ValueError('This file starts with NCH. That is Web of Shadows format, not an SM3 PC pack.')

    probe=pack_route_backend.probe_pack_bytes(pcpack_path.name, data)
    valid_sm3_route=bool(
        data.startswith(b'APKF')
        or data[SM3_MAGIC_OFF:SM3_MAGIC_OFF+4] == SM3_MAGIC
        or probe.hsam_offsets
        or probe.apkf_offsets
        or probe.outer_rows
        or probe.compact_header.get('is_compact_header')
    )
    if not valid_sm3_route:
        raise ValueError(
            'Not recognized as SM3 PC PCPACK/PCAPK/APKF by the universal route probe. Detection: '
            + json.dumps(probe.to_dict(), indent=2)
        )

    apkf_slices, filtered_markers = pack_route_backend.apkf_slices_from_probe(data, probe)

    chain_root=ensure_dir(out_root/'_DIRECT_PCPACK_TEX_CHAIN')
    tex_root=ensure_dir(chain_root/'TEX')
    reports=ensure_dir(out_root/'REPORTS')
    targets=[]; apkf_summaries=[]

    for slice_index, source in enumerate(apkf_slices):
        label=clean_name(source.label, f'APKF_{slice_index:04d}')
        try:
            apkf=pack_route_backend.APKFArchive(source.payload, source.label)
        except Exception as e:
            apkf_summaries.append({
                'label':label,
                'source_kind':source.source_kind,
                'absolute_base':hex(source.absolute_base),
                'archive_folder':source.archive_folder,
                'error':str(e),
            })
            continue

        apkf_summaries.append({
            'label':label,
            'source_kind':source.source_kind,
            'source_route_reason':source.route_reason,
            'absolute_base':hex(source.absolute_base),
            'archive_folder':source.archive_folder,
            'outer_index':'' if source.parent_outer_index is None else source.parent_outer_index,
            'outer_hash':'' if source.parent_outer_hash is None else hex32(source.parent_outer_hash),
            'outer_type':'' if source.parent_outer_type is None else f'0x{source.parent_outer_type:X}',
            'file_count':len(apkf.files),
        })

        for f in apkf.files:
            if f.file_type.upper()!='TEX' or len(f.component_offsets)<2:
                continue
            (c0s,c0e),(c1s,c1e)=f.component_offsets[0],f.component_offsets[1]
            abs0s=source.absolute_base+c0s; abs0e=source.absolute_base+c0e
            abs1s=source.absolute_base+c1s; abs1e=source.absolute_base+c1e
            if not (0 <= abs0s <= abs0e <= len(data) and 0 <= abs1s <= abs1e <= len(data)):
                apkf_summaries.append({
                    'label':label,
                    'source_kind':source.source_kind,
                    'absolute_base':hex(source.absolute_base),
                    'warning':f'TEX {f.filename or hex32(f.filename_hash)} component range outside selected pack',
                })
                continue
            c0=data[abs0s:abs0e]; c1=data[abs1s:abs1e]
            desc=parse_tex_desc(c0) or {}
            safe=clean_name(f.filename, f'TEX_{f.global_index:05d}')
            h=hex32(f.filename_hash)
            # Prefix with archive index too: global_index resets inside every APKF.
            d=ensure_dir(tex_root/f'A{slice_index:04d}_F{f.global_index:05d}_TEX_{h}_{safe}')
            (d/f'component0_{len(c0)}bytes.bin').write_bytes(c0)
            (d/f'component1_{len(c1)}bytes.bin').write_bytes(c1)
            row={
                'asset':f.filename,'safe_asset':safe,'filename_hash':h,'file_type':'TEX','global_index':f.global_index,
                'source_apkf_label':label,
                'source_apkf_absolute_base':hex(source.absolute_base),
                'source_archive_folder':source.archive_folder,
                'source_archive_kind':source.source_kind,
                'source_route_reason':source.route_reason,
                'source_outer_index':'' if source.parent_outer_index is None else source.parent_outer_index,
                'source_outer_hash':'' if source.parent_outer_hash is None else hex32(source.parent_outer_hash),
                'source_outer_type':'' if source.parent_outer_type is None else f'0x{source.parent_outer_type:X}',
                'component0_size':len(c0),'component1_size':len(c1),
                'component0_absolute_start':hex(abs0s),'component0_absolute_end':hex(abs0e),
                'component1_absolute_start':hex(abs1s),'component1_absolute_end':hex(abs1e),
                'component0_absolute_start_dec':abs0s,'component0_absolute_end_dec':abs0e,
                'component1_absolute_start_dec':abs1s,'component1_absolute_end_dec':abs1e,
                'width':desc.get('width',''),'height':desc.get('height',''),'mips':desc.get('mips',''),
                'format_raw':desc.get('format_raw',''),'format_kind':desc.get('format_kind',''),
                'group':asset_group(f.filename),
                'chain_folder':str(d)
            }
            targets.append(row)

    write_csv(reports/'PCPACK_DIRECT_TEX_TARGETS.csv', targets)
    write_csv(reports/'PCPACK_DIRECT_APKF_SUMMARY.csv', apkf_summaries)
    detect_info=probe.to_dict()
    detect_info.update({
        'tex_swapper_universal_route_probe':True,
        'tex_swapper_valid_sm3_route':valid_sm3_route,
        'discovered_apkf_slices':len(apkf_slices),
        'discovered_tex_targets':len(targets),
        'filtered_apkf_markers':filtered_markers,
        'note':'v5.2.136 Tex Swapper uses the same multi-route APKF discovery family as Pack Extractor; no rigid 0x30/0x54-only gate.',
    })
    (reports/'PACK_DETECT.json').write_text(json.dumps(detect_info,indent=2),encoding='utf-8')
    return chain_root, targets

def dds_payload_from_file(path:Path):
    b=path.read_bytes()
    if not b.startswith(b'DDS '):
        return None
    # Standard DDS header is 128 bytes; DX10 extended header is 148 bytes.
    if len(b)>=132 and b[84:88]==b'DX10':
        return b[148:]
    return b[128:]



def parse_dds_header_file(path:Path):
    """Parse enough of a DDS header to verify SM3 original-format replacement safety."""
    b=Path(path).read_bytes()
    if not b.startswith(b'DDS ') or len(b) < 128:
        raise ValueError('Not a standard DDS file or DDS header is too small.')
    if struct.unpack_from('<I', b, 4)[0] != 124:
        raise ValueError('DDS header size is not 124 bytes.')
    height=struct.unpack_from('<I', b, 12)[0]
    width=struct.unpack_from('<I', b, 16)[0]
    mips=struct.unpack_from('<I', b, 28)[0] or 1
    pf_size=struct.unpack_from('<I', b, 76)[0]
    pf_flags=struct.unpack_from('<I', b, 80)[0]
    fourcc=b[84:88]
    rgbbits=struct.unpack_from('<I', b, 88)[0]
    rmask=struct.unpack_from('<I', b, 92)[0]
    gmask=struct.unpack_from('<I', b, 96)[0]
    bmask=struct.unpack_from('<I', b, 100)[0]
    amask=struct.unpack_from('<I', b, 104)[0]
    header_size=148 if fourcc == b'DX10' else 128
    payload=b[header_size:]
    if fourcc in (b'DXT1', b'DXT3', b'DXT5'):
        fmt=fourcc.decode('ascii')
    elif rgbbits == 32:
        # SM3 PC format 21 route is BGRA/A8R8G8B8 style.
        fmt='BGRA32'
    elif rgbbits == 8 or (pf_flags & 0x20000):
        fmt='L8'
    else:
        fmt='UNKNOWN'
    header=b[:header_size]
    return {
        'path':str(path),'width':width,'height':height,'mips':mips,
        'pf_size':pf_size,'pf_flags':hex(pf_flags),'fourcc':fourcc.decode('ascii','replace'),
        'rgbbits':rgbbits,'rmask':hex(rmask),'gmask':hex(gmask),'bmask':hex(bmask),'amask':hex(amask),
        'format_kind':fmt,'header_size':header_size,'payload_size':len(payload),'payload':payload,
        'header_sha256':sha256_bytes(header),'payload_sha256':sha256_bytes(payload)
    }


def expected_target_dds_header(target:dict) -> bytes:
    """Build the exact DDS header the tool exports for this target descriptor."""
    w=int(target.get('width') or 0)
    h=int(target.get('height') or 0)
    mips=int(target.get('mips') or 1)
    fmt=str(target.get('format_kind') or '')
    payload_size=int(target.get('component1_size') or 0)
    return build_dds_header(w,h,mips,fmt,payload_size)

def dds_header_info_for_target(dds_path:Path, target:dict):
    """Return actual/expected header hashes for strict header-lock checks."""
    b=Path(dds_path).read_bytes()
    info=parse_dds_header_file(Path(dds_path))
    actual_header=b[:info['header_size']]
    expected_header=expected_target_dds_header(target)
    return {
        'actual_header_size': info['header_size'],
        'expected_header_size': len(expected_header),
        'actual_header_sha256': sha256_bytes(actual_header),
        'expected_header_sha256': sha256_bytes(expected_header),
        'actual_header_matches_expected': actual_header == expected_header,
    }

def validate_dds_matches_target_header_locked(dds_path:Path, target:dict, strict:bool=True):
    """Validate format + payload + exact DDS header for target-locked final reimport."""
    info, problems = validate_dds_matches_target(dds_path, target, strict=False)
    header = dds_header_info_for_target(dds_path, target)
    if not header['actual_header_matches_expected']:
        problems.append(
            'DDS header does not match the SM3 target/export header exactly '
            f"actual={header['actual_header_sha256']} expected={header['expected_header_sha256']}"
        )
    info.update(header)
    if problems and strict:
        raise ValueError('DDS does not match original SM3 TEX target/header lock:\n- ' + '\n- '.join(problems))
    return info, problems

def normalize_dds_to_target_game_format(edited_dds_path:Path, target:dict, output_dir:Path):
    """v5.2.34: rebuild a DDS as SM3 target-header + edited payload.

    This is for Paint.NET/GIMP/editor overwrite recovery where the visual/payload is
    intended for the same target but the editor rewrote harmless DDS header bytes.
    The function DOES NOT resize, recompress, regenerate mipmaps, or guess formats.
    It only accepts edited DDS files that already match the SM3 target descriptor
    and component1 payload size.
    """
    edited_dds_path=Path(edited_dds_path)
    output_dir=ensure_dir(Path(output_dir))
    info, problems = validate_dds_matches_target(edited_dds_path, target, strict=False)
    fatal=[p for p in problems if not p.lower().startswith('dds header')]
    if fatal:
        raise ValueError('Cannot normalize DDS; edited file does not match target format/data:\n- ' + '\n- '.join(fatal))
    expected_header=expected_target_dds_header(target)
    edited_payload=info['payload']
    expected_payload_size=int(target.get('component1_size') or 0)
    if len(edited_payload) != expected_payload_size:
        raise ValueError(f'Cannot normalize DDS; payload={len(edited_payload)} target={expected_payload_size}')
    out_path=output_dir/Path(edited_dds_path).name
    normalized_bytes=expected_header + edited_payload
    out_path.write_bytes(normalized_bytes)
    final_info=parse_dds_header_file(out_path)
    target_header=expected_target_dds_header(target)
    header_matches=out_path.read_bytes()[:len(target_header)] == target_header
    return out_path, {
        'source_dds':str(edited_dds_path),
        'normalized_dds':str(out_path),
        'asset':target.get('asset'),
        'hash':target.get('filename_hash'),
        'width':target.get('width'),
        'height':target.get('height'),
        'mips':target.get('mips'),
        'format':target.get('format_kind'),
        'payload_size':len(edited_payload),
        'source_header_sha256':info.get('header_sha256',''),
        'target_header_sha256':sha256_bytes(expected_header),
        'normalized_header_sha256':final_info.get('header_sha256',''),
        'source_payload_sha256':info.get('payload_sha256',''),
        'normalized_payload_sha256':final_info.get('payload_sha256',''),
        'source_header_already_game_format':info.get('header_sha256','') == sha256_bytes(expected_header),
        'normalized_header_matches_target':header_matches,
        'status':'NORMALIZED_GAME_FORMAT_DDS',
        'note':'SM3 target DDS header + edited DDS payload; no resize/recompress/mip generation was performed.',
    }


def rebuild_source_pixels_to_target_game_dds(source_path:Path, target:dict, output_dir:Path, force_opaque:bool=True):
    """v5.2.38: rebuild a GIMP/editor output from visible pixels into the SM3 target DDS shell.

    Use this when GIMP overwrote an exported DDS and changed the descriptor so much that
    header-only normalization is impossible: wrong mips, BGRA32 instead of DXT1/DXT5,
    different payload size, etc. The source file supplies pixels only. The current SM3
    target supplies width, height, mip count, DDS format, and component1 payload size.

    This DOES create/recompress a new game-format payload with the built-in encoder. It is
    safer for game loading than forcing a mismatched DDS, but it is not byte-identical to
    the editor's DDS payload. Use it for suit-edit workflow tests where the visual change
    matters more than preserving the external editor's exact DDS internals.
    """
    source_path=Path(source_path)
    output_dir=ensure_dir(Path(output_dir))
    if not HAS_PIL:
        raise ValueError('Pillow is required for editor-safe rebuild from pixels.')
    payload=encode_image_to_component1(source_path, target, force_opaque=force_opaque)
    expected_size=int(target.get('component1_size') or 0)
    if len(payload) != expected_size:
        raise ValueError(f'editor-safe rebuild payload mismatch: rebuilt={len(payload)} target={expected_size}')
    safe=clean_name(target.get('asset','texture'))
    h=str(target.get('filename_hash') or '0x00000000')
    w=int(target.get('width') or 0)
    hh=int(target.get('height') or 0)
    mips=int(target.get('mips') or 1)
    fmt=str(target.get('format_kind') or '')
    out_name=f'{h}.{safe}.GIMP_SAFE_REBUILT_TO_SM3_GAME_FORMAT.dds'
    out_path=output_dir/out_name
    out_path.write_bytes(build_dds_header(w,hh,mips,fmt,len(payload)) + payload)
    preview_path=''
    try:
        src_img=prepare_source_image_for_encoding(source_path, force_opaque=force_opaque).resize((w,hh), Image.LANCZOS)
        prev=output_dir/f'{h}.{safe}.GIMP_SAFE_REBUILT_PREVIEW.png'
        src_img.save(prev)
        preview_path=str(prev)
    except Exception:
        pass
    info=parse_dds_header_file(out_path)
    return out_path, {
        'source_file':str(source_path),
        'rebuilt_dds':str(out_path),
        'preview_png':preview_path,
        'asset':target.get('asset'),
        'hash':h,
        'target_width':w,
        'target_height':hh,
        'target_mips':mips,
        'target_format':fmt,
        'target_component1_size':expected_size,
        'rebuilt_payload_size':len(payload),
        'rebuilt_header_sha256':info.get('header_sha256',''),
        'rebuilt_payload_sha256':info.get('payload_sha256',''),
        'force_opaque_rgb':bool(force_opaque),
        'status':'GIMP_SAFE_REBUILT_TO_SM3_GAME_FORMAT',
        'note':'Source supplied pixels only; tool rebuilt SM3 target width/height/mips/format/payload. This fixes GIMP overwrite cases that cannot be header-normalized after the fact.',
    }

def find_header_lock_manifest(folder:Path):
    folder=Path(folder)
    candidates=[
        folder/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.json',
        folder/'TEX_TARGET_FORMAT_NAME_LOCK_MANIFEST.json',
    ]
    for p in candidates:
        if p.exists():
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data, dict) and isinstance(data.get('items'), list):
                    return p, data.get('items', [])
                if isinstance(data, list):
                    return p, data
            except Exception:
                pass
    csv_candidates=[
        folder/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.csv',
        folder/'TEX_TARGET_FORMAT_NAME_LOCK_MANIFEST.csv',
    ]
    for p in csv_candidates:
        if p.exists():
            try:
                with p.open(newline='',encoding='utf-8') as f:
                    return p, list(csv.DictReader(f))
            except Exception:
                pass
    return None, []

def manifest_rows_by_filename(rows:list[dict])->dict:
    out={}
    for row in rows or []:
        for key in ('dds_filename','dds_name','file','filename'):
            val=str(row.get(key,'')).strip()
            if val:
                out[Path(val).name.lower()]=row
    return out

def validate_dds_matches_target(dds_path:Path, target:dict, strict:bool=True):
    info=parse_dds_header_file(dds_path)
    expected={
        'width':int(target.get('width') or 0),
        'height':int(target.get('height') or 0),
        'mips':int(target.get('mips') or 1),
        'format_kind':str(target.get('format_kind') or '').upper(),
        'component1_size':int(target.get('component1_size') or 0),
    }
    problems=[]
    if info['width'] != expected['width']:
        problems.append(f"width DDS={info['width']} target={expected['width']}")
    if info['height'] != expected['height']:
        problems.append(f"height DDS={info['height']} target={expected['height']}")
    if info['mips'] != expected['mips']:
        problems.append(f"mips DDS={info['mips']} target={expected['mips']}")
    if info['format_kind'].upper() != expected['format_kind']:
        problems.append(f"format DDS={info['format_kind']} target={expected['format_kind']}")
    if info['payload_size'] != expected['component1_size']:
        problems.append(f"payload DDS={info['payload_size']} target={expected['component1_size']}")
    if problems and strict:
        raise ValueError('DDS does not match original SM3 TEX format:\n- ' + '\n- '.join(problems))
    return info, problems


# ============================================================
# Built-in image -> SM3 TEX component1 converter (v1.7)
# ============================================================

def clamp_u8(x):
    return 0 if x < 0 else 255 if x > 255 else int(x)

def rgb_to_565(r,g,b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def rgb_from_565(c):
    r=((c >> 11) & 31) * 255 // 31
    g=((c >> 5) & 63) * 255 // 63
    b=(c & 31) * 255 // 31
    return (r,g,b)

def color_dist2(a,b):
    dr=a[0]-b[0]; dg=a[1]-b[1]; db=a[2]-b[2]
    return dr*dr+dg*dg+db*db

def block_pixels_rgba(img, bx, by):
    w,h=img.size
    px=img.load()
    out=[]
    for y in range(4):
        sy=min(by*4+y, h-1)
        for x in range(4):
            sx=min(bx*4+x, w-1)
            out.append(px[sx,sy])
    return out

def choose_color_endpoints(pixels):
    # v1.9: choose the farthest RGB pair in the block instead of only min/max luma.
    # This keeps color variation better with the simple built-in research DXT encoder.
    rgbs=[(p[0],p[1],p[2]) for p in pixels if p[3] >= 8] or [(p[0],p[1],p[2]) for p in pixels]
    best_a=rgbs[0]; best_b=rgbs[0]; best_d=-1
    for a in rgbs:
        for b in rgbs:
            d=(a[0]-b[0])*(a[0]-b[0])+(a[1]-b[1])*(a[1]-b[1])+(a[2]-b[2])*(a[2]-b[2])
            if d > best_d:
                best_d=d; best_a=a; best_b=b
    la=best_a[0]*299+best_a[1]*587+best_a[2]*114
    lb=best_b[0]*299+best_b[1]*587+best_b[2]*114
    cmax, cmin = (best_a, best_b) if la >= lb else (best_b, best_a)
    c0=rgb_to_565(*cmax); c1=rgb_to_565(*cmin)
    if c0 < c1: c0,c1=c1,c0
    return c0,c1

def encode_dxt_color_block(pixels, force_four_color=True):
    c0,c1=choose_color_endpoints(pixels)
    r0,g0,b0=rgb_from_565(c0)
    r1,g1,b1=rgb_from_565(c1)
    palette=[(r0,g0,b0),(r1,g1,b1)]
    # Always use four-color mode for game textures unless caller deliberately changes endpoint order.
    palette.append(((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3))
    palette.append(((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3))
    bits=0
    for i,p in enumerate(pixels):
        rgb=(p[0],p[1],p[2])
        best=min(range(4), key=lambda j: color_dist2(rgb,palette[j]))
        bits |= (best & 3) << (2*i)
    return struct.pack('<HHI', c0, c1, bits)

def encode_dxt1_image(img):
    img=img.convert('RGBA')
    w,h=img.size
    out=bytearray()
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            out += encode_dxt_color_block(block_pixels_rgba(img,bx,by))
    return bytes(out)

def encode_dxt3_alpha_block(pixels):
    # 4-bit explicit alpha, 16 pixels = 64 bits.
    val=0
    for i,p in enumerate(pixels):
        a=(p[3] + 8) // 17
        val |= (a & 0xF) << (4*i)
    return struct.pack('<Q', val)

def encode_dxt3_image(img):
    img=img.convert('RGBA')
    w,h=img.size
    out=bytearray()
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            pixels=block_pixels_rgba(img,bx,by)
            out += encode_dxt3_alpha_block(pixels)
            out += encode_dxt_color_block(pixels)
    return bytes(out)

def encode_dxt5_alpha_block(pixels):
    alphas=[p[3] for p in pixels]
    a0=max(alphas); a1=min(alphas)
    if a0 == a1:
        a0=255 if a0 >= 128 else 0
        a1=0 if a0 == 255 else 255
    palette=[a0,a1]
    if a0 > a1:
        palette += [(6*a0+1*a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(1*a0+6*a1)//7]
    else:
        palette += [(4*a0+1*a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(1*a0+4*a1)//5,0,255]
    bits=0
    for i,a in enumerate(alphas):
        best=min(range(8), key=lambda j: abs(a-palette[j]))
        bits |= (best & 7) << (3*i)
    return bytes([a0 & 255, a1 & 255]) + bits.to_bytes(6,'little')

def encode_dxt5_image(img):
    img=img.convert('RGBA')
    w,h=img.size
    out=bytearray()
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            pixels=block_pixels_rgba(img,bx,by)
            out += encode_dxt5_alpha_block(pixels)
            out += encode_dxt_color_block(pixels)
    return bytes(out)

def mip_dimensions(w,h,mips):
    dims=[]
    for i in range(max(1,int(mips))):
        dims.append((max(1,w>>i), max(1,h>>i)))
    return dims


def is_diffuse_like_target(target:dict)->bool:
    name=str(target.get('asset','')).lower()
    # Good first replacement targets are color/diffuse maps. Avoid shader controls.
    return ('dif' in name or 'diff' in name or 'base' in name or 'color' in name) and not any(x in name for x in ['_nor','normal','_spe','_spx','_ppi','_ppp','_ao','_env','mask'])

def unsafe_target_reason(target:dict)->str:
    name=str(target.get('asset','')).lower()
    fmt=str(target.get('format_kind','')).upper()
    flags=[]
    if any(x in name for x in ['_nor','normal']): flags.append('normal map')
    if any(x in name for x in ['_spe','_spx','spec']): flags.append('specular/shine map')
    if any(x in name for x in ['_ppi','_ppp']): flags.append('packed shader/control map')
    if '_ao' in name or 'ambient' in name: flags.append('ambient occlusion/control map')
    if '_env' in name or 'reflect' in name: flags.append('environment/reflection map')
    if fmt in ['L8','BGRA32'] and not is_diffuse_like_target(target): flags.append(f'special numeric format {fmt}')
    if not is_diffuse_like_target(target): flags.append('not a clear diffuse/color target')
    return ', '.join(dict.fromkeys(flags))


def _decode_dxt_color_values(c0:int, c1:int, force_four:bool=False):
    a=rgb_from_565(c0); b=rgb_from_565(c1)
    if force_four or c0 > c1:
        return [a,b,((2*a[0]+b[0])//3,(2*a[1]+b[1])//3,(2*a[2]+b[2])//3),((a[0]+2*b[0])//3,(a[1]+2*b[1])//3,(a[2]+2*b[2])//3)]
    return [a,b,((a[0]+b[0])//2,(a[1]+b[1])//2,(a[2]+b[2])//2),(0,0,0)]

def _decode_dxt_color_block(block:bytes, force_four:bool=False):
    c0,c1,bits=struct.unpack_from('<HHI', block, 0)
    colors=_decode_dxt_color_values(c0,c1,force_four=force_four)
    out=[]
    for i in range(16):
        idx=(bits >> (2*i)) & 3
        r,g,b=colors[idx]
        a=255
        if (not force_four) and c0 <= c1 and idx == 3:
            a=0
        out.append((r,g,b,a))
    return out

def decode_dds_first_image_to_rgba(dds_path:Path):
    """Fallback DDS reader for first mip only. Supports DXT1/DXT3/DXT5/BGRA32/L8.

    This is used by v3.8 Target-Format Convert so a source DDS with the wrong
    size/mip/format can still provide pixels that get re-encoded into the
    currently selected SM3 target slot.
    """
    info=parse_dds_header_file(dds_path)
    w=int(info['width']); h=int(info['height']); fmt=str(info['format_kind']).upper(); payload=info['payload']
    img=Image.new('RGBA',(w,h),(0,0,0,255))
    px=img.load()
    if fmt=='BGRA32':
        need=w*h*4
        raw=payload[:need]
        return Image.frombytes('RGBA',(w,h), raw, 'raw', 'BGRA')
    if fmt=='L8':
        need=w*h
        raw=payload[:need]
        return Image.frombytes('L',(w,h), raw).convert('RGBA')
    bw=(w+3)//4; bh=(h+3)//4
    pos=0
    for by in range(bh):
        for bx in range(bw):
            if fmt=='DXT1':
                block=payload[pos:pos+8]; pos+=8
                if len(block)<8: continue
                colors=_decode_dxt_color_block(block, force_four=False)
                alphas=[c[3] for c in colors]
            elif fmt=='DXT3':
                ab=payload[pos:pos+8]; cb=payload[pos+8:pos+16]; pos+=16
                if len(ab)<8 or len(cb)<8: continue
                aval=int.from_bytes(ab,'little')
                alphas=[]
                for i in range(16):
                    a4=(aval >> (4*i)) & 0xF
                    alphas.append((a4<<4)|a4)
                colors=_decode_dxt_color_block(cb, force_four=True)
            elif fmt=='DXT5':
                ab=payload[pos:pos+8]; cb=payload[pos+8:pos+16]; pos+=16
                if len(ab)<8 or len(cb)<8: continue
                a0=ab[0]; a1=ab[1]
                atab=[a0,a1]
                if a0>a1:
                    atab += [(6*a0+1*a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(1*a0+6*a1)//7]
                else:
                    atab += [(4*a0+1*a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(1*a0+4*a1)//5,0,255]
                aval=int.from_bytes(ab[2:8],'little')
                alphas=[]
                for i in range(16):
                    alphas.append(atab[(aval >> (3*i)) & 7])
                colors=_decode_dxt_color_block(cb, force_four=True)
            else:
                raise ValueError(f'Fallback DDS reader does not support {fmt}')
            for yy in range(4):
                y=by*4+yy
                if y>=h: continue
                for xx in range(4):
                    x=bx*4+xx
                    if x>=w: continue
                    i=yy*4+xx
                    r,g,b,_=colors[i]
                    px[x,y]=(r,g,b,alphas[i])
    return img

def load_source_image_any(image_path:Path):
    image_path=Path(image_path)
    if image_path.suffix.lower()=='.dds':
        try:
            return Image.open(image_path).convert('RGBA')
        except Exception:
            return decode_dds_first_image_to_rgba(image_path)
    return Image.open(image_path).convert('RGBA')

def prepare_source_image_for_encoding(image_path:Path, force_opaque:bool=True):
    src=load_source_image_any(image_path).convert('RGBA')
    if force_opaque:
        # Drop alpha and force 255 alpha. This prevents transparent PNG alpha from
        # making the in-game texture pale/ghosted. RGB values are preserved.
        src=src.convert('RGB').convert('RGBA')
        src.putalpha(255)
    return src

def make_side_by_side_preview(original_preview:Path|None, converted_preview:Path, out_path:Path, title_left='ORIGINAL GAME PREVIEW', title_right='NEW SOURCE RESIZED'):
    if not HAS_PIL:
        return None
    try:
        right=Image.open(converted_preview).convert('RGBA')
        if original_preview and Path(original_preview).exists():
            left=Image.open(original_preview).convert('RGBA')
        else:
            left=Image.new('RGBA', right.size, (40,40,40,255))
        size=(256,256)
        left.thumbnail(size, Image.LANCZOS); right.thumbnail(size, Image.LANCZOS)
        W=size[0]*2+30; H=size[1]+44
        canvas=Image.new('RGBA',(W,H),(20,20,20,255))
        canvas.paste(left,(10,34)); canvas.paste(right,(size[0]+20,34))
        # Avoid font dependency; write only when default font works.
        try:
            from PIL import ImageDraw
            d=ImageDraw.Draw(canvas)
            d.text((10,10),title_left,fill=(255,255,255,255))
            d.text((size[0]+20,10),title_right,fill=(255,255,255,255))
        except Exception:
            pass
        out_path.parent.mkdir(parents=True,exist_ok=True)
        canvas.save(out_path)
        return out_path
    except Exception:
        return None

def make_mip_images(img, w, h, mips):
    img=img.convert('RGBA').resize((w,h), Image.LANCZOS)
    out=[]
    for mw,mh in mip_dimensions(w,h,mips):
        if img.size != (mw,mh):
            out.append(img.resize((mw,mh), Image.LANCZOS))
        else:
            out.append(img.copy())
    return out

def encode_image_to_component1(image_path:Path, target:dict, force_opaque:bool=True):
    """Convert a normal image into the exact SM3 TEX component1 payload for the selected target. v1.9 can force opaque RGB."""
    if not HAS_PIL:
        raise ValueError('Pillow is required for built-in image conversion.')
    w=int(target.get('width') or 0); h=int(target.get('height') or 0); mips=int(target.get('mips') or 1)
    fmt=str(target.get('format_kind') or '').upper()
    need=int(target.get('component1_size') or 0)
    if w<=0 or h<=0 or need<=0:
        raise ValueError('Selected TEX target is missing width/height/component1 size.')
    src=prepare_source_image_for_encoding(image_path, force_opaque=force_opaque)
    mips_imgs=make_mip_images(src,w,h,mips)
    payload=bytearray()
    if fmt == 'DXT1':
        for im in mips_imgs: payload += encode_dxt1_image(im)
    elif fmt == 'DXT3':
        for im in mips_imgs: payload += encode_dxt3_image(im)
    elif fmt == 'DXT5':
        for im in mips_imgs: payload += encode_dxt5_image(im)
    elif fmt == 'L8':
        for im in mips_imgs: payload += im.convert('L').tobytes()
    elif fmt == 'BGRA32':
        for im in mips_imgs: payload += im.tobytes('raw','BGRA')
    else:
        raise ValueError(f'Built-in image converter does not support format {fmt}. Supported: DXT1, DXT3, DXT5, L8, BGRA32.')
    if len(payload) != need:
        # v4.9 parity fix: some SM3 L8 targets include a tiny alignment/padding tail
        # after the normal mip chain. The standalone converter v1.5 proved this on
        # ch_spideyps3_tex3_ppi (128x128 L8 mips=8: 21845 -> 21848).
        # Keep the rule tight so other formats still require exact payload size.
        if fmt == 'L8' and abs(need - len(payload)) <= 16:
            if len(payload) < need:
                payload += bytes(need - len(payload))
            else:
                payload = payload[:need]
        else:
            raise ValueError(f'Converted payload size mismatch. got={len(payload)} expected={need}. Format={fmt}, dims={w}x{h}, mips={mips}.')
    return bytes(payload)

def build_dds_header(width,height,mips,fmt_kind,payload_size):
    # DDS_HEADER fields; enough for common viewers.
    flags=0x0002100F
    caps=0x1000
    if mips and mips > 1:
        flags |= 0x20000
        caps |= 0x400008
    pitch_or_linear=0
    pf_flags=0; fourcc=b'\x00\x00\x00\x00'; rgbbits=0; rmask=gmask=bmask=amask=0
    fmt=fmt_kind.upper()
    if fmt in ('DXT1','DXT2','DXT3','DXT4','DXT5'):
        pf_flags=0x4; fourcc=fmt.encode('ascii')
        pitch_or_linear=max(1,(width+3)//4)*max(1,(height+3)//4)*(8 if fmt=='DXT1' else 16)
    elif fmt=='BGRA32':
        pf_flags=0x41; rgbbits=32; rmask=0x00FF0000; gmask=0x0000FF00; bmask=0x000000FF; amask=0xFF000000
        pitch_or_linear=width*4
    elif fmt=='L8':
        pf_flags=0x20000; rgbbits=8; rmask=0xFF
        pitch_or_linear=width
    header=bytearray()
    header += b'DDS '
    header += struct.pack('<I',124)
    header += struct.pack('<I',flags)
    header += struct.pack('<I',height)
    header += struct.pack('<I',width)
    header += struct.pack('<I',pitch_or_linear)
    header += struct.pack('<I',0)  # depth
    header += struct.pack('<I',mips)
    header += bytes(44)
    header += struct.pack('<I',32)
    header += struct.pack('<I',pf_flags)
    header += fourcc
    header += struct.pack('<I',rgbbits)
    header += struct.pack('<I',rmask)
    header += struct.pack('<I',gmask)
    header += struct.pack('<I',bmask)
    header += struct.pack('<I',amask)
    header += struct.pack('<I',caps)
    header += struct.pack('<I',0)
    header += struct.pack('<I',0)
    header += struct.pack('<I',0)
    header += struct.pack('<I',0)
    return bytes(header)

def write_converted_outputs(image_path:Path, target:dict, outdir:Path, force_opaque:bool=True, original_preview_path:Path|None=None):
    outdir=ensure_dir(outdir)
    payload=encode_image_to_component1(image_path,target,force_opaque=force_opaque)
    safe=clean_name(target.get('asset','texture'))
    h=target.get('filename_hash','0x00000000')
    w=int(target.get('width') or 0); hh=int(target.get('height') or 0); mips=int(target.get('mips') or 1); fmt=str(target.get('format_kind') or '')
    base=f'{h}.{safe}.component1_{len(payload)}bytes_FROM_IMAGE'
    bin_path=outdir/(base+'.bin')
    dds_path=outdir/(base+'.dds')
    preview_path=outdir/(base+'_preview.png')
    payload_path=bin_path
    bin_path.write_bytes(payload)
    dds_path.write_bytes(build_dds_header(w,hh,mips,fmt,len(payload)) + payload)
    # Preview is source resized to target base mip. This shows what will be encoded, not a DXT roundtrip decode.
    img=prepare_source_image_for_encoding(image_path, force_opaque=force_opaque).resize((w,hh), Image.LANCZOS)
    img.save(preview_path)
    side_by_side_path=outdir/(base+'_SIDE_BY_SIDE_original_vs_new.png')
    side_by_side=make_side_by_side_preview(original_preview_path, preview_path, side_by_side_path)
    meta={
        'source_image':str(image_path),'asset':target.get('asset'),'filename_hash':h,'format_kind':fmt,
        'width':w,'height':hh,'mips':mips,'component1_size':len(payload),
        'bin':str(bin_path),'dds':str(dds_path),'preview_png':str(preview_path),'side_by_side_png':str(side_by_side) if side_by_side else '',
        'force_opaque_rgb': bool(force_opaque),
        'target_safety': 'diffuse_like' if is_diffuse_like_target(target) else ('WARNING: '+unsafe_target_reason(target)),
        'note':'PNG preview shows the source image resized to target base mip before SM3 encoding. Patch uses the component1 .bin payload.'
    }
    (outdir/(base+'_CONVERT_LOG.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return payload_path, dds_path, preview_path, meta


def make_patch_payload_from_replacement(repl:Path, target:dict, original_component1:bytes):
    """Return bytes to paste into component1, or raise ValueError."""
    repl=Path(repl)
    raw=repl.read_bytes()
    need=int(target['component1_size'])
    # Direct raw component payload.
    if len(raw)==need:
        return raw, 'RAW_EXACT_SIZE'
    # DDS payload exact-size, v2.1 validates original final format too.
    if raw.startswith(b'DDS '):
        info, problems = validate_dds_matches_target(repl, target, strict=True)
        payload = info['payload']
        return payload, 'DDS_ORIGINAL_FORMAT_VALIDATED'
    # Built-in image conversion for DXT1/DXT3/DXT5/L8/BGRA32 with mip-chain generation.
    # WARNING: this is experimental. Use Export Original DDS -> edit DDS -> Patch COPY with ORIGINAL-FORMAT DDS for the clean route.
    if repl.suffix.lower() in ('.png','.bmp','.jpg','.jpeg'):
        payload=encode_image_to_component1(repl,target,force_opaque=True)
        if len(payload)==need:
            return payload, 'IMAGE_CONVERTED_TO_'+str(target.get('format_kind'))
        raise ValueError(f'Converted image payload size does not match component1. converted={len(payload)} target={need}.')
    raise ValueError(f'Replacement is {len(raw)} bytes but target component1 is {need} bytes. Use exact-size raw component1 or DDS with exact payload size.')


def copy_and_patch_pcpack(original:Path, target:dict, replacement:Path, output_path:Path):
    data=bytearray(original.read_bytes())
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
    original_component1=bytes(data[s:e])
    payload,mode=make_patch_payload_from_replacement(replacement,target,original_component1)
    if len(payload)!=need:
        raise ValueError(f'Internal size mismatch. payload={len(payload)} target={need}')
    data[s:e]=payload
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    log={
        'original_pcpack':str(original),'patched_pcpack':str(output_path),'replacement':str(replacement),'replacement_mode':mode,
        'asset':target.get('asset'),'filename_hash':target.get('filename_hash'),'component':'component1',
        'offset_start_hex':hex(s),'offset_end_hex':hex(e),'size':need,
        'safety':'original file was not modified; exact same-size component1 paste into new copy only'
    }
    (output_path.parent/(output_path.stem+'_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_PATCH_LOG.txt')).write_text('\n'.join(f'{k}: {v}' for k,v in log.items()),encoding='utf-8')
    return log



def copy_and_patch_pcpack_convert_source_to_target(original:Path, target:dict, source_path:Path, output_path:Path, force_opaque:bool=True):
    """v3.8: Convert a chosen DDS/image into the CURRENTLY SELECTED target format.

    This fixes the common workflow bug where the user wants to paste/use a 64x64 DXT1
    source over a 128x128 DXT1 no-mip target or a DXT1 source over a DXT5 target.
    The source file supplies pixels only; the selected target supplies width/height,
    format, mip count, and final component1 size.
    """
    payload=encode_image_to_component1(source_path, target, force_opaque=force_opaque)
    data=bytearray(original.read_bytes())
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
    if len(payload)!=need:
        raise ValueError(f'Converted payload size mismatch. converted={len(payload)} target={need}')
    original_component1=bytes(data[s:e])
    data[s:e]=payload
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    # Write a converted DDS next to the patched PCPACK so the user can inspect what was inserted.
    w=int(target.get('width') or 0); h=int(target.get('height') or 0); mips=int(target.get('mips') or 1); fmt=str(target.get('format_kind') or '')
    converted_dds=output_path.parent/(output_path.stem+'_CONVERTED_TO_SELECTED_TARGET.dds')
    converted_dds.write_bytes(build_dds_header(w,h,mips,fmt,len(payload))+payload)
    preview_png=''
    try:
        if HAS_PIL:
            prev=output_path.parent/(output_path.stem+'_CONVERTED_TO_SELECTED_TARGET_PREVIEW.png')
            prepare_source_image_for_encoding(source_path, force_opaque=force_opaque).resize((w,h), Image.LANCZOS).save(prev)
            preview_png=str(prev)
    except Exception:
        pass
    log={
        'mode':'V3_8_TARGET_FORMAT_CONVERT_PATCH',
        'original_pcpack':str(original),'patched_pcpack':str(output_path),'source_file':str(source_path),
        'asset':target.get('asset'),'filename_hash':target.get('filename_hash'),'component':'component1',
        'target_width':w,'target_height':h,'target_format':fmt,'target_mips':mips,
        'target_component1_size':need,'converted_payload_size':len(payload),
        'offset_start_hex':hex(s),'offset_end_hex':hex(e),
        'converted_dds':str(converted_dds),'converted_preview_png':preview_png,
        'same_as_original': bool(payload==original_component1),
        'safety':'source pixels were converted into the selected target format; original PCPACK was not modified'
    }
    (output_path.parent/(output_path.stem+'_TARGET_FORMAT_CONVERT_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    return log

def copy_and_patch_pcpack_original_format_dds(original:Path, target:dict, dds_path:Path, output_path:Path):
    """Patch a NEW PCPACK copy using a DDS that exactly matches original TEX descriptor."""
    info, problems = validate_dds_matches_target(dds_path, target, strict=True)
    data=bytearray(original.read_bytes())
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
    payload=info['payload']
    if len(payload) != need:
        raise ValueError(f'Internal DDS payload size mismatch after validation. payload={len(payload)} target={need}')
    original_component1=bytes(data[s:e])
    same_as_original=(payload == original_component1)
    data[s:e]=payload
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    log={
        'original_pcpack':str(original),'patched_pcpack':str(output_path),'replacement_dds':str(dds_path),
        'replacement_mode':'DDS_ORIGINAL_FORMAT_VALIDATED_V2_0',
        'asset':target.get('asset'),'filename_hash':target.get('filename_hash'),'component':'component1',
        'offset_start_hex':hex(s),'offset_end_hex':hex(e),'size':need,
        'dds_width':info['width'],'dds_height':info['height'],'dds_mips':info['mips'],'dds_format_kind':info['format_kind'],
        'same_payload_as_original':same_as_original,
        'safety':'original file was not modified; DDS had to match target width/height/mips/format/payload before patching'
    }
    (output_path.parent/(output_path.stem+'_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_PATCH_LOG.txt')).write_text('\n'.join(f'{k}: {v}' for k,v in log.items()),encoding='utf-8')
    return log




def copy_and_patch_pcpack_original_format_dds_many(original:Path, patch_items:list[tuple[dict, Path]], output_path:Path):
    """Patch multiple selected TEX component1 payloads into ONE new PCPACK copy.

    Each replacement must be an original-format DDS that exactly matches its selected
    target's width, height, mip count, format, and component1 payload size.
    """
    if not patch_items:
        raise ValueError('No patch items were provided.')
    data=bytearray(Path(original).read_bytes())
    rows=[]
    used_ranges=[]
    for target, dds_path in patch_items:
        info, problems = validate_dds_matches_target(Path(dds_path), target, strict=True)
        s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
        payload=info['payload']
        if len(payload) != need:
            raise ValueError(f"{target.get('asset')}: DDS payload size mismatch after validation. payload={len(payload)} target={need}")
        for os_, oe_, oname in used_ranges:
            if not (e <= os_ or s >= oe_):
                raise ValueError(f"Patch ranges overlap: {target.get('asset')} overlaps {oname}")
        original_component1=bytes(data[s:e])
        data[s:e]=payload
        used_ranges.append((s,e,str(target.get('asset'))))
        rows.append({
            'asset':target.get('asset'),
            'filename_hash':target.get('filename_hash'),
            'replacement_dds':str(dds_path),
            'offset_start_hex':hex(s),'offset_end_hex':hex(e),'size':need,
            'dds_width':info['width'],'dds_height':info['height'],'dds_mips':info['mips'],'dds_format_kind':info['format_kind'],
            'same_payload_as_original':payload == original_component1,
            'status':'PATCHED'
        })
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    log={
        'mode':'BATCH_DDS_ORIGINAL_FORMAT_VALIDATED_V2_5',
        'original_pcpack':str(original),
        'patched_pcpack':str(output_path),
        'patch_count':len(rows),
        'safety':'original PCPACK was not modified; every DDS had to match its selected texture descriptor before patching; all selected edits were written into one new PCPACK copy',
        'items':rows,
    }
    (output_path.parent/(output_path.stem+'_BATCH_DDS_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_BATCH_DDS_PATCH_LOG.txt')).write_text('\n'.join([f"{k}: {v}" for k,v in log.items() if k!='items'])+'\n\nITEMS:\n'+'\n'.join(f"{r['asset']} <- {r['replacement_dds']} @ {r['offset_start_hex']}-{r['offset_end_hex']}" for r in rows),encoding='utf-8')
    write_csv(output_path.parent/(output_path.stem+'_BATCH_DDS_PATCH_ITEMS.csv'), rows)
    return log


def copy_and_patch_pcpack_header_locked_dds_many(original:Path, patch_items:list[tuple[dict, Path, dict]], output_path:Path):
    """Patch multiple DDS files into one new PCPACK with exact name/format/header lock.

    This is stricter than the older exact DDS route: DDS header bytes must match
    the target/export header exactly, so the reimport follows the same header the
    game/tool expects instead of only matching descriptor fields.
    """
    if not patch_items:
        raise ValueError('No header-locked patch items were provided.')
    data=bytearray(Path(original).read_bytes())
    rows=[]
    used_ranges=[]
    for target, dds_path, manifest_row in patch_items:
        dds_path=Path(dds_path)
        info, problems = validate_dds_matches_target_header_locked(dds_path, target, strict=True)
        s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
        payload=info['payload']
        if len(payload) != need:
            raise ValueError(f"{target.get('asset')}: DDS payload size mismatch after header lock. payload={len(payload)} target={need}")
        for os_, oe_, oname in used_ranges:
            if not (e <= os_ or s >= oe_):
                raise ValueError(f"Patch ranges overlap: {target.get('asset')} overlaps {oname}")
        original_component1=bytes(data[s:e])
        data[s:e]=payload
        used_ranges.append((s,e,str(target.get('asset'))))
        rows.append({
            'asset':target.get('asset'),
            'filename_hash':target.get('filename_hash'),
            'replacement_dds':str(dds_path),
            'offset_start_hex':hex(s),'offset_end_hex':hex(e),'size':need,
            'dds_width':info['width'],'dds_height':info['height'],'dds_mips':info['mips'],'dds_format_kind':info['format_kind'],
            'header_sha256':info.get('header_sha256',''),
            'expected_header_sha256':info.get('expected_header_sha256',''),
            'header_matches_target':info.get('actual_header_matches_expected'),
            'same_payload_as_original':payload == original_component1,
            'manifest_header_sha256':manifest_row.get('original_dds_header_sha256','') if isinstance(manifest_row,dict) else '',
            'status':'PATCHED_HEADER_NAME_LOCKED'
        })
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    log={
        'mode':'HEADER_NAME_LOCKED_DDS_REIMPORT_V5_2_33',
        'original_pcpack':str(original),
        'patched_pcpack':str(output_path),
        'patch_count':len(rows),
        'safety':'every DDS had to match target filename/hash, width, height, mip count, format, payload size, and exact DDS header bytes; original PCPACK was not modified',
        'items':rows,
    }
    (output_path.parent/(output_path.stem+'_HEADER_NAME_LOCKED_REIMPORT_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_HEADER_NAME_LOCKED_REIMPORT_LOG.txt')).write_text('\n'.join([f"{k}: {v}" for k,v in log.items() if k!='items'])+'\n\nITEMS:\n'+'\n'.join(f"{r['asset']} <- {Path(r['replacement_dds']).name} header={r['header_matches_target']} @ {r['offset_start_hex']}-{r['offset_end_hex']}" for r in rows),encoding='utf-8')
    write_csv(output_path.parent/(output_path.stem+'_HEADER_NAME_LOCKED_REIMPORT_ITEMS.csv'), rows)
    return log

def export_original_component_as_dds(original:Path, target:dict, outdir:Path):
    data=original.read_bytes()
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec'])
    payload=data[s:e]
    w=int(target.get('width') or 0); h=int(target.get('height') or 0); mips=int(target.get('mips') or 1); fmt=str(target.get('format_kind') or '')
    safe=clean_name(target.get('asset','texture'))
    hashv=target.get('filename_hash','0x00000000')
    outdir=ensure_dir(outdir)
    dds=outdir/f'{hashv}.{safe}.ORIGINAL_EDIT_THIS.dds'
    raw=outdir/f'{hashv}.{safe}.ORIGINAL_component1_{len(payload)}bytes.bin'
    raw.write_bytes(payload)
    dds_header=build_dds_header(w,h,mips,fmt,len(payload))
    dds_bytes=dds_header+payload
    dds.write_bytes(dds_bytes)
    meta={'asset':target.get('asset'),'hash':hashv,'format':fmt,'width':w,'height':h,'mips':mips,'component1_size':len(payload),'dds':str(dds),'raw':str(raw),'target_key':target_edit_key(target),'original_dds_sha256':sha256_bytes(dds_bytes),'original_dds_header_sha256':sha256_bytes(dds_header),'original_dds_header_size':len(dds_header),'original_component1_sha256':sha256_bytes(payload),'note':'v5.2.33 header-locked route: edit this DDS externally but keep the same filename, same DDS header, same width/height/mips/format, and same payload size before target-locked reimport.'}
    (outdir/f'{hashv}.{safe}.DDS_EXPORT_LOG.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    try:
        sidecar,index=write_dds_edit_session_files(dds,raw,meta)
        meta['sidecar']=str(sidecar); meta['session_index']=str(index)
    except Exception:
        pass
    return dds, raw, meta



def copy_and_patch_pcpack_smart_mixed_many(original:Path, smart_items:list[dict], output_path:Path, force_opaque:bool=True):
    """v4.4: Patch exact DDS items and convert wrong-mip/format DDS/images into target format.

    smart_items rows:
      {'target': target_dict, 'path': Path, 'mode': 'EXACT'|'CONVERT', 'reason': str}
    """
    if not smart_items:
        raise ValueError('No smart reimport items were provided.')
    data=bytearray(Path(original).read_bytes())
    rows=[]
    used_ranges=[]
    for item in smart_items:
        target=item['target']
        source=Path(item['path'])
        mode=str(item.get('mode','')).upper()
        s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
        for os_, oe_, oname in used_ranges:
            if not (e <= os_ or s >= oe_):
                raise ValueError(f"Patch ranges overlap: {target.get('asset')} overlaps {oname}")
        original_component1=bytes(data[s:e])
        if mode == 'EXACT':
            info, problems = validate_dds_matches_target(source, target, strict=True)
            payload=info['payload']
            patch_mode='EXACT_ORIGINAL_FORMAT_DDS'
        elif mode == 'CONVERT':
            payload=encode_image_to_component1(source, target, force_opaque=force_opaque)
            patch_mode='CONVERTED_TO_SELECTED_TARGET_FORMAT'
        else:
            raise ValueError(f"Unknown smart reimport mode {mode} for {source}")
        if len(payload) != need:
            raise ValueError(f"{target.get('asset')}: payload size mismatch after {mode}. payload={len(payload)} target={need}")
        data[s:e]=payload
        used_ranges.append((s,e,str(target.get('asset'))))
        rows.append({
            'asset':target.get('asset'),
            'filename_hash':target.get('filename_hash'),
            'replacement':str(source),
            'patch_mode':patch_mode,
            'match_reason':item.get('reason',''),
            'offset_start_hex':hex(s),
            'offset_end_hex':hex(e),
            'size':need,
            'target_width':target.get('width'),
            'target_height':target.get('height'),
            'target_mips':target.get('mips'),
            'target_format_kind':target.get('format_kind'),
            'same_payload_as_original':payload == original_component1,
            'status':'PATCHED'
        })
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    log={
        'mode':'SMART_MIPMAP_REIMPORT_V4_4',
        'original_pcpack':str(original),
        'patched_pcpack':str(output_path),
        'patch_count':len(rows),
        'exact_count':sum(1 for r in rows if r['patch_mode']=='EXACT_ORIGINAL_FORMAT_DDS'),
        'convert_count':sum(1 for r in rows if r['patch_mode']=='CONVERTED_TO_SELECTED_TARGET_FORMAT'),
        'safety':'original PCPACK was not modified; exact items validated, convert items rebuilt to selected target width/height/format/mip/payload',
        'items':rows,
    }
    (output_path.parent/(output_path.stem+'_SMART_REIMPORT_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    write_csv(output_path.parent/(output_path.stem+'_SMART_REIMPORT_ITEMS.csv'), rows)
    return log



def _normalize_export_asset_name_from_path(path:Path)->str:
    """Return a likely SM3 asset token from an exported/converter filename.

    Handles names like:
      0xHASH.asset.ORIGINAL_EDIT_THIS.dds
      0xHASH.asset.dds
      0xHASH.asset.CONVERT_FROM_ID.runtime.dds
    """
    stem=Path(path).stem
    # Remove common export/converter suffixes. Keep the left side asset name.
    for marker in ('.ORIGINAL_EDIT_THIS', '.original_edit_this', '.CONVERT_FROM_ID', '.convert_from_id', '.CONVERTED_FROM', '.converted_from'):
        idx=stem.lower().find(marker.lower())
        if idx >= 0:
            stem=stem[:idx]
            break
    m=re.match(r'(?i)^(0x[0-9a-f]{8})[._-](.+)$', stem)
    if m:
        return m.group(2).strip().lower()
    return stem.strip().lower()

def _filename_direct_target_match(source_path:Path, targets:list[dict]):
    """Name-locked match used by v5.0 folder reimport.

    If the file name contains a real SM3 target hash or exact asset name, return
    that target immediately. This prevents folder reimport from treating exported
    ORIGINAL_EDIT_THIS files as ambiguous just because several targets share the
    same descriptor/size/format.
    """
    name=Path(source_path).name.lower()
    hashes=re.findall(r'0x[0-9a-f]{8}', name)
    if hashes:
        by_hash={}
        for t in targets:
            h=str(t.get('filename_hash','')).lower()
            if h:
                by_hash[h]=t
        # Prefer the first hash in the filename.
        for h in hashes:
            if h in by_hash:
                return by_hash[h], 'FILENAME_HASH_EXACT_LOCK'
    asset_token=_normalize_export_asset_name_from_path(Path(source_path))
    if asset_token:
        exact=[t for t in targets if str(t.get('asset','')).lower()==asset_token]
        if len(exact)==1:
            return exact[0], 'FILENAME_ASSET_EXACT_LOCK'
    return None, ''

def target_edit_key(target:dict)->str:
    """Stable key for remembering which original DDS belongs to which selected TEX target."""
    return '|'.join([
        str(target.get('filename_hash','')),
        str(target.get('asset','')),
        str(target.get('format_kind','')),
        str(target.get('width','')),
        str(target.get('height','')),
        str(target.get('mips','')),
        str(target.get('component1_size','')),
    ])


def sha256_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(path:Path)->str:
    try:
        return str(Path(path).resolve())
    except Exception:
        return str(path)


def write_dds_edit_session_files(dds:Path, raw:Path, meta:dict):
    """Write sidecar/session hints so the tool can auto-detect the edited DDS later."""
    dds=Path(dds); raw=Path(raw)
    meta=dict(meta)
    meta['sidecar_version']='SM3_DDS_EDIT_SESSION_v2_4'
    meta['target_key']=meta.get('target_key') or '|'.join([
        str(meta.get('hash','')), str(meta.get('asset','')), str(meta.get('format','')),
        str(meta.get('width','')), str(meta.get('height','')), str(meta.get('mips','')), str(meta.get('component1_size',''))
    ])
    meta['original_dds_path']=safe_rel(dds)
    meta['original_raw_path']=safe_rel(raw)
    meta['original_dds_sha256']=sha256_file(dds) if dds.exists() else ''
    try:
        _info=parse_dds_header_file(dds)
        _raw=Path(dds).read_bytes()
        meta['original_dds_header_sha256']=sha256_bytes(_raw[:_info['header_size']])
        meta['original_dds_header_size']=_info['header_size']
    except Exception:
        meta.setdefault('original_dds_header_sha256','')
        meta.setdefault('original_dds_header_size','')
    meta['note']='Edit/overwrite the DDS in Paint.NET or GIMP, then use the editor-safe final reimport. The final route validates filename/target and can patch direct, normalize header-only changes, or rebuild visible pixels into the SM3 target DDS format when the editor rewrites the DDS.'
    sidecar=dds.with_suffix(dds.suffix+'.sm3edit.json')
    sidecar.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    index=dds.parent/'SM3_DDS_EDIT_SESSION_INDEX.json'
    sessions=[]
    if index.exists():
        try:
            old=json.loads(index.read_text(encoding='utf-8'))
            if isinstance(old,dict): sessions=old.get('sessions',[])
            elif isinstance(old,list): sessions=old
        except Exception:
            sessions=[]
    sessions=[s for s in sessions if s.get('target_key')!=meta['target_key']]
    sessions.append(meta)
    index.write_text(json.dumps({'version':'SM3_DDS_EDIT_SESSION_INDEX_v2_4','sessions':sessions},indent=2),encoding='utf-8')
    return sidecar, index


def _dxt_block_size(fmt_kind:str)->int:
    fmt=(fmt_kind or '').upper()
    if fmt == 'DXT1': return 8
    if fmt in ('DXT3','DXT5'): return 16
    return 0

def _mip_byte_size(fmt_kind:str, w:int, h:int)->int:
    fmt=(fmt_kind or '').upper()
    if fmt in ('DXT1','DXT3','DXT5'):
        return max(1,(w+3)//4) * max(1,(h+3)//4) * _dxt_block_size(fmt)
    if fmt == 'BGRA32':
        return max(1,w) * max(1,h) * 4
    if fmt == 'L8':
        return max(1,w) * max(1,h)
    return 0

def _tint_565_red(c:int)->int:
    # Keep the block's index data and alpha untouched, but push the color endpoints red.
    r=(c>>11)&31; g=(c>>5)&63; b=c&31
    r=min(31, max(8, int(r*1.25)+6))
    g=max(0, int(g*0.45))
    b=max(0, int(b*0.45))
    return (r<<11)|(g<<5)|b

def _edit_payload_red_tint(payload:bytes, target:dict)->bytes:
    """Make a visible edited-DDS control while preserving original DDS format/size/mips.

    This is NOT the old PNG converter. It edits the original compressed/raw payload in-place:
    - DXT1/DXT3/DXT5: changes only color endpoint words in each block; keeps alpha and index bits.
    - L8: brightens/inverts luminance in a mild checker pattern.
    - BGRA32: boosts red channel and lowers blue/green slightly.
    """
    fmt=str(target.get('format_kind') or '').upper()
    w=int(target.get('width') or 0); h=int(target.get('height') or 0); mips=int(target.get('mips') or 1)
    out=bytearray(payload)
    pos=0
    for mw,mh in mip_dimensions(w,h,mips):
        sz=_mip_byte_size(fmt,mw,mh)
        if sz <= 0 or pos+sz > len(out):
            break
        if fmt in ('DXT1','DXT3','DXT5'):
            bs=_dxt_block_size(fmt)
            color_off=0 if fmt=='DXT1' else 8
            for bo in range(pos, pos+sz, bs):
                if bo+color_off+4 <= len(out):
                    c0=struct.unpack_from('<H', out, bo+color_off)[0]
                    c1=struct.unpack_from('<H', out, bo+color_off+2)[0]
                    struct.pack_into('<H', out, bo+color_off, _tint_565_red(c0))
                    struct.pack_into('<H', out, bo+color_off+2, _tint_565_red(c1))
        elif fmt == 'L8':
            for i in range(pos, pos+sz):
                v=out[i]
                out[i]=clamp_u8(255-v if ((i-pos)//16)%2 else min(255, v+64))
        elif fmt == 'BGRA32':
            for i in range(pos, pos+sz, 4):
                if i+3 < len(out):
                    b,g,r,a=out[i],out[i+1],out[i+2],out[i+3]
                    out[i]=clamp_u8(b*0.45)
                    out[i+1]=clamp_u8(g*0.55)
                    out[i+2]=clamp_u8(max(r, 160))
                    out[i+3]=a
        pos += sz
    return bytes(out)

def export_test_edited_dds_from_original(original:Path, target:dict, outdir:Path):
    """Export original DDS plus a same-format edited DDS test file."""
    original=Path(original); outdir=ensure_dir(Path(outdir))
    data=original.read_bytes()
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec'])
    payload=data[s:e]
    w=int(target.get('width') or 0); h=int(target.get('height') or 0); mips=int(target.get('mips') or 1); fmt=str(target.get('format_kind') or '')
    safe=clean_name(target.get('asset','texture'))
    hashv=target.get('filename_hash','0x00000000')
    header=build_dds_header(w,h,mips,fmt,len(payload))
    original_dds=outdir/f'{hashv}.{safe}.ORIGINAL_EDIT_THIS.dds'
    edited_dds=outdir/f'{hashv}.{safe}.EDITED_DDS_TEST_RED_TINT.dds'
    original_dds.write_bytes(header+payload)
    edited_payload=_edit_payload_red_tint(payload,target)
    edited_dds.write_bytes(header+edited_payload)
    info, problems=validate_dds_matches_target(edited_dds,target,strict=True)
    log={
        'asset':target.get('asset'), 'hash':hashv, 'format':fmt, 'width':w, 'height':h, 'mips':mips,
        'component1_size':len(payload), 'original_dds':str(original_dds), 'edited_dds':str(edited_dds),
        'edited_payload_same_size':len(edited_payload)==len(payload),
        'edited_payload_differs_from_original':edited_payload != payload,
        'validation':'passed original DDS format/size checks',
        'note':'This edited DDS test preserves the original DDS header/format/mips/payload size. It only changes compressed/raw color data, so it is a safer test than PNG conversion.'
    }
    (outdir/f'{hashv}.{safe}.EDITED_DDS_TEST_LOG.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
    return original_dds, edited_dds, log

def export_test_edited_dds_and_patch(original:Path, target:dict, outdir:Path, output_pcpack:Path):
    original_dds, edited_dds, log = export_test_edited_dds_from_original(original,target,outdir)
    patch_log = copy_and_patch_pcpack_original_format_dds(original,target,edited_dds,output_pcpack)
    combo={'edited_dds_log':log,'patch_log':patch_log}
    (Path(output_pcpack).parent/(Path(output_pcpack).stem+'_EDITED_DDS_TEST_AND_PATCH_LOG.json')).write_text(json.dumps(combo,indent=2),encoding='utf-8')
    return combo


def collect_preview_images(output_root:Path):
    output_root=Path(output_root)
    items=[]
    for folder in ['OPEN_FIRST_PNGS','BEST_VISUAL_PREVIEWS','PNG_PREVIEWS','RESEARCH_VARIANTS']:
        d=output_root/folder
        if not d.exists(): continue
        for p in d.rglob('*'):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                items.append(p)
    items.sort(key=lambda p: (0 if 'OPEN_FIRST' in str(p) else 1 if 'BEST_VISUAL' in str(p) else 2, p.name.lower()))
    return items


# v4.8: sha256_bytes is defined once above and always returns lowercase hex for consistent logs.

def copy_and_patch_pcpack_with_original_component(original:Path, target:dict, output_path:Path):
    """Patch a NEW copy using the exact original component1 bytes from the source pack."""
    data=bytearray(original.read_bytes())
    original_sha=sha256_bytes(bytes(data))
    s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec']); need=e-s
    original_component1=bytes(data[s:e])
    data[s:e]=original_component1
    output_path=Path(output_path)
    output_path.write_bytes(data)
    patched_sha=sha256_bytes(bytes(data))
    log={
        'mode':'ORIGINAL_COMPONENT1_SELF_REPLACE_SELECTED',
        'original_pack':str(original),
        'output_pack':str(output_path),
        'original_sha256':original_sha,
        'patched_sha256':patched_sha,
        'byte_identical_expected': True,
        'byte_identical_actual': original_sha == patched_sha,
        'asset':target.get('asset'),
        'filename_hash':target.get('filename_hash'),
        'component':'component1',
        'offset_start':hex(s),'offset_end':hex(e),'size':need,
        'meaning':'This should create a byte-identical copy. If this copy looks wrong in-game, you are probably testing the wrong pack/file path or the game is using cached/different data. If this copy looks normal but converted-image patches look pale/white, the issue is converter/alpha/channel/target selection.'
    }
    (output_path.parent/(output_path.stem+'_ORIGINAL_SELF_REPLACE_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_ORIGINAL_SELF_REPLACE_LOG.txt')).write_text('\n'.join(f'{k}: {v}' for k,v in log.items()),encoding='utf-8')
    return log

def make_full_original_texture_selftest_copy(original:Path, targets:list[dict], output_path:Path):
    """Write every TEX component1 back over itself into a NEW copy and verify SHA stays identical."""
    data=bytearray(original.read_bytes())
    original_sha=sha256_bytes(bytes(data))
    rows=[]
    for t in targets:
        try:
            s=int(t['component1_absolute_start_dec']); e=int(t['component1_absolute_end_dec'])
            if not (0 <= s <= e <= len(data)):
                rows.append({'asset':t.get('asset'),'filename_hash':t.get('filename_hash'),'status':'BAD_OFFSET','start':s,'end':e})
                continue
            payload=bytes(data[s:e])
            data[s:e]=payload
            rows.append({'asset':t.get('asset'),'filename_hash':t.get('filename_hash'),'format_kind':t.get('format_kind'),'component1_size':e-s,'start_hex':hex(s),'end_hex':hex(e),'status':'SELF_REPLACED_ORIGINAL_BYTES'})
        except Exception as exc:
            rows.append({'asset':t.get('asset'),'filename_hash':t.get('filename_hash'),'status':'ERROR','error':str(exc)})
    output_path=Path(output_path)
    output_path.write_bytes(data)
    patched_sha=sha256_bytes(bytes(data))
    log={
        'mode':'FULL_ORIGINAL_TEXTURE_SELF_REPLACE_ALL_TEX_COMPONENT1',
        'original_pack':str(original),
        'output_pack':str(output_path),
        'targets_processed':len(targets),
        'original_sha256':original_sha,
        'patched_sha256':patched_sha,
        'byte_identical_expected': True,
        'byte_identical_actual': original_sha == patched_sha,
        'meaning':'This patches every detected TEX component1 using the exact original bytes. A byte-identical result proves the patch writer/offsets did not alter the pack. Use this as the control test before blaming the extractor or repacker.'
    }
    log_json=output_path.parent/(output_path.stem+'_FULL_ORIGINAL_SELF_TEST_LOG.json')
    log_txt=output_path.parent/(output_path.stem+'_FULL_ORIGINAL_SELF_TEST_LOG.txt')
    csv_path=output_path.parent/(output_path.stem+'_FULL_ORIGINAL_SELF_TEST_TARGETS.csv')
    log_json.write_text(json.dumps(log,indent=2),encoding='utf-8')
    log_txt.write_text('\n'.join(f'{k}: {v}' for k,v in log.items()),encoding='utf-8')
    write_csv(csv_path, rows)
    return log


def restore_all_tex_from_clean_original_pack(edited_or_bad_pack:Path, clean_original_pack:Path, targets:list[dict], output_path:Path, restore_component0:bool=True):
    """Create a NEW PCPACK copy from edited_or_bad_pack, restoring every detected TEX component from a clean original pack.

    This is for the case where a converted/custom texture made the suit white/pale. It does not rebuild the pack;
    it copies original TEX bytes back into the exact same offsets from a clean untouched pack.
    """
    edited_or_bad_pack=Path(edited_or_bad_pack)
    clean_original_pack=Path(clean_original_pack)
    output_path=Path(output_path)
    bad=bytearray(edited_or_bad_pack.read_bytes())
    clean=clean_original_pack.read_bytes()
    if len(bad) != len(clean):
        raise ValueError(f'Pack sizes do not match. Edited/bad={len(bad)} clean original={len(clean)}. Restore requires same-size pack copies.')
    before_sha=sha256_bytes(bytes(bad))
    clean_sha=sha256_bytes(clean)
    rows=[]
    restored_c0=0; restored_c1=0; changed_before=0
    for t in targets:
        asset=t.get('asset') or ''
        h=t.get('filename_hash') or ''
        for comp in (['component0','component1'] if restore_component0 else ['component1']):
            try:
                s=int(t[f'{comp}_absolute_start_dec']); e=int(t[f'{comp}_absolute_end_dec'])
                if not (0 <= s <= e <= len(bad)):
                    rows.append({'asset':asset,'filename_hash':h,'component':comp,'status':'BAD_OFFSET','start':s,'end':e})
                    continue
                old=bytes(bad[s:e]); orig=clean[s:e]
                was_different=(old != orig)
                if was_different: changed_before += 1
                bad[s:e]=orig
                if comp=='component0': restored_c0 += 1
                else: restored_c1 += 1
                rows.append({
                    'asset':asset,'filename_hash':h,'component':comp,
                    'offset_start_hex':hex(s),'offset_end_hex':hex(e),'size':e-s,
                    'was_different_before_restore':was_different,
                    'status':'RESTORED_FROM_CLEAN_ORIGINAL'
                })
            except Exception as exc:
                rows.append({'asset':asset,'filename_hash':h,'component':comp,'status':'ERROR','error':str(exc)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bad)
    after_sha=sha256_bytes(bytes(bad))
    byte_identical_to_clean=(after_sha == clean_sha)
    log={
        'mode':'RESTORE_ALL_DETECTED_TEX_FROM_CLEAN_ORIGINAL',
        'edited_or_bad_input_pack':str(edited_or_bad_pack),
        'clean_original_source_pack':str(clean_original_pack),
        'output_restored_pack':str(output_path),
        'targets_processed':len(targets),
        'restore_component0':bool(restore_component0),
        'restored_component0_count':restored_c0,
        'restored_component1_count':restored_c1,
        'components_that_were_different_before_restore':changed_before,
        'bad_input_sha256_before':before_sha,
        'clean_original_sha256':clean_sha,
        'restored_output_sha256':after_sha,
        'restored_output_byte_identical_to_clean_original':byte_identical_to_clean,
        'meaning':'If output is byte-identical to clean original, every byte matches. If false, non-TEX bytes still differ, but all detected TEX component0/component1 bytes were restored from the clean pack.'
    }
    (output_path.parent/(output_path.stem+'_RESTORE_ALL_TEX_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
    (output_path.parent/(output_path.stem+'_RESTORE_ALL_TEX_LOG.txt')).write_text('\n'.join(f'{k}: {v}' for k,v in log.items()),encoding='utf-8')
    write_csv(output_path.parent/(output_path.stem+'_RESTORE_ALL_TEX_COMPONENTS.csv'), rows)
    return log


class TexSwapperTab(ttk.Frame):
    def __init__(self, parent, app_state=None):
        super().__init__(parent)
        self.app_state = app_state
        self.root = self
        self.pcpack_var=tk.StringVar()
        self.output_var=tk.StringVar(value="")
        self.replacement_folder_var=tk.StringVar()
        self.search_var=tk.StringVar()
        self.force_opaque_var=tk.BooleanVar(value=True)
        self.diffuse_safe_var=tk.BooleanVar(value=True)
        self.strict_diffuse_var=tk.BooleanVar(value=False)
        self.status_var=tk.StringVar(value=f'Ready. {APP_NAME} by {APP_AUTHOR}. Exact-format DDS only; black/white previews mean format review.')
        self.selected_target_var=tk.StringVar(value='Selected texture: none')
        self.targets=[]; self.filtered=[]; self.images=[]; self.selected_target=None; self.selected_image=None
        self.img_ref=None
        self.dark_mode=True
        self.dds_export_history={}  # target_key -> export metadata from this session
        self.last_export_dir=None
        self.native_tex_folder_var=tk.StringVar(value='')
        self.native_tex_browser_records=[]
        self.native_tex_browser_photo=None
        self.native_tex_browser_selected=None
        self.native_tex_browser_search_var=tk.StringVar(value='')
        self.native_tex_selected_target_var=tk.StringVar(value='Selected classic TEX target: none')
        self.style=ttk.Style()
        self._theme_widgets=[]
        self.build_ui()
        if self.app_state is not None:
            try:
                self.app_state.on_theme_change(lambda _theme: self.apply_theme())
            except Exception:
                self.apply_theme()
        else:
            self.apply_theme()

    def apply_theme(self, dark=True):
        """Apply the global Toolkit theme to the Tex Swapper tab."""
        # v5.2.103: Tex Swapper no longer keeps a separate local dark/light palette.
        # It follows the global Theme selector so the logo/header/buttons do not split colors.
        bg = COLORS.get('bg', '#171717')
        panel = COLORS.get('panel', '#202020')
        panel2 = COLORS.get('panel2', panel)
        fg = COLORS.get('fg', '#F2F2F2')
        muted = COLORS.get('muted', '#BDBDBD')
        entry = COLORS.get('field', '#2B2B2B')
        accent = COLORS.get('accent', '#3A78D8')
        select = COLORS.get('select', '#404B64')
        header_bg = COLORS.get('header', bg)
        brand_fg = COLORS.get('brand', fg)
        byline_fg = COLORS.get('byline', muted)
        self.dark_mode = (bg.lower() not in ('#f2f2f2', '#ffffff', '#eaf3fa'))
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        try:
            self.root.configure(bg=bg)
        except Exception:
            pass
        for sty in ['TFrame','TLabelframe','TLabelFrame','TNotebook','TNotebook.Tab']:
            try:
                self.style.configure(sty, background=bg, foreground=fg)
            except Exception:
                pass
        try:
            self.style.configure('TLabel', background=bg, foreground=fg)
            self.style.configure('Header.TFrame', background=header_bg)
            self.style.configure('Brand.TLabel', background=header_bg, foreground=brand_fg, font=('Segoe UI',18,'bold'))
            self.style.configure('Byline.TLabel', background=header_bg, foreground=byline_fg, font=('Segoe UI',10,'bold'))
            self.style.configure('HeaderNote.TLabel', background=header_bg, foreground=muted, font=('Segoe UI',9))
            self.style.configure('Status.TLabel', background=panel, foreground=fg)
            self.style.configure('TCheckbutton', background=bg, foreground=fg)
            self.style.map('TCheckbutton', background=[('active', bg)], foreground=[('active', fg)])
            self.style.configure('TButton', background=COLORS.get('button', panel), foreground=fg, bordercolor=COLORS.get('border', '#555555'), focusthickness=1, focuscolor=accent)
            self.style.map('TButton', background=[('pressed', COLORS.get('button_pressed', panel2)), ('active', COLORS.get('button_hover', panel2))], foreground=[('active', fg)])
            self.style.configure('TEntry', fieldbackground=entry, foreground=fg, insertcolor=fg, bordercolor=COLORS.get('border', '#555555'))
            self.style.map('TEntry', fieldbackground=[('focus', entry), ('readonly', entry)], foreground=[('focus', fg), ('readonly', fg)])
            self.style.configure('Treeview', background=entry, fieldbackground=entry, foreground=fg, rowheight=24)
            self.style.configure('Treeview.Heading', background=panel, foreground=fg)
            self.style.map('Treeview', background=[('selected', select)], foreground=[('selected', fg)])
        except Exception:
            pass
        for widget in getattr(self, '_theme_widgets', []):
            try:
                cls=widget.winfo_class()
                if cls in ('Text','Listbox'):
                    widget.configure(bg=entry, fg=fg, insertbackground=fg, selectbackground=select, selectforeground=fg, highlightbackground=panel, highlightcolor=accent)
                elif cls == 'Canvas':
                    widget.configure(bg=panel, highlightbackground=panel, highlightcolor=accent)
                elif cls == 'Button':
                    widget.configure(bg=COLORS.get('button', panel), fg=fg, activebackground=COLORS.get('button_hover', panel2), activeforeground=fg, highlightbackground=COLORS.get('border', panel), highlightcolor=accent)
                else:
                    try:
                        widget.configure(bg=bg, fg=fg)
                    except Exception:
                        widget.configure(bg=bg)
            except Exception:
                pass
        try:
            self.info.configure(bg=entry, fg=fg, insertbackground=fg, selectbackground=select, selectforeground=fg)
            self.img_list.configure(bg=entry, fg=fg, selectbackground=select, selectforeground=fg)
        except Exception:
            pass
        self.set_status(f'Theme applied. {APP_NAME} is ready; original PCPACKs are never modified.')

    def toggle_dark_mode(self):
        self.apply_theme(not getattr(self, 'dark_mode', True))

    def build_ui(self):
        # Menu fallback keeps every major action reachable even on small screens.
        menubar=tk.Menu(self.root)
        file_menu=tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open SM3 Pack...', command=self.choose_pcpack)
        file_menu.add_command(label='Choose Output Folder...', command=self.choose_output)
        file_menu.add_command(label='Select Replacement Folder...', command=self.choose_replacement_folder)
        file_menu.add_command(label='Open Output', command=self.open_output_folder)
        file_menu.add_command(label='Open Replacement Folder', command=self.open_replacement_folder)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)

        actions_menu=tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label='Build TEX Preview', command=self.build_preview)
        actions_menu.add_separator()
        actions_menu.add_command(label='SINGLE SELECTED DDS EXPORT', command=self.export_original_dds)
        actions_menu.add_command(label='EXPORT EDIT-READY DDS + MANIFEST', command=self.export_all_header_locked_dds_manifest)
        actions_menu.add_command(label='.TEX: EXPORT SELECTED ORIGINAL .TEX', command=self.export_selected_original_tex)
        actions_menu.add_command(label='.TEX: DDS -> .TEX USING SELECTED EXTRACTOR SHELL', command=self.convert_dds_to_native_tex_selected)
        actions_menu.add_command(label='SINGLE FILE EDITOR-SAFE PATCH -> WRITE PCPACK', command=self.single_file_gimp_safe_patch_write_pcpack)
        actions_menu.add_command(label='MULTIPLE FILE EDITOR-SAFE PATCH -> WRITE PCPACK', command=self.multiple_file_editor_safe_patch_write_pcpack)
        actions_menu.add_command(label='FINAL EDITOR-SAFE REIMPORT -> WRITE PATCHED PCPACK', command=self.final_safe_reimport_auto_normalize_folder)
        actions_menu.add_separator()
        actions_menu.add_command(label='RESTORE: All TEX from Clean Original Pack', command=self.restore_all_tex_from_clean_original)
        actions_menu.add_command(label='BUGCHECK: Scan Current Targets', command=self.bugcheck_current_targets)
        menubar.add_cascade(label='Actions', menu=actions_menu)

        view_menu=tk.Menu(menubar, tearoff=0)
        # v5.2.91: global Theme selector handles Classic / Light / Full Dark.
        view_menu.add_command(label='Open Index', command=self.open_index)
        view_menu.add_command(label='Reload Output', command=self.reload_existing)
        menubar.add_cascade(label='View', menu=view_menu)
        self._tool_menu = menubar

        header=ttk.Frame(self.root,style='Header.TFrame',padding=(12,8,12,6)); header.pack(fill='x')
        ttk.Label(header,text=APP_NAME,style='Brand.TLabel').grid(row=0,column=0,sticky='w')
        ttk.Label(header,text=f'Made by {APP_AUTHOR}',style='Byline.TLabel').grid(row=0,column=1,sticky='w',padx=(12,0))
        ttk.Label(header,text=APP_BUILD,style='HeaderNote.TLabel').grid(row=0,column=2,sticky='e')
        ttk.Label(header,text='SM3 PC + Xbox texture viewer. PC editing/reimport stays exact-format; Xbox is preview + DDS export only.',style='HeaderNote.TLabel').grid(row=1,column=0,columnspan=3,sticky='w',pady=(2,0))
        header.columnconfigure(1,weight=1)

        # v5.2.145: keep Tex Swapper focused on two tabs only.
        # Classic Workflow contains the proven PCPACK flow plus the quick loose .TEX actions.
        # Browse + Image embeds the old folder-preview window directly in the Toolkit.
        self.workflow_tabs=ttk.Notebook(self.root)
        self.workflow_tabs.pack(fill='both',expand=True,padx=8,pady=(2,8))
        self.classic_workflow_page=ttk.Frame(self.workflow_tabs)
        self.native_tex_browser_page=ttk.Frame(self.workflow_tabs)
        self.workflow_tabs.add(self.classic_workflow_page,text='Classic Workflow')
        self.workflow_tabs.add(self.native_tex_browser_page,text='Browse + Image')
        classic_parent=self.classic_workflow_page

        # Top file selectors stay compact so they do not push action buttons off-screen.
        top=ttk.Frame(classic_parent,padding=(8,6,8,4)); top.pack(fill='x')
        ttk.Label(top,text='SM3 PC/Xbox Pack:').grid(row=0,column=0,sticky='w')
        ttk.Entry(top,textvariable=self.pcpack_var,width=72).grid(row=0,column=1,sticky='ew',padx=4)
        ttk.Button(top,text='Browse Pack',command=self.choose_pcpack).grid(row=0,column=2,padx=2)
        ttk.Button(top,text='Build Preview',command=self.build_preview).grid(row=0,column=3,padx=2)
        ttk.Label(top,text='Output folder:').grid(row=1,column=0,sticky='w',pady=(4,0))
        ttk.Entry(top,textvariable=self.output_var,width=72).grid(row=1,column=1,sticky='ew',padx=4,pady=(4,0))
        ttk.Button(top,text='Choose Output',command=self.choose_output).grid(row=1,column=2,padx=2,pady=(4,0))
        ttk.Button(top,text='Open Output',command=self.open_output_folder).grid(row=1,column=3,padx=2,pady=(4,0))
        ttk.Label(top,text='Replacement DDS folder:').grid(row=2,column=0,sticky='w',pady=(4,0))
        ttk.Entry(top,textvariable=self.replacement_folder_var,width=72).grid(row=2,column=1,sticky='ew',padx=4,pady=(4,0))
        ttk.Button(top,text='Select Repl Folder',command=self.choose_replacement_folder).grid(row=2,column=2,padx=2,pady=(4,0))
        ttk.Button(top,text='Open Repl',command=self.open_replacement_folder).grid(row=2,column=3,padx=2,pady=(4,0))
        top.columnconfigure(1,weight=1)

        mid=ttk.Frame(classic_parent,padding=(8,0,8,4)); mid.pack(fill='x')
        ttk.Label(mid,text='Search textures:').grid(row=0,column=0,sticky='w')
        ent=ttk.Entry(mid,textvariable=self.search_var,width=34); ent.grid(row=0,column=1,sticky='ew',padx=4)
        ent.bind('<KeyRelease>',lambda e:self.apply_filter())
        ttk.Button(mid,text='Clear Search',command=self.clear_search).grid(row=0,column=2,padx=2)
        ttk.Checkbutton(mid,text='Force opaque RGB',variable=self.force_opaque_var).grid(row=0,column=3,sticky='w',padx=4)
        ttk.Checkbutton(mid,text='Warn non-diffuse',variable=self.diffuse_safe_var).grid(row=0,column=4,sticky='w',padx=4)
        ttk.Checkbutton(mid,text='Strict diffuse only',variable=self.strict_diffuse_var).grid(row=0,column=5,sticky='w',padx=4)
        ttk.Button(mid,text='Open Index',command=self.open_index).grid(row=0,column=6,padx=2)
        ttk.Button(mid,text='Reload',command=self.reload_existing).grid(row=0,column=7,padx=2)
        # v5.2.91: theme switching moved to the global top-bar Theme selector.
        ttk.Label(mid,textvariable=self.selected_target_var,style='Status.TLabel').grid(row=1,column=0,columnspan=9,sticky='ew',pady=(4,0))
        mid.columnconfigure(1,weight=1)

        # Main body: left = target list, middle = preview/info, right = always-visible action panel.
        body=ttk.PanedWindow(classic_parent,orient='horizontal'); body.pack(fill='both',expand=True,padx=8,pady=(0,8))

        left=ttk.Frame(body,padding=4); body.add(left,weight=3)
        ttk.Label(left,text='TEX Targets - Ctrl-click / Shift-click for batch selection',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        tree_frame=ttk.Frame(left); tree_frame.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(tree_frame,columns=('asset','size','fmt','bytes'),show='headings',height=24,selectmode='extended')
        tree_y=ttk.Scrollbar(tree_frame,orient='vertical',command=self.tree.yview)
        tree_x=ttk.Scrollbar(tree_frame,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set,xscrollcommand=tree_x.set)
        for col,w in [('asset',310),('size',82),('fmt',92),('bytes',92)]:
            self.tree.heading(col,text=col)
            self.tree.column(col,width=w,anchor='w',stretch=(col=='asset'))
        self.tree.grid(row=0,column=0,sticky='nsew')
        tree_y.grid(row=0,column=1,sticky='ns')
        tree_x.grid(row=1,column=0,sticky='ew')
        tree_frame.columnconfigure(0,weight=1); tree_frame.rowconfigure(0,weight=1)
        self.tree.bind('<<TreeviewSelect>>',self.on_target_select)
        self.bind_mousewheel_to_widget(self.tree)

        center=ttk.Frame(body,padding=4); body.add(center,weight=3)
        ttk.Label(center,text='Preview Image',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        self.preview_label=ttk.Label(center)
        self.preview_label.pack(fill='x',expand=False,pady=(4,6))
        info_frame=ttk.Frame(center); info_frame.pack(fill='both',expand=True)
        self.info=tk.Text(info_frame,height=14,wrap='word')
        info_y=ttk.Scrollbar(info_frame,orient='vertical',command=self.info.yview)
        self.info.configure(yscrollcommand=info_y.set)
        self.info.grid(row=0,column=0,sticky='nsew')
        info_y.grid(row=0,column=1,sticky='ns')
        info_frame.columnconfigure(0,weight=1); info_frame.rowconfigure(0,weight=1)
        self.bind_mousewheel_to_widget(self.info)

        right=ttk.Frame(body,padding=4); body.add(right,weight=3)
        ttk.Label(right,text='Actions — PCPACK + .TEX',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        actions=ttk.Notebook(right)
        actions.pack(fill='x',expand=False,pady=(2,6))

        def _scroll_tab(name):
            outer=ttk.Frame(actions)
            actions.add(outer,text=name)
            canvas=tk.Canvas(outer,highlightthickness=0,borderwidth=0,height=170,bg='#202020')
            ybar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
            inner=ttk.Frame(canvas,padding=6)
            inner_id=canvas.create_window((0,0),window=inner,anchor='nw')
            def _cfg_inner(event=None):
                canvas.configure(scrollregion=canvas.bbox('all'))
            def _cfg_canvas(event=None):
                try: canvas.itemconfigure(inner_id,width=event.width)
                except Exception: pass
            inner.bind('<Configure>',_cfg_inner)
            canvas.bind('<Configure>',_cfg_canvas)
            canvas.configure(yscrollcommand=ybar.set)
            canvas.grid(row=0,column=0,sticky='nsew')
            ybar.grid(row=0,column=1,sticky='ns')
            outer.columnconfigure(0,weight=1); outer.rowconfigure(0,weight=1)
            self.bind_mousewheel_to_widget(canvas)
            inner.columnconfigure(0,weight=1)
            inner.columnconfigure(1,weight=1)
            if not hasattr(self,'_theme_widgets'): self._theme_widgets=[]
            self._theme_widgets.append(canvas)
            return inner
        def _grid_btn(parent, text, command, row, col=0, colspan=1):
            btn=ttk.Button(parent,text=text,command=command)
            btn.grid(row=row,column=col,columnspan=colspan,sticky='ew',padx=3,pady=3)
            return btn

        tab_main=_scroll_tab('Classic')
        ttk.Label(tab_main,text='PCPACK / DDS',font=('TkDefaultFont',10,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',padx=3,pady=(0,3))
        _grid_btn(tab_main,'1) SINGLE DDS EXPORT',self.export_original_dds,1,0,2)
        _grid_btn(tab_main,'2) EXPORT ALL DDS',self.export_all_header_locked_dds_manifest,2,0,2)
        _grid_btn(tab_main,'3) SAFE PATCH -> PCPACK',self.single_file_gimp_safe_patch_write_pcpack,3,0,2)
        _grid_btn(tab_main,'4) MULTI SAFE PATCH -> PCPACK',self.multiple_file_editor_safe_patch_write_pcpack,4,0,2)
        _grid_btn(tab_main,'5) FOLDER REIMPORT -> PCPACK',self.final_safe_reimport_auto_normalize_folder,5,0,2)
        _grid_btn(tab_main,'Set Edited DDS Folder',self.choose_replacement_folder,6,0,2)
        _grid_btn(tab_main,'Open Output Folder',self.open_output_folder,7,0)
        _grid_btn(tab_main,'Open Edited DDS',self.open_replacement_folder,7,1)
        ttk.Separator(tab_main,orient='horizontal').grid(row=8,column=0,columnspan=2,sticky='ew',padx=3,pady=(8,6))
        ttk.Label(tab_main,text='LOOSE .TEX',font=('TkDefaultFont',10,'bold')).grid(row=9,column=0,columnspan=2,sticky='w',padx=3,pady=(0,3))
        _grid_btn(tab_main,'6) EXPORT ORIGINAL .TEX',self.export_selected_original_tex,10,0,2)
        _grid_btn(tab_main,'7) DDS -> SELECTED .TEX',self.convert_dds_to_native_tex_selected,11,0,2)
        ttk.Label(tab_main,text='Classic keeps the fast PCPACK + loose .TEX actions together. Browse + Image has its own full page, so no extra browser window/button is needed here.',wraplength=300,justify='left').grid(row=12,column=0,columnspan=2,sticky='ew',padx=3,pady=(8,3))

        tab_recovery=_scroll_tab('Recovery')
        _grid_btn(tab_recovery,'RESTORE: All TEX from Clean Original Pack',self.restore_all_tex_from_clean_original,0,0,2)
        _grid_btn(tab_recovery,'BUGCHECK: Scan Current Targets',self.bugcheck_current_targets,1,0,2)
        _grid_btn(tab_recovery,'CONTROL: Original Selected Texture',self.self_replace_selected,2,0,2)
        ttk.Label(tab_recovery,text='Recovery tools only. Use Classic Workflow for PCPACK export/reimport and quick loose .TEX export/conversion. Use Browse + Image to review folders of native .TEX files.',wraplength=300,justify='left').grid(row=3,column=0,columnspan=2,sticky='ew',padx=3,pady=(8,3))

        tab_advanced=_scroll_tab('Advanced')
        _grid_btn(tab_advanced,'Dump Component0/1',self.dump_selected,0,0,2)
        _grid_btn(tab_advanced,'BATCH Export DDS for Selected',self.batch_export_original_dds,1,0,2)
        _grid_btn(tab_advanced,'CONTROL: Full Original-Texture Self Test',self.full_selftest_copy,2,0,2)
        ttk.Label(tab_advanced,text='Advanced diagnostics. Normal users should stay on Classic Workflow or Browse + Image.',wraplength=300,justify='left').grid(row=3,column=0,columnspan=2,sticky='ew',padx=3,pady=(8,3))

        ttk.Separator(right,orient='horizontal').pack(fill='x',pady=(4,6))
        ttk.Label(right,text='Preview Files',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        img_frame=ttk.Frame(right); img_frame.pack(fill='both',expand=True)
        self.img_list=tk.Listbox(img_frame,height=12,selectmode='browse')
        img_y=ttk.Scrollbar(img_frame,orient='vertical',command=self.img_list.yview)
        img_x=ttk.Scrollbar(img_frame,orient='horizontal',command=self.img_list.xview)
        self.img_list.configure(yscrollcommand=img_y.set,xscrollcommand=img_x.set)
        if not hasattr(self,'_theme_widgets'):
            self._theme_widgets=[]
        self._theme_widgets.extend([self.info,self.img_list])
        self.img_list.grid(row=0,column=0,sticky='nsew')
        img_y.grid(row=0,column=1,sticky='ns')
        img_x.grid(row=1,column=0,sticky='ew')
        img_frame.columnconfigure(0,weight=1); img_frame.rowconfigure(0,weight=1)
        self.img_list.bind('<<ListboxSelect>>',self.on_image_select)
        self.bind_mousewheel_to_widget(self.img_list)
        img_btns=ttk.Frame(right); img_btns.pack(fill='x',pady=4)
        ttk.Button(img_btns,text='Open Image',command=self.open_selected_image).pack(side='left',padx=2)
        ttk.Button(img_btns,text='Open Folder',command=self.open_selected_image_folder).pack(side='left',padx=2)

        self._build_native_tex_browser_page()

        ttk.Label(self.root,textvariable=self.status_var,relief='sunken',anchor='w',style='Status.TLabel').pack(side='bottom',fill='x')

    def _build_native_tex_workflow_page(self):
        """Legacy no-op page retained only for source compatibility; loose .TEX actions now live in Classic Workflow."""
        return

        page=self.native_tex_workflow_page
        top=ttk.Frame(page,padding=12); top.pack(fill='x')
        ttk.Label(top,text='Loose Native .TEX Workflow',font=('TkDefaultFont',14,'bold')).pack(anchor='w')
        ttk.Label(
            top,
            text='Use this page when you want to export a selected SM3 TEX target as a loose .TEX or convert an edited DDS back to that target identity. The proven v5.2.137 PHYS/no-PHYS and mip-count preservation rules are unchanged.',
            wraplength=1050,justify='left'
        ).pack(anchor='w',pady=(4,10))

        target_box=ttk.LabelFrame(page,text='Selected target from Classic Workflow',padding=10)
        target_box.pack(fill='x',padx=12,pady=(0,8))
        ttk.Label(target_box,textvariable=self.native_tex_selected_target_var,wraplength=1050,justify='left').pack(side='left',fill='x',expand=True)
        ttk.Button(target_box,text='Go to Classic Workflow',command=lambda:self.workflow_tabs.select(self.classic_workflow_page)).pack(side='right',padx=(8,0))

        actions=ttk.LabelFrame(page,text='Native .TEX Actions',padding=12)
        actions.pack(fill='x',padx=12,pady=8)
        ttk.Button(actions,text='1) EXPORT SELECTED ORIGINAL .TEX',command=self.export_selected_original_tex).grid(row=0,column=0,sticky='ew',padx=4,pady=4)
        ttk.Button(actions,text='2) UNIVERSAL DDS -> .TEX (SELECTED SM3 TARGET)',command=self.convert_dds_to_native_tex_selected).grid(row=1,column=0,sticky='ew',padx=4,pady=4)
        ttk.Button(actions,text='Open Output Folder',command=self.open_output_folder).grid(row=2,column=0,sticky='ew',padx=4,pady=4)
        actions.columnconfigure(0,weight=1)

        note=ttk.LabelFrame(page,text='What each page is for',padding=12)
        note.pack(fill='x',padx=12,pady=8)
        ttk.Label(note,text=(
            'Classic Workflow = original PCPACK export/edit/reimport workflow.\n'
            '.TEX = loose native .TEX conversion using the selected game target identity.\n'
            'Browse + Image = choose a folder of extracted/loose .tex files and review them directly inside the Toolkit.'
        ),justify='left',wraplength=1050).pack(anchor='w')

    def _build_native_tex_browser_page(self):
        page=self.native_tex_browser_page
        top=ttk.Frame(page,padding=(10,8)); top.pack(fill='x')
        ttk.Label(top,text='Browse + Image — SM3 PC / Xbox .TEX Review',font=('TkDefaultFont',14,'bold')).grid(row=0,column=0,columnspan=5,sticky='w')
        ttk.Label(top,text='Folder:').grid(row=1,column=0,sticky='w',pady=(8,0))
        ttk.Entry(top,textvariable=self.native_tex_folder_var).grid(row=1,column=1,sticky='ew',padx=4,pady=(8,0))
        ttk.Button(top,text='Choose .TEX Folder',command=self.choose_native_tex_browser_folder).grid(row=1,column=2,padx=3,pady=(8,0))
        ttk.Button(top,text='Rescan',command=self.rescan_native_tex_browser_folder).grid(row=1,column=3,padx=3,pady=(8,0))
        ttk.Button(top,text='Open Folder',command=self.open_native_tex_browser_folder).grid(row=1,column=4,padx=3,pady=(8,0))
        ttk.Label(top,text='Search:').grid(row=2,column=0,sticky='w',pady=(6,0))
        ent=ttk.Entry(top,textvariable=self.native_tex_browser_search_var)
        ent.grid(row=2,column=1,sticky='ew',padx=4,pady=(6,0))
        ent.bind('<KeyRelease>',lambda _e:self.apply_native_tex_browser_filter())
        ttk.Button(top,text='Clear Search',command=self.clear_native_tex_browser_search).grid(row=2,column=2,padx=3,pady=(6,0))
        ttk.Label(top,text='Select a texture below to preview it. No extra window opens.',style='Status.TLabel').grid(row=2,column=3,columnspan=2,sticky='e',padx=3,pady=(6,0))
        top.columnconfigure(1,weight=1)

        pan=ttk.PanedWindow(page,orient='horizontal'); pan.pack(fill='both',expand=True,padx=10,pady=(0,10))
        left=ttk.Frame(pan,padding=4); right=ttk.Frame(pan,padding=4)
        pan.add(left,weight=5); pan.add(right,weight=5)

        ttk.Label(left,text='SM3 .TEX Files',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        tf=ttk.Frame(left); tf.pack(fill='both',expand=True,pady=(4,0))
        self.native_tex_browser_tree=ttk.Treeview(tf,columns=('asset','size','fmt','mips','hash','status'),show='headings',selectmode='browse')
        ys=ttk.Scrollbar(tf,orient='vertical',command=self.native_tex_browser_tree.yview)
        xs=ttk.Scrollbar(tf,orient='horizontal',command=self.native_tex_browser_tree.xview)
        self.native_tex_browser_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        for c,w in [('asset',280),('size',90),('fmt',150),('mips',55),('hash',105),('status',110)]:
            self.native_tex_browser_tree.heading(c,text=c)
            self.native_tex_browser_tree.column(c,width=w,anchor='w',stretch=(c=='asset'))
        self.native_tex_browser_tree.grid(row=0,column=0,sticky='nsew')
        ys.grid(row=0,column=1,sticky='ns'); xs.grid(row=1,column=0,sticky='ew')
        tf.columnconfigure(0,weight=1); tf.rowconfigure(0,weight=1)
        self.native_tex_browser_tree.bind('<<TreeviewSelect>>',self.on_native_tex_browser_select)
        self.bind_mousewheel_to_widget(self.native_tex_browser_tree)

        ttk.Label(right,text='Texture Preview',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        self.native_tex_browser_preview=ttk.Label(right,text='Choose a .TEX folder, then select a texture.',anchor='center')
        self.native_tex_browser_preview.pack(fill='both',expand=True,pady=6)
        self.native_tex_browser_info_var=tk.StringVar(value='')
        ttk.Label(right,textvariable=self.native_tex_browser_info_var,wraplength=560,justify='left').pack(fill='x',pady=(0,6))
        btns=ttk.Frame(right); btns.pack(fill='x')
        ttk.Button(btns,text='DDS -> Selected .TEX Identity',command=self.native_tex_browser_convert_selected).pack(side='left',padx=2,pady=2)
        ttk.Button(btns,text='EXPORT SELECTED .TEX',command=self.native_tex_browser_export_selected_tex).pack(side='left',padx=2,pady=2)
        ttk.Button(btns,text='EXPORT TO DDS',command=self.native_tex_browser_export_selected_dds).pack(side='left',padx=2,pady=2)
        ttk.Button(btns,text='OPEN OUTPUT',command=self.native_tex_browser_open_output).pack(side='left',padx=2,pady=2)
        ttk.Button(btns,text='Reveal .TEX',command=self.native_tex_browser_reveal_selected).pack(side='left',padx=2,pady=2)

    def choose_pcpack(self):
        p=filedialog.askopenfilename(
            title='Select Spider-Man 3 PC or Xbox pack',
            filetypes=[
                ('SM3 PC/Xbox packs','*.PCPACK *.pcpack *.PCAPK *.pcapk *.APKF *.apkf *.XEPACK *.xepack *.XEAPK *.xeapk *.XPACK *.xpack'),
                ('Xbox 360 packs','*.XEPACK *.xepack *.XEAPK *.xeapk *.XPACK *.xpack'),
                ('SM3 PC packs','*.PCPACK *.pcpack *.PCAPK *.pcapk *.APKF *.apkf'),
                ('All files','*.*'),
            ],
        )
        if p: self.pcpack_var.set(p)
    def choose_output(self):
        p=filedialog.askdirectory(title='Select output folder')
        if p:
            self.output_var.set(p)
            # If no replacement folder has been chosen yet, use the output folder as a useful default.
            if not self.replacement_folder_var.get().strip():
                self.replacement_folder_var.set(p)

    def open_output_folder(self):
        raw=self.output_var.get().strip()
        if not raw:
            messagebox.showinfo('Output folder not set','Choose an output folder first.')
            return
        p=Path(raw)
        if p.exists() and p.is_dir():
            open_path(p)
        else:
            messagebox.showinfo('Output folder not set','Choose an output folder first.')

    def choose_replacement_folder(self):
        p=filedialog.askdirectory(title='Select folder containing edited DDS replacement files')
        if p:
            self.replacement_folder_var.set(p)
            self.last_export_dir=p
            self.set_status('Replacement DDS folder set: '+p)

    def open_replacement_folder(self):
        p=Path(self.replacement_folder_var.get().strip())
        if p.exists() and p.is_dir():
            open_path(p)
        else:
            messagebox.showinfo('Replacement folder not set','Select a replacement DDS folder first.')

    def clear_search(self):
        self.search_var.set('')
        self.apply_filter()
        self.set_status('Search cleared.')

    def update_selected_target_label(self, target=None):
        target = target or self.selected_target
        if not target:
            self.selected_target_var.set('Selected texture: none')
            try:
                self.native_tex_selected_target_var.set('Selected classic TEX target: none')
            except Exception:
                pass
            return
        self.selected_target_var.set(
            'Selected texture: '
            + str(target.get('asset','')) + ' | '
            + str(target.get('filename_hash','')) + ' | '
            + f"{target.get('width')}x{target.get('height')} "
            + str(target.get('format_kind','')) + ' | '
            + 'mips ' + str(target.get('mips','')) + ' | '
            + 'payload ' + str(target.get('component1_size','')) + ' bytes'
        )
        try:
            self.native_tex_selected_target_var.set(
                'Selected classic TEX target: '
                + str(target.get('asset','')) + ' | '
                + str(target.get('filename_hash','')) + ' | '
                + f"{target.get('width')}x{target.get('height')} "
                + str(target.get('format_kind','')) + ' | mips '
                + str(target.get('mips',''))
            )
        except Exception:
            pass

    def manual_options_check(self):
        """v4.7: Audit manual workflow wiring and current patch readiness."""
        raw_out = self.output_var.get().strip()
        if not raw_out:
            messagebox.showinfo('Output folder not set','Choose an output folder first.')
            return
        outroot = Path(raw_out)
        report_dir = outroot / 'MANUAL_OPTIONS_CHECK_v4_8'
        report_dir.mkdir(parents=True, exist_ok=True)

        pc = Path(self.pcpack_var.get()) if self.pcpack_var.get() else Path('')
        selected_targets = []
        try:
            selected_targets = self.get_selected_targets()
        except Exception:
            selected_targets = []

        checks = []
        def add(name, status, detail, required=False):
            checks.append({
                'manual_option': name,
                'status': status,
                'detail': detail,
                'required_for_patch': bool(required),
            })

        # Core state checks.
        add('PCPACK selected', 'OK' if pc.exists() else 'WARN', str(pc) if str(pc) else 'No PCPACK selected', True)
        add('Build Preview / targets loaded', 'OK' if self.targets else 'WARN', f'{len(self.targets)} target(s) loaded', True)
        add('Current selected target(s)', 'OK' if selected_targets else 'INFO', f'{len(selected_targets)} selected target(s)')
        add('Replacement folder set', 'OK' if self.replacement_folder_var.get().strip() else 'INFO', self.replacement_folder_var.get().strip() or 'No replacement folder set')
        add('Output folder', 'OK', str(outroot))

        # Function presence checks.
        required_methods = [
            ('Selected exact one DDS', 'old_selected_one_file_direct_export'),
            ('Selected convert image/DDS to target', 'selected_target_format_convert_direct'),
            ('One file auto file-first', 'old_one_file_auto_select_and_patch'),
            ('Manual old folder texture picker', 'manual_old_folder_texture_picker'),
            ('Manual selected pair files in order', 'manual_replace_selected_with_multiple_files'),
            ('Multi-file auto select + patch', 'manual_multi_file_auto_select_and_patch'),
            ('Export all DDS', 'export_all_dds'),
            ('Reimport all DDS folder', 'reimport_all_dds_folder'),
            ('Smart reimport exact + convert mips', 'smart_reimport_all_folder'),
            ('Bugcheck current targets', 'bugcheck_current_targets'),
            ('Resolve current selected target', 'resolve_current_selected_target'),
            ('Smart mixed patch helper route', '_build_selected_order_smart_items'),
        ]
        for label, meth in required_methods:
            ok = hasattr(self, meth) and callable(getattr(self, meth, None))
            add(label, 'OK' if ok else 'ERROR', f'method {meth} ' + ('found' if ok else 'missing'), True)

        # Top-level helper checks from globals.
        helper_names = [
            'copy_and_patch_pcpack_smart_mixed_many',
            'copy_and_patch_pcpack_original_format_dds_many',
            'validate_dds_matches_target',
            'export_original_component_as_dds',
            'encode_image_to_component1',
            'target_edit_key',
        ]
        for h in helper_names:
            ok = h in globals() and callable(globals().get(h))
            add('Helper: '+h, 'OK' if ok else 'ERROR', 'available' if ok else 'missing', True)

        # Manual workflow guidance based on current selection count.
        if len(selected_targets) == 1:
            t = selected_targets[0]
            add(
                'Recommended manual route for current selection',
                'INFO',
                f"One target selected: use SELECTED EXACT if DDS matches, or legacy selected convert / SMART route if mips-format differ. Target={t.get('asset')} {t.get('width')}x{t.get('height')} {t.get('format_kind')} mips {t.get('mips')}"
            )
        elif len(selected_targets) > 1:
            add(
                'Recommended manual route for current selection',
                'INFO',
                f'{len(selected_targets)} targets selected: use MANUAL SELECTED: Pair Files In Order. Select replacement files in the same order.'
            )
        else:
            add(
                'Recommended manual route for current selection',
                'INFO',
                'No target selected. Build Preview, then select one target for one-file routes or multiple targets for pair-in-order route.'
            )

        # Report selected target details.
        target_rows = []
        for i,t in enumerate(selected_targets):
            target_rows.append({
                'selection_order': i+1,
                'asset': t.get('asset'),
                'hash': t.get('filename_hash'),
                'size': f"{t.get('width')}x{t.get('height')}",
                'format': t.get('format_kind'),
                'mips': t.get('mips'),
                'component1_size': t.get('component1_size'),
                'target_key': target_edit_key(t) if 'target_edit_key' in globals() else '',
            })

        write_csv(report_dir/'MANUAL_OPTIONS_CHECK_v4_8.csv', checks)
        write_csv(report_dir/'SELECTED_TARGETS_v4_8.csv', target_rows)

        summary = {
            'tool': 'THE_TEX_SWAPPER_TSGAMING264_v4_8',
            'pcpack': str(pc) if str(pc) else '',
            'pcpack_exists': pc.exists() if str(pc) else False,
            'target_count_loaded': len(self.targets),
            'selected_target_count': len(selected_targets),
            'replacement_folder': self.replacement_folder_var.get().strip(),
            'output_folder': str(outroot),
            'errors': [c for c in checks if c['status'] == 'ERROR'],
            'warnings': [c for c in checks if c['status'] == 'WARN'],
        }
        (report_dir/'MANUAL_OPTIONS_CHECK_SUMMARY_v4_8.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

        error_count = len(summary['errors'])
        warn_count = len(summary['warnings'])
        if error_count:
            msg = f'Internal options audit found {error_count} ERROR(s) and {warn_count} warning(s).\\n\\nReport folder:\\n{report_dir}'
            messagebox.showerror('Manual Options Check', msg)
        else:
            msg = f'Internal options audit passed. Warnings: {warn_count}.\\n\\nReport folder:\\n{report_dir}'
            messagebox.showinfo('Manual Options Check', msg)
        self.set_status(f'Internal options audit complete. Errors={error_count}, warnings={warn_count}. Report: {report_dir}')


    def bugcheck_current_targets(self):
        """Write a small sanity report for the currently scanned PCPACK/TEX target list."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Build Preview or Reload first.')
            return
        raw_out = self.output_var.get().strip()
        if not raw_out:
            messagebox.showinfo('Output folder not set','Choose an output folder first.')
            return
        outroot = Path(raw_out)
        report_dir = outroot / 'BUGCHECK_REPORTS'
        report_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        issues = []
        seen = set()
        for i,t in enumerate(self.targets):
            asset = str(t.get('asset',''))
            key = target_edit_key(t)
            width = int(t.get('width') or 0)
            height = int(t.get('height') or 0)
            mips = int(t.get('mips') or 0)
            c1 = int(t.get('component1_size') or 0)
            fmt = str(t.get('format_kind') or '')
            issue = []
            if key in seen: issue.append('DUPLICATE_TARGET_KEY')
            seen.add(key)
            if width <= 0 or height <= 0: issue.append('BAD_DIMENSIONS')
            if mips <= 0 or mips > 32: issue.append('BAD_MIP_COUNT')
            if c1 <= 0: issue.append('BAD_COMPONENT1_SIZE')
            if fmt not in ('DXT1','DXT3','DXT5','DXT5_CANDIDATE','BGRA32','L8'): issue.append('UNKNOWN_FORMAT')
            if issue:
                issues.append((asset, issue))
            rows.append({
                'index': i,
                'asset': asset,
                'hash': t.get('filename_hash',''),
                'size': f'{width}x{height}',
                'mips': mips,
                'format': fmt,
                'component1_size': c1,
                'issues': ';'.join(issue) if issue else 'OK',
            })
        write_csv(report_dir/'TEX_TARGET_BUGCHECK.csv', rows)
        summary = {
            'tool': 'THE_TEX_SWAPPER_TSGAMING264_v4_1',
            'target_count': len(self.targets),
            'issue_count': len(issues),
            'pcpack': self.pcpack_var.get(),
            'output_folder': self.output_var.get(),
            'note': 'This report checks target metadata only. It does not modify any PCPACK.'
        }
        (report_dir/'TEX_TARGET_BUGCHECK_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        messagebox.showinfo('Bugcheck complete', f'Checked {len(self.targets)} targets. Issues: {len(issues)}\n\nFolder:\n{report_dir}')
        self.set_status(f'Bugcheck complete. Issues: {len(issues)}. Report: {report_dir}')


    def set_status(self,msg):
        self.status_var.set(msg); self.root.update_idletasks()
    def build_preview(self):
        if core is None:
            messagebox.showerror('Missing decoder',f'Could not import bundled v1.4 decoder. Make sure you extracted the whole zip, not just the exe/script. Original error: {CORE_IMPORT_ERROR}')
            return
        pc=Path(self.pcpack_var.get())
        raw_out_text=self.output_var.get().strip()
        if not raw_out_text:
            messagebox.showinfo('Output folder not set','Choose an output folder first.')
            return
        raw_out=Path(raw_out_text)
        base_out=resolve_user_output_base(raw_out)
        if not pc.exists():
            messagebox.showerror('Missing pack','Select an original SM3 PC or Xbox pack first.')
            return

        # v5.2.162: direct Xbox/XE pack route. Keep the PC PCPACK editor path unchanged.
        # Xbox packs are extracted read-only into the Tex Swapper workspace, then
        # their combined .tex resources are opened in Browse + Image using the
        # proven Xenos endian + untile decoder.
        xbox_exts={'.xepack','.xeapk','.xpack','.x360'}
        is_xbox_pack=(pc.suffix.lower() in xbox_exts or 'XEPACK' in pc.name.upper() or 'XEAPK' in pc.name.upper())
        if is_xbox_pack:
            try:
                out=reset_generated_build_workspace(base_out)
                self.set_status('Xbox 360 pack detected. Extracting TEX resources read-only...')
                summary=xbox_pack_backend.extract_xbox_resources(pc,out,log=self.set_status)
                run_root=Path(summary.get('output_root') or out)
                tex_folder=run_root/'01_RESOURCES'/'TEX'
                tex_count=int(summary.get('tex_resources_extracted') or 0)
                self.targets=[]
                self.selected_target=None
                self.update_selected_target_label(None)
                self.populate_targets()
                self.native_tex_folder_var.set(str(tex_folder))
                self.load_native_tex_browser_folder(tex_folder)
                self.workflow_tabs.select(self.native_tex_browser_page)
                self.output_var.set(str(run_root))
                self.set_status(f'Xbox pack loaded: {tex_count} TEX resources. Preview is read-only; DDS export enabled. Workspace: {run_root}')
                if tex_count==0:
                    messagebox.showinfo('Xbox pack loaded - no TEX resources','The Xbox pack parsed successfully but contains no payload-backed TEX resources.')
                return
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror('Xbox TEX preview failed',str(e))
                self.set_status(f'Xbox TEX preview failed: {e}')
                return

        # v5.2.136: do NOT use the old rigid SM3 header guard here.
        # The universal scanner below shares the Pack Extractor's multi-route
        # probe and can accept compact/nonstandard/direct APKF SM3 packs.
        try:
            _head = pc.read_bytes()[:4]
        except OSError:
            _head = b''
        if _head[:3] == b'NCH':
            self.set_status(wrong_game_detail(pc))
            messagebox.showerror('SM3 pack route not recognized', WRONG_GAME_GUARD_MESSAGE)
            return
        try:
            # v4.8 safety: never delete the user's selected output folder.
            # Only delete/rebuild our generated workspace under that folder.
            out=reset_generated_build_workspace(base_out)
            self.set_status('Scanning PCPACK and extracting TEX components...')
            chain,targets=scan_pcpack_textures_to_chain(pc,out)
            self.set_status(f'Found {len(targets)} TEX files. Building previews...')
            # core.process may clear its destination, so keep it inside the generated workspace.
            preview_out=out/PREVIEW_DIR_NAME
            if targets:
                core.process(chain, preview_out)
            else:
                # A valid SM3 pack is allowed to contain no TEX resources. Do not
                # mislabel it as a wrong-game pack and do not make preview_core fail
                # on an intentionally empty TEX chain.
                ensure_dir(preview_out)
            # Put a copy of direct target CSV inside preview reports too.
            ensure_dir(preview_out/'REPORTS')
            shutil.copy2(out/'REPORTS'/'PCPACK_DIRECT_TEX_TARGETS.csv', preview_out/'REPORTS'/'PCPACK_DIRECT_TEX_TARGETS.csv')
            shutil.copy2(out/'REPORTS'/'PACK_DETECT.json', preview_out/'REPORTS'/'PACK_DETECT.json')
            self.output_var.set(str(preview_out))
            self.targets=targets
            self.selected_target=None
            self.update_selected_target_label(None)
            self.populate_targets()
            self.load_images()
            if targets:
                self.set_status(f'Done. Loaded {len(targets)} texture targets and {len(self.images)} preview images. Workspace: {out}')
            else:
                self.set_status(f'Valid SM3 pack loaded. This pack contains 0 viewable TEX resources. Workspace: {out}')
                messagebox.showinfo('Valid SM3 pack - no TEX resources', 'The pack was recognized successfully, but it contains no TEX resources for the Tex Swapper to preview.')
        except Exception as e:
            traceback.print_exc()
            if exception_suggests_wrong_game(e):
                self.set_status(wrong_game_detail(pc))
                messagebox.showerror('SM3 pack route not recognized', WRONG_GAME_GUARD_MESSAGE)
            else:
                messagebox.showerror('Build failed',str(e))
                self.set_status('Build failed.')
    def reload_existing(self):
        out=Path(self.output_var.get())
        csvp=out/'REPORTS'/'PCPACK_DIRECT_TEX_TARGETS.csv'
        if not csvp.exists():
            alt=out.parent/'REPORTS'/'PCPACK_DIRECT_TEX_TARGETS.csv'
            csvp=alt if alt.exists() else csvp
        if csvp.exists():
            with open(csvp,newline='',encoding='utf-8') as f:
                self.targets=list(csv.DictReader(f))
            self.selected_target=None
            self.update_selected_target_label(None)
            self.populate_targets()
        self.load_images()
        self.set_status(f'Reloaded {len(self.targets)} targets and {len(self.images)} images.')
    def populate_targets(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.apply_filter()
    def apply_filter(self):
        q=self.search_var.get().lower().strip()
        for i in self.tree.get_children(): self.tree.delete(i)
        self.filtered=[]
        for idx,t in enumerate(self.targets):
            hay=' '.join(str(t.get(k,'')) for k in ['asset','filename_hash','group','format_kind']).lower()
            if q and q not in hay: continue
            self.filtered.append((idx,t))
            size=f"{t.get('width')}x{t.get('height')}"
            self.tree.insert('', 'end', iid=str(idx), values=(t.get('asset'), size, t.get('format_kind'), t.get('component1_size')))
    def find_best_image_for_asset(self, asset):
        if not asset: return None
        low=asset.lower()
        for p in self.images:
            if low in p.name.lower() and ('BEST' in p.name.upper() or 'OPEN_FIRST' in str(p).upper()): return p
        for p in self.images:
            if low in p.name.lower(): return p
        return None
    def on_target_select(self,event=None):
        sel=self.tree.selection()
        if not sel:
            self.update_selected_target_label(None)
            return
        try:
            idx=int(sel[0])
            t=self.targets[idx]
        except Exception:
            return
        self.selected_target=t
        self.update_selected_target_label(t)
        self.set_status(f'Selected texture: {t.get("asset")} | {t.get("filename_hash")} | {t.get("width")}x{t.get("height")} {t.get("format_kind")} mips {t.get("mips")}')
        p=self.find_best_image_for_asset(t.get('asset',''))
        if p: self.show_image(p)
        self.show_info(t)
    def show_info(self,t):
        self.info.delete('1.0','end')
        if not t: return
        text=[]
        text.append(f'{APP_NAME} - Made by {APP_AUTHOR}')
        text.append('')
        for k in ['asset','filename_hash','group','width','height','mips','format_kind','format_raw','component0_size','component1_size','component1_absolute_start','component1_absolute_end','source_apkf_label']:
            text.append(f'{k}: {t.get(k,"")}')
        text.append('\nCLASSIC PCPACK RULES:')
        text.append('- Patches a NEW PCPACK copy only.')
        text.append('- Replacement component1 must be exact same size in Classic PCPACK patch mode.')
        text.append('- DDS input is okay if DDS payload after header equals target component1 size.')
        text.append('- FINAL route: EXPORT EDIT-READY DDS + MANIFEST -> edit/overwrite DDS -> FINAL EDITOR-SAFE REIMPORT. Exact DDS files patch directly; header-only edits are normalized; Paint.NET/GIMP-overwritten wrong-format/mip/payload DDS files are rebuilt from visible pixels into the SM3 target game format before writing one new PCPACK copy.')
        text.append('- PNG/JPG/BMP conversion is legacy/experimental; use DDS for real edits.')
        text.append('- GIMP can rewrite DDS internals. v5.2.38 handles this by rebuilding the edited pixels into the target SM3 format/mip shell during final reimport.')
        text.append('- v2.7: set a Replacement DDS folder so AUTO/BATCH AUTO knows exactly where edited DDS files are coming from.')
        text.append('- v2.9: Previous Folder Auto Replace scans a folder of DDS files, matches all same textures automatically, and exports one patched PCPACK copy.')
        text.append('- v3.0: Manual Old Folder Texture Picker lets you load all DDS files from an old folder and choose exactly which replacements to patch.')
        text.append('- v3.1: MANUAL Replace Selected with One File is for replacing the currently selected texture using one selected DDS/image/raw file.')
        text.append('- v3.2: MULTI FILE lets you select more than one DDS at once; the tool auto-maps valid DDS files to selected/current TEX targets and exports one patched PCPACK.')
        text.append('- v3.3: legacy one-file auto was restored/prioritized. Use it when you only want to select one DDS and patch one texture without the multi-file flow getting in the way.')
        text.append('- v3.4: OLD legacy one-file auto is an explicit v3.1-style single-DDS button.')
        text.append('- v3.5: OLD SELECTED ONE FILE restores the older selected-texture workflow: select texture first, pick one DDS, then immediately export one patched PCPACK copy without the auto-select/mapping window.')
        text.append('- v3.6: SAME FILE(S) lets you select one or more DDS files and auto-patch matching current targets without selecting/extracting one texture first. OLD SELECTED also now reads the current tree selection before saying no texture selected.')
        text.append('- v3.2: MANUAL Replace Selected with Files supports selecting multiple DDS files for selected textures. DDS is recommended; PNG/JPG raw conversion stays legacy/experimental.')
        text.append('- v1.9 Diffuse-safe mode warns before patching _nor/_spe/_spx/_ppi/_ppp/_ao/_env/control maps.')
        text.append('- CONTROL buttons patch using the original extracted bytes. Those copies should stay byte-identical.')
        text.append('')
        text.append('.TEX / RAIMIHOOK WORKFLOW:')
        text.append('- DDS -> loose .tex is a separate workflow and does NOT patch the PCPACK slot.')
        text.append('- Larger DDS dimensions and larger payloads are allowed in .Tex mode.')
        text.append('- v5.2.111: Browse .TEX Folder previews loose/extracted SM3 .tex files directly from disk.')
        text.append('- Universal selected-target conversion no longer rejects a valid SM3 texture just because the old extractor-shell route is unavailable.')
        text.append('- Selected-target/source conversion now preserves the original loose layout: either 0x44 IMG + payload or 0x44 IMG + ASCII PHYS + payload. Generated fallback output still uses PHYS.')
        text.append('- Supported converter inputs: DXT1/2/3/4/5, DX10 BC1/2/3, BGRA32/A8R8G8B8, and L8/R8 2D DDS.')
        self.info.insert('1.0','\n'.join(text))
    def load_images(self):
        out=Path(self.output_var.get())
        self.images=collect_preview_images(out)
        self.img_list.delete(0,'end')
        for p in self.images:
            try: rel=str(p.relative_to(out))
            except Exception: rel=p.name
            self.img_list.insert('end',rel)
    def on_image_select(self,event=None):
        sel=self.img_list.curselection()
        if not sel: return
        p=self.images[sel[0]]; self.selected_image=p; self.show_image(p)
    def show_image(self,p:Path):
        self.selected_image=p
        if not HAS_PIL:
            self.preview_label.configure(text=str(p)); return
        try:
            img=Image.open(p).convert('RGBA')
            img.thumbnail((460,360),Image.LANCZOS)
            self.img_ref=ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.img_ref,text='')
        except Exception as e:
            self.preview_label.configure(text=f'Could not load image:\n{p}\n{e}')
    def open_index(self):
        out=Path(self.output_var.get())/'PREVIEW_INDEX.html'
        if out.exists(): open_path(out)
        else: messagebox.showinfo('Missing','PREVIEW_INDEX.html not found yet.')
    def open_selected_image(self):
        if self.selected_image: open_path(self.selected_image)
    def open_selected_image_folder(self):
        if self.selected_image: open_path(self.selected_image.parent)

    def get_selected_targets(self):
        """Return all currently selected texture targets. Supports Ctrl/Shift multi-select."""
        out=[]
        seen=set()
        try:
            sels=self.tree.selection()
        except Exception:
            sels=[]
        for iid in sels:
            try:
                idx=int(iid)
                if idx not in seen and 0 <= idx < len(self.targets):
                    out.append(self.targets[idx]); seen.add(idx)
            except Exception:
                pass
        if not out and self.selected_target:
            out=[self.selected_target]
        return out

    def bind_mousewheel_to_widget(self, widget):
        def _wheel(event, w=widget):
            try:
                if getattr(event, 'num', None) == 4:
                    w.yview_scroll(-3, 'units')
                elif getattr(event, 'num', None) == 5:
                    w.yview_scroll(3, 'units')
                else:
                    delta = int(-1 * (event.delta / 120)) if event.delta else 0
                    if delta:
                        w.yview_scroll(delta * 3, 'units')
            except Exception:
                pass
            return 'break'
        for seq in ('<MouseWheel>','<Button-4>','<Button-5>'):
            try: widget.bind(seq, _wheel)
            except Exception: pass

    def target_safety_ok_or_confirm(self, action='patch'):
        t=self.selected_target
        if not t:
            return False
        reason=unsafe_target_reason(t)
        if self.strict_diffuse_var.get() and not is_diffuse_like_target(t):
            messagebox.showwarning(
                'Strict diffuse-only mode',
                'This target is not a safe diffuse/color texture.\n\n'
                + 'Target: ' + str(t.get('asset')) + '\n'
                + 'Reason: ' + reason + '\n\n'
                + 'Pick a _dif/_diff texture first.'
            )
            return False
        if self.diffuse_safe_var.get() and reason:
            return messagebox.askyesno(
                'Target warning',
                'This texture may NOT be a normal color/diffuse image.\n\n'
                + 'Target: ' + str(t.get('asset')) + '\n'
                + 'Reason: ' + reason + '\n\n'
                + 'If you patch this, the suit can turn white/pale/wrong. Continue anyway?'
            )
        return True

    def _native_tex_default_dir(self)->Path:
        raw=self.output_var.get().strip()
        if raw:
            try:
                return resolve_user_output_base(Path(raw))
            except Exception:
                return Path(raw)
        return Path.cwd()

    def _choose_native_tex_save_path(self,default_name:str)->Path|None:
        initial=self._native_tex_default_dir()
        p=filedialog.asksaveasfilename(
            title='Save RaimiHook loose native .TEX',
            initialdir=str(initial),
            initialfile=default_name,
            defaultextension='.tex',
            filetypes=[('SM3 loose native TEX','*.tex'),('All files','*.*')],
        )
        return Path(p) if p else None

    def export_selected_original_tex(self):
        """v5.2.108: export the exact selected extractor-style .tex from the clean PCPACK."""
        target=self.resolve_current_selected_target()
        if not target:
            messagebox.showinfo('Select target first','Build Preview and select ONE TEX target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        try:
            asset=str(target.get('asset') or 'texture')
            h=parse_sm3_hash_value(target.get('filename_hash'),asset)
            safe=clean_name(asset,'texture')
            out=self._choose_native_tex_save_path(f'0x{h:08X}.{safe}.tex')
            if not out:
                return
            report=write_selected_original_tex_from_pcpack(pc,target,out)
            Path(report['tex']+'.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            self.last_export_dir=str(Path(report['tex']).parent)
            self.output_var.set(str(Path(report['tex']).parent))
            self.set_status(f"Original extractor .TEX exported: {asset} | {Path(report['tex']).name}")
            messagebox.showinfo(
                'Selected original .TEX exported',
                'The tool created the exact SM3 Pack Extractor-style file:\n\n'
                f"{report['tex']}\n\n"
                f"component0: {report['component0_bytes']} bytes\n"
                f"component1: {report['component1_bytes']} bytes\n\n"
                'This is component0 + component1 directly from the clean PCPACK.'
            )
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Original .TEX export failed',str(e))
            self.set_status(f'Original .TEX export failed: {e}')

    def browse_native_tex_folder(self):
        """Compatibility action: open the embedded Browse + Image page and choose a folder."""
        try:
            self.workflow_tabs.select(self.native_tex_browser_page)
        except Exception:
            pass
        self.choose_native_tex_browser_folder()

    def choose_native_tex_browser_folder(self):
        start=self.native_tex_folder_var.get().strip() or self.replacement_folder_var.get().strip() or self.last_export_dir or str(Path.cwd())
        folder=filedialog.askdirectory(
            title='Select folder containing SM3 PC/Xbox .TEX files',
            initialdir=start if start and Path(start).exists() else None,
        )
        if not folder:
            return
        self.native_tex_folder_var.set(str(folder))
        self.load_native_tex_browser_folder(Path(folder))

    def rescan_native_tex_browser_folder(self):
        raw=self.native_tex_folder_var.get().strip()
        if not raw:
            self.choose_native_tex_browser_folder()
            return
        folder=Path(raw)
        if not folder.is_dir():
            messagebox.showerror('Browse + Image',f'The selected .TEX folder does not exist:\n\n{folder}')
            return
        self.load_native_tex_browser_folder(folder)

    def open_native_tex_browser_folder(self):
        raw=self.native_tex_folder_var.get().strip()
        if not raw or not Path(raw).is_dir():
            messagebox.showinfo('Browse + Image','Choose a .TEX folder first.')
            return
        open_path(Path(raw))

    def load_native_tex_browser_folder(self,folder:Path):
        folder=Path(folder)
        files=sorted([p for p in folder.rglob('*') if p.is_file() and p.suffix.lower()=='.tex'],key=lambda p:(p.name.lower(),str(p).lower()))
        records=[]; failures=[]
        for pth in files:
            try:
                records.append(parse_native_tex_file(pth))
            except Exception as exc:
                failures.append((pth,str(exc)))
        self.native_tex_browser_records=records
        self.native_tex_browser_selected=None
        self.native_tex_browser_photo=None
        self.apply_native_tex_browser_filter()
        if not records:
            self.native_tex_browser_preview.configure(image='',text='No readable SM3 .TEX files found in this folder.')
            self.native_tex_browser_info_var.set('')
            msg=f'No readable SM3 .tex files were found in:\n{folder}'
            if failures:
                msg+=f'\n\nUnreadable .tex files: {len(failures)}\nFirst error: {failures[0][0].name}: {failures[0][1]}'
            self.set_status(msg.replace('\n',' | '))
            return
        children=self.native_tex_browser_tree.get_children()
        if children:
            first=children[0]
            self.native_tex_browser_tree.selection_set(first)
            self.native_tex_browser_tree.focus(first)
            self.on_native_tex_browser_select()
        self.set_status(f'Browse + Image loaded {len(records)} readable .TEX files from {folder}. Unreadable: {len(failures)}.')

    def apply_native_tex_browser_filter(self):
        tree=getattr(self,'native_tex_browser_tree',None)
        if tree is None:
            return
        for iid in tree.get_children():
            tree.delete(iid)
        q=self.native_tex_browser_search_var.get().strip().lower()
        for idx,rec in enumerate(self.native_tex_browser_records):
            hay=' '.join(str(rec.get(k,'')) for k in ('name','asset','filename_hash','format_kind','payload_status')).lower()
            if q and q not in hay:
                continue
            tree.insert('', 'end', iid=str(idx), values=(
                rec.get('asset',''),
                f"{rec.get('width','?')}x{rec.get('height','?')}",
                rec.get('format_kind',''),
                rec.get('mips',''),
                rec.get('filename_hash',''),
                rec.get('payload_status',''),
            ))

    def clear_native_tex_browser_search(self):
        self.native_tex_browser_search_var.set('')
        self.apply_native_tex_browser_filter()

    def on_native_tex_browser_select(self,_event=None):
        sels=self.native_tex_browser_tree.selection()
        if not sels:
            self.native_tex_browser_selected=None
            return
        try:
            rec=self.native_tex_browser_records[int(sels[0])]
        except Exception:
            return
        self.native_tex_browser_selected=rec
        exp=rec.get('expected_payload_bytes')
        if str(rec.get('platform','PC')).upper()=='X360':
            self.native_tex_browser_info_var.set(
                f"{rec.get('name','')}\nPlatform: XBOX 360 | Hash: {rec.get('filename_hash','')} | {rec.get('width')}x{rec.get('height')} | "
                f"{rec.get('format_kind','')} | mips {rec.get('mips')}\n"
                f"Xenos format {rec.get('xbox_xenos_format')} | endian {rec.get('xbox_endian')} | "
                f"tiled: {'YES' if rec.get('xbox_tiled') else 'NO'} | pitch {rec.get('xbox_pitch_pixels')} px\n"
                f"GPU payload: {rec.get('payload_bytes')} bytes | base allocation: {rec.get('xbox_base_alloc_bytes')} | "
                f"linear base mip: {rec.get('first_mip_bytes')} bytes | {rec.get('payload_status','')}\n"
                "Xbox mode is READ-ONLY: preview + base-mip DDS export are safe; reimport is disabled."
            )
        else:
            marker='YES' if rec.get('has_phys_marker') else 'NO (legacy/read-compatible)'
            self.native_tex_browser_info_var.set(
                f"{rec.get('name','')}\nPlatform: PC | Hash: {rec.get('filename_hash','')} | {rec.get('width')}x{rec.get('height')} | "
                f"{rec.get('format_kind','')} | mips {rec.get('mips')} | depth {rec.get('depth')}\n"
                f"PHYS marker: {marker} | payload: {rec.get('payload_bytes')} bytes"
                + (f" / expected {exp}" if exp is not None else '')
                + f" | {rec.get('payload_status','')}"
            )
        try:
            img=native_tex_preview_pil(rec)
            img.thumbnail((620,600),Image.LANCZOS)
            photo=ImageTk.PhotoImage(img)
            self.native_tex_browser_photo=photo
            self.native_tex_browser_preview.configure(image=photo,text='')
        except Exception as exc:
            self.native_tex_browser_photo=None
            self.native_tex_browser_preview.configure(image='',text=f'Preview unavailable\n\n{exc}')
        self.set_status(f"Browse + Image: {rec.get('asset','')} | {rec.get('filename_hash','')} | {rec.get('width')}x{rec.get('height')} {rec.get('format_kind','')}")

    def native_tex_browser_convert_selected(self):
        rec=self.native_tex_browser_selected
        if not rec:
            messagebox.showinfo('Browse + Image','Select one .TEX file first.')
            return
        self.convert_dds_using_native_tex_record(rec,parent=self.winfo_toplevel())

    def native_tex_browser_export_selected_tex(self):
        rec=self.native_tex_browser_selected
        if not rec:
            messagebox.showinfo('Browse + Image','Select one .TEX file first.')
            return
        src=Path(rec['path'])
        if not src.is_file():
            messagebox.showerror('Export Selected .TEX failed',f'Selected .TEX no longer exists:\n\n{src}')
            return
        initial=Path(self.last_export_dir) if self.last_export_dir and Path(self.last_export_dir).exists() else src.parent
        out=filedialog.asksaveasfilename(
            title='Export Selected .TEX',initialdir=str(initial),initialfile=src.name,
            defaultextension='.tex',filetypes=[('SM3 loose native TEX','*.tex'),('All files','*.*')],
        )
        if not out:
            return
        dst=Path(out)
        try:
            if src.resolve()==dst.resolve():
                raise ValueError('Choose a different output location. The selected source .TEX is already at that path.')
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
            self.last_export_dir=str(dst.parent)
            self.output_var.set(str(dst.parent))
            self.set_status(f'Exported selected .TEX unchanged: {src.name} -> {dst}')
            messagebox.showinfo('Selected .TEX exported',f'Exact loose SM3 .TEX copied byte-for-byte unchanged:\n\n{dst}')
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror('Export Selected .TEX failed',str(exc))
            self.set_status(f'Export Selected .TEX failed: {exc}')

    def native_tex_browser_export_selected_dds(self):
        rec=self.native_tex_browser_selected
        if not rec:
            messagebox.showinfo('Browse + Image','Select one .TEX file first.')
            return
        src=Path(rec['path'])
        initial=Path(self.last_export_dir) if self.last_export_dir and Path(self.last_export_dir).exists() else src.parent
        out=filedialog.asksaveasfilename(
            title='Export Selected .TEX to DDS',initialdir=str(initial),initialfile=src.with_suffix('.dds').name,
            defaultextension='.dds',filetypes=[('DirectDraw Surface','*.dds'),('All files','*.*')],
        )
        if not out:
            return
        try:
            report=export_native_tex_record_to_dds(rec,Path(out))
            dst=Path(report['dds'])
            self.last_export_dir=str(dst.parent)
            self.output_var.set(str(dst.parent))
            self.set_status(f"Exported selected .TEX to DDS: {src.name} -> {dst.name}")
            messagebox.showinfo('DDS exported',
                'Selected SM3 .TEX exported to DDS without pixel re-encoding:\n\n'
                f"{dst}\n\n{report['width']}x{report['height']} | {report['format']} | {report['mips']} mip(s)")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror('Export to DDS failed',str(exc))
            self.set_status(f'Export to DDS failed: {exc}')

    def native_tex_browser_open_output(self):
        raw=self.output_var.get().strip() or self.last_export_dir or ''
        if not raw or not Path(raw).is_dir():
            messagebox.showinfo('Browse + Image','Export a .TEX or DDS first, or choose an output folder.')
            return
        open_path(Path(raw))

    def native_tex_browser_reveal_selected(self):
        rec=self.native_tex_browser_selected
        if not rec:
            messagebox.showinfo('Browse + Image','Select one .TEX file first.')
            return
        open_path(Path(rec['path']).parent)

    def convert_dds_using_native_tex_record(self,rec:dict,parent=None):
        """Convert a DDS using any selected loose/extracted .tex as the target identity shell."""
        if str(rec.get('platform','PC')).upper()=='X360':
            messagebox.showinfo(
                'Xbox TEX is read-only for now',
                'Xbox 360 texture preview and base-mip DDS export are enabled.\n\n'
                'DDS -> Xbox .TEX reimport is intentionally disabled until the reverse Xenos tiling/repack path is proven safe.',
                parent=parent,
            )
            return
        start=self.replacement_folder_var.get().strip() or self.last_export_dir or str(Path(rec['path']).parent)
        dds=filedialog.askopenfilename(
            title=f"Select DDS for {rec.get('asset','texture')}",
            initialdir=start if start and Path(start).exists() else None,
            filetypes=[('DDS texture','*.dds'),('All files','*.*')],
            parent=parent,
        )
        if not dds: return
        default_name=f"{rec['filename_hash']}.{clean_name(rec.get('asset') or 'texture','texture')}.tex"
        initial=Path(self.last_export_dir) if self.last_export_dir and Path(self.last_export_dir).exists() else Path(rec['path']).parent
        out=filedialog.asksaveasfilename(
            title='Save universal SM3 loose .TEX',initialdir=str(initial),initialfile=default_name,
            defaultextension='.tex',filetypes=[('SM3 loose native TEX','*.tex'),('All files','*.*')],parent=parent,
        )
        if not out: return
        try:
            report=write_native_tex_from_dds_using_native_tex_shell(Path(rec['path']),Path(dds),Path(out))
            rp=Path(report['tex']+'.json'); rp.write_text(json.dumps(report,indent=2),encoding='utf-8')
            self.last_export_dir=str(Path(report['tex']).parent)
            self.replacement_folder_var.set(self.last_export_dir)
            self.set_status(f"Universal .TEX created: {Path(report['tex']).name} | {report['width']}x{report['height']} {report['format']}")
            messagebox.showinfo('Universal .TEX created',
                f"Target: {report['asset']}\nHash: {report['hash']}\n"
                f"DDS: {report['width']}x{report['height']} {report['format']} | mips {report['mips']}\n"
                f"PHYS payload: {report['phys_bytes']} bytes\n\nOutput:\n{report['tex']}\n\n"
                'The selected .TEX identity/header was preserved and the output now also preserves the original PHYS/no-PHYS layout and mip-count contract when available.',parent=parent)
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('.TEX conversion failed',str(exc),parent=parent)
            self.set_status(f'.TEX conversion failed: {exc}')

    def convert_dds_to_native_tex_selected(self):
        """v5.2.111: universal selected-SM3-target DDS -> loose .tex."""
        target=self.resolve_current_selected_target()
        if not target:
            messagebox.showinfo(
                'Select target first',
                'Build Preview, select the TEX target row you want to replace, then use the .Tex tab again.\n\n'
                'This route uses the selected SM3 target name/hash, preserves its real IMG shell when available, and falls back safely when the old extractor-shell path is unavailable.'
            )
            return
        start=self.replacement_folder_var.get().strip() or self.last_export_dir or str(self._native_tex_default_dir())
        dds=filedialog.askopenfilename(
            title='Select edited DDS to wrap as loose .TEX',
            initialdir=start if start and Path(start).exists() else None,
            filetypes=[('DDS texture','*.dds'),('All files','*.*')],
        )
        if not dds:
            return
        try:
            asset=str(target.get('asset') or 'texture')
            h=parse_sm3_hash_value(target.get('filename_hash'),asset)
            safe=clean_name(asset,'texture')
            default_name=f'0x{h:08X}.{safe}.tex'
            out=self._choose_native_tex_save_path(default_name)
            if not out:
                return
            pc=Path(self.pcpack_var.get())
            report=write_native_tex_from_dds_using_extractor_shell(pc,target,Path(dds),out)
            actual_out=Path(report['tex'])
            report_path=Path(str(actual_out)+'.json')
            report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
            self.last_export_dir=str(actual_out.parent)
            self.replacement_folder_var.set(str(actual_out.parent))
            self.set_status(
                f'.TEX WRAP complete: {asset} | 0x{h:08X} | '
                f"{report['width']}x{report['height']} {report['format']} mips {report['mips']} | {actual_out.name}"
            )
            messagebox.showinfo(
                '.TEX conversion complete',
                'Universal SM3 native .TEX created successfully.\n\n'
                f"Target: {asset}\nHash: 0x{h:08X}\n"
                f"DDS: {report['width']}x{report['height']} {report['format']} | mips {report['mips']}\n"
                f"PHYS: {report['phys_bytes']} bytes\n\n"
                f"Output:\n{actual_out}\n\n"
                f"Shell mode: {report.get('component0_source','')}\n"
                'The selected target identity is preserved; width/height/mips/format are updated for the new DDS.\n\n'
                'This .Tex workflow has NO original PCPACK component1 same-size restriction. '
                'Use the output with RaimiHook Stage 2B NativeTEX.'
            )
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('.TEX conversion failed',str(e))
            self.set_status(f'.TEX conversion failed: {e}')

    def convert_dds_to_native_tex_auto(self):
        """Legacy v5.2.107 synthetic-shell route; hidden from v5.2.108 normal UI."""
        start=self.replacement_folder_var.get().strip() or self.last_export_dir or str(self._native_tex_default_dir())
        dds=filedialog.askopenfilename(
            title='Select DDS to wrap as loose .TEX (auto name/hash)',
            initialdir=start if start and Path(start).exists() else None,
            filetypes=[('DDS texture','*.dds'),('All files','*.*')],
        )
        if not dds:
            return
        try:
            asset,h=native_tex_identity_from_dds_filename(Path(dds))
            safe=clean_name(asset,'texture')
            default_name=f'0x{h:08X}.{safe}.tex'
            out=self._choose_native_tex_save_path(default_name)
            if not out:
                return
            report=write_native_tex_from_dds(Path(dds),out,asset,h)
            report['identity_mode']='AUTO_FROM_DDS_FILENAME'
            report_path=out.with_suffix(out.suffix+'.json')
            report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
            self.last_export_dir=str(out.parent)
            self.replacement_folder_var.set(str(out.parent))
            self.set_status(
                f'.TEX AUTO WRAP complete: {asset} | 0x{h:08X} | '
                f"{report['width']}x{report['height']} {report['format']} mips {report['mips']}"
            )
            messagebox.showinfo(
                '.TEX auto conversion complete',
                f"Detected resource: {asset}\nHash: 0x{h:08X}\n\n"
                f"Created:\n{out}\n\n"
                'For Toolkit-exported DDS names such as 0xHASH.asset.ORIGINAL_EDIT_THIS.dds, '
                'the hash/name are recovered automatically.'
            )
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('.TEX auto conversion failed',str(e))
            self.set_status(f'.TEX auto conversion failed: {e}')

    def export_original_dds(self):
        target=self.resolve_current_selected_target()
        if not target:
            messagebox.showinfo('Select target','Select ONE texture target first, then click SINGLE SELECTED DDS EXPORT.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose output folder for DDS export') or '')
        if not str(outdir): return
        try:
            dds,raw,meta=export_original_component_as_dds(pc,target,outdir)
            key=target_edit_key(target)
            self.dds_export_history[key]=meta
            self.last_export_dir=str(Path(dds).parent)
            if not self.replacement_folder_var.get().strip():
                self.replacement_folder_var.set(str(Path(dds).parent))
            messagebox.showinfo(
                'SINGLE SELECTED DDS EXPORT complete',
                'Exported DDS and raw component1.\n\n'
                + 'DDS:\n' + str(dds) + '\n\n'
                + 'Raw:\n' + str(raw) + '\n\n'
                + 'Current workflow: edit/overwrite this DDS in Paint.NET/GIMP, then use editor-safe single-file or folder final patch. The new route can recover many editor DDS header/format/mip changes by rebuilding into SM3 target format.'
            )
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('DDS export failed',str(e))

    def export_all_dds(self):
        """v4.2: Export every detected TEX target as original-format DDS."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose output folder for legacy full DDS export') or '')
        if not str(outdir):
            return
        ok=[]; errors=[]
        try:
            ensure_dir(outdir)
            for t in self.targets:
                try:
                    dds,raw,meta=export_original_component_as_dds(pc,t,outdir)
                    key=target_edit_key(t)
                    self.dds_export_history[key]=meta
                    ok.append({
                        'asset':t.get('asset'),
                        'hash':t.get('filename_hash'),
                        'format':t.get('format_kind'),
                        'size':f"{t.get('width')}x{t.get('height')}",
                        'mips':t.get('mips'),
                        'component1_size':t.get('component1_size'),
                        'dds':str(dds),
                        'raw':str(raw),
                        'status':'EXPORTED'
                    })
                except Exception as exc:
                    errors.append({
                        'asset':t.get('asset'),
                        'hash':t.get('filename_hash'),
                        'error':str(exc),
                        'status':'ERROR'
                    })
            write_csv(outdir/'EXPORT_ALL_DDS_REPORT_v4_2.csv', ok+errors)
            summary={
                'tool':'THE_TEX_SWAPPER_TSGAMING264_v4_2',
                'mode':'EXPORT_ALL_DDS',
                'pcpack':str(pc),
                'output_folder':str(outdir),
                'exported_count':len(ok),
                'error_count':len(errors),
                'target_count':len(self.targets),
                'note':'Edit DDS files externally while preserving format/mips, then use legacy folder reimport.'
            }
            (outdir/'EXPORT_ALL_DDS_SUMMARY_v4_2.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            self.last_export_dir=str(outdir)
            self.replacement_folder_var.set(str(outdir))
            messagebox.showinfo('legacy full DDS export complete', f'Exported {len(ok)} DDS files. Errors: {len(errors)}\n\nFolder:\n{outdir}\n\nAfter editing, use legacy folder reimport.')
            self.set_status(f'legacy full DDS export complete: {len(ok)} exported, {len(errors)} errors. Folder: {outdir}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('legacy full DDS export failed',str(e))

    def export_all_header_locked_dds_manifest(self):
        """v5.2.33: Export target-name + exact-header locked DDS files and manifest."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose output folder for EDIT-READY DDS export') or '')
        if not str(outdir):
            return
        ok=[]; errors=[]
        try:
            ensure_dir(outdir)
            for t in self.targets:
                try:
                    dds,raw,meta=export_original_component_as_dds(pc,t,outdir)
                    info=parse_dds_header_file(Path(dds))
                    dds_bytes=Path(dds).read_bytes()
                    row={
                        'target_key':target_edit_key(t),
                        'asset':t.get('asset'),
                        'hash':t.get('filename_hash'),
                        'width':t.get('width'),
                        'height':t.get('height'),
                        'mips':t.get('mips'),
                        'format':t.get('format_kind'),
                        'component1_size':t.get('component1_size'),
                        'dds_filename':Path(dds).name,
                        'raw_filename':Path(raw).name,
                        'dds_header_size':info.get('header_size'),
                        'original_dds_header_sha256':sha256_bytes(dds_bytes[:info.get('header_size',128)]),
                        'original_dds_sha256':sha256_bytes(dds_bytes),
                        'original_component1_sha256':meta.get('original_component1_sha256',''),
                        'status':'EXPORTED_HEADER_LOCKED',
                    }
                    ok.append(row)
                except Exception as exc:
                    errors.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'error':str(exc),'status':'ERROR'})
            write_csv(outdir/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.csv', ok+errors)
            (outdir/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.json').write_text(json.dumps({'version':'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST_v5_2_33','pcpack':pc.name,'items':ok,'errors':errors},indent=2),encoding='utf-8')
            (outdir/'TEX_TARGET_REIMPORT_HEADER_RULES.txt').write_text(
                'TEX Target Header + Name Lock Rules\n'
                '===================================\n\n'
                'Use this folder for final-safe texture edits.\n'
                '- Keep the exported filename: 0xHASH.asset.ORIGINAL_EDIT_THIS.dds\n'
                '- Keep the DDS header exactly the same.\n'
                '- Keep width/height/mips/format/payload size exactly the same.\n'
                '- Reimport with FINAL EDITOR-SAFE REIMPORT -> WRITE PATCHED PCPACK.\n'
                '- Random DDS files, wrong names, wrong headers, wrong mips, or wrong payload sizes are blocked.\n',
                encoding='utf-8'
            )
            self.last_export_dir=str(outdir)
            self.replacement_folder_var.set(str(outdir))
            messagebox.showinfo('EDIT-READY DDS export complete', f'Exported {len(ok)} edit-ready DDS files. Errors: {len(errors)}\n\nFolder:\n{outdir}')
            self.set_status(f'EDIT-READY DDS export complete: {len(ok)} exported, {len(errors)} errors. Folder: {outdir}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('HEADER-LOCKED export failed',str(e))

    def normalize_gimp_dds_to_game_format_folder(self):
        """v5.2.34: normalize edited DDS files back to the exact SM3 target DDS header.

        Use after editing/overwriting exported DDS files in GIMP/Paint.NET/other editors
        when the image data is intended for the same target, but the DDS header was
        rewritten. This does not resize/recompress; it only preserves edited payload
        while restoring the game/tool target header.
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=Path(filedialog.askdirectory(title='Choose edited DDS folder to normalize to SM3 game format', initialdir=start_dir if start_dir else None) or '')
        if not str(folder):
            return
        src_files=sorted([p for p in folder.rglob('*.dds') if p.is_file()])
        src_files=[p for p in src_files if not any(part.upper().endswith('REPORTS') or 'NORMALIZED' in part.upper() for part in p.parts)]
        if not src_files:
            messagebox.showinfo('No DDS files',f'No DDS files found in:\n{folder}')
            return
        outdir=ensure_dir(folder/'GAME_FORMAT_NORMALIZED_DDS')
        ready=[]; blocked=[]; manifest_items=[]
        used=set()
        for src in src_files:
            target, reason = _filename_direct_target_match(src, self.targets)
            if not target:
                blocked.append({'file':str(src),'reason':'NO_TARGET_NAME_OR_HASH_LOCK','status':'BLOCKED'})
                continue
            key=target_edit_key(target)
            if key in used:
                blocked.append({'file':str(src),'asset':target.get('asset'),'reason':'DUPLICATE_TARGET_ALREADY_USED','status':'BLOCKED'})
                continue
            try:
                normalized, row = normalize_dds_to_target_game_format(src, target, outdir)
                used.add(key)
                row['match_reason']=reason
                ready.append(row)
                manifest_items.append({
                    'target_key':target_edit_key(target),
                    'asset':target.get('asset'),
                    'hash':target.get('filename_hash'),
                    'width':target.get('width'),
                    'height':target.get('height'),
                    'mips':target.get('mips'),
                    'format':target.get('format_kind'),
                    'component1_size':target.get('component1_size'),
                    'dds_filename':Path(normalized).name,
                    'original_dds_header_sha256':row.get('target_header_sha256',''),
                    'original_dds_sha256':sha256_file(Path(normalized)),
                    'original_component1_sha256':row.get('normalized_payload_sha256',''),
                    'status':'NORMALIZED_GAME_FORMAT_DDS_READY_FOR_HEADER_NAME_LOCKED_REIMPORT',
                })
            except Exception as exc:
                blocked.append({'file':str(src),'asset':target.get('asset') if 'target' in locals() and target else '', 'reason':str(exc),'status':'BLOCKED'})
        write_csv(outdir/'GIMP_GAME_FORMAT_NORMALIZE_READY.csv', ready)
        write_csv(outdir/'GIMP_GAME_FORMAT_NORMALIZE_BLOCKED.csv', blocked)
        write_csv(outdir/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.csv', manifest_items)
        (outdir/'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST.json').write_text(json.dumps({'version':'TEX_TARGET_HEADER_NAME_LOCK_MANIFEST_v5_2_34_NORMALIZED_GAME_FORMAT','items':manifest_items,'errors':blocked},indent=2),encoding='utf-8')
        summary={
            'version':'v5.2.34',
            'mode':'GIMP_OVERWRITE_GAME_FORMAT_NORMALIZER',
            'source_folder':str(folder),
            'normalized_folder':str(outdir),
            'ready_count':len(ready),
            'blocked_count':len(blocked),
            'rule':'target name/hash + same dimensions/mips/format/payload required; output DDS uses SM3 target header plus edited payload',
        }
        (outdir/'GIMP_GAME_FORMAT_NORMALIZE_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (outdir/'GIMP_GAME_FORMAT_NORMALIZE_RULES.txt').write_text(
            'GIMP / editor overwrite recovery route\n'
            '====================================\n\n'
            'This folder contains DDS files rebuilt as: SM3 target DDS header + edited DDS payload.\n'
            'Use it when Paint.NET/GIMP/editor overwrote the exported DDS and rewrote header bytes.\n\n'
            'Required before normalization:\n'
            '- filename must still identify the target hash/name\n'
            '- width/height/mips/format must match the SM3 target\n'
            '- payload size must match the target component1 size\n'
            '- no resize/recompression/mipmap generation is performed here\n\n'
            'Next step:\n'
            '- Run FINAL EDITOR-SAFE REIMPORT -> WRITE PATCHED PCPACK using this folder.\n',
            encoding='utf-8'
        )
        self.last_export_dir=str(outdir)
        self.replacement_folder_var.set(str(outdir))
        messagebox.showinfo('Editor DDS normalize complete', f'Normalized {len(ready)} DDS files. Blocked: {len(blocked)}\n\nFolder:\n{outdir}\n\nNext: run FINAL EDITOR-SAFE REIMPORT -> WRITE PATCHED PCPACK using this folder.')
        self.set_status(f'Editor DDS normalize complete: {len(ready)} ready, {len(blocked)} blocked. Folder: {outdir}')


    def multiple_file_editor_safe_patch_write_pcpack(self):
        """v5.2.144: patch several explicitly selected edited files into one NEW PCPACK.

        This is the middle ground between the single-file test route and the folder-wide
        final reimport route. The user Ctrl/Shift-selects only the files they want.

        Rules:
        - every selected file must identify its SM3 target by exported hash/name
        - DDS files that already match the target patch directly
        - harmless DDS header rewrites are normalized back to the target header
        - editor-overwritten DDS files and PNG/BMP/JPG/JPEG inputs are rebuilt from
          visible pixels into the target SM3 width/height/mips/format/payload
        - duplicate mappings to the same target are blocked
        - one NEW PCPACK is written; the original PCPACK is never modified
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing. Load a clean original PCPACK first.')
            return

        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        chosen=filedialog.askopenfilenames(
            title='Choose MULTIPLE edited DDS/images to patch into one NEW PCPACK',
            initialdir=start_dir if start_dir else None,
            filetypes=[
                ('DDS / image files','*.dds *.png *.bmp *.jpg *.jpeg'),
                ('DDS files','*.dds'),
                ('Image files','*.png *.bmp *.jpg *.jpeg'),
                ('All files','*.*'),
            ]
        )
        if not chosen:
            return
        src_files=[Path(x) for x in chosen if str(x).strip()]
        src_files=[x for x in src_files if x.exists() and x.is_file()]
        if not src_files:
            messagebox.showinfo('No valid files','No existing DDS/image files were selected.')
            return

        raw_output=self.output_var.get().strip()
        try:
            base_dir=resolve_user_output_base(Path(raw_output)) if raw_output else src_files[0].parent
        except Exception:
            base_dir=Path(raw_output) if raw_output else src_files[0].parent
        base_dir=ensure_dir(base_dir)
        work_dir=ensure_dir(base_dir/'MULTIPLE_FILE_PATCH_WORK')
        norm_dir=ensure_dir(work_dir/'AUTO_NORMALIZED_DDS')
        rebuild_dir=ensure_dir(work_dir/'EDITOR_SAFE_REBUILT_DDS')
        report_dir=ensure_dir(work_dir/'REPORTS')

        patch_items=[]
        ready=[]
        blocked=[]
        normalized_rows=[]
        rebuilt_rows=[]
        used=set()
        manifest_cache={}

        for source in src_files:
            target, reason = _filename_direct_target_match(source, self.targets)
            if not target:
                blocked.append({
                    'source_file':str(source),
                    'asset':'',
                    'hash':'',
                    'reason':'NO_TARGET_NAME_OR_HASH_LOCK',
                    'status':'BLOCKED_MULTIPLE_FILE_PATCH',
                })
                continue

            key=target_edit_key(target)
            if key in used:
                blocked.append({
                    'source_file':str(source),
                    'asset':target.get('asset'),
                    'hash':target.get('filename_hash'),
                    'reason':'DUPLICATE_TARGET_ALREADY_USED',
                    'status':'BLOCKED_MULTIPLE_FILE_PATCH',
                })
                continue

            # Respect strict diffuse-only mode without forcing a warning dialog for every file.
            if self.strict_diffuse_var.get() and not is_diffuse_like_target(target):
                blocked.append({
                    'source_file':str(source),
                    'asset':target.get('asset'),
                    'hash':target.get('filename_hash'),
                    'reason':'STRICT_DIFFUSE_BLOCKED: '+unsafe_target_reason(target),
                    'status':'BLOCKED_MULTIPLE_FILE_PATCH',
                })
                continue

            manifest_row={}
            parent_key=str(source.parent.resolve())
            if parent_key not in manifest_cache:
                mp, rows=find_header_lock_manifest(source.parent)
                manifest_cache[parent_key]=(mp, manifest_rows_by_filename(rows))
            _manifest_path, manifest_by_file=manifest_cache[parent_key]
            manifest_row=manifest_by_file.get(source.name.lower(), {})

            final_dds=None
            action=''
            normalize_reason=''
            info={}
            try:
                if source.suffix.lower()=='.dds':
                    try:
                        info, descriptor_problems=validate_dds_matches_target(source,target,strict=False)
                    except Exception as parse_exc:
                        descriptor_problems=['DDS_PARSE_FAILED_FOR_DESCRIPTOR_CHECK: '+str(parse_exc)]

                    if descriptor_problems:
                        rebuilt, row = rebuild_source_pixels_to_target_game_dds(
                            source, target, rebuild_dir, force_opaque=bool(self.force_opaque_var.get())
                        )
                        row['match_reason']=reason
                        row['source_descriptor_problems']='; '.join(descriptor_problems)
                        row['source_action']='MULTIPLE_FILE_EDITOR_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                        rebuilt_rows.append(row)
                        final_dds=Path(rebuilt)
                        action='MULTIPLE_FILE_EDITOR_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                        normalize_reason='Source DDS descriptor changed in an editor; rebuilt visible pixels into the selected SM3 target game DDS format.'
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            raise ValueError('Rebuilt DDS still failed header lock: ' + '; '.join(final_problems))
                    else:
                        header=dds_header_info_for_target(source,target)
                        if not header.get('actual_header_matches_expected'):
                            normalized, row = normalize_dds_to_target_game_format(source, target, norm_dir)
                            row['match_reason']=reason
                            row['source_action']='MULTIPLE_FILE_AUTO_NORMALIZED_HEADER_RECOVERY'
                            normalized_rows.append(row)
                            final_dds=Path(normalized)
                            action='MULTIPLE_FILE_AUTO_NORMALIZED_HEADER_RECOVERY'
                            normalize_reason='DDS descriptor/payload matched but header differed; restored the SM3 target header before patching.'
                            info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                            if final_problems:
                                raise ValueError('Normalized DDS still failed header lock: ' + '; '.join(final_problems))
                        else:
                            final_dds=source
                            action='MULTIPLE_FILE_PATCH_DIRECT_HEADER_OK'
                            info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                            if final_problems:
                                raise ValueError('DDS failed final header lock: ' + '; '.join(final_problems))
                elif source.suffix.lower() in IMAGE_EXTS:
                    rebuilt, row = rebuild_source_pixels_to_target_game_dds(
                        source, target, rebuild_dir, force_opaque=bool(self.force_opaque_var.get())
                    )
                    row['match_reason']=reason
                    row['source_action']='MULTIPLE_FILE_IMAGE_REBUILT_FROM_SOURCE_PIXELS'
                    rebuilt_rows.append(row)
                    final_dds=Path(rebuilt)
                    action='MULTIPLE_FILE_IMAGE_REBUILT_FROM_SOURCE_PIXELS'
                    normalize_reason='Image source supplied visible pixels; rebuilt into the SM3 target game DDS format before patching.'
                    info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                    if final_problems:
                        raise ValueError('Image-rebuilt DDS still failed header lock: ' + '; '.join(final_problems))
                else:
                    raise ValueError('Unsupported source type. Use DDS, PNG, BMP, JPG, or JPEG.')

                if manifest_row and manifest_row.get('original_dds_header_sha256') and manifest_row.get('original_dds_header_sha256') != info.get('header_sha256'):
                    raise ValueError('Final DDS header does not match the export manifest header.')

                patch_items.append((target, final_dds, manifest_row))
                used.add(key)
                ready.append({
                    'source_file':str(source),
                    'final_dds_for_patch':str(final_dds),
                    'asset':target.get('asset'),
                    'hash':target.get('filename_hash'),
                    'match_reason':reason,
                    'action':action,
                    'normalize_reason':normalize_reason,
                    'width':info.get('width'),
                    'height':info.get('height'),
                    'mips':info.get('mips'),
                    'format_kind':info.get('format_kind'),
                    'payload_size':info.get('payload_size'),
                    'header_sha256':info.get('header_sha256'),
                    'expected_header_sha256':info.get('expected_header_sha256'),
                    'status':'READY_MULTIPLE_FILE_PATCH',
                })
            except Exception as exc:
                blocked.append({
                    'source_file':str(source),
                    'asset':target.get('asset') if target else '',
                    'hash':target.get('filename_hash') if target else '',
                    'reason':str(exc).replace('\n',' | '),
                    'status':'BLOCKED_MULTIPLE_FILE_PATCH',
                })

        write_csv(report_dir/'MULTIPLE_FILE_PATCH_READY.csv', ready)
        write_csv(report_dir/'MULTIPLE_FILE_PATCH_BLOCKED.csv', blocked)
        write_csv(report_dir/'MULTIPLE_FILE_AUTO_NORMALIZED.csv', normalized_rows)
        write_csv(report_dir/'MULTIPLE_FILE_EDITOR_SAFE_REBUILT.csv', rebuilt_rows)
        summary={
            'version':'v5.2.146',
            'mode':'MULTIPLE_FILE_EDITOR_SAFE_PATCH',
            'selected_file_count':len(src_files),
            'ready_count':len(patch_items),
            'blocked_count':len(blocked),
            'direct_header_ok_count':sum(1 for r in ready if r.get('action')=='MULTIPLE_FILE_PATCH_DIRECT_HEADER_OK'),
            'auto_normalized_count':len(normalized_rows),
            'editor_safe_rebuilt_count':len(rebuilt_rows),
            'rule':'user selects explicit files; target hash/name lock required; editor-safe normalization/rebuild uses the same target format rules as the single/folder routes; output is one NEW PCPACK',
        }
        (report_dir/'MULTIPLE_FILE_PATCH_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (report_dir/'MULTIPLE_FILE_PATCH_RULES.txt').write_text(
            'MULTIPLE FILE EDITOR-SAFE PATCH - v5.2.146\n'
            '=========================================\n\n'
            'Use Ctrl/Shift in the file picker to select only the edited textures you want to patch.\n'
            '- Filename hash/name identifies each SM3 target.\n'
            '- Exact target-format DDS patches directly.\n'
            '- Header-only editor changes are normalized.\n'
            '- Wrong-format/mip editor DDS and PNG/BMP/JPG/JPEG inputs are rebuilt from visible pixels into the SM3 target format.\n'
            '- Duplicate mappings and unidentified files are blocked.\n'
            '- Original PCPACK is never modified. One NEW PCPACK contains all ready selected files.\n',
            encoding='utf-8'
        )

        if not patch_items:
            messagebox.showwarning(
                'No multiple-file patches ready',
                f'None of the {len(src_files)} selected files passed the editor-safe rules.\n\nReport:\n{report_dir}'
            )
            self.set_status(f'MULTIPLE FILE PATCH found no ready files. Report: {report_dir}')
            return

        final_out_dir=ensure_dir(base_dir/'MULTIPLE_FILE_PATCH_OUTPUT')
        default_name=pc.stem+'_PATCHED_MULTIPLE_SELECTED_FILES'+pc.suffix
        out_path=final_out_dir/default_name
        if out_path.exists():
            base=out_path.stem
            ext=out_path.suffix
            idx=1
            while (final_out_dir/f'{base}_{idx:03d}{ext}').exists():
                idx+=1
            out_path=final_out_dir/f'{base}_{idx:03d}{ext}'

        msg=(
            f'{len(patch_items)} of {len(src_files)} selected files are ready.\n'
            f'Direct header OK: {summary["direct_header_ok_count"]}\n'
            f'Auto-normalized: {summary["auto_normalized_count"]}\n'
            f'Editor-safe rebuilt: {summary["editor_safe_rebuilt_count"]}\n'
            f'Blocked: {summary["blocked_count"]}\n\n'
            'The tool will write ONE NEW patched PCPACK here:\n'
            f'{out_path}\n\n'
            'Original PCPACK will NOT be modified.'
        )
        if not messagebox.askyesno('Confirm MULTIPLE FILE patch', msg):
            return

        try:
            log=copy_and_patch_pcpack_header_locked_dds_many(pc, patch_items, out_path)
            log['mode']='MULTIPLE_FILE_EDITOR_SAFE_PATCH_V5_2_144'
            log['multiple_file_scan_summary']=summary
            log['final_output_folder']=str(final_out_dir)
            (final_out_dir/(out_path.stem+'_MULTIPLE_FILE_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            (final_out_dir/'00_MULTIPLE_FILE_PATCHED_PCPACK_IS_HERE.txt').write_text(
                'MULTIPLE FILE PATCH COMPLETE\n'
                '============================\n\n'
                f'Your patched PCPACK is here:\n{out_path}\n\n'
                f'Patched file count: {log.get("patch_count",len(patch_items))}\n'
                f'Blocked selected file count: {summary["blocked_count"]}\n\n'
                'Use this NEW PCPACK copy for testing. The original PCPACK was not modified.\n',
                encoding='utf-8'
            )
            (final_out_dir/'FINAL_MULTIPLE_FILE_PATCHED_PCPACK_PATH.txt').write_text(str(out_path)+'\n',encoding='utf-8')
            self.last_export_dir=str(final_out_dir)
            try:
                open_path(final_out_dir)
            except Exception:
                pass
            messagebox.showinfo(
                'MULTIPLE FILE PCPACK WRITTEN',
                f'Patched {log.get("patch_count",len(patch_items))} selected files into ONE NEW PCPACK.\n\n'
                f'Blocked: {summary["blocked_count"]}\n\n'
                f'YOUR FINAL PCPACK IS HERE:\n{out_path}\n\n'
                f'Reports:\n{report_dir}'
            )
            self.set_status(f'MULTIPLE FILE PCPACK WRITTEN: {len(patch_items)} items -> {out_path}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('Multiple file patch failed', str(e))

    def final_safe_reimport_auto_normalize_folder(self):
        """v5.2.38: one-button final DDS reimport with editor-safe suit rebuild.

        This is the creator-safe route for edited DDS folders:
        - target must be locked by SM3 hash/name in the filename
        - exact/header-locked DDS files patch directly
        - header-only changed DDS files are normalized as target header + edited payload
        - Paint.NET/GIMP/editor overwritten DDS files with wrong format/mips/payload are decoded
          from visible pixels, then rebuilt into the SM3 target game format/mip shell
        - original PCPACK is never modified; output is one new patched PCPACK copy
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=Path(filedialog.askdirectory(title='Choose edited DDS folder for FINAL EDITOR-SAFE REIMPORT', initialdir=start_dir if start_dir else None) or '')
        if not str(folder):
            return
        all_dds=sorted([p for p in folder.rglob('*.dds') if p.is_file()])
        blocked_parts=('REPORTS','REIMPORT_REPORTS','HEADER_NAME_LOCKED_REIMPORT_REPORTS','FINAL_GAME_FORMAT_REIMPORT_WORK','GIMP_SAFE_REBUILT_DDS','AUTO_NORMALIZED_DDS')
        # v5.2.36: filter by path relative to the selected folder, not by the full
        # absolute path. This allows the user to select an already-created
        # GAME_FORMAT_NORMALIZED_DDS or AUTO_NORMALIZED_DDS folder directly.
        # When the parent folder is selected, nested old work/report folders are
        # still skipped so the tool does not double-patch generated copies.
        src_files=[]
        for pth in all_dds:
            try:
                rel_parts=[part.upper() for part in pth.relative_to(folder).parts[:-1]]
            except Exception:
                rel_parts=[part.upper() for part in pth.parts[:-1]]
            if any(part in blocked_parts for part in rel_parts):
                continue
            src_files.append(pth)
        if not src_files:
            messagebox.showinfo('No DDS files',f'No DDS files found in:\n{folder}\n\nTip: v5.2.38 expects the folder containing your edited/overwritten suit DDS files and writes the final .PCPACK into FINAL_PATCHED_PCPACK_OUTPUT.')
            return

        selected_folder_kind='NORMALIZED_GAME_FORMAT_DDS_INPUT' if folder.name.upper() in ('GAME_FORMAT_NORMALIZED_DDS','AUTO_NORMALIZED_DDS') else 'EDITED_DDS_INPUT'
        work_dir=ensure_dir(folder/'FINAL_GAME_FORMAT_REIMPORT_WORK')
        norm_dir=ensure_dir(work_dir/'AUTO_NORMALIZED_DDS')
        rebuild_dir=ensure_dir(work_dir/'GIMP_SAFE_REBUILT_DDS')
        report_dir=ensure_dir(work_dir/'REPORTS')
        manifest_path, manifest_rows = find_header_lock_manifest(folder)
        manifest_by_file=manifest_rows_by_filename(manifest_rows)

        patch_items=[]
        ready=[]
        skipped=[]
        normalized_rows=[]
        gimp_rebuilt_rows=[]
        used=set()

        for src in src_files:
            target, reason = _filename_direct_target_match(src, self.targets)
            if not target:
                skipped.append({'file':str(src),'reason':'NO_TARGET_NAME_OR_HASH_LOCK','status':'BLOCKED'})
                continue
            key=target_edit_key(target)
            if key in used:
                skipped.append({'file':str(src),'asset':target.get('asset'),'reason':'DUPLICATE_TARGET_ALREADY_USED','status':'BLOCKED'})
                continue
            manifest_row=manifest_by_file.get(src.name.lower(), {})
            try:
                info, descriptor_problems=validate_dds_matches_target(src,target,strict=False)
                final_dds=src
                action='PATCH_DIRECT_HEADER_OK'
                normalize_reason=''

                if descriptor_problems:
                    # v5.2.38: GIMP can overwrite a DDS into BGRA/no-mip/wrong payload.
                    # Header-only normalization cannot fix that after the fact, so decode
                    # the edited visible pixels and rebuild a new DDS using the SM3 target shell.
                    try:
                        rebuilt, rebuild_row = rebuild_source_pixels_to_target_game_dds(
                            src, target, rebuild_dir, force_opaque=bool(self.force_opaque_var.get())
                        )
                        rebuild_row['match_reason']=reason
                        rebuild_row['source_descriptor_problems']='; '.join(descriptor_problems)
                        rebuild_row['source_action']='GIMP_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                        gimp_rebuilt_rows.append(rebuild_row)
                        final_dds=Path(rebuilt)
                        action='GIMP_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                        normalize_reason='Source DDS did not match SM3 descriptor after Paint.NET/GIMP/editor overwrite; rebuilt visible pixels into SM3 target width/height/mips/format/payload.'
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            skipped.append({'file':str(src),'rebuilt_dds':str(final_dds),'asset':target.get('asset'),'reason':'; '.join(final_problems),'status':'BLOCKED_GIMP_SAFE_REBUILD_STILL_NOT_HEADER_LOCKED'})
                            continue
                    except Exception as rebuild_exc:
                        skipped.append({
                            'file':str(src),
                            'asset':target.get('asset'),
                            'reason':'; '.join(descriptor_problems) + ' | GIMP_SAFE_REBUILD_FAILED: ' + str(rebuild_exc).replace('\n',' | '),
                            'status':'BLOCKED_DESCRIPTOR_MISMATCH_AND_REBUILD_FAILED'
                        })
                        continue
                else:
                    header=dds_header_info_for_target(src,target)
                    if not header.get('actual_header_matches_expected'):
                        normalized, norm_row = normalize_dds_to_target_game_format(src, target, norm_dir)
                        norm_row['match_reason']=reason
                        norm_row['source_action']='AUTO_NORMALIZED_HEADER_RECOVERY'
                        normalized_rows.append(norm_row)
                        final_dds=Path(normalized)
                        action='AUTO_NORMALIZED_HEADER_RECOVERY'
                        normalize_reason='DDS descriptor/payload matched but header differed; restored SM3 target/export header before patching.'
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            skipped.append({'file':str(src),'normalized_dds':str(final_dds),'asset':target.get('asset'),'reason':'; '.join(final_problems),'status':'BLOCKED_NORMALIZED_STILL_NOT_HEADER_LOCKED'})
                            continue
                    else:
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            skipped.append({'file':str(src),'asset':target.get('asset'),'reason':'; '.join(final_problems),'status':'BLOCKED_HEADER_LOCKED_VALIDATION'})
                            continue

                if manifest_row and manifest_row.get('original_dds_header_sha256') and manifest_row.get('original_dds_header_sha256') != info.get('header_sha256'):
                    skipped.append({'file':str(src),'final_dds':str(final_dds),'asset':target.get('asset'),'reason':'Final DDS header does not match manifest/export header','status':'BLOCKED_MANIFEST_HEADER_MISMATCH'})
                    continue

                patch_items.append((target, final_dds, manifest_row))
                used.add(key)
                ready.append({
                    'file':str(src),
                    'final_dds_for_patch':str(final_dds),
                    'asset':target.get('asset'),
                    'hash':target.get('filename_hash'),
                    'match_reason':reason,
                    'action':action,
                    'normalize_reason':normalize_reason,
                    'width':info.get('width'),
                    'height':info.get('height'),
                    'mips':info.get('mips'),
                    'format_kind':info.get('format_kind'),
                    'payload_size':info.get('payload_size'),
                    'header_sha256':info.get('header_sha256'),
                    'expected_header_sha256':info.get('expected_header_sha256'),
                    'status':'READY_FINAL_SAFE_REIMPORT',
                })
            except Exception as exc:
                skipped.append({'file':str(src),'asset':target.get('asset') if target else '', 'reason':str(exc),'status':'BLOCKED_EXCEPTION'})

        write_csv(report_dir/'FINAL_SAFE_REIMPORT_READY.csv', ready)
        write_csv(report_dir/'FINAL_SAFE_REIMPORT_BLOCKED.csv', skipped)
        write_csv(report_dir/'FINAL_SAFE_AUTO_NORMALIZED.csv', normalized_rows)
        write_csv(report_dir/'FINAL_SAFE_GIMP_SAFE_REBUILT.csv', gimp_rebuilt_rows)
        summary={
            'version':'v5.2.40',
            'mode':'FINAL_EDITOR_SAFE_DDS_REIMPORT_AUTO_REBUILD',
            'input_kind':selected_folder_kind,
            'source_folder':str(folder),
            'manifest':str(manifest_path) if manifest_path else '',
            'ready_count':len(patch_items),
            'blocked_count':len(skipped),
            'auto_normalized_count':len(normalized_rows),
            'gimp_safe_rebuilt_count':len(gimp_rebuilt_rows),
            'direct_header_ok_count':sum(1 for r in ready if r.get('action')=='PATCH_DIRECT_HEADER_OK'),
            'rule':'target hash/name required; exact-header DDS patches direct; safe header-changed DDS is normalized; Paint.NET/GIMP/editor overwritten DDS with wrong descriptor is decoded from visible pixels and rebuilt into target SM3 width/height/mips/format/payload before patching',
        }
        (report_dir/'FINAL_SAFE_REIMPORT_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (report_dir/'FINAL_SAFE_REIMPORT_RULES.txt').write_text(
            'FINAL EDITOR-SAFE DDS REIMPORT - v5.2.40\n'
            '=================================\n\n'
            'Use this after EXPORT EDIT-READY DDS + MANIFEST and external DDS editing. It also accepts overwritten GIMP DDS files directly.\n\n'
            'Allowed:\n'
            '- same target hash/name in filename\n'
            '- same width/height/mip count/format\n'
            '- same component1 payload size\n'
            '- exact SM3 DDS header, or safe header-only recovery using SM3 target header + edited payload\n\n'
            'Blocked:\n'
            '- wrong target name/hash\n'
            '- wrong dimensions, mip count, DDS format, or payload size\n'
            '- duplicate mappings to the same target\n'
            '- any file that would require resize/recompress/mipmap generation/guessing\n\n'
            'Patch output is always one NEW PCPACK copy. Original PCPACK is not modified. Editor-safe rebuild may recompress the visible pixels into SM3 target format.\n',
            encoding='utf-8'
        )

        if not patch_items:
            messagebox.showwarning('No final-safe patches',f'No DDS files passed final-safe checks. Blocked: {len(skipped)}\n\nReport:\n{report_dir}')
            self.set_status(f'FINAL SAFE REIMPORT found no safe patches. Report: {report_dir}')
            return
        # v5.2.37: do not rely on a Save As dialog for the final pack.
        # The user was seeing only DDS output after the final route, so the tool now
        # auto-creates a loud output folder beside the selected DDS folder and writes
        # the patched .PCPACK there every time.
        final_out_dir=ensure_dir(folder/'FINAL_PATCHED_PCPACK_OUTPUT')
        default_name=pc.stem+'_PATCHED_FINAL_SAFE_DDS'+pc.suffix
        out_path=final_out_dir/default_name
        if out_path.exists():
            base=out_path.stem
            ext=out_path.suffix
            idx=1
            while (final_out_dir/f'{base}_{idx:03d}{ext}').exists():
                idx+=1
            out_path=final_out_dir/f'{base}_{idx:03d}{ext}'

        msg=(
            f'{len(patch_items)} DDS files passed FINAL SAFE checks.\n'
            f'Direct header OK: {summary["direct_header_ok_count"]}\n'
            f'Auto-normalized header recovery: {summary["auto_normalized_count"]}\n'
            f'Editor-safe rebuilt from pixels: {summary["gimp_safe_rebuilt_count"]}\n'
            f'Blocked: {len(skipped)}\n\n'
            'The tool will now WRITE ONE NEW patched PCPACK automatically here:\n'
            f'{out_path}\n\n'
            'Original PCPACK will NOT be modified.'
        )
        if not messagebox.askyesno('Confirm FINAL SAFE DDS reimport', msg):
            return
        try:
            log=copy_and_patch_pcpack_header_locked_dds_many(pc, patch_items, out_path)
            log['mode']='FINAL_EDITOR_SAFE_DDS_REIMPORT_V5_2_40_AUTO_WRITE_PCPACK'
            log['final_safe_scan_summary']=summary
            log['final_output_folder']=str(final_out_dir)
            log['visible_output_note']='The patched PCPACK is written inside FINAL_PATCHED_PCPACK_OUTPUT. DDS files are only intermediate/edit inputs.'
            (final_out_dir/(out_path.stem+'_FINAL_SAFE_DDS_REIMPORT_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            (final_out_dir/'00_PATCHED_PCPACK_IS_HERE.txt').write_text(
                'FINAL SAFE DDS REIMPORT COMPLETE\n'
                '================================\n\n'
                'Your patched PCPACK is here:\n'
                f'{out_path}\n\n'
                f'Patched DDS count: {log["patch_count"]}\n'
                f'Auto-normalized header recovery count: {summary["auto_normalized_count"]}\n'
                f'Editor-safe rebuilt from pixels count: {summary["gimp_safe_rebuilt_count"]}\n'
                f'Blocked DDS count: {len(skipped)}\n\n'
                'Use this NEW PCPACK copy for testing. The original PCPACK was not modified.\n'
                'DDS folders are intermediate/edit folders only; the .PCPACK in this folder is the final output.\n',
                encoding='utf-8'
            )
            (final_out_dir/'FINAL_PATCHED_PCPACK_PATH.txt').write_text(str(out_path)+'\n',encoding='utf-8')
            self.last_export_dir=str(final_out_dir)
            self.replacement_folder_var.set(str(final_out_dir))
            try:
                open_path(final_out_dir)
            except Exception:
                pass
            messagebox.showinfo(
                'FINAL PCPACK WRITTEN',
                f'Patched {log["patch_count"]} DDS files into ONE NEW PCPACK.\n\n'
                f'Auto-normalized: {summary["auto_normalized_count"]}\n'
                f'Blocked: {len(skipped)}\n\n'
                'YOUR FINAL PCPACK IS HERE:\n'
                f'{out_path}\n\n'
                f'Reports:\n{report_dir}'
            )
            self.set_status(f'FINAL SAFE PCPACK WRITTEN: {log["patch_count"]} items -> {out_path}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('FINAL SAFE DDS reimport failed',str(e))

    def single_file_gimp_safe_patch_write_pcpack(self):
        """v5.2.39: patch ONE edited DDS/image into ONE new PCPACK using the editor-safe final route.

        Daily-use route for quick suit tests:
        - user selects one edited DDS/image
        - tool target-locks by SM3 hash/name in the filename, or uses the selected row after confirmation
        - exact/header-safe DDS patches directly
        - header-only DDS changes are auto-normalized
        - Paint.NET/GIMP/editor overwritten DDS/images are rebuilt from visible pixels into the selected SM3 target format
        - output is a loud FINAL_SINGLE_FILE_PATCH_OUTPUT folder with one new .PCPACK copy
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing. Load a clean original PCPACK first.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        source=Path(filedialog.askopenfilename(
            title='Choose ONE edited DDS/image to patch into a new PCPACK',
            initialdir=start_dir if start_dir else None,
            filetypes=[
                ('DDS / image files','*.dds *.png *.bmp *.jpg *.jpeg'),
                ('DDS files','*.dds'),
                ('Image files','*.png *.bmp *.jpg *.jpeg'),
                ('All files','*.*'),
            ]
        ) or '')
        if not str(source):
            return
        if not source.exists():
            messagebox.showerror('Missing file',f'File does not exist:\n{source}')
            return

        target, reason = _filename_direct_target_match(source, self.targets)
        selected_target = self.resolve_current_selected_target()
        if not target and selected_target:
            target=selected_target
            reason='SELECTED_ROW_TARGET_CONFIRM'
            if not messagebox.askyesno(
                'Use selected target for single-file patch?',
                'This file name does not contain a direct SM3 target hash/name lock.\n\n'
                f'File:\n{source.name}\n\n'
                'Use the currently selected texture row as the target?\n\n'
                f'Target: {target.get("asset")}\nHash: {target.get("filename_hash")}\n\n'
                'Only continue if this file is meant for that exact texture slot.'
            ):
                return
        if not target:
            messagebox.showwarning(
                'No target match',
                'The file name did not match a SM3 target hash/name, and no texture row is selected.\n\n'
                'Fix one of these:\n'
                '- select the target texture row first, then click Single File Patch again\n'
                '- or keep the exported filename like 0xHASH.asset.ORIGINAL_EDIT_THIS.dds'
            )
            return

        self.selected_target=target
        if not self.target_safety_ok_or_confirm('single_file_gimp_safe_patch'):
            return

        work_dir=ensure_dir(source.parent/'SINGLE_FILE_PATCH_WORK')
        norm_dir=ensure_dir(work_dir/'AUTO_NORMALIZED_DDS')
        rebuild_dir=ensure_dir(work_dir/'GIMP_SAFE_REBUILT_DDS')
        report_dir=ensure_dir(work_dir/'REPORTS')
        ready=[]; blocked=[]; normalized_rows=[]; rebuilt_rows=[]
        final_dds=None
        action=''
        normalize_reason=''
        info={}
        try:
            is_dds=source.suffix.lower()=='.dds'
            if is_dds:
                try:
                    info, descriptor_problems=validate_dds_matches_target(source,target,strict=False)
                except Exception as parse_exc:
                    descriptor_problems=['DDS_PARSE_FAILED_FOR_DESCRIPTOR_CHECK: '+str(parse_exc)]
                if descriptor_problems:
                    rebuilt, row = rebuild_source_pixels_to_target_game_dds(
                        source, target, rebuild_dir, force_opaque=bool(self.force_opaque_var.get())
                    )
                    row['match_reason']=reason
                    row['source_descriptor_problems']='; '.join(descriptor_problems)
                    row['source_action']='SINGLE_FILE_GIMP_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                    rebuilt_rows.append(row)
                    final_dds=Path(rebuilt)
                    action='SINGLE_FILE_GIMP_SAFE_REBUILT_FROM_SOURCE_PIXELS'
                    normalize_reason='Source DDS descriptor did not match SM3 target after editor overwrite; rebuilt visible pixels into target game DDS format.'
                    info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                    if final_problems:
                        raise ValueError('Rebuilt DDS still failed header lock:\n- ' + '\n- '.join(final_problems))
                else:
                    header=dds_header_info_for_target(source,target)
                    if not header.get('actual_header_matches_expected'):
                        normalized, row = normalize_dds_to_target_game_format(source, target, norm_dir)
                        row['match_reason']=reason
                        row['source_action']='SINGLE_FILE_AUTO_NORMALIZED_HEADER_RECOVERY'
                        normalized_rows.append(row)
                        final_dds=Path(normalized)
                        action='SINGLE_FILE_AUTO_NORMALIZED_HEADER_RECOVERY'
                        normalize_reason='DDS descriptor/payload matched but header differed; restored SM3 target/export header before patching.'
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            raise ValueError('Normalized DDS still failed header lock:\n- ' + '\n- '.join(final_problems))
                    else:
                        final_dds=source
                        action='SINGLE_FILE_PATCH_DIRECT_HEADER_OK'
                        info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                        if final_problems:
                            raise ValueError('DDS failed final header lock:\n- ' + '\n- '.join(final_problems))
            elif source.suffix.lower() in IMAGE_EXTS:
                rebuilt, row = rebuild_source_pixels_to_target_game_dds(
                    source, target, rebuild_dir, force_opaque=bool(self.force_opaque_var.get())
                )
                row['match_reason']=reason
                row['source_action']='SINGLE_FILE_IMAGE_REBUILT_FROM_SOURCE_PIXELS'
                rebuilt_rows.append(row)
                final_dds=Path(rebuilt)
                action='SINGLE_FILE_IMAGE_REBUILT_FROM_SOURCE_PIXELS'
                normalize_reason='Image source supplied pixels; rebuilt into SM3 target game DDS format before patching.'
                info, final_problems=validate_dds_matches_target_header_locked(final_dds,target,strict=False)
                if final_problems:
                    raise ValueError('Image-rebuilt DDS still failed header lock:\n- ' + '\n- '.join(final_problems))
            else:
                raise ValueError('Unsupported single-file source type. Use DDS, PNG, BMP, JPG, or JPEG.')

            ready.append({
                'source_file':str(source),
                'final_dds_for_patch':str(final_dds),
                'asset':target.get('asset'),
                'hash':target.get('filename_hash'),
                'match_reason':reason,
                'action':action,
                'normalize_reason':normalize_reason,
                'width':info.get('width'),
                'height':info.get('height'),
                'mips':info.get('mips'),
                'format_kind':info.get('format_kind'),
                'payload_size':info.get('payload_size'),
                'header_sha256':info.get('header_sha256'),
                'expected_header_sha256':info.get('expected_header_sha256'),
                'status':'READY_SINGLE_FILE_PATCH',
            })
        except Exception as exc:
            blocked.append({
                'source_file':str(source),
                'asset':target.get('asset') if target else '',
                'hash':target.get('filename_hash') if target else '',
                'reason':str(exc).replace('\n',' | '),
                'status':'BLOCKED_SINGLE_FILE_PATCH',
            })

        write_csv(report_dir/'SINGLE_FILE_PATCH_READY.csv', ready)
        write_csv(report_dir/'SINGLE_FILE_PATCH_BLOCKED.csv', blocked)
        write_csv(report_dir/'SINGLE_FILE_AUTO_NORMALIZED.csv', normalized_rows)
        write_csv(report_dir/'SINGLE_FILE_GIMP_SAFE_REBUILT.csv', rebuilt_rows)
        summary={
            'version':'v5.2.40',
            'mode':'SINGLE_FILE_GIMP_SAFE_PATCH_SCAN',
            'source_file':str(source),
            'target_asset':target.get('asset') if target else '',
            'target_hash':target.get('filename_hash') if target else '',
            'match_reason':reason,
            'ready_count':len(ready),
            'blocked_count':len(blocked),
            'auto_normalized_count':len(normalized_rows),
            'gimp_safe_rebuilt_count':len(rebuilt_rows),
            'direct_header_ok_count':1 if action=='SINGLE_FILE_PATCH_DIRECT_HEADER_OK' else 0,
            'rule':'one source file only; target hash/name or selected-row confirmation required; exact/header-safe DDS patches direct; header-only DDS is normalized; GIMP/editor DDS or image is rebuilt from visible pixels into target SM3 game format',
        }
        (report_dir/'SINGLE_FILE_PATCH_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (report_dir/'SINGLE_FILE_PATCH_RULES.txt').write_text(
            'SINGLE FILE EDITOR-SAFE PATCH - v5.2.40\n'
            '====================================\n\n'
            'Use this for one edited texture test.\n'
            '- Best route: export edit-ready DDS, edit/overwrite one DDS, click Single File Patch.\n'
            '- Target is chosen by filename hash/name, or by the selected texture row after confirmation.\n'
            '- DDS files with exact target header patch directly.\n'
            '- DDS files with only a header mismatch are auto-normalized.\n'
            '- Paint.NET/GIMP-overwritten DDS/images are rebuilt from visible pixels into the SM3 target format/mips/payload.\n'
            '- Original PCPACK is never modified. Output is one new PCPACK copy.\n',
            encoding='utf-8'
        )

        if not ready or not final_dds:
            messagebox.showwarning('Single file blocked',f'The selected file did not pass single-file patch rules.\n\nReport:\n{report_dir}')
            self.set_status(f'SINGLE FILE PATCH blocked. Report: {report_dir}')
            return

        final_out_dir=ensure_dir(source.parent/'FINAL_SINGLE_FILE_PATCH_OUTPUT')
        safe_asset=clean_name(target.get('asset','texture'))
        default_name=f'{pc.stem}_PATCHED_SINGLE_{safe_asset}{pc.suffix}'
        out_path=final_out_dir/default_name
        if out_path.exists():
            base=out_path.stem
            ext=out_path.suffix
            idx=1
            while (final_out_dir/f'{base}_{idx:03d}{ext}').exists():
                idx+=1
            out_path=final_out_dir/f'{base}_{idx:03d}{ext}'

        msg=(
            'Single-file patch is ready.\n\n'
            f'Target: {target.get("asset")}\n'
            f'Hash: {target.get("filename_hash")}\n'
            f'Action: {action}\n\n'
            'The tool will write ONE NEW patched PCPACK here:\n'
            f'{out_path}\n\n'
            'Original PCPACK will NOT be modified.'
        )
        if not messagebox.askyesno('Confirm SINGLE FILE patch', msg):
            return
        try:
            log=copy_and_patch_pcpack_header_locked_dds_many(pc, [(target, final_dds, {})], out_path)
            log['mode']='SINGLE_FILE_EDITOR_SAFE_PATCH_V5_2_40_AUTO_WRITE_PCPACK'
            log['single_file_scan_summary']=summary
            log['final_output_folder']=str(final_out_dir)
            log['visible_output_note']='The patched PCPACK is written inside FINAL_SINGLE_FILE_PATCH_OUTPUT.'
            (final_out_dir/(out_path.stem+'_SINGLE_FILE_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            (final_out_dir/'00_SINGLE_FILE_PATCHED_PCPACK_IS_HERE.txt').write_text(
                'SINGLE FILE PATCH COMPLETE\n'
                '==========================\n\n'
                'Your patched PCPACK is here:\n'
                f'{out_path}\n\n'
                f'Target: {target.get("asset")}\n'
                f'Hash: {target.get("filename_hash")}\n'
                f'Action: {action}\n'
                f'Patched DDS count: {log.get("patch_count",1)}\n\n'
                'Use this NEW PCPACK copy for testing. The original PCPACK was not modified.\n',
                encoding='utf-8'
            )
            (final_out_dir/'FINAL_SINGLE_FILE_PATCHED_PCPACK_PATH.txt').write_text(str(out_path)+'\n',encoding='utf-8')
            self.last_export_dir=str(final_out_dir)
            try:
                open_path(final_out_dir)
            except Exception:
                pass
            messagebox.showinfo(
                'SINGLE FILE PCPACK WRITTEN',
                'Patched one edited file into ONE NEW PCPACK.\n\n'
                f'Target: {target.get("asset")}\n'
                f'Action: {action}\n\n'
                'YOUR FINAL PCPACK IS HERE:\n'
                f'{out_path}\n\n'
                f'Reports:\n{report_dir}'
            )
            self.set_status(f'SINGLE FILE PCPACK WRITTEN: {source.name} -> {out_path}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('Single file patch failed', str(e))

    def header_name_locked_reimport_folder(self):
        """v5.2.33: Final-safe folder reimport: target name/hash + exact DDS header lock."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=Path(filedialog.askdirectory(title='Choose EDIT-READY DDS folder to reimport', initialdir=start_dir if start_dir else None) or '')
        if not str(folder):
            return
        manifest_path, manifest_rows = find_header_lock_manifest(folder)
        manifest_by_file=manifest_rows_by_filename(manifest_rows)
        src_files=sorted([p for p in folder.rglob('*.dds') if p.is_file()])
        src_files=[p for p in src_files if not any(part.upper().endswith('REPORTS') or part.upper().startswith('REIMPORT') for part in p.parts)]
        if not src_files:
            messagebox.showinfo('No DDS files',f'No DDS files found in:\n{folder}')
            return
        patch_items=[]; skipped=[]; report=[]; used=set()
        for src in src_files:
            target, reason = _filename_direct_target_match(src, self.targets)
            if not target:
                skipped.append({'file':str(src),'reason':'NO_TARGET_NAME_OR_HASH_LOCK','status':'BLOCKED'})
                continue
            key=target_edit_key(target)
            if key in used:
                skipped.append({'file':str(src),'asset':target.get('asset'),'reason':'DUPLICATE_TARGET_ALREADY_USED','status':'BLOCKED'})
                continue
            manifest_row=manifest_by_file.get(src.name.lower(), {})
            try:
                info, problems=validate_dds_matches_target_header_locked(src,target,strict=False)
                if problems:
                    skipped.append({'file':str(src),'asset':target.get('asset'),'reason':'; '.join(problems),'status':'BLOCKED'})
                    continue
                if manifest_row and manifest_row.get('original_dds_header_sha256') and manifest_row.get('original_dds_header_sha256') != info.get('header_sha256'):
                    skipped.append({'file':str(src),'asset':target.get('asset'),'reason':'DDS header changed from manifest export header','status':'BLOCKED'})
                    continue
                patch_items.append((target, src, manifest_row))
                used.add(key)
                report.append({'file':str(src),'asset':target.get('asset'),'hash':target.get('filename_hash'),'match_reason':reason,'header_sha256':info.get('header_sha256'),'status':'READY_HEADER_NAME_LOCKED'})
            except Exception as exc:
                skipped.append({'file':str(src),'asset':target.get('asset'),'reason':str(exc),'status':'BLOCKED'})
        report_dir=ensure_dir(folder/'HEADER_NAME_LOCKED_REIMPORT_REPORTS')
        write_csv(report_dir/'HEADER_NAME_LOCKED_READY.csv', report)
        write_csv(report_dir/'HEADER_NAME_LOCKED_BLOCKED.csv', skipped)
        summary={'version':'v5.2.33','mode':'HEADER_NAME_LOCKED_REIMPORT_SCAN','manifest':str(manifest_path) if manifest_path else '', 'ready_count':len(patch_items),'blocked_count':len(skipped),'folder':str(folder)}
        (report_dir/'HEADER_NAME_LOCKED_SCAN_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        if not patch_items:
            messagebox.showwarning('No safe header-locked patches',f'No DDS files passed header+name lock. Blocked: {len(skipped)}\n\nReport:\n{report_dir}')
            return
        if not messagebox.askyesno('Confirm HEADER+NAME locked reimport', f'{len(patch_items)} DDS files passed header+name lock. Blocked: {len(skipped)}.\n\nWrite ONE NEW patched PCPACK copy?'):
            return
        default_name=pc.stem+'_PATCHED_HEADER_NAME_LOCKED'+pc.suffix
        out=filedialog.asksaveasfilename(title='Save header+name locked patched PCPACK as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_header_locked_dds_many(pc, patch_items, Path(out))
            messagebox.showinfo('HEADER+NAME locked patch complete', f'Patched {log["patch_count"]} DDS files into a new PCPACK copy.\n\nOutput:\n{out}')
            self.set_status(f'HEADER+NAME locked patch complete: {log["patch_count"]} items -> {out}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('Header locked patch failed',str(e))

    def reimport_all_dds_folder(self):
        """v5.0: Folder reimport now uses the same exact-or-convert rule as single patch.

        Old behavior was exact/descriptor-only, so exported files like
        0xHASH.asset.ORIGINAL_EDIT_THIS.dds could be skipped as AMBIGUOUS even
        though the same file worked with selected single patch. v5.0 trusts
        hash/asset filenames first, then converts to the target format if strict
        DDS validation fails.
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=Path(filedialog.askdirectory(title='Choose folder to REIMPORT ALL / v5.0 exact-or-convert', initialdir=start_dir if start_dir else None) or '')
        if not str(folder):
            return

        exts={'.dds','.png','.jpg','.jpeg','.bmp'}
        src_files=sorted([p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in exts])
        # Avoid re-reading generated report/output folders if the user reruns the same folder.
        src_files=[p for p in src_files if not any(part.upper().endswith('REPORTS') or part.upper().startswith('REIMPORT_ALL_REPORTS') or part.upper().startswith('SMART_REIMPORT_REPORTS') for part in p.parts)]
        if not src_files:
            messagebox.showinfo('No files',f'No DDS/PNG/JPG/BMP files found in:\n{folder}')
            return

        used=set()
        smart_items=[]
        skipped=[]
        report_rows=[]

        for src in src_files:
            target, reason = self.smart_target_guess_for_source(src)
            if not target:
                skipped.append((src, reason))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':'','hash':'','mode':'','reason':reason})
                continue

            k=target_edit_key(target)
            if k in used:
                skipped.append((src, 'TARGET_ALREADY_MAPPED'))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':target.get('asset'),'hash':target.get('filename_hash'),'mode':'','reason':'TARGET_ALREADY_MAPPED'})
                continue

            mode='CONVERT'
            detail=reason
            if src.suffix.lower()=='.dds':
                try:
                    validate_dds_matches_target(src,target,strict=True)
                    mode='EXACT'
                    detail=reason + '; EXACT_DDS_MATCH'
                except Exception as exc:
                    mode='CONVERT'
                    detail=reason + '; WILL_CONVERT_TO_TARGET_FORMAT_AFTER_VALIDATION_FAIL: ' + str(exc).replace('\n',' | ')
            else:
                mode='CONVERT'
                detail=reason + '; IMAGE_WILL_CONVERT_TO_TARGET_FORMAT'

            r=unsafe_target_reason(target) if (self.diffuse_safe_var.get() or self.strict_diffuse_var.get()) else ''
            if r and self.strict_diffuse_var.get():
                skipped.append((src, 'STRICT_DIFFUSE_BLOCKED: '+r))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':target.get('asset'),'hash':target.get('filename_hash'),'mode':mode,'reason':'STRICT_DIFFUSE_BLOCKED: '+r})
                continue

            used.add(k)
            smart_items.append({'target':target,'path':src,'mode':mode,'reason':detail})
            report_rows.append({
                'status':'WILL_PATCH',
                'source':str(src),
                'asset':target.get('asset'),
                'hash':target.get('filename_hash'),
                'target_size':f"{target.get('width')}x{target.get('height')}",
                'target_format':target.get('format_kind'),
                'target_mips':target.get('mips'),
                'target_payload':target.get('component1_size'),
                'mode':mode,
                'reason':detail
            })

        report_dir=folder/'REIMPORT_ALL_REPORTS_v5_0'
        ensure_dir(report_dir)
        write_csv(report_dir/'REIMPORT_ALL_MATCH_REPORT_v5_0.csv', report_rows)
        summary={
            'tool':'THE_TEX_SWAPPER_TSGAMING264_v5_0',
            'mode':'REIMPORT_ALL_EXACT_OR_CONVERT_SINGLE_PATCH_PARITY',
            'pcpack':str(pc),
            'folder':str(folder),
            'source_files_found':len(src_files),
            'will_patch':len(smart_items),
            'exact_count':sum(1 for i in smart_items if i.get('mode')=='EXACT'),
            'convert_count':sum(1 for i in smart_items if i.get('mode')=='CONVERT'),
            'skipped':len(skipped),
            'report_folder':str(report_dir),
        }
        (report_dir/'REIMPORT_ALL_SUMMARY_v5_0.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

        if not smart_items:
            messagebox.showwarning('No reimport matches', f'No patchable matches found.\n\nReport:\n{report_dir}')
            self.set_status(f'REIMPORT ALL v5.0 found no patchable matches. Report: {report_dir}')
            return

        preview='\n'.join(f"- {i['mode']}: {i['target'].get('asset')} <- {Path(i['path']).name}" for i in smart_items[:24])
        if len(smart_items)>24:
            preview += f'\n...and {len(smart_items)-24} more.'

        skipped_text=''
        if skipped:
            skipped_text='\n\nSkipped / still needs manual review:\n' + '\n'.join(f"- {Path(p).name}: {reason}" for p,reason in skipped[:16])
            if len(skipped)>16:
                skipped_text += f'\n...and {len(skipped)-16} more.'

        msg=(
            f'REIMPORT ALL v5.0 found {len(smart_items)} patchable file(s).\n'
            f'Exact DDS: {summary["exact_count"]}\n'
            f'Convert like single patch: {summary["convert_count"]}\n'
            f'Skipped: {summary["skipped"]}\n\n'
            f'{preview}'
            f'{skipped_text}\n\n'
            f'Report folder:\n{report_dir}\n\n'
            'v5.0 rule: hash/asset-named files are target-locked, so they are not skipped as ambiguous. Continue and write ONE NEW patched PCPACK copy?'
        )
        if not messagebox.askyesno('REIMPORT ALL v5.0 review', msg):
            self.set_status(f'REIMPORT ALL v5.0 cancelled. Report: {report_dir}')
            return

        self.replacement_folder_var.set(str(folder))
        out=filedialog.asksaveasfilename(
            title='Save REIMPORT ALL v5.0 patched PCPACK copy',
            initialfile=pc.stem+'_PATCHED_REIMPORT_ALL_v5_0'+pc.suffix,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return

        try:
            log=copy_and_patch_pcpack_smart_mixed_many(pc, smart_items, Path(out), force_opaque=bool(self.force_opaque_var.get()))
            log['mode']='REIMPORT_ALL_EXACT_OR_CONVERT_SINGLE_PATCH_PARITY_V5_0'
            log['match_report']=str(report_dir/'REIMPORT_ALL_MATCH_REPORT_v5_0.csv')
            log['skipped']=[{'file':str(p),'reason':reason} for p,reason in skipped]
            (Path(out).parent/(Path(out).stem+'_REIMPORT_ALL_SUMMARY_v5_0.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('REIMPORT ALL v5.0 complete', f'Patched {log["patch_count"]} texture(s).\nExact: {log["exact_count"]}\nConverted: {log["convert_count"]}\n\nOutput:\n{out}')
            self.set_status(f'REIMPORT ALL v5.0 complete: {log["patch_count"]} patched ({log["exact_count"]} exact, {log["convert_count"]} converted).')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('REIMPORT ALL v5.0 failed', str(exc))


    def smart_target_guess_for_source(self, source_path:Path):
        """v5.0: Guess a target for exact OR convert import.

        Priority:
        1. .sm3edit sidecar target_key
        2. exact filename hash lock: 0xHASH.*
        3. exact filename asset lock: 0xHASH.asset.ORIGINAL_EDIT_THIS / 0xHASH.asset
        4. unique full asset/hash name match
        5. exact descriptor fallback from old scanner

        The important v5.0 fix is #2/#3. If the file is already named after a
        real Tex Swapper target, folder reimport must trust that target and use
        the same exact-or-convert path as single selected patch.
        """
        p=Path(source_path)
        target_by_key={target_edit_key(t):t for t in self.targets}
        # Sidecars from EXPORT ALL are the safest mapping.
        for side in [p.with_suffix(p.suffix+'.sm3edit.json'), p.with_suffix('.sm3edit.json')]:
            if side.exists():
                try:
                    sm=json.loads(side.read_text(encoding='utf-8'))
                    tk=sm.get('target_key')
                    if tk in target_by_key:
                        return target_by_key[tk], 'SIDECAR_TARGET_KEY'
                except Exception:
                    pass

        direct, direct_reason = _filename_direct_target_match(p, self.targets)
        if direct:
            return direct, direct_reason

        low=str(p.name).lower()
        strong=[]
        # Hash matches are exact, but if the file contains multiple old strings,
        # exact hash wins before substring asset guesses.
        for t in self.targets:
            h=str(t.get('filename_hash','')).lower()
            if h and h in low:
                strong.append(t)
        if len(strong)==1:
            return strong[0], 'FILENAME_HASH_UNIQUE'
        if len(strong)>1:
            return None, 'AMBIGUOUS_FILENAME_HASH_MATCHES_' + str(len(strong))

        strong=[]
        for t in self.targets:
            asset=str(t.get('asset','')).lower()
            if asset and asset in low:
                strong.append(t)
        if len(strong)==1:
            return strong[0], 'FILENAME_ASSET_UNIQUE'
        if len(strong)>1:
            return None, 'AMBIGUOUS_FILENAME_ASSET_MATCHES_' + str(len(strong))

        # Exact descriptor fallback for DDS files.
        if p.suffix.lower()=='.dds':
            row=self.scan_one_dds_for_manual_picker(p)
            if row.get('best'):
                return row['best'], 'EXACT_SCANNER_BEST'
            matches=list(row.get('matches') or [])
            if len(matches)==1:
                return matches[0], 'EXACT_SCANNER_UNIQUE'
            if len(matches)>1:
                return None, 'AMBIGUOUS_EXACT_DESCRIPTOR_' + str(len(matches))
        return None, 'NO_TARGET_GUESS'

    def smart_reimport_all_folder(self):
        """v4.4: Reimport a folder using exact DDS when possible, otherwise convert to target mip/format."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return

        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=Path(filedialog.askdirectory(title='Choose folder for legacy smart reimport', initialdir=start_dir if start_dir else None) or '')
        if not str(folder):
            return

        exts={'.dds','.png','.jpg','.jpeg','.bmp'}
        src_files=sorted([p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in exts])
        if not src_files:
            messagebox.showinfo('No files',f'No DDS/PNG/JPG/BMP files found in:\n{folder}')
            return

        used=set()
        smart_items=[]
        skipped=[]
        report_rows=[]

        for src in src_files:
            target, reason = self.smart_target_guess_for_source(src)
            if not target:
                skipped.append((src, reason))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':'','hash':'','mode':'','reason':reason})
                continue
            k=target_edit_key(target)
            if k in used:
                skipped.append((src, 'TARGET_ALREADY_MAPPED'))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':target.get('asset'),'hash':target.get('filename_hash'),'mode':'','reason':'TARGET_ALREADY_MAPPED'})
                continue

            mode='CONVERT'
            detail=reason
            if src.suffix.lower()=='.dds':
                try:
                    validate_dds_matches_target(src,target,strict=True)
                    mode='EXACT'
                    detail=reason + '; EXACT_DDS_MATCH'
                except Exception as exc:
                    mode='CONVERT'
                    detail=reason + '; WILL_CONVERT_TO_TARGET_FORMAT_AFTER_VALIDATION_FAIL: ' + str(exc).replace('\n',' | ')
            else:
                mode='CONVERT'
                detail=reason + '; IMAGE_WILL_CONVERT_TO_TARGET_FORMAT'

            # Strict diffuse safety still applies.
            r=unsafe_target_reason(target) if (self.diffuse_safe_var.get() or self.strict_diffuse_var.get()) else ''
            if r and self.strict_diffuse_var.get():
                skipped.append((src, 'STRICT_DIFFUSE_BLOCKED: '+r))
                report_rows.append({'status':'SKIPPED','source':str(src),'asset':target.get('asset'),'hash':target.get('filename_hash'),'mode':mode,'reason':'STRICT_DIFFUSE_BLOCKED: '+r})
                continue

            used.add(k)
            smart_items.append({'target':target,'path':src,'mode':mode,'reason':detail})
            report_rows.append({
                'status':'WILL_PATCH',
                'source':str(src),
                'asset':target.get('asset'),
                'hash':target.get('filename_hash'),
                'target_size':f"{target.get('width')}x{target.get('height')}",
                'target_format':target.get('format_kind'),
                'target_mips':target.get('mips'),
                'target_payload':target.get('component1_size'),
                'mode':mode,
                'reason':detail
            })

        report_dir=folder/'SMART_REIMPORT_REPORTS'
        ensure_dir(report_dir)
        write_csv(report_dir/'SMART_REIMPORT_MATCH_REPORT_v4_4.csv', report_rows)
        summary={
            'tool':'THE_TEX_SWAPPER_TSGAMING264_v4_4',
            'mode':'SMART_REIMPORT_EXACT_OR_CONVERT',
            'pcpack':str(pc),
            'folder':str(folder),
            'source_files_found':len(src_files),
            'will_patch':len(smart_items),
            'exact_count':sum(1 for i in smart_items if i.get('mode')=='EXACT'),
            'convert_count':sum(1 for i in smart_items if i.get('mode')=='CONVERT'),
            'skipped':len(skipped),
            'report_folder':str(report_dir),
        }
        (report_dir/'SMART_REIMPORT_SUMMARY_v4_4.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

        if not smart_items:
            messagebox.showwarning('No smart matches', f'No patchable matches found.\n\nReport:\n{report_dir}')
            self.set_status(f'legacy smart reimport found no patchable matches. Report: {report_dir}')
            return

        preview='\n'.join(f"- {i['mode']}: {i['target'].get('asset')} <- {Path(i['path']).name}" for i in smart_items[:20])
        if len(smart_items)>20:
            preview += f'\n...and {len(smart_items)-20} more.'

        msg=(
            f'legacy smart reimport found {len(smart_items)} patchable file(s).\n'
            f'Exact: {summary["exact_count"]}\n'
            f'Convert due to mip/format/size/source image: {summary["convert_count"]}\n'
            f'Skipped: {summary["skipped"]}\n\n'
            f'{preview}\n\n'
            f'Report folder:\n{report_dir}\n\n'
            'Continue and write ONE NEW patched PCPACK copy?'
        )
        if not messagebox.askyesno('Confirm legacy smart reimport', msg):
            self.set_status(f'legacy smart reimport cancelled. Report: {report_dir}')
            return

        out=filedialog.asksaveasfilename(
            title='Save legacy smart reimport patched PCPACK copy',
            initialfile=pc.stem+'_PATCHED_SMART_REIMPORT_'+pc.suffix,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return

        try:
            log=copy_and_patch_pcpack_smart_mixed_many(pc, smart_items, Path(out), force_opaque=bool(self.force_opaque_var.get()))
            log['match_report']=str(report_dir/'SMART_REIMPORT_MATCH_REPORT_v4_4.csv')
            (Path(out).parent/(Path(out).stem+'_SMART_REIMPORT_SUMMARY_v4_4.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('legacy smart reimport complete', f'Patched {log["patch_count"]} texture(s).\nExact: {log["exact_count"]}\nConverted: {log["convert_count"]}\n\nOutput:\n{out}')
            self.set_status(f'legacy smart reimport complete: {log["patch_count"]} patched ({log["exact_count"]} exact, {log["convert_count"]} converted).')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('legacy smart reimport failed', str(exc))


    def batch_export_original_dds(self):
        targets=self.get_selected_targets()
        if not targets:
            messagebox.showinfo('Select textures','Select one or more textures first. Use Ctrl-click or Shift-click in the texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose one folder for all exported DDS files') or '')
        if not str(outdir): return
        ok=[]; errors=[]
        try:
            for t in targets:
                try:
                    dds,raw,meta=export_original_component_as_dds(pc,t,outdir)
                    key=target_edit_key(t)
                    self.dds_export_history[key]=meta
                    self.last_export_dir=str(Path(dds).parent)
                    ok.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'dds':str(dds),'raw':str(raw),'status':'EXPORTED'})
                except Exception as exc:
                    errors.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'error':str(exc),'status':'ERROR'})
            ensure_dir(outdir)
            write_csv(outdir/'BATCH_DDS_EXPORT_REPORT.csv', ok+errors)
            self.replacement_folder_var.set(str(outdir))
            messagebox.showinfo('Batch DDS export finished', f'Exported {len(ok)} DDS files. Errors: {len(errors)}\n\nFolder:\n{outdir}\n\nEdit the DDS files in Paint.NET/GIMP, then use the editor-safe folder final patch to write one PCPACK copy.')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('Batch export failed',str(e))

    def batch_auto_detect_edited_dds_and_patch(self):
        targets=self.get_selected_targets()
        if not targets:
            messagebox.showinfo('Select textures','Select one or more textures first. Use Ctrl-click or Shift-click in the texture list.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        risky=[]
        if self.diffuse_safe_var.get() or self.strict_diffuse_var.get():
            for t in targets:
                reason=unsafe_target_reason(t)
                if reason:
                    risky.append((t,reason))
            if risky and self.strict_diffuse_var.get():
                messagebox.showwarning('Strict diffuse-only mode', 'Batch contains non-diffuse/control targets. Disable strict mode or select only _dif/_diff textures.\n\n' + '\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:12]))
                return
            if risky:
                msg='Some selected textures may not be normal diffuse/color maps. Continue?\n\n'
                msg += '\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                if len(risky)>15: msg += f'\n...and {len(risky)-15} more.'
                if not messagebox.askyesno('Batch target warning', msg):
                    return
        patch_items=[]; missing=[]; same=[]; errors=[]
        for t in targets:
            try:
                candidates=self.find_auto_edited_dds_candidates(t)
                edited=[c for c in candidates if not c.get('same_as_original')]
                if edited:
                    patch_items.append((t, Path(edited[0]['path'])))
                elif candidates:
                    same.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'best_match':str(candidates[0].get('path')),'status':'MATCH_FOUND_BUT_NOT_EDITED'})
                else:
                    missing.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'status':'NO_MATCHING_EDITED_DDS'})
            except Exception as exc:
                errors.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'error':str(exc),'status':'ERROR'})
        if not patch_items:
            msg='No edited DDS files were found for the selected textures.\n\nUse BATCH: Export DDS for Selected, edit the DDS files in Paint.NET/GIMP, then try the editor-safe folder final patch again.\n\nOr click Select Replacement Folder for Batch and choose the folder where your edited DDS files are saved.'
            if same: msg += f'\n\n{len(same)} matching DDS files looked identical to the original.'
            if missing: msg += f'\n{len(missing)} selected textures had no matching DDS.'
            if errors: msg += f'\n{len(errors)} errors occurred.'
            messagebox.showinfo('No batch edits detected', msg)
            return
        summary='BATCH AUTO found edited DDS files for:\n\n'
        summary+='\n'.join(f"- {t.get('asset')}  <-  {dds.name}" for t,dds in patch_items[:20])
        if len(patch_items)>20: summary += f'\n...and {len(patch_items)-20} more.'
        if same or missing or errors:
            summary += f'\n\nSkipped: identical={len(same)}, missing={len(missing)}, errors={len(errors)}'
        summary += '\n\nPatch all found edited DDS files into ONE new PCPACK copy?'
        if not messagebox.askyesno('Confirm batch patch', summary):
            return
        default_name=pc.stem+f'_PATCHED_BATCH_{len(patch_items)}_DDS'+pc.suffix
        out=filedialog.asksaveasfilename(title='Save ONE patched PCPACK copy with all selected edited DDS files',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack_original_format_dds_many(pc, patch_items, Path(out))
            report_rows=[]
            for t,dds in patch_items:
                report_rows.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'dds':str(dds),'status':'PATCHED'})
            report_rows += same + missing + errors
            write_csv(Path(out).parent/(Path(out).stem+'_BATCH_AUTO_DETECT_REPORT.csv'), report_rows)
            messagebox.showinfo('Batch patch complete', f'Patched {len(patch_items)} edited DDS files into one new PCPACK copy.\n\nOriginal was not modified.\n\nOutput:\n{out}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('Batch patch failed',str(e))


    def previous_folder_auto_replace(self):
        """v2.9: patch every valid matching DDS from a previous replacement folder into one PCPACK copy.

        This is for the workflow the user requested:
        Build Preview -> select a previous folder with the same texture DDS files -> auto-replace -> export pack.
        It does NOT require the user to manually multi-select every texture.
        """
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select and Build Preview for a clean original PCPACK first.')
            return
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this pack\'s TEX targets, then run Previous Folder Auto Replace.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=filedialog.askdirectory(title='Select PREVIOUS folder containing edited/replacement DDS files', initialdir=start_dir if start_dir else None)
        if not folder:
            return
        folder=Path(folder)
        self.replacement_folder_var.set(str(folder))
        self.last_export_dir=str(folder)
        if self.diffuse_safe_var.get() or self.strict_diffuse_var.get():
            risky=[]
            for t in self.targets:
                reason=unsafe_target_reason(t)
                if reason:
                    # Only warn for risky targets that actually have a matching DDS candidate.
                    try:
                        cand=self.find_auto_edited_dds_candidates(t)
                    except Exception:
                        cand=[]
                    if cand:
                        risky.append((t,reason))
            if risky and self.strict_diffuse_var.get():
                messagebox.showwarning(
                    'Strict diffuse-only mode',
                    'Previous Folder Auto Replace found possible non-diffuse/control DDS matches, but strict diffuse-only mode is enabled.\n\n'
                    'Disable strict mode or remove risky DDS files from the previous folder.\n\n'
                    + '\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                )
                return
            if risky:
                msg='Previous Folder Auto Replace found possible DDS matches for non-diffuse/control textures. Continue?\n\n'
                msg += '\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                if len(risky)>15:
                    msg += f'\n...and {len(risky)-15} more.'
                if not messagebox.askyesno('Previous folder target warning', msg):
                    return

        patch_items=[]; identical=[]; missing=[]; errors=[]; duplicate_notes=[]
        seen_offsets=set()
        for t in self.targets:
            try:
                candidates=self.find_auto_edited_dds_candidates(t)
                if not candidates:
                    missing.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'status':'NO_MATCHING_DDS_IN_PREVIOUS_FOLDER'})
                    continue
                edited=[c for c in candidates if not c.get('same_as_original')]
                chosen = edited[0] if edited else candidates[0]
                if not edited:
                    identical.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'dds':str(chosen.get('path')),'status':'MATCH_FOUND_BUT_IDENTICAL_TO_ORIGINAL'})
                    # Do not patch identical no-op files by default; this keeps output/log cleaner.
                    continue
                off_key=(str(t.get('component1_absolute_start_dec')), str(t.get('component1_absolute_end_dec')))
                if off_key in seen_offsets:
                    duplicate_notes.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'dds':str(chosen.get('path')),'status':'DUPLICATE_OFFSET_SKIPPED'})
                    continue
                seen_offsets.add(off_key)
                patch_items.append((t, Path(chosen['path'])))
            except Exception as exc:
                errors.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'error':str(exc),'status':'ERROR'})

        report_rows=[]
        for t,dds in patch_items:
            report_rows.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'dds':str(dds),'status':'PATCHED_FROM_PREVIOUS_FOLDER'})
        report_rows += identical + missing + errors + duplicate_notes

        if not patch_items:
            report_dir=Path(self.output_var.get())
            try:
                ensure_dir(report_dir)
                write_csv(report_dir/'PREVIOUS_FOLDER_AUTO_REPLACE_SCAN_REPORT.csv', report_rows)
            except Exception:
                pass
            msg='No edited DDS files were found in the selected previous folder.\n\n'
            msg+='The folder may contain original/unmodified DDS files, wrong DDS format, or names that do not match this pack.\n\n'
            msg+=f'Previous folder:\n{folder}\n\n'
            msg+=f'Identical matches: {len(identical)}\nMissing: {len(missing)}\nErrors: {len(errors)}'
            messagebox.showinfo('No previous-folder edits detected', msg)
            return

        summary='Previous Folder Auto Replace found edited DDS files for this pack:\n\n'
        summary += '\n'.join(f"- {t.get('asset')}  <-  {dds.name}" for t,dds in patch_items[:24])
        if len(patch_items)>24:
            summary += f'\n...and {len(patch_items)-24} more.'
        summary += f'\n\nFolder:\n{folder}\n\n'
        summary += f'Will patch: {len(patch_items)}\nIdentical/no-op skipped: {len(identical)}\nNo match: {len(missing)}\nErrors: {len(errors)}'
        summary += '\n\nExport ONE patched PCPACK copy now?'
        if not messagebox.askyesno('Confirm previous-folder auto replace', summary):
            return
        default_name=pc.stem+f'_PATCHED_PREVIOUS_FOLDER_{len(patch_items)}_DDS'+pc.suffix
        out=filedialog.asksaveasfilename(title='Export patched PCPACK copy from previous folder DDS replacements', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_original_format_dds_many(pc, patch_items, Path(out))
            log['mode']='PREVIOUS_FOLDER_AUTO_REPLACE_V2_9'
            log['previous_folder']=str(folder)
            log['patched_count']=len(patch_items)
            log['identical_skipped_count']=len(identical)
            log['missing_count']=len(missing)
            log['error_count']=len(errors)
            (Path(out).parent/(Path(out).stem+'_PREVIOUS_FOLDER_AUTO_REPLACE_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            write_csv(Path(out).parent/(Path(out).stem+'_PREVIOUS_FOLDER_AUTO_REPLACE_REPORT.csv'), report_rows)
            messagebox.showinfo('Previous folder patch complete', f'Patched {len(patch_items)} edited DDS files from the previous folder into one new PCPACK copy.\n\nOriginal was not modified.\n\nOutput:\n{out}')
            self.set_status(f'Previous folder auto replace complete: patched {len(patch_items)} DDS files into {out}')
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Previous folder patch failed', str(e))



    def select_target_in_tree(self, target):
        """Select a target in the main TEX tree, when visible, and show its preview/info."""
        if not target:
            return False
        wanted = target_edit_key(target)
        for idx, t in enumerate(self.targets):
            if target_edit_key(t) == wanted:
                iid = str(idx)
                try:
                    if self.tree.exists(iid):
                        self.tree.selection_set(iid)
                        self.tree.focus(iid)
                        self.tree.see(iid)
                    self.selected_target = t
                    p = self.find_best_image_for_asset(t.get('asset',''))
                    if p:
                        self.show_image(p)
                    self.show_info(t)
                    return True
                except Exception:
                    self.selected_target = t
                    self.show_info(t)
                    return True
        return False

    def resolve_current_selected_target(self):
        """v3.6: resolve the current texture selection reliably.

        Some Tk/Treeview states can leave self.selected_target empty even though one row is
        highlighted. This prevents false "No texture selected" messages in the one-file
        replacement flows.
        """
        try:
            sels=list(self.tree.selection())
        except Exception:
            sels=[]
        if sels:
            try:
                idx=int(sels[0])
                if 0 <= idx < len(self.targets):
                    self.selected_target=self.targets[idx]
                    return self.selected_target
            except Exception:
                pass
        return self.selected_target

    def same_files_select_dds_and_patch(self):
        """v3.6: select one or more DDS files and auto-patch matching targets.

        This is for the user's "replace the same files" workflow: after Build Preview, choose
        DDS replacement files directly. The tool matches them by sidecar/name/hash/descriptor,
        validates each against the current PCPACK TEX target, then writes one patched PCPACK copy.
        No texture row needs to be selected first.
        """
        if not self.targets:
            messagebox.showinfo('Build preview first', 'Click Build Preview first so the tool knows this PCPACK\'s texture targets.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        files=filedialog.askopenfilenames(
            title='SAME FILE(S): select one or more edited DDS replacement files',
            initialdir=start_dir if start_dir else None,
            filetypes=[('DDS/images','*.dds *.png *.bmp *.jpg *.jpeg'),('DDS files','*.dds'),('Images','*.png *.bmp *.jpg *.jpeg'),('All files','*.*')]
        )
        if not files:
            return
        dds_files=[Path(f) for f in files]
        patch_items=[]; skipped=[]; ambiguous=[]
        used=set()
        for dds in dds_files:
            row=self.scan_one_dds_for_manual_picker(dds)
            if row.get('status')=='BAD_DDS':
                skipped.append((dds,'BAD_DDS: '+str(row.get('error','')))); continue
            matches=list(row.get('matches') or [])
            if not matches:
                info=row.get('info') or {}
                skipped.append((dds, f"NO_MATCH format={info.get('format_kind')} size={info.get('width')}x{info.get('height')} mips={info.get('mips')}")); continue
            target=row.get('best')
            if not target and len(matches)==1:
                target=matches[0]
            if not target:
                ambiguous.append((dds,matches)); continue
            key=target_edit_key(target)
            if key in used:
                skipped.append((dds,'TARGET_ALREADY_MAPPED')); continue
            try:
                validate_dds_matches_target(dds, target, strict=True)
            except Exception as exc:
                skipped.append((dds,'VALIDATION_FAIL: '+str(exc))); continue
            used.add(key); patch_items.append((target,dds))
        if ambiguous:
            skipped.extend((p, f'AMBIGUOUS_MATCHES_{len(m)} use Manual Old Folder Texture Picker if needed') for p,m in ambiguous)
        if skipped:
            msg=f'Valid same-file matches: {len(patch_items)}\nSkipped/ambiguous: {len(skipped)}\n\n'
            msg+='\n'.join(f'- {Path(p).name}: {reason}' for p,reason in skipped[:25])
            if len(skipped)>25: msg += f'\n...and {len(skipped)-25} more.'
            msg+='\n\nContinue with the valid matches?'
            if not patch_items or not messagebox.askyesno('Same-file auto replace review', msg):
                return
        self._patch_many_dds_with_review(pc, patch_items, 'SAME_FILES_AUTO_REPLACE_V3_6', '_PATCHED_SAME_FILES_AUTO_', 'SAME_FILES_AUTO_REPLACE_LOG')

    def old_selected_one_file_direct_export(self):
        """v4.0 stable: SELECTED EXACT workflow.

        Select one texture target first, pick one DDS that already matches it, then
        export one patched PCPACK copy. This button does not auto-select another
        target and does not convert. Use legacy selected convert for wrong-size/wrong-mip
        source files.
        """
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        if not self.target_safety_ok_or_confirm('selected_exact_one_dds_v40'):
            return
        start_dir=self.replacement_folder_var.get().strip() or self.get_last_export_dir_for_selected() or self.last_export_dir or self.output_var.get()
        dds=filedialog.askopenfilename(
            title='SELECTED EXACT: choose ONE DDS that already matches the selected texture',
            initialdir=start_dir if start_dir else None,
            filetypes=[('DDS files','*.dds'),('All files','*.*')]
        )
        if not dds:
            return
        dds_path=Path(dds)
        try:
            validate_dds_matches_target(dds_path, target, strict=True)
        except Exception as exc:
            msg=(
                'This button is the strict/exact DDS path. The replacement DDS must already match the selected texture.\n\n'
                f'Selected target requires:\n'
                f'- {target.get("width")}x{target.get("height")}\n'
                f'- {target.get("format_kind")}\n'
                f'- mips {target.get("mips")}\n'
                f'- payload {target.get("component1_size")} bytes\n\n'
                'Validation error:\n' + str(exc) + '\n\n'
                'Do you want to use this file as pixels only and convert it into the selected target format instead?'
            )
            if messagebox.askyesno('DDS does not match selected texture', msg):
                out=filedialog.asksaveasfilename(
                    title='Export converted patched PCPACK copy',
                    initialfile=pc.stem+'_PATCHED_SELECTED_CONVERT_'+clean_name(target.get('asset','tex'))+pc.suffix,
                    filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
                )
                if not out:
                    return
                try:
                    log=copy_and_patch_pcpack_convert_source_to_target(pc,target,dds_path,Path(out),force_opaque=bool(self.force_opaque_var.get()))
                    log['mode']='V4_1_EXACT_FAILED_USER_ACCEPTED_CONVERT'
                    log['source_file']=str(dds_path)
                    log['target_asset']=target.get('asset')
                    messagebox.showinfo('Converted patch complete', f'Converted source into selected target format and created:\n{out}')
                    self.set_status(f'v4.1 convert fallback complete: {target.get("asset")} <- {dds_path.name}')
                except Exception as exc2:
                    traceback.print_exc(); messagebox.showerror('Convert fallback failed', str(exc2))
            return
        default_name=pc.stem+'_PATCHED_SELECTED_EXACT_'+clean_name(target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(
            title='Export patched PCPACK copy',
            initialfile=default_name,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_original_format_dds(pc,target,dds_path,Path(out))
            log['mode']='V4_1_SELECTED_EXACT_ONE_DDS_DIRECT_EXPORT'
            log['replacement_dds']=str(dds_path)
            log['target_asset']=target.get('asset')
            log['note']='Stable final exact workflow: selected target first, one matching DDS, direct Save As export; no auto-select and no conversion.'
            (Path(out).parent/(Path(out).stem+'_V4_SELECTED_EXACT_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo(
                'Selected exact DDS patch complete',
                'Patched the selected texture into a new PCPACK copy.\n\n'
                f'Texture:\n{target.get("asset")}\n\n'
                f'Replacement:\n{dds_path.name}\n\n'
                f'Output:\n{out}'
            )
            self.set_status(f'v4.1 selected exact patch complete: {target.get("asset")} <- {dds_path.name}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('Selected exact patch failed', str(exc))

    def selected_target_format_convert_direct(self):
        """v4.0 stable: explicit selected-target conversion workflow.

        Use this when the source file is the wrong size, mip count, or DDS format.
        Source supplies pixels only; selected target supplies final width/height,
        format, mip count, and payload size.
        """
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        if not self.target_safety_ok_or_confirm('selected_convert_to_target_v40'):
            return
        start_dir=self.replacement_folder_var.get().strip() or self.get_last_export_dir_for_selected() or self.last_export_dir or self.output_var.get()
        src=filedialog.askopenfilename(
            title='legacy selected convert: choose DDS/image to convert into the selected target format',
            initialdir=start_dir if start_dir else None,
            filetypes=[('DDS/images','*.dds *.png *.bmp *.jpg *.jpeg'),('DDS files','*.dds'),('Images','*.png *.bmp *.jpg *.jpeg'),('All files','*.*')]
        )
        if not src:
            return
        src_path=Path(src)
        confirm=(
            'This will use the chosen file as PIXELS ONLY and convert it into the currently selected texture slot.\n\n'
            f'Selected target:\n{target.get("asset")}\n\n'
            f'Final target format:\n- {target.get("width")}x{target.get("height")}\n- {target.get("format_kind")}\n- mips {target.get("mips")}\n- payload {target.get("component1_size")} bytes\n\n'
            'Continue?'
        )
        if not messagebox.askyesno('Convert source into selected target format', confirm):
            return
        default_name=pc.stem+'_PATCHED_SELECTED_CONVERT_'+clean_name(target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(
            title='Export converted patched PCPACK copy',
            initialfile=default_name,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_convert_source_to_target(pc,target,src_path,Path(out),force_opaque=bool(self.force_opaque_var.get()))
            log['mode']='V4_1_SELECTED_CONVERT_SOURCE_TO_TARGET_FORMAT'
            log['source_file']=str(src_path)
            log['target_asset']=target.get('asset')
            messagebox.showinfo(
                'Selected target-format conversion complete',
                'Converted the chosen file into the selected texture format and exported one patched PCPACK copy.\n\n'
                f'Target:\n{target.get("asset")}\n\n'
                f'Source:\n{src_path.name}\n\n'
                f'Output:\n{out}'
            )
            self.set_status(f'v4.1 selected convert complete: {target.get("asset")} <- {src_path.name}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('Selected target-format conversion failed', str(exc))

    def scan_one_dds_for_manual_picker(self, dds_path:Path):
        """Scan one DDS file against the current PCPACK TEX targets.

        v3.1: same matching logic as the old-folder picker, but for one chosen DDS.
        This is what fixes the workflow where the user wants to manually select one
        replacement texture instead of selecting a whole folder.
        """
        p=Path(dds_path)
        try:
            info=parse_dds_header_file(p)
        except Exception as exc:
            return {'path':p,'file':p.name,'status':'BAD_DDS','error':str(exc),'info':None,'matches':[],'strong':[],'best':None,'method':'BAD_DDS'}
        exact=[]; strong=[]; sidecar_target=None
        target_by_key={target_edit_key(t):t for t in self.targets}
        for side in [p.with_suffix(p.suffix+'.sm3edit.json'), p.with_suffix('.sm3edit.json')]:
            if side.exists():
                try:
                    sm=json.loads(side.read_text(encoding='utf-8'))
                    tk=sm.get('target_key')
                    if tk in target_by_key:
                        sidecar_target=target_by_key[tk]
                        break
                except Exception:
                    pass
        for t in self.targets:
            try:
                _info,_problems=validate_dds_matches_target(p,t,strict=True)
            except Exception:
                continue
            exact.append(t)
            low=str(p).lower()
            asset=str(t.get('asset','')).lower()
            h=str(t.get('filename_hash','')).lower()
            if (sidecar_target is t) or (asset and asset in low) or (h and h in low):
                strong.append(t)
        method='NO_TARGET_MATCH'
        best=None
        if sidecar_target and sidecar_target in exact:
            method='SIDECAR_EXACT'; best=sidecar_target
        elif len(strong)==1:
            method='NAME_HASH_EXACT'; best=strong[0]
        elif len(exact)==1:
            method='UNIQUE_DESCRIPTOR'; best=exact[0]
        elif len(strong)>1:
            method='MULTIPLE_NAME_MATCHES'
        elif len(exact)>1:
            method='AMBIGUOUS_DESCRIPTOR'
        return {'path':p,'file':p.name,'status':'OK' if exact else 'NO_MATCH','error':'','info':info,'matches':exact,'strong':strong,'best':best,'method':method}

    def pick_target_for_one_dds_row(self, row, prefer_selected=True):
        """Choose the best current TEX target for one DDS row, with manual fallback."""
        matches=row.get('matches') or []
        if not matches:
            return None
        # If user already selected a target and it validates against this DDS, respect that.
        if prefer_selected and self.selected_target:
            sk=target_edit_key(self.selected_target)
            for t in matches:
                if target_edit_key(t)==sk:
                    return t
        if row.get('best'):
            return row['best']
        if len(matches)==1:
            return matches[0]
        # Too ambiguous. Ask the user to pick one in a small dialog.
        win=tk.Toplevel(self.root)
        win.title('Choose Target for One DDS - v3.3 restored one-file flow')
        win.geometry('780x420')
        choice={'target':None}
        ttk.Label(win,text='This DDS matches multiple TEX targets. Pick the one you want to replace:',font=('TkDefaultFont',11,'bold')).pack(anchor='w',padx=8,pady=(8,2))
        ttk.Label(win,text=str(row.get('path')),wraplength=740).pack(anchor='w',padx=8,pady=(0,6))
        frame=ttk.Frame(win,padding=8); frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=('asset','hash','fmt','size'),show='headings',selectmode='browse')
        for col,w in [('asset',340),('hash',110),('fmt',80),('size',90)]:
            tree.heading(col,text=col); tree.column(col,width=w,anchor='w',stretch=(col=='asset'))
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns')
        frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1)
        for i,t in enumerate(matches):
            tree.insert('', 'end', iid=str(i), values=(t.get('asset'), t.get('filename_hash'), t.get('format_kind'), f"{t.get('width')}x{t.get('height')}"))
        def use_choice():
            sel=tree.selection()
            if not sel:
                return
            try:
                choice['target']=matches[int(sel[0])]
            except Exception:
                choice['target']=None
            win.destroy()
        btns=ttk.Frame(win,padding=8); btns.pack(fill='x')
        ttk.Button(btns,text='Use Selected Target',command=use_choice).pack(side='right',padx=4)
        ttk.Button(btns,text='Cancel',command=win.destroy).pack(side='right',padx=4)
        tree.bind('<Double-1>', lambda e: use_choice())
        try:
            tree.selection_set('0'); tree.focus('0')
        except Exception:
            pass
        win.grab_set()
        self.root.wait_window(win)
        return choice.get('target')


    def choose_target_for_source_conversion(self, source_path:Path, source_info:dict|None=None):
        """v3.9: file-first fallback. User chooses a DDS/image first; if it does not
        exactly match any TEX target, let the user choose the target slot and convert the
        source pixels into that selected target format. This removes the too-strong
        requirement to select a texture before testing one-file replacement.
        """
        if not self.targets:
            return None
        win=tk.Toplevel(self.root)
        win.title('Choose target texture for source conversion - v3.9')
        win.geometry('940x560')
        choice={'target':None}
        ttk.Label(win,text='No exact TEX slot matched this file. Choose the texture slot to convert/patch into:',font=('TkDefaultFont',11,'bold')).pack(anchor='w',padx=8,pady=(8,2))
        info_line=f'Source file: {source_path}'
        if source_info:
            try:
                info_line += f"\nSource detected: {source_info.get('width')}x{source_info.get('height')} {source_info.get('format_kind')} mips {source_info.get('mips')}"
            except Exception:
                pass
        ttk.Label(win,text=info_line,wraplength=900).pack(anchor='w',padx=8,pady=(0,6))
        search_var=tk.StringVar(value='')
        sf=ttk.Frame(win,padding=(8,0,8,4)); sf.pack(fill='x')
        ttk.Label(sf,text='Filter targets:').pack(side='left')
        ent=ttk.Entry(sf,textvariable=search_var,width=42); ent.pack(side='left',fill='x',expand=True,padx=6)
        frame=ttk.Frame(win,padding=8); frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=('asset','hash','size','fmt','mips','bytes'),show='headings',selectmode='browse')
        cols=[('asset',330),('hash',110),('size',90),('fmt',80),('mips',55),('bytes',90)]
        for col,w in cols:
            tree.heading(col,text=col); tree.column(col,width=w,anchor='w',stretch=(col=='asset'))
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); sx.grid(row=1,column=0,sticky='ew')
        frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1)
        visible=[]
        def populate(*_):
            nonlocal visible
            q=search_var.get().strip().lower()
            visible=[]
            tree.delete(*tree.get_children())
            for t in self.targets:
                text=' '.join(str(t.get(k,'')) for k in ('asset','filename_hash','format_kind','group')).lower()
                if q and q not in text:
                    continue
                visible.append(t)
                iid=str(len(visible)-1)
                tree.insert('', 'end', iid=iid, values=(t.get('asset'),t.get('filename_hash'),f"{t.get('width')}x{t.get('height')}",t.get('format_kind'),t.get('mips'),t.get('component1_size')))
            if visible:
                try: tree.selection_set('0'); tree.focus('0')
                except Exception: pass
        def use_choice():
            sel=tree.selection()
            if not sel:
                return
            try:
                choice['target']=visible[int(sel[0])]
            except Exception:
                choice['target']=None
            win.destroy()
        ent.bind('<KeyRelease>', populate)
        tree.bind('<Double-1>', lambda e: use_choice())
        btns=ttk.Frame(win,padding=8); btns.pack(fill='x')
        ttk.Button(btns,text='Convert Source Into Selected Target',command=use_choice).pack(side='right',padx=4)
        ttk.Button(btns,text='Cancel',command=win.destroy).pack(side='right',padx=4)
        ttk.Label(btns,text='Target decides final width/height/DXT/mips. Source supplies pixels only.',wraplength=520).pack(side='left',anchor='w')
        populate()
        win.grab_set()
        self.root.wait_window(win)
        return choice.get('target')

    def old_one_file_auto_select_and_patch(self):
        """v3.9: one-file workflow is file-first again.

        User does NOT need to select a texture first.
        Pick one DDS/image, then:
          - if it exactly matches one/current target, patch it directly;
          - if it does not match, optionally choose a target slot and convert the source
            pixels into that target format before exporting one patched PCPACK copy.
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK\'s texture targets.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        src=filedialog.askopenfilename(
            title='legacy one-file auto: select ONE DDS/image replacement file',
            initialdir=start_dir if start_dir else None,
            filetypes=[('DDS/images','*.dds *.png *.bmp *.jpg *.jpeg'),('DDS files','*.dds'),('Images','*.png *.bmp *.jpg *.jpeg'),('All files','*.*')]
        )
        if not src:
            return
        src_path=Path(src)
        row=None; info=None; target=None; direct_match=False
        if src_path.suffix.lower()=='.dds':
            row=self.scan_one_dds_for_manual_picker(src_path)
            if row.get('status')!='BAD_DDS':
                info=row.get('info') or {}
                if row.get('matches'):
                    # File-first auto. Prefer an exact name/sidecar/best match. Only use current selection
                    # as a tie-breaker, not as a hard requirement.
                    target=self.pick_target_for_one_dds_row(row, prefer_selected=True)
                    direct_match=bool(target)
            else:
                # Bad/odd DDS can still sometimes be opened as an image by Pillow, so allow convert fallback.
                info=None
        else:
            info=None
        convert_to_target=False
        if not direct_match:
            msg='This file did not exactly match a current TEX target by size/format/mips/payload.\n\n'
            if src_path.suffix.lower()=='.dds' and row and row.get('status')!='BAD_DDS':
                inf=row.get('info') or {}
                msg += f"Source DDS detected:\n- {inf.get('width')}x{inf.get('height')}\n- {inf.get('format_kind')}\n- mips {inf.get('mips')}\n- payload {len(inf.get('payload',b''))} bytes\n\n"
            msg += ('v3.9 can still use this file as PIXELS ONLY. You will choose the target texture slot next, '
                    'and the tool will convert the source into that target slot format.\n\n'
                    'This is the correct route when a source is 64x64 but the target is 128x128, or when mip counts differ.\n\n'
                    'Choose target texture and convert?')
            if not messagebox.askyesno('No exact one-file match', msg):
                return
            target=self.choose_target_for_source_conversion(src_path, info)
            if not target:
                return
            convert_to_target=True
        else:
            self.select_target_in_tree(target)
            if not self.target_safety_ok_or_confirm('one_file_auto_v39'):
                return
            try:
                validate_dds_matches_target(src_path, target, strict=True)
            except Exception as exc:
                # This should be rare because direct_match came from validation, but keep a safe fallback.
                if not messagebox.askyesno('DDS no longer matches selected target', str(exc)+'\n\nConvert source pixels into this selected target format instead?'):
                    return
                convert_to_target=True
        default_name=pc.stem+'_PATCHED_ONE_FILE_AUTO_'+clean_name(target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            if convert_to_target:
                log=copy_and_patch_pcpack_convert_source_to_target(pc,target,src_path,Path(out),force_opaque=bool(self.force_opaque_var.get()))
                log['mode']='ONE_FILE_AUTO_SOURCE_TO_TARGET_CONVERT_V3_9'
                log['source_file']=str(src_path)
                log['target_asset']=target.get('asset')
                messagebox.showinfo('One-file auto convert complete',
                    'Converted the chosen file into the selected target texture format and exported one patched PCPACK copy.\n\n'
                    f'Target:\n{target.get("asset")}\n\n'
                    f'Source:\n{src_path.name}\n\n'
                    f'Final target format:\n{target.get("width")}x{target.get("height")} {target.get("format_kind")} mips {target.get("mips")}\n\n'
                    f'Output:\n{out}')
                self.set_status(f'v3.9 one-file auto converted source into target: {target.get("asset")} <- {src_path.name}')
            else:
                log=copy_and_patch_pcpack_original_format_dds(pc,target,src_path,Path(out))
                log['mode']='ONE_FILE_AUTO_EXACT_MATCH_V3_9'
                log['replacement_dds']=str(src_path)
                log['target_asset']=target.get('asset')
                (Path(out).parent/(Path(out).stem+'_ONE_FILE_AUTO_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
                messagebox.showinfo('One-file auto patch complete',
                    'Patched one exact-format DDS into a new PCPACK copy.\n\n'
                    f'Target:\n{target.get("asset")}\n\nReplacement:\n{src_path.name}\n\nOutput:\n{out}')
                self.set_status(f'v3.9 one-file auto exact patch complete: {target.get("asset")} <- {src_path.name}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('One-file auto patch failed', str(exc))

    def manual_one_file_auto_select_and_patch(self):
        """v3.3: restored v3.1-style ONE DDS workflow. Choose exactly ONE DDS, auto-select one matching TEX target, patch one new PCPACK copy."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK\'s texture targets.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        dds=filedialog.askopenfilename(title='legacy one-file auto: Select exactly ONE DDS replacement file', initialdir=start_dir if start_dir else None, filetypes=[('DDS','*.dds'),('All files','*.*')])
        if not dds:
            return
        row=self.scan_one_dds_for_manual_picker(Path(dds))
        if row.get('status')=='BAD_DDS':
            messagebox.showerror('Bad DDS', row.get('error','Could not read DDS.'))
            return
        if not row.get('matches'):
            info=row.get('info') or {}
            messagebox.showerror('No matching TEX target', 'This DDS does not match any current TEX target by width/height/format/mips/payload size.\n\n'
                f"DDS: {dds}\nFormat: {info.get('format_kind')}\nSize: {info.get('width')}x{info.get('height')}\nMips: {info.get('mips')}\nPayload: {len(info.get('payload',b''))} bytes")
            return
        target=self.pick_target_for_one_dds_row(row, prefer_selected=True)
        if not target:
            return
        self.select_target_in_tree(target)
        if not self.target_safety_ok_or_confirm('one_file_auto_select_patch'):
            return
        try:
            info,_=validate_dds_matches_target(Path(dds), target, strict=True)
        except Exception as exc:
            messagebox.showerror('DDS does not match selected target', str(exc))
            return
        same=(info.get('payload',b'') == self.get_original_payload_for_target(target))
        confirm=(
            'Patch this ONE DDS into a NEW PCPACK copy?\n\n'
            f"Auto-selected target:\n{target.get('asset')}\n{target.get('filename_hash')}\n\n"
            f"DDS:\n{dds}\n\n"
            f"Match method: {row.get('method')}\nFormat: {info.get('format_kind')}\nSize: {info.get('width')}x{info.get('height')}\nMips: {info.get('mips')}\nPayload: {len(info.get('payload',b''))} bytes\n\n"
        )
        if same:
            confirm += 'WARNING: DDS payload is identical to the original texture. This will be a no-op/control patch.\n\n'
        confirm += 'Continue?'
        if not messagebox.askyesno('Confirm one-file patch', confirm):
            return
        default_name=pc.stem+'_PATCHED_ONE_DDS_'+clean_name(target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_original_format_dds(pc,target,Path(dds),Path(out))
            log['mode']='ONE_FILE_AUTO_SELECT_PATCH_V3_3_RESTORED'
            log['replacement_dds']=str(dds)
            log['target_asset']=target.get('asset')
            (Path(out).parent/(Path(out).stem+'_ONE_FILE_PATCH_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('One-file patch complete', f'Patched one DDS into a new PCPACK copy.\n\nTarget:\n{target.get("asset")}\n\nOutput:\n{out}')
            self.set_status(f'v3.3 restored one-file patch complete: {target.get("asset")} <- {Path(dds).name}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('One-file patch failed', str(exc))


    def _patch_many_dds_with_review(self, pc:Path, patch_items:list[tuple[dict, Path]], mode:str, default_suffix:str, report_name:str):
        """Patch multiple strict original-format DDS replacements into one new PCPACK copy."""
        if not patch_items:
            messagebox.showinfo('No valid DDS matches','No valid matching DDS replacements were found. Make sure the DDS files match the target texture format, size, mip count, and payload size.')
            return
        # De-dupe by target; keep first unless user confirms replacement not needed here.
        dedup=[]; seen=set(); dup=0
        for t,pth in patch_items:
            k=target_edit_key(t)
            if k in seen:
                dup+=1; continue
            seen.add(k); dedup.append((t,pth))
        patch_items=dedup
        risky=[]
        if self.diffuse_safe_var.get() or self.strict_diffuse_var.get():
            for t,_ in patch_items:
                r=unsafe_target_reason(t)
                if r: risky.append((t,r))
            if risky and self.strict_diffuse_var.get():
                messagebox.showwarning('Strict diffuse-only mode', 'Selected replacements include non-diffuse/control targets. Disable strict mode or remove them.\n\n'+'\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:12]))
                return
            if risky:
                msg='Selected replacements include textures that may not be normal diffuse/color maps. Continue?\n\n'
                msg+='\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                if len(risky)>15: msg += f'\n...and {len(risky)-15} more.'
                if not messagebox.askyesno('Target warning', msg):
                    return
        preview='\n'.join(f"- {t.get('asset')}  <-  {Path(pth).name}" for t,pth in patch_items[:20])
        if len(patch_items)>20:
            preview += f'\n...and {len(patch_items)-20} more.'
        if not messagebox.askyesno('Confirm multi-file patch', f'Patch {len(patch_items)} DDS file(s) into ONE new PCPACK copy?\n\n{preview}\n\nOriginal PCPACK will not be modified.'):
            return
        default_name=pc.stem+default_suffix+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            log=copy_and_patch_pcpack_original_format_dds_many(pc, patch_items, Path(out))
            rows=[]
            for t,pth in patch_items:
                rows.append({'asset':t.get('asset'),'hash':t.get('filename_hash'),'format':t.get('format_kind'),'size':f"{t.get('width')}x{t.get('height')}",'mips':t.get('mips'),'dds':str(pth),'status':'PATCHED'})
            write_csv(Path(out).parent/(Path(out).stem+'_'+report_name+'.csv'), rows)
            log['mode']=mode
            log['patched_count']=len(patch_items)
            log['items']=rows
            (Path(out).parent/(Path(out).stem+'_'+report_name+'.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('Multi-file patch complete', f'Patched {len(patch_items)} DDS file(s) into one new PCPACK copy.\n\nOutput:\n{out}')
            self.set_status(f'{mode}: patched {len(patch_items)} DDS files into {out}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('Multi-file patch failed', str(exc))

    def _pick_multiple_dds_files(self, title:str):
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        files=filedialog.askopenfilenames(
            title=title,
            initialdir=start_dir if start_dir else None,
            filetypes=[
                ('DDS / image files','*.dds *.png *.bmp *.jpg *.jpeg'),
                ('DDS files','*.dds'),
                ('Image files','*.png *.bmp *.jpg *.jpeg'),
                ('All files','*.*')
            ]
        )
        return [Path(f) for f in files] if files else []

    def _auto_map_dds_files(self, dds_files:list[Path], restrict_to_selected:bool=False):
        selected=self.get_selected_targets() if restrict_to_selected else []
        selected_keys={target_edit_key(t) for t in selected}
        patch_items=[]; skipped=[]; ambiguous=[]
        used_targets=set()
        for dds in dds_files:
            row=self.scan_one_dds_for_manual_picker(Path(dds))
            if row.get('status')=='BAD_DDS':
                skipped.append((dds,'BAD_DDS: '+str(row.get('error','')))); continue
            matches=list(row.get('matches') or [])
            if restrict_to_selected and selected_keys:
                matches=[t for t in matches if target_edit_key(t) in selected_keys]
            if not matches:
                skipped.append((dds,'NO_MATCH_FOR_SELECTED_TARGETS' if restrict_to_selected else 'NO_MATCH')); continue
            # Prefer exact/sidecar/best, but do not reuse a target.
            preferred=[]
            best=row.get('best')
            if best and target_edit_key(best) in [target_edit_key(t) for t in matches]:
                preferred.append(best)
            preferred.extend(matches)
            chosen=None
            for t in preferred:
                k=target_edit_key(t)
                if k not in used_targets:
                    chosen=t; break
            if not chosen:
                skipped.append((dds,'TARGET_ALREADY_MAPPED')); continue
            if len(matches)>1 and (not row.get('best')):
                ambiguous.append((dds,matches)); continue
            try:
                validate_dds_matches_target(Path(dds), chosen, strict=True)
            except Exception as exc:
                skipped.append((dds,'VALIDATION_FAIL: '+str(exc))); continue
            used_targets.add(target_edit_key(chosen)); patch_items.append((chosen,Path(dds)))
        return patch_items, skipped, ambiguous

    def _patch_smart_selected_items_with_review(self, pc:Path, selected:list, files:list[Path], smart_items:list, skipped:list, report_rows:list, default_tag:str, mode_label:str):
        """v4.9 shared selected multi-patch review.

        This uses copy_and_patch_pcpack_smart_mixed_many, so selected multi-file
        patching follows the same rule as the working single selected workflows:
        exact DDS when it matches, otherwise convert source pixels into the selected
        target's width/height/format/mips/payload.
        """
        risky=[]
        if self.diffuse_safe_var.get() or self.strict_diffuse_var.get():
            for item in smart_items:
                r=unsafe_target_reason(item['target'])
                if r:
                    risky.append((item['target'],r))
            if risky and self.strict_diffuse_var.get():
                messagebox.showwarning(
                    'Strict diffuse-only mode',
                    'Selected replacements include non-diffuse/control targets. Disable strict mode or remove them.\n\n'
                    + '\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:12])
                )
                return False
            if risky:
                msg='Selected replacements include textures that may not be normal diffuse/color maps. Continue?\n\n'
                msg+='\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                if len(risky)>15:
                    msg += f'\n...and {len(risky)-15} more.'
                if not messagebox.askyesno('Target warning', msg):
                    return False

        exact_count=sum(1 for i in smart_items if i.get('mode')=='EXACT')
        convert_count=sum(1 for i in smart_items if i.get('mode')=='CONVERT')
        preview='\n'.join(f"- {i['mode']}: {i['target'].get('asset')} <- {Path(i['path']).name}" for i in smart_items[:20])
        if len(smart_items)>20:
            preview += f'\n...and {len(smart_items)-20} more.'

        skip_text=''
        if skipped:
            skip_text='\n\nSkipped / unpaired:\n' + '\n'.join(f"- {Path(p).name}: {reason}" for p,reason in skipped[:15])
            if len(skipped)>15:
                skip_text += f'\n...and {len(skipped)-15} more.'

        if not smart_items:
            messagebox.showwarning(
                'No selected pair mappings',
                'No patchable selected target/file pairs were created.\n\n'
                + (skip_text or 'Check your selected targets and files.')
            )
            return False

        msg=(
            f'Selected targets: {len(selected)}\n'
            f'Selected files: {len(files)}\n'
            f'Will patch: {len(smart_items)}\n'
            f'Exact DDS: {exact_count}\n'
            f'Convert to target format/mips: {convert_count}\n\n'
            f'{preview}'
            f'{skip_text}\n\n'
            'v4.9 rule: selected multi-file patch now uses the SAME exact-or-convert path as single selected patch.\n\n'
            'Continue and write ONE NEW PCPACK copy?'
        )
        if not messagebox.askyesno('v4.9 selected multi-file pair review', msg):
            return False

        default_name=pc.stem+default_tag+pc.suffix
        out=filedialog.asksaveasfilename(
            title='Save patched PCPACK copy from v4.9 selected multi-file mappings',
            initialfile=default_name,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return False

        try:
            log=copy_and_patch_pcpack_smart_mixed_many(pc, smart_items, Path(out), force_opaque=bool(self.force_opaque_var.get()))
            log['mode']=mode_label
            log['selected_target_count']=len(selected)
            log['selected_file_count']=len(files)
            log['skipped']=[{'file':str(p),'reason':reason} for p,reason in skipped]
            report_path=Path(out).parent/(Path(out).stem+'_MANUAL_SELECTED_PAIR_REPORT_v4_9.csv')
            write_csv(report_path, report_rows)
            (Path(out).parent/(Path(out).stem+'_MANUAL_SELECTED_PAIR_LOG_v4_9.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo(
                'v4.9 selected multi-file patch complete',
                f'Patched {log["patch_count"]} texture(s) into one new PCPACK copy.\n'
                f'Exact: {log["exact_count"]}\n'
                f'Converted: {log["convert_count"]}\n\n'
                f'Output:\n{out}\n\nReport:\n{report_path}'
            )
            self.set_status(f'v4.9 selected multi-pair patched {log["patch_count"]}: {out}')
            return True
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('v4.9 selected multi-file patch failed', str(exc))
            return False


    def manual_multi_file_auto_select_and_patch(self):
        """v4.9: choose multiple files and patch one new PCPACK copy.

        If texture targets are already selected, this now routes through the selected
        exact-or-convert smart path. That fixes the inconsistency where single selected
        patch worked but multi-select/auto patch rejected the same DDS/image as "not right".
        If no targets are selected, it preserves the older exact auto-match route.
        """
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows this PCPACK\'s texture targets.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select a clean PCPACK first.')
            return
        selected=self.get_selected_targets()
        title='Select replacement DDS/image files'
        if selected:
            title+=' IN THE SAME ORDER as selected targets'
        else:
            title+=' to auto-match exactly'
        files=self._pick_multiple_dds_files(title)
        if not files:
            return

        if selected:
            smart_items, skipped, report_rows = self._build_selected_order_smart_items(selected, files)
            self._patch_smart_selected_items_with_review(
                pc, selected, files, smart_items, skipped, report_rows,
                f'_PATCHED_V4_9_SELECTED_MULTI_{len(smart_items)}_FILES',
                'MULTI_SMART_SELECTED_EXACT_OR_CONVERT_V4_9'
            )
            return

        # No selected targets: keep older strict auto-match behavior. This path can only
        # patch original-format DDS files because there is no selected target to convert into.
        patch_items, skipped, ambiguous = self._auto_map_dds_files(files, restrict_to_selected=False)
        if ambiguous:
            skipped.extend((p, f'AMBIGUOUS_MATCHES_{len(m)}') for p,m in ambiguous)
        if skipped:
            msg=f'Valid exact auto-matches: {len(patch_items)}\nSkipped/ambiguous: {len(skipped)}\n\n'
            msg+='\n'.join(f'- {Path(p).name}: {reason}' for p,reason in skipped[:20])
            if len(skipped)>20:
                msg+=f'\n...and {len(skipped)-20} more.'
            msg+='\n\nTip: if these files work with single legacy selected convert, select the target rows first and use this same button again. v4.9 will convert them in selected order.'
            if not patch_items or not messagebox.askyesno('Multi-file auto-match review', msg):
                return
        self._patch_many_dds_with_review(pc, patch_items, 'MULTI_FILE_AUTO_SELECT_PATCH_STRICT_EXACT_V4_9', '_PATCHED_MULTI_FILE_AUTO_', 'MULTI_FILE_AUTO_PATCH_LOG')


    def _source_can_convert_to_target(self, source_path:Path, target:dict):
        """Return (mode, reason) for a selected source -> selected target.

        EXACT if DDS matches target descriptor.
        CONVERT if the file is DDS/image but descriptor does not match; source supplies pixels and target supplies width/height/format/mips.
        """
        p=Path(source_path)
        if p.suffix.lower()=='.dds':
            try:
                validate_dds_matches_target(p, target, strict=True)
                return 'EXACT', 'DDS exact target match'
            except Exception as exc:
                return 'CONVERT', 'DDS will convert to selected target format because exact validation failed: ' + str(exc).replace('\n',' | ')
        if p.suffix.lower() in ('.png','.bmp','.jpg','.jpeg'):
            return 'CONVERT', 'Image will convert to selected target format'
        return '', 'Unsupported source file type'

    def _rank_source_for_target_name(self, source_path:Path, target:dict):
        """Small score for assigning unpaired files to selected targets."""
        low=str(Path(source_path).name).lower()
        asset=str(target.get('asset','')).lower()
        h=str(target.get('filename_hash','')).lower()
        score=0
        if h and h in low:
            score+=100
        if asset and asset in low:
            score+=100
        # Asset pieces help when names are partially cleaned
        for piece in re.split(r'[_\\.\\-\\s]+', asset):
            if len(piece) >= 4 and piece in low:
                score += 8
        return score

    def _build_selected_order_smart_items(self, selected_targets:list, source_files:list[Path]):
        """v4.6: Pair selected targets to selected files without dropping files that work singly.

        If counts match, pair by selection order. This is the important bugfix.
        If counts do not match, first use filename/hash matches, then fill remaining targets in order.
        """
        selected_targets=list(selected_targets)
        source_files=[Path(p) for p in source_files]
        smart_items=[]
        report=[]
        skipped=[]
        used_files=set()
        used_targets=set()

        def add_pair(t, p, pair_reason):
            k=target_edit_key(t)
            pp=str(Path(p))
            if k in used_targets:
                skipped.append((p, 'TARGET_ALREADY_USED: '+str(t.get('asset')))); return False
            if pp in used_files:
                skipped.append((p, 'FILE_ALREADY_USED')); return False
            mode, reason = self._source_can_convert_to_target(Path(p), t)
            if not mode:
                skipped.append((p, reason)); return False
            used_targets.add(k); used_files.add(pp)
            smart_items.append({'target':t,'path':Path(p),'mode':mode,'reason':pair_reason+'; '+reason})
            report.append({
                'status':'WILL_PATCH',
                'pair_reason':pair_reason,
                'mode':mode,
                'source':str(p),
                'asset':t.get('asset'),
                'hash':t.get('filename_hash'),
                'target_size':f"{t.get('width')}x{t.get('height')}",
                'target_format':t.get('format_kind'),
                'target_mips':t.get('mips'),
                'target_payload':t.get('component1_size'),
                'detail':reason
            })
            return True

        # Main route: user selected N targets and N files. Respect that order.
        if len(selected_targets)==len(source_files):
            for t,p in zip(selected_targets, source_files):
                add_pair(t,p,'SELECTED_TARGET_ORDER_TO_FILE_PICK_ORDER')
        else:
            # First, strong name/hash assignment.
            candidates=[]
            for ti,t in enumerate(selected_targets):
                for fi,p in enumerate(source_files):
                    score=self._rank_source_for_target_name(p,t)
                    if score>0:
                        candidates.append((score,ti,fi,t,p))
            candidates.sort(reverse=True, key=lambda x:x[0])
            for score,ti,fi,t,p in candidates:
                if target_edit_key(t) in used_targets or str(Path(p)) in used_files:
                    continue
                add_pair(t,p,f'FILENAME_HASH_ASSET_SCORE_{score}')

            # Then fill remaining in order: selected target order with remaining file order.
            remaining_targets=[t for t in selected_targets if target_edit_key(t) not in used_targets]
            remaining_files=[p for p in source_files if str(Path(p)) not in used_files]
            for t,p in zip(remaining_targets, remaining_files):
                add_pair(t,p,'REMAINING_SELECTED_ORDER_FALLBACK')

            # Anything left over is reported, not silently lost.
            for p in source_files:
                if str(Path(p)) not in used_files:
                    skipped.append((p,'EXTRA_FILE_NOT_PAIRED_TO_SELECTED_TARGET'))
            for t in selected_targets:
                if target_edit_key(t) not in used_targets:
                    report.append({
                        'status':'NO_FILE_FOR_SELECTED_TARGET',
                        'pair_reason':'NO_FILE_LEFT',
                        'mode':'',
                        'source':'',
                        'asset':t.get('asset'),
                        'hash':t.get('filename_hash'),
                        'target_size':f"{t.get('width')}x{t.get('height')}",
                        'target_format':t.get('format_kind'),
                        'target_mips':t.get('mips'),
                        'target_payload':t.get('component1_size'),
                        'detail':'No source file was paired to this selected target.'
                    })

        return smart_items, skipped, report


    def manual_replace_selected_with_multiple_files(self):
        """v4.9: Pair selected targets with selected files in order, exact-or-convert.

        This is the clean manual route. It intentionally mirrors single selected patch:
        exact DDS is pasted directly; DDS/image that does not match exactly is used as
        pixels and converted into the selected target's format/mips/payload.
        """
        selected=self.get_selected_targets()
        if not selected:
            messagebox.showinfo('Select targets','Select one or more texture targets first. Use Ctrl-click or Shift-click for more than one.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return

        files=self._pick_multiple_dds_files('Select replacement DDS/image files IN THE SAME ORDER as the selected texture targets')
        if not files:
            return

        smart_items, skipped, report_rows = self._build_selected_order_smart_items(selected, files)
        self._patch_smart_selected_items_with_review(
            pc, selected, files, smart_items, skipped, report_rows,
            f'_PATCHED_SELECTED_PAIR_{len(smart_items)}_FILES',
            'MANUAL_SELECTED_MULTI_PAIR_EXACT_OR_CONVERT_V4_9'
        )


    def manual_replace_selected_with_one_file(self):
        """v3.1: manual one-file replacement for the currently selected TEX target.

        DDS is the recommended/strict path. Other image/raw inputs use the older replacement logic.
        """
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('manual_one_file_replace'):
            return
        start_dir=self.replacement_folder_var.get().strip() or self.get_last_export_dir_for_selected() or self.output_var.get()
        repl=filedialog.askopenfilename(title='Select ONE replacement file for the SELECTED texture', initialdir=start_dir if start_dir else None, filetypes=[('Recommended DDS','*.dds'),('Supported','*.dds *.bin *.raw *.png *.bmp *.jpg *.jpeg'),('All files','*.*')])
        if not repl:
            return
        replp=Path(repl)
        default_name=pc.stem+'_PATCHED_ONE_FILE_'+clean_name(target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out:
            return
        try:
            if replp.suffix.lower()=='.dds':
                # Strict original-format DDS route.
                log=copy_and_patch_pcpack_original_format_dds(pc,target,replp,Path(out))
                log['mode']='MANUAL_SELECTED_ONE_DDS_REPLACE_V3_1'
            else:
                if not messagebox.askyesno('Legacy replacement input', 'This is not a DDS file. PNG/JPG/BIN replacement uses the older/experimental path.\n\nDDS exported from this tool and edited in Paint.NET/GIMP is recommended; the editor-safe route can rebuild many overwritten DDS files back into SM3 format.\n\nContinue anyway?'):
                    return
                log=copy_and_patch_pcpack(pc,target,replp,Path(out))
                log['mode']='MANUAL_SELECTED_ONE_FILE_LEGACY_REPLACE_V3_1'
            log['manual_replacement_file']=str(replp)
            (Path(out).parent/(Path(out).stem+'_MANUAL_ONE_FILE_REPLACE_LOG.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('Manual one-file replace complete', f'Patched selected texture into a new PCPACK copy.\n\nTexture:\n{target.get("asset")}\n\nReplacement:\n{replp}\n\nOutput:\n{out}')
            self.set_status(f'v3.1 manual one-file replace complete: {target.get("asset")} <- {replp.name}')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('Manual one-file replace failed', str(exc))

    def scan_dds_folder_for_manual_picker(self, folder:Path):
        """Scan every DDS in a chosen old/replacement folder and return rich rows.

        Unlike the automatic folder workflow, this intentionally lists DDS files even when
        the tool cannot safely auto-pick a target. The user can manually map a DDS to any
        current TEX target as long as the DDS validates against that target's original
        descriptor.
        """
        folder=Path(folder)
        rows=[]
        if not folder.exists() or not folder.is_dir():
            return rows
        target_by_key={target_edit_key(t):t for t in self.targets}
        for p in sorted(folder.rglob('*.dds')):
            try:
                info=parse_dds_header_file(p)
            except Exception as exc:
                rows.append({'path':p,'file':p.name,'status':'BAD_DDS','error':str(exc),'info':None,'matches':[]})
                continue
            exact=[]; strong=[]; sidecar_target=None
            # 1) Sidecar exact key from this tool's exports.
            for side in [p.with_suffix(p.suffix+'.sm3edit.json'), p.with_suffix('.sm3edit.json')]:
                if side.exists():
                    try:
                        sm=json.loads(side.read_text(encoding='utf-8'))
                        tk=sm.get('target_key')
                        if tk in target_by_key:
                            sidecar_target=target_by_key[tk]
                            break
                    except Exception:
                        pass
            # 2) Validate against every current target by original DDS descriptor.
            for t in self.targets:
                try:
                    _info,_problems=validate_dds_matches_target(p,t,strict=True)
                except Exception:
                    continue
                exact.append(t)
                low=str(p).lower()
                asset=str(t.get('asset','')).lower()
                h=str(t.get('filename_hash','')).lower()
                tk=target_edit_key(t)
                if (sidecar_target is t) or (asset and asset in low) or (h and h in low):
                    strong.append(t)
            method='NO_TARGET_MATCH'
            best=None
            if sidecar_target and sidecar_target in exact:
                method='SIDECAR_EXACT'
                best=sidecar_target
            elif len(strong)==1:
                method='NAME_HASH_EXACT'
                best=strong[0]
            elif len(exact)==1:
                method='UNIQUE_DESCRIPTOR'
                best=exact[0]
            elif len(strong)>1:
                method='MULTIPLE_NAME_MATCHES'
            elif len(exact)>1:
                method='AMBIGUOUS_DESCRIPTOR'
            rows.append({'path':p,'file':p.name,'status':'OK' if exact else 'NO_MATCH','error':'','info':info,'matches':exact,'strong':strong,'best':best,'method':method})
        return rows

    def manual_old_folder_texture_picker(self):
        """v3.0 manual picker: select old folder, load all DDS files, choose exact mappings, patch one PCPACK."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Click Build Preview first so the tool knows the current PCPACK texture targets, then use the manual old folder picker.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
        folder=filedialog.askdirectory(title='Select OLD/PREVIOUS folder containing DDS replacement textures', initialdir=start_dir if start_dir else None)
        if not folder:
            return
        folder=Path(folder)
        self.replacement_folder_var.set(str(folder))
        self.last_export_dir=str(folder)
        dds_rows=self.scan_dds_folder_for_manual_picker(folder)

        win=tk.Toplevel(self.root)
        win.title('Manual Old Folder / One DDS Picker - v4.5')
        win.geometry('1280x780')
        win.minsize(1050,650)
        try:
            win.transient(self.root)
        except Exception:
            pass
        mappings=[]  # list of {'target':dict,'dds':Path,'method':str}
        skip_dds_paths=set()  # DDS paths marked DO NOT PATCH in this picker session
        preview_state={'photo':None}

        top=ttk.Frame(win,padding=8); top.pack(fill='x')
        ttk.Label(top,text='Manual Old Folder Texture Picker',font=('TkDefaultFont',13,'bold')).pack(anchor='w')
        ttk.Label(top,text=f'Folder: {folder}',wraplength=1180).pack(anchor='w')
        ttk.Label(top,text='Pick a current TEX target on the left, pick a DDS from the old folder on the right, then Add Mapping. Use DO NOT PATCH for files you want loaded/previewed but excluded. Patch selected mappings into one new PCPACK copy.',wraplength=1180).pack(anchor='w',pady=(2,0))

        main=ttk.PanedWindow(win,orient='horizontal'); main.pack(fill='both',expand=True,padx=8,pady=6)
        left=ttk.Frame(main,padding=4); main.add(left,weight=3)
        mid=ttk.Frame(main,padding=4); main.add(mid,weight=3)
        right=ttk.Frame(main,padding=4); main.add(right,weight=3)

        ttk.Label(left,text='Current PCPACK TEX targets',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        search_var=tk.StringVar()
        ttk.Entry(left,textvariable=search_var).pack(fill='x',pady=(0,4))
        tframe=ttk.Frame(left); tframe.pack(fill='both',expand=True)
        ttree=ttk.Treeview(tframe,columns=('asset','size','fmt','bytes'),show='headings',selectmode='browse')
        for col,w in [('asset',290),('size',70),('fmt',70),('bytes',80)]:
            ttree.heading(col,text=col); ttree.column(col,width=w,anchor='w',stretch=(col=='asset'))
        ty=ttk.Scrollbar(tframe,orient='vertical',command=ttree.yview); tx=ttk.Scrollbar(tframe,orient='horizontal',command=ttree.xview)
        ttree.configure(yscrollcommand=ty.set,xscrollcommand=tx.set)
        ttree.grid(row=0,column=0,sticky='nsew'); ty.grid(row=0,column=1,sticky='ns'); tx.grid(row=1,column=0,sticky='ew')
        tframe.columnconfigure(0,weight=1); tframe.rowconfigure(0,weight=1)
        self.bind_mousewheel_to_widget(ttree)

        def refill_targets(*_):
            q=search_var.get().lower().strip()
            for iid in ttree.get_children(): ttree.delete(iid)
            for idx,t in enumerate(self.targets):
                hay=' '.join(str(t.get(k,'')) for k in ['asset','filename_hash','format_kind','group']).lower()
                if q and q not in hay: continue
                ttree.insert('', 'end', iid=str(idx), values=(t.get('asset'), f"{t.get('width')}x{t.get('height')}", t.get('format_kind'), t.get('component1_size')))
        search_var.trace_add('write', refill_targets)
        refill_targets()

        ttk.Label(mid,text='DDS files loaded from old/replacement folder',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        dframe=ttk.Frame(mid); dframe.pack(fill='both',expand=True)
        dtree=ttk.Treeview(dframe,columns=('file','fmt','size','method','matches'),show='headings',selectmode='extended')
        for col,w in [('file',300),('fmt',70),('size',70),('method',150),('matches',70)]:
            dtree.heading(col,text=col); dtree.column(col,width=w,anchor='w',stretch=(col=='file'))
        dy=ttk.Scrollbar(dframe,orient='vertical',command=dtree.yview); dx=ttk.Scrollbar(dframe,orient='horizontal',command=dtree.xview)
        dtree.configure(yscrollcommand=dy.set,xscrollcommand=dx.set)
        dtree.grid(row=0,column=0,sticky='nsew'); dy.grid(row=0,column=1,sticky='ns'); dx.grid(row=1,column=0,sticky='ew')
        dframe.columnconfigure(0,weight=1); dframe.rowconfigure(0,weight=1)
        self.bind_mousewheel_to_widget(dtree)

        preview_box=ttk.Frame(mid,padding=(0,6,0,0)); preview_box.pack(fill='x')
        ttk.Label(preview_box,text='Selected DDS preview',font=('TkDefaultFont',9,'bold')).pack(anchor='w')
        preview_img_label=ttk.Label(preview_box,text='No DDS selected',anchor='center')
        preview_img_label.pack(fill='x',pady=(2,2))
        preview_text_var=tk.StringVar(value='Select a DDS on the right list to preview it here.')
        ttk.Label(preview_box,textvariable=preview_text_var,wraplength=360).pack(anchor='w')

        for i,row in enumerate(dds_rows):
            info=row.get('info') or {}
            size=f"{info.get('width','?')}x{info.get('height','?')}" if info else ''
            fmt=info.get('format_kind','') if info else ''
            dtree.insert('', 'end', iid=str(i), values=(row['file'], fmt, size, row.get('method') or row.get('status'), len(row.get('matches') or [])))

        ttk.Label(right,text='Patch mappings',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        mframe=ttk.Frame(right); mframe.pack(fill='both',expand=True)
        mtree=ttk.Treeview(mframe,columns=('asset','dds','method'),show='headings',selectmode='extended')
        for col,w in [('asset',240),('dds',260),('method',110)]:
            mtree.heading(col,text=col); mtree.column(col,width=w,anchor='w',stretch=(col in ('asset','dds')))
        my=ttk.Scrollbar(mframe,orient='vertical',command=mtree.yview); mx=ttk.Scrollbar(mframe,orient='horizontal',command=mtree.xview)
        mtree.configure(yscrollcommand=my.set,xscrollcommand=mx.set)
        mtree.grid(row=0,column=0,sticky='nsew'); my.grid(row=0,column=1,sticky='ns'); mx.grid(row=1,column=0,sticky='ew')
        mframe.columnconfigure(0,weight=1); mframe.rowconfigure(0,weight=1)
        self.bind_mousewheel_to_widget(mtree)

        status=tk.StringVar(value=f'Loaded {len(dds_rows)} DDS files. Valid target-match DDS files: {sum(1 for r in dds_rows if r.get("matches"))}.')
        ttk.Label(win,textvariable=status,style='Status.TLabel',padding=6).pack(fill='x')

        def refresh_mappings():
            for iid in mtree.get_children(): mtree.delete(iid)
            for i,m in enumerate(mappings):
                mtree.insert('', 'end', iid=str(i), values=(m['target'].get('asset'), Path(m['dds']).name, m.get('method','MANUAL')))
            status.set(f'Mappings ready: {len(mappings)}. DDS loaded: {len(dds_rows)}.')

        def selected_target_from_modal():
            sel=ttree.selection()
            if not sel: return None
            try: return self.targets[int(sel[0])]
            except Exception: return None

        def selected_dds_row_from_modal():
            sel=dtree.selection()
            if not sel: return None
            try: return dds_rows[int(sel[0])]
            except Exception: return None

        def update_dds_preview(*_):
            row=selected_dds_row_from_modal()
            if not row:
                preview_state['photo']=None
                preview_img_label.configure(image='', text='No DDS selected')
                preview_text_var.set('Select a DDS on the DDS list to preview it here.')
                return
            p=Path(row.get('path',''))
            info=row.get('info') or {}
            skip_note=' [DO NOT PATCH]' if str(p) in skip_dds_paths else ''
            preview_text_var.set(f"{p.name}{skip_note} | {info.get('width','?')}x{info.get('height','?')} {info.get('format_kind','')} mips {info.get('mips','?')} | matches {len(row.get('matches') or [])}")
            try:
                # v4.8: use the same DDS-aware fallback loader as conversion routes.
                # Some valid/patchable DDS files do not preview through Pillow directly.
                im=load_source_image_any(p).convert('RGBA')
                im.thumbnail((160,160))
                bg=Image.new('RGB', im.size, (225,225,225))
                bg.paste(im, mask=im.split()[-1])
                photo=ImageTk.PhotoImage(bg)
                preview_state['photo']=photo
                preview_img_label.configure(image=photo, text='')
            except Exception as exc:
                preview_state['photo']=None
                preview_img_label.configure(image='', text='Preview unavailable')
                preview_text_var.set(preview_text_var.get() + f' | preview error: {exc}')

        dtree.bind('<<TreeviewSelect>>', update_dds_preview)

        def mark_selected_dds_skip():
            row=selected_dds_row_from_modal()
            if not row:
                messagebox.showinfo('Select DDS','Select one DDS file to mark as DO NOT PATCH.', parent=win); return
            p=str(Path(row.get('path','')))
            skip_dds_paths.add(p)
            # Remove any existing mapping using this DDS path.
            mappings[:] = [m for m in mappings if str(Path(m['dds'])) != p]
            for iid in dtree.selection():
                try:
                    vals=list(dtree.item(iid,'values'))
                    if len(vals)>=4:
                        vals[3]='DO_NOT_PATCH'
                    dtree.item(iid, values=vals)
                except Exception:
                    pass
            refresh_mappings()
            update_dds_preview()
            status.set(f'Marked DO NOT PATCH: {Path(p).name}')

        def unmark_selected_dds_skip():
            row=selected_dds_row_from_modal()
            if not row:
                messagebox.showinfo('Select DDS','Select one DDS file to unmark.', parent=win); return
            p=str(Path(row.get('path','')))
            skip_dds_paths.discard(p)
            for iid in dtree.selection():
                try:
                    r=dds_rows[int(iid)]
                    info=r.get('info') or {}
                    size=f"{info.get('width','?')}x{info.get('height','?')}" if info else ''
                    fmt=info.get('format_kind','') if info else ''
                    dtree.item(iid, values=(r.get('file'), fmt, size, r.get('method') or r.get('status'), len(r.get('matches') or [])))
                except Exception:
                    pass
            update_dds_preview()
            status.set(f'Unmarked DO NOT PATCH: {Path(p).name}')

        def mapping_exists(target, dds):
            for m in mappings:
                if target_edit_key(m['target'])==target_edit_key(target):
                    return True
            return False

        def add_mapping(target, dds_path, method='MANUAL'):
            if str(Path(dds_path)) in skip_dds_paths:
                messagebox.showinfo('DDS marked DO NOT PATCH', f'This DDS is marked DO NOT PATCH:\n{Path(dds_path).name}\n\nUnmark it first if you want to map it.', parent=win)
                return False
            try:
                validate_dds_matches_target(Path(dds_path), target, strict=True)
            except Exception as exc:
                messagebox.showerror('DDS does not match selected TEX target', str(exc), parent=win)
                return False
            if mapping_exists(target, dds_path):
                if not messagebox.askyesno('Replace existing mapping', f"A mapping already exists for:\n{target.get('asset')}\n\nReplace it with this DDS?", parent=win):
                    return False
                mappings[:] = [m for m in mappings if target_edit_key(m['target'])!=target_edit_key(target)]
            mappings.append({'target':target,'dds':Path(dds_path),'method':method})
            refresh_mappings()
            return True

        def add_selected_mapping():
            t=selected_target_from_modal(); row=selected_dds_row_from_modal()
            if not t or not row:
                messagebox.showinfo('Select both sides','Select one current TEX target and one DDS file first.', parent=win); return
            if row.get('status')=='BAD_DDS':
                messagebox.showerror('Bad DDS', row.get('error','Bad DDS'), parent=win); return
            add_mapping(t, row['path'], 'MANUAL_USER_SELECTED')

        def auto_add_strong_matches():
            added=0; ambiguous=0; bad=0
            for row in dds_rows:
                if str(Path(row.get('path',''))) in skip_dds_paths:
                    continue
                t=row.get('best')
                if not t:
                    if row.get('matches'): ambiguous += 1
                    continue
                try:
                    info,_=validate_dds_matches_target(row['path'], t, strict=True)
                except Exception:
                    bad += 1; continue
                original=self.get_original_payload_for_target(t)
                same=(info.get('payload',b'') == original) if original else False
                # Prefer changed files, but still allow exact originals if user is restoring.
                if add_mapping(t, row['path'], row.get('method','AUTO_STRONG')):
                    added += 1
            messagebox.showinfo('Auto Add Strong Matches', f'Added/updated {added} mappings.\nAmbiguous DDS needing manual choice: {ambiguous}\nBad skipped: {bad}', parent=win)

        def add_selected_dds_to_best_target():
            added=0; amb=0
            for iid in dtree.selection():
                try: row=dds_rows[int(iid)]
                except Exception: continue
                if str(Path(row.get('path',''))) in skip_dds_paths:
                    continue
                t=row.get('best')
                if t:
                    if add_mapping(t,row['path'],row.get('method','AUTO_SELECTED_DDS')): added+=1
                else:
                    amb+=1
            if amb:
                messagebox.showinfo('Some DDS are ambiguous', f'Added {added}.\n{amb} selected DDS files need manual target selection on the left.', parent=win)

        def remove_selected_mappings():
            sels=[]
            for iid in mtree.selection():
                try: sels.append(int(iid))
                except Exception: pass
            if not sels: return
            keep=[m for i,m in enumerate(mappings) if i not in set(sels)]
            mappings[:] = keep
            refresh_mappings()

        def clear_mappings():
            mappings.clear(); refresh_mappings()


        def add_one_dds_file_to_picker():
            """v3.2: add one or more DDS files into this manual picker and auto-map when possible."""
            start_dir=self.replacement_folder_var.get().strip() or self.last_export_dir or self.output_var.get()
            paths=filedialog.askopenfilenames(title='Select ONE OR MORE DDS replacement files', initialdir=start_dir if start_dir else None, filetypes=[('DDS','*.dds'),('All files','*.*')], parent=win)
            if not paths:
                return
            added=0; mapped=0; no_match=0; bad=0; ambiguous=0
            for p in paths:
                row=self.scan_one_dds_for_manual_picker(Path(p))
                dds_rows.append(row)
                i=len(dds_rows)-1
                info=row.get('info') or {}
                size=f"{info.get('width','?')}x{info.get('height','?')}" if info else ''
                fmt=info.get('format_kind','') if info else ''
                dtree.insert('', 'end', iid=str(i), values=(row.get('file',Path(p).name), fmt, size, row.get('method') or row.get('status'), len(row.get('matches') or [])))
                added += 1
                try:
                    dtree.selection_add(str(i)); dtree.focus(str(i)); dtree.see(str(i))
                except Exception:
                    pass
                if row.get('status')=='BAD_DDS':
                    bad += 1; continue
                if not row.get('matches'):
                    no_match += 1; continue
                target=selected_target_from_modal() if len(paths)==1 else None
                if target:
                    try:
                        validate_dds_matches_target(Path(p), target, strict=True)
                    except Exception:
                        target=None
                if not target:
                    target=row.get('best')
                if not target and len(row.get('matches') or [])==1:
                    target=row['matches'][0]
                if target:
                    if add_mapping(target, Path(p), row.get('method','MULTI_FILE_AUTO')):
                        mapped += 1
                    try:
                        for idx,t in enumerate(self.targets):
                            if target_edit_key(t)==target_edit_key(target):
                                ttree.selection_set(str(idx)); ttree.focus(str(idx)); ttree.see(str(idx)); break
                    except Exception:
                        pass
                else:
                    ambiguous += 1
            status.set(f'Added {added} DDS file(s). Auto-mapped {mapped}. No match {no_match}. Bad {bad}. Ambiguous {ambiguous}.')
            if bad or no_match or ambiguous:
                messagebox.showinfo('DDS files loaded', f'Added {added} DDS file(s).\nAuto-mapped: {mapped}\nNo target match: {no_match}\nBad DDS: {bad}\nAmbiguous: {ambiguous}\n\nFor ambiguous files, select a target on the left, select the DDS on the right, then click Add Mapping.', parent=win)

        def patch_mappings():
            if not mappings:
                messagebox.showinfo('No mappings','Add mappings first.', parent=win); return
            risky=[]
            if self.diffuse_safe_var.get() or self.strict_diffuse_var.get():
                for m in mappings:
                    r=unsafe_target_reason(m['target'])
                    if r: risky.append((m['target'],r))
                if risky and self.strict_diffuse_var.get():
                    messagebox.showwarning('Strict diffuse-only mode', 'Mappings include non-diffuse/control targets. Disable strict mode or remove them.\n\n'+'\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:12]), parent=win)
                    return
                if risky:
                    msg='Mappings include textures that may not be normal diffuse/color maps. Continue?\n\n'
                    msg+='\n'.join(f"- {t.get('asset')}: {r}" for t,r in risky[:15])
                    if len(risky)>15: msg += f'\n...and {len(risky)-15} more.'
                    if not messagebox.askyesno('Target warning', msg, parent=win):
                        return
            default_name=pc.stem+f'_PATCHED_MANUAL_PICK_{len(mappings)}_DDS'+pc.suffix
            out=filedialog.asksaveasfilename(title='Save patched PCPACK copy from manual mappings', initialfile=default_name, filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')], parent=win)
            if not out: return
            try:
                patch_items=[(m['target'], Path(m['dds'])) for m in mappings]
                log=copy_and_patch_pcpack_original_format_dds_many(pc, patch_items, Path(out))
                rows=[]
                for m in mappings:
                    rows.append({'asset':m['target'].get('asset'),'hash':m['target'].get('filename_hash'),'dds':str(m['dds']),'method':m.get('method',''),'status':'PATCHED'})
                write_csv(Path(out).parent/(Path(out).stem+'_MANUAL_OLD_FOLDER_PICKER_REPORT.csv'), rows)
                (Path(out).parent/(Path(out).stem+'_MANUAL_OLD_FOLDER_PICKER_LOG.json')).write_text(json.dumps({'mode':'MANUAL_OLD_FOLDER_OR_MULTI_DDS_PICKER_V3_2','old_folder':str(folder),'patched_count':len(mappings),'items':rows},indent=2),encoding='utf-8')
                messagebox.showinfo('Manual patch complete', f'Patched {len(mappings)} selected DDS replacements into one new PCPACK copy.\n\nOutput:\n{out}', parent=win)
                status.set(f'Patched {len(mappings)} DDS replacements into {out}')
            except Exception as exc:
                traceback.print_exc(); messagebox.showerror('Manual patch failed', str(exc), parent=win)

        btns=ttk.Frame(win,padding=8); btns.pack(fill='x')
        ttk.Button(btns,text='Add DDS File(s)...',command=add_one_dds_file_to_picker).pack(side='left',padx=3)
        ttk.Button(btns,text='Auto Add Strong Matches',command=auto_add_strong_matches).pack(side='left',padx=3)
        ttk.Button(btns,text='Add Selected DDS -> Best Target',command=add_selected_dds_to_best_target).pack(side='left',padx=3)
        ttk.Button(btns,text='Add Mapping: Left Target <- Right DDS',command=add_selected_mapping).pack(side='left',padx=3)
        ttk.Button(btns,text='DO NOT PATCH Selected DDS',command=mark_selected_dds_skip).pack(side='left',padx=3)
        ttk.Button(btns,text='Unmark DDS',command=unmark_selected_dds_skip).pack(side='left',padx=3)
        ttk.Button(btns,text='Clear Selected Mapping',command=remove_selected_mappings).pack(side='left',padx=3)
        ttk.Button(btns,text='Clear All Mappings',command=clear_mappings).pack(side='left',padx=3)
        ttk.Button(btns,text='PATCH MAPPINGS -> Export PCPACK',command=patch_mappings).pack(side='right',padx=3)
        ttk.Button(btns,text='Close',command=win.destroy).pack(side='right',padx=3)

        # Preload strong matches so the user can remove/add before patching.
        try:
            auto_count=0
            for row in dds_rows:
                if str(Path(row.get('path',''))) in skip_dds_paths:
                    continue
                if row.get('best') and row.get('method') in ('SIDECAR_EXACT','NAME_HASH_EXACT'):
                    t=row['best']
                    try:
                        validate_dds_matches_target(row['path'], t, strict=True)
                    except Exception:
                        continue
                    if not mapping_exists(t,row['path']):
                        mappings.append({'target':t,'dds':Path(row['path']),'method':row.get('method')})
                        auto_count+=1
            refresh_mappings()
            if auto_count:
                status.set(f'Preloaded {auto_count} strong name/sidecar mappings. Review, add missing ones manually, then patch.')
        except Exception:
            pass

    def dump_selected(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose dump output folder') or '')
        if not str(outdir): return
        data=pc.read_bytes(); t=self.selected_target
        for comp in ['component0','component1']:
            s=int(t[f'{comp}_absolute_start_dec']); e=int(t[f'{comp}_absolute_end_dec'])
            name=f"{t.get('filename_hash')}.{clean_name(t.get('asset'))}.{comp}_{e-s}bytes.bin"
            (outdir/name).write_bytes(data[s:e])
        messagebox.showinfo('Dumped','Dumped component0 and component1 for selected texture.')
    def self_replace_selected(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        default_name=pc.stem+'_CONTROL_ORIGINAL_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save original-texture self-replace PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack_with_original_component(pc,self.selected_target,Path(out))
            messagebox.showinfo('Original self-replace copy made','Control copy created. It should be byte-identical to the original.\n\n'+json.dumps(log,indent=2)[:1800])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Self-replace failed',str(e))

    def full_selftest_copy(self):
        if not self.targets:
            messagebox.showinfo('Build preview first','Build Direct Preview first so the TEX target list is loaded.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        default_name=pc.stem+'_CONTROL_ALL_ORIGINAL_TEX'+pc.suffix
        out=filedialog.asksaveasfilename(title='Save full original-texture self-test PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=make_full_original_texture_selftest_copy(pc,self.targets,Path(out))
            messagebox.showinfo('Full original-texture self-test copy made','Full control copy created. It should be byte-identical to the original.\n\n'+json.dumps(log,indent=2)[:1800])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Full self-test failed',str(e))

    def restore_all_tex_from_clean_original(self):
        if not self.targets:
            messagebox.showinfo('Build preview first','Select the white/bad/edited PCPACK, then click Build Direct Preview first so the TEX target list is loaded.')
            return
        bad_pack=Path(self.pcpack_var.get())
        if not bad_pack.exists():
            messagebox.showerror('Missing selected pack','Select the white/bad/edited PCPACK in the main PCPACK box first.')
            return
        clean=filedialog.askopenfilename(title='Select CLEAN untouched original PCPACK to copy original TEX bytes from',filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not clean: return
        default_name=bad_pack.stem+'_RESTORED_ALL_TEX_FROM_CLEAN'+bad_pack.suffix
        out=filedialog.asksaveasfilename(title='Save restored PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=restore_all_tex_from_clean_original_pack(bad_pack, Path(clean), self.targets, Path(out), restore_component0=True)
            messagebox.showinfo('All TEX restored from clean original', 'Restored copy created. Original files were not modified.\n\n'+json.dumps(log,indent=2)[:1900])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Restore failed', str(e))

    def convert_image_selected(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        if not HAS_PIL:
            messagebox.showerror('Pillow missing','Pillow is required for image conversion.')
            return
        if not self.target_safety_ok_or_confirm('convert'):
            return
        img=filedialog.askopenfilename(title='Select source image to convert',filetypes=[('Images','*.png *.bmp *.jpg *.jpeg'),('All files','*.*')])
        if not img: return
        outdir=Path(self.output_var.get())/'CONVERTED_REPLACEMENTS'
        try:
            bin_path,dds_path,preview_path,meta=write_converted_outputs(Path(img), self.selected_target, outdir, force_opaque=self.force_opaque_var.get(), original_preview_path=self.find_best_image_for_asset(self.selected_target.get('asset','')))
            self.selected_image=preview_path
            self.show_image(preview_path)
            self.load_images()
            messagebox.showinfo('Converted image', 'Converted image to exact-size SM3 component1. WARNING: image conversion is experimental; original-format DDS is the clean route.\n\nRaw payload:\n'+str(bin_path)+'\n\nDDS copy:\n'+str(dds_path)+'\n\nPreview:\n'+str(preview_path)+'\n\nSide-by-side is saved next to it when possible.')
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Conversion failed',str(e))

    def convert_and_patch_selected(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('convert_patch'):
            return
        img=filedialog.askopenfilename(title='Select source image to convert + patch',filetypes=[('Images','*.png *.bmp *.jpg *.jpeg'),('All files','*.*')])
        if not img: return
        outdir=Path(self.output_var.get())/'CONVERTED_REPLACEMENTS'
        try:
            bin_path,dds_path,preview_path,meta=write_converted_outputs(Path(img), self.selected_target, outdir, force_opaque=self.force_opaque_var.get(), original_preview_path=self.find_best_image_for_asset(self.selected_target.get('asset','')))
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Conversion failed',str(e))
            return
        default_name=pc.stem+'_PATCHED_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack(pc,self.selected_target,bin_path,Path(out))
            self.selected_image=preview_path
            self.show_image(preview_path)
            messagebox.showinfo('Converted + patched copy made','Converted image and patched a new PCPACK copy. Original was not modified.\n\n'+json.dumps(log,indent=2)[:1500])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Patch failed',str(e))



    def make_edited_dds_test_and_patch(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('edited_dds_test_patch'):
            return
        default_name=pc.stem+'_PATCHED_EDITED_DDS_TEST_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save edited-DDS test patched PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            outdir=Path(self.output_var.get())/'DDS_EDIT_TESTS'
            combo=export_test_edited_dds_and_patch(pc,self.selected_target,outdir,Path(out))
            messagebox.showinfo('Edited DDS test patch made',
                'Created an edited DDS test and patched it into a NEW PCPACK copy. Original was not modified.\n\n'
                'This test preserves original DDS format/mips/payload size and only changes color data.\n\n'
                + json.dumps(combo,indent=2)[:1800])
            self.load_images()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Edited DDS test failed',str(e))

    def get_last_export_dir_for_selected(self):
        if not self.selected_target:
            return None
        key=target_edit_key(self.selected_target)
        meta=self.dds_export_history.get(key) or {}
        p=meta.get('dds') or meta.get('original_dds_path')
        if p and Path(p).exists():
            return str(Path(p).parent)
        if self.last_export_dir and Path(self.last_export_dir).exists():
            return str(self.last_export_dir)
        return None

    def get_original_payload_for_target(self, target):
        pc=Path(self.pcpack_var.get())
        if not (target and pc.exists()):
            return b''
        data=pc.read_bytes()
        s=int(target['component1_absolute_start_dec']); e=int(target['component1_absolute_end_dec'])
        return bytes(data[s:e])

    def get_original_payload_for_selected(self):
        return self.get_original_payload_for_target(self.selected_target)

    def find_auto_edited_dds_candidates(self, target=None):
        """Find edited DDS candidates for a selected/supplied target.

        v2.5 behavior:
        - remembers exported DDS paths in the current session;
        - reads .sm3edit.json sidecars/index files if present;
        - scans likely edit folders for matching hash/name .dds files;
        - validates DDS width/height/mips/format/payload before returning it;
        - prefers files whose payload differs from the original PCPACK component1;
        - can be called for one selected texture or many selected textures during batch patching.
        """
        target = target or self.selected_target
        if not target:
            return []
        key=target_edit_key(target)
        pc=Path(self.pcpack_var.get())
        original_payload=self.get_original_payload_for_target(target) if pc.exists() else b''
        asset=clean_name(str(target.get('asset',''))).lower()
        hashv=str(target.get('filename_hash','')).lower()
        folders=[]
        meta=self.dds_export_history.get(key) or {}
        for p in [meta.get('dds'), meta.get('original_dds_path')]:
            if p:
                pp=Path(p)
                if pp.exists(): folders.append(pp.parent)
        repl_folder = self.replacement_folder_var.get().strip() if hasattr(self, 'replacement_folder_var') else ''
        if repl_folder:
            folders.append(Path(repl_folder))
        if self.last_export_dir:
            folders.append(Path(self.last_export_dir))
        outroot=Path(self.output_var.get())
        folders += [outroot, outroot/'DDS_EXPORTS', outroot/'DDS_EDIT_WORK', outroot/'DDS_EDIT_TESTS', outroot/'EXPORTED_DDS_FOR_EDITING']
        # Remove duplicates and non-existing dirs.
        uniq=[]
        seen=set()
        for f in folders:
            try:
                rf=Path(f).resolve()
            except Exception:
                continue
            if rf.exists() and rf.is_dir() and str(rf).lower() not in seen:
                seen.add(str(rf).lower()); uniq.append(rf)
        candidate_paths=[]
        # Explicit recorded DDS first.
        for p in [meta.get('dds'), meta.get('original_dds_path')]:
            if p and Path(p).exists(): candidate_paths.append(Path(p))
        # Scan matching DDS names in likely folders. Keep this small and safe.
        for folder in uniq:
            try:
                for p in folder.rglob('*.dds'):
                    try:
                        rel=str(p.relative_to(folder))
                        # The user-selected replacement folder is trusted, so allow deeper artist subfolders there.
                        repl_root = self.replacement_folder_var.get().strip() if hasattr(self, 'replacement_folder_var') else ''
                        is_repl_root = repl_root and str(Path(folder).resolve()).lower()==str(Path(repl_root).resolve()).lower()
                        if (not is_repl_root) and rel.count(os.sep)>2:
                            continue
                    except Exception:
                        pass
                    low=p.name.lower()
                    if hashv and hashv in low:
                        candidate_paths.append(p)
                    elif asset and asset in low:
                        candidate_paths.append(p)
                    else:
                        side=p.with_suffix(p.suffix+'.sm3edit.json')
                        if side.exists():
                            try:
                                sm=json.loads(side.read_text(encoding='utf-8'))
                                if sm.get('target_key')==key:
                                    candidate_paths.append(p)
                            except Exception:
                                pass
            except Exception:
                continue
        # Deduplicate.
        dedup=[]; seen=set()
        for p in candidate_paths:
            try: rp=Path(p).resolve()
            except Exception: continue
            if str(rp).lower() in seen: continue
            seen.add(str(rp).lower()); dedup.append(rp)
        results=[]
        for p in dedup:
            try:
                info, problems = validate_dds_matches_target(p, target, strict=True)
            except Exception as e:
                continue
            payload=info.get('payload',b'')
            same=(payload == original_payload) if original_payload else False
            low=p.name.lower()
            score=0
            if meta.get('dds') and safe_rel(p)==safe_rel(Path(meta.get('dds'))): score += 100
            if not same: score += 50
            else: score -= 50
            repl_root = self.replacement_folder_var.get().strip() if hasattr(self, 'replacement_folder_var') else ''
            if repl_root:
                try:
                    Path(p).resolve().relative_to(Path(repl_root).resolve())
                    score += 80
                except Exception:
                    pass
            if any(x in low for x in ['edit','edited','final','mod','custom','paint','replace','replacement']): score += 25
            if hashv and hashv in low: score += 15
            if asset and asset in low: score += 15
            try: score += min(20, max(0, int((p.stat().st_mtime)/100000000)))
            except Exception: pass
            results.append({'path':p,'info':info,'same_as_original':same,'score':score,'mtime':p.stat().st_mtime if p.exists() else 0})
        results.sort(key=lambda r:(not r['same_as_original'], r['score'], r['mtime']), reverse=True)
        return results

    def auto_detect_edited_dds_and_patch(self):
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('auto_detect_edited_dds_patch'):
            return
        candidates=self.find_auto_edited_dds_candidates()
        edited=[c for c in candidates if not c.get('same_as_original')]
        if not edited:
            msg='No edited DDS was auto-detected for the selected texture.\n\n'
            msg+='v2.4 expects this workflow:\n'
            msg+='1. Export Original DDS for Editing.\n'
            msg+='2. Edit/overwrite that DDS in Paint.NET or GIMP.\n'
            msg+='3. Save with the SAME format and mipmaps.\n'
            msg+='4. Or set Replacement DDS folder to the folder where your edited DDS files are saved.\n'
            msg+='5. Click AUTO: Detect Edited DDS + Patch COPY.\n\n'
            if candidates:
                msg+='Matching DDS files were found, but they appear byte-identical to the original texture payload. Edit/save the DDS first.\n\n'
                msg+='Best match:\n'+str(candidates[0]['path'])
            messagebox.showinfo('No edited DDS found', msg)
            return
        chosen=edited[0]
        info=chosen['info']
        confirm=(
            'Auto-detected edited DDS for this selected texture:\n\n'
            f"Texture: {self.selected_target.get('asset')}\n"
            f"DDS: {chosen['path']}\n\n"
            f"Format: {info.get('format_kind')}\n"
            f"Size: {info.get('width')}x{info.get('height')}\n"
            f"Mips: {info.get('mips')}\n"
            f"Payload: {len(info.get('payload',b''))} bytes\n\n"
            'Patch this DDS into a NEW PCPACK copy?'
        )
        if not messagebox.askyesno('Confirm auto-detected DDS', confirm):
            return
        default_name=pc.stem+'_PATCHED_AUTO_DDS_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack_original_format_dds(pc,self.selected_target,Path(chosen['path']),Path(out))
            log['auto_detected_dds']=str(chosen['path'])
            messagebox.showinfo('Auto-detected DDS patch made','Patched copy created using auto-detected edited DDS. Original PCPACK was not modified.\n\n'+json.dumps(log,indent=2)[:1900])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Auto patch failed',str(e))

    def patch_selected_original_format_dds(self):
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('original_format_dds_patch'):
            return
        initialdir=self.get_last_export_dir_for_selected() or None
        dds=filedialog.askopenfilename(title='Select edited DDS exported from this SAME target',initialdir=initialdir,filetypes=[('DDS','*.dds'),('All files','*.*')])
        if not dds: return
        try:
            info, problems = validate_dds_matches_target(Path(dds), self.selected_target, strict=True)
        except Exception as e:
            messagebox.showerror('DDS does not match target', str(e) + '\n\nUse Export Original DDS for Editing first, edit that DDS, and keep the same format/mips/size.')
            return
        default_name=pc.stem+'_PATCHED_ORIGINAL_DDS_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack_original_format_dds(pc,self.selected_target,Path(dds),Path(out))
            messagebox.showinfo('Original-format DDS patch made','Patched copy created using validated original DDS format. Original was not modified.\n\n'+json.dumps(log,indent=2)[:1800])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Patch failed',str(e))

    def patch_selected(self):
        target=self.resolve_current_selected_target()
        if not target:
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        if not self.target_safety_ok_or_confirm('patch'):
            return
        repl=filedialog.askopenfilename(title='Select replacement raw component1 or DDS/PNG (DDS strongly recommended)',filetypes=[('Supported','*.bin *.raw *.dds *.png *.bmp *.jpg *.jpeg'),('All files','*.*')])
        if not repl: return
        default_name=pc.stem+'_PATCHED_'+clean_name(self.selected_target.get('asset','tex'))+pc.suffix
        out=filedialog.asksaveasfilename(title='Save patched PCPACK copy as',initialfile=default_name,filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if not out: return
        try:
            log=copy_and_patch_pcpack(pc,self.selected_target,Path(repl),Path(out))
            messagebox.showinfo('Patched copy made','Patched copy created. Original was not modified.\n\n'+json.dumps(log,indent=2)[:1500])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('Patch failed',str(e))
