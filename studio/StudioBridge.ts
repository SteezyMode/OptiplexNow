// Studio controls for the MIT-licensed UltraBox engine.
// The original piano roll and synthesizer remain the authoritative editor.
import { Config } from "../synth/SynthConfig";
import { Note, Pattern } from "../synth/synth";
import { SongDocument } from "./SongDocument";
import { SongEditor } from "./SongEditor";
import { ChangeGroup, ChangeSequence } from "./Change";
import { ChangeEnsurePatternExists, ChangeNoteAdded, ChangeEQFilterSimpleCut, ChangeEchoSustain } from "./changes";

type Project = { id: number; name: string; revision: number; song: string };
const SESSION_PROJECT = "studio.currentProject";
const TOKEN_KEY = "studio.apiToken";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, label?: string): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (label !== undefined) node.textContent = label;
    return node;
}

function token(): string {
    let value = sessionStorage.getItem(TOKEN_KEY) || "";
    if (value.length < 32) {
        value = window.prompt("Studio project-library token (from the server's .env file):") || "";
        if (value.length >= 32) sessionStorage.setItem(TOKEN_KEY, value);
    }
    if (value.length < 32) throw Error("A project-library token is required.");
    return value;
}
async function request(path: string, body?: unknown): Promise<any> {
    const response = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: {
            "Authorization": "Bearer " + token(),
            ...(body === undefined ? {} : { "Content-Type": "application/json" })
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store"
    });
    const data = await response.json();
    if (!response.ok) {
        if (response.status === 401) sessionStorage.removeItem(TOKEN_KEY);
        throw Error(data.error || ("HTTP " + response.status));
    }
    return data;
}

