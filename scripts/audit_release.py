"""Check reviewed public files plus Git ignore behavior; no raw secret values emitted."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
import sys
from pathlib import Path
from dotenv import dotenv_values
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.package_release import ROOT,release_files

def ignore_checks(root=ROOT):
    blocked=['.env','.env.local','.env.production','backend/.env','live-bindings.json','live-bindings-backup.json','private/live-acceptance.json','.pnpm-store/v3/cache.bin','.cache/huggingface/weights.bin','.venv/pyvenv.cfg','frontend/node_modules/a.js','artifacts/private/raw-response.json']
    public=['.env.example','mcp-config.example.json','docs/live-bindings.schema.json','scripts/release-manifest.json']
    with tempfile.TemporaryDirectory(prefix='mcsketch-ignore-') as temp:
        subprocess.run(['git','init','--quiet',temp],check=True,capture_output=True)
        shutil.copyfile(Path(root)/'.gitignore',Path(temp)/'.gitignore')
        results={}
        for name in blocked+public:
            p=subprocess.run(['git','-C',temp,'check-ignore','--no-index','-q',name],capture_output=True)
            if p.returncode not in (0,1):raise RuntimeError('Git ignore validation failed')
            ignored=p.returncode==0;results[name]={'ignored':ignored,'expected_ignored':name in blocked,'passed':ignored==(name in blocked)}
    return results

def audit():
    files=release_files();findings=[]
    # Check exact local secret bytes, including media; never log values or hashes.
    secrets={v.strip().encode() for v in (os.getenv('MCD_MCP_TOKEN',''),dotenv_values(ROOT/'.env').get('MCD_MCP_TOKEN','')) if isinstance(v,str) and v.strip()}
    patterns=[re.compile(r'Bearer\s+([A-Za-z0-9_.-]{24,})'),re.compile(r'(?:ghp_|github_pat_|sk-)[A-Za-z0-9_]{24,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
    for p in files:
        if any(value in p.read_bytes() for value in secrets):findings.append({'file':p.relative_to(ROOT).as_posix(),'issue':'configured_token_bytes'})
        if p.suffix.lower() not in {'.png','.gif','.jpg','.jpeg'}:
            content=p.read_text(encoding='utf-8-sig')
            if any(rx.search(content) for rx in patterns):findings.append({'file':p.relative_to(ROOT).as_posix(),'issue':'credential_signature'})
    checks=ignore_checks()
    declaration=(ROOT/'CONTEST_DECLARATION.md').read_bytes()
    remote=urllib.request.urlopen('https://raw.githubusercontent.com/M-China/mcd-developer-innovation-challenge/main/CONTEST_DECLARATION.md',timeout=25).read()
    report={'reviewed_file_count':len(files),'largest_file_bytes':max(p.stat().st_size for p in files),'credential_signature_findings':findings,'configured_token_bytes_checked':bool(secrets),'gitignore_checks':checks,'official_declaration_exact':declaration==remote,'declaration_sha256':hashlib.sha256(declaration).hexdigest(),'scope':'Reviewed manifest, configured token bytes in all file types, credential signatures and Git ignore behavior; not a guarantee against all secret formats','passed':not findings and all(c['passed'] for c in checks.values()) and declaration==remote}
    (ROOT/'artifacts/release-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    import sys
    result=audit();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
