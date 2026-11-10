"""Cameroon pilot test (World Land country pack, portrait 390x844 + 360x780):  python3 tools/test_cameroon.py [shots_dir]
World Land -> Cameroon -> age choice -> hub with 4 full-screen modes (Learn / Play / Quiz / Stories) in BOTH age bands:
every Learn card (L1-L6b little, B1a-B9 big) shows the exact pack text, all 7 Play activities are played to the end,
quiz rounds draw only from the band's pool with no repeat inside a round, options are shuffled but the key stays bound
to the option id, the pool-exhaustion rule (Finish / Practise again -> labelled practice repeat) works, stories page through,
English/French switch changes the text, Ari/Ezra lines are exactly the pack lines, back navigation, every spoken line has
a recorded clip, no console errors; then one online visit -> OFFLINE reload -> Cameroon still works from the service worker.
Phone screenshots go to shots_dir (default /workspace/cameroon-pilot-shots)."""
import asyncio,threading,functools,http.server,sys,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/cameroon-pilot-shots');OUT.mkdir(parents=True,exist_ok=True)
PK=json.load(open(ROOT/'content/countries/cameroon.json'));BANK=json.load(open(ROOT/'content/countries/cameroon-quiz.json'))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def handle(self):
        try:super().handle()
        except Exception:pass
fails=[]
def ok(c,m):
    print(('OK   ' if c else 'FAIL ')+m,flush=True)
    if not c:fails.append(m)
async def scr(pg,name,t=5000):
    try:await pg.wait_for_function(f"screen==='{name}'",timeout=t)
    except Exception:pass
    return await pg.evaluate('screen')
async def shot(pg,name,vw):
    if vw==390:await pg.wait_for_timeout(250);await pg.screenshot(path=str(OUT/name),full_page=True)
OVER="""()=>{const W=innerWidth,bad=[];document.querySelectorAll('#main button,#main p,#main .cmedia,#main table').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width)return;if(r.left<-2||r.right>W+2)bad.push((e.id||e.className||e.tagName)+' '+Math.round(r.left)+'-'+Math.round(r.right))});
 const small=[...document.querySelectorAll('#main button')].filter(b=>{const r=b.getBoundingClientRect();return r.width&&b.offsetParent&&!b.disabled&&(r.width<47.5||r.height<47.5)}).map(b=>(b.id||b.className)+' '+Math.round(b.getBoundingClientRect().width)+'x'+Math.round(b.getBoundingClientRect().height));
 return {sw:document.documentElement.scrollWidth,W,bad:bad.slice(0,5),small:small.slice(0,5),broken:[...document.images].filter(i=>i.getAttribute('src')&&i.complete&&!i.naturalWidth).map(i=>i.src)}}"""
async def layout(pg,tag):
    r=await pg.evaluate(OVER)
    ok(r['sw']<=r['W']+1 and not r['bad'],f'{tag}: no horizontal overflow {r["bad"]}')
    ok(not r['small'],f'{tag}: child buttons >= 48px {r["small"]}')
    ok(not r['broken'],f'{tag}: images load {r["broken"][:3]}')
def L(o,lang='en'):return o[lang] if isinstance(o,dict) else o
async def hub(pg):
    await pg.evaluate("go('ctry',{c:'cameroon'})");await scr(pg,'ctry')
async def set_age(pg,age):
    await hub(pg);await pg.click(f'.cagebtn[data-age="{age}"]');await scr(pg,'ctry')
