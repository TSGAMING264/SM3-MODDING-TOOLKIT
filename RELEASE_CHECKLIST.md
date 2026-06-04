# Public Release Checklist

Before publishing or submitting for Nexus review:

- [ ] No Spider-Man 3 game assets are included.
- [ ] No PCPACK, PCAPK, APKF, XEPACK, PS3PACK, DDS dumps, copied packs, or extracted game output folders are included.
- [ ] No local Windows paths, usernames, personal folder paths, or private names are present.
- [ ] No dev report bundles, diagnostic ZIPs, scanner output, or temporary test output are present.
- [ ] No `__pycache__` folders or `.pyc` files are present.
- [ ] Source runs from a clean checkout.
- [ ] `python -m pip install -r requirements.txt` works.
- [ ] `python SM3_TOOLS.py` starts the toolkit from source.
- [ ] README and build instructions are current.
- [ ] Release builds are made from this same public source.
