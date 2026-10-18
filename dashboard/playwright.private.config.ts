import {defineConfig} from '@playwright/test';
import config from './playwright.config';
export default defineConfig({...config,testDir:'./tests/private-e2e',use:{...config.use,baseURL:'http://127.0.0.1:5174'},webServer:{command:'npm run dev -- --port 5174',url:'http://127.0.0.1:5174',reuseExistingServer:false,env:{VITE_OBSERVATORY_DATA_SOURCE:'supabase',VITE_SUPABASE_URL:'https://test.supabase.co',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_publishable_SYNTHETIC_TEST'}}});
