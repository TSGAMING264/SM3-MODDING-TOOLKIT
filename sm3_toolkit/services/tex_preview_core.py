#!/usr/bin/env python3
"""
SM3 PC Character Texture Preview Component0 v1.4

Generic Spider-Man 3 PC CH_* character TEX preview tool.
Works on model-chain output folders/zips made by the current extractors:
- CH_SPIDERMAN
- CH_BLACKSUIT
- CH_PLAYERGOBLIN
- CH_PETER
- future CH_* character chain outputs with TEX/component0+component1 folders

It reads the 68-byte TEX component0 descriptor:
  width      = u32 @ 0x18
  height     = u32 @ 0x1C
  mip_count  = u32 @ 0x24
  format     = u32 @ 0x28

Supported preview interpretations:
  DXT1 / DXT3 / DXT5 FourCC -> real DDS + PNG first mip preview
  numeric 50                -> L8 plus DXT1/DXT3/DXT5 review candidates; black/white output means format review
  numeric 21                -> raw 32-bit BGRA/A8R8G8B8-style preview, plus swizzle/enlarged strip previews
Unknown formats are copied as RAW_ONLY for research.

New in v1.4:
  - RGB_OPAQUE previews so alpha does not hide the image on a dark background
  - DXT1_OPAQUE comparison for DXT1 files that accidentally preview with 1-bit alpha
  - Format 50 caution: writes L8 plus DXT candidate previews so black/white views can be reviewed instead of trusted blindly
  - Format 21 research variants: BGRA/RGBA/ARGB/ABGR swizzles and enlarged strip previews
  - Cleaner contact sheet uses the best visual preview first, not always the raw RGBA decode
"""
import os, sys, zipfile, tempfile, shutil, struct, csv, json, html, math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False

DDSD_CAPS=0x1
DDSD_HEIGHT=0x2
DDSD_WIDTH=0x4
DDSD_PITCH=0x8
DDSD_PIXELFORMAT=0x1000
DDSD_MIPMAPCOUNT=0x20000
DDSD_LINEARSIZE=0x80000
DDSCAPS_COMPLEX=0x8
DDSCAPS_TEXTURE=0x1000
DDSCAPS_MIPMAP=0x400000
DDPF_ALPHAPIXELS=0x1
DDPF_FOURCC=0x4
DDPF_RGB=0x40
DDPF_LUMINANCE=0x20000

FOURCC_OK = {b'DXT1', b'DXT3', b'DXT5'}
NUMERIC_FORMATS = {
    # Historical WOS converter note: TEX.py/DDS.py can label numeric 0x32 as L8.
    # WOS toolkit dev clue for SM3: some black/white previews are format interpretation problems.
    # Therefore format 50 still writes L8, but the tool also generates DXT1/DXT3/DXT5 candidate previews.
    50: {"preview_kind":"L8", "fourcc":"L8", "note":"component0 format=50 / 0x32; L8 is only one interpretation. v5.2.14 writes DXT1/DXT3/DXT5 review candidates because black/white output can mean wrong format detection."},
    21: {"preview_kind":"BGRA32", "fourcc":"BGRA32", "note":"component0 format=21 / 0x15; WOS TEX converter labels this as A8R8G8B8/BGRA32-style raw32 texture"},
}

def read_u32le(b, off):
    if off + 4 > len(b):
        return 0
    return struct.unpack_from('<I', b, off)[0]

def safe_ascii_fourcc(v):
    b = struct.pack('<I', v)
    try:
        s = b.decode('ascii')
        if all(32 <= ord(c) <= 126 for c in s):
            return s
    except Exception:
        pass
    return None

