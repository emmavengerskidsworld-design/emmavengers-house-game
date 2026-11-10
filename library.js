/* ===== Emmavengers World content library (Stage 1) =====
   The app is a player; the content lives in content/library, built from content/src by tools/content_build.py.

   catalog.json  ->  indexes/<collection>.<hash>.json  ->  packs/<pack>.<hash>.json (+ @<lang> text files)

   What this file does:
   - Opens with the last verified copy kept on this device (IndexedDB), so the app starts offline and instantly.
     The very first visit downloads the catalog and the starter ("preload") packs.
   - Every file is checked against the SHA-256 and size written in the file that points at it. A file that does not
     match is never used. Language files must belong to the exact structure file they were built for.
   - Updates are incremental: the small catalog is re-read; only indexes and packs whose hash changed are downloaded.
     A new release is stored first, then switched on in ONE IndexedDB transaction (no half updates). The previous
     release is kept: if the current copy is damaged, the app falls back to it automatically (rollback).
     Older or conflicting catalogs (lower or equal sequence with different content) are refused.
   - The running session keeps the content it started with; a downloaded update is used from the next start
     (EWLib.applyUpdate() can switch at a safe moment, e.g. on the home map).
   - Packs needing something this app version cannot show (unknown game template, newer schema) are not loaded.
   - Nothing about the child is sent anywhere: requests are the same public files for everyone.
   Honest limit: hashes prove files were not damaged or mixed up, not who published them. Publisher signatures
   (blueprint 05 section 7, TUF) are a later step.

   API (window.EWLib): ready (Promise), get(id), find({type,land,ageBand,mode,subject,region,topic,pack}),
   text(lt, lang), textOr(lt, [langs]), locales(), packs(), ensure(packId), packFor(recordId), status(),
   checkForUpdates(), applyUpdate(), on(event, fn), forEachText(fn), legacy.{lands,countryIndex,uiStrings,country}. */
