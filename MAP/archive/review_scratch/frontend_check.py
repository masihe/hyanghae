"""Apply the same label/boundary audit to the attached nine-region sketch."""
from reproduce import ROOT, SCRATCH
import json
import time
import textwrap
import numpy as np
import pandas as pd
import scent_map as sm
from scipy.spatial import ConvexHull, Delaunay
from scipy.spatial.distance import pdist, squareform, cdist

started=time.perf_counter()
doc=json.loads((ROOT/'output/scent_map_v1.json').read_text(encoding='utf-8'))
p=doc['perfumes']
xy=np.array([[r['x'],r['y']] for r in p])
original=np.array([r['cluster'] for r in p])
big=[c for c in np.unique(original) if (original==c).sum()>=10]
centers=np.array([xy[original==c].mean(axis=0) for c in big])
labels=original.copy()
for i in np.flatnonzero(~np.isin(original,big)):
    labels[i]=big[np.linalg.norm(xy[i]-centers,axis=1).argmin()]
sizes=sorted([int((labels==c).sum()) for c in big],reverse=True)
assert sizes==[285,201,148,128,122,48,29,24,15]
data=pd.read_csv(ROOT/'perfumes.csv',usecols=['id','accords']).set_index('id')
targets=data.loc[[r['id'] for r in p]].copy()
targets['accord_list']=targets.accords.map(sm.parse_accords)
for c in big:
    acc={}
    for ls in targets.loc[labels==c,'accord_list']:
        for name,value in ls: acc[name]=acc.get(name,0)+value
    doc['clusters'][int(c)]['top_accords']=[a for a,v in sorted(acc.items(),key=lambda av:-av[1])[:3]]
out={'sizes':sizes,'moves':[{'id':p[i]['id'],'from':int(original[i]),'to':int(labels[i])}
                         for i in np.flatnonzero(original!=labels)]}
def save(key,value,since):
    out[key]=value
    out.setdefault('timings',{})[key]=time.perf_counter()-since
    out['seconds']=time.perf_counter()-started
    (SCRATCH/'frontend_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(key,'complete',flush=True)

# Reuse the exact scratch audit calculations, changing only the input labels.
source=(SCRATCH/'experiments.py').read_text(encoding='utf-8')
a=source.index('    t = time.perf_counter()\n    vocab =')
b=source.index('t = time.perf_counter()\ndl=squareform')
exec(compile(textwrap.dedent(source[a:b]),str(SCRATCH/'experiments.py')+' [label block]','exec'))
end=source.index('t=time.perf_counter()\n# Exact expectation')
exec(compile(source[b:end],str(SCRATCH/'experiments.py')+' [boundary block]','exec'))
