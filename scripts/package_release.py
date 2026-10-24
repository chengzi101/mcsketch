"""Build only explicitly reviewed files; never sweep local directories for release."""
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def release_files(root=ROOT):
    root=Path(root).resolve()
    names=json.loads((root/'scripts/release-manifest.json').read_text(encoding='utf-8'))['files']
    index=root/'frontend/dist/index.html'
    names += ['frontend/dist/index.html']
    names += ['frontend/dist/'+m for m in re.findall(r'(?:src|href)="/(assets/[^"?#]+)"',index.read_text(encoding='utf-8'))]
    files=[]
    for name in sorted(set(names)):
        original=root/name;p=original.resolve()
        if not p.is_relative_to(root) or not p.is_file() or original.is_symlink():
            raise ValueError('Missing or unsafe release entry: '+name)
        if p.stat().st_size>8_000_000:
            raise ValueError('Large release entry requires explicit review: '+name)
        files.append(p)
    return files

def package(root=ROOT):
    root=Path(root).resolve();out=root/'artifacts/mcsketch.zip';out.parent.mkdir(exist_ok=True)
    files=release_files(root)
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for p in files:z.write(p,Path('mcsketch')/p.relative_to(root))
    return out,files

if __name__=='__main__':
    out,files=package();print(f'{out} ({out.stat().st_size:,} bytes, {len(files)} reviewed entries)')
