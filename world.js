/* ===== Emmavengers World =====
   The app home is a world map shaped like Africa. Each land opens its own inner map; each place on it is an activity.
   Everything (lands, places, cards, voice lines, map art, music theme) comes from lands.json, so new lands, places,
   letters, animals or countries can be added there without touching code. Activity types: link (existing game screens:
   house / bible / morning), cards (tap-to-learn deck), quiz (letter | pic | flag), count (count objects 1-10).
   After editing lands.json: generate voice clips for new lines (tools/check_voice.py + tools/gen_voice.py) and run
   python3 tools/build_sw.py so phones get the update offline. */
let LANDS=null,curLand=null,worldGreeted=false;
const WORLD_SCREENS=['land','wcards','wquiz','wcount','wreward'];
const landById=id=>LANDS&&LANDS.lands.find(l=>l.id===id);
const placeById=(L,id)=>L&&L.places.find(p=>p.id===id);
const wDeck=id=>LANDS.decks[id];
function wSave(){try{return JSON.parse(localStorage.getItem('emmaWorld')||'{}')}catch(e){return{}}}
function wPut(s){try{localStorage.setItem('emmaWorld',JSON.stringify(s))}catch(e){}}
const wFill=(t,it)=>t.replace(/\{(\w+)\}/g,(_,k)=>k==='lname'?String(it.name).toLowerCase():k==='word'?String(it.word).toLowerCase():(it[k]!=null?it[k]:''));
const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
/* every line the world can speak (used by tools/check_voice.py to find clips that still need generating) */
function worldVoice(){const S=[],A=x=>(Array.isArray(x)?x:[x]).forEach(t=>t&&S.push(t));if(!LANDS)return S;
 A(LANDS.world.intro);
 LANDS.lands.forEach(L=>{A(L.intro);L.places.forEach(p=>{A(p.intro);
  if(p.type==='quiz')wDeck(p.deck).items.filter(it=>it.hunt!==false).forEach(it=>A(wFill(p.ask,it)));
  if(p.type==='count')wDeck(p.objects).items.forEach(o=>A(o.ask))})});
 Object.values(LANDS.decks).forEach(d=>{A(d.done);(d.items||[]).forEach(it=>A(it.say))});
 A(['Great job! Level complete!','Amen!']);return [...new Set(S)]}
window.__worldVoice=worldVoice;

/* --- Android / browser back: activity -> land -> world map -> exit. One guard entry while away from the map. --- */
let hGuard=false,hIgnore=false;
try{history.replaceState({emma:'root'},'')}catch(e){}
function histSync(s){try{if(s==='home'){if(hGuard){hGuard=false;hIgnore=true;history.back()}}else if(!hGuard){history.pushState({emma:'in'},'');hGuard=true}}catch(e){}}
addEventListener('popstate',()=>{if(hIgnore){hIgnore=false;return}hGuard=false;
 const pn=document.querySelector('#ppanel,#vpanel,.pop');if(pn){pn.remove();if(screen!=='home')histSync(screen);return}
 if(screen!=='home')$('#backBtn').click()});

/* --- map sizing: the 9:16 map fills the space under the header without overflowing --- */
function fitMap(){const m=$('#wmap');if(!m)return;const cs=getComputedStyle(main);
 const top=m.offsetTop-main.offsetTop,avH=main.clientHeight-top-parseFloat(cs.paddingBottom)-10,avW=main.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);
 const w=Math.max(160,Math.min(avW,avH*9/16));m.style.width=w+'px';m.style.height=(w*16/9)+'px'}
addEventListener('resize',fitMap);

/* --- World map (home) --- */
function home(){curLand=null;state={};if(!LANDS){go('house');return}const W=LANDS.world;$('#title').textContent=W.title;
 main.innerHTML=`<div class="wmap world" id="wmap" style="background-image:url('${W.img}')">${LANDS.lands.map(L=>
  `<button class="wland" data-l="${L.id}" aria-label="${esc(L.name)}" style="left:${L.x}%;top:${L.y}%;width:${L.w}%;height:${L.h}%"></button>`).join('')}${LANDS.lands.map(L=>
  `<button class="wsignb" data-l="${L.id}" style="left:${L.sx}%;top:${L.sy}%"><span class="wsign" style="--c:${L.color}">${esc(L.name)}</span></button>`).join('')}<button class="say wsay" aria-label="Read aloud">🔊</button></div>`;
 fitMap();
 main.querySelector('.wsay').onclick=()=>say(W.intro);
 main.querySelectorAll('[data-l]').forEach(b=>b.onclick=()=>{sfx.tap();go('land',{id:b.dataset.l})});
 if(!worldGreeted){worldGreeted=true;say(W.intro)}
 setTimeout(()=>{if(screen==='home')warmVoice(LANDS.lands.map(L=>L.intro))},500)}

