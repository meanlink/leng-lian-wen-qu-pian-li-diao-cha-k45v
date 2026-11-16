from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from src.config.database import get_db
from src.models import Dataset, DoorEvent, DatasetVersion
from src.schemas.dataset import DatasetInput, SupplementInput, ResolveInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import datasets
from src.services import versions as versions_svc
from src.services.audit import record
from src.utils.serialization import dataset_dict, event_dict, version_dict
router=APIRouter(prefix='/datasets')
def _locked_dataset(db,id):
    d=db.scalar(select(Dataset).where(Dataset.id==id).with_for_update())
    if not d: raise HTTPException(404,'数据批次不存在')
    return d
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    out=[]
    for d in db.scalars(select(Dataset).order_by(Dataset.id.desc())):
        row=dataset_dict(d)
        row['pending_events']=db.scalar(select(func.count()).select_from(DoorEvent).where(DoorEvent.dataset_id==d.id,DoorEvent.status=='pending'))
        v=versions_svc.published_version(db,d.id)
        row['current_version_no']=v.version_no if v else None
        out.append(row)
    return out
@router.post('',status_code=201)
def create(data:DatasetInput,db=Depends(get_db),u=Depends(can_write)):
    d=datasets.create(db,data,u.email); record(db,u.email,'dataset.create',{'id':d.id,'rows':len(d.records)})
    db.commit(); return dataset_dict(d)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    d=db.get(Dataset,id)
    if not d:raise HTTPException(404,'数据批次不存在')
    return {**dataset_dict(d),'records':d.records}
@router.get('/{id}/events')
def events(id:int,db=Depends(get_db),u=Depends(current_user)):
    if not db.get(Dataset,id): raise HTTPException(404,'数据批次不存在')
    return [event_dict(e) for e in db.scalars(select(DoorEvent).where(DoorEvent.dataset_id==id).order_by(DoorEvent.id.desc()))]
@router.post('/{id}/events',status_code=201)
def supplement(id:int,data:SupplementInput,db=Depends(get_db),u=Depends(can_write)):
    d=_locked_dataset(db,id)
    evs,version,created=versions_svc.supplement(db,d,data,u.email)
    record(db,u.email,'dataset.supplement',{'id':id,'events':len(evs),'applied':sum(1 for e in evs if e.status=='applied'),'pending':sum(1 for e in evs if e.status=='pending'),'version':version.version_no if version else None,'replayed':not created})
    db.commit()
    return {'events':[event_dict(e) for e in evs],'version':version_dict(version) if version else None,'created':created}
@router.post('/{id}/events/{event_id}/resolve')
def resolve(id:int,event_id:int,data:ResolveInput,db=Depends(get_db),u=Depends(can_write)):
    d=_locked_dataset(db,id)
    e=db.get(DoorEvent,event_id)
    if not e or e.dataset_id!=id: raise HTTPException(404,'补录记录不存在')
    e,version=versions_svc.resolve_event(db,d,e,data,u.email)
    record(db,u.email,'event.resolve',{'id':event_id,'action':data.action,'version':version.version_no if version else None})
    db.commit()
    return {'event':event_dict(e),'version':version_dict(version) if version else None}
@router.get('/{id}/versions')
def versions(id:int,db=Depends(get_db),u=Depends(current_user)):
    if not db.get(Dataset,id): raise HTTPException(404,'数据批次不存在')
    return [version_dict(v) for v in db.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id==id).order_by(DatasetVersion.version_no))]
@router.post('/{id}/versions/{version_id}/publish')
def publish(id:int,version_id:int,db=Depends(get_db),u=Depends(admin_only)):
    d=_locked_dataset(db,id)
    v=db.get(DatasetVersion,version_id)
    if not v or v.dataset_id!=id: raise HTTPException(404,'调查版本不存在')
    v,changed=versions_svc.publish(db,d,v,u.email)
    if changed: record(db,u.email,'version.publish',{'dataset':id,'version':v.version_no})
    db.commit()
    return version_dict(v)