async def answer_quiz_round(pg,tag,wrong_first=False):
    """answers every question of the current round; returns the item ids seen"""
    ids=[]
    for _ in range(12):
        s=await pg.evaluate('screen')
        if s!='cquiz' or not await pg.query_selector('.copt'):break
        q=await pg.evaluate('CT.qcur');ids.append(q['id'])
        if wrong_first and len(ids)==1:
            w=await pg.evaluate(f"[...document.querySelectorAll('.copt')].map(b=>b.dataset.o).find(o=>o!=='{q['key']}')")
            await pg.click(f'.copt[data-o="{w}"]');await pg.wait_for_timeout(150)
            ok(await pg.is_visible('#chintline') and await pg.is_visible('#cskip'),f'{tag}: wrong answer shows hint + Skip')
            item=[x for x in BANK['items'] if x['id']==q['id']][0]
            ok((await pg.text_content('#chintline')).strip()==item['en']['hint'],f'{tag}: hint text is the bank hint')
            ok(await pg.is_disabled(f'.copt[data-o="{w}"]'),f'{tag}: wrong option disabled (supported retry)')
        await pg.click(f'.copt[data-o="{q["key"]}"]');await pg.wait_for_selector('#cnx')
        fb=(await pg.text_content('.cfb.ok')).strip();item=[x for x in BANK['items'] if x['id']==q['id']][0]
        if len(ids)==1:ok(item['en']['feedback'] in fb or item['fr_draft_pending_fluent_review']['feedback'] in fb,f'{tag}: correct shows item feedback')
        await pg.click('#cnx');await pg.wait_for_timeout(120)
    return ids