export function mountStudio(doc: SongDocument, editor: SongEditor): void {
    const container = document.getElementById("beepboxEditorContainer");
    if (!container) return;
    const outer = el("details", "studio-panel");
    outer.open = false;
    const heading = el("summary", "studio-heading", "EXPERIMENTAL / STEP GRID & XY PAD");
    const content = el("div", "studio-content");
    const intro = el("p", "studio-hint", "An additional instrument surface. The original UltraBox piano roll, sounds, and undo history still work.");
    const toolbar = el("div", "studio-toolbar");
    const length = el("select", "studio-select");
    length.title = "Number of visible sixteenth-note steps; additional steps use subsequent bars";
    [8,16,24,32].forEach(n => {
        const opt=el("option"); opt.value=String(n);opt.textContent=String(n)+" STEPS";
        length.appendChild(opt);
    });
    length.value="16";
    const basePitch = el("input", "studio-base");
    basePitch.type="number";basePitch.min="0";basePitch.max="70";basePitch.value="36";
    basePitch.title="First MIDI-style pitch index of the eight melodic rows";
    const bar = el("span","studio-subtitle","");
    const notice=el("span","studio-status","READY");
    toolbar.append(length,el("span","studio-subtitle","MELODY ROOT"),basePitch,bar);
    const steps=el("div","studio-steps");
    const perfTitle=el("h3","studio-section","PERFORMANCE");
    const perfRow=el("div","studio-performance");
    const pad=el("div","studio-xy");
    pad.tabIndex=0;
    pad.setAttribute("role","slider");
    pad.setAttribute("aria-label","Live filter cutoff and echo XY pad");
    pad.setAttribute("aria-valuemin","0");
    pad.setAttribute("aria-valuemax","100");
    pad.setAttribute("aria-valuenow","50");
    const cursor=el("div","studio-xy-dot");
    pad.appendChild(cursor);
    const padInfo=el("div","studio-pad-info");
    padInfo.append(el("span",undefined,"X: FILTER CUTOFF"),el("span",undefined,"Y: ECHO LEVEL"));
    const latchLabel=el("label","studio-latch");
    const latch=el("input"); latch.type="checkbox";
    latchLabel.append(latch,document.createTextNode(" Keep FX settings when released"));
    const hint=el("p","studio-hint","Enable Filter and Echo on the selected UltraBox instrument before using the pad. The pad is momentary unless Keep is checked.");
    perfRow.append(pad,padInfo,latchLabel);
    const library=el("div","studio-library");
    const save=el("button","studio-action","SAVE PROJECT");
    const saveAs=el("button","studio-action","SAVE AS");
    const load=el("button","studio-action","LOAD PROJECT");
    const clearToken=el("button","studio-action studio-quiet","CHANGE TOKEN");
    library.append(save,saveAs,load,clearToken);
    // Keep the actual UltraBox instrument first. Song-management remains visible
    // under the editor; experimental live controls are collapsed below it.
    const projectBar = el("div", "studio-projectbar");
    projectBar.append(el("span", "studio-projectbar-label", "STUDIO / SAVED PROJECTS"), library, notice);
    content.append(intro,toolbar,steps,perfTitle,perfRow,hint);
    outer.append(heading,content);
    container.append(projectBar,outer);

    let currentProject: Project | null=null;
    try {
        const raw=sessionStorage.getItem(SESSION_PROJECT);
        if(raw){
            const saved=JSON.parse(raw) as Project;
            if(saved.song===window.location.hash.replace(/^#/,"")) currentProject=saved;
        }
    }catch { /* browser storage can be unavailable */ }
    function status(message:string):void { notice.textContent=message; }
    function stepPosition(index:number):{bar:number;start:number;end:number}|null{
        const stepParts=Config.partsPerBeat/4;
        const absolute=index*stepParts;
        const barOffset=Math.floor(absolute/doc.song.partsPerPattern);
        const b=doc.bar+barOffset;
        if(b>=doc.song.barCount) return null;
        const start=absolute-barOffset*doc.song.partsPerPattern;
        return {bar:b,start,end:Math.min(doc.song.partsPerPattern,start+stepParts)};
    }
    function selectedPitch(row:number,isDrum:boolean):number{
        return isDrum?row:Math.max(0,Math.min(84,Number(basePitch.value)||36))+row;
    }
    function toggle(row:number,index:number):void{
        if(doc.song.getChannelIsMod(doc.channel)){status("SELECT A DRUM OR SYNTH CHANNEL");return;}
        const pos=stepPosition(index);
        if(!pos){status("EXTEND THE SONG IN ULTRABOX TO EDIT THESE STEPS");return;}
        const isDrum=doc.song.getChannelIsNoise(doc.channel);
        const pitch=selectedPitch(row,isDrum);
        const changes=new ChangeSequence();
        let pattern:Pattern|null=doc.song.getPattern(doc.channel,pos.bar);
        if(!pattern){
            changes.append(new ChangeEnsurePatternExists(doc,doc.channel,pos.bar));
            pattern=doc.song.getPattern(doc.channel,pos.bar);
        }
        if(!pattern){status("COULD NOT CREATE PATTERN");return;}
        const note=pattern.notes.find(n=>n.start===pos.start && n.end===pos.end);
        if(note){
            const indexInPattern=pattern.notes.indexOf(note);
            const next=note.clone();
            const n=next.pitches.indexOf(pitch);
            if(n>=0)next.pitches.splice(n,1);else next.pitches.push(pitch);
            changes.append(new ChangeNoteAdded(doc,pattern,note,indexInPattern,true));
            if(next.pitches.length)changes.append(new ChangeNoteAdded(doc,pattern,next,indexInPattern,false));
        }else{
            // UltraBox's native editor generally does not overlap distinct note
            // objects on one channel. Preserve complex or tied notes unchanged.
            if(pattern.notes.some(n=>n.start<pos.end&&n.end>pos.start)){
                status("LONG NOTE HERE — EDIT IT IN PIANO ROLL");
                return;
            }
            const fresh=new Note(pitch,pos.start,pos.end,Config.noteSizeMax,false);
            let idx=pattern.notes.findIndex(n=>n.start>pos.start);
            if(idx<0)idx=pattern.notes.length;
            changes.append(new ChangeNoteAdded(doc,pattern,fresh,idx,false));
        }
        doc.record(changes);
        render();
    }
    function render():void{
        steps.replaceChildren();
        const isDrum=doc.song.getChannelIsNoise(doc.channel);
        const isMod=doc.song.getChannelIsMod(doc.channel);
        const count=Number(length.value);
        bar.textContent="BAR "+String(doc.bar+1)+" · "+(isMod?"MODULATION":isDrum?"DRUMS":"SYNTH");
        const rows=isDrum?12:8;
        const grid=el("div","studio-grid");
        grid.style.setProperty("--studio-cols",String(count));
        const corner=el("span","studio-corner","");
        grid.appendChild(corner);
        for(let i=0;i<count;i++){
            const pos=stepPosition(i);
            const col=el("span","studio-step-number",pos?String(i+1):"—");
            if(i%4===0)col.classList.add("studio-beat");
            grid.appendChild(col);
        }
        for(let row=rows-1;row>=0;row--){
            const pitch=selectedPitch(row,isDrum);
            grid.appendChild(el("span","studio-row-label",isDrum?"D"+String(pitch+1):"N"+String(pitch)));
            for(let i=0;i<count;i++){
                const pos=stepPosition(i);
                const pattern=pos?doc.song.getPattern(doc.channel,pos.bar):null;
                const exact=pattern?.notes.find(n=>n.start===pos?.start&&n.end===pos?.end&&n.pitches.includes(pitch));
                const btn=el("button","studio-step","");
                btn.type="button";
                btn.disabled=(!pos||isMod);
                btn.classList.toggle("active",!!exact);
                if(i%4===0)btn.classList.add("studio-beat");
                btn.setAttribute("aria-label",(isDrum?"Drum ":"Note ")+pitch+", step "+(i+1)+(exact?", active":""));
                btn.setAttribute("aria-pressed",exact?"true":"false");
                btn.addEventListener("click",()=>toggle(row,i));
                grid.appendChild(btn);
            }
        }
        steps.appendChild(grid);
    }
    doc.notifier.watch(render);
    length.addEventListener("change",render);
    basePitch.addEventListener("change",render);
    render();

    let dragging=false;
    let original:{cut:number;echo:number;channel:number;instrument:number}|null=null;
    function locate(event:PointerEvent):void {
        if(!dragging||!original)return;
        const rect=pad.getBoundingClientRect();
        const x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
        const y=1-Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
        cursor.style.left=(x*100)+"%";
        cursor.style.top=((1-y)*100)+"%";
        pad.setAttribute("aria-valuenow",String(Math.round(x*100)));
        const inst=doc.song.channels[original.channel].instruments[original.instrument];
        if(!inst)return;
        inst.eqFilterSimpleCut=Math.round(x*(Config.filterSimpleCutRange-1));
        inst.echoSustain=Math.round(y*(Config.echoSustainRange-1));
        doc.notifier.changed();
    }
    pad.addEventListener("pointerdown",event=>{
        if(doc.song.getChannelIsMod(doc.channel)){status("SELECT A SYNTH OR DRUM CHANNEL");return;}
        const inst=doc.song.channels[doc.channel].instruments[doc.getCurrentInstrument()];
        if(!inst)return;
        original={cut:inst.eqFilterSimpleCut,echo:inst.echoSustain,channel:doc.channel,instrument:doc.getCurrentInstrument()};
        dragging=true;pad.setPointerCapture(event.pointerId);locate(event);
    });
    pad.addEventListener("pointermove",locate);
    function finish():void{
        if(!dragging||!original)return;
        dragging=false;
        const inst=doc.song.channels[original.channel].instruments[original.instrument];
        if(inst){
            if(!latch.checked){
                inst.eqFilterSimpleCut=original.cut;
                inst.echoSustain=original.echo;
            }else{
                // Commit one browser-history entry for the complete XY gesture.
                // UltraBox's native changes update its instrument, notifier and URL.
                if(doc.channel===original.channel && doc.getCurrentInstrument()===original.instrument){
                    const both=new ChangeGroup();
                    both.append(new ChangeEQFilterSimpleCut(doc,original.cut,inst.eqFilterSimpleCut));
                    both.append(new ChangeEchoSustain(doc,original.echo,inst.echoSustain));
                    doc.record(both);
                }
            }
            doc.notifier.changed();
        }
        if(latch.checked)status("FX LATCHED — SAVE PROJECT TO KEEP THEM");
        original=null;
    }
    pad.addEventListener("pointerup",finish);
    pad.addEventListener("pointercancel",finish);
    clearToken.addEventListener("click",()=>{sessionStorage.removeItem(TOKEN_KEY);status("TOKEN CLEARED");});

    function remember(p:Project):void{
        currentProject=p;
        sessionStorage.setItem(SESSION_PROJECT,JSON.stringify(p));
    }
    async function saveProject(asNew:boolean):Promise<void>{
        try{
            const previous=(!asNew?currentProject:null);
            const name=window.prompt("Project name:",previous?.name || doc.song.title || "Untitled");
            if(!name)return;
            const result=await request("/api/projects",{
                id:previous?.id, revision:previous?.revision || 0,
                name:name.trim(),song:doc.song.toBase64String()
            }) as Project;
            remember({...result,song:doc.song.toBase64String()});
            status("SAVED: "+result.name+" · REVISION "+result.revision);
        }catch(e){status("SAVE FAILED: "+String(e));}
    }
    save.addEventListener("click",()=>{void saveProject(false);});
    saveAs.addEventListener("click",()=>{void saveProject(true);});
    load.addEventListener("click",async()=>{
        try{
            const found=await request("/api/projects") as {projects:Project[]};
            if(!found.projects.length){status("NO SAVED PROJECTS");return;}
            const message=found.projects.map((p,i)=>String(i+1)+". "+p.name+" (r"+p.revision+")").join("\n");
            const choice=window.prompt("Load project number:\n"+message);
            if(!choice)return;
            const idx=Number(choice)-1;
            if(!Number.isInteger(idx)||idx<0||idx>=found.projects.length){status("INVALID SELECTION");return;}
            const song=await request("/api/projects/"+found.projects[idx].id) as Project;
            remember(song);
            window.location.assign(window.location.pathname+"#"+song.song);
        }catch(e){status("LOAD FAILED: "+String(e));}
    });
}
