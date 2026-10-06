
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

const ALLOWED_ORIGIN = "https://showchoo.github.io";
const VERCEL_ORIGIN = "https://vrc-club-charts.vercel.app";
const ALLOWED_ORIGINS = new Set([ALLOWED_ORIGIN, VERCEL_ORIGIN]);

const corsHeaders = {
  "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
};

function json(body: unknown, status=200){
  return new Response(JSON.stringify(body),{
    status,
    headers:{...corsHeaders,"Content-Type":"application/json; charset=utf-8"}
  });
}

function clean(value: unknown, max: number){
  const s=String(value ?? "").trim().slice(0,max);
  return s || null;
}

function cleanPath(value: unknown){
  let s=String(value ?? "").trim();
  if(!s.startsWith("/")) s="/";
  s=s.split("?")[0].split("#")[0].slice(0,300);
  return s || "/";
}

function cleanHost(value: unknown){
  const s=clean(value,255);
  if(!s) return null;
  if(!/^[a-z0-9.-]+(?::\d+)?$/i.test(s)) return null;
  if(s==="showchoo.github.io") return null;
  return s.toLowerCase();
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DAY_MS=24*60*60*1000;

async function visitorHash(value:string, serverKey:string):Promise<string>{
  const digest=await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode("VCC:ANALYTICS:UNIQUE:v1:"+serverKey+":"+value));
  return Array.from(new Uint8Array(digest))
    .map(x=>x.toString(16).padStart(2,"0")).join("");
}

function jstDay(now:Date):string{
  const p=new Intl.DateTimeFormat("en-CA",{
    timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"
  }).formatToParts(now);
  const parts=Object.fromEntries(p.filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
  return parts.year+"-"+parts.month+"-"+parts.day;
}

async function handleVccRequest(req: Request) {
  if(req.method==="OPTIONS") return new Response("ok",{headers:corsHeaders});
  if(req.method!=="POST") return json({error:"Method not allowed"},405);

  const origin=req.headers.get("origin")||"";
  if(!ALLOWED_ORIGINS.has(origin)) return json({error:"Origin not allowed"},403);

  let body:any;
  try{body=await req.json()}catch(_){return json({error:"Invalid JSON"},400)}

  const url=Deno.env.get("SUPABASE_URL")||"";
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
  if(!url||!serviceKey) return json({error:"Server configuration error"},500);

  const supabase=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
  const row={
    path:cleanPath(body?.path),
    referrer_host:cleanHost(body?.referrerHost),
    utm_source:clean(body?.utmSource,120),
    utm_medium:clean(body?.utmMedium,120),
    utm_campaign:clean(body?.utmCampaign,180),
  };

  const {error}=await supabase.from("site_analytics_events").insert(row);
  if(error) return json({error:"Could not record page view"},500);

  // A random ID remains only in the browser. The server stores a salted hash,
  // no IP, User-Agent, raw ID or verified identity.
  const visitorId=typeof body?.visitorId==="string" ? body.visitorId : "";
  if(UUID.test(visitorId)){
    const visitor_hash=await visitorHash(visitorId,serviceKey);
    const {error:uniqueError}=await supabase.from("site_analytics_unique_visits")
      .upsert({
        visitor_hash, visit_day:jstDay(new Date()),
        last_seen_at:new Date().toISOString()
      },{onConflict:"visitor_hash,visit_day"});
    if(uniqueError) console.error("Unique browser aggregate unavailable",uniqueError.code);
  }

  // No indefinite identifier retention. Old daily hashes are purged on
  // every recorded pageview, even when the visitor has disabled local storage.
  const cutoff=new Date(Date.now()-40*DAY_MS).toISOString().slice(0,10);
  const {error:cleanupError}=await supabase.from("site_analytics_unique_visits")
    .delete().lt("visit_day",cutoff);
  if(cleanupError) console.error("Unique browser cleanup unavailable",cleanupError.code);

  return json({ok:true},202);
}

Deno.serve(async (req: Request) => {
  const response = await handleVccRequest(req);
  const origin = req.headers.get("origin") || "";
  if (ALLOWED_ORIGINS.has(origin)) {
    response.headers.set("Access-Control-Allow-Origin", origin);
  }
  return response;
});
