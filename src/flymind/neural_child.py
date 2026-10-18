"""Resource-limited Linux child; scientific engine code remains untouched."""
import argparse
import json
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['weak','strong'],required=True);p.add_argument('--connectome',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if sys.platform=='linux':
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(25,25))
        resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))
    from src.neural.escape import run_case
    print(json.dumps(run_case(a.connectome,a.output,a.case)))
if __name__=='__main__':main()
