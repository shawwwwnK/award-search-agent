// Offline render/event checks using a minimal DOM stub; not browser visual QA.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=__dirname,html=fs.readFileSync(path.join(root,'review.html'),'utf8');
const blocks=[...html.matchAll(/<script(?: [^>]*)?>(.*?)<\/script>/gs)].map(m=>m[1]);
class Element{constructor(){this.children=[];this.dataset={};this.innerHTML='';this.hidden=false;this.checked=true;this.classList={toggle(){}}}appendChild(e){this.children.push(e)}}
const ids=Object.fromEntries(['data','tabs','case-head','tools','content','highlight'].map(x=>[x,new Element()]));ids.data.textContent=blocks[0];
const modes=['both','free','bound'].map(mode=>{const e=new Element();e.dataset.mode=mode;return e});
const document={getElementById:id=>{assert.ok(ids[id],'known element '+id);return ids[id]},createElement:()=>new Element(),querySelectorAll:q=>q==='#tabs button'?ids.tabs.children:q==='[data-mode]'?modes:[]};
const ctx=vm.createContext({document,console});vm.runInContext(blocks[1],ctx);
const data=JSON.parse(blocks[0]);assert.equal(ids.tabs.children.length,5);let rendered=0;
for(const key of ['A','B','C','D']){
 ids.tabs.children.find(b=>b.dataset.key===key).onclick();
 for(const b of modes){b.onclick();const text=ids.content.innerHTML;assert.ok(!text.includes('{{clause:'),'all clauses resolved');const cards=[...text.matchAll(/class="card"/g)].length;assert.equal(cards,data.facts.cases[key].records.length*(b.dataset.mode==='both'?2:1));rendered++}
}
ids.highlight.checked=false;ids.highlight.onchange();ids.tabs.children.find(b=>b.dataset.key==='tests').onclick();assert.equal(ids.tools.hidden,true);assert.ok(ids.content.innerHTML.includes('free text was not checked'));
ids.tabs.children.find(b=>b.dataset.key==='C').onclick();assert.ok(ids['case-head'].innerHTML.includes('55,000 miles'));assert.equal(ids.tools.hidden,false);
const report={kind:'offline_javascript_logic_smoke_only',case_mode_renders:rendered,case_count:4,views:['side-by-side','free','bound'],unresolved_clauses:0,selected_card_coverage:'pass',failure_tab:'pass',context_record_separate:'pass',browser_visual_qa:false,model_calls:0};
fs.writeFileSync(path.join(root,'ui-checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
