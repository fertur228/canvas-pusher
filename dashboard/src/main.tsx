import { createRoot } from 'react-dom/client';
import { Component, lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import App from './App';
import './styles.css';
const PrivateObservatory=lazy(()=>import('./PrivateObservatory'));
class Boundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<div className="loading-screen"><h1>Observatory unavailable</h1><p role="alert">A display error occurred. Reload to reset the private session.</p><button onClick={()=>location.reload()}>Reload</button></div>:this.props.children;}
}
const mode=import.meta.env.VITE_OBSERVATORY_DATA_SOURCE||'local';
createRoot(document.getElementById('root')!).render(<Boundary><Suspense fallback={<p>Loading Observatory…</p>}>{mode==='local'?<App/>:mode==='supabase'?<PrivateObservatory/>:<p role="alert">Invalid Observatory data source</p>}</Suspense></Boundary>);
