/* ===== Country player (Emmavengers World · World Land) =====
   One generic player for every country pack in content/countries/. A country is pure data:
   content/countries/index.json lists the packs; each pack (e.g. cameroon.json) holds Learn cards per age band,
   Play activities (known templates: grid-route.v1, ordered-slots.v1, match.v1, map-select.v1,
   evidence-comparison.v1, inquiry.v1), a quiz bank file, stories, pre-written guide lines (Ari + Ezra) and media
   descriptions, all in English + French. Adding a country = add its JSON + a "country" place in lands.json.
   No free text, no search, no microphone, no generated speech: only the lines written in the pack are shown/spoken.
   Local data kept (localStorage, no personal data): language, age band, guide on/off, quiz items seen today,
   a "visited" stamp and minimal practice events (item id, first-try correct, hint used, repeat). */
const CT={index:null,ui:null,packs:{},banks:{},ready:false,enteredAt:0,breakShown:false,shownLines:new Set()};
const CT_SCREENS=['ctry','clearn','cplay','cgame','cquiz','cstory','cread','cdone'];
WORLD_SCREENS.push(...CT_SCREENS);
function ctPrefs(){try{return Object.assign({lang:'en',age:null,guide:true},JSON.parse(localStorage.getItem('emmaCtryPrefs')||'{}'))}catch(e){return{lang:'en',age:null,guide:true}}}
function ctSetPrefs(p){try{localStorage.setItem('emmaCtryPrefs',JSON.stringify(Object.assign(ctPrefs(),p)))}catch(e){}}
function ctProg(){try{return JSON.parse(localStorage.getItem('emmaCtry')||'{}')}catch(e){return{}}}
function ctPutProg(s){try{localStorage.setItem('emmaCtry',JSON.stringify(s))}catch(e){}}
const ctLang=()=>ctPrefs().lang==='fr'?'fr':'en';
const LT=o=>o==null?'':typeof o==='string'?o:(o[ctLang()]!=null?o[ctLang()]:o.en);
const UT=k=>LT((CT.cur&&CT.cur.payload.ui&&CT.cur.payload.ui[k])||(CT.ui&&CT.ui.strings[k])||k);
const ctBand=()=>ctPrefs().age==='big'?'big':'little';
const ctToday=()=>{const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')};
/* Every string a pack can speak, both languages (tools/check_voice.py makes sure each has a recorded clip). */
const CT_FR=new Set(),CT_ALL=new Set();
function ctStrings(pk){const out=[];const add=(o)=>{if(!o)return;if(typeof o==='string'){out.push([o,'en']);return}if(o.en)out.push([o.en,'en']);if(o.fr)out.push([o.fr,'fr'])};
 const P=pk.payload;Object.values(P.lines).forEach(l=>add(l.text));
 ['little','big'].forEach(b=>P.learn[b].cards.forEach(c=>add(c.text)));
 P.play.forEach(g=>{add(g.title);add(g.mission);add(g.prompt);add(g.hint);add(g.success);add(g.caption);add(g.task);add(g.feedback);
  if(g.feedback&&g.feedback.success)Object.values(g.feedback).forEach(add);
  (g.prompts||[]).forEach(p=>add(p.ask));(g.questions||[]).forEach(q=>{add(q.ask);Object.values(q.options).forEach(add)});
  if(g.next)Object.values(g.next.options).forEach(add)});
 const Q=P.quiz,bank=CT.banks[pk.payload.slug];add(Q.exhausted);
 if(bank)bank.items.forEach(it=>Object.entries(Q.localeKeys).forEach(([lg,k])=>{const x=it[k];if(!x)return;[x.prompt,x.hint,x.feedback,...Object.values(x.options)].forEach(t=>t&&out.push([t,lg]))}));
 P.stories.forEach(s=>{add(s.title);add(s.banner);Object.values(s.pages).forEach(ps=>ps.forEach(p=>add(p.text)));Object.values(s.reflection).forEach(add)});
 if(CT.ui){['shorter','needToKnow'].forEach(k=>add(CT.ui.strings[k]))}
 return out}
function ctIndexStrings(pk){ctStrings(pk).forEach(([t,lg])=>{CT_ALL.add(t);if(lg==='fr')CT_FR.add(t)})}
window.__ctryVoice=()=>[...new Set(Object.values(CT.packs).flatMap(pk=>ctStrings(pk).map(x=>x[0])))];
/* Pilot clips exist once (default voice folder) in English and French, so every voice setting uses them. */
window.voiceOnlyMia=t=>CT_ALL.has(t);
window.ttsLangFor=t=>CT_FR.has(t)?'fr-FR':'en-US';
function ctLoad(){const j=u=>fetch(u).then(r=>{if(!r.ok)throw new Error(u);return r.json()});
 return Promise.all([j('content/countries/index.json'),j('content/countries/ui.json')]).then(([ix,ui])=>{CT.index=ix;CT.ui=ui;
  return Promise.all(ix.countries.map(c=>j(c.file).then(pk=>j(pk.payload.quiz.bank).then(b=>{CT.packs[c.slug]=pk;CT.banks[c.slug]=b;ctIndexStrings(pk)}))))}).then(()=>{CT.ready=true;window.CTRY_READY=true})}
const ctReady=ctLoad().catch(e=>{console.warn('country packs not loaded',e)});

/* ---- speech + guide bubble (Ari / Ezra). One voice at a time; captions = exact spoken text. ---- */
function ctLine(id){const l=CT.cur.payload.lines[id];return l?{id,speaker:l.speaker,text:LT(l.text)}:null}
function ctSay(texts){say(texts.filter(Boolean),0,1)}
function ctGuide(ids,after){const P=ctPrefs();let ls=(ids||[]).map(ctLine).filter(Boolean);
 if(CT.enteredAt&&!CT.breakShown&&Date.now()-CT.enteredAt>(CT.cur.payload.breakAfterMinutes||10)*60000){CT.breakShown=true;ls.unshift(ctLine('ari.cm.break'))}
 const box=$('#cguide');if(box){box.innerHTML='';box.classList.toggle('hide',!P.guide||!ls.length)}
 if(!P.guide)ls=[];
 if(box)ls.forEach(l=>{const d=document.createElement('button');d.className='cbub '+l.speaker;d.dataset.line=l.id;
  d.innerHTML=`<img src="img/world/guides/${l.speaker==='ezra'?'ezra-face':'ari-hello'}.webp" alt=""><span><b>${l.speaker==='ezra'?'Ezra':'Ari'}</b> ${esc(l.text)}</span>`;
  d.setAttribute('aria-label',(l.speaker==='ezra'?'Ezra: ':'Ari: ')+l.text);
  d.onclick=e=>{e.stopPropagation();stopVoice();box.classList.add('hide')};box.appendChild(d)});
 ctSay([...ls.map(l=>l.text),...(after||[])])}
function ctHideGuide(){const b=$('#cguide');if(b)b.classList.add('hide')}
const GUIDE_HTML='<div class="cguide hide" id="cguide" aria-live="polite"></div>';

/* ---- media renderers (art is placeholder unless noted; flag is drawn from the pack's flag data) ---- */
function ctFlag(F,o={}){const W=300,H=200,sw=W/3,st=F.stripes;const cx=sw*F.star.stripe+sw/2,cy=H/2,R=H*0.19,r=R*0.382;
 let pts=[];for(let i=0;i<10;i++){const a=-Math.PI/2+i*Math.PI/5,rr=i%2?r:R;pts.push((cx+rr*Math.cos(a)).toFixed(1)+','+(cy+rr*Math.sin(a)).toFixed(1))}
 const names=CT.cur.payload.play.find(g=>g.template==='ordered-slots.v1');
 const words=o.words&&names?names.pieces.slice(0,3).map((p,i)=>`<text x="${sw*i+sw/2}" y="${H-14}" text-anchor="middle" class="fw">${esc(LT(p.name))}</text>`).join(''):'';
 return `<svg class="cflag" viewBox="-26 -10 ${W+36} ${H+40}" role="img" aria-label="${esc(LT(CT.cur.payload.media.flag.alt))}"><rect x="-20" y="-6" width="8" height="${H+34}" rx="3" fill="#8a6a3a"/><circle cx="-16" cy="-6" r="7" fill="#e7b416"/>
 ${st.map((c,i)=>`<rect x="${sw*i}" y="0" width="${sw+.5}" height="${H}" fill="${c}"/>`).join('')}<polygon points="${pts.join(' ')}" fill="${F.star.color}"/>${words}<rect x="0" y="0" width="${W}" height="${H}" fill="none" stroke="#17324d" stroke-width="2"/></svg>`}
const SCENES={
 coast:'<rect width="160" height="120" fill="#bfe6ff"/><circle cx="130" cy="24" r="12" fill="#ffd54a"/><rect y="62" width="160" height="34" fill="#2f86e8"/><path d="M0 70q10-6 20 0t20 0 20 0 20 0 20 0 20 0 20 0 20 0" stroke="#fff" stroke-width="3" fill="none"/><path d="M0 92q40-10 80-2t80-4v34H0z" fill="#f2d48a"/>',
 forest:'<rect width="160" height="120" fill="#d7f2d0"/><rect y="96" width="160" height="24" fill="#5a8f3a"/>'+[12,40,70,100,128].map((x,i)=>`<rect x="${x+12}" y="${70-i%2*8}" width="6" height="30" fill="#7a4a22"/><circle cx="${x+15}" cy="${60-i%2*8}" r="${18+i%2*4}" fill="${i%2?'#1f7a3a':'#2e9a48'}"/>`).join(''),
 grassland:'<rect width="160" height="120" fill="#fff1c9"/><path d="M0 80q40-40 80-10t80-20v70H0z" fill="#9ccc65"/><path d="M0 96q50-20 100 0t60-6v30H0z" fill="#c5a84a"/>'+[20,50,90,130].map(x=>`<path d="M${x} 104l3-12 3 12M${x+8} 106l2-9 2 9" stroke="#7d6a1f" stroke-width="2" fill="none"/>`).join(''),
 mountain:'<rect width="160" height="120" fill="#cfe8ff"/><path d="M10 110L80 22l70 88z" fill="#6d7f8f"/><path d="M80 22l-16 20 8 4 8-6 8 6 8-4z" fill="#eef3f7"/><rect y="104" width="160" height="16" fill="#4f8f3a"/>'};
const ctScene=(k,big)=>`<svg class="cscene${big?' big':''}" viewBox="0 0 160 120" role="img" aria-label="${esc(k)}">${SCENES[k]||''}</svg>`;
const PH=()=>`<span class="cph">${esc(UT('placeholder'))}</span>`;
function ctGrid(o={}){const G=CT.cur.payload.practiceMap,pos=o.pos||[1,1];
 const cell=(c,r,k)=>{const here=pos[0]===r&&pos[1]===k,lab=LT(G.cellLabel).replace('{r}',r+1).replace('{c}',k+1).replace('{place}',LT(c.name));
  return `<button class="ccell${here?' here':''}${o.highlight===c.id?' hl':''}" data-r="${r}" data-c="${k}" aria-label="${esc(lab)}"${o.interactive?'':' tabindex="-1" disabled'}><i>${c.icon}</i><span>${esc(LT(c.name))}</span>${here?'<em class="ctoken" aria-hidden="true">🦁</em>':''}</button>`};
 const arrow=o.arrow?`<span class="carrow a-${o.arrow}" aria-hidden="true">➜</span>`:'';
 return `<div class="cmapwrap"><div class="cnorth" aria-hidden="true">⬆ ${esc(UT('north'))}</div><div class="cgrid">${G.rows.map((row,r)=>row.map((c,k)=>cell(c,r,k)).join('')).join('')}${arrow}</div>
 <div class="ckey"><b>${esc(UT('key'))}:</b> 📖 = ${esc(LT(G.rows[0][1].name))}</div></div>`}
function ctCompass(o={}){const g=CT.cur.payload.play.find(x=>x.template==='map-select.v1');const at=p=>g.neighbours.filter(n=>n.pos===p);
 const nb=n=>`<button class="cnb" data-n="${n.id}"${o.interactive?'':' disabled tabindex="-1"'}>${esc(LT(n.name))}</button>`;
 const slot=p=>`<div class="ccmp-${p}">${at(p).map(nb).join('')}</div>`;
 return `<div class="ccompass"><div class="cnotmap">${esc(UT('notMap'))}</div><div class="ccmp">${slot('nw')}<div class="ccmp-n cdir">⬆ ${esc(UT('north'))}</div>${slot('ne')}<div class="ccmp-w cdir">⬅ ${esc(UT('west'))}</div><div class="ccmp-c">${esc(LT(CT.cur.payload.name))}</div>${slot('e')}<div class="ccmp-sw csea">🌊 ${esc(UT('seaSW'))}</div>${slot('s')}${slot('se')}</div></div>`}
function ctMedia(id,o={}){const M=CT.cur.payload.media[id];if(!M)return'';
 switch(M.kind){
  case'flag':return `<div class="cmedia">${ctFlag(CT.cur.payload.flag)}</div>`;
  case'grid':return `<div class="cmedia">${ctGrid({arrow:M.arrow,highlight:M.highlight,interactive:M.interactive,pos:o.pos})}</div>`;
  case'scenes':return `<div class="cmedia cscenes">${M.scenes.map(s=>ctScene(s)).join('')}${PH()}</div>`;
  case'scene':return `<div class="cmedia">${ctScene(M.scene,1)}${PH()}</div>`;
  case'compass':return `<div class="cmedia">${ctCompass()}</div>`;
  case'cities':return `<div class="cmedia ccities">${M.cities.map((c,i)=>`<div class="ccity"><i>${c.icon}</i><b>${esc(c.name)}</b><small>${esc(UT(i?'port':'capital'))}</small></div>`).join('')}</div>`;
  case'count-boxes':return `<div class="cmedia cboxes"><div>${Array.from({length:M.n},(_,i)=>`<i>${i+1}</i>`).join('')}</div><b>${esc(UT('regions10'))}</b>${PH()}</div>`;
  case'count-table':return `<div class="cmedia">${ctTable(M.rows)}</div>`;
  default:return `<div class="cmedia cplace"><i>${M.icon||'🖼️'}</i><span>${esc(LT(M.label))}</span>${PH()}</div>`}}
const ctTable=rows=>`<table class="ctable"><tr><th></th><th>${esc(UT('visitors'))}</th></tr>${rows.map(r=>`<tr><td>${esc(LT(r.label))}</td><td><b>${r.value}</b></td></tr>`).join('')}</table>`;

/* ---- shared chrome ---- */
function ctTop(title){$('#title').textContent=title||LT(CT.cur.payload.name);main.setAttribute('lang',ctLang())}
function ctRequire(a,fn){if(!CT.ready){main.innerHTML='<div class="prompt">…</div>';ctReady.then(()=>{if(CT.ready&&CT_SCREENS.includes(screen))fn(a)});return true}
 const pk=CT.packs[(a&&a.c)||(CT.cur&&CT.cur.payload.slug)];if(!pk){go('land',{id:'world'});return true}CT.cur=pk;curLand=pk.tags.land;return false}
const ctA=extra=>Object.assign({c:CT.cur.payload.slug},extra||{});
function ctBind(){main.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{if(!b.closest('#cguide'))ctHideGuide()}))}
function ctStamp(){const P=ctProg(),k=CT.cur.payload.slug;P[k]=P[k]||{};const first=!P[k].stamp;P[k].stamp=true;ctPutProg(P);return first}
function ctEvent(ev){const P=ctProg();P.events=(P.events||[]).concat([ev]).slice(-200);ctPutProg(P)}

