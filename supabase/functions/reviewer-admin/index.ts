
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.95.0";

const ALLOWED_ORIGIN = "https://showchoo.github.io";
const VERCEL_ORIGIN = "https://vrc-club-charts.vercel.app";
const ALLOWED_ORIGINS = new Set([ALLOWED_ORIGIN, VERCEL_ORIGIN]);
const VRCHAT_WORLD_API = "https://api.vrchat.cloud/api/1/worlds/";
const WORLD_CATALOG_URL = "https://raw.githubusercontent.com/showchoo/vrc-club-charts/main/data/worlds.json";

const corsHeaders = {
  "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
  "Access-Control-Allow-Headers": "content-type, apikey, authorization, x-vcc-admin-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b)=>b.toString(16).padStart(2,"0")).join("");
}

function safeSlug(value: string) {
  return value.normalize("NFKD").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,48);
}

function randomReviewerCode() {
  const bytes=new Uint8Array(24);
  crypto.getRandomValues(bytes);
  let binary="";
  for(const b of bytes) binary+=String.fromCharCode(b);
  return "vcc_rev_"+btoa(binary).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
}

function worldGenres(sourceCategories: unknown, reasons: unknown) {
  const genres = new Set<string>(["CLUB"]);
  const cats = Array.isArray(sourceCategories) ? sourceCategories.map(String) : [];
  const reasonText = Array.isArray(reasons) ? reasons.map(String).join(" ").toLowerCase() : "";
  if (cats.includes("event_venue")) genres.add("EVENT");
  if (reasonText.includes("dj")) genres.add("DJ");
  if (reasonText.includes("dance") || reasonText.includes("ダンス")) genres.add("DANCE");
  if (reasonText.includes("music") || reasonText.includes("音楽")) genres.add("MUSIC");
  if (reasonText.includes("audiolink") || reasonText.includes("オーディオリンク")) genres.add("AUDIOLINK");
  if (reasonText.includes("stage") || reasonText.includes("ステージ")) genres.add("STAGE");
  return [...genres];
}