(function (G) {
'use strict';
const PLAYER = '1.0.0', FORMAT = 1, SCHEMA_MAJOR = '1';
const TEMPLATES = ['grid-route.v1', 'ordered-slots.v1', 'match.v1', 'map-select.v1', 'evidence-comparison.v1', 'inquiry.v1'];
const LIMITS = { catalog: 65536, index: 524288, pack: 2097152, lang: 2097152 };

/* ---------- SHA-256 (WebCrypto, or a small built-in version where WebCrypto is unavailable) ---------- */
const K = new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
function sha256js(bytes) {
  const l = bytes.length, n = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(n); m.set(bytes); m[l] = 0x80;
  const dv = new DataView(m.buffer); dv.setUint32(n - 4, (l * 8) >>> 0); dv.setUint32(n - 8, Math.floor(l / 0x20000000));
  const H = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]), W = new Uint32Array(64);
  const r = (x, k) => (x >>> k) | (x << (32 - k));
  for (let o = 0; o < n; o += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(o + i * 4);
    for (let i = 16; i < 64; i++) { const a = W[i - 15], b = W[i - 2]; W[i] = (W[i - 16] + (r(a, 7) ^ r(a, 18) ^ (a >>> 3)) + W[i - 7] + (r(b, 17) ^ r(b, 19) ^ (b >>> 10))) >>> 0 }
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (r(e, 6) ^ r(e, 11) ^ r(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + W[i]) >>> 0, t2 = ((r(a, 2) ^ r(a, 13) ^ r(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0 }
    H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h }
  return [...H].map(x => x.toString(16).padStart(8, '0')).join('');
}
const hex = buf => [...new Uint8Array(buf)].map(x => x.toString(16).padStart(2, '0')).join('');
async function sha256(bytes) {
  try { if (G.crypto && G.crypto.subtle) return hex(await G.crypto.subtle.digest('SHA-256', bytes)) } catch (e) {}
  return sha256js(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
}
const enc = s => new TextEncoder().encode(s);
const dec = b => new TextDecoder('utf-8', { fatal: true }).decode(b);
const semver = v => String(v).split('.').map(x => parseInt(x, 10) || 0);
const vcmp = (a, b) => { const x = semver(a), y = semver(b); for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i]; return 0 };
class LibError extends Error { constructor(code, msg) { super(msg || code); this.code = code } }

/* ---------- device storage: IndexedDB (one transaction for blobs + pointer), memory if unavailable ---------- */
function idbStore(name) {
  return new Promise((res, rej) => {
    let rq; try { rq = G.indexedDB.open(name, 1) } catch (e) { return rej(e) }
    rq.onupgradeneeded = () => { const db = rq.result; if (!db.objectStoreNames.contains('blobs')) db.createObjectStore('blobs'); if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta') };
    rq.onerror = () => rej(rq.error); rq.onblocked = () => rej(new Error('blocked'));
    rq.onsuccess = () => {
      const db = rq.result;
      const tx = (stores, mode, fn) => new Promise((ok, no) => { const t = db.transaction(stores, mode); let out; t.oncomplete = () => ok(out); t.onerror = () => no(t.error); t.onabort = () => no(t.error || new Error('abort')); out = fn(t) });
      const get = (s, k) => new Promise((ok, no) => { const t = db.transaction(s, 'readonly'); const r = t.objectStore(s).get(k); r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error) });
      res({ kind: 'indexeddb',
        getState: () => get('meta', 'state'),
        getBlob: h => get('blobs', h),
        hasBlobs: hs => Promise.all(hs.map(h => new Promise((ok) => { const t = db.transaction('blobs', 'readonly'); const r = t.objectStore('blobs').count(h); r.onsuccess = () => ok(r.result > 0); r.onerror = () => ok(false) }))),
        commit: (blobs, state) => tx(['blobs', 'meta'], 'readwrite', t => { const b = t.objectStore('blobs'); for (const [h, v] of Object.entries(blobs)) b.put(v, h); if (state) t.objectStore('meta').put(state, 'state') }),
        keys: () => new Promise((ok, no) => { const t = db.transaction('blobs', 'readonly'); const r = t.objectStore('blobs').getAllKeys(); r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error) }),
        remove: hs => tx(['blobs'], 'readwrite', t => { const b = t.objectStore('blobs'); hs.forEach(h => b.delete(h)) }),
        close: () => db.close() });
    };
  });
}
function memStore() {
  const blobs = new Map(); let state = null;
  return { kind: 'memory', getState: async () => state, getBlob: async h => blobs.get(h), hasBlobs: async hs => hs.map(h => blobs.has(h)),
    commit: async (b, s) => { for (const [h, v] of Object.entries(b)) blobs.set(h, v); if (s) state = JSON.parse(JSON.stringify(s)) },
    keys: async () => [...blobs.keys()], remove: async hs => hs.forEach(h => blobs.delete(h)), close() {} };
}

/* ---------- hydrate: structure + language files -> records with {"en":..,"fr":..} texts ---------- */
function hydrate(struct, langs) {
  const fill = o => {
    if (Array.isArray(o)) return o.map(fill);
    if (o && typeof o === 'object') {
      if ('$t' in o && Object.keys(o).length === 1) { const lt = {}; for (const lf of langs) { const s = lf.strings[o.$t]; if (s != null) lt[lf.locale] = s } return lt }
      const out = {}; for (const k in o) out[k] = fill(o[k]); return out }
    return o };
  return struct.records.map(fill);
}

function create(opts) {
  const cfg = Object.assign({ base: 'content/library/', db: 'ew-content-v1', locales: null, autoUpdate: true, updateDelay: 4000,
    minIntervalMs: 6 * 3600 * 1000, timeoutMs: 20000, retries: 2, player: PLAYER, templates: TEMPLATES, fetch: null, log: false }, opts || {});
  const fetchFn = cfg.fetch || ((u, o) => G.fetch(u, o));
  const listeners = {};
  const S = { ready: false, sequence: 0, source: null, lastCheck: 0, lastResult: null, errors: [], fetched: [], bytes: 0, storage: null, skipped: [], pending: null };
  let store = null, M = null, st = null, checking = null;
  const log = (...a) => { if (cfg.log) console.log('[EWLib]', ...a) };
  const emit = (ev, d) => (listeners[ev] || []).forEach(f => { try { f(d) } catch (e) { console.warn(e) } });
  const note = (code, msg) => { S.errors.push({ code, msg: String(msg), at: Date.now() }); if (S.errors.length > 30) S.errors.shift(); log(code, msg) };

  async function fetchBytes(path, noStore) {
    let last;
    for (let t = 0; t <= cfg.retries; t++) {
      const ac = G.AbortController ? new AbortController() : null; const tm = ac && setTimeout(() => ac.abort(), cfg.timeoutMs);
      try {
        const r = await fetchFn(cfg.base + path, { cache: noStore ? 'no-store' : 'default', signal: ac && ac.signal, credentials: 'same-origin' });
        if (r.status === 404) throw new LibError('missing', path + ' not found (404)');
        if (!r.ok) throw new LibError('http', path + ' HTTP ' + r.status);
        const b = new Uint8Array(await r.arrayBuffer()); S.fetched.push(path); S.bytes += b.length; return b;
      } catch (e) { last = e; if (e.code === 'missing') break; if (t < cfg.retries) await new Promise(z => setTimeout(z, 300 * (t + 1))) }
      finally { if (tm) clearTimeout(tm) }
    }
    throw last.code ? last : new LibError('offline', path + ': ' + (last && last.message));
  }
  /* a verified file: {sha, text, json} */
  async function getRef(ref, kind, haveText) {
    if (!ref || typeof ref.path !== 'string' || !/^[a-z0-9@._\/-]+\.json$/.test(ref.path) || ref.path.includes('..')) throw new LibError('bad-ref', 'bad file reference');
    if (ref.bytes > LIMITS[kind]) throw new LibError('too-big', ref.path + ' is larger than allowed');
    let text = haveText, fromNet = false;
    if (text == null) text = await store.getBlob(ref.sha256);
    let bytes;
    if (text == null) { bytes = await fetchBytes(ref.path); fromNet = true } else bytes = enc(text);
    if (bytes.length !== ref.bytes) throw new LibError('size', ref.path + ': size ' + bytes.length + ' != ' + ref.bytes);
    const h = await sha256(bytes);
    if (h !== ref.sha256) throw new LibError('hash', ref.path + ': SHA-256 does not match');
    if (fromNet) text = dec(bytes);
    return { sha: h, text, json: JSON.parse(text), fromNet };
  }
  function checkCatalog(c) {
    if (!c || c.format !== FORMAT) throw new LibError('format', 'catalog format ' + (c && c.format) + ' not supported');
    if (String(c.schemaVersion).split('.')[0] !== SCHEMA_MAJOR) throw new LibError('schema', 'schema ' + c.schemaVersion + ' not supported');
    if (c.player && c.player.min && vcmp(cfg.player, c.player.min) < 0) throw new LibError('incompatible', 'content needs app ' + c.player.min + '+');
    if (c.player && c.player.maxExclusive && vcmp(cfg.player, c.player.maxExclusive) >= 0) throw new LibError('incompatible', 'content is for apps before ' + c.player.maxExclusive);
    if (!Array.isArray(c.collections) || typeof c.sequence !== 'number') throw new LibError('format', 'catalog incomplete');
  }
  const packOk = e => {
    const rq = e.requires || {};
    if (rq.schema && String(rq.schema) !== SCHEMA_MAJOR) return 'schema ' + rq.schema;
    const miss = (rq.templates || []).filter(t => !cfg.templates.includes(t));
    return miss.length ? 'needs ' + miss.join(', ') : null };
  const wantLocales = cat => cfg.locales || cat.locales.filter(l => l.status === 'active' || l.status === 'in-review').map(l => l.tag);

  /* Build (or extend) the in-memory model from verified files. */
  function newModel(cat, catSha) {
    return { cat, catSha, indexes: {}, idxSha: {}, entries: {}, packs: {}, recs: new Map(), order: [], withdrawn: new Set((cat.withdrawals || []).map(w => w.id)) } }
  function addIndex(m, coll, f) {
    if (f.json.format !== FORMAT || f.json.collection !== coll.id) throw new LibError('format', 'index ' + coll.id + ' does not match the catalog');
    m.indexes[coll.id] = f.json; m.idxSha[coll.id] = f.sha; for (const e of f.json.packs) { e._coll = coll.id; m.entries[e.id] = e } }
  function addPack(m, e, sf, lfs) {
    if (sf.json.format !== FORMAT || sf.json.pack !== e.id) throw new LibError('format', 'pack file ' + e.id + ' does not match its index');
    for (const lf of lfs) if (lf.json.pack !== e.id || lf.json.struct !== e.file.sha256 || lf.json.strings.length !== sf.json.strings) throw new LibError('mismatch', 'language file ' + e.id + '@' + lf.json.locale + ' was built for another version');
    const recs = hydrate(sf.json, lfs.map(x => x.json));
    for (const r of recs) if (m.recs.has(r.id) && m.recs.get(r.id)._pack !== e.id) throw new LibError('duplicate', r.id + ' appears in two packs');
    for (const r of recs) { Object.defineProperty(r, '_pack', { value: e.id, enumerable: false }); m.recs.set(r.id, r); m.order.push(r.id) }
    m.packs[e.id] = { file: sf.sha, locales: Object.fromEntries(lfs.map(x => [x.json.locale, x.sha])) };
  }
  /* Load (verify) a whole release: from the device when `snap` is given and from the network otherwise / for changes. */
  async function loadRelease(opt) {
    const { catFile, installed } = opt;
    const cat = catFile.json; checkCatalog(cat);
    const m = newModel(cat, catFile.sha), langs = wantLocales(cat), blobs = {}, keep = f => { if (f.fromNet) blobs[f.sha] = f.text };
    /* getRef reads the device copy first, so unchanged indexes/packs are never downloaded again */
    for (const c of cat.collections) { const f = await getRef(c.index, 'index'); keep(f); addIndex(m, c, f) }
    const want = Object.values(m.entries).filter(e => e.preload || installed.includes(e.id));
    const work = want.map(e => async () => {
      const why = packOk(e); if (why) { S.skipped.push({ pack: e.id, why }); return null }
      const sf = await getRef(e.file, 'pack'); keep(sf);
      const lfs = [];
      for (const lg of langs) if (e.locales && e.locales[lg]) { const lf = await getRef(e.locales[lg], 'lang'); keep(lf); lfs.push(lf) }
      return [e, sf, lfs] });
    const done = await pool(work, 4);
    for (const d of done) if (d) addPack(m, d[0], d[1], d[2]);
    for (const e of want) if (e.preload && !m.packs[e.id] && !S.skipped.find(s => s.pack === e.id)) throw new LibError('missing', 'starter pack ' + e.id + ' not loaded');
    const snapOut = { sequence: cat.sequence, channel: cat.channel, catalog: catFile.sha, catalogText: catFile.text, indexes: m.idxSha, packs: m.packs, committed: Date.now() };
    return { model: m, snap: snapOut, blobs };
  }
  async function pool(fns, n) { const out = new Array(fns.length); let i = 0; const run = async () => { while (i < fns.length) { const k = i++; out[k] = await fns[k]() } }; await Promise.all(Array.from({ length: Math.min(n, fns.length) }, run)); return out }
  async function fromDevice(snap) {
    if (!snap || !snap.catalogText) throw new LibError('empty', 'no saved release');
    const b = enc(snap.catalogText), h = await sha256(b);
    if (h !== snap.catalog) throw new LibError('hash', 'saved catalog damaged');
    return loadRelease({ catFile: { sha: h, text: snap.catalogText, json: JSON.parse(snap.catalogText) }, installed: Object.keys(snap.packs || {}) });
  }
  async function fetchCatalog() {
    const b = await fetchBytes('catalog.json', true);
    if (b.length > LIMITS.catalog) throw new LibError('too-big', 'catalog too large');
    const text = dec(b); return { sha: await sha256(b), text, json: JSON.parse(text), fromNet: true };
  }
  async function gc() {
    const live = new Set();
    for (const s of [st.active, st.previous]) if (s) { live.add(s.catalog); Object.values(s.indexes).forEach(h => live.add(h)); Object.values(s.packs).forEach(p => { live.add(p.file); Object.values(p.locales).forEach(h => live.add(h)) }) }
    try { const ks = await store.keys(); const dead = ks.filter(k => !live.has(k)); if (dead.length) await store.remove(dead) } catch (e) { note('gc', e.message) }
  }
  async function commit(r) {
    const nst = Object.assign({}, st, { v: 1, active: r.snap, previous: (st.active && st.active.catalog !== r.snap.catalog) ? st.active : st.previous });
    await store.commit(r.blobs, nst); st = nst; await gc();
  }

  async function init() {
    try { store = await idbStore(cfg.db) } catch (e) { store = memStore(); note('storage', 'IndexedDB unavailable: content kept for this visit only') }
    S.storage = store.kind;
    try { st = (await store.getState()) || { v: 1 } } catch (e) { st = { v: 1 }; note('storage', e.message) }
    let r = null;
    for (const which of ['active', 'previous']) {
      if (!st[which]) continue;
      try { r = await fromDevice(st[which]); S.source = which === 'active' ? 'device' : 'device-rollback';
        if (which === 'previous') { note('rollback', 'saved release ' + st.active.sequence + ' was unusable; using ' + st.previous.sequence); st = Object.assign({}, st, { active: st.previous, previous: null }); await store.commit({}, st); emit('rollback', { sequence: r.snap.sequence }) }
        if (Object.keys(r.blobs).length) await store.commit(r.blobs, null); /* files re-downloaded to repair the copy */
        break }
      catch (e) { note('device-' + which, e.message); r = null }
    }
    if (!r) {
      const cf = await fetchCatalog();
      const installed = st.active ? Object.keys(st.active.packs || {}) : [];
      r = await loadRelease({ catFile: cf, installed });
      if (st.active) { note('recovered', 'saved copies were unusable; downloaded release ' + r.snap.sequence); st = Object.assign({}, st, { active: null, previous: null }) }
      await commit(r); S.source = 'network';
    }
    M = r.model; S.sequence = M.cat.sequence; S.ready = true;
    emit('ready', { sequence: S.sequence, source: S.source });
    if (cfg.autoUpdate && S.source !== 'network') setTimeout(() => api.checkForUpdates().catch(() => {}), cfg.updateDelay);
    return api;
  }

  /* ---------- incremental update ---------- */
  async function doCheck(force) {
    if (!force && st.lastCheck && Date.now() - st.lastCheck < cfg.minIntervalMs) return { result: 'skipped-recent' };
    if (G.navigator && G.navigator.onLine === false) return { result: 'offline' };
    const before = S.fetched.length, b0 = S.bytes;
    let res;
    try {
      const cf = await fetchCatalog();
      const base = st.active;
      if (base && cf.sha === base.catalog) res = { result: 'current', sequence: base.sequence };
      else {
        const cat = cf.json; checkCatalog(cat);
        if (base && cat.sequence < base.sequence) throw new LibError('replay', 'refused older catalog ' + cat.sequence + ' (have ' + base.sequence + ')');
        if (base && cat.sequence === base.sequence) throw new LibError('conflict', 'catalog ' + cat.sequence + ' changed without a new sequence');
        const r = await loadRelease({ catFile: cf, installed: Object.keys(base ? base.packs : {}) });
        const changed = Object.keys(r.snap.packs).filter(p => !base || !base.packs[p] || JSON.stringify(base.packs[p]) !== JSON.stringify(r.snap.packs[p]));
        await commit(r);
        S.pending = r.model;
        res = { result: 'updated', sequence: r.snap.sequence, changed };
        emit('update', res);
      }
    } catch (e) { res = { result: 'failed', code: e.code || 'error', error: e.message }; note('update-' + (e.code || 'error'), e.message) }
    res.files = S.fetched.slice(before); res.bytes = S.bytes - b0;
    st = Object.assign({}, st, { lastCheck: Date.now(), lastResult: res.result }); try { await store.commit({}, st) } catch (e) {}
    S.lastCheck = st.lastCheck; S.lastResult = res; return res;
  }

  /* ---------- queries ---------- */
  const visible = r => r && !M.withdrawn.has(r.id);
  const api = {
    PLAYER, FORMAT, ready: null,
    get: id => { const r = M && M.recs.get(id); return visible(r) ? r : null },
    find(q) {
      q = q || {}; const out = [];
      for (const id of M.order) { const r = M.recs.get(id); if (!visible(r)) continue; const T = r.tags || {};
        if (q.type && r.type !== q.type) continue; if (q.pack && r._pack !== q.pack) continue; if (q.status && r.status !== q.status) continue;
        if (q.land && T.land !== q.land) continue;
        if (q.ageBand && !(T.ageBands || []).includes(q.ageBand)) continue;
        if (q.mode && !(T.modes || []).includes(q.mode)) continue;
        if (q.subject && !(T.subjects || []).includes(q.subject)) continue;
        if (q.region && !(T.regions || []).includes(q.region)) continue;
        if (q.topic && !(T.topics || []).includes(q.topic)) continue;
        if (q.lang && !hasLang(r, q.lang)) continue;
        out.push(r) }
      return out },
    text: (lt, lang) => (lt && typeof lt === 'object' && lt[lang] != null) ? lt[lang] : null,
    textOr(lt, langs) { for (const l of langs || []) { const t = api.text(lt, l); if (t != null) return t } return null },
    locales: () => M ? M.cat.locales.slice() : [],
    installedLocales: () => M ? wantLocales(M.cat) : [],
    packs: () => M ? Object.values(M.entries).map(e => ({ id: e.id, collection: e._coll, revision: e.revision, preload: e.preload, installed: !!M.packs[e.id], summary: e.summary || null, locales: Object.keys(e.locales || {}), bytes: e.file.bytes })) : [],
    packFor(id) { if (M.recs.has(id)) return M.recs.get(id)._pack; const e = Object.values(M.entries).find(e => e.summary && e.summary.id === id); return e ? e.id : null },
    async ensure(packId) {
      if (M.packs[packId]) return true;
      const e = M.entries[packId]; if (!e) throw new LibError('unknown-pack', packId);
      const why = packOk(e); if (why) throw new LibError('incompatible', packId + ': ' + why);
      const sf = await getRef(e.file, 'pack'), lfs = [], blobs = {};
      for (const lg of wantLocales(M.cat)) if (e.locales[lg]) lfs.push(await getRef(e.locales[lg], 'lang'));
      for (const f of [sf, ...lfs]) if (f.fromNet) blobs[f.sha] = f.text;
      addPack(M, e, sf, lfs);
      const snap = Object.assign({}, st.active, { packs: Object.assign({}, st.active.packs, { [packId]: M.packs[packId] }) });
      await store.commit(blobs, st = Object.assign({}, st, { active: snap }));
      emit('pack', { id: packId }); return true },
    status: () => JSON.parse(JSON.stringify(Object.assign({}, S, { pending: S.pending ? S.pending.cat.sequence : null, installed: M ? Object.keys(M.packs) : [] }))),
    checkForUpdates(force) { if (!checking) checking = doCheck(force).finally(() => { checking = null }); return checking },
    applyUpdate() { if (!S.pending) return false; M = S.pending; S.pending = null; S.sequence = M.cat.sequence; emit('applied', { sequence: S.sequence }); return true },
    on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); return api },
    forEachText(fn) { for (const id of M.order) { const r = M.recs.get(id); if (visible(r)) walkLt(r.payload, 'payload', (p, lt) => fn(r, p, lt)) } },
    _debug: () => ({ st, store, M }),
    close() { try { store && store.close() } catch (e) {} }
  };
  const isLt = v => v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length > 0 && Object.entries(v).every(([k, x]) => /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/.test(k) && typeof x === 'string');
  function walkLt(o, p, fn) { if (isLt(o)) return fn(p, o); if (Array.isArray(o)) o.forEach((v, i) => walkLt(v, p + '[' + i + ']', fn)); else if (o && typeof o === 'object') for (const k in o) walkLt(o[k], p + '.' + k, fn) }
  function hasLang(r, lang) { let ok = true, any = false; walkLt(r.payload, '', (p, lt) => { any = true; if (lt[lang] == null) ok = false }); return ok }

  /* ---------- pre-Stage-1 shapes for today's screens (same rules as tools/content/legacy.py) ---------- */
  const isLtE = v => isLt(v);
  const flat = (o, lg) => isLtE(o) ? o[lg] : Array.isArray(o) ? o.map(x => flat(x, lg)) : (o && typeof o === 'object') ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, flat(v, lg)])) : o;
  const R = id => M.recs.get(id);
  const key = id => R(id).payload.key;
  api.legacy = {
    lands() {
      const W = R('ew.world.home').payload;
      const out = { version: W.formatVersion || 1, world: { title: W.title.en, img: W.img, intro: W.intro.en, layout: W.layout, bg2: W.bg2 }, lands: [], decks: {}, phonemes: {}, study: null };
      for (const lid of W.lands) { const r = R(lid); if (!r) continue; const p = flat(r.payload, 'en'); const L = { id: p.key, name: p.name };
        if (p.landType) L.type = p.landType; for (const k of ['color', 'img', 'music']) if (k in p) L[k] = p[k];
        for (const [k, v] of Object.entries(p.layout)) if (k !== 'm6') L[k] = v; L.intro = p.intro;
        L.places = p.places.filter(q => !q.country || M.recs.has(q.country) || api.packFor(q.country)).map(q => { const o = {};
          for (const [k, v] of Object.entries(q)) { if (k === 'key') o.id = v; else if (k === 'deck' || k === 'objects') o[k] = key(v); else if (k === 'country') o[k] = (R(v) ? R(v).payload.slug : summaryOf(v).slug); else o[k] = v } return o });
        if (p.layout.m6) L.m6 = p.layout.m6; out.lands.push(L) }
      for (const r of api.find({ type: 'deck' })) { const p = flat(r.payload, 'en'); const D = { kind: p.kind }; if ('done' in p) D.done = p.done;
        D.items = p.items.map(it => Object.fromEntries(Object.entries(it).map(([k, v]) => [k, k === 'greeting' ? v.text : v]))); out.decks[p.key] = D }
      const lex = R('ew.lexicon.letter-sounds'); if (lex) for (const e of lex.payload.entries) out.phonemes[e.text] = e.ipa;
      const st = R('ew.library.study');
      if (st) { const p = flat(st.payload, 'en'); out.study = { prompt: p.prompt, sections: p.sections.map(s => { const o = {};
          for (const [k, v] of Object.entries(s)) { if (k === 'key') o.id = v; else if (k === 'source') o[k] = v.deck ? 'deck:' + key(v.deck) : (v.module || ''); else o[k] = v } return o }) };
        if (st.evidence && st.evidence.note) out.study._help = st.evidence.note }
      return out },
    countryIndex() {
      const cs = Object.values(M.entries).filter(e => e.summary && e.summary.type === 'country').map(e => e.summary);
      return { schemaVersion: '1.0.0', id: 'ew.index.countries', revision: 1, status: 'draft',
        countries: cs.map(s => ({ id: s.id, slug: s.slug, revision: s.revision || 1, file: 'content/countries/' + s.slug + '.json', land: s.tags && s.tags.land })) } },
    uiStrings(id) { const r = R(id || 'ew.ui.country-player'); return { schemaVersion: '1.0.0', id: r.id, revision: r.revision, status: r.status, note: (r.evidence && r.evidence.note) || '', strings: r.payload.strings } },
    async country(slugOrId) {
      const s = Object.values(M.entries).map(e => e.summary).find(s => s && s.type === 'country' && (s.slug === slugOrId || s.id === slugOrId));
      const cid = s ? s.id : slugOrId; const pid = api.packFor(cid); if (!pid) throw new LibError('unknown', slugOrId);
      await api.ensure(pid); return legacyCountry(cid) }
  };
  function summaryOf(id) { const e = Object.values(M.entries).find(e => e.summary && e.summary.id === id); return e ? e.summary : {} }
  function legacyCountry(cid) {
    const C = R(cid), P = C.payload, lkey = id => R(id).payload.key, skey = id => R(id).payload.key;
    const sv = id => R(id).payload.note || R(id).payload.url;
    const pay = { slug: P.slug, name: P.name, flag: P.flag, hub: Object.fromEntries(Object.entries(P.hub).map(([k, v]) => [k, lkey(v)])), lines: {}, learn: {}, practiceMap: P.practiceMap,
      play: [], quiz: null, stories: [], media: {}, breakAfterMinutes: P.breakAfterMinutes, ui: P.ui };
    for (const id of P.lines) { const l = R(id).payload; pay.lines[l.key] = { speaker: R(l.speaker).payload.key, text: l.text } }
    for (const band of ['little', 'big']) { const les = R(P.learn[band]), bands = les.tags.ageBands;
      pay.learn[band] = { lessonId: les.id, cards: les.payload.cards.map(id => { const c = R(id), cp = c.payload;
        const o = { id: cp.key, image: R(cp.image).payload.key, text: cp.text, sources: ((c.evidence || {}).sources || []).map(skey), kind: cp.kind };
        if (cp.lines) o.lines = cp.lines.map(lkey); const cb = c.tags.ageBands; if (cb.length === 1 && cb.length < bands.length && bands.includes(cb[0])) o.band = cb[0]; return o }) } }
    for (const id of P.play) { const a = R(id); const g = { id: a.payload.key, ref: a.id, template: a.payload.template, bands: a.tags.ageBands };
      for (const [k, v] of Object.entries(a.payload)) if (k !== 'key' && k !== 'template') g[k] = k === 'lines' ? v.map(lkey) : v;
      if (a.evidence && a.evidence.note) g.note = a.evidence.note; pay.play.push(g) }
    const Q = P.quiz, LK = Object.fromEntries(Q.legacyLocaleKeys), q = { bank: 'content/countries/' + P.slug + '-quiz.json', localeKeys: LK };
    for (const [k, v] of Object.entries(Q)) if (k !== 'bank' && k !== 'legacyLocaleKeys') q[k] = v;
    pay.quiz = q;
    for (const id of P.stories) { const s = R(id); const o = { id: s.id }; if ('classification' in s.payload) o.classification = s.payload.classification; o.bands = s.tags.ageBands;
      for (const [k, v] of Object.entries(s.payload)) if (k !== 'classification') o[k] = v; if (s.evidence && s.evidence.note) o.note = s.evidence.note; pay.stories.push(o) }
    for (const id of P.media) { const m = Object.assign({}, R(id).payload); const k = m.key; delete m.key; pay.media[k] = m }
    const T = C.tags, tags = {}; for (const k of ['land', 'relatedLands', 'ageBands', 'modes', 'access', 'sensitivity']) if (k in T) tags[k] = T[k];
    const LZ = C.l10n || {}, locs = {}, lorder = [...(LZ.required || []), ...Object.keys(LZ)];
    for (const lg of lorder) if (lg !== 'required' && LZ[lg] && !(lg in locs)) locs[lg] = { status: LZ[lg].status };
    const pack = { schemaVersion: '1.0.0', id: C.id, type: 'country-pack', revision: C.revision, status: C.status, sourceLanguage: C.sourceLanguage, locales: locs, tags,
      evidence: { spec: C.evidence.spec, sources: C.evidence.sources.map(id => ({ sourceId: skey(id), url: R(id).payload.url, checkedOn: R(id).payload.checkedOn })), gaps: C.evidence.gaps || [] },
      editorial: { ownerRole: C.review.ownerRole, reviewRecordRefs: C.review.records || [], approvalRef: C.review.approvalRef }, payload: pay };
    const B = R(Q.bank), bp = B.payload;
    const items = bp.items.map(id => { const it = R(id), ip = it.payload, srcs = it.evidence.sources;
      const o = { id: it.id, revision: it.revision, status: it.status, type: ip.responseType, band: it.tags.ageBands[0], construct: ip.construct,
        source: srcs.map(sv).join(' ; '), sourceKey: skey(srcs[0]), existingFrom10b: (it.evidence.provenance || {}).existingFrom10b, answerKey: ip.answerKey };
      for (const [lg, k] of Object.entries(LK)) { if (ip.prompt[lg] == null) continue; const blk = { prompt: ip.prompt[lg], options: Object.fromEntries(Object.entries(ip.options).map(([oid, t]) => [oid, t[lg]])) };
        for (const f of ['hint', 'feedback']) if (ip[f] && ip[f][lg] != null) blk[f] = ip[f][lg]; o[k] = blk }
      o.readAloudAllowed = ip.readAloudAllowed; o.shuffleOptions = ip.shuffleOptions; o.factCheckStatus = (it.review || {}).factCheck; o.reviewStatus = (it.review || {}).note; return o });
    const bank = { bank: B.id, revision: B.revision, status: B.status, note: (B.evidence || {}).note, sources: Object.fromEntries((bp.sources || []).map(id => [skey(id), sv(id)])), items, roundRules: bp.roundRules };
    return { pack, bank };
  }
  api.ready = init().catch(e => { S.ready = false; note('init-' + (e.code || 'error'), e.message); throw e });
  return api;
}

G.EWLibrary = { create, sha256, sha256js, PLAYER, FORMAT, LibError };
if (G.EW_LIBRARY_AUTO !== false && !G.EWLib) { G.EWLib = create(G.EW_LIBRARY_CONFIG || {}); G.EWLib.ready.catch(() => {}) }
})(typeof window !== 'undefined' ? window : globalThis);
