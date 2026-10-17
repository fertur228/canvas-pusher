import {handler} from '../telegram-webhook/handler.ts';
import {flymindConfig} from './config.ts';

Deno.serve(handler(flymindConfig(name=>Deno.env.get(name)??'')));
