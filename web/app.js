"use strict";
const $ = id => document.getElementById(id);
const labels = {ALARMA:"Alarma",PRECAUCION:"Precaución",SIN_ALERTA:"Sin alerta",SIN_DATOS:"Sin datos",INCOMPLETO:"Incompleto",FALLO:"Fallo"};
let key = sessionStorage.getItem("canari_operator") || "", busy=false, sound=null, newestEvent=0, lastRows=[], staleWindow=15;
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const fmt=(x,d=2)=>x===null||x===undefined?"Sin medición":Number(x).toFixed(d);
const date=x=>new Date(x*1000).toLocaleString("es-CO");
async function api(path, options={}){
 const r=await fetch(path,{...options,headers:{Authorization:"Bearer "+key,...options.headers},signal:AbortSignal.timeout(8000)});
 if(!r.ok){let body=await r.json().catch(()=>({}));throw new Error(body.error||"No se pudo consultar el servidor");}
 return r;
}
function badge(level){return element("span",labels[level]||level,"badge "+level);}
function drawNodes(nodes){
 $("nodes").replaceChildren();
 for(const n of nodes){
  const c=element("article",undefined,"node "+n.level),top=element("div",undefined,"topline");
  top.append(element("span",n.id+" · "+(n.source==="simulation"?"SIMULADO":"LABORATORIO")),badge(n.level));c.append(top,element("h3",n.label));
  const valid=n.latest&&n.level!=="SIN_DATOS"&&n.level!=="FALLO", v=valid?n.latest:{};
  const main=element("div",fmt(v.ch4_vol_pct),"metric-main");main.append(element("small"," % vol CH₄"));c.append(main);
  const metrics=element("div",undefined,"metrics");
  for(const [name,label,unit] of [["o2_vol_pct","OXÍGENO","% vol"],["temperature_c","TEMPERATURA","°C"],["humidity_pct","HUMEDAD","% HR"]]){
   const m=element("div");m.append(element("small",label),element("strong",fmt(v[name],1)),element("small",unit));metrics.append(m);
  }c.append(metrics,element("p",n.reasons.join(". "),"detail"),element("div",`Alarma CH₄ ≥ ${n.ch4_alarm_vol_pct} % vol · Antigüedad: ${n.age_seconds===null?"sin muestra":n.age_seconds+" s"}`,"detail"));$("nodes").append(c);
 }
 $("counts").textContent=`${nodes.length} nodos · ${nodes.filter(n=>n.level==="ALARMA").length} en alarma`;
}
function drawEvents(events){
 const tbody=$("events");tbody.replaceChildren();
 for(const e of events){
  const tr=element("tr"),state=element("td"),action=element("td");state.append(badge(e.level));
  if(e.acknowledged_ts){action.textContent="Leído · "+date(e.acknowledged_ts);}
  else {const b=element("button","Reconocer","secondary");b.addEventListener("click",async()=>{b.disabled=true;try{await api(`/api/events/${e.id}/ack`,{method:"POST"});await refresh();}catch(err){$("message").textContent=err.message;}finally{b.disabled=false;}});action.append(b);}
  tr.append(element("td",date(e.created_ts)),element("td",e.node_id),state,element("td",JSON.parse(e.reasons).join(". ")),action);tbody.append(tr);
 }
 if(!events.length){const tr=element("tr"),td=element("td","Sin eventos.");td.colSpan=5;tr.append(td);tbody.append(tr);}
 if(sound&&events.some(e=>e.id>newestEvent&&["ALARMA","SIN_DATOS","FALLO"].includes(e.level))){
  const osc=sound.createOscillator(),gain=sound.createGain();osc.connect(gain);gain.connect(sound.destination);osc.frequency.value=700;gain.gain.value=.08;osc.start();osc.stop(sound.currentTime+.22);
 }if(events.length)newestEvent=Math.max(newestEvent,...events.map(e=>e.id));
}
function svg(tag,attrs,text){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
function drawChart(){
 const chart=$("chart"),metric=$("metric").value,rows=[...lastRows].sort((a,b)=>a.captured_ts-b.captured_ts);
 chart.replaceChildren();
 const valid=rows.filter(r=>r[metric]!==null&&r.device_status==="ok");
 if(!valid.length){chart.append(svg("text",{x:35,y:100,fill:"#61717b","font-size":16},"No hay lecturas válidas para esta variable."));return;}
 const lo=Math.min(...valid.map(r=>r[metric])),hi=Math.max(...valid.map(r=>r[metric])),pad=Math.max((hi-lo)*.15,.1),min=metric==="temperature_c"?lo-pad:Math.max(0,lo-pad),max=hi+pad;
 const start=rows[0].captured_ts,end=rows[rows.length-1].captured_ts;
 const x=t=>65+790*(t-start)/Math.max(1,end-start),y=v=>205-165*(v-min)/Math.max(.1,max-min);
 for(let i=0;i<=4;i++){const v=min+(max-min)*i/4,yy=y(v);chart.append(svg("line",{x1:65,y1:yy,x2:855,y2:yy,stroke:"#e5ecef"}),svg("text",{x:55,y:yy+4,fill:"#61717b","font-size":12,"text-anchor":"end"},v.toFixed(2)));}
 let segment=[];
 const flush=()=>{if(segment.length)chart.append(svg("polyline",{points:segment.join(" "),fill:"none",stroke:"#876615","stroke-width":2.5}));segment=[];};
 let prev=null;
 for(const row of rows){if(row[metric]===null||row.device_status!=="ok"){flush();prev=null;continue;}if(prev!==null&&row.captured_ts-prev>staleWindow)flush();segment.push(x(row.captured_ts)+","+y(row[metric]));prev=row.captured_ts;chart.append(svg("circle",{cx:x(row.captured_ts),cy:y(row[metric]),r:2.5,fill:"#876615"}));}flush();
 chart.append(svg("text",{x:65,y:237,fill:"#61717b","font-size":12},date(start)),svg("text",{x:855,y:237,fill:"#61717b","font-size":12,"text-anchor":"end"},date(end)));
}
function drawHistory(rows){lastRows=rows;$("history").replaceChildren();for(const r of rows.slice(0,25)){const tr=element("tr");for(const v of [date(r.captured_ts),fmt(r.ch4_vol_pct),fmt(r.o2_vol_pct),fmt(r.temperature_c),fmt(r.humidity_pct),r.source,labels[r.level]])tr.append(element("td",v));$("history").append(tr);}$("history-info").textContent=`Últimas ${Math.min(25,rows.length)} de ${rows.length} muestras consultadas. CSV exporta hasta 10 000 del nodo.`;drawChart();}
async function refresh(){
 if(!key||busy)return;busy=true;
 try{
  const [s,e]=await Promise.all([api("/api/status").then(r=>r.json()),api("/api/events").then(r=>r.json())]);
  staleWindow=s.config.stale_after_seconds;
  const select=$("node"),current=select.value;
  if(select.options.length!==s.nodes.length||!s.nodes.some(n=>n.id===current)){select.replaceChildren();for(const n of s.nodes){const o=element("option",n.id+" · "+n.label);o.value=n.id;select.append(o);}if(s.nodes.some(n=>n.id===current))select.value=current;}
  const h=await api("/api/readings?node_id="+encodeURIComponent(select.value)+"&limit=100").then(r=>r.json());
  drawNodes(s.nodes);drawEvents(e);drawHistory(h.readings);
  $("connection").textContent="Conectado al servidor";$("updated").textContent="Consulta: "+new Date(s.server_time).toLocaleTimeString("es-CO");$("message").textContent="Consulta actualizada. Revisa el estado de cada nodo.";
 }catch(err){$("connection").textContent="Sin conexión de datos";$("updated").textContent="No se pueden confirmar lecturas actuales";$("message").textContent=err.message;$("nodes").replaceChildren(element("p","Lecturas actuales no disponibles. Revisa la clave y el servidor.","empty"));$("counts").textContent="Sin datos actuales";lastRows=[];drawChart();}
 finally{busy=false;}
}
$("login").addEventListener("submit",e=>{e.preventDefault();key=$("key").value.trim();sessionStorage.setItem("canari_operator",key);$("key").value="";refresh();});
$("logout").addEventListener("click",()=>{key="";sessionStorage.removeItem("canari_operator");location.reload();});
$("node").addEventListener("change",refresh);$("metric").addEventListener("change",drawChart);
$("sound").addEventListener("click",async()=>{if(sound){await sound.close();sound=null;$("sound").textContent="Activar sonido";}else{sound=new AudioContext();await sound.resume();$("sound").textContent="Desactivar sonido";}});
$("export").addEventListener("click",async()=>{try{const r=await api("/api/export.csv?limit=10000&node_id="+encodeURIComponent($("node").value));const url=URL.createObjectURL(await r.blob());const a=element("a");a.href=url;a.download="canari_lecturas.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){$("message").textContent=err.message;}});
setInterval(refresh,3000);refresh();
