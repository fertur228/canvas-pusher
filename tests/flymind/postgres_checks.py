"""Optional real SQL tests. Dedicated local socket only; never accepts a production URL."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import time
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--socket',required=True);p.add_argument('--port',type=int,default=55439);p.add_argument('--psql',default='psql')
    a=p.parse_args()
    if not Path(a.socket).resolve().as_posix().startswith('/private/tmp/flymind-'):
        raise SystemExit('Only a dedicated /private/tmp/flymind-* test cluster is allowed')
    database=f'flymind_test_{os.getpid()}_{time.time_ns()}'
    assert re.fullmatch(r'flymind_test_[0-9_]+',database)
    base=[a.psql,'-h',a.socket,'-p',str(a.port),'-v','ON_ERROR_STOP=1']
    subprocess.run(base+['-d','postgres','-c',f'CREATE DATABASE {database}'],check=True)
    try:
        command=base+['-d',database]
        for path in [ROOT/'tests/flymind/sql/bootstrap.sql', *sorted((ROOT/'supabase/migrations').glob('*.sql')), ROOT/'tests/flymind/sql/checks.sql']:
            command+=['-f',str(path)]
        subprocess.run(command,check=True)
    finally:
        subprocess.run(base+['-d','postgres','-c',f'DROP DATABASE {database}'],check=True)


if __name__=='__main__':main()
