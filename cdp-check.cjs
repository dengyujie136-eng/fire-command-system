const http = require('http');
function getJson(path){return new Promise((resolve,reject)=>{http.get({host:'127.0.0.1',port:9224,path},res=>{let d='';res.on('data',c=>d+=c);res.on('end',()=>resolve(JSON.parse(d)))}).on('error',reject)})}
function putJson(path){return new Promise((resolve,reject)=>{const req=http.request({host:'127.0.0.1',port:9224,path,method:'PUT'},res=>{let d='';res.on('data',c=>d+=c);res.on('end',()=>resolve(JSON.parse(d)))});req.on('error',reject);req.end();})}
function send(ws, method, params={}){return new Promise((resolve,reject)=>{const id=++send.id;ws.send(JSON.stringify({id,method,params}));const onMsg=(ev)=>{const msg=JSON.parse(ev.data);if(msg.id===id){ws.removeEventListener('message',onMsg);msg.error?reject(new Error(JSON.stringify(msg.error))):resolve(msg.result)}};ws.addEventListener('message',onMsg)})} send.id=0;
(async()=>{
  const tabInfo = await putJson('/json/new?http://127.0.0.1:5175/resource-dispatch%3Fcdp-check%3D1');
  const ws = new WebSocket(tabInfo.webSocketDebuggerUrl);
  await new Promise(resolve=>ws.addEventListener('open',resolve,{once:true}));
  await send(ws,'Runtime.enable'); await send(ws,'Page.enable');
  const logs=[]; ws.addEventListener('message', ev=>{const msg=JSON.parse(ev.data); if(msg.method==='Runtime.consoleAPICalled') logs.push({type:msg.params.type,args:msg.params.args.map(a=>a.value||a.description).join(' ')}); if(msg.method==='Runtime.exceptionThrown') logs.push({type:'exception',args:msg.params.exceptionDetails.text});});
  await new Promise(r=>setTimeout(r,3000));
  const seed = `(() => {
    const event = {
      forefireResult: { area: 8.1, geojson: { type:'FeatureCollection', features:[{ type:'Feature', properties:{elapsed_seconds:4320}, geometry:{ type:'Polygon', coordinates:[[[101.255,28.522],[101.264,28.542],[101.286,28.539],[101.292,28.519],[101.274,28.509],[101.255,28.522]]] } }] } },
      agentResult: { packages: {
        route_package: { entry_point:{name:'高风险目标入口点', longitude:101.269444, latitude:28.530278}, assembly_point:{name:'南侧安全集结点', longitude:101.264, latitude:28.515}, route_options:[
          {id:'main_evacuation', name:'主疏散路线', risk:'low', distance_km:3.2, eta_min:8, color:'#22c55e', coordinates:[[101.269444,28.530278],[101.267,28.526],[101.264,28.515]], elevation_profile:[{distance_km:0,elevation_m:3000},{distance_km:1.4,elevation_m:2860},{distance_km:3.2,elevation_m:2740}]},
          {id:'rescue_approach', name:'消防救援接近路线', risk:'medium', distance_km:4.1, eta_min:12, color:'#f59e0b', coordinates:[[101.269444,28.530278],[101.278,28.526],[101.281,28.517],[101.264,28.515]]},
          {id:'safe_route', name:'安全路径', risk:'low', distance_km:3.8, eta_min:10, color:'#38bdf8', coordinates:[[101.269444,28.530278],[101.260,28.527],[101.258,28.518],[101.264,28.515]]}
        ]},
        resource_package: { dispatch_tasks:[{action:'A区增援', source_point:{longitude:101.245,latitude:28.505}, target_point:{longitude:101.264,latitude:28.526}, color:'#f59e0b'}] }
      }, input_summary:{final_area_km2:8.1,risk_level:'high'}, recommended_plan:{name:'PLAN-A'}, warnings:[] },
      agentMessages:[], updatedAt:new Date().toISOString()
    };
    localStorage.setItem('fire-command-active-event', JSON.stringify(event));
  })()`;
  await send(ws,'Runtime.evaluate',{expression:seed, awaitPromise:true});
  async function inspect(url){
    await send(ws,'Page.navigate',{url});
    await new Promise(r=>setTimeout(r,12000));
    const res=await send(ws,'Runtime.evaluate',{expression:`(() => { const cvs=[...document.querySelectorAll('canvas')].map(c=>{const r=c.getBoundingClientRect();return {w:Math.round(r.width),h:Math.round(r.height),cls:String(c.className||'')}}); const txt=document.body.innerText; return {url:location.href, canvas:cvs, text:txt.slice(0,1200), hasCanvas:cvs.some(c=>c.w>100&&c.h>100)}; })()`, returnByValue:true});
    return res.result.value;
  }
  const resource = await inspect('http://127.0.0.1:5175/resource-dispatch?cdp-seeded=1');
  const route = await inspect('http://127.0.0.1:5175/emergency-route?cdp-seeded=1');
  console.log(JSON.stringify({resource, route, logs:logs.slice(-50)}, null, 2));
  ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
