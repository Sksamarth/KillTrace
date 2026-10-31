export function scanMetrics(bytes:number,size:number,records:number,seconds:number,status:string) {
  const percent=Number.isFinite(bytes)&&Number.isFinite(size)&&size>0
    ?Math.max(0,Math.min(100,100*bytes/size))
    :status==='completed'&&size===0?100:0;
  const rate=Number.isFinite(seconds)&&seconds>0&&Number.isFinite(records)&&records>=0?records/seconds:null;
  return {percent,rate,blocks:Math.floor(percent/5)};
}