/* --- A land's inner map: places are tappable; "Back to Map" returns to the world map --- */
function land(a){const L=landById((a&&a.id)||curLand);if(!L){go('home');return}curLand=L.id;state={land:L.id};$('#title').textContent=L.name;
 const best=wSave().best||{};
 main.innerHTML=`<button class="btn wback" id="wback">Back to Map</button><div class="wmap" id="wmap" style="background-image:url('${L.img}')">${L.places.map(p=>{const st=best[p.id];
  return `<button class="wplace" data-p="${p.id}" style="left:${p.x}%;top:${p.y}%" aria-label="${esc(p.name)}"><span class="ic">${p.photo?`<i style="background-image:url('${p.icon}');background-position:${p.pos||'center'}"></i>`:`<img src="${p.icon}" alt="">`}</span><span class="wsign" style="--c:${L.color}">${esc(p.name)}</span>${st?`<span class="wst">${'⭐'.repeat(st)+'☆'.repeat(3-st)}</span>`:''}</button>`}).join('')}<button class="say wsay" aria-label="Read aloud">🔊</button></div>`;
 fitMap();
 $('#wback').onclick=()=>{sfx.tap();go('home')};
 main.querySelector('.wsay').onclick=()=>say(L.intro);
 main.querySelectorAll('.wplace').forEach(b=>b.onclick=()=>{sfx.tap();openPlace(L,placeById(L,b.dataset.p))});
 say(L.intro);
 setTimeout(()=>{if(screen==='land')warmVoice(L.places.flatMap(p=>[p.intro,...(p.deck?wDeck(p.deck).items.slice(0,4).flatMap(it=>it.say.slice(0,2)):[])]).filter(Boolean))},600)}
function openPlace(L,p){if(!p)return;const a={l:L.id,p:p.id};
 if(p.type==='link'){go(p.go);return}
 if(p.type==='cards')go('wcards',a);else if(p.type==='quiz')go('wquiz',a);else if(p.type==='count')go('wcount',a)}

/* --- cards: tap a tile to open its big card (voice + 3D picture). First look at each card = 1 star. --- */
const LCOL=['#e8261c','#2f86e8','#1f8a2b','#ff8c00','#a855f7','#e83e8c'];
const wThumb=u=>u.replace("img/world/","img/world/thumbs/");
const TI=u=>`data-src="${wThumb(u)}" data-fb="${u}"`;
function tileHTML(k,it,i,seen){const s=seen.has(String(it.id||it.n))?' seen':'';const id=esc(it.id||it.n);
 if(k==='letter')return `<button class="wtile${s}" data-i="${i}" aria-label="${id}" style="--lc:${LCOL[i%6]}"><b class="lt">${it.id}</b><img ${TI(it.img)} alt=""></button>`;
 if(k==='number')return `<button class="wtile${s}" data-i="${i}" aria-label="${id}" style="--lc:${LCOL[i%6]}"><b class="lt">${it.n}</b><img ${TI(it.img)} alt=""></button>`;
 if(k==='country')return `<button class="wtile${s}" data-i="${i}"><img ${TI(it.flag)} alt=""><span>${esc(it.name)}</span></button>`;
 return `<button class="wtile${s}" data-i="${i}"><img ${TI(it.img)} alt=""><span>${esc(it.name)}</span></button>`}
function cardHTML(k,it){
 if(k==='letter'){const w=it.show||`<b>${it.word[0]}</b>${it.word.slice(1)}`;return `<div class="big">${it.id}<small>${it.id.toLowerCase()}</small></div><img class="hero" src="${it.img}" alt="${esc(it.word)}"><div class="wword">${it.id==='X'?`X is at the end of ${w}`:`${it.id} is for ${w}`}</div>`}
 if(k==='number')return `<div class="big">${it.n}</div><div class="objs">${Array.from({length:it.n},(_,j)=>`<img src="${it.img}" alt="" style="animation-delay:${(.25+j*.32).toFixed(2)}s">`).join('')}</div><div class="wword">${it.word}</div>`;
 if(k==='animal')return `<img class="hero" src="${it.img}" alt="${esc(it.name)}"><div class="wword"><b>${esc(it.name)}</b></div><div class="fact">${esc(it.fact)}</div>`;
 if(k==='country')return `<img class="flag" src="${it.flag}" alt="Flag of ${esc(it.name)}"><div class="wword"><b>${esc(it.name)}</b></div><div class="greet">${esc(it.greeting)}</div><div class="fact">"${esc(it.meaning)}" in ${esc(it.language)}</div><div class="frow"><img class="food" src="${it.foodImg}" alt=""><span>${esc(it.food)}</span></div>`;
 return `<img class="hero" src="${it.img}" alt=""><div class="wword"><b>${esc(it.name)}</b></div><div class="fact">${esc(it.text||'')}</div>`}
