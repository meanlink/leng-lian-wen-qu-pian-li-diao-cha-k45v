"""开箱补录与温区调查版本链：补录校验、待核对处理、版本生成与原子发布切换。"""
import math
import time
from fastapi import HTTPException
from sqlalchemy import select, func, or_
from src.models import Dataset, DoorEvent, DatasetVersion, Job, Report, Delivery
from src.services.business import compute_affected
from src.utils.serialization import checksum


def applied_events(db, dataset_id):
    return list(db.scalars(select(DoorEvent).where(DoorEvent.dataset_id == dataset_id, DoorEvent.status == 'applied').order_by(DoorEvent.id)))


def published_version(db, dataset_id):
    return db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id, DatasetVersion.status == 'published'))


def _snapshot(events):
    return [{'route': e.route, 'start_minute': e.start_minute, 'end_minute': e.end_minute, 'label': e.label} for e in events]


def get_or_create_version(db, dataset, actor, note=''):
    """按当前生效补录集生成调查版本；同一内容指纹的版本只存在一份，重试不产生重复。"""
    snapshot = _snapshot(applied_events(db, dataset.id))
    fp = checksum({'dataset': dataset.checksum, 'events': snapshot})
    v = db.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id, DatasetVersion.checksum == fp))
    if v:
        return v, False
    no = db.scalar(select(func.max(DatasetVersion.version_no)).where(DatasetVersion.dataset_id == dataset.id)) or 0
    v = DatasetVersion(dataset_id=dataset.id, version_no=no + 1, status='draft', events=snapshot,
                       affected=compute_affected(dataset.records, snapshot), checksum=fp,
                       note=note, created_by=actor, created_at=time.time())
    db.add(v)
    db.flush()
    return v, True


def _finite_or_none(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _bounds_problem(start, end):
    if start is None or end is None:
        return '缺少起止分钟'
    s, e = float(start), float(end)
    if not (math.isfinite(s) and math.isfinite(e)):
        return '起止分钟须为有限数值'
    if s > e:
        return '起点分钟大于终点分钟'
    return None


def _overlaps(s1, e1, s2, e2):
    return s1 <= e2 and s2 <= e1


def supplement(db, dataset, data, actor):
    """在同一测温批次上补录开箱区间。原样本不改；缺边界或与已生效区间重叠的进入待核对。
    request_id 是幂等键：中断后重试返回首次结果，不新增重复补录或版本。"""
    existing = list(db.scalars(select(DoorEvent).where(DoorEvent.dataset_id == dataset.id, DoorEvent.request_id == data.request_id)))
    if existing:
        version = None
        if any(e.status == 'applied' for e in existing):
            version, _ = get_or_create_version(db, dataset, actor)
        return existing, version, False
    routes = {str(r.get('route')) for r in dataset.records}
    taken = [(e.route, float(e.start_minute), float(e.end_minute)) for e in applied_events(db, dataset.id)]
    events = []
    for seq, item in enumerate(data.events):
        route = item.route.strip()
        if route not in routes:
            raise HTTPException(422, f'路线 {route} 不在该批次测温记录中')
        start, end = _finite_or_none(item.start_minute), _finite_or_none(item.end_minute)
        reason = _bounds_problem(start, end)
        status = 'pending' if reason else 'applied'
        if not reason and any(r == route and _overlaps(start, end, s2, e2) for r, s2, e2 in taken):
            status, reason = 'pending', '与已生效开箱区间重叠'
        if status == 'applied':
            taken.append((route, start, end))
        ev = DoorEvent(dataset_id=dataset.id, route=route, start_minute=start, end_minute=end,
                       label=item.label.strip(), status=status, reason=reason or '',
                       request_id=data.request_id, seq=seq, created_by=actor, created_at=time.time())
        db.add(ev)
        events.append(ev)
    db.flush()
    version = None
    if any(e.status == 'applied' for e in events):
        version, _ = get_or_create_version(db, dataset, actor, note=f'补录 {sum(1 for e in events if e.status == "applied")} 段开箱区间')
    return events, version, True


def resolve_event(db, dataset, event, data, actor):
    """处理待核对补录：修正边界后生效（重新校验重叠），或驳回。生效会生成新草稿版本。"""
    if event.status != 'pending':
        raise HTTPException(409, '仅待核对的补录可以处理')
    if data.action == 'dismiss':
        event.status, event.reason = 'dismissed', ''
        db.flush()
        return event, None
    if data.action != 'apply':
        raise HTTPException(422, '处理动作只支持 apply 或 dismiss')
    start = _finite_or_none(data.start_minute) if data.start_minute is not None else event.start_minute
    end = _finite_or_none(data.end_minute) if data.end_minute is not None else event.end_minute
    reason = _bounds_problem(start, end)
    if reason:
        raise HTTPException(422, reason + '，请修正后再生效')
    for other in applied_events(db, dataset.id):
        if other.route == event.route and _overlaps(start, end, float(other.start_minute), float(other.end_minute)):
            raise HTTPException(409, '仍与已生效开箱区间重叠，请调整边界或驳回')
    event.start_minute, event.end_minute, event.status, event.reason = start, end, 'applied', ''
    db.flush()
    version, _ = get_or_create_version(db, dataset, actor, note='待核对补录生效')
    return event, version


def publish(db, dataset, version, actor):
    """原子切换：同一时刻只有一个已发布版本；计算、批准、分发都以它为准。
    重复发布是幂等空操作；已发简报保留原内容，仅标记受影响版本。"""
    if version.status == 'published':
        return version, False
    if version.status == 'superseded':
        raise HTTPException(409, '该版本已被更新的版本取代，不能重新发布')
    current = published_version(db, dataset.id)
    if current:
        current.status = 'superseded'
    version.status = 'published'
    version.published_at = time.time()
    stale = db.scalars(select(Delivery).join(Report, Delivery.report_id == Report.id).join(Job, Report.job_id == Job.id)
                       .where(Job.dataset_id == dataset.id, or_(Delivery.version_id.is_(None), Delivery.version_id != version.id), Delivery.superseded_by.is_(None)))
    for d in stale:
        d.superseded_by = version.version_no
    db.flush()
    return version, True
