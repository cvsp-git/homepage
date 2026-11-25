const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const [src,dst]=process.argv.slice(2);const t=fs.readFileSync(src,'utf8');
const m=t.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);let W=+m[1],H=+m[2];const k=Math.min(1,1600/Math.max(W,H));const w=Math.round(W*k),h=Math.round(H*k);
const b=await chromium.launch();const p=await b.newPage({viewport:{width:w,height:h}});
await p.setContent(`<html><body style="margin:0;background:#fff"><img src="data:image/svg+xml;base64,${Buffer.from(t).toString('base64')}" style="width:${w}px;height:${h}px;display:block"></body></html>`);
await p.waitForTimeout(300);await p.screenshot({path:dst});await b.close();})();
