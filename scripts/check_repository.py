"""Offline, non-disclosing credential/large-file gate. Checks candidate files + Git history."""
import argparse
import json
from pathlib import Path
import re
import subprocess

RULES={
 'github_token':rb'gh[pousr]_[A-Za-z0-9]{30,}',
 'github_fine_grained_token':rb'github_pat_[A-Za-z0-9_]{50,}',
 'telegram_token':rb'(?<![0-9])[0-9]{8,12}:[A-Za-z0-9_-]{30,}',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'supabase_secret':rb'sb_secret_[A-Za-z0-9_-]{25,}',
}

def findings(data):
    found=[name for name,pattern in RULES.items() if re.search(pattern,data)]
    # JWT server keys are secrets even when their service_role label is base64 encoded.
    import base64
    for match in re.finditer(rb'eyJ[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]{20,}',data):
        try:
            claims=json.loads(base64.urlsafe_b64decode(match[1]+b'='*(-len(match[1])%4)))
            if claims.get('role')=='service_role':found.append('service_role_jwt')
        except (ValueError,UnicodeError):pass
    return sorted(set(found))


def main():
    p=argparse.ArgumentParser();p.add_argument('--history',action='store_true');a=p.parse_args()
    files=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z']).decode().split('\0')
    issues=[];seen=set()
    for name in files:
        if not name or name in seen:continue
        seen.add(name);path=Path(name)
        if not path.is_file():continue
        if name.startswith(('supabase/.temp/','.env')):issues.append({'path':name,'issue':'private_or_generated_path_tracked'});continue
        if path.stat().st_size>10*1024*1024:issues.append({'path':name,'issue':'large_file_review_required'});continue
        for kind in findings(path.read_bytes()):issues.append({'path':name,'issue':kind})
    history=[]
    if a.history:
        for commit in subprocess.check_output(['git','rev-list','--all']).decode().splitlines():
            diff=subprocess.check_output(['git','show','--format=','--no-ext-diff',commit])
            for kind in findings(diff):history.append({'commit':commit,'issue':kind})
    report={'files_checked':len(seen),'working_tree_findings':issues,'history_findings':history,'scope':'Known credential signatures and path/size gate; not a proof of absence of all private information'}
    print(json.dumps(report,indent=2));raise SystemExit(bool(issues or history))

if __name__=='__main__':main()
