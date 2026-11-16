import {datasets} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {parseCSV} from '../utils/csv.js';
import {EventStatus,VersionStatus} from '../constants/enums.js';
function eventItem(e,canWrite){
 const bounds=e.start_minute==null||e.end_minute==null?'边界缺失':fmt(e.start_minute)+'–'+fmt(e.end_minute)+' 分钟';
 if(e.status==='pending'&&canWrite)return '<article class="event-item"><div><span class="chip pending">待核对</span><strong>'+esc(e.route)+'</strong><p>'+esc(e.label||'开箱事件')+' · '+esc(e.reason||'待核对')+'</p><div class="bound-inputs"><input type="number" step="any" data-bs="'+e.id+'" value="'+(e.start_minute??'')+'" placeholder="开始分钟"><input type="number" step="any" data-be="'+e.id+'" value="'+(e.end_minute??'')+'" placeholder="结束分钟"></div></div><div class="event-actions"><button class="button small" data-apply="'+e.id+'">修正生效</button><button class="text-button" data-dismiss="'+e.id+'">驳回</button></div></article>';
 return '<article class="event-item"><div><span class="chip '+esc(e.status)+'">'+esc(EventStatus[e.status]||e.status)+'</span><strong>'+esc(e.route)+'</strong><p>'+esc(e.label||'开箱事件')+' · '+esc(bounds)+'</p><small>'+esc(e.created_by)+' · '+date(e.created_at)+'</small></div></article>';
}
function versionItem(v,isAdmin){
 return '<article class="version-item"><div><span class="chip '+esc(v.status)+'">'+esc(VersionStatus[v.status]||v.status)+'</span><strong>v'+v.version_no+'</strong><p>'+(v.events.length?'补录 '+v.events.length+' 段 · 事件影响 '+v.affected_total+' 点':'基线 · 无开箱补录')+(v.note?' · '+esc(v.note):'')+'</p><small>SHA256 '+esc(v.checksum.slice(0,18))+'…'+(v.published_at?' · 发布于 '+date(v.published_at):'')+'</small></div>'+(v.status==='draft'&&isAdmin?'<button class="button small" data-publish="'+v.id+'">发布此版本</button>':'')+'</article>';
}
export async function dataPage(){
 workspace.datasets=await datasets.list();
 if(!workspace.selectedDataset||!workspace.datasets.some(d=>d.id===workspace.selectedDataset))workspace.selectedDataset=workspace.datasets[0]?.id;
 const selected=workspace.selectedDataset?await datasets.get(workspace.selectedDataset):null;
 const [events,versions]=selected?await Promise.all([datasets.events(selected.id),datasets.versions(selected.id)]):[[],[]];
 const m=workspace.meta,canWrite=session.user.role!=='viewer',isAdmin=session.user.role==='admin';
 const routes=selected?[...new Set(selected.records.map(r=>String(r.route)))]:[];
 return heading('02 / DATA INTAKE','数据接入与批次追溯','保留原始业务字段、来源和内容指纹。分析任务始终绑定一个不可变数据批次；开箱补录只追加版本，不改原样本。')+'<div class="dataset-grid"><section class="panel"><div class="section-title"><h2>业务批次</h2><span>'+workspace.datasets.length+' 批</span></div><div class="batch-list">'+workspace.datasets.map(d=>'<button class="batch-item'+(d.id===workspace.selectedDataset?' active':'')+'" data-dataset="'+d.id+'"><strong>'+esc(d.name)+'</strong><span>'+d.rows+' 条 · '+esc(d.source)+'</span><small>v'+(d.current_version_no??'—')+' 已发布 · SHA256 '+esc(d.checksum.slice(0,14))+'…'+(d.pending_events?' · <b class="pending-count">'+d.pending_events+' 条待核对</b>':'')+'</small></button>').join('')+'</div><div class="section-title"><h2>接入新数据</h2></div><form id="dataset-form"><label>批次名称<input name="name" required minlength="2" placeholder="例如：11 月复测批次"></label><label>上传 CSV 或 JSON<input type="file" id="file-input" accept=".json,.csv"></label><label>记录 JSON<textarea name="records" rows="6" placeholder="粘贴 JSON 数组，或先选择上方文件" required></textarea></label><p class="hint">字段：'+m.columns.map(c=>esc(c.key)+' / '+esc(c.label)).join('，')+'。5–5,000 条记录。</p><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>校验并接入批次</button></form></section><section class="panel"><div class="section-title"><h2 id="preview-name">'+esc(selected?.name||'尚无批次')+'</h2><span>预览前 30 条</span></div><div id="data-preview">'+table(m.columns,selected?.records.slice(0,30)||[])+'</div></section></div>'
 +(selected?'<section class="panel"><div class="section-title"><h2>开箱事件补录 · '+esc(selected.name)+'</h2><span>原样本只读，生效补录生成新调查版本</span></div><div class="supplement-grid"><form id="event-form"><label>路线<select name="route">'+routes.map(r=>'<option value="'+esc(r)+'">'+esc(r)+'</option>').join('')+'</select></label><div class="parameter-grid"><label>开箱开始 · 发车后分钟<input type="number" step="any" name="start_minute" placeholder="留空则进入待核对"></label><label>开箱结束 · 发车后分钟<input type="number" step="any" name="end_minute" placeholder="留空则进入待核对"></label></div><label>事件说明<input name="label" maxlength="160" placeholder="例如：收费站开箱查验"></label><button type="submit" class="primary" '+(canWrite?'':'disabled')+'>补录开箱区间</button><p class="hint">缺边界或与已生效区间重叠的补录进入待核对；提交中断后重试不会重复记录。覆盖的测温点在调查中标为事件影响。</p></form><div><div class="section-title"><h2>补录记录</h2><span>'+events.filter(e=>e.status==='pending').length+' 条待核对</span></div><div class="event-list">'+(events.map(e=>eventItem(e,canWrite)).join('')||'<p class="empty">尚无补录记录。</p>')+'</div></div></div></section><section class="panel"><div class="section-title"><h2>版本链</h2><span>仅已发布版本进入计算、批准与定时分发</span></div><div class="version-chain">'+versions.map(v=>versionItem(v,isAdmin)).join('')+'</div></section>':'');
}
export function bindData(refresh){
 let source='manual.json';
 const requestId=crypto.randomUUID();
 document.querySelector('#file-input').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;source=file.name;const text=await file.text(),records=file.name.endsWith('.csv')?parseCSV(text):JSON.parse(text);document.querySelector('[name=records]').value=JSON.stringify(records,null,2);}catch(error){notify(error.message,true);}});
 document.querySelectorAll('[data-dataset]').forEach(button=>button.onclick=async()=>{workspace.selectedDataset=Number(button.dataset.dataset);await refresh();});
 submit(document.querySelector('#dataset-form'),async f=>{await datasets.create({name:f.get('name'),source,records:JSON.parse(f.get('records'))});notify('数据已接入，可前往工作台执行分析');await refresh();});
 const eventForm=document.querySelector('#event-form');
 if(eventForm)submit(eventForm,async f=>{
  const ev={route:f.get('route'),label:f.get('label')||''};
  if(f.get('start_minute')!=='')ev.start_minute=Number(f.get('start_minute'));
  if(f.get('end_minute')!=='')ev.end_minute=Number(f.get('end_minute'));
  const r=await datasets.supplement(workspace.selectedDataset,{request_id:requestId,events:[ev]});
  const pending=r.events.filter(e=>e.status==='pending').length;
  notify(!r.created?'该请求已记录过，未重复补录':pending?'已记录，'+pending+' 段进入待核对':'补录已生效，已生成新草稿版本');
  await refresh();
 });
 document.querySelectorAll('[data-apply]').forEach(b=>b.onclick=async()=>{
  const id=b.dataset.apply,payload={action:'apply'};
  const s=document.querySelector('[data-bs="'+id+'"]').value,e=document.querySelector('[data-be="'+id+'"]').value;
  if(s!=='')payload.start_minute=Number(s);
  if(e!=='')payload.end_minute=Number(e);
  try{await datasets.resolve(workspace.selectedDataset,id,payload);notify('补录已生效，生成新草稿版本');await refresh();}catch(err){notify(err.message,true);}
 });
 document.querySelectorAll('[data-dismiss]').forEach(b=>b.onclick=async()=>{try{await datasets.resolve(workspace.selectedDataset,b.dataset.dismiss,{action:'dismiss'});notify('补录已驳回');await refresh();}catch(err){notify(err.message,true);}});
 document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=async()=>{try{const v=await datasets.publish(workspace.selectedDataset,b.dataset.publish);notify('v'+v.version_no+' 已发布：计算、批准与分发已切换到该版本');await refresh();}catch(err){notify(err.message,true);}});
}
