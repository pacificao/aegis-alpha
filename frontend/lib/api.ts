export type Status = "NOT_STARTED"|"IN_PROGRESS"|"COMPLETE"|"BLOCKED"|"WAITING_FOR_CREDENTIALS";
export type Task = {id:number;ordinal:number;title:string;status:Status;notes:string;updated_at:string};
export type Phase = {id:number;number:number;name:string;description:string;status:Status;completion_percentage:number;tasks:Task[]};

export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const response=await fetch(path,{...options,credentials:"include",headers:{"Content-Type":"application/json",...(options.headers||{})}});
  if(response.status===401&&typeof window!=="undefined"&&!location.pathname.startsWith("/login")){location.href="/login";throw new Error("Authentication required")}
  if(!response.ok){const body=await response.json().catch(()=>({detail:"Request failed"}));throw new Error(body.detail||"Request failed")}
  return response.json();
}