/* ---- Hub: four big modes, one country card, age band + language + guide switches ---- */
function ctry(a){if(ctRequire(a,ctry))return;const pk=CT.cur,P=ctPrefs(),pr=ctProg(),me=pr[pk.payload.slug]||{};ctTop();
 const fromLand=a&&a.from==='land';if(fromLand&&!CT.enteredAt){CT.enteredAt=Date.now();CT.breakShown=false}
 if(!P.age){main.innerHTML=`<div class="chub"><h2 class="cq">${esc(UT('whoIsPlaying'))}</h2><div class="cages"><button class="cmode cage" data-age="little"><img src="img/world/guides/ari-hello.webp" alt=""><b>${esc(UT('little'))}</b></button><button class="cmode cage" data-age="big"><img src="img/world/guides/ari-map.webp" alt=""><b>${esc(UT('bigx'))}</b></button></div>${ctLangRow()}</div>`;
  main.querySelectorAll('.cage').forEach(b=>b.onclick=()=>{sfx.tap();ctSetPrefs({age:b.dataset.age});go('ctry',ctA({from:fromLand?'land':''}))});ctLangBind(()=>go('ctry',ctA({from:fromLand?'land':''})));return}
 const modes=[['learn','📖','clearn'],['play','🧩','cplay'],['quiz','❓','cquiz'],['stories','📚','cstory']];
 main.innerHTML=`<div class="chub">${fromLand?'<img class="cswoop" src="img/world/guides/ezra-carry.webp" alt="">':''}
  <div class="cdraft">${esc(UT('draft'))}</div>
  <div class="ccard"><div class="cflagbox">${ctFlag(pk.payload.flag)}</div><div class="cname"><b>${esc(LT(pk.payload.name))}</b>${me.stamp?`<span class="cstamp">🏅 ${esc(UT('visited'))}</span>`:''}</div><img class="cari" src="img/world/guides/ari-map.webp" alt="Ari"></div>
  ${GUIDE_HTML}<div class="cmodes">${modes.map(([k,ic,s])=>`<button class="cmode" data-go="${s}" data-mode="${k}"><i>${ic}</i><b>${esc(UT(k))}</b></button>`).join('')}</div>
  <div class="crow csettings"><div class="cseg" role="group"><button class="cagebtn${P.age==='little'?' on':''}" data-age="little" aria-pressed="${P.age==='little'}">${esc(UT('littleShort'))}</button><button class="cagebtn${P.age==='big'?' on':''}" data-age="big" aria-pressed="${P.age==='big'}">${esc(UT('bigShort'))}</button></div>
  ${ctLangSeg()}<button class="cbtn2${P.guide?' on':''}" id="cguideTog" aria-pressed="${P.guide}">🦁 ${esc(UT(P.guide?'guideOn':'guideOff'))}</button></div></div>`;
 main.querySelectorAll('.cmode').forEach(b=>b.onclick=()=>{sfx.tap();go(b.dataset.go,ctA())});
 main.querySelectorAll('.cagebtn').forEach(b=>b.onclick=()=>{sfx.tap();ctSetPrefs({age:b.dataset.age});go('ctry',ctA())});
 ctLangBind(()=>go('ctry',ctA()));
 $('#cguideTog').onclick=()=>{sfx.tap();ctSetPrefs({guide:!ctPrefs().guide});go('ctry',ctA())};
 ctBind();
 if(fromLand){const P2=ctProg(),k=pk.payload.slug;P2[k]=P2[k]||{};const again=(P2[k].visits||0)>0;P2[k].visits=(P2[k].visits||0)+1;ctPutProg(P2);
  ctGuide([pk.payload.hub.travel,again?pk.payload.hub.introAgain:pk.payload.hub.intro])}
 warmVoice(['ari.cm.learn','ari.cm.story'].map(id=>ctLine(id).text),0)}
