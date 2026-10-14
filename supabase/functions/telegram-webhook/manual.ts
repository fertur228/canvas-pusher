/** Fail closed before dispatch: an old main branch must never fall back to legacy delivery. */
export async function manualPreflight(config:{githubToken:string;repo:string;ref:string;manualEnabled?:boolean},account:string,request:typeof fetch) {
 if(!config.manualEnabled||!config.githubToken||!/^[\w.-]+\/[\w.-]+$/.test(config.repo)||!config.ref)throw new Error('manual_not_configured');
 const get=async(path:string)=>{const r=await request(`https://api.github.com/repos/${config.repo}/${path}`,{headers:{Authorization:`Bearer ${config.githubToken}`,Accept:'application/vnd.github+json'},signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error('github_configuration_unavailable');return r.json();};
 const names=['CANVAS_WORKER_ENABLED','FLYMIND_ENABLED','FLYMIND_ACCOUNT_ID','DELIVERY_MODE','FLYMIND_PRODUCTION_AUTHORIZED'];
 const values=await Promise.all(names.map(n=>get(`actions/variables/${n}`).then(x=>x.value)));
 if(values[0]!=='true'||values[1]!=='true'||values[2]!==account||!['test','production'].includes(values[3])||(values[3]==='production'&&values[4]!=='true'))throw new Error('worker_activation_gates_closed');
 const workflow=await get('actions/workflows/check_canvas.yml');
 if(workflow.state!=='active')throw new Error('worker_workflow_disabled');
 const code=await get(`contents/.github/workflows/check_canvas.yml?ref=${encodeURIComponent(config.ref)}`);
 if(code.encoding!=='base64')throw new Error('unverified_workflow');
 const source=atob(code.content.replace(/\s/g,''));
 if(!source.includes('MANUAL_REQUEST_ID:')||!source.includes('src.flymind.manual_sync run'))throw new Error('selected_branch_not_upgraded');
 const finalizer=await get('actions/workflows/flymind-manual-completion.yml');
 if(finalizer.state!=='active')throw new Error('completion_workflow_unavailable');
}
