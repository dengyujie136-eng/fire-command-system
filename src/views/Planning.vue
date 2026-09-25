<template>
<main class="planning">
  <aside class="control">
    <header><small>TEAM → TARGET</small><h1>消防队路径与资源规划</h1><p>{{ incident.eventName }} · 演练点位</p></header>
    <p class="notice">消防队起点可随机生成或点击地图设置；任务目标依据当前推演火线推荐，也可手动补充。路径由 A* 在演示网格计算，不代表真实道路导航。</p><div class="spread-source" v-if="spreadRunId"><b>火势推演 {{ spreadRunId }}</b><span>预测过火 {{ spreadArea.toFixed(3) }} km² · 最大半径 {{ spreadRadius.toFixed(2) }} km</span></div><p v-else class="alert">尚无火势推演结果；请先到推演页运行模型。</p>
    <section><div class="title"><h2>消防队起点</h2><b>{{ teams.length }} 支</b></div>
      <div class="actions"><button @click="generateTeams(4)">随机生成 4 支</button><button @click="pick('team')">地图增加队伍</button></div>
      <div v-for="(item,index) in teams" :key="item.id" class="row"><i class="team"></i><span>消防队 {{ index+1 }}<small>{{ coord(item) }}</small></span><button @click="remove('team',index)">×</button></div>
    </section>
    <section><div class="title"><h2>灭火任务目标</h2><b>{{ targets.length }} 处</b></div>
      <div class="actions"><button :disabled="!hasSubmittedFireline" @click="recommendTargets">按已提交火线推荐</button><button @click="pick('target')">地图增加目标</button></div>
      <div v-for="(item,index) in targets" :key="item.id" class="row"><i class="target"></i><span>{{ item.label || "目标 "+(index+1) }}<small>{{ coord(item) }} · {{ item.source || "人工标记" }}</small></span><button @click="remove('target',index)">×</button></div>
      <p v-if="!targets.length">请在地图上添加目标。</p>
    </section>
    <div v-if="shortage" class="alert">目标多于队伍 {{ shortage }} 处，需要增派 {{ shortage }} 支救援力量。<button @click="addReserves">增派队伍</button></div>
    <div v-if="targets.length && teams.length>targets.length" class="spare">多出的 {{ teams.length-targets.length }} 支队伍将作为协同增援，分配到最近目标。</div>
    <p v-if="unsafeTeamIndices.length" class="alert">队伍 {{ unsafeTeamIndices.map(index=>index+1).join('、') }} 位于推演火场范围内，请重新生成或在地图上移动到火线外。</p>
    <p v-if="unsafeTargetIndices.length" class="alert">目标 {{ unsafeTargetIndices.map(index=>index+1).join('、') }} 位于火场禁行范围内，请将目标放到火线外围接近点。</p>
    <button class="primary" :disabled="busy||!hasSubmittedFireline||!teams.length||!targets.length||unsafeTeamIndices.length>0||unsafeTargetIndices.length>0" @click="plan">{{ busy?'计算中…':'生成队伍到目标的路径' }}</button>
    <p v-if="error" class="alert">{{ error }}</p>
  </aside>
  <div class="map-area">
    <CesiumMap ref="mapRef" :longitude="center[0]" :latitude="center[1]" :height="85000" :scene-id="incident.eventId" :show-wind-field="false" />
    <div class="map-hint">{{ mode==='team'?'点击地图放置消防队':mode==='target'?'点击地图放置目标':'绿色为消防队 · 橙色为目标 · 彩色线为路径' }} <button v-if="mode" @click="cancel">取消</button></div>
    <div class="map-foot">橙色范围为 {{ spreadRunId ? "推演火线 " + spreadRunId : "待推演" }} · 路径为演示网格</div>
  </div>
  <Teleport defer to="#business-panel"><aside class="results">
    <header><small>ROUTE OUTPUT</small><h2>路径与补给</h2><p>火线来自最新推演 {{ spreadRunId || "未生成" }}；真实行动需要核实道路、地形、封路和队伍位置。</p></header><button v-if="scenarioAwaiting" class="primary" :disabled="busy" @click="confirmScenario">确认演练场景并运行资源与路径工作流</button>
    <div class="counts"><span>队伍 <b>{{ teams.length }}</b></span><span>目标 <b>{{ targets.length }}</b></span><span>路线 <b>{{ plans.length }}</b></span></div>
    <div v-if="terrainStatus" class="spread-source"><b>{{ terrainStatus.available?'Copernicus DEM 地形成本已启用':'DEM 未参与本次规划' }}</b><span>{{ terrainStatus.available?'分辨率 '+terrainStatus.resolution_m?.join('×')+' m · 已采样 '+terrainStatus.sampled_points+' 个节点 · 真实道路尚未接入':terrainStatus.reason }}</span></div>
    <p v-if="!plans.length">点击“生成路径”后在这里查看计算结果。</p>
    <article v-for="(item,index) in plans" :key="index"><strong>消防队 {{ item.team_index+1 }} → 目标 {{ item.target_index+1 }} · {{ item.assignment_role==='reinforcement'?'协同增援':'主责' }}</strong><b>{{ item.route.success ? Number(item.route.distance_km).toFixed(2)+' km · '+Number(item.route.estimated_travel_time_minutes).toFixed(1)+' 分钟' : '不可达' }}</b><small>风险值 {{ item.route.success ? Number(item.route.risk_score).toFixed(2) : '--' }} · 火线避障 A*</small><small v-if="item.access_mode==='dismounted_approach'" class="access-warning">车辆坡度不可达 · 已切换消防员徒步接近</small><button class="explain-button" :disabled="explainingIndex===index||!item.route.success" @click="explainRoute(item,index)">{{ explainingIndex===index?'千问分析中…':'调用千问解释绕行' }}</button><div v-if="routeExplanations[index]" class="route-explanation"><b>{{ routeExplanations[index].used_remote?'千问路线解释':'结构化降级说明' }}</b><p>{{ routeExplanations[index].explanation }}</p><small>{{ routeExplanations[index].provider }} · {{ routeExplanations[index].model }}<template v-if="routeExplanations[index].evidence"> · 直线 {{ Number(routeExplanations[index].evidence.direct_distance_km).toFixed(2) }} km · 绕行倍率 {{ Number(routeExplanations[index].evidence.detour_ratio).toFixed(2) }}</template></small></div></article>
    <p v-if="unassigned.length" class="alert">目标 {{ unassigned.map((x:number)=>x+1).join('、') }} 尚无队伍，请增派。</p>
    <section><h3>演练资源库存</h3><p>已移除无人机；不代表真实库存。</p><div v-for="item in resources" :key="item.resource_type" class="resource"><span>{{ resourceName(item.resource_type) }}</span><b>{{ item.quantity }}</b></div><p v-if="!resources.length">暂无线下库存数据。</p><p v-if="inventoryShortage" class="alert">当前演练库存的灭火队伍少于地图起点 {{ inventoryShortage }} 支，请核实或补充队伍。</p></section>
    <section><h3>水与食物需求</h3><div v-for="(item,index) in teams" :key="item.id" class="supply"><b>队 {{ index+1 }}</b><label>水 L <input v-model.number="item.water" type="number" min="0"></label><label>食品 <input v-model.number="item.food" type="number" min="0"></label></div><p>合计 {{ waterTotal }} L 水 · {{ foodTotal }} 份食品；仅记录需求，尚未配送。</p></section>
  </aside></Teleport>
