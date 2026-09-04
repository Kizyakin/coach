const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export async function api<T>(path:string, options?:RequestInit):Promise<T>{
  const r=await fetch(`${API}${path}`,{headers:{'Content-Type':'application/json',...(options?.headers||{})},...options});
  if(!r.ok) throw new Error((await r.text())||`HTTP ${r.status}`); return r.json();
}
export {API};
