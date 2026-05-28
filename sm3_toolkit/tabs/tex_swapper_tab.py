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
  - v3.4 adds an explicit OLD ONE FILE AUTO option that uses the original v3.1 one-DDS auto-select workflow.
  - v3.6 fixes false 'No texture selected' errors.
  - v3.7 cleans up the UI by removing the extra SAME FILE(S) select button and making the old selected one-file direct export the primary one-file workflow.
  - v3.8 fixes the selected one-file workflow by offering Target-Format Convert when the chosen DDS/image does not match the selected slot.
  - v3.9 restores file-first ONE FILE AUTO so selecting a texture first is not required.
  - v4.0 Stable Final separates exact DDS patching, selected-target conversion, and file-first auto replacement so each workflow behaves consistently.
  - v4.7 Manual Options Audit adds clearer selection display, Clear Search, stronger selection resolving, improved exact/convert fallback, and a sanity check report.
  - v4.8 Preview Output Safety Fix stops PREVIEW_OUTPUT nesting, avoids deleting user-selected folders, improves manual DDS preview fallback, and normalizes hash logging.
  - v4.9 Multi-Select Single-Patch Parity Fix makes selected multi-file patching use the same exact-or-convert path as the working single selected patch route.
  - v5.0 Reimport-All Single-Patch Parity Fix makes folder reimport trust exact hash/asset filenames and use exact-or-convert instead of skipping name-locked files as ambiguous.
  - THE TEX SWAPPER build adds visible TSGAMING264 branding and a refreshed header/status interface.
  - This base tool does NOT include red-suit-to-black-suit swap/comparison logic; that remains separate.

Insert safety rules:
  - Exact same-size replacement only.
  - Original PCPACK is never modified.
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
CORE_IMPORT_ERROR = None

SM3_MAGIC_OFF=0x30
SM3_COUNT_OFF=0x54
SM3_TABLE_START_CANDIDATES=[0x36C,0x368,0x364,0x370,0x360,0x35C,0x374]
SM3_MAGIC=b'hsam'
NCH_MAGIC=b'NCH\x00'
FOURCC_OK={b'DXT1',b'DXT3',b'DXT5'}
IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp'}