function ctLangSeg(){const l=ctLang();return `<div class="cseg" role="group" aria-label="Language / Langue"><button class="clang${l==='en'?' on':''}" data-lang="en" aria-pressed="${l==='en'}">English</button><button class="clang${l==='fr'?' on':''}" data-lang="fr" aria-pressed="${l==='fr'}">Français</button></div>`}
const ctLangRow=()=>`<div class="crow">${ctLangSeg()}</div>`;
function ctLangBind(re){main.querySelectorAll('.clang').forEach(b=>b.onclick=()=>{sfx.tap();ctSetPrefs({lang:b.dataset.lang});re()})}

/* ---- Learn: one card per screen (image + ≤2 sentences + read aloud / replay / next) ---- */
function clearn(a){if(ctRequire(a,clearn))return;const L=CT.cur.payload.learn[ctBand()],cards=L.cards,i=Math.max(0,Math.min(a.i||0,cards.length-1)),c=cards[i];ctTop(UT('learn'));
 const text=LT(c.text);
 main.innerHTML=`<div class="cscr clearn"><div class="cprog">${i+1} / ${cards.length}${c.band?` · <span class="ctag">${esc(UT('optional'))} · ${esc(UT('older'))}</span>`:''}</div>
  ${ctMedia(c.image)}<p class="ctext" id="ctext">${esc(text)}</p>
  <div class="cnav"><button class="cbtn2" id="cprev"${i?'':' disabled'}>◀ ${esc(UT('prev'))}</button><button class="say" id="csay" aria-label="${esc(UT('replay'))}">🔊</button><button class="btn cnext" id="cnext">${esc(UT(i===cards.length-1?'done':'next'))} ▶</button></div>${GUIDE_HTML}</div>`;
 $('#cprev').onclick=()=>{sfx.tap();go('clearn',ctA({i:i-1}))};
 $('#cnext').onclick=()=>{sfx.tap();if(i===cards.length-1)go('cdone',ctA({mode:'learn'}));else go('clearn',ctA({i:i+1}))};
 $('#csay').onclick=()=>{ctHideGuide();ctSay([text])};
 if(c.kind==='try')ctTryGrid(c);
 ctBind();
 const key='learn:'+c.id+':'+ctLang();const ids=CT.shownLines.has(key)?[]:(c.lines||[]);CT.shownLines.add(key);ctGuide(ids,[text]);
 warmVoice(cards.slice(i+1,i+3).map(x=>LT(x.text)),0)}
