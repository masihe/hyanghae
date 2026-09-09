"""Bounded review experiments. Requires byte-identical baseline first."""
from reproduce import ROOT, SCRATCH, digest
import json
import time
import sys
import numpy as np
import pandas as pd
import build_map as bm
import scent_map as sm
import umap
from sklearn.cluster import AgglomerativeClustering
from scipy.spatial import ConvexHull, Delaunay
from scipy.spatial.distance import pdist, squareform, cdist

started = time.perf_counter()
check = json.loads((SCRATCH / 'baseline_check.json').read_text())
assert all(x['byte_equal'] for x in check['comparison'].values())
resume = '--resume-boundaries' in sys.argv
out = json.loads((SCRATCH / 'measurements.json').read_text(encoding='utf-8')) if resume else {'timings': {}}
if resume:
    started -= out['seconds']

def save(key, value, since):
    out[key] = value
    out['timings'][key] = time.perf_counter() - since
    out['seconds'] = time.perf_counter() - started
    (SCRATCH / 'measurements.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(key, json.dumps(value, ensure_ascii=False), flush=True)

t = time.perf_counter()
df, targets, idf, S, D, ix, ce, ae = bm.prepare(with_selection_comparison=False)
doc = json.loads((ROOT / 'output/scent_map_v1.json').read_text(encoding='utf-8'))
assert [p['id'] for p in doc['perfumes']] == targets['id'].tolist()
xy = np.array([[p['x'], p['y']] for p in doc['perfumes']])
labels = np.array([p['cluster'] for p in doc['perfumes']])
merged, _ = bm.merge_small_clusters(D, labels)
reminds = sm.load_edges('reminds_edges.csv')
conf = reminds[bm.confident(reminds)]
save('prepare', {'n':len(targets), 'edges':len(ce)}, t)

if resume:
    reducer42 = umap.UMAP(n_components=2, metric='precomputed', n_neighbors=10, min_dist=.1, random_state=42)
    raw42 = reducer42.fit_transform(D)
else:
    t = time.perf_counter()
    rows = []
    reducer42 = None
    raw42 = None
    for nn in [10, 15]:
        for seed in [0, 1, 2, 3, 42]:
            reducer = umap.UMAP(n_components=2, metric='precomputed', n_neighbors=nn, min_dist=.1, random_state=seed)
            coords = reducer.fit_transform(D)
            metrics = bm.evaluate_layout(coords.astype(float), D, ix, ce)
            rows.append({'nn':nn, 'seed':seed, **metrics})
            if nn == 10 and seed == 42:
                reducer42, raw42 = reducer, coords
            print('seed complete', nn, seed, flush=True)
    tab = pd.DataFrame(rows)
    summary = []
    for nn, g in tab.groupby('nn'):
        summary.append({'nn':int(nn), **{m:{'mean':g[m].mean(), 'sd_sample':g[m].std(ddof=1)}
                       for m in ['trust@10','knn_overlap@10','reminds_pct']}})
    paired = tab[tab.nn==10].set_index('seed').select_dtypes('number') - tab[tab.nn==15].set_index('seed').select_dtypes('number')
    save('seeds', {'rows': rows, 'summary':summary, 'paired_nn10_minus_nn15':{
        m:{'mean':paired[m].mean(), 'sd_sample':paired[m].std(ddof=1), 'values':paired[m].tolist()}
        for m in ['trust@10','knn_overlap@10','reminds_pct']}}, t)

    t = time.perf_counter()
    cluster_rows = []
    for seed in [0,1,2,3,42]:
        np.random.seed(seed)
        lab = AgglomerativeClustering(n_clusters=12, metric='precomputed', linkage='average').fit_predict(D)
        cluster_rows.append({'seed':seed,'exact_equal':bool(np.array_equal(labels,lab))})
    comparisons = []
    for method in ['average','complete','single']:
        lab = AgglomerativeClustering(n_clusters=12, metric='precomputed', linkage=method).fit_predict(D)
        obs, exp, per = bm.region_cohesion(xy, lab)
        cross = sum(lab[ix[a]] != lab[ix[b]] for a,b in ce)
        comparisons.append({'method':method, 'k':len(np.unique(lab)), 'cohesion':obs,'expected':exp,
            'cross':int(cross), 'cross_fraction':float(cross/len(ce)), 'sizes':sorted(np.bincount(lab).tolist(),reverse=True),
            'weak_labels':sum(v<.35 for v in per.values()),'per_cluster':per})
    save('clusters', {'determinism':cluster_rows,'comparisons':comparisons},t)

    t = time.perf_counter()
    supervised = []
    for w in [.05,.1]:
        coords = umap.UMAP(n_components=2, metric='precomputed', n_neighbors=10, min_dist=.1,
                          random_state=42,target_metric='categorical',target_weight=w).fit_transform(D,y=merged)
        m = bm.experiment_metrics(coords,D,ix,ce,ae,merged,targets['display'].to_numpy())
        m.update({'weight':w,'far_dist':2.5/(1-w),'cross_graph_multiplier':float(np.exp(-2.5/(1-w)))})
        supervised.append(m)
    save('supervised_low',supervised,t)

    t = time.perf_counter()
    pool = sm.usable_pool(df).sort_values(['vote_count','id'], ascending=[False,True])
    def selection_stats(name, sub):
        e = bm.edges_within(conf,set(sub.id))
        return {'method':name,'n':len(sub),'accords':int(sub.dominant_accord.nunique()),
                'brands':int(sub.brand.nunique()), 'confident_edges':len(e),
                'top10_brand_share':float(sub.brand.value_counts().head(10).sum()/len(sub)),
                'vote_min':int(sub.vote_count.min()),'vote_median':float(sub.vote_count.median()),
                'group_counts':sub.group.value_counts().to_dict()}
    # Exactly two alternatives, neither reads edge labels during selection.
    # Minimal coverage constraint, then fill by popularity. Brand cap is fixed at 20.
    representatives = pool.drop_duplicates('dominant_accord')
    cover = pd.concat([representatives,pool[~pool.id.isin(representatives.id)]]).head(1000)
    capped = pool[pool.groupby('brand').cumcount()<20].head(1000)
    save('selection',[selection_stats('popularity',pool.head(1000)),selection_stats('adopted',targets),
                      selection_stats('one_per_accord_then_popularity',cover),selection_stats('brand_cap20',capped)],t)

    t = time.perf_counter()
    # Reproduce Development only. Do not access a saved Holdout, materialize its slice,
    # or evaluate it. Pair aggregation and split match verify_similarity.py:36-82.
    e = reminds[(reminds.src>0)&(reminds.dst>0)&(reminds.up_votes>=0)&(reminds.down_votes>=0)]
    pair = pd.DataFrame({'low':np.minimum(e.src,e.dst),'high':np.maximum(e.src,e.dst),'up':e.up_votes,'down':e.down_votes})
    pair = pair.groupby(['low','high'],sort=False,as_index=False)[['up','down']].sum()
    total = pair.up+pair.down
    rel = pair[(pair.low!=pair.high)&(total>=20)&(pair.up/total>=.8)&pair.low.isin(df.id)&pair.high.isin(df.id)]
    relevant = {}
    for a,b in rel[['low','high']].itertuples(index=False,name=None):
        relevant.setdefault(int(a),set()).add(int(b)); relevant.setdefault(int(b),set()).add(int(a))
    valid_ids = set(df.loc[df.accord_list.str.len().gt(0)&df.note_set.str.len().gt(0),'id'])
    eligible = np.array(sorted(q for q,vs in relevant.items() if len(vs)>=2 and q in valid_ids),dtype=np.int32)
    development = np.random.default_rng(42).permutation(np.random.default_rng(42).choice(eligible,size=1000,replace=False))[:700]
    tuning = set(np.random.default_rng(42).permutation(development)[:500].tolist())
    dev = set(development.tolist())
    edge_set = set(ce)
    undirected = {tuple(sorted(p)) for p in ce}
    overlap = {}
    for name,qs in [('development700',dev),('tuning500',tuning),('validation200',dev-tuning)]:
        used = {(q,b) for q in qs for b in relevant[q]}
        u_used = {tuple(sorted(p)) for p in used}
        overlap[name] = {'queries_on_map':len(qs & set(targets.id)),
            'map_edges_source_query':sum(a in qs for a,b in ce),
            'map_directed_relevance_overlap':len(edge_set & used),
            'map_directed_edges_matching_unordered_relevance':sum(tuple(sorted(p)) in u_used for p in ce),
            'map_unique_unordered_relevance_overlap':len(undirected & u_used)}
    save('development_overlap',{'eligible':len(eligible),'development':len(dev),'map_directed':len(ce),
                              'map_unique_unordered':len(undirected),'sets':overlap},t)

    t = time.perf_counter()
    vocab = sorted({a for ls in targets.accord_list for a,_ in ls})
    vi = {a:i for i,a in enumerate(vocab)}
    raw = np.zeros((len(targets),len(vocab)))
    top5 = raw.copy()
    for i,ls in enumerate(targets.accord_list):
        for j,(a,v) in enumerate(ls):
            raw[i,vi[a]]=v
            if j<5: top5[i,vi[a]]=v
    label_rows=[]
    for c in np.unique(labels):
        mask=labels==c
        row={'cluster':int(c),'size':int(mask.sum()),'frequency_strength':doc['clusters'][int(c)]['top_accords']}
        for name,arr in [('top5',top5),('all8',raw)]:
            glob=arr.mean(axis=0)
            mean=arr[mask].mean(axis=0)
            lift=np.divide(mean,glob,out=np.zeros_like(mean),where=glob>0)
            coverage=(arr[mask]>0).mean(axis=0)
            for threshold in [.2,.3,.4]:
                inds=[i for i in range(len(vocab)) if coverage[i]>=threshold]
                inds.sort(key=lambda i:(-lift[i],-mean[i],vocab[i]))
                row[f'{name}_{threshold}']=[{'accord':vocab[i],'lift':float(lift[i]),'coverage':float(coverage[i])} for i in inds[:3]]
        label_rows.append(row)
    save('labels',label_rows,t)

t = time.perf_counter()
dl=squareform(pdist(xy)); np.fill_diagonal(dl,np.inf)
h=float(np.median(np.partition(dl,10,axis=1)[:,9]))
def boundary_stats(name,membership):
    total=int(membership.sum())
    correct=int(membership[np.arange(len(labels)),labels].sum())
    per=[]
    for c in range(12):
        inside=membership[:,c]
        per.append({'cluster':c,'inside':int(inside.sum()),'other':int((inside&(labels!=c)).sum()),
                    'own_retained':int((inside&(labels==c)).sum())})
    return {'method':name,'point_region_memberships':total,'other_memberships':total-correct,
            'contamination':(total-correct)/total,'own_retention':correct/len(labels),
            'points_in_any_region':int(membership.any(axis=1).sum()),'per_cluster':per}
boundary=[]
membership=np.zeros((len(xy),12),dtype=bool)
for c in range(12):
    pts=xy[labels==c]
    if len(pts)>=3 and np.linalg.matrix_rank(pts-pts[0])==2:
        hull=ConvexHull(pts)
        membership[:,c]=(xy@hull.equations[:,:2].T+hull.equations[:,2]<=1e-10).all(axis=1)
boundary.append(boundary_stats('convex_hull',membership))
for scale in [1,2,4]:
    membership=np.zeros((len(xy),12),dtype=bool)
    for c in range(12):
        pts=xy[labels==c]
        if len(pts)<3 or np.linalg.matrix_rank(pts-pts[0])<2: continue
        tri=Delaunay(pts)
        for vs in pts[tri.simplices]:
            a,b,d=np.linalg.norm(vs[0]-vs[1]),np.linalg.norm(vs[1]-vs[2]),np.linalg.norm(vs[2]-vs[0])
            area2=abs(np.linalg.det(np.stack([vs[1]-vs[0],vs[2]-vs[0]])))
            if area2<=0 or a*b*d/(2*area2)>scale*h: continue
            bary=np.linalg.solve(np.stack([vs[1]-vs[0],vs[2]-vs[0]],axis=1),(xy-vs[0]).T).T
            membership[:,c]|=(bary>=-1e-10).all(axis=1)&(bary.sum(axis=1)<=1+1e-10)
    boundary.append(boundary_stats(f'alpha_circumradius_le_{scale}h',membership))
for scale in [.5,1,2]:
    kernel=np.exp(-cdist(xy,xy,'sqeuclidean')/(2*(h*scale)**2))
    for loo in [False,True]:
        k=kernel.copy()
        if loo: np.fill_diagonal(k,0)
        scores=np.column_stack([k[:,labels==c].sum(axis=1) for c in range(12)])
        winner=scores.argmax(axis=1)
        membership=np.eye(12,dtype=bool)[winner]
        boundary.append(boundary_stats(f'kde_sum_h{scale}_loo{loo}',membership))
save('boundaries',{'h_median_10th_neighbor':h,'rows':boundary},t)

t=time.perf_counter()
# Exact expectation calculations for the existing definitions; no metric changes.
counts=np.bincount(labels)
merged_counts=np.bincount(merged)
save('metric_expectations',{'n':len(labels),'reminds_no_tie_null':float(np.arange(999).mean()/999),
    'cohesion_code':float(((counts/1000)**2).sum()),
    'cohesion_without_replacement':float((counts*(counts-1)).sum()/(1000*999)),
    'merged_cohesion_code':float(((merged_counts/1000)**2).sum()),
    'merged_cohesion_without_replacement':float((merged_counts*(merged_counts-1)).sum()/(1000*999)),
    'mean_preserved_neighbors':float(bm.knn_overlap(D,raw42)*10)},t)

t=time.perf_counter()
# Check raw JSONL against caches without altering caches.
cache_people=df.set_index('id').people
people_bad=0; raw_edges=[]; n_raw=0
with (ROOT/'perfumes.jsonl').open(encoding='utf-8') as f:
    for line in f:
        p=json.loads(line); n_raw+=1
        cp=cache_people.loc[p['id']]; rp=p.get('people')
        people_bad+=int(not ((rp is None and pd.isna(cp)) or (rp is not None and rp==cp)))
        for e in (p.get('similar') or {}).get('reminds_me_of') or []:
            raw_edges.append((p['id'],e.get('id'),e.get('up_votes') or 0,e.get('down_votes') or 0))
raw_e=pd.DataFrame(raw_edges,columns=['src','dst','up_votes','down_votes'])
save('raw_cache',{'jsonl_records':n_raw,'people_mismatch':people_bad,'reminds_raw_count':len(raw_e),
                  'reminds_cache_equal':bool(raw_e.equals(reminds))},t)
del raw_edges, raw_e

t=time.perf_counter()
# The requested expansion includes group-missing perfumes, but requires both features.
full=df[(df.people>=500)&df.accord_list.str.len().gt(0)&df.note_set.str.len().gt(0)]
extra=full[~full.id.isin(targets.id)].sort_values('id').reset_index(drop=True)
combined=pd.concat([targets,extra],ignore_index=True)
A,_=sm.build_accord_matrix(list(combined.accord_list))
B,w,_,_=sm.build_note_matrix(list(combined.note_set),idf)
ns=(B*w).sum(axis=1)
Dnew=np.empty((len(extra),1000),dtype=np.float64)
for start in range(0,len(extra),256):
    sl=slice(1000+start,min(1000+start+256,len(combined)))
    inter=(B[sl]*w)@B[:1000].T
    union=ns[sl,None]+ns[None,:1000]-inter
    sn=np.divide(inter,union,out=np.zeros_like(inter),where=union>0)
    Dnew[start:start+len(sn)]=1-np.clip(.5*(A[sl]@A[:1000].T)+.5*sn,0,1)
transformed=reducer42.transform(Dnew)
allxy=np.vstack([raw42,transformed])
allix={int(v):i for i,v in enumerate(combined.id)}
e_all=bm.edges_within(conf,set(combined.id))
train_ids=set(targets.id); extra_ids=set(extra.id)
projection=[]
for name,mask in [('trained_to_trained',e_all.src.isin(train_ids)&e_all.dst.isin(train_ids)),
                  ('extra_to_any',e_all.src.isin(extra_ids)),
                  ('extra_to_trained',e_all.src.isin(extra_ids)&e_all.dst.isin(train_ids)),
                  ('extra_to_extra',e_all.src.isin(extra_ids)&e_all.dst.isin(extra_ids))]:
    edges=list(e_all.loc[mask,['src','dst']].itertuples(index=False,name=None))
    pct,n=bm.edge_distance_percentile(allxy,allix,edges)
    projection.append({'cohort':name,'n_edges':n,'reminds_pct':pct,
                       'source_nodes':len({a for a,b in edges})})
save('transform',{'people_ge500':int((df.people>=500).sum()),'eligible_with_features':len(full),
    'extra':len(extra),'extra_missing_group':int(extra.group.isna().sum()),
    'candidate_universe':len(combined),'nonfinite_coords':int((~np.isfinite(allxy)).sum()),
    'baseline_training_only':bm.edge_distance_percentile(raw42,ix,ce)[0], 'rows':projection},t)

unchanged=all(digest(ROOT/p)==sha for p,sha in check['protected_sha256'].items())
save('protected_unchanged',unchanged,time.perf_counter())
