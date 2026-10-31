import { useEffect, useRef, useState } from 'react';
import cytoscape, { type Core } from 'cytoscape';

export type GraphNode = {id:string;label:string;kind:string};
export type GraphEdge = {id:string;source:string;target:string;detection_id?:string;relationship?:string;status?:string};

export function AttackGraph({nodes,edges,onEvidence}:{nodes:GraphNode[];edges:GraphEdge[];onEvidence:(id:string)=>void}) {
  const container=useRef<HTMLDivElement>(null);
  const instance=useRef<Core|null>(null);
  const [selected,setSelected]=useState<Record<string,string>|null>(null);
  useEffect(()=>{
    if(!container.current)return;
    const visible=nodes.slice(0,100);
    const ids=new Set(visible.map(node=>node.id));
    const cy=cytoscape({container:container.current,
      elements:[...visible.map(node=>({data:node})),...edges.filter(edge=>ids.has(edge.source)&&ids.has(edge.target)).slice(0,300).map(edge=>({data:edge}))],
      layout:{name:'circle',padding:65}, minZoom:0.15,maxZoom:3,wheelSensitivity:0.2,
      style:[
        {selector:'node',style:{label:'data(label)','background-color':'#7197a4',color:'#dce9e5','font-size':11,'text-valign':'bottom','text-margin-y':10,width:24,height:24,'border-width':2,'border-color':'#14251f'}},
        {selector:'node[kind="actor"]',style:{'background-color':'#8fe89d',shape:'diamond',width:34,height:34}},
        {selector:'node[kind="account"]',style:{'background-color':'#cfb87c',shape:'round-rectangle'}},
        {selector:'edge',style:{width:1.5,'line-color':'#426155','curve-style':'bezier','target-arrow-shape':'triangle','target-arrow-color':'#426155'}},
        {selector:':selected',style:{'border-color':'#d8ff86','border-width':4,'line-color':'#d8ff86','target-arrow-color':'#d8ff86'}},
      ]});
    instance.current=cy; setSelected(null);
    cy.on('tap','node, edge',event=>setSelected(event.target.data()));
    const resize=new ResizeObserver(()=>cy.resize());resize.observe(container.current);
    return()=>{resize.disconnect();cy.destroy();instance.current=null;};
  },[nodes,edges]);
  return <div className="graph-workbench">
    <div className="graph-toolbar"><span>{nodes.length} entities / {edges.length} evidence associations</span><div><button onClick={()=>instance.current?.fit(undefined,65)}>Fit</button><button onClick={()=>{const cy=instance.current;if(cy)cy.zoom(cy.zoom()*1.25);}}>+</button><button onClick={()=>{const cy=instance.current;if(cy)cy.zoom(cy.zoom()/1.25);}}>−</button></div></div>
    <div ref={container} className="attack-graph" role="img" aria-label="Interactive incident evidence graph; drag nodes and use controls to zoom"/>
    <div className="graph-inspector" aria-live="polite">{selected?<><strong>{selected.label || selected.relationship || 'Evidence association'}</strong><dl>{Object.entries(selected).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>{selected.detection_id&&<button onClick={()=>onEvidence(selected.detection_id)}>Inspect supporting evidence</button>}</>:<p>Select a node or edge to inspect it. Drag nodes to arrange the graph.</p>}</div>
    <p className="console-note">Arrows show evidence associations, not confirmed attacker movement. Green: actor; gold: account; blue: target or reporting observer. Rendering capped at 100 nodes / 300 edges.</p>
  </div>;
}
