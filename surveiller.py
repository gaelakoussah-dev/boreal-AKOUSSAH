"""Lance le pipeline des qu'un fichier source est nouveau ou modifie.
  python surveiller.py             : boucle (verifie toutes les 60 s)
  python surveiller.py --une-fois  : une seule verification, pour cron ou le planificateur Windows"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from commun import SOURCES

ETAT = Path(".etat_sources.json")


def signature():
    return {str(f): [f.stat().st_size, f.stat().st_mtime_ns] for f in sorted(SOURCES.rglob("*")) if f.is_file()}


def verifier():
    avant = json.loads(ETAT.read_text()) if ETAT.exists() else {}
    maintenant = signature()
    if maintenant == avant:
        return None
    nouveaux = [f for f in maintenant if maintenant[f] != avant.get(f)]
    print(f"{len(nouveaux)} fichier(s) nouveau(x) ou modifie(s), lancement du pipeline")
    code = subprocess.call([sys.executable, "lancer.py"])
    if code == 0:
        ETAT.write_text(json.dumps(maintenant))
    return code


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--une-fois", action="store_true")
    args = p.parse_args()
    if args.une_fois:
        code = verifier()
        return 0 if code in (None, 0) else code
    while True:
        verifier()
        time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