async function handleVccRequest(req: Request) {
  if (req.method==="OPTIONS") return new Response("ok",{headers:corsHeaders});
  if (req.method!=="POST") return json({error:"Method not allowed"},405);

  const origin=req.headers.get("origin");
  if(origin && !ALLOWED_ORIGINS.has(origin)) return json({error:"Origin not allowed"},403);

  const adminKey=req.headers.get("x-vcc-admin-key")||"";
  const configuredKey=Deno.env.get("VCC_ADMIN_KEY")||"";
  if(configuredKey.length<24) return json({error:"Admin key is not configured"},503);
  if(!adminKey || await sha256(adminKey)!==await sha256(configuredKey))
    return json({error:"Unauthorized"},401);

  const url=Deno.env.get("SUPABASE_URL")||"";
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
  if(!url||!serviceKey) return json({error:"Server configuration error"},500);
  const supabase=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});

  let body:any;
  try{body=await req.json()}catch(_){return json({error:"Invalid JSON"},400)}
  const action=String(body?.action||"");

  if(action==="list"){
    const {data,error}=await supabase.from("reviewer_applications")
      .select("id,vrchat_name,contact,experience,background,affiliations,availability,status,created_at,reviewed_at,reviewer_id")
      .eq("status","pending").order("created_at",{ascending:true});
    if(error) return json({error:error.message},500);
    return json({applications:data||[]});
  }

  if(action==="list_community_reviews"){
    const {data,error}=await supabase.from("community_reviews")
      .select("id,world_id,display_name,reviewed_at,visual,lighting,sound,spatial,interaction,originality,optimization,comment,conflict,status,created_at")
      .eq("status","pending").order("created_at",{ascending:true}).limit(100);
    if(error) return json({error:error.message},500);
    return json({reviews:data||[]});
  }

  if(action==="publish_community_review" || action==="reject_community_review"){
    const reviewId=String(body?.id||"").trim();
    if(!/^[0-9a-f-]{36}$/i.test(reviewId)) return json({error:"Invalid review ID"},400);
    const decision=action==="publish_community_review" ? "published":"rejected";
    const now=new Date().toISOString();
    const {data,error}=await supabase.from("community_reviews")
      .update({status:decision,moderated_at:now,published_at:decision==="published"?now:null})
      .eq("id",reviewId).eq("status","pending").select("id,status").maybeSingle();
    if(error) return json({error:error.message},500);
    if(!data) return json({error:"Review is no longer pending"},409);
    return json({ok:true,id:data.id,status:data.status});
  }

  if(action==="list_reviews"){
    const {data,error}=await supabase.from("review_submissions")
      .select("id,reviewer_id,world_id,conflict,reviewed_at,visual,lighting,sound,spatial,interaction,originality,optimization,comment,status,created_at")
      .eq("status","pending").order("created_at",{ascending:true});
    if(error) return json({error:error.message},500);
    return json({reviews:data||[]});
  }


  if(action==="list_analytics"){
    const now=Date.now();
    const dayMs=24*60*60*1000;
    const since30=new Date(now-30*dayMs).toISOString();
    const since7=now-7*dayMs;

    const {count:allTime,error:countError}=await supabase.from("site_analytics_events")
      .select("id",{count:"exact",head:true});
    if(countError) return json({error:countError.message},500);

    const events:any[]=[];
    let truncated=false;
    for(let offset=0;offset<10000;offset+=1000){
      const {data,error}=await supabase.from("site_analytics_events")
        .select("path,referrer_host,utm_source,utm_medium,utm_campaign,created_at")
        .gte("created_at",since30)
        .order("created_at",{ascending:true})
        .range(offset,offset+999);
      if(error) return json({error:error.message},500);
      events.push(...(data||[]));
      if((data||[]).length<1000) break;
      if(offset===9000) truncated=true;
    }

    const jstDay=(value:any)=>{
      const parts=new Intl.DateTimeFormat("en-US",{
        timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"
      }).formatToParts(new Date(value));
      const m=Object.fromEntries(parts.map(p=>[p.type,p.value]));
      return `${m.year}-${m.month}-${m.day}`;
    };
    const today=jstDay(new Date());
    // Unique browser estimates are derived exclusively on the server from
    // recently observed salted hashes. Never send visitor hashes to the admin UI.
    const uniqueRows:any[]=[];
    let uniqueTruncated=false;
    for(let offset=0;offset<10000;offset+=1000){
      const {data,error}=await supabase.from("site_analytics_unique_visits")
        .select("visitor_hash,last_seen_at,visit_day")
        .gte("last_seen_at",since30)
        .order("last_seen_at",{ascending:true})
        .range(offset,offset+999);
      if(error) return json({error:"Unique browser count unavailable"},503);
      uniqueRows.push(...(data||[]));
      if((data||[]).length<1000) break;
      if(offset===9000) uniqueTruncated=true;
    }
    const todayBrowserIds=new Set<string>();
    const sevenBrowserIds=new Set<string>();
    const thirtyBrowserIds=new Set<string>();
    for(const visit of uniqueRows){
      if(visit.visit_day===today) todayBrowserIds.add(visit.visitor_hash);
      if(new Date(visit.last_seen_at).getTime()>=since7)
        sevenBrowserIds.add(visit.visitor_hash);
      thirtyBrowserIds.add(visit.visitor_hash);
    }

    const daily=new Map<string,number>();
    const pages=new Map<string,number>();
    const sources=new Map<string,number>();
    const campaigns=new Map<string,number>();
    let todayViews=0;
    let sevenDayViews=0;

    for(const event of events){
      const ts=new Date(event.created_at).getTime();
      const day=jstDay(event.created_at);
      daily.set(day,(daily.get(day)||0)+1);
      pages.set(event.path,(pages.get(event.path)||0)+1);
      if(day===today) todayViews+=1;
      if(ts>=since7) sevenDayViews+=1;

      const source=event.utm_source
        ? `UTM: ${String(event.utm_source)}`
        : (event.referrer_host || "Direct / unknown");
      sources.set(source,(sources.get(source)||0)+1);

      if(event.utm_campaign){
        const key=`${event.utm_campaign}${event.utm_source ? " · "+event.utm_source : ""}`;
        campaigns.set(key,(campaigns.get(key)||0)+1);
      }
    }

    const top=(map:Map<string,number>,limit=10)=>[...map.entries()]
      .sort((a,b)=>b[1]-a[1])
      .slice(0,limit)
      .map(([name,count])=>({name,count}));

    const dailyRows=[...daily.entries()]
      .sort((a,b)=>a[0].localeCompare(b[0]))
      .map(([date,count])=>({date,count}));

    return json({
      generatedAt:new Date().toISOString(),
      summary:{
        allTime:Number(allTime||0),
        last30:events.length,
        last7:sevenDayViews,
        today:todayViews,
        truncated
      },
      daily:dailyRows,
      topPages:top(pages),
      topSources:top(sources),
      topCampaigns:top(campaigns),
      uniqueVisitors:{
        today:todayBrowserIds.size,
        last7:sevenBrowserIds.size,
        last30:thirtyBrowserIds.size,
        truncated:uniqueTruncated,
        since:"2026-10-06",
        note:"Estimated unique browsers, not identified people. Counts begin after implementation."
      }
    });
  }

  if(action==="list_world_candidate_decisions"){
    const {data,error}=await supabase.from("world_candidate_decisions")
      .select("world_id,status").order("reviewed_at",{ascending:false});
    if(error) return json({error:error.message},500);
    return json({decisions:data||[]});
  }


  if(action==="list_editor_scores"){
    const {data,error}=await supabase.from("editor_world_scores")
      .select("world_id,visual,lighting,sound,spatial,interaction,originality,optimization,total_score,editor_pick,note,updated_at")
      .order("editor_pick",{ascending:false})
      .order("total_score",{ascending:false});
    if(error) return json({error:error.message},500);
    return json({scores:data||[]});
  }

  if(action==="upsert_editor_score" || action==="delete_editor_score"){
    const worldId=String(body?.id||"").trim();
    if(!/^wrld_[0-9a-fA-F-]{36}$/.test(worldId)) return json({error:"Invalid World ID"},400);

    let inCatalog=false;
    try{
      const response=await fetch(WORLD_CATALOG_URL,{headers:{"User-Agent":"VRCClubCharts-Admin/1.0"}});
      if(response.ok){
        const worlds=await response.json();
        inCatalog=Array.isArray(worlds) && worlds.some((w:any)=>w?.id===worldId && w?.chartEligible===true);
      }
    }catch(_){}
    if(!inCatalog){
      const {data:approved}=await supabase.from("worlds_public")
        .select("id").eq("id",worldId).eq("chart_eligible",true).maybeSingle();
      inCatalog=Boolean(approved);
    }
    if(!inCatalog) return json({error:"World is not in the approved club catalog"},400);

    if(action==="delete_editor_score"){
      const {error}=await supabase.from("editor_world_scores").delete().eq("world_id",worldId);
      if(error) return json({error:error.message},500);
      return json({ok:true,worldId});
    }

    const defs:Record<string,[number,number]>={
      visual:[0,20], lighting:[0,20], sound:[0,15], spatial:[0,15],
      interaction:[0,10], originality:[0,10], optimization:[0,10],
    };
    const scores:any={};
    for(const [key,[min,max]] of Object.entries(defs)){
      const value=Number(body?.scores?.[key]);
      if(!Number.isInteger(value) || value<min || value>max){
        return json({error:`Invalid editor score: ${key}`},400);
      }
      scores[key]=value;
    }
    const note=String(body?.note||"").trim();
    if(note.length>1000) return json({error:"Editor note must be 1000 characters or fewer"},400);
    const row={
      world_id:worldId,
      ...scores,
      editor_pick:body?.editorPick===true,
      note:note||null,
      updated_at:new Date().toISOString(),
    };
    const {data,error}=await supabase.from("editor_world_scores")
      .upsert(row,{onConflict:"world_id"})
      .select("world_id,visual,lighting,sound,spatial,interaction,originality,optimization,total_score,editor_pick,note,updated_at")
      .single();
    if(error) return json({error:error.message},500);
    return json({ok:true,score:data});
  }

  if(action==="approve_world_candidate" || action==="reject_world_candidate"){
    const worldId=String(body?.id||"").trim();
    if(!/^wrld_[0-9a-fA-F-]{36}$/.test(worldId)) return json({error:"Invalid World ID"},400);
    const candidateName=String(body?.name||"").trim().slice(0,200);
    const source=String(body?.source||"").trim().slice(0,500) || null;

    if(action==="reject_world_candidate"){
      const {error}=await supabase.from("world_candidate_decisions").upsert({
        world_id:worldId,
        status:"rejected",
        candidate_name:candidateName||null,
        source_url:source,
        reviewed_at:new Date().toISOString(),
      },{onConflict:"world_id"});
      if(error) return json({error:error.message},500);
      return json({ok:true,status:"rejected",worldId});
    }

    let world:any;
    try{
      const response=await fetch(VRCHAT_WORLD_API+encodeURIComponent(worldId),{
        headers:{
          "Accept":"application/json",
          "User-Agent":"VRCClubCharts/0.4 (+https://showchoo.github.io/vrc-club-charts/)"
        }
      });
      if(!response.ok) return json({error:`VRChat World verification failed (HTTP ${response.status})`},400);
      world=await response.json();
    }catch(_){
      return json({error:"Could not verify World with VRChat"},503);
    }

    if(String(world?.id||"")!==worldId) return json({error:"VRChat World ID mismatch"},400);
    const releaseStatus=String(world?.releaseStatus||"").toLowerCase();
    if(releaseStatus && releaseStatus!=="public") return json({error:"Only public VRChat Worlds can be approved"},400);

    const officialName=String(world?.name||candidateName||"").trim();
    const officialAuthor=String(world?.authorName||"").trim();
    if(!officialName || !officialAuthor) return json({error:"VRChat World metadata is incomplete"},400);

    const genres=worldGenres(body?.sourceCategories,body?.reasons);
    const approvedAt=new Date().toISOString();

    const {error:worldError}=await supabase.from("worlds_public").upsert({
      id:worldId,
      name:officialName,
      author:officialAuthor,
      genres,
      chart_eligible:true,
      source,
      approved_at:approvedAt,
    },{onConflict:"id"});
    if(worldError) return json({error:worldError.message},500);

    const {error:decisionError}=await supabase.from("world_candidate_decisions").upsert({
      world_id:worldId,
      status:"approved",
      candidate_name:candidateName||officialName,
      source_url:source,
      reviewed_at:approvedAt,
    },{onConflict:"world_id"});
    if(decisionError){
      await supabase.from("worlds_public").delete().eq("id",worldId);
      return json({error:decisionError.message},500);
    }

    return json({
      ok:true,
      status:"approved",
      worldId,
      name:officialName,
      author:officialAuthor,
      genres,
    });
  }

  const id=String(body?.id||"");
  if(!/^[0-9a-f-]{36}$/i.test(id)) return json({error:"Invalid id"},400);

  if(action==="approve_review" || action==="reject_review"){
    const {data:review,error:fetchError}=await supabase.from("review_submissions")
      .select("*").eq("id",id).single();
    if(fetchError||!review) return json({error:"Review submission not found"},404);
    if(review.status!=="pending") return json({error:"Review is no longer pending"},409);

    if(action==="reject_review"){
      const {error}=await supabase.from("review_submissions")
        .update({status:"rejected",reviewed_by_admin_at:new Date().toISOString()})
        .eq("id",id).eq("status","pending");
      if(error) return json({error:error.message},500);
      return json({ok:true,status:"rejected"});
    }

    const reviewId="review-"+id;
    const published={
      id:reviewId,
      submission_id:id,
      world_id:review.world_id,
      reviewer_id:review.reviewer_id,
      conflict:review.conflict,
      reviewed_at:review.reviewed_at,
      visual:review.visual,
      lighting:review.lighting,
      sound:review.sound,
      spatial:review.spatial,
      interaction:review.interaction,
      originality:review.originality,
      optimization:review.optimization,
      comment:review.comment,
      status:"published",
    };
    const {error:insertError}=await supabase.from("reviews_public").insert(published);
    if(insertError) return json({error:insertError.message},500);

    const {error:updateError}=await supabase.from("review_submissions")
      .update({status:"approved",reviewed_by_admin_at:new Date().toISOString(),published_review_id:reviewId})
      .eq("id",id).eq("status","pending");
    if(updateError){
      await supabase.from("reviews_public").delete().eq("id",reviewId);
      return json({error:updateError.message},500);
    }
    return json({ok:true,status:"approved",reviewId});
  }

  const {data:application,error:fetchError}=await supabase.from("reviewer_applications")
    .select("id,vrchat_name,experience,status,reviewer_id").eq("id",id).single();
  if(fetchError||!application) return json({error:"Application not found"},404);

  if(action==="reject"){
    if(application.status!=="pending") return json({error:"Application is no longer pending"},409);
    const {error}=await supabase.from("reviewer_applications")
      .update({status:"rejected",reviewed_at:new Date().toISOString()})
      .eq("id",id).eq("status","pending");
    if(error) return json({error:error.message},500);
    return json({ok:true,status:"rejected"});
  }

  if(action==="approve"){
    if(application.status!=="pending") return json({error:"Application is no longer pending"},409);
    const baseSlug=safeSlug(application.vrchat_name);
    const baseId="reviewer-"+(baseSlug||id.slice(0,8));
    let reviewerId=baseId;
    const {data:collision}=await supabase.from("reviewers_public").select("id").eq("id",reviewerId).maybeSingle();
    if(collision) reviewerId=(baseId+"-"+id.slice(0,8)).slice(0,63);

    const reviewerAccessCode=randomReviewerCode();
    const tokenHash=await sha256(reviewerAccessCode);
    const approvedAt=new Date().toISOString();

    const {error:insertReviewerError}=await supabase.from("reviewers_public").insert({
      id:reviewerId,
      name:application.vrchat_name,
      status:"active",
      tags:Array.isArray(application.experience)?application.experience:[],
      approved_at:approvedAt,
    });
    if(insertReviewerError) return json({error:insertReviewerError.message},500);

    const {error:credentialError}=await supabase.from("reviewer_credentials").insert({
      reviewer_id:reviewerId,
      token_hash:tokenHash
    });
    if(credentialError){
      await supabase.from("reviewers_public").delete().eq("id",reviewerId);
      return json({error:credentialError.message},500);
    }

    const {error:updateError}=await supabase.from("reviewer_applications")
      .update({status:"approved",reviewer_id:reviewerId,reviewed_at:approvedAt})
      .eq("id",id).eq("status","pending");
    if(updateError){
      await supabase.from("reviewer_credentials").delete().eq("reviewer_id",reviewerId);
      await supabase.from("reviewers_public").delete().eq("id",reviewerId);
      return json({error:updateError.message},500);
    }
    return json({ok:true,status:"approved",reviewerId,reviewerAccessCode});
  }

  return json({error:"Unknown action"},400);
}

Deno.serve(async (req: Request) => {
  const response = await handleVccRequest(req);
  const origin = req.headers.get("origin") || "";
  if (ALLOWED_ORIGINS.has(origin)) {
    response.headers.set("Access-Control-Allow-Origin", origin);
  }
  return response;
});