</main>
</template>
<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import CesiumMap from '../components/CesiumMap.vue'
import {planningAPI} from '../api/modules'
import {useIncidentContextStore} from '../stores/incidentContextStore'
import {useFireEventStore} from '../stores/fireEventStore'
type Point={id:string;longitude:number;latitude:number;water:number;food:number;label?:string;source?:string}
type Plan={team_index:number;target_index:number;assignment_role?:'primary'|'reinforcement';access_mode?:'vehicle'|'dismounted_approach';route:any}
const incident=useIncidentContextStore(),route=useRoute()
const fireEvent=useFireEventStore()
const mapRef=ref<InstanceType<typeof CesiumMap>|null>(null)
const teams=ref<Point[]>([]),targets=ref<Point[]>([]),plans=ref<Plan[]>([]),unassigned=ref<number[]>([])
const explainingIndex=ref<number|null>(null),routeExplanations=ref<Record<number,any>>({})
const terrainStatus=ref<any>(null)
const mode=ref<'team'|'target'|null>(null),busy=ref(false),error=ref('')
const center=computed<[number,number]>(()=>{const p=incident.workflow?.artifacts?.confirmed_point?.coordinates;return Array.isArray(p)&&p.length===2?[Number(p[0]),Number(p[1])]:incident.selectedEvent?.center||[-121.38,39.87]})
const shortage=computed(()=>Math.max(0,targets.value.length-teams.value.length))
const submittedFireline=computed(()=>fireEvent.submittedFireline)
const hasSubmittedFireline=computed(()=>Boolean(submittedFireline.value?.spreadRunId))
const spreadRunId=computed(()=>submittedFireline.value?.spreadRunId || '')
const spreadArea=computed(()=>Number(submittedFireline.value?.finalAreaKm2||0))
const spreadRadius=computed(()=>Number(submittedFireline.value?.maxRadiusKm||0))
const scenarioAwaiting=computed(()=>hasSubmittedFireline.value && incident.workflow?.current_stage==='scenario' && incident.workflow?.status==='WAITING_FOR_INPUT')
const fireFront=computed(()=>submittedFireline.value?.finalGeojson || submittedFireline.value?.geojson || null)
const resources=computed<any[]>(()=>((incident.workflow?.scenario?.resources||[]) as any[]).filter(x=>x.resource_type!=='uav'))
const inventoryShortage=computed(()=>{const count=Number(resources.value.find(x=>x.resource_type==='fire_team')?.quantity);return Number.isFinite(count)?Math.max(0,teams.value.length-count):0})
const waterTotal=computed(()=>teams.value.reduce((n,x)=>n+Math.max(0,Number(x.water)||0),0))
const foodTotal=computed(()=>teams.value.reduce((n,x)=>n+Math.max(0,Number(x.food)||0),0))
function pointInsideRing(item:Point,ring:[number,number][]){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const [xi,yi]=ring[i],[xj,yj]=ring[j];if(((yi>item.latitude)!==(yj>item.latitude))&&(item.longitude<(xj-xi)*(item.latitude-yi)/(yj-yi)+xi))inside=!inside}return inside}
const unsafeTeamIndices=computed(()=>{const ring=latestFireRing()?.ring||[];return ring.length?teams.value.map((item,index)=>pointInsideRing(item,ring)?index:-1).filter(index=>index>=0):[]})
const unsafeTargetIndices=computed(()=>{const ring=latestFireRing()?.ring||[];return ring.length?targets.value.map((item,index)=>pointInsideRing(item,ring)?index:-1).filter(index=>index>=0):[]})
const colors=['#38bdf8','#e879f9','#fbbf24','#34d399','#fb7185']
function point(longitude:number,latitude:number):Point{return{id:crypto.randomUUID(),longitude,latitude,water:0,food:0}}
function coord(p:Point){return p.longitude.toFixed(4)+', '+p.latitude.toFixed(4)}
function resourceName(x:string){return({fire_team:'灭火队伍',fire_engine:'消防车辆',firefighter_unit:'消防单元',medical:'医疗保障',water_supply:'供水保障',evacuation_support:'疏散保障'} as Record<string,string>)[x]||x}
function randomTeam(index:number){
 const angle=(index*137.5+40+Math.random()*25)*Math.PI/180
 const safeRadiusKm=Math.max(4.5,spreadRadius.value+2.5)+Math.random()*2
 const latitudeRadians=center.value[1]*Math.PI/180
 const latitudeOffset=safeRadiusKm/111.32
 const longitudeOffset=safeRadiusKm/Math.max(20,111.32*Math.cos(latitudeRadians))
 return point(center.value[0]+Math.cos(angle)*longitudeOffset,center.value[1]+Math.sin(angle)*latitudeOffset)
}
function invalidate(){plans.value=[];unassigned.value=[];routeExplanations.value={};terrainStatus.value=null;error.value='';void nextTick(draw)}
function generateTeams(n:number){teams.value=Array.from({length:n},(_,i)=>randomTeam(i));invalidate()}
function addReserves(){const n=shortage.value;for(let i=0;i<n;i++)teams.value.push(randomTeam(teams.value.length));invalidate()}
function remove(kind:'team'|'target',index:number){(kind==='team'?teams.value:targets.value).splice(index,1);invalidate()}
function cancel(){mapRef.value?.cancelMapPointSelection();mode.value=null}
function pick(kind:'team'|'target'){mode.value=kind;mapRef.value?.beginMapPointSelection('ADD_RESOURCE_POINT',({longitude,latitude})=>{(kind==='team'?teams.value:targets.value).push(point(longitude,latitude));mode.value=null;invalidate()})}
function featureRings(feature:any):[number,number][][]{
 const geometry=feature?.geometry
 if(geometry?.type==='Polygon')return Array.isArray(geometry.coordinates?.[0])?[geometry.coordinates[0]]:[]
 if(geometry?.type==='MultiPolygon')return (geometry.coordinates||[]).map((polygon:any)=>polygon?.[0]).filter((ring:any)=>Array.isArray(ring))
 return []
}
function latestFireRing():{ring:[number,number][];properties:any}|null{
 const features=(fireFront.value?.features||[]).filter((x:any)=>featureRings(x).some((ring)=>ring.length>=4))
 if(!features.length)return null
 const feature=[...features].sort((a:any,b:any)=>Number(a.properties?.elapsed_minutes||0)-Number(b.properties?.elapsed_minutes||0)).at(-1)
 const ring=(featureRings(feature)[0]||[]).filter((p:any)=>Array.isArray(p)&&p.length>=2).map((p:any)=>[Number(p[0]),Number(p[1])] as [number,number])
 return ring.length>=4?{ring,properties:feature.properties||{}}:null
}
function recommendTargets(){
 const front=latestFireRing()
 if(!front){error.value='没有可用的推演火线，无法按火势推荐目标。';return}
 const points=front.ring.slice(0,-1)
 const intensity=front.properties.sector_fire_intensity_kw_m||[]
 const radius=front.properties.sector_radii_km||[]
 const count=Math.max(2,Math.min(6,Math.ceil(Math.sqrt(Math.max(0.1,Number(front.properties.area_km2||spreadArea.value)))/2)+1))
 const sorted=points.map((p,i)=>({p,i,score:Number(intensity[i]||1)*Number(radius[i]||1)})).sort((a,b)=>b.score-a.score)
 const picked:typeof sorted=[]
 for(const candidate of sorted){
   if(picked.every(other=>Math.min(Math.abs(other.i-candidate.i),points.length-Math.abs(other.i-candidate.i))>=Math.max(2,Math.floor(points.length/count/2))))picked.push(candidate)
   if(picked.length>=count)break
 }
 const c=center.value
 targets.value=picked.map((item,index)=>{
   const x=c[0]+(item.p[0]-c[0])*1.28
   const y=c[1]+(item.p[1]-c[1])*1.28
   return {...point(x,y),label:'火线接近目标 '+(index+1),source:'推演 '+spreadRunId.value}
 })
 invalidate()
}
async function confirmScenario(){busy.value=true;error.value='';try{await incident.confirmScenario({note:'已检查推演目标点，执行演练资源与路径规划'})}catch(e:any){error.value=e?.message||'场景确认失败'}finally{busy.value=false}}
function draw(){const map=mapRef.value;if(!map)return;map.clearDemoEntities()
 const fireFeatures=(fireFront.value?.features||[]).filter((feature:any)=>featureRings(feature).some((ring)=>ring.length>=4))
 const latestFeature=[...fireFeatures].sort((a:any,b:any)=>Number(a.properties?.elapsed_minutes||0)-Number(b.properties?.elapsed_minutes||0)).at(-1)
 featureRings(latestFeature).forEach((ring,index)=>map.addDemoArea({name:`current-fireline-${index+1}`,coordinates:ring,color:'#fb923c',label:index===0?'推演火线':''}))
 teams.value.forEach((p,i)=>map.addDemoPoint({name:'消防队 '+(i+1),position:[p.longitude,p.latitude],color:'#34d399',label:'队'+(i+1),size:14,symbol:'team'}))
 targets.value.forEach((p,i)=>map.addDemoPoint({name:'目标 '+(i+1),position:[p.longitude,p.latitude],color:'#fb923c',label:'目标'+(i+1),size:14,symbol:'target'}))
 plans.value.forEach((x,i)=>{const coords=x.route?.geometry?.coordinates;if(x.route?.success&&Array.isArray(coords)&&coords.length>1)map.addDemoRoute({name:'队伍'+(x.team_index+1)+'→目标'+(x.target_index+1),coordinates:coords,color:colors[i%colors.length],width:4,arrow:true})})
}
async function plan(){
 if(!hasSubmittedFireline.value){error.value='请先在推理页提交火线范围，再进入规划阶段。';return}
 busy.value=true;error.value=''
 try{const c=center.value,ring=latestFireRing()?.ring||[];const response=await fetch('/api/planning/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:incident.eventId,teams:teams.value.map(({longitude,latitude})=>({longitude,latitude})),targets:targets.value.map(({longitude,latitude})=>({longitude,latitude})),fire_center:{longitude:c[0],latitude:c[1]},fire_radius_km:spreadRadius.value,fire_perimeter:ring.map(([longitude,latitude])=>({longitude,latitude}))})});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'路径计算失败 '+response.status);plans.value=data.plans||[];unassigned.value=data.unassigned_target_indices||[];terrainStatus.value=data.terrain||null;await nextTick();draw()}catch(e:any){error.value=e?.message||'路径计算失败'}finally{busy.value=false}}
async function explainRoute(item:Plan,index:number){const team=teams.value[item.team_index],target=targets.value[item.target_index];if(!team||!target)return;explainingIndex.value=index;error.value='';try{const ring=latestFireRing()?.ring||[];routeExplanations.value={...routeExplanations.value,[index]:await planningAPI.explainRoute({event_id:incident.eventId,team_index:item.team_index,target_index:item.target_index,assignment_role:item.assignment_role||'primary',team:{longitude:team.longitude,latitude:team.latitude},target:{longitude:target.longitude,latitude:target.latitude},route:item.route,fire_perimeter:ring.map(([longitude,latitude])=>({longitude,latitude}))})}}catch(e:any){error.value=e?.message||'千问路线解释失败'}finally{explainingIndex.value=null}}
onMounted(async()=>{try{await incident.loadEvents();await incident.loadLatestWorkflow()}catch(e:any){error.value=e?.message||'事件或推演结果读取失败'}generateTeams(4);if(hasSubmittedFireline.value)recommendTargets();else error.value='请先在推理页提交火线范围，再进入规划阶段。';if(route.query.auto_plan==='1'&&targets.value.length)void plan();await nextTick();mapRef.value?.on('load',()=>{mapRef.value?.flyTo({center:center.value,height:85000});draw()})})
watch(()=>incident.eventId,async()=>{teams.value=[];targets.value=[];plans.value=[];try{await incident.loadLatestWorkflow()}catch{}generateTeams(4);if(hasSubmittedFireline.value)recommendTargets()})
watch(()=>fireEvent.submittedSpreadRunId,()=>{targets.value=[];plans.value=[];if(hasSubmittedFireline.value)recommendTargets()})
</script>
<style scoped>
.planning{height:100%;display:grid;grid-template-columns:290px minmax(0,1fr);background:#07131e;color:#eaf5fa;overflow:hidden}.control,.results{min-width:0;min-height:0;overflow:auto;padding:12px;background:#0b1e2b}.control{border-right:1px solid #294657}
header small{color:#5eead4;font-size:10px;font-weight:800}h1{font-size:17px;margin:4px 0}h2,h3{font-size:13px;margin:0}p{color:#a1b9c5;font-size:10px;line-height:1.5}.notice{padding:8px;border-left:3px solid #38bdf8;background:#102b3b}
section{margin:10px 0;padding:9px;border:1px solid #294c5d;border-radius:6px}.title,.row,.resource{display:flex;justify-content:space-between;align-items:center;gap:6px}.title b{color:#5eead4;font-size:10px}.actions{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}
button{padding:5px 7px;border:1px solid #347286;border-radius:5px;background:#114458;color:#e0f7fb;font-size:10px;cursor:pointer}.row{padding:6px 0;border-top:1px solid #244253}.row i{width:9px;height:9px;border-radius:50%;flex:none}.row i.team{background:#34d399}.row i.target{background:#fb923c}.row span{flex:1;font-size:11px}.row small{display:block;color:#8da9b8;font-size:9px}.alert{padding:8px;background:#49311a;color:#fde68a;border-radius:5px}.spare{padding:7px;margin:7px 0;background:#103b32;color:#86efac;border-radius:5px;font-size:10px}.primary{width:100%;min-height:36px;background:#0f766e;border-color:#2dd4bf}.primary:disabled{opacity:.5}
.spread-source{display:grid;gap:4px;padding:8px;background:#123745;border-left:3px solid #fb923c;font-size:10px}.spread-source span{color:#afd0da}
.map-area{position:relative;min-width:0}.map-area :deep(.cesium-map-shell){position:absolute;inset:0}.map-hint,.map-foot{position:absolute;z-index:5;left:10px;padding:8px;background:#071723e8;border:1px solid #31566a;border-radius:5px;font-size:10px}.map-hint{top:10px}.map-foot{bottom:10px}
.results{height:100%}.counts{display:flex;justify-content:space-between;margin:10px 0;padding:8px;background:#123241;font-size:10px}.counts b{display:block;font-size:16px}.results article{display:grid;gap:5px;margin:7px 0;padding:8px;border:1px solid #286778;border-radius:5px;background:#102b3a;font-size:11px}.results article b{color:#5eead4}.results article small{color:#96b5c3}.resource{padding:5px 0;border-top:1px solid #244253;font-size:10px}.supply{display:flex;gap:5px;align-items:center;padding:5px 0;font-size:10px}.supply input{width:43px;background:#0b2534;color:white;border:1px solid #31566a}
.explain-button{justify-self:start;margin-top:2px}.route-explanation{display:grid;gap:4px;padding:7px;border-left:3px solid #38bdf8;background:#0a2130}.route-explanation p{margin:0;color:#d9edf3;font-size:10px}.route-explanation>b{font-size:10px;color:#7dd3fc}
.access-warning{padding:5px;background:#49311a;color:#fde68a!important;border-radius:4px}
@media(max-width:900px){.planning{grid-template-columns:230px minmax(0,1fr)}}@media(max-width:640px){.planning{height:auto;overflow:auto;grid-template-columns:1fr}.map-area{height:55vh;min-height:400px}}
</style>