function wcards(a){const L=landById(a.l),p=placeById(L,a.p),D=wDeck(p.deck);curLand=L.id;state={land:L.id,place:p.id};$('#title').textContent=p.name;
 const sv=wSave(),seen=new Set(((sv.seen||{})[p.deck])||[]);
 main.innerHTML=`<div class="prompt"><span>${esc(p.intro)}</span><button class="say" aria-label="Read aloud">🔊</button></div><div class="wprog">⭐ <b id="wseen">${seen.size}</b> / ${D.items.length}</div><div class="wgrid k-${D.kind}">${D.items.map((it,i)=>tileHTML(D.kind,it,i,seen)).join('')}</div>`;
 bindSay(p.intro);showShelfImgs();
 main.querySelectorAll('.wtile').forEach(b=>b.onclick=()=>{sfx.tap();showWCard(D,p,+b.dataset.i)});
 setTimeout(()=>{if(screen==='wcards')warmVoice([...D.items.slice(0,3).flatMap(it=>it.say),...D.items.slice(3).map(it=>it.say[0])])},800)}
function showWCard(D,p,i){document.querySelectorAll('.pop').forEach(x=>x.remove());const it=D.items[i],key=String(it.id||it.n);setTimeout(()=>warmVoice(D.items.slice(i+1,i+3).flatMap(x=>x.say)),1500);
 const sv=wSave();sv.seen=sv.seen||{};const seen=new Set(sv.seen[p.deck]||[]);const fresh=!seen.has(key);
 const d=document.createElement('div');d.className='pop wpop';
 d.innerHTML=`<div class="wcard k-${D.kind}">${cardHTML(D.kind,it)}<div class="row"><button class="say" aria-label="Read aloud">🔊</button><button class="btn" id="wnext">Next ➜</button><button class="btn" id="wdone">Done ✓</button></div></div>`;
 document.body.appendChild(d);
 let lines=it.say.slice();
 if(fresh){seen.add(key);sv.seen[p.deck]=[...seen];wPut(sv);stars++;setScore();const t=main.querySelector(`.wtile[data-i="${i}"]`);if(t){t.classList.add('seen');const r=t.getBoundingClientRect();burst(r.left+r.width/2,r.top+r.height/2)}
  const c=$('#wseen');if(c)c.textContent=seen.size;
  if(seen.size===D.items.length&&D.done){lines.push(D.done);confetti(160);setTimeout(()=>{for(let k=0;k<3;k++)setTimeout(()=>burst(innerWidth*(.25+.25*k),innerHeight*.3),k*200)},300)}}
 if(D.kind==='prayer')confetti(40);
 say(lines);
 d.querySelector('.say').onclick=()=>say(it.say);
 d.querySelector('#wnext').onclick=()=>{sfx.tap();showWCard(D,p,(i+1)%D.items.length)};
 d.querySelector('#wdone').onclick=()=>{sfx.tap();stopVoice();d.remove()};
 d.addEventListener('click',e=>{if(e.target===d){sfx.tap();stopVoice();d.remove()}})}

/* --- quizzes & counting: same stars/praise/celebration as the house levels --- */
function whenQuiet(fn,min=1200,max=4500){const t0=Date.now();let q=0;const iv=setInterval(()=>{const busyV=!vEl.paused||(window.speechSynthesis&&speechSynthesis.speaking)||sayHold>Date.now();q=busyV?0:q+150;
 if((Date.now()-t0>=min&&q>=450)||Date.now()-t0>=max){clearInterval(iv);fn()}},150)}
function wGood(el,line,next){sfx.right();stars++;setScore();state.score++;const r=el.getBoundingClientRect();burst(r.left+r.width/2,r.top+r.height/2);el.classList.add('ok');lockAll();
 const tok=++state.tok;say([PRAISE[Math.random()*PRAISE.length|0],line].filter(Boolean),1);confetti(60);whenQuiet(()=>{if(state.tok===tok)next()})}
