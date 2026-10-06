import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

const ALLOWED = new Set(["https://vrc-club-charts.vercel.app", "https://showchoo.github.io"]);
const CATALOG = "https://raw.githubusercontent.com/showchoo/vrc-club-charts/main/data/worlds.json";
const ID = /^wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_BODY = 1024;
const MAX_DAY = 3;
const headers = {
  "Access-Control-Allow-Origin": "https://vrc-club-charts.vercel.app",
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Vary": "Origin", "Cache-Control": "no-store",
};
const respond = (value: unknown, code=200) =>
  new Response(JSON.stringify(value), {status: code,
    headers: {...headers, "Content-Type": "application/json; charset=utf-8"}});

function parseWorldLink(raw: unknown): string | null {
  if (typeof raw !== "string" || raw.length > 350) return null;
  try {
    const u = new URL(raw.trim());
    if (u.protocol !== "https:" || u.hostname !== "vrchat.com"
      || u.port || u.username || u.password) return null;
    const m = /^\/home\/world\/(wrld_[0-9a-f-]{36})(?:\/info)?\/?$/i.exec(u.pathname);
    if (!m || !ID.test(m[1])) return null;
    if (u.search || u.hash) return null;
    return m[1].toLowerCase();
  } catch (_) { return null; }
}
const str = (value: unknown, cap: number) =>
  typeof value === "string" ? value.trim().slice(0, cap) : "";
async function hash(input: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, "0")).join("");
}

async function isPublished(id: string, db: any): Promise<boolean> {
  const {data} = await db.from("worlds_public").select("id")
    .eq("id",id).eq("chart_eligible",true).maybeSingle();
  if (data) return true;
  try {
    const res = await fetch(CATALOG, {headers: {"Accept":"application/json"},
      signal: AbortSignal.timeout(8000)});
    if (!res.ok) return false;
    const list = await res.json();
    return Array.isArray(list) && list.some((v:any) => v?.id===id && v.chartEligible===true);
  } catch (_) { return false; }
}

