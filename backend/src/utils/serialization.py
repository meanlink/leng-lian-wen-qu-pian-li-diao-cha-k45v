import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def event_dict(e):
    return {k:getattr(e,k) for k in ['id','dataset_id','route','start_minute','end_minute','label','status','reason','created_by','created_at']}
def version_dict(v):
    return {'id':v.id, 'dataset_id':v.dataset_id, 'version_no':v.version_no, 'status':v.status, 'events':v.events,
            'affected_total':sum(len(s) for s in v.affected.values()), 'affected_routes':{k:len(s) for k,s in v.affected.items()},
            'checksum':v.checksum, 'note':v.note, 'created_by':v.created_by, 'created_at':v.created_at, 'published_at':v.published_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','version_id','version_no','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination','version_no','superseded_by']}