def parse_component0(c0: bytes):
    if len(c0) < 44:
        return None
    words = [read_u32le(c0, i*4) for i in range(len(c0)//4)]
    asset_hash = read_u32le(c0, 12)
    width = read_u32le(c0, 24)
    height = read_u32le(c0, 28)
    mip_count = read_u32le(c0, 36)
    fmt_raw = read_u32le(c0, 40)
    if width <= 0 or height <= 0 or width > 8192 or height > 8192:
        return None
    if mip_count <= 0 or mip_count > 32:
        mip_count = 1
    raw_fourcc_bytes = struct.pack('<I', fmt_raw)
    if raw_fourcc_bytes in FOURCC_OK:
        fourcc = raw_fourcc_bytes.decode('ascii')
        return {"hash": asset_hash, "width": width, "height": height, "mip_count": mip_count,
                "format_raw": fmt_raw, "format_text": fourcc, "preview_kind": fourcc, "fourcc": fourcc,
                "words": words, "format_note":"real FourCC from component0"}
    if fmt_raw in NUMERIC_FORMATS:
        info = NUMERIC_FORMATS[fmt_raw].copy()
        return {"hash": asset_hash, "width": width, "height": height, "mip_count": mip_count,
                "format_raw": fmt_raw, "format_text": str(fmt_raw), "preview_kind": info["preview_kind"], "fourcc": info["fourcc"],
                "words": words, "format_note": info["note"]}
    fmt_txt = safe_ascii_fourcc(fmt_raw) or str(fmt_raw)
    return {"hash": asset_hash, "width": width, "height": height, "mip_count": mip_count,
            "format_raw": fmt_raw, "format_text": fmt_txt, "preview_kind": "UNKNOWN", "fourcc": "", "words": words,
            "format_note": "unknown component0 format; saved raw only"}

def dxt_block_bytes(fourcc):
    return 8 if fourcc == 'DXT1' else 16

def mip_chain_size(width, height, fourcc, mip_count):
    bpb = dxt_block_bytes(fourcc)
    total = 0
    w,h = width,height
    for _ in range(max(1, mip_count)):
        bw = max(1, (w + 3)//4)
        bh = max(1, (h + 3)//4)
        total += bw*bh*bpb
        w = max(1, w//2)
        h = max(1, h//2)
    return total

def first_mip_size(width, height, fourcc):
    return max(1,(width+3)//4)*max(1,(height+3)//4)*dxt_block_bytes(fourcc)

def make_dds_dxt_header(width, height, fourcc, mip_count, linear_size):
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    caps = DDSCAPS_TEXTURE
    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    header = bytearray()
    header += b'DDS '
    header += struct.pack('<I', 124)
    header += struct.pack('<I', flags)
    header += struct.pack('<I', height)
    header += struct.pack('<I', width)
    header += struct.pack('<I', linear_size)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', mip_count)
    header += b'\x00' * (11*4)
    header += struct.pack('<I', 32)
    header += struct.pack('<I', DDPF_FOURCC)
    header += fourcc.encode('ascii')
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', caps)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    assert len(header) == 128
    return bytes(header)


def l8_mip_chain_size(width, height, mip_count):
    total = 0
    w,h = width,height
    for _ in range(max(1, mip_count)):
        total += max(1,w) * max(1,h)
        w = max(1, w//2)
        h = max(1, h//2)
    return total

def make_dds_l8_header(width, height, mip_count=1):
    # DDS luminance 8-bit (L8). WOS DDS.py uses DDPF_LUMINANCE with RGBBitCount=8 and RBitMask=0xFF.
    pitch = width
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_PITCH
    caps = DDSCAPS_TEXTURE
    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    header = bytearray()
    header += b'DDS '
    header += struct.pack('<I', 124)
    header += struct.pack('<I', flags)
    header += struct.pack('<I', height)
    header += struct.pack('<I', width)
    header += struct.pack('<I', pitch)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', mip_count)
    header += b'\x00' * (11*4)
    header += struct.pack('<I', 32)
    header += struct.pack('<I', DDPF_LUMINANCE)
    header += struct.pack('<I', 0)              # no FourCC
    header += struct.pack('<I', 8)              # bits per pixel
    header += struct.pack('<I', 0x000000ff)     # luminance mask
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', caps)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    assert len(header) == 128
    return bytes(header)

def make_dds_bgra32_header(width, height, mip_count=1):
    # Uncompressed 32-bit BGRA data with A8R8G8B8-style masks.
    pitch = width * 4
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_PITCH
    caps = DDSCAPS_TEXTURE
    header = bytearray()
    header += b'DDS '
    header += struct.pack('<I', 124)
    header += struct.pack('<I', flags)
    header += struct.pack('<I', height)
    header += struct.pack('<I', width)
    header += struct.pack('<I', pitch)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 1)
    header += b'\x00' * (11*4)
    header += struct.pack('<I', 32)                     # DDS_PIXELFORMAT size
    header += struct.pack('<I', DDPF_RGB | DDPF_ALPHAPIXELS)
    header += struct.pack('<I', 0)                      # no FourCC
    header += struct.pack('<I', 32)                     # RGB bit count
    header += struct.pack('<I', 0x00ff0000)             # R mask
    header += struct.pack('<I', 0x0000ff00)             # G mask
    header += struct.pack('<I', 0x000000ff)             # B mask
    header += struct.pack('<I', 0xff000000)             # A mask
    header += struct.pack('<I', caps)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    header += struct.pack('<I', 0)
    assert len(header) == 128
    return bytes(header)

def color565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return (r,g,b,255)

def decode_color_block(block8, allow_transparent=True):
    c0, c1, bits = struct.unpack_from('<HHI', block8, 0)
    col0 = color565(c0)
    col1 = color565(c1)
    colors = [col0, col1]
    if c0 > c1 or not allow_transparent:
        colors.append(tuple((2*col0[i]+col1[i])//3 for i in range(3)) + (255,))
        colors.append(tuple((col0[i]+2*col1[i])//3 for i in range(3)) + (255,))
    else:
        colors.append(tuple((col0[i]+col1[i])//2 for i in range(3)) + (255,))
        colors.append((0,0,0,0))
    out=[]
    for i in range(16):
        out.append(colors[(bits >> (2*i)) & 3])
    return out

def decode_dxt1(data, width, height):
    pixels=[(0,0,0,0)]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+8>len(data): break
            block = decode_color_block(data[off:off+8], True)
            off += 8
            for y in range(4):
                for x in range(4):
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        pixels[py*width+px]=block[y*4+x]
    return pixels

def decode_dxt3(data, width, height):
    pixels=[(0,0,0,0)]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+16>len(data): break
            alpha_bytes=data[off:off+8]
            color_bytes=data[off+8:off+16]
            off += 16
            block=decode_color_block(color_bytes, False)
            aval=int.from_bytes(alpha_bytes, 'little')
            for y in range(4):
                for x in range(4):
                    i=y*4+x
                    a4=(aval >> (4*i)) & 0xF
                    a=a4*17
                    r,g,b,_=block[i]
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        pixels[py*width+px]=(r,g,b,a)
    return pixels

def decode_dxt5(data, width, height):
    pixels=[(0,0,0,0)]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+16>len(data): break
            a0=data[off]; a1=data[off+1]
            alpha_bits=int.from_bytes(data[off+2:off+8], 'little')
            alphas=[a0,a1]
            if a0>a1:
                alphas += [(6*a0+1*a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(1*a0+6*a1)//7]
            else:
                alphas += [(4*a0+1*a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(1*a0+4*a1)//5,0,255]
            color_block=decode_color_block(data[off+8:off+16], False)
            off += 16
            for y in range(4):
                for x in range(4):
                    i=y*4+x
                    ai=(alpha_bits >> (3*i)) & 7
                    r,g,b,_=color_block[i]
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        pixels[py*width+px]=(r,g,b,alphas[ai])
    return pixels

def write_png_dxt_preview(dds_payload, out_png, width, height, fourcc):
    if not HAS_PIL:
        return False
    first = dds_payload[:first_mip_size(width,height,fourcc)]
    if fourcc == 'DXT1':
        pix = decode_dxt1(first, width, height)
    elif fourcc == 'DXT3':
        pix = decode_dxt3(first, width, height)
    elif fourcc == 'DXT5':
        pix = decode_dxt5(first, width, height)
    else:
        return False
    img = Image.new('RGBA', (width,height))
    img.putdata(pix)
    img.save(out_png)
    return True

def write_png_bgra32(payload, out_png, width, height):
    if not HAS_PIL:
        return False
    need=width*height*4
    if len(payload) < need:
        return False
    img = Image.frombytes('RGBA', (width,height), payload[:need], 'raw', 'BGRA')
    img.save(out_png)
    return True



def write_png_l8(payload, out_png, width, height):
    if not HAS_PIL:
        return False
    need = width * height
    if len(payload) < need:
        return False
    img = Image.frombytes('L', (width,height), payload[:need])
    img.convert('RGBA').save(out_png)
    return True

def write_l8_variants(payload, out_dir, asset, width, height):
    made=[]
    if not HAS_PIL: return made
    need = width * height
    if len(payload) < need: return made
    raw = payload[:need]
    out_dir.mkdir(parents=True, exist_ok=True)
    # Plain grayscale
    p = out_dir/f'{asset}__L8_GRAY.png'
    try:
        Image.frombytes('L',(width,height),raw).save(p); made.append(str(p))
    except Exception: pass
    # Inverted grayscale sometimes reveals masks better.
    try:
        inv = bytes(255-b for b in raw)
        p = out_dir/f'{asset}__L8_INVERTED.png'
        Image.frombytes('L',(width,height),inv).save(p); made.append(str(p))
    except Exception: pass
    # Auto-contrast for low-range control maps.
    try:
        vals=list(raw); mn=min(vals); mx=max(vals)
        if mx > mn:
            stretch = bytes(max(0,min(255, round((v-mn)*255/(mx-mn)))) for v in vals)
            p = out_dir/f'{asset}__L8_AUTO_CONTRAST.png'
            Image.frombytes('L',(width,height),stretch).save(p); made.append(str(p))
    except Exception: pass
    return made

def decode_dxt5_alpha_values(block8):
    if len(block8) < 8:
        return [0]*16
    a0=block8[0]; a1=block8[1]
    bits=int.from_bytes(block8[2:8], 'little')
    vals=[a0,a1]
    if a0>a1:
        vals += [(6*a0+1*a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(1*a0+6*a1)//7]
    else:
        vals += [(4*a0+1*a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(1*a0+4*a1)//5,0,255]
    return [vals[(bits >> (3*i)) & 7] for i in range(16)]

def decode_dxt5_alpha_plane(data, width, height):
    vals=[0]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+16>len(data): break
            block=decode_dxt5_alpha_values(data[off:off+8])
            off += 16
            for y in range(4):
                for x in range(4):
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        vals[py*width+px]=block[y*4+x]
    return vals

def decode_bc5_normal(data, width, height):
    # BC5/ATI2 style: first 8 bytes = X alpha block, next 8 bytes = Y alpha block.
    pixels=[(128,128,255,255)]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+16>len(data): break
            xs=decode_dxt5_alpha_values(data[off:off+8])
            ys=decode_dxt5_alpha_values(data[off+8:off+16])
            off += 16
            for y in range(4):
                for x in range(4):
                    i=y*4+x
                    xv=xs[i]; yv=ys[i]
                    nx=(xv/255.0)*2.0-1.0
                    ny=(yv/255.0)*2.0-1.0
                    zz=max(0.0,1.0-nx*nx-ny*ny)
                    nz=zz**0.5
                    z=int(max(0,min(255,(nz*0.5+0.5)*255)))
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        pixels[py*width+px]=(xv,yv,z,255)
    return pixels

def write_pixels_png(pixels, out_png, width, height):
    if not HAS_PIL:
        return False
    img=Image.new('RGBA',(width,height))
    img.putdata(pixels)
    img.save(out_png)
    return True

def write_gray_png(vals, out_png, width, height):
    if not HAS_PIL:
        return False
    img=Image.new('L',(width,height))
    img.putdata(vals[:width*height])
    img.convert('RGBA').save(out_png)
    return True

def make_opaque_from_rgba_png(src_png, out_png):
    if not HAS_PIL or not Path(src_png).exists():
        return False
    img=Image.open(src_png).convert('RGBA')
    r,g,b,a=img.split()
    Image.merge('RGBA',(r,g,b,Image.new('L',img.size,255))).save(out_png)
    return True


def write_channel_variants_from_png(src_png, out_dir, asset):
    made=[]
    if not HAS_PIL or not src_png or not Path(src_png).exists():
        return made
    img=Image.open(src_png).convert('RGBA')
    r,g,b,a=img.split()
    for name,ch in [('R',r),('G',g),('B',b),('A',a)]:
        p=out_dir/f'{asset}__CHANNEL_{name}.png'
        ch.convert('RGBA').save(p); made.append(str(p))
    p=out_dir/f'{asset}__RGB_OPAQUE.png'
    Image.merge('RGBA',(r,g,b,Image.new('L',img.size,255))).save(p); made.append(str(p))
    return made

def write_dxt1_opaque_png(payload, out_png, width, height):
    # Some SM3 DXT1 files are color-only. The normal DXT1 decoder may make c0<=c1 pixels transparent.
    if not HAS_PIL:
        return False
    pixels=[(0,0,0,255)]*(width*height)
    off=0
    for by in range(0,height,4):
        for bx in range(0,width,4):
            if off+8>len(payload): break
            block=decode_color_block(payload[off:off+8], False)
            off += 8
            for y in range(4):
                for x in range(4):
                    px=bx+x; py=by+y
                    if px<width and py<height:
                        r,g,b,a=block[y*4+x]
                        pixels[py*width+px]=(r,g,b,255)
    return write_pixels_png(pixels,out_png,width,height)

def write_dxt5nm_normal_png(payload, out_png, width, height):
    # Common normal map packing: X in alpha, Y in green; reconstruct Z.
    if not HAS_PIL:
        return False
    pix=decode_dxt5(payload[:first_mip_size(width,height,'DXT5')],width,height)
    out=[]
    for r,g,b,a in pix:
        x=a; y=g
        nx=(x/255.0)*2.0-1.0
        ny=(y/255.0)*2.0-1.0
        nz=max(0.0,1.0-nx*nx-ny*ny)**0.5
        z=int(max(0,min(255,(nz*0.5+0.5)*255)))
        out.append((x,y,z,255))
    return write_pixels_png(out,out_png,width,height)

def write_dxt_rgba_channels(payload, out_dir, asset, width, height, fourcc):
    made=[]
    if not HAS_PIL: return made
    first=payload[:first_mip_size(width,height,fourcc)]
    if fourcc=='DXT1': pix=decode_dxt1(first,width,height)
    elif fourcc=='DXT3': pix=decode_dxt3(first,width,height)
    elif fourcc=='DXT5': pix=decode_dxt5(first,width,height)
    else: return made
    channels={'R':[p[0] for p in pix], 'G':[p[1] for p in pix], 'B':[p[2] for p in pix], 'A':[p[3] for p in pix]}
    for ch,vals in channels.items():
        p=out_dir/f'{asset}__CHANNEL_{ch}.png'
        write_gray_png(vals,p,width,height); made.append(str(p))
    # RGB opaque preview
    p=out_dir/f'{asset}__RGB_OPAQUE.png'
    write_pixels_png([(r,g,b,255) for r,g,b,a in pix],p,width,height); made.append(str(p))
    return made

def write_format50_research_variants(payload, out_dir, asset, width, height):
    made=[]
    if not HAS_PIL: return made
    out_dir.mkdir(parents=True,exist_ok=True)
    # v5.2.14: format 50/L8 can make color textures look black/white if the format guess is wrong.
    # Write DXT candidates for visual review only. These are not automatic patch approvals.
    for fourcc in ('DXT1','DXT3','DXT5'):
        try:
            need = first_mip_size(width, height, fourcc)
            if len(payload) < need:
                continue
            first = payload[:need]
            if fourcc == 'DXT1':
                pix = decode_dxt1(first, width, height)
            elif fourcc == 'DXT3':
                pix = decode_dxt3(first, width, height)
            else:
                pix = decode_dxt5(first, width, height)
            p = out_dir / f'{asset}__FMT50_REVIEW_AS_{fourcc}.png'
            write_pixels_png([(r,g,b,255) for r,g,b,a in pix], p, width, height)
            made.append(str(p))
            dds = out_dir / f'{asset}__FMT50_REVIEW_AS_{fourcc}.dds'
            dds.write_bytes(make_dds_dxt_header(width,height,fourcc,1,need) + first)
            made.append(str(dds))
        except Exception:
            pass
    try:
        first=payload[:first_mip_size(width,height,'DXT5')]
        p=out_dir/f'{asset}__FMT50_DXT5_ALPHA_ONLY.png'
        write_gray_png(decode_dxt5_alpha_plane(first,width,height),p,width,height); made.append(str(p))
    except Exception: pass
    return made

def write_bgra_swizzle_variants(payload, out_dir, asset, width, height):
    made=[]
    if not HAS_PIL: return made
    need=width*height*4
    if len(payload)<need: return made
    raw=payload[:need]
    swizzles={
        'BGRA':('B','G','R','A'),
        'RGBA':('R','G','B','A'),
        'ARGB':('A','R','G','B'),
        'ABGR':('A','B','G','R'),
        'RGBX_OPAQUE':('R','G','B','255'),
        'BGRX_OPAQUE':('B','G','R','255'),
    }
    idx={'B':0,'G':1,'R':2,'A':3}
    pixels_bytes=list(raw)
    for name,order in swizzles.items():
        outpix=[]
        for i in range(0,need,4):
            src=[pixels_bytes[i],pixels_bytes[i+1],pixels_bytes[i+2],pixels_bytes[i+3]]
            rgba=[]
            for o in order:
                rgba.append(255 if o=='255' else src[idx[o]])
            outpix.append(tuple(rgba))
        p=out_dir/f'{asset}__RAW32_{name}.png'
        write_pixels_png(outpix,p,width,height); made.append(str(p))
        # If this is a tiny strip like 2x256, also write a widened copy for human viewing.
        if width<=8 or height<=8:
            try:
                img=Image.open(p).convert('RGBA')
                scale_x=max(1, min(64, 256//max(1,width)))
                scale_y=max(1, min(64, 256//max(1,height)))
                big=img.resize((width*scale_x,height*scale_y),Image.Resampling.NEAREST)
                bp=out_dir/f'{asset}__RAW32_{name}__ENLARGED.png'
                big.save(bp); made.append(str(bp))
            except Exception: pass
    # channel grayscale previews
    for ci,ch in enumerate(['B','G','R','A']):
        vals=[pixels_bytes[i+ci] for i in range(0,need,4)]
        p=out_dir/f'{asset}__RAW32_CHANNEL_{ch}.png'
        write_gray_png(vals,p,width,height); made.append(str(p))
    return made

def choose_best_visual_png(row, variant_paths):
    asset=(row.get('asset') or '').lower()
    kind=row.get('preview_kind')
    # For special packed maps, use clearer research previews first.
    if kind=='L8':
        for suffix in ['__L8_AUTO_CONTRAST.png','__L8_GRAY.png']:
            for p in variant_paths:
                if p.endswith(suffix): return p
    if kind=='DXT5_CANDIDATE':
        priorities=['__FMT50_DXT5_ALPHA_ONLY.png','__FMT50_BC5_ATI2_NORMAL_CANDIDATE.png','__RGB_OPAQUE.png']
        for suffix in priorities:
            for p in variant_paths:
                if p.endswith(suffix): return p
    if kind=='BGRA32':
        for p in variant_paths:
            if p.endswith('__RAW32_BGRA__ENLARGED.png'): return p
        for p in variant_paths:
            if p.endswith('__RAW32_BGRA.png'): return p
    # For DXT5 normal maps, opaque RGB is clearer in contact sheets.
    if '_nor' in asset:
        for p in variant_paths:
            if p.endswith('__RGB_OPAQUE.png'): return p
    return row.get('png','')

def extract_input(input_path: Path, temp_root: Path):
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() == '.zip':
        dst = temp_root / 'input_zip'
        dst.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path, 'r') as z:
            z.extractall(dst)
        return dst
    raise ValueError('Input must be a folder or zip containing SM3 extracted model chain TEX files. Do not select the original PCPACK here; run the chain extractor first.')

def find_tex_dirs(root: Path):
    dirs=[]
    for d in root.rglob('*'):
        if not d.is_dir():
            continue
        if not list(d.glob('component0_*bytes.bin')) or not list(d.glob('component1_*bytes.bin')):
            continue
        pstr = str(d).replace('\\','/').upper()
        name = d.name.upper()
        if '/TEX/' in pstr or '_TEX_' in name or '/TEXTURE/' in pstr:
            dirs.append(d)
    return sorted(dirs)

def short_asset_name(d: Path):
    name = d.name
    # Examples:
    # 00069_TEX_0x037B351C_ch_blacksuit_topweb -> ch_blacksuit_topweb
    # 00042_TEX_0x124EC16F_ch_harry_head_nor -> ch_harry_head_nor
    parts = name.split('_')
    if len(parts) >= 4 and parts[1].upper() == 'TEX':
        return '_'.join(parts[3:])
    return name

def asset_group(asset):
    low=asset.lower()
    if low.endswith(('_dif','_dif1','_dif2','_ao','_ao1')):
        return 'DIFFUSE_AO'
    if '_nor' in low or low.endswith('_nrm'):
        return 'NORMAL'
    if '_spe' in low or '_spx' in low or '_rfl' in low or '_env' in low or '_ems' in low:
        return 'SPEC_REFLECT_ENV'
    if '_ppi' in low or '_ppp' in low:
        return 'PPI_PPP_SPECIAL'
    return 'OTHER'

def maybe_payload_offset_note(payload, expected):
    if len(payload) == expected:
        return ''
    if len(payload) == expected + 8:
        return 'payload has +8 bytes vs expected; keeping full raw and trimming DDS preview to expected size'
    if len(payload) == expected + 16:
        return 'payload has +16 bytes vs expected; keeping full raw and trimming DDS preview to expected size'
    return f'payload_size={len(payload)} expected={expected}; DDS/PNG preview uses first expected bytes when possible'

def build_contact_sheet(out: Path, rows):
    if not HAS_PIL:
        return ''
    imgs=[]
    for r in rows:
        p=r.get('best_png','') or r.get('png','')
        if p and Path(p).exists():
            try:
                img=Image.open(p).convert('RGBA')
                imgs.append((r,img.copy()))
            except Exception:
                pass
    if not imgs:
        return ''
    thumb=160; pad=16; label_h=48
    cols=4
    rows_n=math.ceil(len(imgs)/cols)
    sheet=Image.new('RGBA',(cols*(thumb+pad)+pad, rows_n*(thumb+label_h+pad)+pad),(22,22,22,255))
    draw=ImageDraw.Draw(sheet)
    for idx,(r,img) in enumerate(imgs):
        col=idx%cols; row=idx//cols
        x=pad+col*(thumb+pad); y=pad+row*(thumb+label_h+pad)
        img.thumbnail((thumb,thumb), Image.LANCZOS)
        bg=Image.new('RGBA',(thumb,thumb),(48,48,48,255))
        bg.alpha_composite(img,((thumb-img.width)//2,(thumb-img.height)//2))
        sheet.alpha_composite(bg,(x,y))
        label=f"{r.get('asset','')[:28]}\n{r.get('width')}x{r.get('height')} {r.get('preview_kind')}"
        draw.text((x,y+thumb+4),label,fill=(235,235,235,255))
    p=out/'CONTACT_SHEET.png'
    sheet.convert('RGB').save(p)
    return str(p)

def process(input_path, output_path):
    input_path=Path(input_path)
    out=Path(output_path)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    reports=out/'REPORTS'; previews=out/'DDS_PREVIEWS'; pngs=out/'PNG_PREVIEWS'; rawdir=out/'RAW_COMPONENTS'; openfirst=out/'OPEN_FIRST_PNGS'; variants=out/'RESEARCH_VARIANTS'; bestdir=out/'BEST_VISUAL_PREVIEWS'
    for p in [reports, previews, pngs, rawdir, openfirst, variants, bestdir]: p.mkdir()
    rows=[]
    with tempfile.TemporaryDirectory(prefix='sm3_pc_tex_v13_') as td:
        root = extract_input(input_path, Path(td))
        tex_dirs = find_tex_dirs(root)
        for d in tex_dirs:
            c0p = sorted(d.glob('component0_*bytes.bin'))[0]
            c1p = sorted(d.glob('component1_*bytes.bin'))[0]
            c0 = c0p.read_bytes()
            payload = c1p.read_bytes()
            desc = parse_component0(c0)
            asset = short_asset_name(d)
            group = asset_group(asset)
            folder = previews / ('_' + asset)
            folder.mkdir(exist_ok=True)
            png_folder = pngs / ('_' + asset)
            png_folder.mkdir(exist_ok=True)
            raw_folder = rawdir / ('_' + asset)
            raw_folder.mkdir(exist_ok=True)
            (raw_folder / c0p.name).write_bytes(c0)
            raw_out = raw_folder / f'{asset}_component1_{len(payload)}bytes.raw'
            raw_out.write_bytes(payload)
            row = {"asset_folder": str(d), "asset": asset, "group": group, "component0_size": len(c0), "component1_size": len(payload)}
            if not desc:
                row["_words"] = []
                row.update({"status":"RAW_ONLY_NO_DESCRIPTOR", "width":"", "height":"", "mip_count":"", "format_raw":"", "format_text":"", "preview_kind":"", "expected_size":"", "dds":"", "png":"", "raw":str(raw_out), "note":"Could not parse component0 descriptor"})
                rows.append(row); continue
            w,h,mips = desc['width'],desc['height'],desc['mip_count']
            fmt_text, fmt_raw, kind, fourcc = desc['format_text'], desc['format_raw'], desc['preview_kind'], desc['fourcc']
            note = desc.get('format_note','')
            dds_out=''; png_out=''; expected=''; status='RAW_ONLY_UNKNOWN_FORMAT'
            if kind in ('DXT1','DXT3','DXT5','DXT5_CANDIDATE'):
                expected = mip_chain_size(w,h,fourcc,mips)
                use_payload = payload[:expected] if len(payload) >= expected else payload
                extra = maybe_payload_offset_note(payload, expected)
                if extra:
                    note += ('; ' if note else '') + extra
                dds_header = make_dds_dxt_header(w,h,fourcc,mips,first_mip_size(w,h,fourcc))
                suffix = f'{w}x{h}_{kind}_mips{mips}'
                dds_path = folder / f'{asset}_{suffix}.dds'
                dds_path.write_bytes(dds_header + use_payload)
                dds_out=str(dds_path)
                png_path = png_folder / f'{asset}_{suffix}.png'
                try:
                    if write_png_dxt_preview(use_payload,png_path,w,h,fourcc):
                        png_out=str(png_path)
                except Exception as e:
                    note += ('; ' if note else '') + f'PNG decode error: {e}'
                status='WROTE_DDS_AND_PNG'
            elif kind == 'L8':
                expected = l8_mip_chain_size(w,h,mips)
                use_payload = payload[:expected] if len(payload) >= expected else payload
                extra = maybe_payload_offset_note(payload, expected)
                if extra:
                    note += ('; ' if note else '') + extra
                suffix = f'{w}x{h}_L8_mips{mips}'
                dds_path = folder / f'{asset}_{suffix}.dds'
                dds_path.write_bytes(make_dds_l8_header(w,h,mips) + use_payload)
                dds_out=str(dds_path)
                png_path = png_folder / f'{asset}_{suffix}.png'
                try:
                    if write_png_l8(use_payload,png_path,w,h):
                        png_out=str(png_path)
                except Exception as e:
                    note += ('; ' if note else '') + f'L8 PNG decode error: {e}'
                status='WROTE_L8_DDS_AND_PNG'
            elif kind == 'BGRA32':
                expected = w*h*4
                use_payload = payload[:expected] if len(payload) >= expected else payload
                extra = maybe_payload_offset_note(payload, expected)
                if extra:
                    note += ('; ' if note else '') + extra
                suffix = f'{w}x{h}_BGRA32'
                dds_path = folder / f'{asset}_{suffix}.dds'
                dds_path.write_bytes(make_dds_bgra32_header(w,h,1) + use_payload)
                dds_out=str(dds_path)
                png_path = png_folder / f'{asset}_{suffix}.png'
                try:
                    if write_png_bgra32(use_payload,png_path,w,h):
                        png_out=str(png_path)
                except Exception as e:
                    note += ('; ' if note else '') + f'BGRA PNG decode error: {e}'
                status='WROTE_BGRA32_DDS_AND_PNG'
            row["_words"] = desc.get("words", [])
            row.update({"status":status, "width":w, "height":h, "mip_count":mips, "format_raw":fmt_raw, "format_text":fmt_text, "preview_kind":kind, "expected_size":expected, "dds":dds_out, "png":png_out, "raw":str(raw_out), "note":note})
            variant_paths=[]
            vdir = variants / ('_' + asset)
            vdir.mkdir(exist_ok=True)
            try:
                if kind in ('DXT1','DXT3','DXT5','DXT5_CANDIDATE') and len(use_payload) > 0:
                    # Fast path: split the already-decoded PNG instead of decoding the full texture repeatedly.
                    variant_paths.extend(write_channel_variants_from_png(png_out, vdir, asset))
                    if fourcc == 'DXT1' and (w*h) <= 262144:
                        p = vdir / f'{asset}__DXT1_OPAQUE_NO_1BIT_ALPHA.png'
                        if write_dxt1_opaque_png(use_payload, p, w, h): variant_paths.append(str(p))
                    # DXT5nm deep normal reconstruction is intentionally skipped in v1.4 fast mode.
                if kind == 'DXT5_CANDIDATE' and len(use_payload) > 0:
                    variant_paths.extend(write_format50_research_variants(use_payload, vdir, asset, w, h))
                if kind == 'L8' and len(use_payload) > 0:
                    variant_paths.extend(write_l8_variants(use_payload, vdir, asset, w, h))
                    if int(row.get('format_raw') or 0) == 50:
                        variant_paths.extend(write_format50_research_variants(payload, vdir, asset, w, h))
                if kind == 'BGRA32' and len(use_payload) > 0:
                    variant_paths.extend(write_bgra_swizzle_variants(use_payload, vdir, asset, w, h))
            except Exception as e:
                note += ('; ' if note else '') + f'variant generation error: {e}'
                row['note'] = note
            row['variants'] = '|'.join(variant_paths)
            best_png = choose_best_visual_png(row, variant_paths)
            row['best_png'] = best_png
            if best_png and Path(best_png).exists():
                try:
                    dst = bestdir / f"{group}__{asset}__BEST__{kind}.png"
                    shutil.copy2(best_png, dst)
                    row['best_copy'] = str(dst)
                except Exception:
                    row['best_copy'] = ''
            else:
                row['best_copy'] = ''
            rows.append(row)
    # copy open-first PNGs
    for r in rows:
        p = r.get('best_png','') or r.get('png','')
        if p and Path(p).exists() and r.get('group') in ('DIFFUSE_AO','NORMAL','SPEC_REFLECT_ENV','PPI_PPP_SPECIAL'):
            target = openfirst / f"{r['group']}__{r['asset']}__{r.get('width')}x{r.get('height')}__{r.get('preview_kind')}__BEST.png"
            try: shutil.copy2(p,target)
            except Exception: pass
    # reports
    keys=["asset","group","status","width","height","mip_count","format_raw","format_text","preview_kind","component0_size","component1_size","expected_size","dds","png","best_png","best_copy","variants","raw","note","asset_folder"]
    with open(reports/'TEXTURE_COMPONENT0_PREVIEW_REPORT.csv','w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f, fieldnames=keys); wr.writeheader(); wr.writerows([{k:r.get(k,'') for k in keys} for r in rows])
    with open(reports/'TEXTURE_COMPONENT0_PREVIEW_REPORT.json','w',encoding='utf-8') as f:
        json.dump([{k:v for k,v in r.items() if k != '_words'} for r in rows], f, indent=2)
    # component0 words report
    max_words=max((len(r.get('_words', [])) for r in rows), default=0)
    with open(reports/'COMPONENT0_U32_WORDS.csv','w',newline='',encoding='utf-8') as f:
        field=['asset']+[f'u32_{i:02d}' for i in range(max_words)]
        wr=csv.DictWriter(f, fieldnames=field); wr.writeheader()
        for r in rows:
            words=r.get('_words', [])
            rr={'asset':r['asset']}
            rr.update({f'u32_{i:02d}':words[i] if i<len(words) else '' for i in range(max_words)})
            wr.writerow(rr)
    sheet=build_contact_sheet(out, rows)
    # html index
    cards=[]
    for r in rows:
        p = r.get('best_png','') or r.get('png','')
        note = r.get('note','') or ''
        if p:
            rel=os.path.relpath(p, out).replace('\\','/')
            cards.append(f"<div class='card {html.escape(r['group'])}'><h3>{html.escape(r['asset'])}</h3><p>{r['width']}x{r['height']} {html.escape(str(r['preview_kind']))} mips={r['mip_count']} fmtRaw={r['format_raw']}</p><img src='{html.escape(rel)}'><p class='note'>{html.escape(note)}</p></div>")
        else:
            cards.append(f"<div class='card {html.escape(r.get('group','OTHER'))}'><h3>{html.escape(r['asset'])}</h3><p>{html.escape(r['status'])}</p><p class='note'>{html.escape(note)}</p></div>")
    sheet_html = ''
    if sheet:
        sheet_rel=os.path.relpath(sheet,out).replace('\\','/')
        sheet_html=f"<p><a href='{html.escape(sheet_rel)}'>Open CONTACT_SHEET.png</a></p><img class='sheet' src='{html.escape(sheet_rel)}'>"
    index = """<!doctype html><html><head><meta charset='utf-8'><title>SM3 PC Character Texture Preview v1.4</title><style>body{font-family:Arial;margin:24px;background:#111;color:#eee}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.card{background:#1d1d1d;padding:12px;border-radius:10px}.card img{max-width:100%;image-rendering:auto;background:#333}.note,.small{color:#bbb;font-size:12px}.sheet{max-width:100%;background:#222}.legend span{display:inline-block;background:#292929;margin:2px;padding:4px 7px;border-radius:6px}</style></head><body><h1>SM3 PC Character Texture Preview v1.4</h1><p class='small'>DDS files are in DDS_PREVIEWS. PNG browser previews are decoded from the first mip or raw BGRA. v1.4 also writes BEST_VISUAL_PREVIEWS and RESEARCH_VARIANTS for messy/special maps; format 50 writes L8 plus DXT1/DXT3/DXT5 review candidates because black/white preview can mean wrong format detection.</p><div class='legend'><span>DXT1/DXT5 real FourCC</span><span>format 50 = L8 + DXT review candidates</span><span>format 21 = raw32 swizzle/strip research</span><span>alpha-safe RGB opaque previews</span></div>""" + sheet_html + "<div class='grid'>" + "\n".join(cards) + "</div></body></html>"
    (out/'PREVIEW_INDEX.html').write_text(index, encoding='utf-8')
    readme = f"""SM3 PC Character Texture Preview Component0 v1.4

Input: {input_path}
Output: {out}
Texture folders found: {len(rows)}

Open first:
PREVIEW_INDEX.html
CONTACT_SHEET.png
OPEN_FIRST_PNGS

Main output folders:
DDS_PREVIEWS       = DDS files you can open/edit with a DDS tool
PNG_PREVIEWS       = quick browser previews
OPEN_FIRST_PNGS    = copied important previews grouped by use
BEST_VISUAL_PREVIEWS = v1.4 best guess human-readable previews
RESEARCH_VARIANTS  = channel/special format comparison previews
RAW_COMPONENTS     = original component0/component1 copies for research
REPORTS            = CSV/JSON reports

Supported input:
- Model-chain ZIP made by the chain extractor
- Extracted model-chain folder

Do NOT select the original PCPACK here.
Run the character chain extractor first, then feed this tool the chain output.

New in v1.4:
- Renamed from BlackSuit-only to generic SM3 PC Character Texture Preview
- Works on Black Suit, Player Goblin, Peter, Spider-Man chain outputs
- Supports normal DXT1/DXT5 FourCC files
- Fixes numeric format 50 / 0x32 as L8 luminance using the uploaded WOS DDS Wrapped TEX converter as reference
- Keeps numeric format 21 / 0x15 as A8R8G8B8/BGRA32 using the uploaded WOS DDS Wrapped TEX converter as reference
- Writes CONTACT_SHEET.png and OPEN_FIRST_PNGS
- Writes COMPONENT0_U32_WORDS.csv for hex/descriptor research
"""
    (out/'READ_ME_FIRST.txt').write_text(readme, encoding='utf-8')
    return rows


# Standalone GUI entry point removed for toolkit service integration.

