/** Browser flow uses mock HTTP + actual immutable engine export. RLS is tested separately in PostgreSQL. */
import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
const blob=readFileSync(new URL('../../../data/neural/runs/escape-resumed-20261014/strong-1.json.gz',import.meta.url));
const raw=JSON.parse(gunzipSync(blob).toString());
const event='a'.repeat(64),account='00000000-0000-0000-0000-000000000001';
const path=`${account}/${event}/${createHash('sha256').update(blob).digest('hex')}.json.gz`;
const row={event_id:event,account_id:account,created_at:raw.created_at_utc,metadata:{status:'complete',encoding:{case:'strong'},telemetry_path:path,telemetry_sha256:createHash('sha256').update(blob).digest('hex'),activity_sha256:raw.activity_sha256,source_code_sha256:{},readout:{classification:'elevated',biological_response_validated:false}}};
const jwt=['eyJhbGciOiJIUzI1NiJ9',Buffer.from(JSON.stringify({sub:account,role:'authenticated',exp:Math.floor(Date.now()/1000)+3600})).toString('base64url'),'SYNTHETIC_SIGNATURE'].join('.');
test('requires sign-in, privately replays real activity, clears session on sign-out',async({page})=>{
 let requests=0;
 await page.route('https://test.supabase.co/**',async route=>{
 requests++;const url=route.request().url();
 if(url.includes('/auth/v1/token'))return route.fulfill({json:{access_token:jwt,refresh_token:'SYNTHETIC',expires_in:3600,token_type:'bearer',user:{id:account,email:'owner@example.invalid',aud:'authenticated',role:'authenticated'}}});
 expect(route.request().headers().authorization).toBe(`Bearer ${jwt}`);
 if(url.includes('/flymind_accounts'))return route.fulfill({json:[{id:account,telegram_chat_id:-100,enabled:true}]});
 if(url.includes('/flymind_experiments'))return route.fulfill({json:[row]});
 if(url.includes('/flymind_health'))return route.fulfill({json:[{last_attempt:new Date().toISOString(),status:'healthy',queue:{'send.done':1}}]});
 if(url.includes('/flymind_attempts'))return route.fulfill({json:[]});
 if(url.includes('/flymind_events'))return route.fulfill({json:{event:{kind:'assignment_created',observed_at:new Date().toISOString(),payload:{name:'<SYNTHETIC task>',course_name:'SYNTHETIC course'}}}});
 if(url.includes('/storage/'))return route.fulfill({body:blob,contentType:'application/gzip'});
 return route.fulfill({status:204});
 });
 await page.goto('/');await expect(page.getByRole('heading',{name:'FlyMind · owner sign-in'})).toBeVisible();expect(requests).toBe(0);
 await page.getByLabel('Email').fill('owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill('SYNTHETIC_ONLY');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Overview & system health'})).toBeVisible();
 await page.getByRole('button',{name:/strong · elevated/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('834');
 await expect(page.getByText(/Trigger: assignment_created/)).toContainText('<SYNTHETIC task>');
 await expect(page.getByText(/Other profiles are bundled research references/)).toBeVisible();
 expect(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.includes('auth-token')))).toBe(false);
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'FlyMind · owner sign-in'})).toBeVisible();await expect(page.getByTestId('total-spikes')).toHaveCount(0);
});
test('unauthorized metadata does not expose experiments or silently switch to demo',async({page})=>{
 await page.route('https://test.supabase.co/**',route=>route.request().url().includes('/auth/v1/token')?route.fulfill({json:{access_token:jwt,refresh_token:'SYNTHETIC',expires_in:3600,token_type:'bearer',user:{id:account,aud:'authenticated',role:'authenticated'}}}):route.fulfill({status:403,json:{message:'denied'}}));
 await page.goto('/');await page.getByLabel('Email').fill('other@example.invalid');await page.getByLabel('Password',{exact:true}).fill('SYNTHETIC');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Private metadata unavailable');await expect(page.getByTestId('total-spikes')).toHaveCount(0);
});

test('production health cannot be masked by test account; switching clears the loaded replay',async({page})=>{
 const production='00000000-0000-0000-0000-000000000002';
 const scopes:string[]=[];
 await page.route('https://test.supabase.co/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname.includes('/auth/v1/token'))return route.fulfill({json:{access_token:jwt,refresh_token:'SYNTHETIC',expires_in:3600,token_type:'bearer',user:{id:account,aud:'authenticated',role:'authenticated'}}});
  if(url.pathname.includes('/flymind_accounts'))return route.fulfill({json:[{id:account,telegram_chat_id:-100,enabled:true},{id:production,telegram_chat_id:100,enabled:true}]});
  const scope=url.searchParams.get('account_id');
  if(url.pathname.includes('/rest/')){expect([`eq.${account}`,`eq.${production}`]).toContain(scope);scopes.push(scope!);}
  if(url.pathname.includes('/flymind_experiments'))return route.fulfill({json:scope===`eq.${production}`?[]:[row]});
  if(url.pathname.includes('/flymind_health'))return route.fulfill({json:[{last_attempt:new Date().toISOString(),status:scope===`eq.${production}`?'degraded':'healthy',queue:{}}]});
  if(url.pathname.includes('/flymind_attempts'))return route.fulfill({json:[]});
  if(url.pathname.includes('/flymind_events'))return route.fulfill({json:{event:{kind:'assignment_created',payload:{name:'SYNTHETIC TEST GROUP'},observed_at:new Date().toISOString()}}});
  if(url.pathname.includes('/storage/'))return route.fulfill({body:blob,contentType:'application/gzip'});
  return route.fulfill({status:204});
 });
 await page.goto('/');await page.getByLabel('Email').fill('owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill('SYNTHETIC');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByLabel('Account',{exact:true})).toHaveValue(production);
 await expect(page.getByText('degraded',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:/strong · elevated/})).toHaveCount(0);
 await page.getByLabel('Account',{exact:true}).selectOption(account);
 await page.getByRole('button',{name:/strong · elevated/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('834');
 await page.getByLabel('Account',{exact:true}).selectOption(production);
 await expect(page.getByText('degraded',{exact:true})).toBeVisible();await expect(page.getByTestId('total-spikes')).toHaveCount(0);
 await expect(page.getByText(/Trigger: assignment_created/)).toHaveCount(0);
 expect(scopes).toContain(`eq.${account}`);expect(scopes).toContain(`eq.${production}`);
});
