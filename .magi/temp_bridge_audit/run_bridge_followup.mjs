import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE='https://magi-bridge-v4.vercel.app/api/step';
const FX=160;
const CAP_YEN=100;
let spentUsd=0;
const dir='.magi/temp_bridge_audit';
const defs=[
  {path:'T009R_checker_C_v3_candidate.py',name:'T009R_checker_C_v3_candidate.txt',type:'text/plain'},
  {path:'Claude_independent_audit_v2_LOCK_BLOCKERS.json',name:'Claude_independent_audit_v2_LOCK_BLOCKERS.json',type:'application/json'},
  {path:'T009R_CheckerC_Audit_Context_from_Prereg_v0.4.json',name:'T009R_CheckerC_Audit_Context_from_Prereg_v0.4.json',type:'application/json'}
];
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const evidence=defs.map(d=>{const content=fs.readFileSync(`${dir}/${d.path}`,'utf8');return {name:d.name,type:d.type,size:Buffer.byteLength(content),content,client_sha256:sha(content)}});
const topic=`T009R confirmatory Checker CをLOCK候補まで持っていくための修正方針を確定する。現candidateはClaude独立監査でLOCK不可。C-1〜C-3、M-4〜M-7、m-8〜m-12、note-13を証拠として扱う。科学的閾値・判定条件・Gate変更禁止。修正チェックリスト答え合わせだけでなく、新しい攻撃面も探す。コードLOCKは実装・adversarial self-test・Claude再監査通過前に宣言禁止。`;
let previous=fs.readFileSync(`${dir}/round1_gpt_revise.txt`,'utf8');
async function step(payload){const remaining=Math.max(0,CAP_YEN-spentUsd*FX);if(remaining<=0)throw new Error('BUDGET_CAP');const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:remaining,budget_fx_yen_per_usd:FX})});const raw=await r.text();let d;try{d=JSON.parse(raw)}catch{throw new Error(`NON_JSON_${r.status}:${raw.slice(0,500)}`)}if(!r.ok)throw new Error(d.error||`HTTP_${r.status}`);if(d.usage?.usd!=null)spentUsd+=Number(d.usage.usd||0);return d}
const transcript=[];const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{
 let v=await step({stage:'claude_verdict',topic,previous,evidence});push(v);
 let auto=0;const fixable=new Set(['REPORTING_OR_INFERENCE','EVIDENCE_RECONCILIATION']);
 while(v?.structured?.reported_verdict==='REVISE'&&!v?.structured?.human_action_required&&fixable.has(v?.structured?.revision_class)&&auto<2){
   auto++;
   const g=await step({stage:'gpt_revise',topic,previous,audit:v.text,evidence});push(g);previous=g.text;
   v=await step({stage:'claude_verdict',topic,previous,evidence});push(v);
 }
 const out={run_kind:'TEMP_BRANCH_PRODUCTION_BRIDGE_CONTINUATION',production_url:'https://magi-bridge-v4.vercel.app',topic,evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),spent_usd:spentUsd,spent_yen:spentUsd*FX,auto_revisions:auto,final_structured:v?.structured||null,transcript,completed_at:new Date().toISOString()};
 fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
}catch(err){const out={run_kind:'TEMP_BRANCH_PRODUCTION_BRIDGE_CONTINUATION',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.error(JSON.stringify(out,null,2));process.exit(1)}