function wNext(a,scr){state.round++;if(state.round>=state.total)go('wreward',a);else go(scr,{...a,r:1})}
function wStart(a,p,total){state={land:a.l,place:a.p,round:0,total,score:0,miss:0,used:[],missed:[],tok:0,prev:0}}
function wquiz(a){const L=landById(a.l),p=placeById(L,a.p),D=wDeck(p.deck);curLand=L.id;const pool=D.items.filter(it=>it.hunt!==false);
 if(!a.r)wStart(a,p,Math.min(p.rounds||8,pool.length*2));
 $('#title').textContent=p.name;
 let t=pick(pool,1,state.used)[0];if(!t){state.used=[];t=pick(pool,1,[state.last])[0]}state.used.push(t);state.last=t;
 const ch=shuffle([t,...pick(pool,2,[t])]);const ask=wFill(p.ask,t);
 let body;
 if(p.mode==='letter')body=`<div class="wqpic"><img src="${t.img}" alt=""><div class="wblank"><b>?</b>${esc(t.word.slice(1))}</div></div><div class="choices wlet">${ch.map(c=>`<button class="opt wl" data-ok="${c===t?1:0}">${c.id}</button>`).join('')}</div>`;
 else body=`<div class="choices wpics ${p.mode==='flag'?'flags':''}">${ch.map(c=>`<button class="wpic" data-ok="${c===t?1:0}" aria-label="choice"><img src="${p.mode==='flag'?c.flag:c.img}" alt=""></button>`).join('')}</div>`;
 main.innerHTML=header(ask)+body;
 main.querySelector('.say').onclick=()=>say(ask);
 say(state.round===0&&!a.r?[p.intro,ask]:[ask]);
 const line=p.mode==='letter'?t.say[1]:t.say[0];
 main.querySelectorAll('[data-ok]').forEach(b=>b.onclick=()=>{if(b.disabled)return;if(b.dataset.ok==='1')wGood(b,line,()=>wNext(a,'wquiz'));else wrong(b)});
 setTimeout(()=>{if(screen==='wquiz')warmVoice(pool.map(it=>wFill(p.ask,it)).concat(pool.map(it=>p.mode==='letter'?it.say[1]:it.say[0])))},700)}
function wcount(a){const L=landById(a.l),p=placeById(L,a.p),NUM=wDeck(p.deck).items,OB=wDeck(p.objects).items;curLand=L.id;
 if(!a.r)wStart(a,p,p.rounds||8);
 $('#title').textContent=p.name;
 let N;do{N=1+(Math.random()*10|0)}while(N===state.prev);state.prev=N;
 const O=OB[Math.random()*OB.length|0];
 const near=shuffle([N-2,N-1,N+1,N+2,N+3,N-3].filter(x=>x>=1&&x<=10));const opts=shuffle([N,near[0],near[1]]);
 main.innerHTML=header(O.ask)+`<div class="wcount" id="wc">${Array.from({length:N},(_,i)=>`<button class="wobj" style="animation-delay:${(i*.06).toFixed(2)}s" aria-label="count"><img src="${O.img}" alt=""></button>`).join('')}</div><div class="hint">Tap each one to count!</div><div class="choices wnums">${opts.map(n=>`<button class="opt wn" data-n="${n}">${n}</button>`).join('')}</div>`;
 main.querySelector('.say').onclick=()=>say(O.ask);
 say(state.round===0&&!a.r?[p.intro,O.ask]:[O.ask]);
 let c=0;main.querySelectorAll('.wobj').forEach(b=>b.onclick=()=>{if(b.classList.contains('counted')||b.disabled)return;c++;b.classList.add('counted');b.dataset.c=c;sfx.pop();say(NUM[c-1].say[0],0,1)});
 main.querySelectorAll('.wn').forEach(b=>b.onclick=()=>{if(b.disabled)return;if(+b.dataset.n===N)wGood(b,NUM[N-1].say[0],()=>wNext(a,'wcount'));else wrong(b)});
 setTimeout(()=>{if(screen==='wcount')warmVoice(OB.map(o=>o.ask).concat(NUM.map(n=>n.say[0])))},700)}
