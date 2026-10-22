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
    metadataCandidatePollTimer:42,metadataCandidatePollAttempts:1,
    metadataCandidateController:new AbortController()};
  const oldController=state.metadataCandidateController;
  const requests=[],cleared=[];
  const context={state,AbortController,JSON,String,Error,Array,Number,encodeURIComponent,
    $:id=>nodes[id],itemById:()=>({id:'t1',title:'Old Song',artist:'Wrong Artist',album:'Wrong Album'}),
    displayTrackTitle:item=>item.title, renderMetadataCandidateProviderPicker:()=>{},
    clearTimeout:id=>cleared.push(id),escapeHtml:value=>String(value),
    fetchJsonResponseBounded:async (...args)=>{requests.push(args);return respond(...args);},
    apiFetch:async (...args)=>{requests.push(args);return {ok:false};},readResponseJsonBounded:async ()=>({}),
    unwrapMetadataResponsePayload:value=>value,
    renderMetadataCandidateSearchResults:(node,results)=>{node.textContent=results.map(row=>row.title).join(',');},
    globalThis:{},
  };
  context.globalThis=context;
  context.fnAudioResponseJsonLoader={parsedBody:status=>status==='parsed'};
  vm.createContext(context);
  if (/function cancelMetadataCandidateLookup\(/.test(app)) vm.runInContext(code('cancelMetadataCandidateLookup'),context);
  vm.runInContext(['metadataCandidateDialogNode','metadataCandidateResultsNode','metadataCandidateStatusNode',
    'searchTrackMetadataManually','openMetadataCandidateDialog'].map(code).join('\n'),context);
  return {nodes,state,oldController,requests,cleared,search:()=>context.searchTrackMetadataManually(),open:()=>context.openMetadataCandidateDialog('t1')};
}
(async()=>{
  const h=harness(); await h.search();
  assert.equal(h.nodes.metadataCandidateSearchResults.textContent,'New Song');
  assert.match(h.nodes.metadataCandidateStatus.textContent,/查询完成/,'query label must finish');
  assert.ok(h.oldController.signal.aborted,'manual search cancels cached/polling lookup');
  assert.ok(h.cleared.includes(42),'manual search cancels pending poll');
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
  const broken=harness(async()=>{throw new Error('请求超时');});
  await broken.search(); assert.match(broken.nodes.metadataCandidateStatus.textContent,/搜索失败/);
  assert.match(broken.nodes.metadataCandidateSearchResults.innerHTML,/请求超时/);
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
