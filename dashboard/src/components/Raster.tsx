import { useEffect, useRef, useState } from 'react';
import { kind, neuronColor } from '../analysis';
import type { Graph, LoadedExperiment } from '../telemetry';
export default function Raster({graph, experiment, time, selected, onSelect, onSeek}:{graph:Graph;experiment:LoadedExperiment;time:number;selected:number;onSelect:(i:number)=>void;onSeek:(t:number)=>void}) {
  const ref=useRef<HTMLCanvasElement>(null), [filter,setFilter]=useState('all'), [width,setWidth]=useState(600);
  const indices=graph.neurons.map((_,i)=>i).filter(i=>filter==='all'||kind(graph.neurons[i])===filter);
  const rows=new Map(indices.map((n,i)=>[n,i]));
  const left=48, top=12, height=240, right=22, bottom=28;
  useEffect(()=>{if (!ref.current) return; const observer=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width)); observer.observe(ref.current); return()=>observer.disconnect();},[]);
  useEffect(()=>{
    const canvas=ref.current;if(!canvas)return;const dpr=Math.min(devicePixelRatio,2);canvas.width=width*dpr;canvas.height=height*dpr;const ctx=canvas.getContext('2d');if(!ctx)return;ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);
    const w=width-left-right,h=height-top-bottom;
    ctx.font='10px monospace';ctx.fillStyle='#7f8b9d';ctx.strokeStyle='#202c3b';
    for(let i=0;i<=5;i++){const x=left+i*w/5;ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,top+h);ctx.stroke();ctx.fillText(String(Math.round(i*experiment.parameters.duration_ms/5)),x-10,height-12);}
    ctx.fillText('row 0',2,top+7);ctx.fillText(String(indices.length-1),6,top+h);ctx.fillText('time (ms)',width/2-25,height-1);
    const row=rows.get(selected);if(row!==undefined){ctx.fillStyle='#ffffff12';ctx.fillRect(left,top+row/indices.length*h-2,w,4);}
    for(const [t,n] of experiment.spikes){const r=rows.get(n);if(r===undefined)continue;ctx.fillStyle=neuronColor(graph.neurons[n]);ctx.fillRect(left+t/experiment.parameters.duration_ms*w,top+(r+.5)/indices.length*h,1.8,Math.max(1,h/indices.length));}
    ctx.strokeStyle='#edb66b';const x=left+time/experiment.parameters.duration_ms*w;ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,top+h);ctx.stroke();
  });
  return <section className="panel"><div className="panel-heading"><div><span className="eyebrow">02 / EVENTS</span><h2>Spike raster</h2></div><select aria-label="Raster population" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All 1,500 neurons</option><option>LC4</option><option>LPLC2</option><option value="GF">Giant Fiber</option></select></div><canvas ref={ref} className="raster" aria-label="Exact recorded simulation spike raster" onClick={e=>{const rect=e.currentTarget.getBoundingClientRect();const x=e.clientX-rect.left,y=e.clientY-rect.top;if(x<left||y<top||y>height-bottom)return;onSeek(Math.min(experiment.parameters.duration_ms,Math.max(0,(x-left)/(width-left-right)*experiment.parameters.duration_ms)));const row=Math.min(indices.length-1,Math.max(0,Math.floor((y-top)/(height-top-bottom)*indices.length)));if(indices[row]!==undefined)onSelect(indices[row]);}}/><p className="caption">Exact simulation events · rows follow the original neuron ID order · {experiment.spikes.length} spikes. Click a row to inspect and seek; full IDs are in the inspector.</p></section>;
}