function ctTryGrid(c){const M=CT.cur.payload.media[c.image];let pos=[1,1];const host=main.querySelector('.cmedia');
 const draw=()=>{host.innerHTML=ctGrid({interactive:true,pos})+`<div class="cdirs one"><button class="cdir-btn" data-d="n">⬆ ${esc(UT('north'))}</button></div>`;
  host.querySelectorAll('.ccell').forEach(b=>b.onclick=()=>{const r=+b.dataset.r,k=+b.dataset.c;if(Math.abs(r-pos[0])+Math.abs(k-pos[1])===1)mv([r,k])});
  host.querySelector('.cdir-btn').onclick=()=>mv([pos[0]-1,pos[1]])};
 const mv=p=>{if(p[0]<0)return;pos=p;sfx.pop();draw();const id=CT.cur.payload.practiceMap.rows[pos[0]][pos[1]].id;if(id===M.goal){sfx.right();host.classList.add('cwin');ctGuide(['ari.cm.correct'])}};
 draw()}

/* ---- Play: list of activities for the age band, then each template ---- */
function cplay(a){if(ctRequire(a,cplay))return;ctTop(UT('play'));const band=ctBand(),G=CT.cur.payload.play;
 const core=G.filter(g=>band==='little'?g.bands.includes('5-7'):g.bands.includes('8-10')),deep=band==='big'?G.filter(g=>!g.bands.includes('8-10')&&g.bands.includes('11-13')):[];
 const btn=g=>`<button class="cmode cgamebtn" data-g="${g.id}"><i>${g.icon}</i><b>${esc(LT(g.title))}</b></button>`;
 main.innerHTML=`<div class="cscr"><div class="cmodes">${core.map(btn).join('')}</div>${deep.length?`<h3 class="csub">${esc(UT('older'))} · ${esc(UT('optional'))}</h3><div class="cmodes">${deep.map(btn).join('')}</div>`:''}${GUIDE_HTML}</div>`;
 main.querySelectorAll('.cgamebtn').forEach(b=>b.onclick=()=>{sfx.tap();go('cgame',ctA({g:b.dataset.g}))});ctBind()}
function cgame(a){if(ctRequire(a,cgame))return;const g=CT.cur.payload.play.find(x=>x.id===a.g);if(!g){go('cplay',ctA());return}ctTop(LT(g.title));
 state={ctry:CT.cur.payload.slug,game:g.id};
 ({'grid-route.v1':gRoute,'ordered-slots.v1':gFlag,'match.v1':gMatch,'map-select.v1':gCompass,'evidence-comparison.v1':gEvidence,'inquiry.v1':gInquiry})[g.template](g)}
function ctWin(g,line,extra){sfx.right();const s=ctStamp();ctEvent({item:g.id,activity:true});
 const w=document.createElement('div');w.className='cwinbox';w.innerHTML=`<p class="cfb ok">✓ ${esc(line)}</p>${extra?`<p class="cfb">${esc(extra)}</p>`:''}<div class="cnav"><button class="cbtn2" id="cagain">↻ ${esc(UT('again'))}</button><button class="btn" id="cfin">${esc(UT('done'))} ✓</button></div>`;
 main.querySelector('.cscr').insertBefore(w,$('#cguide'));
 $('#cagain').onclick=()=>{sfx.tap();go('cgame',ctA({g:g.id}))};$('#cfin').onclick=()=>{sfx.tap();go('cdone',ctA({mode:'play',g:g.id}))};
 w.scrollIntoView({block:'nearest'});ctSay([line,extra])}
function ctHint(t,extra){sfx.wrong();ctGuide(['ari.cm.hint'],[t,extra].filter(Boolean));const h=$('#chintline');if(h){h.textContent=t;h.classList.remove('hide')}}
/* grid-route.v1: 3x3 practice map, N/S/E/W buttons or tap a neighbouring square; Undo / Start again / Help; any valid route */
function gRoute(g){const G=CT.cur.payload.practiceMap;let pos=g.start.slice(),hist=[],done=false,helped=false;
 const D={n:[-1,0],s:[1,0],e:[0,1],w:[0,-1]};
 main.innerHTML=`<div class="cscr"><p class="ctext sm">${esc(LT(g.mission))} <button class="say" id="csay" aria-label="${esc(UT('readAloud'))}">🔊</button></p><div class="cmedia" id="cgm"></div>
  <div class="cdirs"><button class="cdir-btn" data-d="n">⬆ ${esc(UT('north'))}</button><button class="cdir-btn" data-d="w">⬅ ${esc(UT('west'))}</button><button class="cdir-btn" data-d="e">${esc(UT('east'))} ➡</button><button class="cdir-btn" data-d="s">⬇ ${esc(UT('south'))}</button></div>
  <div class="cnav"><button class="cbtn2" id="cundo">↶ ${esc(UT('undo'))}</button><button class="cbtn2" id="creset">⟲ ${esc(UT('reset'))}</button><button class="cbtn2" id="chelp">? ${esc(UT('hint'))}</button>${g.countMoves?`<span class="cmoves">${esc(UT('moves'))}: <b id="cmv">0</b></span>`:''}</div>
  <p class="cfb hint hide" id="chintline"></p>${GUIDE_HTML}</div>`;
 const draw=()=>{$('#cgm').innerHTML=ctGrid({interactive:!done,pos});const m=$('#cmv');if(m)m.textContent=hist.length;
  main.querySelectorAll('#cgm .ccell').forEach(b=>b.onclick=()=>{if(done)return;const r=+b.dataset.r,c=+b.dataset.c;if(Math.abs(r-pos[0])+Math.abs(c-pos[1])===1)move([r,c]);else if(!(r===pos[0]&&c===pos[1]))ctHint(LT(g.feedback.routeHelp))})};
 const move=p=>{hist.push(pos);pos=p;sfx.pop();draw();const id=G.rows[pos[0]][pos[1]].id;
  if(id===g.goal){done=true;draw();main.querySelectorAll('.cdir-btn,#cundo').forEach(b=>b.disabled=true);
   const n=hist.length;ctWin(g,LT(g.feedback.success),g.shortest&&n>g.shortest?UT('shorter'):'');ctEvent({item:g.id,moves:n});return}
  if(!helped&&hist.length>=g.routeHelpAfter){helped=true;ctHint(LT(g.feedback.routeHelp))}};
 main.querySelectorAll('.cdir-btn').forEach(b=>b.onclick=()=>{if(done)return;const d=D[b.dataset.d],p=[pos[0]+d[0],pos[1]+d[1]];
  if(p[0]<0||p[0]>2||p[1]<0||p[1]>2){sfx.wrong();const h=$('#chintline');h.textContent=LT(g.feedback.edge);h.classList.remove('hide');ctSay([LT(g.feedback.edge)]);return}move(p)});
 $('#cundo').onclick=()=>{if(done||!hist.length)return;sfx.tap();pos=hist.pop();draw()};
 $('#creset').onclick=()=>{sfx.tap();go('cgame',ctA({g:g.id}))};
 $('#chelp').onclick=()=>ctHint(LT(g.feedback.hint));
 $('#csay').onclick=()=>ctSay([LT(g.mission)]);
 draw();ctBind();ctGuide(g.lines||[],[LT(g.mission)])}
