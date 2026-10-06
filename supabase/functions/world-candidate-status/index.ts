import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

// Public read-only moderation STATUS (not reviewer details, admin notes, or credentials).
// GitHub Actions must fail closed if this check is unavailable or truncated.
const CORS = {
  "Access-Control-Allow-Origin": "https://vrc-club-charts.vercel.app",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Cache-Control": "no-store",
  "Vary": "Origin",
};
const ALLOWED = new Set(["https://vrc-club-charts.vercel.app", "https://showchoo.github.io"]);
const respond=(value:unknown,status=200)=>new Response(JSON.stringify(value),{
  status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"},
});

Deno.serve(async(req:Request)=>{
  const origin=req.headers.get("Origin") || "";
  if(origin && !ALLOWED.has(origin)) return respond({error:"Origin not allowed"},403);
  if(req.method==="OPTIONS"){
    const response=new Response(null,{status:204,headers:CORS});
    if(origin) response.headers.set("Access-Control-Allow-Origin",origin);
    return response;
  }
  if(req.method!=="GET") return respond({error:"Method not allowed"},405);
  const url=Deno.env.get("SUPABASE_URL");
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!url || !serviceKey) return respond({error:"Server not configured"},503);
  try {
    const db=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
    const rows:{world_id:string,status:string}[]=[];
    for(let offset=0;offset<5000;offset+=500){
      const {data,error}=await db.from("world_candidate_decisions")
        .select("world_id,status")
        .in("status",["approved","rejected"])
        .order("world_id",{ascending:true})
        .range(offset,offset+499);
      if(error) throw error;
      for(const entry of data||[]){
        if(typeof entry.world_id==="string" && ["approved","rejected"].includes(entry.status))
          rows.push({world_id:entry.world_id,status:entry.status});
      }
      if((data||[]).length<500) break;
      if(offset===4500) return respond({error:"Moderation statuses exceed safe limit"},503);
    }
    const result=respond({decisions:rows,complete:true});
    if(origin) result.headers.set("Access-Control-Allow-Origin",origin);
    return result;
  }catch(error){
    console.error("Moderation status fetch failure",error instanceof Error?error.name:"unknown");
    return respond({error:"Unable to verify moderation decisions"},503);
  }
});