APP_NAME='THE TEX SWAPPER'
APP_AUTHOR='TSGAMING264'
APP_BUILD='Creator Safe v1.1 - One File Auto Restored'
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
    """Parse PCPACK, write TEX component folders, and return texture target rows."""
    pack=SM3PCPack(pcpack_path)
    chain_root=ensure_dir(out_root/'_DIRECT_PCPACK_TEX_CHAIN')
    tex_root=ensure_dir(chain_root/'TEX')
    reports=ensure_dir(out_root/'REPORTS')
    targets=[]; apkf_summaries=[]
    for outer in pack.apkf_entries():
        label=f'F{outer.index:04d}_{hex32(outer.hash)}_T{outer.type_id:02X}'
        payload=pack.data[outer.offset:outer.end]
        try:
            apkf=APKFArchive(payload,label)
        except Exception as e:
            apkf_summaries.append({'label':label,'error':str(e)})
            continue
        apkf_summaries.append({'label':label,'outer_index':outer.index,'outer_hash':hex32(outer.hash),'outer_offset':hex(outer.offset),'outer_size':outer.size,'file_count':len(apkf.files)})
        for f in apkf.files:
            if f.file_type.upper()!='TEX' or len(f.component_offsets)<2: continue
            (c0s,c0e),(c1s,c1e)=f.component_offsets[0],f.component_offsets[1]
            abs0s=outer.offset+c0s; abs0e=outer.offset+c0e; abs1s=outer.offset+c1s; abs1e=outer.offset+c1e
            c0=pack.data[abs0s:abs0e]; c1=pack.data[abs1s:abs1e]
            desc=parse_tex_desc(c0) or {}
            safe=clean_name(f.filename, f'TEX_{f.global_index:05d}')
            h=hex32(f.filename_hash)
            d=ensure_dir(tex_root/f'{f.global_index:05d}_TEX_{h}_{safe}')
            (d/f'component0_{len(c0)}bytes.bin').write_bytes(c0)
            (d/f'component1_{len(c1)}bytes.bin').write_bytes(c1)
            row={
                'asset':f.filename,'safe_asset':safe,'filename_hash':h,'file_type':'TEX','global_index':f.global_index,
                'source_apkf_label':label,'source_outer_index':outer.index,'source_outer_hash':hex32(outer.hash),
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
    (reports/'PACK_DETECT.json').write_text(json.dumps(pack.detect_info,indent=2),encoding='utf-8')
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
    return {
        'path':str(path),'width':width,'height':height,'mips':mips,
        'pf_size':pf_size,'pf_flags':hex(pf_flags),'fourcc':fourcc.decode('ascii','replace'),
        'rgbbits':rgbbits,'rmask':hex(rmask),'gmask':hex(gmask),'bmask':hex(bmask),'amask':hex(amask),
        'format_kind':fmt,'header_size':header_size,'payload_size':len(payload),'payload':payload
    }

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
    if fmt in ('DXT1','DXT3','DXT5'):
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
    dds_bytes=build_dds_header(w,h,mips,fmt,len(payload))+payload
    dds.write_bytes(dds_bytes)
    meta={'asset':target.get('asset'),'hash':hashv,'format':fmt,'width':w,'height':h,'mips':mips,'component1_size':len(payload),'dds':str(dds),'raw':str(raw),'target_key':target_edit_key(target),'original_dds_sha256':sha256_bytes(dds_bytes),'original_component1_sha256':sha256_bytes(payload),'note':'v2.4 recommended route: edit this DDS externally, keep same width/height/mips/format, then use AUTO: Detect Edited DDS + Patch COPY or Patch COPY with ORIGINAL-FORMAT DDS.'}
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
    meta['note']='Edit/overwrite the DDS in Paint.NET, then use AUTO: Detect Edited DDS + Patch COPY. The tool will validate format/mips/size before patching.'
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
        self.output_var=tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.replacement_folder_var=tk.StringVar()
        self.search_var=tk.StringVar()
        self.force_opaque_var=tk.BooleanVar(value=True)
        self.diffuse_safe_var=tk.BooleanVar(value=True)
        self.strict_diffuse_var=tk.BooleanVar(value=False)
        self.status_var=tk.StringVar(value=f'Ready. {APP_NAME} by {APP_AUTHOR}.')
        self.selected_target_var=tk.StringVar(value='Selected texture: none')
        self.targets=[]; self.filtered=[]; self.images=[]; self.selected_target=None; self.selected_image=None
        self.img_ref=None
        self.dark_mode=True
        self.dds_export_history={}  # target_key -> export metadata from this session
        self.last_export_dir=None
        self.style=ttk.Style()
        self.build_ui()
        self.apply_theme(True)

    def apply_theme(self, dark=True):
        """Apply a readable dark/light theme to the Tk/ttk UI."""
        self.dark_mode = bool(dark)
        if self.dark_mode:
            bg='#171717'; panel='#202020'; fg='#F2F2F2'; muted='#BDBDBD'; entry='#2B2B2B'; accent='#3A78D8'; select='#404B64'
            header_bg='#101318'; brand_fg='#DCE6F2'; byline_fg='#AFC0D6'
        else:
            bg='#F0F0F0'; panel='#FFFFFF'; fg='#111111'; muted='#333333'; entry='#FFFFFF'; accent='#2B5EAA'; select='#CDE1FF'
            header_bg='#FFFFFF'; brand_fg='#1F2937'; byline_fg='#4B5563'
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        try:
            self.root.configure(bg=bg)
        except Exception:
            pass
        for sty in ['TFrame','TLabelframe','TNotebook','TNotebook.Tab']:
            try: self.style.configure(sty, background=bg, foreground=fg)
            except Exception: pass
        try: self.style.configure('TLabel', background=bg, foreground=fg)
        except Exception: pass
        try:
            self.style.configure('Header.TFrame', background=header_bg)
            self.style.configure('Brand.TLabel', background=header_bg, foreground=brand_fg, font=('Segoe UI',18,'bold'))
            self.style.configure('Byline.TLabel', background=header_bg, foreground=byline_fg, font=('Segoe UI',10,'bold'))
            self.style.configure('HeaderNote.TLabel', background=header_bg, foreground=muted, font=('Segoe UI',9))
            self.style.configure('Status.TLabel', background=panel, foreground=fg)
        except Exception: pass
        try: self.style.configure('TCheckbutton', background=bg, foreground=fg)
        except Exception: pass
        try:
            self.style.configure('TButton', background=panel, foreground=fg, bordercolor='#555555', focusthickness=1, focuscolor=accent)
            self.style.map('TButton', background=[('active', '#333333' if self.dark_mode else '#E5E5E5')])
        except Exception: pass
        try:
            self.style.configure('TEntry', fieldbackground=entry, foreground=fg, insertcolor=fg)
        except Exception: pass
        try:
            self.style.configure('Treeview', background=entry, fieldbackground=entry, foreground=fg, rowheight=24)
            self.style.configure('Treeview.Heading', background=panel, foreground=fg)
            self.style.map('Treeview', background=[('selected', select)], foreground=[('selected', fg)])
        except Exception: pass
        for widget in getattr(self, '_theme_widgets', []):
            try:
                cls=widget.winfo_class()
                if cls in ('Text','Listbox'):
                    widget.configure(bg=entry, fg=fg, insertbackground=fg, selectbackground=select, selectforeground=fg, highlightbackground=panel, highlightcolor=accent)
                else:
                    widget.configure(bg=bg, fg=fg)
            except Exception:
                pass
        try:
            self.info.configure(bg=entry, fg=fg, insertbackground=fg, selectbackground=select, selectforeground=fg)
            self.img_list.configure(bg=entry, fg=fg, selectbackground=select, selectforeground=fg)
        except Exception:
            pass
        mode='Dark mode ON.' if self.dark_mode else 'Light mode ON.'
        self.set_status(f'{mode} {APP_NAME} by {APP_AUTHOR} is ready.')

    def toggle_dark_mode(self):
        self.apply_theme(not getattr(self, 'dark_mode', True))

    def build_ui(self):
        # Menu fallback keeps every major action reachable even on small screens.
        menubar=tk.Menu(self.root)
        file_menu=tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open PCPACK...', command=self.choose_pcpack)
        file_menu.add_command(label='Choose Output Folder...', command=self.choose_output)
        file_menu.add_command(label='Select Replacement Folder...', command=self.choose_replacement_folder)
        file_menu.add_command(label='Open Output Folder', command=lambda: open_path(Path(self.output_var.get())))
        file_menu.add_command(label='Open Replacement Folder', command=self.open_replacement_folder)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)

        actions_menu=tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label='Build TEX Preview', command=self.build_preview)
        actions_menu.add_separator()
        actions_menu.add_command(label='EXPORT ALL DDS', command=self.export_all_dds)
        actions_menu.add_command(label='ONE FILE AUTO: File First -> Patch', command=self.old_one_file_auto_select_and_patch)
        actions_menu.add_command(label='SELECTED CONVERT: Image/DDS -> Target Format', command=self.selected_target_format_convert_direct)
        actions_menu.add_command(label='AUTO Detect Edited DDS + Patch', command=self.auto_detect_edited_dds_and_patch)
        actions_menu.add_command(label='REIMPORT ALL DDS FOLDER -> ONE PACK', command=self.reimport_all_dds_folder)
        actions_menu.add_command(label='SMART REIMPORT: Exact + Convert Mips -> ONE PACK', command=self.smart_reimport_all_folder)
        actions_menu.add_separator()
        actions_menu.add_command(label='RESTORE: All TEX from Clean Original Pack', command=self.restore_all_tex_from_clean_original)
        actions_menu.add_command(label='BUGCHECK: Scan Current Targets', command=self.bugcheck_current_targets)
        menubar.add_cascade(label='Actions', menu=actions_menu)

        view_menu=tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label='Toggle Dark / Light', command=self.toggle_dark_mode)
        view_menu.add_command(label='Open Index', command=self.open_index)
        view_menu.add_command(label='Reload Output', command=self.reload_existing)
        menubar.add_cascade(label='View', menu=view_menu)
        self._tool_menu = menubar

        header=ttk.Frame(self.root,style='Header.TFrame',padding=(12,8,12,6)); header.pack(fill='x')
        ttk.Label(header,text=APP_NAME,style='Brand.TLabel').grid(row=0,column=0,sticky='w')
        ttk.Label(header,text=f'Made by {APP_AUTHOR}',style='Byline.TLabel').grid(row=0,column=1,sticky='w',padx=(12,0))
        ttk.Label(header,text=APP_BUILD,style='HeaderNote.TLabel').grid(row=0,column=2,sticky='e')
        ttk.Label(header,text='SM3 PC texture export/reimport workflow - clean creator-safe layout.',style='HeaderNote.TLabel').grid(row=1,column=0,columnspan=3,sticky='w',pady=(2,0))
        header.columnconfigure(1,weight=1)

        # Top file selectors stay compact so they do not push action buttons off-screen.
        top=ttk.Frame(self.root,padding=(8,6,8,4)); top.pack(fill='x')
        ttk.Label(top,text='Clean SM3 PCPACK:').grid(row=0,column=0,sticky='w')
        ttk.Entry(top,textvariable=self.pcpack_var,width=72).grid(row=0,column=1,sticky='ew',padx=4)
        ttk.Button(top,text='Browse PCPACK',command=self.choose_pcpack).grid(row=0,column=2,padx=2)
        ttk.Button(top,text='Build Preview',command=self.build_preview).grid(row=0,column=3,padx=2)
        ttk.Label(top,text='Output folder:').grid(row=1,column=0,sticky='w',pady=(4,0))
        ttk.Entry(top,textvariable=self.output_var,width=72).grid(row=1,column=1,sticky='ew',padx=4,pady=(4,0))
        ttk.Button(top,text='Choose Output',command=self.choose_output).grid(row=1,column=2,padx=2,pady=(4,0))
        ttk.Button(top,text='Open Output',command=lambda: open_path(Path(self.output_var.get()))).grid(row=1,column=3,padx=2,pady=(4,0))
        ttk.Label(top,text='Replacement DDS folder:').grid(row=2,column=0,sticky='w',pady=(4,0))
        ttk.Entry(top,textvariable=self.replacement_folder_var,width=72).grid(row=2,column=1,sticky='ew',padx=4,pady=(4,0))
        ttk.Button(top,text='Select Repl Folder',command=self.choose_replacement_folder).grid(row=2,column=2,padx=2,pady=(4,0))
        ttk.Button(top,text='Open Repl',command=self.open_replacement_folder).grid(row=2,column=3,padx=2,pady=(4,0))
        top.columnconfigure(1,weight=1)

        mid=ttk.Frame(self.root,padding=(8,0,8,4)); mid.pack(fill='x')
        ttk.Label(mid,text='Search textures:').grid(row=0,column=0,sticky='w')
        ent=ttk.Entry(mid,textvariable=self.search_var,width=34); ent.grid(row=0,column=1,sticky='ew',padx=4)
        ent.bind('<KeyRelease>',lambda e:self.apply_filter())
        ttk.Button(mid,text='Clear Search',command=self.clear_search).grid(row=0,column=2,padx=2)
        ttk.Checkbutton(mid,text='Force opaque RGB',variable=self.force_opaque_var).grid(row=0,column=3,sticky='w',padx=4)
        ttk.Checkbutton(mid,text='Warn non-diffuse',variable=self.diffuse_safe_var).grid(row=0,column=4,sticky='w',padx=4)
        ttk.Checkbutton(mid,text='Strict diffuse only',variable=self.strict_diffuse_var).grid(row=0,column=5,sticky='w',padx=4)
        ttk.Button(mid,text='Open Index',command=self.open_index).grid(row=0,column=6,padx=2)
        ttk.Button(mid,text='Reload',command=self.reload_existing).grid(row=0,column=7,padx=2)
        ttk.Button(mid,text='Dark/Light',command=self.toggle_dark_mode).grid(row=0,column=8,padx=2)
        ttk.Label(mid,textvariable=self.selected_target_var,style='Status.TLabel').grid(row=1,column=0,columnspan=9,sticky='ew',pady=(4,0))
        mid.columnconfigure(1,weight=1)

        # Main body: left = target list, middle = preview/info, right = always-visible action panel.
        body=ttk.PanedWindow(self.root,orient='horizontal'); body.pack(fill='both',expand=True,padx=8,pady=(0,8))

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

        right=ttk.Frame(body,padding=4); body.add(right,weight=2)
        ttk.Label(right,text='Actions - clean creator workflow',font=('TkDefaultFont',11,'bold')).pack(anchor='w')
        actions=ttk.Notebook(right)
        actions.pack(fill='x',expand=False,pady=(2,6))

        def _scroll_tab(name):
            outer=ttk.Frame(actions)
            actions.add(outer,text=name)
            canvas=tk.Canvas(outer,highlightthickness=0,borderwidth=0,height=205)
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

        tab_main=_scroll_tab('Main')
        _grid_btn(tab_main,'EXPORT ALL DDS',self.export_all_dds,0,0,2)
        _grid_btn(tab_main,'ONE FILE AUTO: File First -> Patch',self.old_one_file_auto_select_and_patch,1,0,2)
        _grid_btn(tab_main,'SELECTED CONVERT: Image/DDS -> Target Format',self.selected_target_format_convert_direct,2,0,2)
        _grid_btn(tab_main,'AUTO Detect Edited DDS + Patch',self.auto_detect_edited_dds_and_patch,3,0,2)
        _grid_btn(tab_main,'Set Replacement Folder',self.choose_replacement_folder,4,0,2)
        _grid_btn(tab_main,'REIMPORT ALL DDS FOLDER -> ONE PACK',self.reimport_all_dds_folder,5,0,2)
        _grid_btn(tab_main,'SMART REIMPORT: Exact + Convert Mips -> ONE PACK',self.smart_reimport_all_folder,6,0,2)
        _grid_btn(tab_main,'Open Output Folder',lambda: open_path(Path(self.output_var.get())),7,0)
        _grid_btn(tab_main,'Open Replacement Folder',self.open_replacement_folder,7,1)

        tab_recovery=_scroll_tab('Recovery')
        _grid_btn(tab_recovery,'TEST Safe Edited DDS + Patch',self.make_edited_dds_test_and_patch,0,0,2)
        _grid_btn(tab_recovery,'RESTORE: All TEX from Clean Original Pack',self.restore_all_tex_from_clean_original,1,0,2)
        _grid_btn(tab_recovery,'BUGCHECK: Scan Current Targets',self.bugcheck_current_targets,2,0,2)
        _grid_btn(tab_recovery,'CONTROL: Original Selected Texture',self.self_replace_selected,3,0,2)

        tab_advanced=_scroll_tab('Advanced')
        _grid_btn(tab_advanced,'Dump Component0/1',self.dump_selected,0,0,2)
        _grid_btn(tab_advanced,'BATCH Export DDS for Selected',self.batch_export_original_dds,1,0,2)
        _grid_btn(tab_advanced,'Patch COPY with Replacement',self.patch_selected,2,0,2)
        _grid_btn(tab_advanced,'CONTROL: Full Original-Texture Self Test',self.full_selftest_copy,3,0,2)
        _grid_btn(tab_advanced,'MANUAL OPTIONS CHECK',self.manual_options_check,4,0,2)

        ttk.Separator(right,orient='horizontal').pack(fill='x',pady=(4,6))
        ttk.Label(right,text='Preview Files',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        img_frame=ttk.Frame(right); img_frame.pack(fill='both',expand=True)
        self.img_list=tk.Listbox(img_frame,height=12,selectmode='browse')
        img_y=ttk.Scrollbar(img_frame,orient='vertical',command=self.img_list.yview)
        img_x=ttk.Scrollbar(img_frame,orient='horizontal',command=self.img_list.xview)
        self.img_list.configure(yscrollcommand=img_y.set,xscrollcommand=img_x.set)
        self._theme_widgets=[self.info,self.img_list]
        self.img_list.grid(row=0,column=0,sticky='nsew')
        img_y.grid(row=0,column=1,sticky='ns')
        img_x.grid(row=1,column=0,sticky='ew')
        img_frame.columnconfigure(0,weight=1); img_frame.rowconfigure(0,weight=1)
        self.img_list.bind('<<ListboxSelect>>',self.on_image_select)
        self.bind_mousewheel_to_widget(self.img_list)
        img_btns=ttk.Frame(right); img_btns.pack(fill='x',pady=4)
        ttk.Button(img_btns,text='Open Image',command=self.open_selected_image).pack(side='left',padx=2)
        ttk.Button(img_btns,text='Open Folder',command=self.open_selected_image_folder).pack(side='left',padx=2)

        ttk.Label(self.root,textvariable=self.status_var,relief='sunken',anchor='w',style='Status.TLabel').pack(side='bottom',fill='x')

    def choose_pcpack(self):
        p=filedialog.askopenfilename(title='Select clean Spider-Man 3 PC .PCPACK',filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')])
        if p: self.pcpack_var.set(p)
    def choose_output(self):
        p=filedialog.askdirectory(title='Select output folder')
        if p:
            self.output_var.set(p)
            # If no replacement folder has been chosen yet, use the output folder as a useful default.
            if not self.replacement_folder_var.get().strip():
                self.replacement_folder_var.set(p)

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

    def manual_options_check(self):
        """v4.7: Audit manual workflow wiring and current patch readiness."""
        outroot = Path(self.output_var.get() or DEFAULT_OUTPUT_DIR)
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
                f"One target selected: use SELECTED EXACT if DDS matches, or SELECTED CONVERT / SMART route if mips-format differ. Target={t.get('asset')} {t.get('width')}x{t.get('height')} {t.get('format_kind')} mips {t.get('mips')}"
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
            msg = f'Manual options check found {error_count} ERROR(s) and {warn_count} warning(s).\\n\\nReport folder:\\n{report_dir}'
            messagebox.showerror('Manual Options Check', msg)
        else:
            msg = f'Manual options check passed. Warnings: {warn_count}.\\n\\nReport folder:\\n{report_dir}'
            messagebox.showinfo('Manual Options Check', msg)
        self.set_status(f'Manual options check complete. Errors={error_count}, warnings={warn_count}. Report: {report_dir}')


    def bugcheck_current_targets(self):
        """Write a small sanity report for the currently scanned PCPACK/TEX target list."""
        if not self.targets:
            messagebox.showinfo('Build preview first','Build Preview or Reload first.')
            return
        outroot = Path(self.output_var.get())
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
        raw_out=Path(self.output_var.get().strip() or DEFAULT_OUTPUT_DIR)
        base_out=resolve_user_output_base(raw_out)
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Select an original SM3 .PCPACK first.')
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
            core.process(chain, preview_out)
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
            self.set_status(f'Done. Loaded {len(targets)} texture targets and {len(self.images)} preview images. Workspace: {out}')
        except Exception as e:
            traceback.print_exc()
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
        text.append('\nINSERT RULES:')
        text.append('- Patches a NEW PCPACK copy only.')
        text.append('- Replacement component1 must be exact same size.')
        text.append('- DDS input is okay if DDS payload after header equals target component1 size.')
        text.append('- FINAL route: Export Original DDS -> edit in Paint.NET -> save same DXT/BC format + mipmaps -> patch ORIGINAL-FORMAT DDS.')
        text.append('- PNG/JPG/BMP conversion is legacy/experimental; use DDS for real edits.')
        text.append('- Paint.NET worked for SM3 DDS edits; GIMP may save BGRA32/no mipmaps unless configured correctly.')
        text.append('- v2.7: set a Replacement DDS folder so AUTO/BATCH AUTO knows exactly where edited DDS files are coming from.')
        text.append('- v2.9: Previous Folder Auto Replace scans a folder of DDS files, matches all same textures automatically, and exports one patched PCPACK copy.')
        text.append('- v3.0: Manual Old Folder Texture Picker lets you load all DDS files from an old folder and choose exactly which replacements to patch.')
        text.append('- v3.1: MANUAL Replace Selected with One File is for replacing the currently selected texture using one selected DDS/image/raw file.')
        text.append('- v3.2: MULTI FILE lets you select more than one DDS at once; the tool auto-maps valid DDS files to selected/current TEX targets and exports one patched PCPACK.')
        text.append('- v3.3: ONE FILE AUTO was restored/prioritized. Use it when you only want to select one DDS and patch one texture without the multi-file flow getting in the way.')
        text.append('- v3.4: OLD ONE FILE AUTO is an explicit v3.1-style single-DDS button.')
        text.append('- v3.5: OLD SELECTED ONE FILE restores the older selected-texture workflow: select texture first, pick one DDS, then immediately export one patched PCPACK copy without the auto-select/mapping window.')
        text.append('- v3.6: SAME FILE(S) lets you select one or more DDS files and auto-patch matching current targets without selecting/extracting one texture first. OLD SELECTED also now reads the current tree selection before saying no texture selected.')
        text.append('- v3.2: MANUAL Replace Selected with Files supports selecting multiple DDS files for selected textures. DDS is recommended; PNG/JPG raw conversion stays legacy/experimental.')
        text.append('- v1.9 Diffuse-safe mode warns before patching _nor/_spe/_spx/_ppi/_ppp/_ao/_env/control maps.')
        text.append('- CONTROL buttons patch using the original extracted bytes. Those copies should stay byte-identical.')
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

    def export_original_dds(self):
        if not self.selected_target:
            messagebox.showinfo('Select target','Select a texture target first.')
            return
        pc=Path(self.pcpack_var.get())
        if not pc.exists():
            messagebox.showerror('Missing PCPACK','Original PCPACK path is missing.')
            return
        outdir=Path(filedialog.askdirectory(title='Choose output folder for DDS export') or '')
        if not str(outdir): return
        try:
            dds,raw,meta=export_original_component_as_dds(pc,self.selected_target,outdir)
            key=target_edit_key(self.selected_target)
            self.dds_export_history[key]=meta
            self.last_export_dir=str(Path(dds).parent)
            if not self.replacement_folder_var.get().strip():
                self.replacement_folder_var.set(str(Path(dds).parent))
            messagebox.showinfo(
                'Original DDS exported',
                'Exported DDS and raw component1.\n\n'
                + 'DDS:\n' + str(dds) + '\n\n'
                + 'Raw:\n' + str(raw) + '\n\n'
                + 'v2.5 workflow: edit/overwrite this DDS in Paint.NET, save same format+mips, then click AUTO or BATCH AUTO to find it automatically when possible.'
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
        outdir=Path(filedialog.askdirectory(title='Choose output folder for EXPORT ALL DDS') or '')
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
                'note':'Edit DDS files externally while preserving format/mips, then use REIMPORT ALL DDS FOLDER.'
            }
            (outdir/'EXPORT_ALL_DDS_SUMMARY_v4_2.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            self.last_export_dir=str(outdir)
            self.replacement_folder_var.set(str(outdir))
            messagebox.showinfo('EXPORT ALL DDS complete', f'Exported {len(ok)} DDS files. Errors: {len(errors)}\n\nFolder:\n{outdir}\n\nAfter editing, use REIMPORT ALL DDS FOLDER -> ONE PACK.')
            self.set_status(f'EXPORT ALL DDS complete: {len(ok)} exported, {len(errors)} errors. Folder: {outdir}')
        except Exception as e:
            traceback.print_exc(); messagebox.showerror('EXPORT ALL DDS failed',str(e))

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
        folder=Path(filedialog.askdirectory(title='Choose folder for SMART REIMPORT', initialdir=start_dir if start_dir else None) or '')
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
            self.set_status(f'SMART REIMPORT found no patchable matches. Report: {report_dir}')
            return

        preview='\n'.join(f"- {i['mode']}: {i['target'].get('asset')} <- {Path(i['path']).name}" for i in smart_items[:20])
        if len(smart_items)>20:
            preview += f'\n...and {len(smart_items)-20} more.'

        msg=(
            f'SMART REIMPORT found {len(smart_items)} patchable file(s).\n'
            f'Exact: {summary["exact_count"]}\n'
            f'Convert due to mip/format/size/source image: {summary["convert_count"]}\n'
            f'Skipped: {summary["skipped"]}\n\n'
            f'{preview}\n\n'
            f'Report folder:\n{report_dir}\n\n'
            'Continue and write ONE NEW patched PCPACK copy?'
        )
        if not messagebox.askyesno('Confirm SMART REIMPORT', msg):
            self.set_status(f'SMART REIMPORT cancelled. Report: {report_dir}')
            return

        out=filedialog.asksaveasfilename(
            title='Save SMART REIMPORT patched PCPACK copy',
            initialfile=pc.stem+'_PATCHED_SMART_REIMPORT_'+pc.suffix,
            filetypes=[('PCPACK','*.PCPACK'),('All files','*.*')]
        )
        if not out:
            return

        try:
            log=copy_and_patch_pcpack_smart_mixed_many(pc, smart_items, Path(out), force_opaque=bool(self.force_opaque_var.get()))
            log['match_report']=str(report_dir/'SMART_REIMPORT_MATCH_REPORT_v4_4.csv')
            (Path(out).parent/(Path(out).stem+'_SMART_REIMPORT_SUMMARY_v4_4.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')
            messagebox.showinfo('SMART REIMPORT complete', f'Patched {log["patch_count"]} texture(s).\nExact: {log["exact_count"]}\nConverted: {log["convert_count"]}\n\nOutput:\n{out}')
            self.set_status(f'SMART REIMPORT complete: {log["patch_count"]} patched ({log["exact_count"]} exact, {log["convert_count"]} converted).')
        except Exception as exc:
            traceback.print_exc(); messagebox.showerror('SMART REIMPORT failed', str(exc))


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
            messagebox.showinfo('Batch DDS export finished', f'Exported {len(ok)} DDS files. Errors: {len(errors)}\n\nFolder:\n{outdir}\n\nEdit the DDS files in Paint.NET, save same format+mips, then use BATCH AUTO to patch them into one PCPACK copy.')
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
            msg='No edited DDS files were found for the selected textures.\n\nUse BATCH: Export DDS for Selected, edit the DDS files in Paint.NET, save same format+mips, then try BATCH AUTO again.\n\nOr click Select Replacement Folder for Batch and choose the folder where your edited DDS files are saved.'
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
        target and does not convert. Use SELECTED CONVERT for wrong-size/wrong-mip
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
            title='SELECTED CONVERT: choose DDS/image to convert into the selected target format',
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
            title='ONE FILE AUTO: select ONE DDS/image replacement file',
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
        dds=filedialog.askopenfilename(title='ONE FILE AUTO: Select exactly ONE DDS replacement file', initialdir=start_dir if start_dir else None, filetypes=[('DDS','*.dds'),('All files','*.*')])
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
            msg+='\n\nTip: if these files work with single SELECTED CONVERT, select the target rows first and use this same button again. v4.9 will convert them in selected order.'
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
                if not messagebox.askyesno('Legacy replacement input', 'This is not a DDS file. PNG/JPG/BIN replacement uses the older/experimental path.\n\nDDS exported from this tool and saved in Paint.NET is strongly recommended.\n\nContinue anyway?'):
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
            msg+='2. Edit/overwrite that DDS in Paint.NET.\n'
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



