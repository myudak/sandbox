"""Copy an encrypted backup with ADB and verify it without downgrading the app."""
import argparse
import hashlib
from pathlib import Path
import subprocess

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serial')
    parser.add_argument('--filename',default='msgstore.db.crypt15')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if Path(args.filename).name!=args.filename or args.filename not in {'msgstore.db.crypt14','msgstore.db.crypt15'}:
        raise ValueError('Only a current backup filename is accepted')
    prefix=['adb']+(['-s',args.serial] if args.serial else [])
    remote='/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/'+args.filename
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/args.filename
    if target.exists():
        raise FileExistsError('Preserving existing backup')
    def remote_hash():
        return subprocess.check_output(prefix+['shell','sha256sum',remote],text=True).split()[0]
    before=remote_hash()
    subprocess.run(prefix+['pull','-a',remote,str(target)],check=True,capture_output=True)
    after=remote_hash()
    digest=hashlib.file_digest(target.open('rb'),'sha256').hexdigest()
    if before!=after or before!=digest:
        raise ValueError('Backup changed or copy failed; do not decrypt this copy')
    print('Encrypted backup copied; source/copy SHA-256 verified. No account or device identifier printed.')

if __name__=='__main__':
    main()