async def online(b,url,vw,vh):
    print(f'--- online {vw}x{vh}')
    ctx=await b.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append('PAGEERR '+str(e)));pg.on('console',lambda m:m.type=='error' and errs.append('CONSOLE '+m.text))
    await pg.goto(url,wait_until='load');await pg.evaluate('localStorage.clear()');await pg.reload(wait_until='load')
    await pg.wait_for_function('LANDS!==null&&screen==="home"&&window.CTRY_READY',timeout=20000)
    # World Land shows the Cameroon place (data-driven from lands.json) and the old activities still exist
    await pg.click('.wsignb[data-l="world"]');await scr(pg,'land')
    ok(await pg.is_visible('.wplace[data-p="cameroon"]'),f'{vw}: World Land has a Cameroon place')
    ok(await pg.is_visible('.wplace[data-p="countries"]') and await pg.is_visible('.wplace[data-p="flagquiz"]'),f'{vw}: Country Cards + Flag Quiz still there')
    await shot(pg,'01-world-land.png',vw)
    await pg.click('.wplace[data-p="cameroon"]');ok(await scr(pg,'ctry')=='ctry',f'{vw}: Cameroon opens')
    ok(await pg.is_visible('.cage[data-age="little"]') and await pg.is_visible('.cage[data-age="big"]'),f'{vw}: first visit asks Little 5-7 / Big 8-13')
    await shot(pg,'02-age-choice.png',vw)
    await pg.click('.cage[data-age="little"]');await scr(pg,'ctry');await pg.wait_for_selector('.cmode[data-mode="learn"]')
    modes=await pg.evaluate("[...document.querySelectorAll('.cmodes .cmode')].map(b=>b.dataset.mode)");ok(modes==['learn','play','quiz','stories'],f'{vw}: hub has exactly 4 modes {modes}')
    bubs=await pg.evaluate("[...document.querySelectorAll('#cguide .cbub')].map(b=>b.dataset.line+'|'+b.textContent.trim())")
    want=[f"ezra.fly|Ezra {PK['payload']['lines']['ezra.fly']['text']['en']}",f"ari.cm.arrive|Ari {PK['payload']['lines']['ari.cm.arrive']['text']['en']}"]
    ok(bubs==want,f'{vw}: arrival bubbles are the exact Ezra + Ari lines {bubs}')
    ok(await pg.is_visible('#title') and (await pg.text_content('#title')).strip()=='Cameroon','hub title')
    await layout(pg,f'{vw} hub');await shot(pg,'03-cameroon-hub-little.png',vw)
    await pg.click('#cguide .cbub');ok(await pg.evaluate("document.querySelector('#cguide').classList.contains('hide')"),f'{vw}: tapping Ari bubble skips it')
    for band in ['little','big']:
        await set_age(pg,band);tag=f'{vw} {band}'
        # ---- Learn: every card, exact text, Next/Back
        await pg.click('.cmode[data-mode="learn"]');ok(await scr(pg,'clearn')=='clearn',f'{tag}: Learn opens full screen')
        cards=PK['payload']['learn'][band]['cards'];ok(len(cards)==(9 if band=='little' else 17),f'{tag}: {len(cards)} learn screens')
        got=[]
        for i,c in enumerate(cards):
            got.append((await pg.text_content('#ctext')).strip())
            if i==0:await layout(pg,f'{tag} learn');await shot(pg,f'04-learn-{band}-{c["id"]}.png',vw)
            if c['id'] in ('L6b',):
                await shot(pg,'05-learn-little-L6b-try.png',vw)
                await pg.click('.cmedia .cdir-btn[data-d="n"]');await pg.wait_for_timeout(150)
                ok(await pg.evaluate("document.querySelector('.cmedia').classList.contains('cwin')"),f'{tag}: L6b north button reaches the library')
            if c['id']=='B9':ok('11' in await pg.text_content('.cprog'),f'{tag}: B9 is marked as optional 11-13')
            if i==1:await pg.click('#cprev');await pg.wait_for_timeout(100);ok((await pg.text_content('#ctext')).strip()==L(cards[0]['text']),f'{tag}: Back goes to previous card');await pg.click('#cnext');await pg.wait_for_timeout(100)
            await pg.click('#cnext');await pg.wait_for_timeout(90)
        ok(got==[L(c['text']) for c in cards],f'{tag}: every Learn card shows exactly the pack text')
        ok(await scr(pg,'cdone')=='cdone',f'{tag}: Learn ends on the Done card')
        bub=await pg.evaluate("[...document.querySelectorAll('#cguide .cbub')].map(b=>b.dataset.line)");ok(bub==['ari.cm.done','ezra.celebrate'],f'{tag}: done card lines {bub}')
        if band=='little':await shot(pg,'06-done-card.png',vw)
        await pg.click('#chub');await scr(pg,'ctry')
        # ---- Play
        await pg.click('.cmode[data-mode="play"]');ok(await scr(pg,'cplay')=='cplay',f'{tag}: Play opens')
        gs=await pg.evaluate("[...document.querySelectorAll('.cgamebtn')].map(b=>b.dataset.g)")
        ok(gs==(['P1','P2','P3'] if band=='little' else ['P4','P5','P6','P7']),f'{tag}: play list {gs}')
        await layout(pg,f'{tag} play list')
        for g in gs:
            await pg.evaluate(f"go('cgame',{{c:'cameroon',g:'{g}'}})");await scr(pg,'cgame');await pg.wait_for_timeout(150);await layout(pg,f'{tag} {g}')
            await shot(pg,f'07-play-{g}.png',vw)
            if g in('P1','P4'):
                if g=='P1':
                    await pg.click('.cdir-btn[data-d="s"]');await pg.click('.cdir-btn[data-d="s"]')
                    ok('edge' in (await pg.text_content('#chintline')) or 'bord' in (await pg.text_content('#chintline')),'P1: leaving the map gives the edge line')
                    await pg.click('#cundo');await pg.click('#cundo');await pg.click('.cdir-btn[data-d="n"]')
                else:
                    for d in 'wwnne':await pg.click(f'.cdir-btn[data-d="{d}"]')  # a longer valid route (W,W,N,N,E from the school) must also be accepted
                    ok((await pg.text_content('#cmv')).strip()=='5','P4: moves are counted')
                ok(await pg.is_visible('.cwinbox'),f'{g}: route reaches the library and is accepted')
                if g=='P4':ok('3 moves' in await pg.text_content('.cwinbox'),'P4: shorter-route comparison shown (no penalty)')
            elif g=='P2':
                await pg.click('.cpiece[data-p="yellow"]');await pg.click('.cslot[data-s="0"]')
                ok(await pg.is_visible('#chintline') and 'Green goes first' in await pg.text_content('#chintline'),'P2: wrong stripe gives the spec hint')
                await pg.click('#cwords');ok(await pg.evaluate("document.querySelector('#cwords').getAttribute('aria-pressed')")=='true','P2: colour-word overlay toggles')
                for p,s in [('green',0),('red',1),('yellow',2),('star',1)]:await pg.click(f'.cpiece[data-p="{p}"]');await pg.click(f'.cslot[data-s="{s}"]')
                ok(await pg.is_visible('.cflagbuild svg.cflag') and await pg.is_visible('.cwinbox'),'P2: flag built, true flag shown')
                await shot(pg,'07-play-P2-done.png',vw)
            elif g=='P3':
                ids=await pg.evaluate("[...document.querySelectorAll('.cpic')].map(b=>b.dataset.p)")
                await pg.click(f'.cpic[data-p="{ids[0]}"]');other=[x for x in ids if x!=ids[0]][0];await pg.click(f'.cname2[data-n="{other}"]')
                ok(not await pg.query_selector('.cpic.ok'),'P3: wrong match is not accepted')
                for i in ids:await pg.click(f'.cpic[data-p="{i}"]');await pg.click(f'.cname2[data-n="{i}"]')
                ok(await pg.evaluate("document.querySelectorAll('.cpic.ok').length")==4 and await pg.is_visible('.cwinbox'),'P3: all four places matched')
            elif g=='P5':
                pr=PK['payload']['play'][4]
                for k in range(len(pr['prompts'])):
                    ask=(await pg.text_content('#cask')).strip();p=[x for x in pr['prompts'] if x['ask']['en']==ask][0]
                    if k==0:
                        wrong=[n['id'] for n in pr['neighbours'] if n['id'] not in p['accept']][0];await pg.click(f'.cnb[data-n="{wrong}"]')
                        ok('Northwest is between' in await pg.text_content('#chintline'),'P5: wrong neighbour gives the compass hint')
                    await pg.click(f'.cnb[data-n="{p["accept"][-1]}"]')
                    if k<len(pr['prompts'])-1:await pg.click('#cnx')
                ok(await pg.is_visible('.cwinbox'),'P5: all five direction prompts answered (south accepts Gabon or Equatorial Guinea)')
            elif g in('P6','P7'):
                for _ in range(2):
                    await pg.wait_for_selector('.copt:not([disabled])');keys=['a']
                    await pg.click('.copt[data-o="a"]')
                    if await pg.query_selector('#cnx'):await pg.click('#cnx')
                ok(await pg.is_visible('.cwinbox'),f'{g}: both steps answered, feedback shown')
                if g=='P6':ok('4,095 m' in await pg.text_content('.ctable') and '4,070 m' in await pg.text_content('.ctable'),'P6: only the two sourced heights are shown')
            await pg.click('#cfin');ok(await scr(pg,'cdone')=='cdone',f'{g}: Done -> done card')
        # ---- Quiz: band pool, no repeat in a round, shuffle, exhaustion
        await hub(pg);await pg.click('.cmode[data-mode="quiz"]');ok(await scr(pg,'cquiz')=='cquiz',f'{tag}: Quiz opens')
        pools=['little'] if band=='little' else ['big','deep']
        for pool in pools:
            await pg.evaluate("(()=>{const P=JSON.parse(localStorage.emmaCtry||'{}');if(P.cameroon)delete P.cameroon.quiz;localStorage.emmaCtry=JSON.stringify(P)})()")
            await pg.evaluate("go('cquiz',{c:'cameroon'})")
            if band=='big':await pg.wait_for_selector('[data-pool]');await shot(pg,'08-quiz-choose-big.png',vw);await pg.click(f'[data-pool="{pool}"]')
            await pg.wait_for_selector('.copt');await layout(pg,f'{tag} quiz {pool}');await shot(pg,f'09-quiz-question-{pool}.png',vw)
            bands={'little':['5-7'],'big':['8-10'],'deep':['11-13']}[pool];n={'little':4,'big':5,'deep':5}[pool];poolsize=sum(1 for x in BANK['items'] if x['band'] in bands)
            ids=await answer_quiz_round(pg,f'{tag} quiz {pool}',wrong_first=True)
            ok(len(ids)==n and len(set(ids))==n,f'{tag} quiz {pool}: round of {n} with no repeats {ids}')
            ok(all([x for x in BANK['items'] if x['id']==i][0]['band'] in bands for i in ids),f'{tag} quiz {pool}: only {bands} items')
            ok(await scr(pg,'cdone')=='cdone',f'{tag} quiz {pool}: round ends on done card')
            seen=set(ids)
            while poolsize-len(seen)>=n:   # more fresh rounds while enough unseen items remain
                await pg.click('#cagain2');await pg.wait_for_selector('.copt');r=await answer_quiz_round(pg,f'{tag} quiz {pool} r');ok(not seen&set(r),f'{tag} quiz {pool}: later round uses unseen items only');seen|=set(r)
            await pg.click('#cagain2');await pg.wait_for_timeout(200)
            ok(await pg.is_visible('#cexh') and (await pg.text_content('#cexh')).strip()==PK['payload']['quiz']['exhausted']['en'],f'{tag} quiz {pool}: pool exhaustion message ({poolsize} items, {len(seen)} seen)')
            ok(await pg.is_visible('#cfinish') and await pg.is_visible('#cpractise'),f'{tag} quiz {pool}: Finish + Practise again buttons')
            if pool!='deep':await shot(pg,f'10-quiz-exhausted-{pool}.png',vw)
            await pg.click('#cpractise');await pg.wait_for_selector('.copt')
            ok('Practice repeat' in await pg.text_content('.cprog'),f'{tag} quiz {pool}: repeat round labelled "Practice repeat"')
            r=await answer_quiz_round(pg,f'{tag} quiz {pool} practice');ok(len(r)==len(set(r))==min(n,poolsize),f'{tag} quiz {pool}: practice round has no repeats')
            ev=await pg.evaluate("JSON.parse(localStorage.emmaCtry).events.filter(e=>e.repeat).length");ok(ev>=len(r),f'{tag} quiz {pool}: practice answers recorded as repeats')
            await pg.click('#cagain2');await pg.wait_for_timeout(150);await pg.click('#cfinish');ok(await scr(pg,'cdone')=='cdone','Finish -> done card')
        # ---- Stories
        await hub(pg);await pg.click('.cmode[data-mode="stories"]');ok(await scr(pg,'cstory')=='cstory',f'{tag}: Stories opens')
        ok(await pg.evaluate("document.querySelectorAll('.cstorybtn').length")==2,f'{tag}: two stories')
        for si,st in enumerate(PK['payload']['stories']):
            await pg.click(f'.cstorybtn[data-s="{si}"]');await scr(pg,'cread');pages=st['pages'].get('all') or st['pages'][band]
            texts=[]
            for i in range(len(pages)):
                texts.append((await pg.text_content('#ctext')).strip())
                if i==0 and si==1:await layout(pg,f'{tag} story');await shot(pg,f'11-story-S2-{band}-p1.png',vw)
                await pg.click('#cnext');await pg.wait_for_timeout(80)
            ok(texts==[p['text']['en'] for p in pages],f'{tag}: story {si+1} shows all {len(pages)} pages in order')
            refl=st['reflection'].get('all') or st['reflection'][band]
            ok((await pg.text_content('#ctext')).strip()==refl['en'],f'{tag}: story {si+1} ends with the ungraded reflection')
            await pg.click('#cskip');await scr(pg,'cdone');await pg.evaluate("go('cstory',{c:'cameroon'})");await scr(pg,'cstory')
    # ---- language switch (hub + learn + quiz + story), French screenshots
    await set_age(pg,'little');await pg.click('.clang[data-lang="fr"]');await scr(pg,'ctry');await pg.wait_for_timeout(150)
    lab=await pg.evaluate("[...document.querySelectorAll('.cmodes .cmode b')].map(b=>b.textContent)");ok(lab==['Apprendre','Jouer','Quiz','Histoires'],f'{vw}: French mode labels {lab}')
    ok((await pg.text_content('#title')).strip()=='Cameroun' and await pg.evaluate("main.getAttribute('lang')")=='fr','French title + lang=fr')
    await shot(pg,'12-french-hub.png',vw)
    await pg.click('.cmode[data-mode="learn"]');await scr(pg,'clearn');ok((await pg.text_content('#ctext')).strip()==PK['payload']['learn']['little']['cards'][0]['text']['fr'],f'{vw}: French Learn card text')
    bub=await pg.evaluate("[...document.querySelectorAll('#cguide .cbub')].map(b=>b.textContent)");ok(any(PK['payload']['lines']['ari.cm.learn']['text']['fr'] in x for x in bub),f'{vw}: Ari speaks the French line')
    ok(await pg.evaluate("ttsLangFor(document.querySelector('#ctext').textContent)")=='fr-FR','French text uses a French voice fallback')
    await shot(pg,'13-french-learn.png',vw)
    await pg.evaluate("(()=>{const P=JSON.parse(localStorage.emmaCtry||'{}');delete P.cameroon.quiz;localStorage.emmaCtry=JSON.stringify(P)})()")
    await pg.evaluate("go('cquiz',{c:'cameroon'})");await pg.wait_for_selector('.copt');q=await pg.evaluate('CT.qcur');item=[x for x in BANK['items'] if x['id']==q['id']][0]
    ok((await pg.text_content('#cqp')).strip()==item['fr_draft_pending_fluent_review']['prompt'],f'{vw}: French quiz prompt')
    txt=await pg.text_content(f'.copt[data-o="{q["key"]}"]');ok(txt.strip()==item['fr_draft_pending_fluent_review']['options'][q['key']],'French key option bound to the same option id')
    await shot(pg,'14-french-quiz.png',vw)
    await pg.evaluate("go('cread',{c:'cameroon',s:0,i:0})");await scr(pg,'cread');ok((await pg.text_content('#ctext')).strip()==PK['payload']['stories'][0]['pages']['all'][0]['text']['fr'],f'{vw}: French story page')
    await shot(pg,'15-french-story.png',vw)
    await hub(pg);await pg.click('.clang[data-lang="en"]');await scr(pg,'ctry');ok((await pg.text_content('.cmode[data-mode="learn"] b')).strip()=='Learn',f'{vw}: back to English')
    # ---- guide off, back navigation, quiz engine properties
    await pg.click('#cguideTog');await scr(pg,'ctry');await pg.click('.cmode[data-mode="learn"]');await scr(pg,'clearn')
    ok(await pg.evaluate("document.querySelector('#cguide').classList.contains('hide')"),f'{vw}: Ari talks off hides guide lines');await hub(pg);await pg.click('#cguideTog')
    await pg.evaluate("go('cgame',{c:'cameroon',g:'P1'})");await scr(pg,'cgame')
    await pg.click('#backBtn');ok(await scr(pg,'cplay')=='cplay','header back: game -> play list')
    await pg.evaluate('emmaBack()');ok(await scr(pg,'ctry')=='ctry','emmaBack: play list -> Cameroon hub')
    await pg.go_back();ok(await scr(pg,'land')=='land' and await pg.evaluate('curLand')=='world','browser back: hub -> World Land')
    await pg.click('.wplace[data-p="cameroon"]');await scr(pg,'ctry')
    bubs=await pg.evaluate("[...document.querySelectorAll('#cguide .cbub')].map(b=>b.dataset.line)");ok(bubs==['ezra.fly','ari.cm.arrive-again'],f'later visit says "Welcome back" {bubs}')
    if vw==390:
        res=await pg.evaluate("""()=>{const out={dup:0,band:0,n:0,orders:new Set()};const bank=CT.banks.cameroon.items;
          for(const pool of ['little','big','deep']){const bands=CT.cur.payload.quiz.pools[pool];for(let k=0;k<300;k++){const P=JSON.parse(localStorage.emmaCtry||'{}');delete P.cameroon.quiz;localStorage.emmaCtry=JSON.stringify(P);
            const r=__ctBuildRound(pool,k%2===1);out.n++;if(new Set(r).size!==r.length)out.dup++;if(r.some(id=>!bands.includes(bank.find(x=>x.id===id).band)))out.band++}}
          for(let k=0;k<40;k++){go('cquiz',{c:'cameroon',pool:'little',practice:true,round:['ew.quiz.pilot-cameroon-q07'],i:0});out.orders.add([...document.querySelectorAll('.copt')].map(b=>b.dataset.o).join(''))}
          return {dup:out.dup,band:out.band,n:out.n,orders:out.orders.size}}""")
        ok(res['dup']==0 and res['band']==0,f"quiz engine: {res['n']} random rounds, no repeats inside a round, never outside the band")
        ok(res['orders']>=3,f"answer options are shuffled at display ({res['orders']} different orders in 40 renders)")
        # day rollover: yesterday's items are avoided when possible
        r=await pg.evaluate("""()=>{const P=JSON.parse(localStorage.emmaCtry||'{}');P.cameroon.quiz={day:'2000-01-01',seen:{big:['ew.quiz.pilot-cameroon-q03','ew.quiz.pilot-cameroon-q04','ew.quiz.pilot-cameroon-q12','ew.quiz.pilot-cameroon-q13','ew.quiz.pilot-cameroon-q14']},prev:{}};localStorage.emmaCtry=JSON.stringify(P);
          return __ctBuildRound('big',false)}""")
        ok(r is not None and len(r)==5 and not set(r)&{'ew.quiz.pilot-cameroon-q03','ew.quiz.pilot-cameroon-q04','ew.quiz.pilot-cameroon-q12','ew.quiz.pilot-cameroon-q13','ew.quiz.pilot-cameroon-q14'},f'new day: fresh round prefers items not seen last session {r}')
        # every spoken Cameroon line (EN + FR) has a recorded clip
        miss=await pg.evaluate("async()=>{const m=[];for(const t of __ctryVoice()){const r=await fetch(voiceUrl(t),{method:'HEAD'});if(!r.ok)m.push(t)}return m}")
        ok(not miss,f'every Cameroon line has a voice clip ({len(miss)} missing {miss[:2]})')
        priv=await pg.evaluate("Object.keys(localStorage)");ok(set(priv)<= {'emmaCtry','emmaCtryPrefs','emmaWorld','emmaStars','emmaLevels','emmaVoice','emmaVoiceOff','emmaParentPin','emmaMuted','emmaMute'} ,f'only app keys in local storage {priv}')
        ev=await pg.evaluate("JSON.parse(localStorage.emmaCtry).events.slice(0,3)");ok(all(set(e)<= {'item','first','supported','repeat','skipped','activity','moves'} for e in ev),f'practice events hold no personal data {ev}')
    ok(not errs,f'{vw}: no JS/console errors {errs[:4]}')
    await ctx.close()