/* ordered-slots.v1: build the flag by select-then-place; colour words are an optional overlay only */
function gFlag(g){const F=CT.cur.payload.flag;let placed=[null,null,null],star=false,sel=null,words=false;
 const pieces=shuffle(g.pieces.map(p=>p.id));
 main.innerHTML=`<div class="cscr"><p class="ctext sm">${esc(LT(g.prompt))} <button class="say" id="csay" aria-label="${esc(UT('readAloud'))}">🔊</button></p>
  <div class="cflagbuild" id="cfb"></div><p class="csmall">${esc(UT('pickPiece'))}</p><div class="cpieces" id="cpc"></div>
  <div class="cnav"><button class="cbtn2" id="cwords" aria-pressed="false">Aa ${esc(UT('colourWords'))}</button><button class="cbtn2" id="chelp">? ${esc(UT('hint'))}</button><button class="cbtn2" id="creset">⟲ ${esc(UT('reset'))}</button></div>
  <p class="cfb hint hide" id="chintline"></p>${GUIDE_HTML}</div>`;
 const P=id=>g.pieces.find(p=>p.id===id);
 const draw=()=>{const all=placed.every(Boolean)&&star;
  $('#cfb').innerHTML=all?ctFlag(F,{words}):`<div class="cpole" aria-hidden="true"></div>${placed.map((p,i)=>`<button class="cslot${p?' full':''}" data-s="${i}" aria-label="${esc(UT('stripe'))} ${i+1}${p?': '+esc(LT(P(p).name)):''}" style="${p?`background:${F.stripes[P(p).slot]}`:''}">${p&&words?`<span class="fw2">${esc(LT(P(p).name))}</span>`:''}${!p?`<span class="cslotn">${i+1}</span>`:''}${i===F.star.stripe&&star?'<span class="cstar">★</span>':''}</button>`).join('')}`;
  $('#cpc').innerHTML=pieces.filter(id=>id==='star'?!star:!placed.includes(id)).map(id=>{const p=P(id);return `<button class="cpiece${sel===id?' sel':''}" data-p="${id}" aria-pressed="${sel===id}">${id==='star'?`<span class="cpsw star">★</span>`:`<span class="cpsw" style="background:${F.stripes[p.slot]}"></span>`}<b>${esc(LT(p.name))}</b></button>`}).join('');
  main.querySelectorAll('.cpiece').forEach(b=>b.onclick=()=>{sfx.tap();sel=b.dataset.p;draw()});
  main.querySelectorAll('.cslot').forEach(b=>b.onclick=()=>drop(+b.dataset.s));
  if(all){sel=null;ctWin(g,LT(g.success))}};
 const drop=i=>{if(!sel){ctSay([LT(g.prompt)]);return}const p=P(sel);
  if(sel==='star'){if(i===F.star.stripe&&placed[i]){star=true;sel=null;sfx.pop();draw()}else ctHint(LT(g.hint));return}
  if(placed[i]){return}if(p.slot===i){placed[i]=sel;sel=null;sfx.pop();draw()}else ctHint(LT(g.hint))};
 $('#cwords').onclick=()=>{words=!words;$('#cwords').setAttribute('aria-pressed',words);$('#cwords').classList.toggle('on',words);draw()};
 $('#chelp').onclick=()=>ctHint(LT(g.hint));$('#creset').onclick=()=>{sfx.tap();go('cgame',ctA({g:g.id}))};$('#csay').onclick=()=>ctSay([LT(g.prompt)]);
 draw();ctBind();ctGuide([],[LT(g.prompt)])}
/* match.v1: pick a picture, then tap its name */
function gMatch(g){const pics=shuffle(g.pairs.map(p=>p.id)),names=shuffle(g.pairs.map(p=>p.id)),done=new Set();let sel=null;
 main.innerHTML=`<div class="cscr"><p class="ctext sm">${esc(LT(g.prompt))} <button class="say" id="csay" aria-label="${esc(UT('readAloud'))}">🔊</button></p><p class="csmall">${esc(UT('pickPicture'))} · ${esc(UT('placeholder'))}</p>
  <div class="cmatch"><div class="cpics" id="cpics"></div><div class="cnames" id="cnames"></div></div><p class="cfb hint hide" id="chintline"></p>${GUIDE_HTML}</div>`;
 const P=id=>g.pairs.find(p=>p.id===id);
 const draw=()=>{$('#cpics').innerHTML=pics.map(id=>`<button class="cpic${sel===id?' sel':''}${done.has(id)?' ok':''}" data-p="${id}" aria-pressed="${sel===id}" aria-label="${esc(UT('placeholder'))} ${pics.indexOf(id)+1}"${done.has(id)?' disabled':''}>${ctScene(P(id).scene)}${done.has(id)?`<b>✓ ${esc(LT(P(id).name))}</b>`:''}</button>`).join('');
  $('#cnames').innerHTML=names.map(id=>`<button class="cname2${done.has(id)?' ok':''}" data-n="${id}"${done.has(id)?' disabled':''}>${done.has(id)?'✓ ':''}${esc(LT(P(id).name))}</button>`).join('');
  main.querySelectorAll('.cpic').forEach(b=>b.onclick=()=>{sfx.tap();sel=b.dataset.p;draw()});
  main.querySelectorAll('.cname2').forEach(b=>b.onclick=()=>{if(!sel){ctSay([LT(P(b.dataset.n).name)]);return}if(b.dataset.n===sel){done.add(sel);sel=null;sfx.pop();draw();if(done.size===g.pairs.length)ctWin(g,LT(g.success))}else{sfx.wrong();ctGuide(['ari.cm.hint'])}})};
 $('#csay').onclick=()=>ctSay([LT(g.prompt)]);draw();ctBind();ctGuide(g.lines||[],[LT(g.prompt)])}
