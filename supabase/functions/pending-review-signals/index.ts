import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

// Public-safe notification signals only. NEVER return review content, authors,
// World IDs, database UUIDs, IP hashes or pending moderation notes.
// GET returns an HMAC pseudonym of each pending review so GitHub can notify
// exactly once without requiring the site owner's private admin key.
// No CORS allowed; anonymous access reveals only count/opaque tokens.
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,headers:{"content-type":"application/json; charset=utf-8",
                  "cache-control":"no-store","x-content-type-options":"nosniff"},
});
const encoder=new TextEncoder();

Deno.serve(async(req:Request)=>{
  if(req.method!=="GET") return json({error:"Method not allowed"},405);
  if(req.headers.has("origin")) return json({error:"Browser requests not supported"},403);
  const url=Deno.env.get("SUPABASE_URL")||"";
  const service=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
  if(!url || !service) return json({error:"Not configured"},503);
  try {
    const db=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
    const key=await crypto.subtle.importKey("raw",encoder.encode(service),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
    const pending:string[]=[];
    const pageSize=300;
    for(let offset=0;offset<3000;offset+=pageSize){
      const {data,error}=await db.from("community_reviews").select("id")
        .eq("status","pending").order("id",{ascending:true})
        .range(offset,offset+pageSize-1);
      if(error) throw error;
      if(!Array.isArray(data)) throw new Error("Missing community review status");
      for(const row of data){
        if(typeof row.id!=="string") throw new Error("Unexpected review ID");
        const mac=await crypto.subtle.sign("HMAC",key,encoder.encode("vcc-pending-review:"+row.id));
        pending.push(Array.from(new Uint8Array(mac)).slice(0,20)
          .map(b=>b.toString(16).padStart(2,"0")).join(""));
      }
      if(data.length<pageSize) return json({complete:true,pending:pending});
    }
    return json({error:"Too many pending reviews; refuse incomplete scan"},503);
  }catch(err){
    console.error("Unable to inspect pending-review notification status",
                  err instanceof Error ? err.name : "error");
    return json({error:"Review status temporarily unavailable"},503);
  }
});
