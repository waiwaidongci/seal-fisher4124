import {DOMAIN} from './constants/domain.js';
import {LEAK_DOMAIN} from './constants/leak.js';
import {post} from './api/client.js';
import {store,load} from './stores/research.js';
import {leakStore,loadLeak} from './stores/leak.js';
import {pages,PAGES_WITH_ID} from './router/index.js';
import {bindForm} from './hooks/forms.js';
const app=document.getElementById('app');let active=false;
const NAV=[
  ['overview','研究总览','seal'],['data','来源录入','seal'],['analysis','分析执行','seal'],
  ['results','结果档案','seal'],['review','业务复核','seal'],['audit','操作留痕','seal'],
  ['leak-rolls','卷材与试件','leak'],['leak-rounds','校准/盲验轮','leak'],
  ['leak-round','研究轮详情','leak'],['leak-jobs','漏封任务','leak'],
];
function login(){app.innerHTML=`<div class="login"><section><div class="eyebrow">${DOMAIN.slug.toUpperCase()} + ${LEAK_DOMAIN.slug.toUpperCase()} / RESEARCH NOTES</div><h1>${DOMAIN.title}<br><span style="font-size:.62em">${LEAK_DOMAIN.title}</span></h1><p class="lead">${DOMAIN.scenario}</p><div class="method-note">${LEAK_DOMAIN.note}</div><small>合成数据研究演示 · 双业务域 · Python 实算</small></section><form id="login-form"><h2>进入研究工作席</h2><label>账号<input name="email" type="email" value="admin@demo.local" required></label><label>密码<input name="password" type="password" value="Research2026!" required></label><button type="submit">登录 →</button><p>负责人 admin / 分析师 analyst / 观察员 viewer<br>后缀 @demo.local · 密码 Research2026!</p><div id="notice" role="alert"></div></form></div>`;bindForm('login-form',async data=>{const x=await post('/auth/login',data);localStorage.setItem('research-token',x.token);localStorage.setItem('research-role',x.role);localStorage.setItem('research-email',x.email);await boot();});}
async function render(){if(active)return;active=true;try{const [key='overview',id]=location.hash.slice(1).split('/'),page=pages[key]||pages.overview;
const navHtml=`<div class="nav-group"><small>包装试封 Fisher 研究（旧研究照常）</small><nav>${NAV.filter(n=>n[2]==='seal').map(([k,v])=>`<a class="${key===k?'active':''}" href="#${k}">${v}</a>`).join('')}</nav></div><div class="nav-group"><small>漏封仪分界校准 / 盲验</small><nav>${NAV.filter(n=>n[2]==='leak').map(([k,v])=>k==='leak-round'?`<a class="${key===k?'active':''}" href="#${k}/${id||''}">${v}</a>`:`<a class="${key===k?'active':''}" href="#${k}">${v}</a>`).join('')}</nav></div>`;
app.innerHTML=`<header><a class="brand" href="#overview">${DOMAIN.title.slice(0,2)} <span>${DOMAIN.slug} + ${LEAK_DOMAIN.slug}</span></a><div class="nav-wrap">${navHtml}</div><button id="logout" class="text">${localStorage.getItem('research-role')} · 退出</button></header><main id="content"><p>读取业务数据…</p></main><footer>RESEARCH NOTES / ${DOMAIN.id} + ${LEAK_DOMAIN.id} <span>合成数据 · 源记录快照 · 可复现核算 · 盲验封存</span></footer><div id="notice" role="alert"></div>`;
const content=PAGES_WITH_ID.has(key)?await page.render(id):await page.render();
document.getElementById('content').innerHTML=content;page.bind(()=>render(),id);document.getElementById('logout').onclick=()=>{localStorage.clear();login();};}catch(e){document.getElementById('notice').textContent=e.message;}finally{active=false;}}
async function boot(){if(!localStorage.getItem('research-token'))return login();try{await Promise.all([load(),loadLeak()]);await render();}catch(e){login();document.getElementById('notice').textContent=e.message;}}
window.addEventListener('hashchange',()=>render());
setInterval(async()=>{
  if(!localStorage.getItem('research-token'))return;
  const [key,id]=location.hash.slice(1).split('/');
  if(key==='results' && store.runs.some(r=>r.id===store.runId && ['queued','running'].includes(r.status))){await load();await render();}
  if(key==='leak-round'||key==='leak-jobs'){await loadLeak();if(leakStore.jobs.some(j=>['queued','running'].includes(j.status)))await render();}
},2000);boot();
