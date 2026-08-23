import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE='https://magi-bridge-v4.vercel.app/api/step';
const FX=160;
const CAP_YEN=120;
let spentUsd=0;
const dir='/tmp/pkg1';
const defs=[
  {path:'T009R_checker_C_v3_candidate_final.py',name:'T009R_checker_C_v3_candidate_final.txt',type:'text/plain'},
  {path:'T009R_Confirmatory_Prereg_DRAFT_v0.5.json',name:'T009R_Confirmatory_Prereg_DRAFT_v0.5.json',type:'application/json'},
  {path:'T009R_result_bundle_schema_v2_candidate.json',name:'T009R_result_bundle_schema_v2_candidate.json',type:'application/json'},
  {path:'T009R_checker_C_v3_selftest_stdout.txt',name:'T009R_checker_C_v3_selftest_stdout.txt',type:'text/plain'},
  {path:'T009R_checker_C_v2_to_v3_summary.json',name:'T009R_checker_C_v2_to_v3_summary.json',type:'application/json'}
];
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const evidence=defs.map(d=>{const content=fs.readFileSync(`${dir}/${d.path}`,'utf8');return {name:d.name,type:d.type,size:Buffer.byteLength(content),content,client_sha256:sha(content)}});
const expected={
  'T009R_checker_C_v3_candidate_final.txt':'3cb1ff60df8463e63cf113b350099e80029a349f9e0270145c83d070792ef4d8',
  'T009R_Confirmatory_Prereg_DRAFT_v0.5.json':'00f72b616bd14dea6a9befcb45b15cdbf3bf15c3f99d8537eda178ec20456e5c',
  'T009R_result_bundle_schema_v2_candidate.json':'2c19b35d2a72b224e6c96d52395bbc42db9c5625b90baffcae9373e48af5e84d',
  'T009R_checker_C_v3_selftest_stdout.txt':'69c2542b79f9bae05e1fc08c9ea860f5250527cc4beb1762d214a78af1c40980',
  'T009R_checker_C_v2_to_v3_summary.json':'5ee8e8ced4d9b070260eb1b8192b0b3605af0f50bb9927f3a62255d3be213710'
};
for(const e of evidence){if(e.client_sha256!==expected[e.name])throw new Error(`EVIDENCE_HASH_MISMATCH ${e.name} ${e.client_sha256}`)}
const totalChars=evidence.reduce((a,e)=>a+e.content.length,0);if(totalChars>80000)throw new Error(`EVIDENCE_TOO_LARGE ${totalChars}`);
const topic=`T009R confirmatory Checker C v3のゼロベース再監査。これは同名Libraryファイルを混ぜず、18件adversarial self-testと完全対応する固定snapshotだけを証拠として使う。candidate SHA=3cb1ff60df8463e63cf113b350099e80029a349f9e0270145c83d070792ef4d8、prereg snapshot SHA=00f72b616bd14dea6a9befcb45b15cdbf3bf15c3f99d8537eda178ec20456e5c、schema SHA=2c19b35d2a72b224e6c96d52395bbc42db9c5625b90baffcae9373e48af5e84d。修正リストの答え合わせではなく、新しく追加したprereg/hash binding、expected-manifest binding、例外処理、schema v2、FULL=A+B、feasibility、relative+absolute tolerance、Ra>1診断が新しい攻撃面を作っていないかコードから再監査する。科学的閾値・Gate・SUPPORTED条件は変更禁止。preregは意図的にDRAFTで、expected_preoutcome_manifest_requirement.locked_sha256はhuman-only pre-outcome manifest作成前なのでTBDのまま。したがって全trialのLOCK可否ではなく、Checker C v3コードが『human anchorを埋めた後にLOCK候補へ昇格できる技術状態か』を判定する。self-test 18件を証拠として評価し、コードレベルblockerが残れば具体的に示す。コードレベルblockerが無ければChecker C candidate auditとしてPASSしてよいが、trial/prereg全体のLOCKはhuman anchor・custodyが終わるまで禁止と明記する。`;

async function step(payload){const remaining=Math.max(0,CAP_YEN-spentUsd*FX);if(remaining<=0)throw new Error('BUDGET_CAP');const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:remaining,budget_fx_yen_per_usd:FX})});const raw=await r.text();let d;try{d=JSON.parse(raw)}catch{throw new Error(`NON_JSON_${r.status}:${raw.slice(0,500)}`)}if(!r.ok)throw new Error(d.error||`HTTP_${r.status}`);if(d.usage?.usd!=null)spentUsd+=Number(d.usage.usd||0);return d}
const transcript=[];const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{
 let g=await step({stage:'gpt_initial',topic,evidence});push(g);
 let a=await step({stage:'claude_audit',topic,previous:g.text,evidence});push(a);
 g=await step({stage:'gpt_revise',topic,previous:g.text,audit:a.text,evidence});push(g);
 let v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v);
 let auto=0;const fixable=new Set(['REPORTING_OR_INFERENCE','EVIDENCE_RECONCILIATION']);
 while(v?.structured?.reported_verdict==='REVISE'&&!v?.structured?.human_action_required&&fixable.has(v?.structured?.revision_class)&&auto<2){auto++;g=await step({stage:'gpt_revise',topic,previous:g.text,audit:v.text,evidence});push(g);v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v)}
 const out={run_kind:'TEMP_BRANCH_FRESH_PRODUCTION_BRIDGE_REAUDIT',production_url:'https://magi-bridge-v4.vercel.app',topic,evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),evidence_total_chars:totalChars,spent_usd:spentUsd,spent_yen:spentUsd*FX,auto_revisions:auto,final_structured:v?.structured||null,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
}catch(err){const out={run_kind:'TEMP_BRANCH_FRESH_PRODUCTION_BRIDGE_REAUDIT',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.error(JSON.stringify(out,null,2));process.exit(1)}