/* map-select.v1: neighbour compass (schematic, list-equivalent buttons) */
function gCompass(g){const order=shuffle(g.prompts.map((_,i)=>i));let k=0,tries=0;
 main.innerHTML=`<div class="cscr"><div class="cprog" id="cprog"></div><p class="ctext sm" id="cask"></p><div class="cmedia" id="ccm"></div>
  <div class="cnav"><button class="cbtn2" id="chelp">? ${esc(UT('hint'))}</button><button class="say" id="csay" aria-label="${esc(UT('readAloud'))}">🔊</button></div><p class="cfb hint hide" id="chintline"></p><div id="cnextbox"></div>${GUIDE_HTML}</div>`;
 const show=(first)=>{const p=g.prompts[order[k]];tries=0;$('#cprog').textContent=`${k+1} / ${order.length}`;$('#cask').textContent=LT(p.ask);$('#ccm').innerHTML=ctCompass({interactive:true});$('#cnextbox').innerHTML='';$('#chintline').classList.add('hide');
  main.querySelectorAll('.cnb').forEach(b=>b.onclick=()=>{if(b.disabled)return;if(p.accept.includes(b.dataset.n)){sfx.right();b.classList.add('ok');main.querySelectorAll('.cnb').forEach(x=>x.disabled=true);ctEvent({item:g.id+':'+p.dir,first:tries===0});
    if(k===order.length-1){ctWin(g,ctLine('ari.cm.correct').text);return}
    $('#cnextbox').innerHTML=`<div class="cnav"><button class="btn" id="cnx">${esc(UT('next'))} ▶</button></div>`;$('#cnx').onclick=()=>{sfx.tap();k++;show()};ctGuide(['ari.cm.correct'])}
   else{tries++;b.classList.add('no');b.disabled=true;ctHint(LT(g.hint))}});
  if(first)ctGuide(g.lines||[],[LT(p.ask)]);else ctSay([LT(p.ask)])};
 $('#chelp').onclick=()=>ctHint(LT(g.hint));$('#csay').onclick=()=>ctSay([$('#cask').textContent]);
 show(1);ctBind()}
/* single-choice step used by evidence-comparison.v1 and inquiry.v1: options shuffled, stable ids */
function ctChoice(host,ask,options,key,onOk,silent){const ids=shuffle(Object.keys(options));let tries=0;
 host.innerHTML=`<p class="ctext sm">${esc(ask)}</p><div class="copts">${ids.map(id=>`<button class="copt" data-o="${id}">${esc(LT(options[id]))}</button>`).join('')}</div>`;
 host.querySelectorAll('.copt').forEach(b=>b.onclick=()=>{if(b.disabled)return;if(b.dataset.o===key){sfx.right();b.classList.add('ok');host.querySelectorAll('.copt').forEach(x=>x.disabled=true);onOk(tries===0)}else{tries++;sfx.wrong();b.classList.add('no');b.disabled=true;ctGuide(['ari.cm.hint'])}});
 if(!silent)ctSay([ask,...ids.map(id=>LT(options[id]))]);return ids.map(id=>LT(options[id]))}
function ctSourceTable(rows){return `<table class="ctable"><tr><th>${esc(UT('source'))}</th><th>${esc(UT('height'))}</th></tr>${rows.map(r=>`<tr><td>${esc(LT(r.source))}</td><td><b>${esc(LT(r.value))}</b></td></tr>`).join('')}</table>`}
function gEvidence(g){main.innerHTML=`<div class="cscr"><div class="cmedia">${ctSourceTable(g.table)}</div><p class="ctext sm">${esc(LT(g.caption))}</p><div id="cq"></div>${GUIDE_HTML}</div>`;
 const step=(j,silent)=>{const q=g.questions[j];return ctChoice($('#cq'),LT(q.ask),q.options,q.key,first=>{ctEvent({item:g.id+':q'+(j+1),first});if(j<g.questions.length-1){const b=document.createElement('div');b.className='cnav';b.innerHTML=`<button class="btn" id="cnx">${esc(UT('next'))} ▶</button>`;$('#cq').appendChild(b);$('#cnx').onclick=()=>{sfx.tap();step(j+1)}}else ctWin(g,LT(g.feedback))},silent)};
 const opts=step(0,1);ctBind();ctGuide(g.lines||[],[LT(g.caption),LT(g.questions[0].ask),...opts])}
function gInquiry(g){const bank=CT.banks[CT.cur.payload.slug],q5=bank.items.find(x=>x.id===g.claimFromQuiz),lk=CT.cur.payload.quiz.localeKeys,loc=q5[lk[ctLang()]]||q5.en;
 const claimOpts={};Object.keys(q5.en.options).forEach(id=>claimOpts[id]={en:q5.en.options[id],fr:(q5[lk.fr]||q5.en).options[id]});
 main.innerHTML=`<div class="cscr"><p class="ctext sm">${esc(LT(g.caption))}</p><div class="cmedia">${ctTable(g.table)}</div><p class="ctext sm">${esc(LT(g.task))}</p><div id="cq"></div>${GUIDE_HTML}</div>`;
 const opts=ctChoice($('#cq'),loc.prompt,claimOpts,q5.answerKey,first=>{ctEvent({item:g.id+':claim',first});
  const b=document.createElement('div');b.className='cnav';b.innerHTML=`<button class="btn" id="cnx">${esc(UT('next'))} ▶</button>`;$('#cq').appendChild(b);
  $('#cnx').onclick=()=>{sfx.tap();ctChoice($('#cq'),UT('needToKnow'),g.next.options,g.next.key,f2=>{ctEvent({item:g.id+':next',first:f2});ctWin(g,LT(g.feedback))})}},1);
 ctBind();ctSay([LT(g.caption),LT(g.task),loc.prompt,...opts])}

/* ---- Quiz: finite bank by age band, no repeats in a round, "seen today" memory, pool-exhaustion rule ---- */
function ctQ(it){const lk=CT.cur.payload.quiz.localeKeys;return it[lk[ctLang()]]||it.en}
function ctQuizState(){const P=ctProg(),k=CT.cur.payload.slug;P[k]=P[k]||{};let q=P[k].quiz||{};const t=ctToday();
 if(q.day!==t){q={day:t,seen:{},prev:q.seen||q.prev||{}}}P[k].quiz=q;ctPutProg(P);return q}
