import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)}),
 events:id=>api('/datasets/'+id+'/events'),supplement:(id,data)=>api('/datasets/'+id+'/events',{method:'POST',body:JSON.stringify(data)}),
 resolve:(id,eventId,data)=>api('/datasets/'+id+'/events/'+eventId+'/resolve',{method:'POST',body:JSON.stringify(data)}),
 versions:id=>api('/datasets/'+id+'/versions'),publish:(id,versionId)=>api('/datasets/'+id+'/versions/'+versionId+'/publish',{method:'POST'})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
