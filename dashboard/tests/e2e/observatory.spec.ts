import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
test('replays real data, switches experiments and inspects recorded coverage',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'Observe the circuit.'})).toBeVisible();
 await expect(page.getByTestId('total-spikes')).toHaveText('834');
 await expect(page.getByTestId('selected-root-id')).toHaveText('720575940622838154');
 await expect(page.getByText('GRAPH LAYOUT · NON-ANATOMICAL')).toBeVisible();
 await expect(page.locator('.scene canvas')).toBeVisible();
 await expect(page.locator('.scene canvas')).toHaveAttribute('data-readout-positions',/720575940632499757/);
 const positions=JSON.parse((await page.locator('.scene canvas').getAttribute('data-readout-positions'))!);
 const target=positions.find((n:{id:string})=>n.id==='720575940632499757');
 await page.locator('.scene canvas').click({position:{x:target.x,y:target.y}});
 await expect(page.getByTestId('selected-root-id')).toHaveText('720575940632499757');
 await page.getByLabel('Replay timeline').fill('281');
 await expect.poll(async()=>Number(await page.locator('.scene canvas').getAttribute('data-draw-calls'))).toBe(2);
 await page.getByLabel('Spatial layout').selectOption('soma');await expect(page.getByText('REAL SOMA · 1497/1,500 available')).toBeVisible();
 await page.getByLabel('Connection scope').selectOption('all');await expect(page.getByText(/largest 2,000/)).toBeVisible();
 await page.getByRole('tab',{name:/Baseline/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('0');
 await page.getByRole('tab',{name:/Weak/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('344');
 await page.getByLabel('Replay timeline').fill('850');await expect(page.getByTestId('replay-time')).toHaveText('850.0');
 await page.getByLabel('Replay speed').selectOption('0.25');await page.getByLabel('Play replay').click();await page.waitForTimeout(200);await page.getByLabel('Pause replay').click();expect(Number(await page.getByTestId('replay-time').textContent())).toBeGreaterThan(850);
 await page.getByLabel('Restart replay').click();await expect(page.getByTestId('replay-time')).toHaveText('0.0');
 await page.getByLabel('Find neuron by ID or type').fill('720575940601712649');await page.getByRole('button',{name:/720575940601712649/}).click();await expect(page.getByText('Voltage was not recorded for this neuron.')).toBeVisible();
 await page.getByLabel('Find neuron by ID or type').fill('720575940632499757');await page.getByRole('button',{name:/720575940632499757/}).click();await expect(page.getByText('0.1 ms samples')).toBeVisible();
 await page.getByRole('tab',{name:/Strong/}).click();await page.getByLabel('Replay timeline').fill('280');await page.getByLabel('Spatial layout').selectOption('graph');await page.getByLabel('Connection scope').selectOption('GF');
 await page.screenshot({path:'test-results/observatory-desktop.png',fullPage:true});
 const metrics=await page.evaluate(()=>({draw_calls:Number(document.querySelector('.scene canvas')?.getAttribute('data-draw-calls')),heap_bytes:(performance as Performance & {memory?:{usedJSHeapSize:number}}).memory?.usedJSHeapSize,resource_bytes:performance.getEntriesByType('resource').filter(r=>r.name.includes('/data/')).reduce((s,r)=>s+(r as PerformanceResourceTiming).decodedBodySize,0)}));
 writeFileSync('test-results/browser-metrics.json',JSON.stringify({renderer:'Chrome SwiftShader (software WebGL; not a hardware FPS benchmark)',...metrics},null,2));
 expect(errors).toEqual([]);
});
test('works on mobile without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await expect(page.getByTestId('total-spikes')).toHaveText('834');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.getByRole('tab',{name:/Weak/}).click();await expect(page.getByTestId('total-spikes')).toHaveText('344');
 await page.screenshot({path:'test-results/observatory-mobile.png',fullPage:true});
});

test('shows a recoverable integrity error for mutated assets',async({page})=>{
 await page.route('**/data/strong.json',route=>route.fulfill({body:'modified',contentType:'application/json'}));
 await page.goto('/');await expect(page.getByRole('alert')).toContainText('checksum mismatch');await expect(page.getByRole('button',{name:'Retry loading verified telemetry'})).toBeVisible();
});
test('static production build serves the same recorded experiment',async({page})=>{
 // A dedicated static-server smoke check is run separately; the dist assets are
 // also required here so accidental omission of public telemetry fails early.
 const catalog=JSON.parse(readFileSync('dist/data/catalog.json','utf8'));
 expect(catalog.experiments.map((e:{spikes:number})=>e.spikes)).toEqual([0,344,834]);
 await page.goto('/');await page.getByLabel('Compare signals').uncheck();await expect(page.locator('.chart-legend').first()).toHaveText('● strong');
});
