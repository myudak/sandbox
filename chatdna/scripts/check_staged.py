"""Reject private artifacts and likely identifiers before every commit."""
from pathlib import Path
import re
import subprocess
import sys

def main():
    git_root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip()).resolve()
    try:
        project_prefix=Path(__file__).resolve().parents[1].relative_to(git_root).as_posix()
    except ValueError:
        # External invocation is also used to audit isolated synthetic test repositories.
        project_prefix=''
    synthetic_prefix=('' if project_prefix in {'','.'} else project_prefix+'/')+'data/synthetic/'
    names = subprocess.check_output(["git","diff","--cached","--name-only","--diff-filter=ACMR"], text=True).splitlines()
    problems=[]
    blocked = {".pt",".pth",".safetensors",".sqlite",".db",".crypt14",".crypt15",".key",".hex",".bin",".zip"}
    for name in names:
        p=Path(name)
        if p.suffix in blocked or any(part in {"private","checkpoints","models","artifacts"} for part in p.parts):
            problems.append(name+": private artifact path")
            continue
        data=subprocess.check_output(["git","show",":"+name])
        if len(data)>1024*1024:
            problems.append(name+": file exceeds 1 MiB review limit")
        if p.suffix==".jsonl" and not name.startswith(synthetic_prefix):
            problems.append(name+": non-synthetic dataset")
        text=data.decode("utf-8",errors="replace")
        for pattern in (r"\b\d{5,}@(s\.whatsapp\.net|lid|g\.us)\b",r"(?:sk-proj-|hf_)[A-Za-z0-9_-]{20,}"):
            if re.search(pattern,text):
                problems.append(name+": identifier or credential pattern")
        for line in text.splitlines():
            if re.search(r'\b[a-fA-F0-9]{64}\b',line) and not re.search(r'(?i)sha256["\s:]|sha256:',line):
                problems.append(name+": unexplained key-sized hexadecimal value")
    if problems:
        print("Staged review failed (values withheld):\n"+"\n".join(problems))
        return 1
    print(f"Staged review passed: {len(names)} files; no private artifacts detected.")
    return 0

if __name__=="__main__":
    sys.exit(main())
