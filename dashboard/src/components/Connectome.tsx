import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Component, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { displayPositions, neuronColor, kind, modelSign, recentSpikes } from '../analysis';
import type { Pair } from '../analysis';
import type { Graph, LoadedExperiment } from '../telemetry';

type Props = { graph: Graph; experiment: LoadedExperiment; pairs: Pair[]; selected: number; onSelect: (i:number) => void; time: number };
function Controls() {
  const { camera, gl, invalidate } = useThree();
  useEffect(() => { const controls = new OrbitControls(camera, gl.domElement); controls.enableDamping = false; controls.minDistance = 10; controls.maxDistance = 100; controls.addEventListener('change', () => invalidate()); return () => controls.dispose(); }, [camera, gl, invalidate]);
  return null;
}
function Nodes({ graph, experiment, positions, indices, selected, onSelect, time }: Props & { positions: ([number,number,number] | null)[]; indices:number[] }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const active = useMemo(() => recentSpikes(experiment, time), [experiment, time]);
  const scratch = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);
  const invalidate = useThree(s => s.invalidate);
  useEffect(() => {
    if (!ref.current) return;
    indices.forEach((ni, instance) => {
      scratch.position.set(...positions[ni]!);
      const size = ni === selected ? .48 : kind(graph.neurons[ni]) === 'GF' ? .36 : active.has(ni) ? .21 : .12;
      scratch.scale.setScalar(size); scratch.updateMatrix(); ref.current!.setMatrixAt(instance, scratch.matrix);
      color.set(ni === selected ? '#ffffff' : active.has(ni) ? '#f3dfb8' : neuronColor(graph.neurons[ni])); ref.current!.setColorAt(instance, color);
    });
    ref.current.instanceMatrix.needsUpdate = true;
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true;
    ref.current.computeBoundingSphere();
    invalidate();
  }, [positions, indices, selected, active, graph, scratch, color, invalidate]);
  return <instancedMesh ref={ref} args={[undefined, undefined, indices.length]} onClick={e => { e.stopPropagation(); if (e.instanceId !== undefined) onSelect(indices[e.instanceId]); }}><sphereGeometry args={[1, 8, 6]}/><meshBasicMaterial toneMapped={false}/></instancedMesh>;
}
function Edges({ graph, positions, pairs }: {graph:Graph; positions:([number,number,number]|null)[]; pairs:Pair[]}) {
  const geometry = useMemo(() => {
    const coords = new Float32Array(pairs.length * 18), colors = new Float32Array(coords.length);
    const c = new THREE.Color();
    pairs.forEach((p,i) => { const a = new THREE.Vector3(...positions[p.pre]!), b = new THREE.Vector3(...positions[p.post]!);
      const direction = b.clone().sub(a).normalize();
      const tip = a.clone().lerp(b,.78);
      const normal = new THREE.Vector3(0,1,0).cross(direction);
      if (normal.lengthSq()<.001) normal.set(1,0,0);
      normal.normalize().multiplyScalar(.13);
      const stem = tip.clone().addScaledVector(direction,-.35);
      coords.set([...a.toArray(), ...b.toArray(), ...tip.toArray(), ...stem.clone().add(normal).toArray(), ...tip.toArray(), ...stem.clone().sub(normal).toArray()], i*18);
      c.set(modelSign(graph.neurons[p.pre]) < 0 ? '#755d81' : '#405e6b'); for (let k=0;k<6;k++) colors.set([c.r,c.g,c.b], i*18+k*3); });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(coords,3)); g.setAttribute('color',new THREE.BufferAttribute(colors,3)); return g;
  }, [pairs, positions, graph]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <lineSegments geometry={geometry}><lineBasicMaterial vertexColors transparent opacity={.26} depthWrite={false}/></lineSegments>;
}
function RenderMetrics({graph,positions}:{graph:Graph;positions:([number,number,number]|null)[]}) {
  const {gl,camera} = useThree();
  useFrame(() => {
    gl.domElement.dataset.drawCalls=String(gl.info.render.calls);
    gl.domElement.dataset.readoutPositions=JSON.stringify(graph.neurons.flatMap((n,i)=>{
      if(n.role!=='readout'||!positions[i])return [];
      const p=new THREE.Vector3(...positions[i]!).project(camera);
      return [{id:n.root_id,x:(p.x+1)*gl.domElement.clientWidth/2,y:(1-p.y)*gl.domElement.clientHeight/2}];
    }));
  });
  return null;
}
class WebGLBoundary extends Component<{children:ReactNode}, {failed:boolean}> {
  state = {failed:false};
  static getDerivedStateFromError() {return {failed:true};}
  render() {return this.state.failed ? <div className="viewer-error">WebGL is unavailable. All scientific charts and the neuron inspector remain available.</div> : this.props.children;}
}
export default function Connectome(props: Props) {
  const [anatomical, setAnatomical] = useState(false), [scope, setScope] = useState('GF'), [minimum, setMinimum] = useState(5), [onlyActive, setOnlyActive] = useState(false), [reset, setReset] = useState(0);
  const positions = useMemo(() => displayPositions(props.graph, anatomical), [props.graph, anatomical]);
  const indices = useMemo(() => props.graph.neurons.map((_,i)=>i).filter(i => positions[i] && (!onlyActive || props.experiment.activity[i].spike_count > 0 || i === props.selected)), [props.graph, positions, onlyActive, props.experiment, props.selected]);
  const visible = useMemo(() => new Set(indices), [indices]);
  const eligible = useMemo(() => props.pairs.filter(p => p.count >= minimum && visible.has(p.pre) && visible.has(p.post) && (scope==='all' || (scope==='GF' ? props.graph.neurons[p.post].role==='readout' : p.pre===props.selected || p.post===props.selected))), [props.pairs, minimum, visible, scope, props.graph, props.selected]);
  const edges = useMemo(() => eligible.slice(0,2000), [eligible]);
  return <section className="panel connectome"><div className="panel-heading"><div><span className="eyebrow">01 / STRUCTURE</span><h2>Escape circuit</h2></div><span className="tag">FlyWire FAFB · v783</span></div>
    <div className="viewer-tools"><label>Layout <select aria-label="Spatial layout" value={anatomical?'soma':'graph'} onChange={e=>setAnatomical(e.target.value==='soma')}><option value="graph">Type-group graph</option><option value="soma" disabled={!props.graph.spatial.soma_count}>Real soma coordinates</option></select></label><label>Connections <select aria-label="Connection scope" value={scope} onChange={e=>setScope(e.target.value)}><option value="GF">Inputs to GF</option><option value="selected">Selected neuron</option><option value="all">All pairs</option></select></label><label>Min. synapses <input aria-label="Minimum synapses" type="number" min={1} max={1000} value={minimum} onChange={e=>setMinimum(Math.max(1,Number(e.target.value)||1))}/></label><button onClick={()=>setReset(r=>r+1)}>Reset view</button></div>
    <div className="scene"><WebGLBoundary><Canvas key={reset} frameloop="demand" dpr={[1,1.5]} camera={{position:[26,18,35],fov:45}} gl={{antialias:true, powerPreference:'high-performance'}}><color attach="background" args={['#0c141f']}/><Controls/><RenderMetrics graph={props.graph} positions={positions}/><Edges graph={props.graph} positions={positions} pairs={edges}/><Nodes {...props} positions={positions} indices={indices}/></Canvas></WebGLBoundary><div className="scene-label"><span className="status-dot"/>{anatomical ? `REAL SOMA · ${props.graph.spatial.soma_count}/1,500 available` : 'GRAPH LAYOUT · NON-ANATOMICAL'}</div><div className="scene-caption">{anatomical ? 'Soma positions from 4×4×40 nm voxels; uniform display scale. No neurite morphology.' : 'Deterministic cell-type grouping. Distances and axes have no anatomical meaning.'}<br/>Arrows run from pre- to postsynaptic cell; lines are not axon paths.</div></div>
    <div className="viewer-footer"><div className="legend"><span style={{color:'#57bba8'}}>● LC4</span><span style={{color:'#829df5'}}>● LPLC2</span><span style={{color:'#edb66b'}}>● GF</span><span>● Partners</span></div><label className="checkbox"><input type="checkbox" checked={onlyActive} onChange={e=>setOnlyActive(e.target.checked)}/>Spiking cells + selection</label></div>
    <p className="caption">{indices.length.toLocaleString()} nodes · {edges.length.toLocaleString()} of {eligible.length.toLocaleString()} qualifying pairs shown{eligible.length>2000?' (largest 2,000; display cap only)':''}. Flash = recorded spike in preceding 20 ms. Edge colors = assumed model sign.</p>
  </section>;
}
