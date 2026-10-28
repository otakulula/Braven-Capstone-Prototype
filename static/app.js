const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const get=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d}catch{return d}};
const put=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
const api=async(u,o)=>(await fetch(u,o)).json();
let match=get("match",null),quest=get("quest",{});

function go(n){
  $$(".view").forEach((v,i)=>v.hidden=i!==n-1);
  $$("#stepper li").forEach((li,i)=>{li.classList.toggle("on",i===n-1);li.classList.toggle("done",i<n-1)});
  scrollTo(0,0);
}

async function initQuiz(){
  const qs=await api("/api/questions");
  $("#quiz").innerHTML=qs.map(q=>`<fieldset><legend>${q.label}</legend>`+(q.type==="scale"
    ?q.items.map(([k,l])=>`<div class="scale"><span>${l}</span><div>${[1,2,3,4,5].map(n=>`<label><input type="radio" name="comfort.${k}" value="${n}" required><b>${n}</b></label>`).join("")}</div></div>`).join("")
    :`<div class="pills">${q.options.map(([v,l])=>`<label><input type="${q.type==="multi"?"checkbox":"radio"}" name="${q.id}" value="${v}" ${q.type==="single"?"required":""}><span>${l}</span></label>`).join("")}</div>`)+"</fieldset>").join("");
}

function collect(){
  const a={challenges:[],comfort:{}};
  for(const [k,v] of new FormData($("#quiz"))){
    if(k==="challenges")a.challenges.push(v);
    else if(k.startsWith("comfort."))a.comfort[k.slice(8)]=+v;
    else a[k]=v;
  }
  return a;
}

$("#demo").onclick=()=>{
  const d={goal:"internship",field:"tech",challenges:["networking","confidence"],time:"medium",format:"virtual","comfort.networking":"1","comfort.coaching":"2","comfort.resume":"3"};
  $$("#quiz input").forEach(i=>{const v=d[i.name];i.checked=Array.isArray(v)?v.includes(i.value):v===i.value});
};

$("#quiz").onsubmit=async e=>{
  e.preventDefault();
  match=await api("/api/match",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(collect())});
  put("match",match);renderResults();go(2);
};

function renderResults(){
  const p=match.primary;
  $("#results").innerHTML=`<div class="card hero"><span class="tag">Your best match</span>
    <h2>${p.icon} ${p.title}</h2><p>${p.blurb}</p>
    <h3>Why this fits you</h3><ul>${match.why.map(w=>`<li>${w}</li>`).join("")}</ul>
    <p class="note">You don't have to just show up. We'll get you ready in ${p.steps-1} small quests first.</p>
    <button class="btn gold" id="open">Open my path</button></div>
    <h3>Also in the library</h3><div class="grid">${match.others.map(o=>`<div class="card dim"><h4>${o.icon} ${o.title}</h4><p>${o.blurb}</p><small>Path coming soon</small></div>`).join("")}</div>`;
  $("#open").onclick=()=>{renderQuest(p.id);go(3)};
}

const evHTML=e=>`<dl class="ev">${Object.entries(e).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;

function stepHTML(t){
  let b=`<span class="tag">${t.type==="boss"?"Final boss":"Quest"}</span><h2>${t.title}</h2><p>${t.text}</p>`;
  if(t.type==="read")b+=`<ul>${t.items.map(i=>`<li>${i}</li>`).join("")}</ul>`;
  if(t.type==="write")b+=`<textarea id="inp" rows="4" aria-label="${t.title}"></textarea>`;
  if(t.type==="pick")b+=t.options.map(o=>`<label class="opt"><input type="radio" name="pick" value="${o}"> ${o}</label>`).join("")+`<textarea id="inp" rows="2" placeholder="Or write your own"></textarea>`;
  if(t.type==="confirm")b+=evHTML(t.event)+`<label class="opt"><input type="checkbox" id="chk"> I've checked the date, time and format</label>`;
  if(t.type==="boss")b+=evHTML(t.event);
  const label={read:"Got it",write:"Save intro",pick:"Save question",confirm:"Looks good",decide:"I'm ready",boss:"Register and show up"}[t.type];
  return b+`<div class="row"><button class="btn ${t.type==="boss"?"gold":""}" id="next">${label}</button>${t.type==="decide"?`<button class="btn ghost" id="later">Not yet</button>`:""}</div><p id="tip" class="note"></p>`;
}

const check={
  write:()=>{const v=$("#inp").value.trim();return v.length>=20?v:(alert("Add a little more. A couple of sentences is plenty."),null)},
  pick:()=>{const c=$("input[name=pick]:checked");return $("#inp").value.trim()||c?.value||(alert("Pick a question or write your own."),null)},
  confirm:()=>$("#chk").checked||(alert("Tick the box once you've checked the details."),null)
};

async function renderQuest(id){
  const r=await api("/api/resource/"+id),s=quest[id]??={done:0,data:{}},n=r.quest.length,cur=s.done;
  const map=r.quest.map((t,i)=>`<li class="${i<cur?"done":i===cur?"now":""}"><i>${i<cur?"✓":i===n-1?"★":i+1}</i>${t.title}</li>`).join("");
  const body=cur>=n
    ?`<div class="card hero"><h2>🏆 Boss defeated!</h2><p>You're registered and prepared. Your intro:</p><blockquote id="mine"></blockquote><p class="note">Next: pick another resource and start its path.</p></div>`
    :`<div class="card">${stepHTML(r.quest[cur])}</div>`;
  $("#quest").innerHTML=`<h2>${r.icon} ${r.title}</h2><div class="bar" role="progressbar" aria-valuenow="${cur}" aria-valuemax="${n}"><i style="width:${cur/n*100}%"></i></div><ul class="map">${map}</ul>${body}`;
  if(cur>=n){$("#mine").textContent=s.data.intro||"";return}
  const t=r.quest[cur];
  if(t.type==="write")$("#inp").value=s.data[t.id]||t.template;
  if($("#later"))$("#later").onclick=()=>$("#tip").textContent="That's fine. Come back when you've said your intro out loud once more.";
  $("#next").onclick=()=>{
    const v=check[t.type]?check[t.type]():true;
    if(v===null||v===undefined)return;
    s.data[t.id]=v;s.done++;put("quest",quest);renderQuest(id);
  };
}

$("#reset").onclick=e=>{e.preventDefault();localStorage.clear();location.reload()};
initQuiz();