async def offline(b,url):
    print('--- offline 412x915')
    ctx=await b.new_context(viewport={'width':412,'height':915},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    net=[];on={'x':False};errs=[]
    pg.on('response',lambda r:on['x'] and r.url.startswith(url) and not r.from_service_worker and net.append(r.url));pg.on('pageerror',lambda e:errs.append(str(e)))
    await pg.goto(url,wait_until='load')
    info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();for(;;){const sw=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(sw.match(/ASSETS=(\\[.*?\\]);/)[1]);
      let have=0;for(const k of (await caches.keys()).filter(k=>k.startsWith('emma-house-')))have+=(await (await caches.open(k)).keys()).length;
      if(have>=want.length&&navigator.serviceWorker.controller)return {have,want:want.length,ctry:want.filter(u=>/content\\/countries|country\\.|guides\\//.test(u)).length,ms:Date.now()-t0};if(Date.now()-t0>300000)return {timeout:true};await new Promise(z=>setTimeout(z,1000))}}""")
    print('  precache',info);ok(not info.get('timeout') and info.get('ctry',0)>=12,f'precache finished incl. Cameroon files ({info.get("ctry")})')
    await ctx.set_offline(True);on['x']=True;await pg.reload(wait_until='load');await pg.wait_for_function('LANDS!==null&&screen==="home"&&window.CTRY_READY',timeout=15000)
    await pg.evaluate("localStorage.setItem('emmaCtryPrefs',JSON.stringify({lang:'en',age:'big',guide:true}))")
    res=await pg.evaluate("""async()=>{const bad=[];const w=()=>new Promise(z=>setTimeout(z,250));
      for(const [s,a] of [['ctry',{}],['clearn',{i:0}],['cplay',{}],['cgame',{g:'P5'}],['cgame',{g:'P6'}],['cquiz',{pool:'big'}],['cstory',{}],['cread',{s:1,i:0}]]){go(s,Object.assign({c:'cameroon'},a));await w();
        if(screen!==s&&!(s==='cquiz'))bad.push('screen '+s+' -> '+screen);[...document.images].filter(i=>i.getAttribute('src')&&i.complete&&!i.naturalWidth).forEach(i=>bad.push(i.src))}
      for(const t of __ctryVoice()){try{const r=await fetch(voiceUrl(t));if(!r.ok)bad.push(t)}catch(e){bad.push(t)}}return bad}""")
    ok(not res,f'offline: Cameroon screens, pictures and every voice clip load {res[:3]}')
    await pg.screenshot(path=str(OUT/'16-offline-story.png'))
    ok(not net,f'offline: no network requests {net[:3]}');ok(not errs,f'offline: no errors {errs[:3]}')
    await ctx.close()
def spec_check():
    """optional: every pack string must appear verbatim in the reviewed spec (only on a machine that has the blueprint)"""
    p=Path(os.environ.get('CM_SPEC','/workspace/world-blueprint/13-cameroon-complete-pilot.md'))
    if not p.exists():print('SKIP spec text check (no blueprint file)');return
    spec=open(p).read().replace('’',"'")
    P=PK['payload'];strs=[]
    for k,l in P['lines'].items():strs+= [l['text']['en'],l['text']['fr']]
    for b in ('little','big'):
        for c in P['learn'][b]['cards']:
            if c['kind']!='map-intro':strs+=[c['text']['en'],c['text']['fr']]
    for s in P['stories']:
        for ps in s['pages'].values():
            for pg in ps:strs+=[pg['text']['en'],pg['text']['fr']]
    miss=[t for t in strs if t not in spec]
    ok(not miss,f'spec: {len(strs)} Learn/line/story strings match 13-cameroon-complete-pilot.md verbatim (missing {miss[:2]})')
async def main():
    spec_check()
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)));threading.Thread(target=srv.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{srv.server_address[1]}/'
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        await online(b,url,390,844);await online(b,url,360,780)
        if '--no-offline' not in sys.argv:await offline(b,url)
        await b.close()
    print('screenshots in',OUT);print('CAMEROON TESTS '+('PASSED' if not fails else f'FAILED {len(fails)}: {fails}'));sys.exit(1 if fails else 0)
asyncio.run(main())
