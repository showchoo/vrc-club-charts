
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

const ORIGINS = new Set(["https://vrc-club-charts.vercel.app", "https://showchoo.github.io"]);
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const WORLD_CATALOG_URL = "https://raw.githubusercontent.com/showchoo/vrc-club-charts/main/data/worlds.json";
const WORLD_ID = /^wrld_[0-9a-fA-F-]{36}$/;
const MAX: Record<string,number> = {
  visual:20, lighting:20, sound:15, spatial:15,
  interaction:10, originality:10, optimization:10,
};
const headers = {
  "Access-Control-Allow-Origin": "https://vrc-club-charts.vercel.app",
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Vary": "Origin",
  "Cache-Control": "no-store",
};

const json = (body: unknown, status=200) =>
  new Response(JSON.stringify(body), {status, headers: {...headers,
    "Content-Type": "application/json; charset=utf-8"}});

async function sha256(value:string):Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,"0")).join("");
}

function todayJst():string {
  const parts = new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
  const fields = Object.fromEntries(parts.filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));
  return fields.year + "-" + fields.month + "-" + fields.day;
}

async function isApprovedWorld(worldId:string, supabase:any):Promise<boolean> {
  const {data} = await supabase.from("worlds_public").select("id")
    .eq("id",worldId).eq("chart_eligible",true).maybeSingle();
  if(data) return true;
  try {
    const response=await fetch(WORLD_CATALOG_URL, {headers:{"Accept":"application/json"},signal:AbortSignal.timeout(9000)});
    if(!response.ok) return false;
    const items=await response.json();
    return Array.isArray(items) && items.some(item=>item?.id===worldId && item?.chartEligible===true);
  } catch(_) {return false;}
}

async function handle(req:Request):Promise<Response> {
  if(req.method==="OPTIONS") return new Response("ok", {headers});
  if(req.method!=="GET" && req.method!=="POST") return json({error:"Method not allowed"},405);
  const origin=req.headers.get("origin")||"";
  if(origin && !ORIGINS.has(origin)) return json({error:"Origin not allowed"},403);
  if(req.method==="POST" && !ORIGINS.has(origin)) return json({error:"Browser origin required"},403);
  if(!SUPABASE_URL || !SERVICE_KEY) return json({error:"Server is not configured"},503);
  const db=createClient(SUPABASE_URL,SERVICE_KEY,{auth:{persistSession:false,autoRefreshToken:false}});

  if(req.method==="GET"){
    const url=new URL(req.url);
    const worldId=(url.searchParams.get("worldId")||"").trim();
    if(worldId && !WORLD_ID.test(worldId)) return json({error:"Invalid World ID"},400);
    const limit=Math.min(12, Math.max(1, Number.parseInt(url.searchParams.get("limit")||"6",10)||6));
    let query=db.from("community_reviews")
      .select("id,world_id,display_name,reviewed_at,visual,lighting,sound,spatial,interaction,originality,optimization,comment,conflict,published_at")
      .eq("status","published").order("published_at",{ascending:false}).limit(limit);
    if(worldId) query=query.eq("world_id",worldId);
    const {data,error}=await query;
    if(error) return json({error:"Reviews temporarily unavailable"},503);
    return json({reviews:data||[]});
  }

  const len=Number(req.headers.get("content-length")||0);
  if(len>8192) return json({error:"Request too large"},413);
  let body:any;
  try{
    const raw=await req.text();
    if(raw.length>8192) return json({error:"Request too large"},413);
    body=JSON.parse(raw);
  }catch(_){return json({error:"Invalid JSON"},400);}
  if(body?.website) return json({ok:true,status:"pending"},202);
  const worldId=String(body?.worldId||"").trim();
  const displayName=String(body?.displayName||"").trim();
  const comment=String(body?.comment||"").trim();
  const visitorToken=String(body?.visitorToken||"").trim();
  const reviewedAt=String(body?.reviewedAt||"").trim();
  const conflict=body?.conflict===true;
  const scores=body?.scores||{};
  if(!WORLD_ID.test(worldId)) return json({error:"World IDが正しくありません。"},400);
  if(displayName.length<2 || displayName.length>60) return json({error:"表示名は2〜60文字で入力してください。"},400);
  if(comment.length<30 || comment.length>1800) return json({error:"コメントは30〜1800文字で入力してください。"},400);
  if(!/^[0-9a-f-]{36}$/i.test(visitorToken)) return json({error:"ブラウザ情報が正しくありません。再読み込みしてください。"},400);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(reviewedAt)) return json({error:"訪問日を入力してください。"},400);
  const date = new Date(reviewedAt+"T00:00:00Z");
  if(!Number.isFinite(date.getTime()) || date.toISOString().slice(0,10)!==reviewedAt ||
     reviewedAt>todayJst() || Date.now()-date.getTime()>370*86400000) {
    return json({error:"過去1年以内の訪問日を入力してください。"},400);
  }
  for(const [name,max] of Object.entries(MAX)){
    if(!Number.isInteger(scores[name]) || scores[name]<0 || scores[name]>max){
      return json({error:"評価点に不正な値があります。"},400);
    }
  }
  if(!await isApprovedWorld(worldId,db)) return json({error:"掲載対象のWorldを選択してください。"},400);

  const ip = (req.headers.get("cf-connecting-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0] || "").trim().slice(0,90);
  const day=todayJst();
  // The salted hashes are not public; daily IP-derived hashes limit bulk spam.
  const ipDayHash=await sha256("ip:"+day+":"+(ip||visitorToken)+":"+SERVICE_KEY);
  const visitorHash=await sha256("visitor:"+visitorToken+":"+SERVICE_KEY);
  const [dayCount,existing]=await Promise.all([
    db.from("community_reviews").select("id",{count:"exact",head:true}).eq("ip_day_hash",ipDayHash),
    db.from("community_reviews").select("id",{count:"exact",head:true})
      .eq("visitor_hash",visitorHash).eq("world_id",worldId)
      .gte("created_at",new Date(Date.now()-30*86400000).toISOString())
  ]);
  if(dayCount.error || existing.error) return json({error:"現在投稿を受け付けられません。"},503);
  if(Number(dayCount.count||0)>=3) return json({error:"本日の投稿上限です。翌日お試しください。"},429);
  if(Number(existing.count||0)>0) return json({error:"このWorldには最近投稿済みです。30日後に再投稿できます。"},409);

  const row:any={
    world_id:worldId,display_name:displayName,comment,reviewed_at:reviewedAt,
    visitor_hash:visitorHash,ip_day_hash:ipDayHash,conflict,status:"pending",
  };
  for(const name of Object.keys(MAX)) row[name]=scores[name];
  const {data,error}=await db.from("community_reviews").insert(row).select("id").single();
  if(error) return json({error:"投稿を保存できませんでした。"},503);
  return json({ok:true,status:"pending",submissionId:data.id},201);
}

Deno.serve(async(req:Request)=>{
  try{
    const response=await handle(req);
    const origin=req.headers.get("origin")||"";
    if(ORIGINS.has(origin)) response.headers.set("Access-Control-Allow-Origin",origin);
    return response;
  }catch(_){
    const response=json({error:"現在投稿を受け付けられません。"},503);
    const origin=req.headers.get("origin")||"";
    if(ORIGINS.has(origin)) response.headers.set("Access-Control-Allow-Origin",origin);
    return response;
  }
});
