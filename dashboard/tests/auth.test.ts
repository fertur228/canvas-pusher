import {describe,it,expect} from 'vitest';
import {validatePublicConfig} from '../src/auth';
import {boundedBytes} from '../src/supabase';
import {healthState} from '../src/PrivateObservatory';
describe('private access safety',()=>{
 it('rejects service secrets, URLs with credentials and forged non-anon public keys',()=>{
  for(const key of ['sb_secret_private','x.'+btoa(JSON.stringify({role:'service_role'}))+'.x'])expect(()=>validatePublicConfig('https://project.supabase.co',key)).toThrow();
  expect(()=>validatePublicConfig('https://user:pass@project.supabase.co','sb_publishable_test')).toThrow();
  expect(validatePublicConfig('https://project.supabase.co','sb_publishable_test').url).toBe('https://project.supabase.co');
 });
 it('bounds compressed and decompressed streaming bodies',async()=>{
  await expect(boundedBytes(new Blob(['12345']).stream(),4)).rejects.toThrow('size limit');
  expect((await boundedBytes(new Blob(['1234']).stream(),4)).byteLength).toBe(4);
 });
 it('stale heartbeat never appears healthy',()=>{
  const h={last_attempt:'2026-10-14T00:00:00Z',last_canvas_success:null,last_database_success:null,last_neural_success:null,last_telegram_success:null,status:'healthy',error_code:null,queue:{}};
  expect(healthState(h,Date.parse('2026-10-14T00:31:00Z'))).toBe('delayed');
  expect(healthState(h,Date.parse('2026-10-14T02:00:00Z'))).toBe('failed');
  expect(healthState(undefined)).toBe('unknown');
 });
});
