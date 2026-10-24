export async function api(path:string, body?:unknown):Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(()=>controller.abort(),path==='recognize'?240000:180000);
  try {
    const res = await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    const data = await res.json();
    if(!res.ok) throw new Error(data.error||'请求失败');
    return data;
  } catch(e) {
    if(e instanceof DOMException && e.name==='AbortError') throw new Error('请求超时，可以继续手动选餐或稍后重试');
    if(e instanceof TypeError)throw new Error('连接后端失败，请确认本地服务正在运行');
    throw e;
  } finally { clearTimeout(timer); }
}
