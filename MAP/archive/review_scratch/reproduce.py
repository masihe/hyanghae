"""Read-only baseline audit; all generated files stay in review_scratch."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]  # MAP/
SCRATCH = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'src' / 'map'), str(ROOT / 'src' / 'common')]
os.environ['NUMBA_CACHE_DIR'] = str(SCRATCH / 'numba_cache')
os.environ['MPLCONFIGDIR'] = str(SCRATCH / 'mpl_cache')
os.environ['TMPDIR'] = str(SCRATCH)
os.environ['TEMP'] = str(SCRATCH)
os.environ['TMP'] = str(SCRATCH)

def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if 'holdout' in str(path).lower():
        raise PermissionError('Final Holdout access is forbidden')
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
        isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if writing and not path.is_relative_to(SCRATCH):
        raise PermissionError(f'Write outside scratch: {path}')

sys.addaudithook(audit)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__ == '__main__':
    started = time.perf_counter()
    protected = [ROOT / n for n in ['src/map/build_map.py', 'src/common/scent_map.py',
                                  'src/map/verify_similarity.py',
                                  'src/map/review_k.py', 'docs/DECISIONS.md']]
    protected += sorted((ROOT / 'results').glob('*.csv'))
    protected += sorted((ROOT / 'output').glob('*'))
    protected = [p for p in protected if p.is_file()]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    versions = {p: importlib.metadata.version(p) for p in
                ['numpy', 'pandas', 'scipy', 'scikit-learn', 'umap-learn', 'numba', 'llvmlite']}
    print('ENVIRONMENT', sys.version, versions, flush=True)
    import build_map as bm
    bm.OUT_DIR = str(SCRATCH / 'baseline' / 'output')
    bm.RESULTS_DIR = str(SCRATCH / 'baseline' / 'results')
    assert bm.SEED == 42
    error = None
    try:
        bm.main()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        error = f'{type(exc).__name__}: {exc}'
    comparison = {}
    for name in ['results/layout_comparison.csv', 'output/scent_map_v1.json',
                 'results/selection_comparison.csv']:
        original, regenerated = ROOT / name, SCRATCH / 'baseline' / name
        comparison[name] = {'original_sha256': digest(original),
                            'regenerated_sha256': digest(regenerated) if regenerated.exists() else None,
                            'byte_equal': original.read_bytes() == regenerated.read_bytes() if regenerated.exists() else False}
    after = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    result = {'seconds': time.perf_counter() - started, 'versions': versions,
              'python': sys.version, 'error': error, 'comparison': comparison,
              'protected_unchanged': before == after, 'protected_sha256': before}
    (SCRATCH / 'baseline_check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('BASELINE_CHECK', json.dumps(result, indent=2), flush=True)