function wreward(a){const L=landById(a.l),p=placeById(L,a.p);curLand=L.id;const s=starsForMiss(state.miss||0),n=state.score,tot=state.total;
 const sv=wSave();sv.best=sv.best||{};sv.best[p.id]=Math.max(s,sv.best[p.id]||0);wPut(sv);
 $('#title').textContent='Great Job!';sfx.win();
 main.innerHTML=`<div class="reward"><h1>Great Job!</h1><div class="bigstars">${[0,1,2].map(i=>`<span style="${i<s?'':'filter:grayscale(1);opacity:.35'}">⭐</span>`).join('')}</div><div class="prompt">You finished ${esc(p.name)}! ${n} of ${tot} right.<br>Total stars: ⭐ ${stars}</div><div style="display:flex;gap:14px;justify-content:center;flex-wrap:wrap"><button class="btn" id="again">Play Again</button><button class="btn" id="tomap">Back to Map</button></div></div>`;
 say('Great job! Level complete!',1);confetti(200);for(let i=0;i<4;i++)setTimeout(()=>burst(innerWidth*(.2+.2*i),innerHeight*.35),i*250);
 $('#again').onclick=()=>{sfx.tap();go(p.type==='count'?'wcount':'wquiz',{l:L.id,p:p.id})};
 $('#tomap').onclick=()=>{sfx.tap();go('land',{id:L.id})}}

/* --- soft looping music, one theme per land (WebAudio, no files). Stops when you leave the land. --- */
const FM=[65,0,69,0,72,0,0,0,70,0,69,0,67,0,0,0,65,0,67,0,69,0,72,0,74,0,72,0,0,0,0,0];
const LTM=[72,74,76,0,79,0,76,0,74,72,74,0,76,0,0,0,77,79,81,0,79,0,77,0,76,74,72,0,0,0,0,0];
const NUMM=[60,64,67,0,62,65,69,0,64,67,71,0,65,69,72,0,67,71,74,0,72,0,67,0,64,0,60,0,0,0,0,0];
const KAL=[69,72,76,72,74,72,69,67,69,72,76,79,76,74,72,69];
Object.assign(BGM,{
 'land:faith':{bpm:72,spb:2,lp:1900,step(i,t,bus,dt){const s=i%32,m=FM[s];if(m){bnote(bus,mtof(m),t,1.2,'sine',.4,.04);bnote(bus,mtof(m+12),t,.5,'sine',.05)}
  if(s%8===0){const c=[[53,57,60],[58,62,65],[60,64,67],[53,57,60]][s>>3];c.forEach((n,k)=>bnote(bus,mtof(n),t+k*.04,dt*7.5,'sine',.13,.5))}}},
 'land:letter':{bpm:116,spb:2,lp:3200,step(i,t,bus,dt){const s=i%32,m=LTM[s];if(m)bnote(bus,mtof(m),t,.2,'triangle',.42);
  if(s%4===0)bnote(bus,mtof([48,48,53,55,48,48,53,55][s>>2]),t,dt*2.5,'sine',.5,.02);if(s%4===2)bnote(bus,mtof(76),t,.06,'square',.04)}},
 'land:number':{bpm:104,spb:2,lp:3000,step(i,t,bus,dt){const s=i%32,m=NUMM[s];if(m)bnote(bus,mtof(m),t,.28,'sine',.45,.004);
  if(s%8===0)bnote(bus,mtof([48,53,55,48][s>>3]),t,dt*6,'triangle',.35,.03);if(s%2===1)bnote(bus,mtof(84),t,.03,'sine',.06,.002)}},
 'land:nature':{bpm:92,spb:2,lp:2600,step(i,t,bus,dt){const s=i%32,m=KAL[s%16];if(s%2===0)bnote(bus,mtof(m-12),t,.5,'sine',.36,.004);
  if(s%8===0)bnote(bus,mtof([45,41,43,40][s>>3]),t,dt*7,'sine',.32,.3);
  if(Math.random()<.07){const f=2200+Math.random()*1400;bnote(bus,f,t,.09,'sine',.1,.004,1.35);bnote(bus,f*1.1,t+.11,.08,'sine',.08,.004,1.3)}}},
 'land:world':{bpm:108,spb:2,lp:3000,step(i,t,bus,dt){const s=i%32,m=KAL[(s*3)%16];bnote(bus,mtof(m),t,.22,'triangle',.3,.003);
  if([0,3,6,8,11,14].includes(s%16))bnote(bus,mtof(s%16<8?45:43),t,.25,'sine',.55,.005,.6);
  if(s%4===2)bnote(bus,1800+Math.random()*300,t,.03,'square',.05,.001)}}});
function worldBgm(s){if(!WORLD_SCREENS.includes(s))return false;const L=landById(curLand);const k=L&&('land:'+L.music);if(k&&BGM[k])bgmPlay(k);else bgmStop();return true}

/* --- boot: load lands.json (precached offline), then open the world map --- */
fetch('lands.json').then(r=>{if(!r.ok)throw 0;return r.json()}).then(j=>{LANDS=j;go('home')}).catch(()=>{go('house')});
