const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../app/ui/app.js'), 'utf8');
function code(name) {
  const match = app.match(new RegExp('^(?:async )?function ' + name + '\\b[\\s\\S]*?^}', 'm'));
  assert.ok(match, name);
  return match[0];
}
function harness(respond = async () => ({response:{ok:true}, data:{ok:true,search_id:'search-fixture',candidates:[{title:'New Song',source:'netease'}]}, bodyStatus:'parsed'})) {
  const nodes = {
    metadataCandidateSearchInput:{value:'New Song'}, metadataCandidateSearchStatus:{textContent:''},
    metadataCandidateStatus:{textContent:''}, metadataCandidateProviderSelect:{value:'netease'},
    metadataCandidateDialog:{open:true,showModal(){this.open=true;}},
    metadataCandidateSearchResults:{textContent:'',innerHTML:''},
  };
  const state = {actionTrackId:'t1', metadataCandidateRequestToken:1, metadataCandidateSearchToken:0,
    metadataCandidateController:new AbortController()};
  const oldController=state.metadataCandidateController;
  const requests=[];
  const context={state,AbortController,JSON,String,Error,Array,Number,encodeURIComponent,
    $:id=>nodes[id],itemById:()=>({id:'t1',title:'Old Song',artist:'Wrong Artist',album:'Wrong Album'}),
    displayTrackTitle:item=>item.title, renderMetadataCandidateProviderPicker:()=>{},
    escapeHtml:value=>String(value),
    fetchJsonResponseBounded:async (...args)=>{requests.push(args);return respond(...args);},
    apiFetch:async (...args)=>{requests.push(args);return {ok:false};},readResponseJsonBounded:async ()=>({}),
    renderMetadataCandidateSearchResults:(node,results)=>{node.textContent=(Array.isArray(results) ? results : []).filter(row=>row && row.title).map(row=>row.title).join(',');},
    globalThis:{},
  };
  context.globalThis=context;
  context.fnAudioResponseJsonLoader={parsedBody:status=>status==='parsed'};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/ui/metadata_response_policy.js'), 'utf8'), context);
  vm.runInContext(code('unwrapMetadataResponsePayload'), context);
  if (/function cancelMetadataCandidateLookup\(/.test(app)) vm.runInContext(code('cancelMetadataCandidateLookup'),context);
  vm.runInContext(['metadataCandidateDialogNode','metadataCandidateResultsNode','metadataCandidateStatusNode',
    'searchTrackMetadataManually','openMetadataCandidateDialog'].map(code).join('\n'),context);
  return {nodes,state,oldController,requests,search:()=>context.searchTrackMetadataManually(),open:()=>context.openMetadataCandidateDialog('t1')};
}
(async()=>{
  const h=harness(); await h.search();
  assert.equal(h.nodes.metadataCandidateSearchResults.textContent,'New Song');
  assert.match(h.nodes.metadataCandidateStatus.textContent,/查询完成/,'query label must finish');
  assert.ok(h.oldController.signal.aborted,'manual search cancels an earlier confirmation');
  assert.equal(h.state.metadataCandidateRequestToken,2,'manual search invalidates the earlier confirmation generation');
  const [url,options,timeout]=h.requests[0];
  assert.equal(url,'api/metadata/track/search');
  assert.equal(timeout,25000,'deadline includes receiving headers and reading body');
  const body=JSON.parse(options.body);
  assert.equal(body.provider_id,'netease');
  assert.equal(body.artist,'','old track artist must not restrict another query');
  assert.equal(body.album,'');
  const opened=harness(); opened.open();
  assert.equal(opened.nodes.metadataCandidateSearchInput.value,'Old Song','opening searches the song immediately');
  assert.equal(opened.requests.length,1);
  const empty=harness(async()=>({response:{ok:true},data:{ok:true,candidates:[]},bodyStatus:'parsed'}));
  await empty.search(); assert.match(empty.nodes.metadataCandidateStatus.textContent,/没有找到/);
  const wrapped = harness(async () => ({response:{ok:true}, bodyStatus:'parsed',
    data:{data:{result:{ok:true,search_id:'wrapped-search',candidates:[{title:'Wrapped song'}]}}}}));
  await wrapped.search();
  assert.equal(wrapped.nodes.metadataCandidateSearchResults.textContent,'Wrapped song',
    'real envelope policy must deliver bridge-wrapped candidates to the current search');
  assert.match(wrapped.nodes.metadataCandidateStatus.textContent,/查询完成/);
  const rejected = harness(async () => ({response:{ok:false,status:503}, bodyStatus:'parsed',
    data:{data:{result:{ok:true,search_id:'rejected-http',candidates:[{title:'Must not render'}]}}}}));
  await rejected.search();
  assert.match(rejected.nodes.metadataCandidateStatus.textContent,/搜索失败/);
  assert.doesNotMatch(rejected.nodes.metadataCandidateSearchResults.textContent,/Must not render/);
  const businessFailure = harness(async () => ({response:{ok:true,status:200}, bodyStatus:'parsed',
    data:{data:{result:{ok:false,candidates:[{title:'Rejected business result'}]}}}}));
  await businessFailure.search();
  assert.match(businessFailure.nodes.metadataCandidateStatus.textContent,/搜索失败/,
    'business rejection must be handled explicitly even when the renderer tolerates absent candidates');
  assert.doesNotMatch(businessFailure.nodes.metadataCandidateSearchResults.textContent,/Rejected business result/);

  const broken=harness(async()=>{throw new Error('请求超时');});
  await broken.search(); assert.match(broken.nodes.metadataCandidateStatus.textContent,/搜索失败/);
  assert.match(broken.nodes.metadataCandidateSearchResults.innerHTML,/请求超时/);
  let attempts = 0;
  const retry = harness(async () => {
    if (++attempts === 1) throw new Error('first search failed');
    return {response:{ok:true},data:{ok:true,search_id:'retry-search',candidates:[{title:'Retry result'}]}};
  });
  await retry.search();
  assert.match(retry.nodes.metadataCandidateSearchStatus.textContent,/搜索失败/);
  retry.nodes.metadataCandidateSearchInput.value = 'corrected title';
  retry.nodes.metadataCandidateProviderSelect.value = 'kuwo';
  await retry.search();
  assert.equal(retry.requests.length,2,'the same search form must remain retryable after failure');
  assert.equal(retry.nodes.metadataCandidateSearchResults.textContent,'Retry result');
  assert.match(retry.nodes.metadataCandidateStatus.textContent,/查询完成/);
  assert.equal(JSON.parse(retry.requests[1][1].body).title,'corrected title');
  assert.equal(JSON.parse(retry.requests[1][1].body).provider_id,'kuwo');
  let resolve; const late=harness(()=>new Promise(done=>resolve=done));
  const running=late.search(); late.state.metadataCandidateSearchToken++; late.nodes.metadataCandidateSearchStatus.textContent='已选择其他数据源';
  resolve({response:{ok:true},data:{ok:true,candidates:[]},bodyStatus:'parsed'}); await running;
  assert.equal(late.nodes.metadataCandidateSearchStatus.textContent,'已选择其他数据源');
  const apply={disabled:false}; let applied;
  const list={innerHTML:'',querySelector:selector=>selector.includes(':checked')?{value:'0'}:apply};
  const ctx={state:{actionTrackId:'t1'},AbortController,Number,JSON,String,Error,
    escapeHtml:String,metadataCandidateSourceLabel:()=>'',
    fnAudioMetadataCandidatePresentationPolicy:{confidencePercent:()=>''},
    apiFetch:async(url,options)=>{applied=JSON.parse(options.body);return {ok:true};},
    readResponseJsonBounded:async()=>({ok:true}),clearLibraryResponseCaches:()=>{}};
  vm.createContext(ctx); vm.runInContext(code('renderMetadataCandidateChoices'),ctx);
  ctx.renderMetadataCandidateChoices(list,[{title:'Visible choice'}],'t1','review','immutable-search-b');
  await apply.onclick();
  assert.equal(applied.search_id,'immutable-search-b','apply must bind to the visible search response');
  console.log('Interactive metadata search state/transport regression checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

function applyFailureHarness(withAbort = true) {
  const writes = [], errors = [];
  let apply;
  const list = {
    _html: "", _text: "",
    get innerHTML() { return this._html; },
    set innerHTML(value) { this._html = value; this._text = ""; apply = { disabled: false }; writes.push(["html", value]); },
    get textContent() { return this._text; },
    set textContent(value) { this._text = value; this._html = ""; writes.push(["text", value]); },
    querySelector: selector => selector.includes(":checked") ? { value: "0" } : apply,
    insertAdjacentHTML: (where, html) => { errors.push(html); writes.push([where, html]); },
  };
  const nodes = {
    metadataCandidateDialog: { open: true, close() { this.open = false; } },
    trackActionDialog: { open: false, close() { this.open = false; } },
    metadataCandidateSearchResults: list,
    metadataCandidateSearchInput: { value: "new query" },
    metadataCandidateSearchStatus: { textContent: "" },
    metadataCandidateStatus: { textContent: "" },
    metadataCandidateProviderSelect: { value: "kuwo" },
  };
  let reject, resolve;
  const response = new Promise((yes, no) => { resolve = yes; reject = no; });
  const state = { actionTrackId: "t1", metadataCandidateRequestToken: 1, metadataCandidateSearchToken: 1,
    metadataCandidateController: null, metadataCandidateSearchController: null };
  let cacheClears = 0, libraryLoads = 0;
  const context = {
    state, AbortController: withAbort ? AbortController : undefined, $: id => nodes[id],
    escapeHtml: String, metadataCandidateSourceLabel: () => "",
    fnAudioMetadataCandidatePresentationPolicy: { confidencePercent: () => "" },
    apiFetch: () => response,
    readResponseJsonBounded: async value => value,
    clearLibraryResponseCaches: () => { cacheClears++; },
    loadLibrary: async refresh => { assert.equal(refresh,false); libraryLoads++; },
    itemById: id => ({ id, title: "new query" }),
    unwrapMetadataResponsePayload: value => value,
    fetchJsonResponseBounded: async () => ({ response: { ok: true }, data: {
      ok: true, search_id: "new-search", candidates: [{ title: "new candidate" }],
    } }),
    clearTimeout() {},
  };
  vm.createContext(context);
  vm.runInContext(["renderMetadataCandidateChoices", "renderMetadataCandidateSearchResults",
    "metadataCandidateDialogNode", "metadataCandidateResultsNode", "metadataCandidateStatusNode",
    "cancelMetadataCandidateLookup", "closeTrackActionDialog", "searchTrackMetadataManually"].map(code).join("\n"), context);
  context.renderMetadataCandidateChoices(list, [{ title: "old candidate" }], "t1", "review", "old-search");
  return { context, nodes, state, writes, errors, list, reject, resolve,
    start: () => apply.onclick(), clears: () => cacheClears, loads: () => libraryLoads };
}
(async () => {
  const failures = [];
  for (const mode of ["new-search", "closed", "other-track"]) {
    const h = applyFailureHarness();
    const result = h.start();
    const controller = h.state.metadataCandidateController;
    if (mode === "closed") h.context.closeTrackActionDialog();
    else {
      if (mode === "other-track") h.state.actionTrackId = "t2";
      await h.context.searchTrackMetadataManually();
    }
    assert.equal(controller.signal.aborted, true, "changing dialog context must abort the previous apply request");
    const before = h.writes.length;
    // A fetch/body failure may be a normal Error even after a caller aborts.
    h.reject(new Error("old confirmation transport failed"));
    await result;
    if (h.writes.length !== before) failures.push(mode);
    assert.equal(h.clears(), 0);
  }
  assert.deepEqual(failures, [], "a stale confirmation failure must not write into another search, track or closed dialog");

  for (const succeed of [false, true]) {
    const fallback = applyFailureHarness(false);
    const old = fallback.start();
    await fallback.context.searchTrackMetadataManually();
    const before = fallback.writes.length;
    if (succeed) fallback.resolve({ ok: true });
    else fallback.reject(new Error("late error without AbortController"));
    await old;
    assert.equal(fallback.writes.length, before,
      "request generations must isolate late confirmations even without AbortController");
    assert.equal(fallback.clears(), 0);
  }

  const current = applyFailureHarness();
  const result = current.start();
  current.reject(new Error("current confirmation failed"));
  await result;
  assert.equal(current.errors.length, 1, "a current confirmation failure must remain visible and retryable");
  assert.match(current.errors[0], /current confirmation failed/);
  assert.equal(current.list.querySelector("apply").disabled, false);
  assert.equal(current.state.metadataCandidateController, null);
  const overlap = applyFailureHarness();
  const oldApply = overlap.start();
  await overlap.context.searchTrackMetadataManually();
  let resolveNew;
  overlap.context.apiFetch = () => new Promise(resolve => { resolveNew = resolve; });
  const newApply = overlap.start();
  const owner = overlap.state.metadataCandidateController;
  const before = overlap.writes.length;
  overlap.reject(new Error("previous apply failed late"));
  await oldApply;
  assert.equal(overlap.writes.length, before);
  assert.equal(overlap.state.metadataCandidateController, owner, "old finally must not release a newer apply controller");
  assert.equal(overlap.list.querySelector("apply").disabled, true);
  overlap.state.pageItems = [{ id: 't1' }];
  overlap.state.libraryLoading = false;
  resolveNew({ ok: true });
  await newApply;
  assert.equal(overlap.loads(),1,'current confirmation must refresh a visible settled library page');
  assert.equal(overlap.clears(), 1, "the current successful apply must still refresh metadata");
  assert.match(overlap.list.textContent, /已确认/);
  assert.equal(overlap.state.metadataCandidateController, null);

  const lateSuccess = applyFailureHarness();
  const finishing = lateSuccess.start();
  lateSuccess.context.closeTrackActionDialog();
  const closedWrites = lateSuccess.writes.length;
  lateSuccess.resolve({ ok: true });
  await finishing;
  assert.equal(lateSuccess.writes.length, closedWrites, "closing must also isolate a late successful confirmation");
  assert.equal(lateSuccess.clears(), 0);
  console.log("Metadata confirmation stale-error isolation regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