async function handle(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") return new Response("ok", {headers});
  if (req.method !== "GET" && req.method !== "POST") return respond({error:"Method not allowed"},405);
  const origin = req.headers.get("origin") || "";
  if (origin && !ALLOWED.has(origin)) return respond({error:"Origin not allowed"},403);
  if (req.method === "POST" && !ALLOWED.has(origin))
    return respond({error:"Browser origin required"},403);
  const url = Deno.env.get("SUPABASE_URL") || "";
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!url || !key) return respond({error:"Server not configured"},503);
  const db = createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});

  if (req.method === "GET") {
    // Public World metadata only: NEVER return IP hashes, reporter details,
    // private decisions or moderator notes. Used by the scheduled AI worker.
    const parsed = new URL(req.url);
    if (parsed.searchParams.get("queue") !== "1") return respond({error:"Not found"},404);
    const limit = Math.min(75,Math.max(1,Number(parsed.searchParams.get("limit") || 50)||50));
    const offset = Math.min(5000,Math.max(0,Number(parsed.searchParams.get("offset") || 0)||0));
    const {data,error} = await db.from("world_submissions")
      .select("world_id,world_name,world_author,world_description,world_tags,world_thumbnail,first_submitted_at")
      .eq("status","queued").order("first_submitted_at",{ascending:true})
      .range(offset,offset + limit - 1);
    if (error) return respond({error:"Queue temporarily unavailable"},503);
    return respond({worlds:data || []});
  }

  if (Number(req.headers.get("content-length") || 0) > MAX_BODY)
    return respond({error:"Request too large"},413);
  let body: any;
  try {
    const raw = await req.text();
    if (raw.length > MAX_BODY) return respond({error:"Request too large"},413);
    body = JSON.parse(raw);
  } catch (_) { return respond({error:"Invalid JSON"},400); }
  if (body?.website) return respond({ok:true,status:"queued"},202);
  const id = parseWorldLink(body?.url);
  if (!id) return respond({error:"VRChatのWorld URLを正しく入力してください。"},400);

  const {data: existing,error:existingError} = await db.from("world_submissions")
    .select("status").eq("world_id",id).maybeSingle();
  if (existingError) return respond({error:"投稿状態を確認できません。"},503);
  if (existing) return respond({ok:true,status:existing.status,worldId:id,alreadySubmitted:true},200);
  if (await isPublished(id,db))
    return respond({ok:true,status:"already_listed",worldId:id},200);

  const ip = (req.headers.get("cf-connecting-ip") ||
    req.headers.get("x-real-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0] || "").trim().slice(0,90);
  const token = str(body?.visitorToken,80);
  if (!ip && !/^[0-9a-f-]{36}$/i.test(token))
    return respond({error:"ブラウザを更新してから投稿してください。"},400);
  const day = new Date().toISOString().slice(0,10);
  const dayHash = await hash("world-submission:" + day + ":" + (ip || token) + ":" + key);
  const {count,error:countError} = await db.from("world_submission_attempts")
    .select("id",{count:"exact",head:true}).eq("ip_day_hash",dayHash)
    .gte("created_at",day+"T00:00:00Z");
  if (countError) return respond({error:"現在投稿を受け付けられません。"},503);
  if ((count || 0) >= MAX_DAY)
    return respond({error:"本日の投稿上限は3件です。"},429);

  let meta: any;
  try {
    const result = await fetch("https://api.vrchat.cloud/api/1/worlds/"+id,{
      headers: {"Accept":"application/json",
        "User-Agent":"VRCClubCharts-WorldSubmission/1.0 (+https://vrc-club-charts.vercel.app/)"},
      signal:AbortSignal.timeout(14000),
    });
    if (!result.ok) {
      if (result.status===404 || result.status===403)
        return respond({error:"公開されているWorldを確認できませんでした。"},422);
      return respond({error:"VRChatの照合に失敗しました。後ほどお試しください。"},503);
    }
    meta = await result.json();
  } catch (_) {return respond({error:"VRChatに接続できませんでした。"},503);}
  if (meta?.id!==id || String(meta?.releaseStatus||"").toLowerCase()!=="public")
    return respond({error:"公開Worldのみ投稿できます。"},422);
  const name = str(meta?.name,120),author=str(meta?.authorName,120);
  if (!name || !author) return respond({error:"Worldの名前または制作者を確認できません。"},422);
  const tagList=Array.isArray(meta?.tags)?meta.tags.filter((x:unknown)=>typeof x==="string")
    .map((x:string)=>x.slice(0,80)).slice(0,25):[];
  const thumb = str(meta?.thumbnailImageUrl,500);
  const safeThumb = /^https:\/\/api\.vrchat\.cloud\//i.test(thumb)?thumb:null;

  // Track accepted requests only; repeat IDs are never charged a Gemini call.
  const {error:attemptError}=await db.from("world_submission_attempts")
    .insert({ip_day_hash:dayHash,world_id:id});
  if (attemptError) return respond({error:"投稿受付に失敗しました。"},503);
  const {error:insertError}=await db.from("world_submissions").insert({
    world_id:id,world_url:"https://vrchat.com/home/world/"+id+"/info",
    world_name:name,world_author:author,
    world_description:str(meta?.description,1800),
    world_tags:tagList,world_thumbnail:safeThumb,status:"queued",
  });
  if (insertError) {
    if (insertError.code==="23505")
      return respond({ok:true,status:"queued",worldId:id,alreadySubmitted:true},200);
    return respond({error:"投稿の保存に失敗しました。"},503);
  }
  return respond({ok:true,status:"queued",worldId:id,name},201);
}

Deno.serve(async(req:Request)=>{
  let result:Response;
  try { result=await handle(req); }
  catch (error) {
    console.error("world-submit failure",error instanceof Error?error.name:"unknown");
    result=respond({error:"現在投稿を受け付けられません。"},503);
  }
  const origin=req.headers.get("origin")||"";
  if (ALLOWED.has(origin)) result.headers.set("Access-Control-Allow-Origin",origin);
  return result;
});