function ctSaveQuiz(q){const P=ctProg(),k=CT.cur.payload.slug;P[k]=P[k]||{};P[k].quiz=q;ctPutProg(P)}
function ctPool(name){const Q=CT.cur.payload.quiz,bands=Q.pools[name];return CT.banks[CT.cur.payload.slug].items.filter(it=>bands.includes(it.band)&&it.status!=='withdrawn')}
/* builds a round: practice=false -> only items not yet seen today (preferring ones not seen last time); null when exhausted */
function ctBuildRound(name,practice){const Q=CT.cur.payload.quiz,n=Q.roundSize[name],pool=ctPool(name),qs=ctQuizState();
 const seen=new Set(qs.seen[name]||[]),prev=new Set(qs.prev[name]||[]);
 if(practice)return shuffle(pool).slice(0,Math.min(n,pool.length)).map(x=>x.id);
 const fresh=pool.filter(it=>!seen.has(it.id));if(fresh.length<n)return null;
 const a=shuffle(fresh.filter(it=>!prev.has(it.id))),b=shuffle(fresh.filter(it=>prev.has(it.id)));return [...a,...b].slice(0,n).map(x=>x.id)}
window.__ctBuildRound=ctBuildRound;
function cquiz(a){if(ctRequire(a,cquiz))return;ctTop(UT('quiz'));const band=ctBand();
 if(!a.pool){if(band==='little'){go('cquiz',ctA({pool:'little'}));return}
  main.innerHTML=`<div class="cscr"><div class="cmodes"><button class="cmode" data-pool="big"><i>🧭</i><b>${esc(UT('quizBig'))}</b></button><button class="cmode" data-pool="deep"><i>🔎</i><b>${esc(UT('quizDeep'))}</b><small>${esc(UT('optional'))}</small></button></div>${GUIDE_HTML}</div>`;
  main.querySelectorAll('[data-pool]').forEach(b=>b.onclick=()=>{sfx.tap();go('cquiz',ctA({pool:b.dataset.pool}))});ctBind();return}
 if(!a.round){const ids=ctBuildRound(a.pool,!!a.practice);if(!ids){ctExhausted(a);return}go('cquiz',ctA({pool:a.pool,practice:!!a.practice,round:ids,i:0}));return}
 const bank=CT.banks[CT.cur.payload.slug],it=bank.items.find(x=>x.id===a.round[a.i]),q=ctQ(it);
 const qs=ctQuizState();qs.seen[a.pool]=[...new Set([...(qs.seen[a.pool]||[]),it.id])];ctSaveQuiz(qs);CT.qcur={id:it.id,key:it.answerKey,pool:a.pool,i:a.i,round:a.round.slice(),practice:!!a.practice};
 const ids=it.shuffleOptions===false?Object.keys(q.options):shuffle(Object.keys(q.options));let tries=0,hint=false;
 main.innerHTML=`<div class="cscr cquizscr"><div class="cprog">${esc(UT('question'))} ${a.i+1} ${esc(UT('of'))} ${a.round.length}${a.practice?` · <span class="ctag">${esc(LT(CT.cur.payload.quiz.practiceLabel))}</span>`:''}</div>
  <p class="ctext" id="cqp">${esc(q.prompt)}</p><div class="cnav"><button class="say" id="csay" aria-label="${esc(UT('readAloud'))}">🔊</button><button class="cbtn2" id="chelp">? ${esc(UT('hint'))}</button></div>
  <div class="copts">${ids.map(id=>`<button class="copt" data-o="${id}">${esc(q.options[id])}</button>`).join('')}</div>
  <p class="cfb hint hide" id="chintline"></p><div id="cafter"></div>${GUIDE_HTML}</div>`;
 const next=()=>{if(a.i+1<a.round.length)go('cquiz',ctA({pool:a.pool,practice:a.practice,round:a.round,i:a.i+1}));else go('cdone',ctA({mode:'quiz',pool:a.pool}))};
 const showSkip=()=>{if($('#cskip'))return;$('#cafter').innerHTML=`<div class="cnav"><button class="cbtn2" id="cskip">${esc(UT('skip'))} ▶</button></div>`;$('#cskip').onclick=()=>{sfx.tap();ctEvent({item:it.id,skipped:true,repeat:!!a.practice});next()}};
 main.querySelectorAll('.copt').forEach(b=>b.onclick=()=>{if(b.disabled)return;
  if(b.dataset.o===it.answerKey){sfx.right();b.classList.add('ok');main.querySelectorAll('.copt').forEach(x=>x.disabled=true);ctEvent({item:it.id,first:tries===0&&!hint,supported:tries>0||hint,repeat:!!a.practice});
   $('#chintline').classList.add('hide');$('#cafter').innerHTML=`<p class="cfb ok">✓ ${esc(q.feedback)}</p><div class="cnav"><button class="btn" id="cnx">${esc(UT(a.i+1<a.round.length?'next':'done'))} ▶</button></div>`;$('#cnx').onclick=()=>{sfx.tap();next()};
   ctGuide(['ari.cm.correct'],[q.feedback])}
  else{tries++;b.classList.add('no');b.disabled=true;ctHint(q.hint);showSkip()}});
 $('#csay').onclick=()=>{ctHideGuide();ctSay([q.prompt,...ids.map(id=>q.options[id])])};
 $('#chelp').onclick=()=>{hint=true;ctHint(q.hint);showSkip()};
 ctBind();const opts=ids.map(id=>q.options[id]);ctSay(band==='little'?[q.prompt,...opts]:[q.prompt]);
 if(a.i+1<a.round.length){const nx=ctQ(bank.items.find(x=>x.id===a.round[a.i+1]));warmVoice([nx.prompt],0)}}
function ctExhausted(a){const Q=CT.cur.payload.quiz;ctTop(UT('quiz'));
 main.innerHTML=`<div class="cscr cexh"><img class="cbigari" src="img/world/guides/ari-thumbs.webp" alt="Ari"><p class="ctext" id="cexh">${esc(LT(Q.exhausted))}</p>
  <div class="cmodes one"><button class="cmode" id="cfinish"><i>🏁</i><b>${esc(LT(Q.finish))}</b></button><button class="cmode" id="cpractise"><i>🔁</i><b>${esc(LT(Q.practise))}</b></button></div>${GUIDE_HTML}</div>`;
 $('#cfinish').onclick=()=>{sfx.tap();go('cdone',ctA({mode:'quiz',pool:a.pool}))};
 $('#cpractise').onclick=()=>{sfx.tap();go('cquiz',ctA({pool:a.pool,practice:true}))};ctBind();ctSay([LT(Q.exhausted)])}

