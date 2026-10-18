/** Explicit hosted QA, real Auth/REST/Storage. Fresh headless profile, no HTTP mocks. */
import {chromium,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {writeFileSync} from 'node:fs';

const e=process.env;
if(e.FLYMIND_HOSTED_TEST!=='isolated-auth' || e.FLYMIND_PREVIEW_URL!=='https://flymind-preview.flymind-observatory.pages.dev/' || !e.FLYMIND_TEST_EMAIL?.endsWith('@example.invalid'))throw new Error('Explicit isolated test configuration required');
let browser,stage='launch';
try {
  browser=await chromium.launch({headless:true,executablePath:e.PLAYWRIGHT_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[];page.on('pageerror',()=>errors.push('pageerror'));
  let privateReads=0,artifactHash,artifactStatus,authStatus;
  const checks=[];
  page.on('response',r=>{
    const u=new URL(r.url());
    if(u.hostname!=='irjasmzytjeohwfpdnrl.supabase.co')return;
    if(u.pathname.startsWith('/rest/'))privateReads++;
    if(u.pathname==='/auth/v1/token')authStatus=r.status();
    if(u.pathname.startsWith('/storage/v1/object/authenticated/flymind-private/'))checks.push((async()=>{artifactStatus=r.status();artifactHash=createHash('sha256').update(await r.body()).digest('hex');})());
  });
  stage='anonymous_screen';await page.goto(e.FLYMIND_PREVIEW_URL);
  await expect(page.getByRole('heading',{name:'FlyMind · owner sign-in'})).toBeVisible();
  expect(privateReads).toBe(0);
  stage='real_auth';await page.getByLabel('Email').fill(e.FLYMIND_TEST_EMAIL);
  await page.getByLabel('Password',{exact:true}).fill(e.FLYMIND_TEST_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  stage='private_metadata';await expect(page.getByLabel('Account',{exact:true})).toHaveValue(e.FLYMIND_TEST_ACCOUNT,{timeout:30000});
  await expect(page.getByLabel('Account',{exact:true}).locator('option')).toHaveCount(1);
  await expect(page.getByText('healthy',{exact:true})).toBeVisible();
  await expect(page.locator('.run-list button')).toHaveCount(1);
  stage='private_replay';await page.getByRole('button',{name:/strong · elevated/}).click();
  await expect(page.getByText('verified private download',{exact:true})).toBeVisible({timeout:30000});
  await expect(page.getByTestId('total-spikes')).toHaveText(e.FLYMIND_EXPECTED_SPIKES);
  await expect(page.locator('.scene canvas')).toBeVisible();
  await page.getByLabel('Find neuron by ID or type').fill('720575940632499757');
  await page.getByRole('button',{name:/720575940632499757/}).click();
  await expect(page.getByText('0.1 ms samples')).toBeVisible();
  await page.getByLabel('Replay timeline').fill('280');
  await expect(page.getByTestId('replay-time')).toHaveText('280.0');
  await page.getByLabel('Play replay').click();
  await expect.poll(async()=>Number(await page.getByTestId('replay-time').textContent())).toBeGreaterThan(280);
  await page.getByLabel('Pause replay').click();
  await page.getByRole('tab',{name:/Weak/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('344');
  await page.getByRole('tab',{name:/Strong/}).click();await expect(page.getByTestId('total-spikes')).toHaveText(e.FLYMIND_EXPECTED_SPIKES);
  await page.getByLabel('Compare signals').uncheck();await expect(page.locator('.chart-legend').first()).toHaveText('● strong');
  await page.getByLabel('Compare signals').check();
  await page.getByLabel('Spatial layout').selectOption('soma');await expect(page.getByText('REAL SOMA · 1497/1,500 available')).toBeVisible();
  await Promise.all(checks);expect(artifactStatus).toBe(200);expect(authStatus).toBe(200);expect(artifactHash).toBe(e.FLYMIND_EXPECTED_HASH);expect(errors).toEqual([]);
  expect(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.includes('auth-token')))).toBe(false);
  stage='sign_out';await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByRole('heading',{name:'FlyMind · owner sign-in'})).toBeVisible();await expect(page.getByTestId('total-spikes')).toHaveCount(0);
  writeFileSync(e.FLYMIND_BROWSER_REPORT,JSON.stringify({status:'passed',real_hosted_frontend:true,isolated_test_identity:true,owner_browser_verified:false,http_mocks:false,auth_http:authStatus,private_storage_http:artifactStatus,sha256_verified:true,account_selector:true,health:true,experiment_history:true,real_engine_decoder:true,spikes:Number(e.FLYMIND_EXPECTED_SPIKES),timeline_play_pause_scrub:true,comparison:true,real_soma:true,private_data_cleared_on_signout:true,javascript_errors:errors.length},null,2));
} catch {console.error(JSON.stringify({status:'failed',stage,private_details_omitted:true}));process.exitCode=1;}
finally {await browser?.close();}
