#!/usr/bin/env python3
"""Conservatively classify AUTOMATIC discovery leads with the existing Gemini club classifier.

Only official, public VRChat World metadata + independent descriptive evidence
may trigger admission. Keyword-based discovery scores NEVER count as Gemini scores.
Administrator rejections or approvals ALWAYS take precedence. All ambiguous
leads remain visible in the Admin candidate queue.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
from pathlib import Path

try:
    from scripts import review_world_submissions as classifier
except ModuleNotFoundError:
    import review_world_submissions as classifier

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "world-candidates.json"
WORLDS = ROOT / "data" / "worlds.json"
DECISIONS = ROOT / "data" / "world-candidate-ai-decisions.json"
MODERATION = "https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-candidate-status"
RETRY_HOURS = 6
CLASSIFIER_REVISION = 'json-validation-20261007-v2'


def moderation_decisions() -> dict[str, str]:
    """Fail closed: never override a moderation decision if its state cannot be read."""
    response = classifier.get_json(MODERATION, timeout=22)
    if not isinstance(response, dict) or response.get("complete") is not True:
        raise ValueError("Admin moderation statuses are incomplete")
    items = response.get("decisions")
    if not isinstance(items, list):
        raise ValueError("Admin moderation statuses are missing")
    result = {}
    for row in items:
        if (not isinstance(row, dict) or
                not classifier.WORLD_ID.fullmatch(str(row.get("world_id") or "")) or
                row.get("status") not in {"approved", "rejected"}):
            raise ValueError("Malformed moderator decision - cannot auto-admit")
        result[row["world_id"]] = row["status"]
    return result


def retry_due(record: dict, now: dt.datetime) -> bool:
    if record.get("status") not in {"verification_unavailable", "classification_unavailable"}:
        return False
    # Reprocess an invalid Gemini response once when the JSON decoder is fixed.
    # Successful/uncertain decisions and verification failures are unaffected.
    if (record.get("status")=="classification_unavailable" and
            record.get("classifierRevision")!=CLASSIFIER_REVISION):
        return True
    try:
        last = dt.datetime.fromisoformat(str(record["reviewedAt"]).replace("Z","+00:00"))
        if last.tzinfo is None:
            return True
        return (now-last).total_seconds() >= RETRY_HOURS * 3600
    except (TypeError, ValueError, KeyError):
        return True


def review_candidates() -> dict:
    catalog=classifier.read_json(WORLDS, [])
    pending=classifier.read_json(CANDIDATES, [])
    prior=classifier.read_json(DECISIONS, [])
    if not isinstance(catalog,list) or not isinstance(pending,list) or not isinstance(prior,list):
        raise ValueError("World catalog, discovery queue or AI decisions not valid JSON arrays")
    if any(not isinstance(x,dict) for x in catalog+pending+prior):
        raise ValueError("World catalog, candidate and decision entries must be objects")
    known={entry.get("id") for entry in catalog}
    history={entry.get("id"):entry for entry in prior if classifier.WORLD_ID.fullmatch(str(entry.get("id") or ""))}
    human=moderation_decisions()
    key=os.environ.get("GEMINI_API_KEY","").strip()
    max_per_run=max(1,min(12,int(os.environ.get("VCC_DISCOVERY_AI_MAX_PER_RUN","6"))))
    now=dt.datetime.now(dt.timezone.utc)
    unique={}
    for item in pending:
        wid=str(item.get("id") or "")
        if classifier.WORLD_ID.fullmatch(wid) and wid not in unique:
            unique[wid]=item

    # Explicitly never interpret prior heuristic 'confidenceScore' as AI confidence.
    to_check=[]
    for wid,candidate in unique.items():
        if wid in known or wid in human:
            continue
        last=history.get(wid)
        if last and not retry_due(last,now):
            continue
        to_check.append(candidate)
    to_check=to_check[:max_per_run]
    if not key:
        print(f"INFO: Gemini key missing; {len(to_check)} discovered Worlds remain pending")
        return {"checked":0,"approved":0,"unresolved":len(pending),"skipped":"gemini_key_missing"}

    approved=[]
    excluded_nonpublic=[]
    attempted=0
    for candidate in to_check:
        wid=candidate["id"]
        # Full public status, name and author MUST be sourced from VRChat itself.
        try:
            meta=classifier.public_metadata(wid)
        except classifier.NonPublicWorldError as exc:
            # Only an explicit releaseStatus from official VRChat metadata
            # means the World is non-public. Remove it from the candidate
            # queue, and retain the ID in the audit to prevent rediscovery.
            history[wid]={**classifier.decide(wid,None,None,"excluded_nonpublic",
                          "Official VRChat releaseStatus: "+exc.release_status),
                          "source":"auto-discovery","classifierRevision":CLASSIFIER_REVISION}
            excluded_nonpublic.append(wid)
            attempted+=1
            print("EXCLUDED_NONPUBLIC "+wid+" status="+exc.release_status)
            continue
        except urllib.error.HTTPError as exc:
            # Anonymous API can refuse GitHub runners (401) or rate-limit.
            # Never label a temporarily inaccessible World as non-club.
            state="verification_unavailable" if exc.code in (401,403,429,500,502,503,504) else "needs_review"
            note="Official World lookup HTTP "+str(exc.code)
            history[wid]={**classifier.decide(wid,None,None,state,note),
                          "source":"auto-discovery","classifierRevision":CLASSIFIER_REVISION}
            attempted+=1
            print(f"VERIFY_{state.upper()} {wid} HTTP {exc.code}")
            if exc.code==429:
                break
            continue
        except (ValueError,urllib.error.URLError,OSError,TimeoutError) as exc:
            # A private/deleted World is not eligible, but admin can verify later.
            state="needs_review" if isinstance(exc,ValueError) else "verification_unavailable"
            history[wid]={**classifier.decide(wid,None,None,state,
                          "Official World metadata unavailable: "+type(exc).__name__),
                          "source":"auto-discovery","classifierRevision":CLASSIFIER_REVISION}
            attempted+=1
            print(f"VERIFY_{state.upper()} {wid} {type(exc).__name__}")
            continue
        try:
            assessment=classifier.classify_world(meta,key)
        except (ValueError,urllib.error.HTTPError,urllib.error.URLError,OSError,TimeoutError) as exc:
            history[wid]={**classifier.decide(wid,meta,None,"classification_unavailable",
                          "Gemini classification temporarily unavailable: "+type(exc).__name__),
                          "source":"auto-discovery","classifierRevision":CLASSIFIER_REVISION}
            attempted+=1
            print(f"CLASSIFICATION_UNAVAILABLE {wid} {type(exc).__name__}")
            # Avoid repeated failing paid API calls if the service is down.
            break
        if classifier.may_auto_approve(assessment,meta):
            catalog.append({
                "id":wid, "name":str(meta["name"]).strip()[:120],
                "author":str(meta["authorName"]).strip()[:120],
                "genres":["CLUB"], "editorialStatus":"unreviewed",
                "chartEligible":True,
                "source":"https://vrchat.com/home/world/"+wid+"/info",
                "discoveredBy":"automatic-discovery-gemini-reviewed",
            })
            known.add(wid)
            approved.append(wid)
            status="approved"
            note="Official public World verified; Gemini and independent nightlife evidence agreed"
            print("APPROVED "+wid+" "+str(meta["name"]).strip()[:120])
        else:
            status="needs_review"
            note="Gemini verdict or independent evidence insufficient; human review required"
            print("NEEDS_REVIEW "+wid+" verdict="+assessment["verdict"])
        history[wid]={**classifier.decide(wid,meta,assessment,status,note),
                      "source":"auto-discovery","classifierRevision":CLASSIFIER_REVISION,
                      "discoverySources":candidate.get("sourceCategories",[])}
        attempted+=1

    if approved:
        catalog.sort(key=lambda x:str(x.get("name") or "").casefold())
        WORLDS.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if approved or excluded_nonpublic:
        # Non-public World IDs stay in the AI audit but never in the visible
        # discovery candidate queue. Previously approved catalog entries
        # are also removed from that queue as before.
        blocked=set(excluded_nonpublic)
        pending=[row for row in pending if row.get("id") not in known
                 and row.get("id") not in blocked]
        CANDIDATES.write_text(json.dumps(pending,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    updated=sorted(history.values(),key=lambda x:(str(x.get("reviewedAt") or ""),str(x["id"])))
    if updated!=prior:
        DECISIONS.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    outcome={"checked":attempted,"approved":len(approved),
             "excluded_nonpublic":len(excluded_nonpublic),"unresolved":len(pending)}
    print("AI discovery candidate review: "+json.dumps(outcome,sort_keys=True))
    return outcome


if __name__=="__main__":
    review_candidates()
