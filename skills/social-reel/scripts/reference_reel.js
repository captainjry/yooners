// Snippets for javascript_tool on a reel page (probe, sheet, cuts) and its audio page (hits).
// Paste ONE block per call; each returns a value. Nothing is written to disk.

// ---------- probe: canvas + duration (reel page) ----------
const v=document.querySelector('video'); v.pause();
({dur:v.duration, w:v.videoWidth, h:v.videoHeight, t:v.currentTime});

// ---------- sheet: 19-frame contact sheet replacing the page body (reel page) ----------
// After it returns, take a screenshot; zoom on tiles to read type.
(async()=>{
const v=document.querySelector('video'); v.muted=true; v.pause();
const d=v.duration, N=19, times=[...Array(N)].map((_,i)=>+(0.2+i*(d-0.6)/(N-1)).toFixed(2));
const port=v.videoHeight>v.videoWidth, cw=port?216:384, ch=port?384:216, cols=5, rows=Math.ceil(N/cols);
const c=document.createElement('canvas'); c.width=cw*cols; c.height=ch*rows; const g=c.getContext('2d');
const seek=t=>new Promise(r=>{v.onseeked=()=>r(); v.currentTime=t;});
for(let i=0;i<N;i++){ await seek(times[i]); await new Promise(r=>setTimeout(r,150));
  g.drawImage(v,(i%cols)*cw,Math.floor(i/cols)*ch,cw,ch);
  g.fillStyle='yellow'; g.font='16px sans-serif'; g.fillText(times[i]+'s',(i%cols)*cw+4,Math.floor(i/cols)*ch+18); }
document.body.innerHTML='<img style="position:fixed;top:0;left:0;height:100vh;z-index:99999;background:#000" src="'+c.toDataURL('image/jpeg',0.8)+'">';
return 'sheet '+c.width+'x'+c.height+' times '+times.join(',');
})();

// ---------- cuts: picture cut points by frame differencing during one playback (reel page) ----------
// Takes duration seconds of wall time. Returns cut times (+/-0.1 s).
(async()=>{
const v=document.querySelector('video'); v.pause(); v.muted=true;
const c=document.createElement('canvas'); c.width=48; c.height=86; const cx=c.getContext('2d',{willReadFrequently:true});
let prev=null; const diffs=[];
v.currentTime=0; await new Promise(r=>{v.onseeked=r;}); await v.play(); const t0=performance.now();
await new Promise(res=>{const iv=setInterval(()=>{const t=v.currentTime;
  if(t>=v.duration-0.4||v.ended||performance.now()-t0>(v.duration+5)*1000){clearInterval(iv);res();return;}
  cx.drawImage(v,0,0,48,86); const d=cx.getImageData(0,0,48,86).data;
  if(prev){let s=0;for(let i=0;i<d.length;i+=4){s+=Math.abs(d[i]-prev[i])+Math.abs(d[i+1]-prev[i+1])+Math.abs(d[i+2]-prev[i+2]);}diffs.push([+t.toFixed(2),Math.round(s/(d.length/4))]);}
  prev=new Uint8ClampedArray(d);},40);});
v.pause();
const vals=diffs.map(x=>x[1]).sort((a,b)=>a-b), med=vals[Math.floor(vals.length/2)];
const cuts=[]; for(let i=1;i<diffs.length-1;i++){ if(diffs[i][1]>Math.max(40,med*4)&&diffs[i][1]>=diffs[i-1][1]&&diffs[i][1]>=diffs[i+1][1]&&(cuts.length==0||diffs[i][0]-cuts[cuts.length-1][0]>0.5)) cuts.push(diffs[i][0]); }
return {med, ncuts:cuts.length, cuts, samples:diffs.length};
})();

// ---------- hits: onset hit map + tempo verdict (AUDIO page /reels/audio/<id>/) ----------
(async()=>{
const a=document.querySelector('audio'); const buf=await fetch(a.currentSrc).then(r=>r.arrayBuffer());
const ac=new (window.AudioContext||window.webkitAudioContext)(); const ab=await ac.decodeAudioData(buf);
const sr=ab.sampleRate, ch=ab.getChannelData(0), hop=Math.round(sr*0.01), n=Math.floor(ch.length/hop);
const env=new Float32Array(n); for(let i=0;i<n;i++){let s=0;for(let j=i*hop;j<(i+1)*hop;j++)s+=ch[j]*ch[j];env[i]=Math.sqrt(s/hop);}
const on=new Float32Array(n); for(let i=1;i<n;i++){const d=Math.log(env[i]+1e-4)-Math.log(env[i-1]+1e-4);on[i]=d>0?d:0;}
const scores=[]; let best={bpm:0,score:-1};
for(let lag=40;lag<=200;lag++){let s=0;for(let i=lag;i<n;i++)s+=on[i]*on[i-lag];s/=(n-lag);scores.push([+(6000/lag).toFixed(1),+s.toFixed(5)]);if(s>best.score)best={bpm:+(6000/lag).toFixed(2),score:+s.toFixed(5)};}
scores.sort((x,y)=>y[1]-x[1]);
const sm=new Float32Array(n); for(let i=1;i<n-1;i++)sm[i]=on[i-1]+on[i]+on[i+1];
const hits=[]; let last=-100; for(let i=1;i<n-1;i++){if(sm[i]>sm[i-1]&&sm[i]>=sm[i+1]&&sm[i]>0.6&&i-last>=20){hits.push([+(i/100).toFixed(2),+sm[i].toFixed(2)]);last=i;}}
const sec=[]; for(let s=0;s<Math.ceil(n/100);s++){let m=0;for(let i=s*100;i<Math.min(n,(s+1)*100);i++)m+=env[i];sec.push(+(m/100).toFixed(3));}
return {dur:+ab.duration.toFixed(2), best, top8:scores.slice(0,8), hits, sec};
})();
