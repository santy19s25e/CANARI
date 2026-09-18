import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--data-dir',type=Path,default=root/'data')
parser.add_argument('--output-dir',type=Path,default=root/'backups')
args=parser.parse_args()
source=args.data_dir/'canari.sqlite3'
if not source.exists():
    parser.error('Todavía no existe una base de datos')
args.output_dir.mkdir(parents=True,exist_ok=True)
target=args.output_dir/('canari_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sqlite3')
with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:
    src.backup(dst)
print('Copia creada:',target.resolve())
