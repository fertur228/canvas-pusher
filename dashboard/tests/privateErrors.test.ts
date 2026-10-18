import {describe,it,expect} from 'vitest';
import {PrivateRequestError,privateErrorMessage,responseError} from '../src/privateErrors';

describe('sanitized private diagnostics',()=>{
  it.each([
    [400,'42703','schema/query mismatch'],
    [400,'PGRST204','schema/query mismatch'],
    [401,'PGRST301','Authentication expired'],
    [403,'42501','Access denied'],
    [503,undefined,'service unavailable'],
    [0,undefined,'Network request failed'],
    [400,'22023','Database request failed'],
  ])('separates HTTP %s / %s from missing ownership', (status,code,expected)=>{
    const error=new PrivateRequestError('Accounts',status,code);
    expect(privateErrorMessage(error)).toContain(expected);
    expect(error.message).toContain(`HTTP ${status||'unavailable'}`);
  });
  it('never returns private server text, response URLs or arbitrary errors',async()=>{
    const error=await responseError('Accounts',new Response(JSON.stringify({code:'42703',message:'PRIVATE assignment',details:'Bearer SECRET',hint:'private-email@example.invalid'}),{status:400}));
    expect(error.message).toContain('42703');
    expect(error.message).not.toMatch(/PRIVATE|SECRET|private-email/);
    expect(privateErrorMessage(new Error('SECRET'))).not.toContain('SECRET');
    expect(new PrivateRequestError('Accounts',400,'Bearer SECRET').message).not.toContain('SECRET');
  });
});
