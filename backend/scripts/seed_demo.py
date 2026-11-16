import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Dataset, DoorEvent, DatasetVersion, Job, Report, Delivery, Audit
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.services.versions import get_or_create_version, published_version
from src.utils.security import hash_password
from src.utils.serialization import checksum
def seed():
    migrate()
    with Session() as db:
        for role,name in [('admin','林知 · 业务负责人'),('analyst','陈舟 · 分析员'),('viewer','周禾 · 观察员')]:
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,name=name,role=role,password=hash_password('Demo123!')))
        db.flush()
        m=metadata()
        d=db.scalar(select(Dataset).where(Dataset.name==m['dataset_name']))
        if not d:
            rows=seed_records()
            d=Dataset(name=m['dataset_name'],source=m['short']+'-202611.csv',records=rows,checksum=checksum(rows),created_at=time.time())
            db.add(d); db.flush()
        # 版本链兜底：每个批次至少有一个已发布的基线版本，老任务与归档回填到该版本
        for ds in db.scalars(select(Dataset)):
            if not db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id==ds.id)):
                vb,_=get_or_create_version(db,ds,'seed',note='基线版本')
                vb.status='published'; vb.published_at=time.time(); db.flush()
            pub_ds=published_version(db,ds.id)
            for j in db.scalars(select(Job).where(Job.dataset_id==ds.id,Job.version_id.is_(None))):
                j.version_id,j.version_no=pub_ds.id,pub_ds.version_no
            for dl in db.scalars(select(Delivery).join(Report,Delivery.report_id==Report.id).join(Job,Report.job_id==Job.id).where(Job.dataset_id==ds.id,Delivery.version_id.is_(None))):
                j=db.get(Job,db.get(Report,dl.report_id).job_id)
                dl.version_id,dl.version_no=j.version_id,j.version_no
        db.flush()
        pub=published_version(db,d.id)
        if not db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name'])):
            params={p['key']:p['default'] for p in m.get('parameters',[])}
            result=analyze(d.records,params)
            json.dumps(result,ensure_ascii=False,allow_nan=False)
            admin=db.scalar(select(User).where(User.role=='admin'))
            j=Job(name='基线复核 · '+m['name'],dataset_id=d.id,version_id=pub.id,version_no=pub.version_no,params=params,status='completed',result=result,created_by=admin.id,created_at=time.time()-3600,finished_at=time.time()-3595,approved=True)
            db.add(j);db.flush()
            r=Report(name='每日业务复核简报',job_id=j.id,destination='业务复核组 · 本地收件箱',interval_seconds=86400,next_run=time.time()+86400,enabled=True)
            db.add(r);db.flush();deliver(db,r)
            db.add(Audit(actor='seed',action='demo.baseline',detail={'dataset':d.id},at=time.time()))
        # 演示补录：一段生效（生成 v2 草稿）、一段缺边界进入待核对；用户处理过后不再重复补录
        if not db.scalar(select(DoorEvent).where(DoorEvent.dataset_id==d.id)):
            now=time.time()
            db.add(DoorEvent(dataset_id=d.id,route='沪东 B',start_minute=112.0,end_minute=124.0,label='收费站开箱查验',status='applied',reason='',request_id='seed-demo-open-1',created_by='seed',created_at=now))
            db.add(DoorEvent(dataset_id=d.id,route='沪东 B',start_minute=150.0,end_minute=None,label='月台开箱待补终点',status='pending',reason='缺少起止分钟',request_id='seed-demo-open-2',created_by='seed',created_at=now))
            db.flush()
            get_or_create_version(db,d,'seed',note='补录开箱区间')
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in [User,Dataset,DoorEvent,DatasetVersion,Job,Report,Delivery,Audit]}
        print(json.dumps(counts,ensure_ascii=False))
        return counts
if __name__=='__main__':seed()
