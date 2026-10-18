import { createClient } from '@supabase/supabase-js';
export function validatePublicConfig(url: string, key: string) {
  const origin=new URL(url);
  if(origin.protocol!=='https:'||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('Configure an HTTPS Supabase origin');
  if(!key||key.startsWith('sb_secret_'))throw new Error('Only a Supabase publishable key is allowed');
  if(!key.startsWith('sb_publishable_')) {
    let claims;try{claims=JSON.parse(atob(key.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));}catch{throw new Error('Invalid publishable key');}
    if(claims.role!=='anon')throw new Error('Service credentials forbidden in browser');
  }
  return {url:origin.origin,key};
}
export function ownerAuth() {
  const {url,key}=validatePublicConfig(import.meta.env.VITE_SUPABASE_URL||'',import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY||'');
  // Single-owner password login; no registration, redirects or tokens in URLs.
  // Memory-only session; reload intentionally requires sign-in. SDK refreshes while open.
  return createClient(url,key,{auth:{persistSession:false,autoRefreshToken:true,detectSessionInUrl:false}});
}
