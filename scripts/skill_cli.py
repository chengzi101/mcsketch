"""Agent entry point reusing the Flask core, no separate recommendation logic."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=["recognize","stores","menu","match","quote","repair","detail","live/tools","live/call"]);parser.add_argument("--input",help="JSON file path, or read stdin")
    args=parser.parse_args();payload=json.loads(Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read() or "{}")
    with create_app().test_client() as client:
        response=client.get("/api/live/tools") if args.action=="live/tools" else client.post("/api/"+args.action,json=payload)
        print(json.dumps(response.json,ensure_ascii=False,indent=2))
        sys.exit(0 if response.status_code<400 else 1)
