import time
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata
from src.services.versions import published_version, get_or_create_version
def create(db, data, user):
    d=db.get(Dataset,data.dataset_id)
    if not d: raise HTTPException(404,'数据批次不存在')
    v=published_version(db,d.id)
    if not v:
        v,_=get_or_create_version(db,d,user.email,note='基线版本')
        v.status='published'; v.published_at=time.time()
    allowed={p['key']:p for p in metadata().get('parameters',[])}
    if set(data.params)-set(allowed): raise HTTPException(422,'包含未知分析参数')
    params={k:p['default'] for k,p in allowed.items()}
    params.update(data.params)
    for key,p in allowed.items():
        v2=params[key]
        if p['type']=='number':
            try:
                v2=float(v2)
                if not (p.get('min',-1e9)<=v2<=p.get('max',1e9)): raise ValueError()
                params[key]=v2
            except (ValueError,TypeError): raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v2) not in [str(o['value']) for o in p.get('options',[])]:
            raise HTTPException(422,f'{p["label"]} 不是有效选项')
    j=Job(name=data.name, dataset_id=data.dataset_id, version_id=v.id, version_no=v.version_no, params=params, created_by=user.id, created_at=time.time(), status='queued')
    db.add(j); db.flush()
    return j
def enqueue(job_id):
    try:
        r=Redis.from_url(REDIS_URL); r.rpush('analysis:queue',job_id); r.close()
    except Exception:
        pass # SQL queued status is the durable fallback
