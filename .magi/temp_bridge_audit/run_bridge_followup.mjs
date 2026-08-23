import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE='https://magi-bridge-v4.vercel.app/api/step';
const FX=160;
const CAP_YEN=120;
let spentUsd=0;
const dir='/tmp/pkg1';
const expected={
  'T009R_checker_C_v3_candidate_final.py':'3cb1ff60df8463e63cf113b350099e80029a349f9e0270145c83d070792ef4d8',
  'T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json':'00f72b616bd14dea6a9befcb45b15cdbf3bf15c3f99d8537eda178ec20456e5c',
  'T009R_result_bundle_schema_v2_candidate.json':'2c19b35d2a72b224e6c96d52395bbc42db9c5625b90baffcae9373e48af5e84d',
  'T009R_checker_C_v3_selftest_stdout.txt':'69c2542b79f9bae05e1fc08c9ea860f5250527cc4beb1762d214a78af1c40980',
  'T009R_checker_C_v2_to_v3_summary_reaudit.json':'5ee8e8ced4d9b070260eb1b8192b0b3605af0f50bb9927f3a62255d3be213710',
  'T009R_v3_v2_adversarial_id_mapping.json':'7c3c68348854537ae9f38009db5bed7de14528b05a6472c31a0c09abf6f2effd',
  'T009R_transfer_failure_run_32639578452.json':'f85cdc09170d0db8974f074a094512cf7c7989af51f6970abb4451732ed44c8e',
  'T009R_Ra_gt_1_diagnostic_sample.json':'7505d13d78d592db5084b082cbe485f105fc33bb41f4d73c9ad129506ed6702d',
  'T009R_prereg_v0_5_collision_incident_20260823.json':'7282b1d2f3679e3b3d778d357a55d2147f4b5781857fbf7e426e8e66595f97c3'
};
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const raw={};
for(const [name,want] of Object.entries(expected)){
  const content=fs.readFileSync(`${dir}/${name}`,'utf8');
  const got=sha(content);
  if(got!==want)throw new Error(`EVIDENCE_HASH_MISMATCH ${name} ${got}`);
  raw[name]=content;
}
const contextObj={
  context_id:'T009R-CHECKER-C-V3-REAUDIT-CONTEXT-EXACT',
  source_integrity:'Every embedded source below was independently SHA-256 verified immediately before this context was built.',
  prereg_hash_continuity:{selftest_sha256:expected['T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json'],bridge_input_sha256:expected['T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json'],equal:true},
  source_sha256:{id_mapping:expected['T009R_v3_v2_adversarial_id_mapping.json'],transport_failure:expected['T009R_transfer_failure_run_32639578452.json'],ra_diagnostic:expected['T009R_Ra_gt_1_diagnostic_sample.json'],prereg_collision_incident:expected['T009R_prereg_v0_5_collision_incident_20260823.json'],summary_reaudit_verified_but_not_embedded_due_bridge_5_file_limit:expected['T009R_checker_C_v2_to_v3_summary_reaudit.json']},
  id_mapping:JSON.parse(raw['T009R_v3_v2_adversarial_id_mapping.json']),
  transport_failure:JSON.parse(raw['T009R_transfer_failure_run_32639578452.json']),
  ra_gt_1_diagnostic_sample:JSON.parse(raw['T009R_Ra_gt_1_diagnostic_sample.json']),
  prereg_v0_5_collision_incident:JSON.parse(raw['T009R_prereg_v0_5_collision_incident_20260823.json'])
};
const context=JSON.stringify(contextObj,null,2);
const evidence=[
  {name:'T009R_checker_C_v3_candidate_final.txt',type:'text/plain',content:raw['T009R_checker_C_v3_candidate_final.py']},
  {name:'T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json',type:'application/json',content:raw['T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json']},
  {name:'T009R_result_bundle_schema_v2_candidate.json',type:'application/json',content:raw['T009R_result_bundle_schema_v2_candidate.json']},
  {name:'T009R_checker_C_v3_selftest_stdout.txt',type:'text/plain',content:raw['T009R_checker_C_v3_selftest_stdout.txt']},
  {name:'T009R_v3_reaudit_context_exact.json',type:'application/json',content:context}
].map(e=>({...e,size:Buffer.byteLength(e.content),client_sha256:sha(e.content)}));
if(evidence.length!==5)throw new Error(`EVIDENCE_COUNT ${evidence.length}`);
const totalChars=evidence.reduce((a,e)=>a+e.content.length,0);if(totalChars>80000)throw new Error(`EVIDENCE_TOO_LARGE ${totalChars}`);
const topic=`T009R Checker C v3のゼロベース・コード再監査。18 self-test PASSだけを理由にLOCK候補とは判定しないこと。Bridge投入直前のhash chainはPASSし、prereg self-test SHAとBridge input SHAはいずれも00f72b616bd14dea6a9befcb45b15cdbf3bf15c3f99d8537eda178ec20456e5c。Checker C v3 raw code SHA=3cb1ff60df8463e63cf113b350099e80029a349f9e0270145c83d070792ef4d8（Bridge表示名のみ.txt、内容は.py原本とbyte-identical）。self-test 18 IDとv2 blocker/required test IDの対応を件数でなくID集合として監査すること。転送失敗 run 32639578452 はTRANSPORT_DECODE_FAIL_BEFORE_HASH_CHECKで、誤証拠がClaudeへ到達する前に機械停止した証跡として保存済み。Ra>1はImplementation A/BのFULL/A/B各partitionで出力されるsecondary diagnosticでD/SUPPORTED判定を変更してはならない。同名prereg v0.5 collisionはserialization差ではなくsemantic content differenceによるVERSION_MANAGEMENT_ACCIDENTで、v0.5名再利用禁止、変更版はv0.6-DRAFT以降。科学的閾値、Gate、SUPPORTED条件は変更禁止。preregはDRAFTでhuman-only anchor/custody、expected pre-outcome manifest hash、A/B実装等のLOCK blockerが残るため、今回PASSし得るのはChecker C v3コードレベル監査だけでtrial/prereg全体LOCKは禁止。v2 blocker closureだけでなく、新しい攻撃面、hash/prereg binding、manifest binding、exception evidence preservation、schema allowlist、FULL=A+B、feasibility、tolerance、primitive-derived verdict、Ra診断をコードから独立再監査し、残存blockerがあれば具体的に示すこと。`;
async function step(payload){const remaining=Math.max(0,CAP_YEN-spentUsd*FX);if(remaining<=0)throw new Error('BUDGET_CAP');const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:remaining,budget_fx_yen_per_usd:FX})});const text=await r.text();let d;try{d=JSON.parse(text)}catch{throw new Error(`NON_JSON_${r.status}:${text.slice(0,500)}`)}if(!r.ok)throw new Error(d.error||`HTTP_${r.status}`);if(d.usage?.usd!=null)spentUsd+=Number(d.usage.usd||0);return d}
const transcript=[];const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{let g=await step({stage:'gpt_initial',topic,evidence});push(g);let a=await step({stage:'claude_audit',topic,previous:g.text,evidence});push(a);g=await step({stage:'gpt_revise',topic,previous:g.text,audit:a.text,evidence});push(g);let v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v);let auto=0;const fixable=new Set(['REPORTING_OR_INFERENCE','EVIDENCE_RECONCILIATION']);while(v?.structured?.reported_verdict==='REVISE'&&!v?.structured?.human_action_required&&fixable.has(v?.structured?.revision_class)&&auto<2){auto++;g=await step({stage:'gpt_revise',topic,previous:g.text,audit:v.text,evidence});push(g);v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v)}const out={run_kind:'TEMP_BRANCH_FRESH_PRODUCTION_BRIDGE_REAUDIT_EXACT_SNAPSHOT',production_url:BASE,pre_bridge_hash_verification:'PASS',prereg_snapshot_sha256:expected['T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json'],checker_v3_sha256:expected['T009R_checker_C_v3_candidate_final.py'],context_sha256:sha(context),evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),evidence_total_chars:totalChars,spent_usd:spentUsd,spent_yen:spentUsd*FX,auto_revisions:auto,final_structured:v?.structured||null,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));}catch(err){const out={run_kind:'TEMP_BRANCH_FRESH_PRODUCTION_BRIDGE_REAUDIT_EXACT_SNAPSHOT',pre_bridge_hash_verification:'PASS',prereg_snapshot_sha256:expected['T009R_Confirmatory_Prereg_DRAFT_v0.5_snapshot_00f72b61.json'],checker_v3_sha256:expected['T009R_checker_C_v3_candidate_final.py'],error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));console.error(JSON.stringify(out,null,2));process.exit(1)}