/* ---- Stories: page-by-page reader (Little = 5 pages, Big = 8 for S2), ungraded reflection, nothing saved ---- */
function cstory(a){if(ctRequire(a,cstory))return;ctTop(UT('stories'));const S=CT.cur.payload.stories;
 main.innerHTML=`<div class="cscr"><div class="cmodes one">${S.map((s,i)=>`<button class="cmode cstorybtn" data-s="${i}"><i>${i?'🦅':'📖'}</i><b>${esc(LT(s.title))}</b><small>${esc(LT(s.banner))}</small></button>`).join('')}</div>${GUIDE_HTML}</div>`;
 main.querySelectorAll('.cstorybtn').forEach(b=>b.onclick=()=>{sfx.tap();go('cread',ctA({s:+b.dataset.s,i:0}))});ctBind();
 const key='stories:'+ctLang();ctGuide(CT.shownLines.has(key)?[]:['ari.cm.story']);CT.shownLines.add(key)}
function ctPages(s){const b=ctBand();return s.pages.all||s.pages[b]||s.pages.little}
function ctRefl(s){return s.reflection.all||s.reflection[ctBand()]||s.reflection.little}
function ctStoryArt(scene){const m={'plan-key':()=>ctGrid({highlight:'library'}),'plan-north':()=>ctGrid({arrow:'n',pos:[1,1]}),'plan-paths':()=>ctTable(CT.cur.payload.media.count.rows),
  's2-1':()=>'<img class="cstoryimg" src="img/world/guides/ezra-carry.webp" alt="">','s2-2':()=>ctScene('coast')+ctScene('forest'),'s2-3':()=>ctScene('grassland')+ctScene('mountain'),
  's2-4':()=>'<img class="cstoryimg sm" src="img/world/guides/ari-think.webp" alt=""><img class="cstoryimg sm" src="img/world/guides/ezra-face.webp" alt="">','s2-5':()=>ctGrid({highlight:'library'}),
  's2-6':()=>'<div class="cplace"><i>📚</i></div>','s2-7':()=>'<div class="cplace"><i>📝</i></div>','s2-8':()=>'<img class="cstoryimg sm" src="img/world/guides/ari-thumbs.webp" alt="">'};
 return `<div class="cmedia cstoryart">${(m[scene]||(()=>''))()}${PH()}</div>`}
function cread(a){if(ctRequire(a,cread))return;const s=CT.cur.payload.stories[a.s];if(!s){go('cstory',ctA());return}const pages=ctPages(s),n=pages.length,i=a.i||0;ctTop(UT('stories'));
 if(i>=n){const r=LT(ctRefl(s));main.innerHTML=`<div class="cscr"><div class="cbanner">${esc(LT(s.banner))}</div><img class="cbigari" src="img/world/guides/ari-think.webp" alt="Ari"><p class="ctext" id="ctext">${esc(r)}</p>
   <div class="cnav"><button class="cbtn2" id="cprev">◀ ${esc(UT('prev'))}</button><button class="say" id="csay" aria-label="${esc(UT('replay'))}">🔊</button><button class="cbtn2" id="cskip">${esc(UT('skip'))}</button><button class="btn" id="cfin">${esc(UT('done'))} ✓</button></div>${GUIDE_HTML}</div>`;
  $('#cprev').onclick=()=>{sfx.tap();go('cread',ctA({s:a.s,i:n-1}))};$('#csay').onclick=()=>ctSay([r]);
  const fin=()=>{sfx.tap();go('cdone',ctA({mode:'stories'}))};$('#cfin').onclick=fin;$('#cskip').onclick=fin;ctBind();ctSay([r]);return}
 const p=pages[i],t=LT(p.text);
 main.innerHTML=`<div class="cscr cstory"><h2 class="cstitle">${esc(LT(s.title))}</h2><div class="cbanner">${esc(LT(s.banner))}</div><div class="cprog">${esc(UT('page'))} ${i+1} / ${n}</div>${ctStoryArt(p.scene)}<p class="ctext story" id="ctext">${esc(t)}</p>
  <div class="cnav"><button class="cbtn2" id="cprev"${i?'':' disabled'}>◀ ${esc(UT('prev'))}</button><button class="say" id="csay" aria-label="${esc(UT('replay'))}">🔊</button><button class="btn" id="cnext">${esc(UT('next'))} ▶</button></div>${GUIDE_HTML}</div>`;
 $('#cprev').onclick=()=>{sfx.tap();go('cread',ctA({s:a.s,i:i-1}))};$('#cnext').onclick=()=>{sfx.tap();go('cread',ctA({s:a.s,i:i+1}))};$('#csay').onclick=()=>ctSay([t]);
 ctBind();ctSay([t]);if(i+1<n)warmVoice([LT(pages[i+1].text)],0)}

/* ---- Done card: Ari + Ezra lines, quiet "visited" stamp once, back to hub or fly home ---- */
function cdone(a){if(ctRequire(a,cdone))return;ctTop(LT(CT.cur.payload.name));const first=ctStamp();
 const again={learn:['clearn',{}],play:['cplay',{}],quiz:['cquiz',{pool:a.pool}],stories:['cstory',{}]}[a.mode]||['ctry',{}];
 main.innerHTML=`<div class="cscr cdone"><img class="cbigari" src="img/world/guides/ari-cheer.webp" alt="Ari">${first?`<div class="cstamp big">🏅 ${esc(UT('visited'))}</div>`:''}
  <div class="cmodes one"><button class="cmode" id="cagain2"><i>↻</i><b>${esc(UT('again'))}</b></button><button class="cmode" id="chub"><i>🏠</i><b>${esc(UT('hub'))}</b></button><button class="cmode" id="cfly"><i>🦅</i><b>${esc(UT('flyHome'))}</b></button></div>${GUIDE_HTML}</div>`;
 $('#cagain2').onclick=()=>{sfx.tap();go(again[0],ctA(again[1]))};$('#chub').onclick=()=>{sfx.tap();go('ctry',ctA())};
 $('#cfly').onclick=()=>{sfx.tap();CT.enteredAt=0;go('home');const l=ctLine('ezra.home');if(ctPrefs().guide)setTimeout(()=>{if(screen==='home'){mascot(l.text);ctSay([l.text])}},50)};
 ctBind();ctGuide(['ari.cm.done','ezra.celebrate'])}

/* ---- wiring into the app router + back button ---- */
Object.assign(XSCREENS,{ctry,clearn,cplay,cgame,cquiz,cstory,cread,cdone});
Object.assign(XBACK,{ctry:()=>{CT.enteredAt=0;go('land',{id:(CT.cur&&CT.cur.tags.land)||'world'})},clearn:()=>go('ctry',ctA()),cplay:()=>go('ctry',ctA()),cquiz:()=>go('ctry',ctA()),cstory:()=>go('ctry',ctA()),cdone:()=>go('ctry',ctA()),
 cgame:()=>go('cplay',ctA()),cread:()=>go('cstory',ctA())});
