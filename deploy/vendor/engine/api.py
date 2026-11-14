"""Deterministic context-fusion engine for nightly crew wellbeing inputs."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any
import math
import uuid


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _num(obj: Any, key: str, default: float = 0.0) -> float:
    try:
        v = float(obj.get(key, default)) if isinstance(obj, dict) else default
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _median(values: list[float], default: float) -> float:
    return float(median(values)) if values else default


def _psychometrics(payload: dict) -> dict:
    """Score optional PT, ICE and Mini-IPIP item maps without changing indices."""
    b = payload.get("behavioral_inputs") or {}
    pt = b.get("pt_scores", payload.get("pt_scores", {})) or {}
    ice = b.get("ice_item_scores", payload.get("ice_item_scores", {})) or {}
    mini = payload.get("mini_ipip", payload.get("ipip_scores", {})) or {}
    if isinstance(pt, list): pt = {str(i + 1): v for i, v in enumerate(pt)}
    if isinstance(ice, list): ice = {str(i + 1): v for i, v in enumerate(ice)}
    if isinstance(mini, list): mini = {str(i + 1): v for i, v in enumerate(mini)}
    def vals(src, ids, reverse, top, floor=0):
        out=[]
        for i in ids:
            v=src.get(str(i),src.get(f"{i:02d}",src.get(f"PT-{i:02d}",src.get(f"ICE-{i}",None)))) if isinstance(src,dict) else None
            if v is None: continue
            try: v=float(v)
            except (ValueError,TypeError): continue
            if not math.isfinite(v): continue
            v=max(floor,min(top,v)); out.append((top+floor-v if i in reverse else v))
        return out
    pt_domains={
      "erms": ([1,8,11,12,14,17],[1,14,17]),
      "sdfc": ([2,3,10,13,18,20],[3,10,13,18]),
      "sprp": ([5,6,7,19],[5,6,7]),
      "scp": ([4,9,15,16],[16]),
    }
    pt_out={k: round(sum(v)/len(v),3) if (v:=vals(pt,ids,rev,4)) else None for k,(ids,rev) in pt_domains.items()}
    ice_domains={"authority_displacement":range(101,109),"cognitive_saliency":range(201,209),"somatic_fullness":range(301,309),"resilience":range(401,409)}
    ice_reverse={106,108,208,401,402,403,404,405,407,408}
    ice_out={k:round(sum(v)/len(v),3) if (v:=vals(ice,ids,ice_reverse,5,1)) else None for k,ids in ice_domains.items()}
    traits={}
    # Accept either named trait totals or 20 item responses.
    for t,ids,rev in [("E",[1,2,3,4],[2,4]),("A",[5,6,7,8],[6,8]),("C",[9,10,11,12],[10,12]),("N",[13,14,15,16],[14,16]),("O",[17,18,19,20],[18,20])]:
        direct=mini.get(t) if isinstance(mini,dict) else None
        if direct is not None:
            try: traits[t]=_clip(float(direct),4,20)
            except (ValueError,TypeError): pass
        else:
            v=vals(mini,ids,rev,5,1)
            if v: traits[t]=sum(v)
    return {"pt_domains":pt_out,"ice_domains":ice_out,"traits":traits}


def _dprime(hits: int, misses: int, fa: int, cr: int) -> float:
    # Loglinear correction keeps inverse-normal values finite at 0% and 100%.
    hr=(hits+.5)/(hits+misses+1) if hits+misses else .5
    far=(fa+.5)/(fa+cr+1) if fa+cr else .5
    def inv(p):
        # Acklam approximation
        a=[-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924]
        b=[-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857]
        c=[-.00778489400243,-.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878]
        d=[.007784695709041,.32246712907004,2.445134137143,3.75440866190742]
        if p<.02425:
            q=math.sqrt(-2*math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p>1-.02425: return -inv(1-p)
        q=p-.5;r=q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    return inv(hr)-inv(far)


def _cognitive(c: dict) -> dict:
    out={}
    if not isinstance(c,dict): return out
    if any(k in c for k in ("pvt_rt_ms","pvt_reaction_times_ms","pvt_reaction_times")):
        rt=c.get("pvt_rt_ms",c.get("pvt_reaction_times_ms",c.get("pvt_reaction_times",[])))
        rt=[float(x) for x in rt if isinstance(x,(int,float)) and math.isfinite(x) and x>=0]
        out["pvt"]={"trials":len(rt),"lapses_355ms":sum(x>355 for x in rt),"lapses_500ms":sum(x>500 for x in rt),"false_starts":sum(x<100 for x in rt),"mean_rt_ms":round(sum(rt)/len(rt),2) if rt else None,"mean_reciprocal_speed":round(sum(1000/x for x in rt if x>0)/max(1,sum(x>0 for x in rt)),4) if rt else None,"sd_rt_ms":round(math.sqrt(sum((x-sum(rt)/len(rt))**2 for x in rt)/len(rt)),2) if rt else None}
    for test, keys in {"dsst":["dsst_throughput","dsst_correct","dsst_errors","dsst_latency_ms"],"stroop":["stroop_congruent_rt_ms","stroop_incongruent_rt_ms","stroop_errors","stroop_incongruent_errors"]}.items():
        if any(k in c for k in keys):
            if test=="dsst":
                n=_num(c,"dsst_throughput",_num(c,"dsst_correct")); err=_num(c,"dsst_errors")
                out[test]={"throughput":n,"error_rate_pct":round(100*err/max(1,n+err),2),"latency_ms":_num(c,"dsst_latency_ms")}
            else:
                a=c.get(keys[0],[]); b=c.get(keys[1],[])
                am=sum(a)/len(a) if isinstance(a,list) and a else _num(c,"stroop_congruent_mean_rt_ms")
                bm=sum(b)/len(b) if isinstance(b,list) and b else _num(c,"stroop_incongruent_mean_rt_ms")
                out[test]={"interference_ms":bm-am,"incongruent_error_rate_pct":100*_num(c,"stroop_incongruent_errors")/max(1,_num(c,"stroop_incongruent_trials",len(b) if isinstance(b,list) else 0))}
    if all(k in c for k in ("nback_hits","nback_misses","nback_false_alarms","nback_correct_rejections")):
        out["spatial_nback"]={"d_prime":round(_dprime(*[int(_num(c,k)) for k in ("nback_hits","nback_misses","nback_false_alarms","nback_correct_rejections")]),3),"lure_commission_errors":int(_num(c,"nback_lure_errors"))}
    if "matrix_answers" in c:
        out["matrices"]={"correct":int(sum(bool(x.get("correct")) for x in c["matrix_answers"] if isinstance(x,dict))),"items":len(c["matrix_answers"])}
    return out


def run(payload: dict) -> dict:
    """Process one nightly record and return JSON-serializable scores and state."""
    if not isinstance(payload, dict):
        payload = {}
    persona=payload.get("persona") or {}; traits=persona.get("traits") or {}
    sensing=payload.get("sensing_data") or {}; behavior=payload.get("behavioral_inputs") or {}
    env=payload.get("environmental_logs") or {}; clinical=payload.get("clinical_scales") or {}
    old=payload.get("state") or {}; old=old if isinstance(old,dict) else {}
    state={"baseline_rr":list(old.get("baseline_rr",[]))[-28:],"cusum_s_t":max(0,_num(old,"cusum_s_t",_num(old,"S_t"))),
           "history":list(old.get("history",[]))[-27:],"persistence_days":max(0,int(_num(old,"persistence_days",_num(old,"persistence",0)))),
           "alert_days":max(0,int(_num(old,"alert_days",0))),"low_z_days":max(0,int(_num(old,"low_z_days",0))),
           "context_history":list(old.get("context_history",[]))[-28:]}
    crisis=_num(clinical,"phq9_item9")>0
    if crisis:
        return {"safety_status":{"crisis_override_triggered":True,"escalation_type":"IMMEDIATE_CRISIS_SUPPORT","emergency_message":"Immediate safety support is needed. Contact mission medical support or local emergency services now, and stay with a trusted person."},"state":state}

    rr=_num(sensing,"rr_med"); quality=_num(sensing,"quality"); hours=_num(sensing,"valid_hours")
    accepted=quality>=.60 and hours>=4 and rr>0
    baseline=persona.get("baselines") or {}
    history=state["baseline_rr"]
    # Until a history exists, use supplied personal baseline; then use the rolling valid-night median/MAD.
    base_med=_num(baseline,"rr_med",_median(history,rr))
    base_mad=max(.40,_num(baseline,"mad_rr",_num(baseline,"rr_mad",.40)))
    # A few nights are not a stable personal reference distribution.  Keep the
    # supplied baseline until the rolling window is fully populated; otherwise
    # a 3-point median/MAD can shrink the scale and turn ordinary noise into
    # apparent drift.
    if len(history)>=28:
        base_med=_median(history,base_med)
        base_mad=max(.40,_median([abs(x-base_med) for x in history],base_mad))
    z=(rr-base_med)/(1.4826*base_mad) if accepted else 0.0
    z=max(-10,min(10,z))
    state["cusum_s_t"]=max(0.0,state["cusum_s_t"]+z-.5) if accepted else state["cusum_s_t"]
    if accepted:
        state["history"]=(state["history"]+[round(z,6)])[-27:]
        state["persistence_days"]=state["persistence_days"]+1 if z>=1.5 else (0 if z<1 else max(0,state["persistence_days"]-1))
        state["low_z_days"]=state["low_z_days"]+1 if z<1 else 0
        if z>=2.5: state["alert_days"]+=1
        elif z<1: state["alert_days"]=0
    hist=state["history"][-3:]
    severe_recent=sum(x>=2.5 for x in hist)>=2
    if not accepted:
        phys_level=int(_num(old,"phys_level",0))
    elif state["cusum_s_t"]>=4 or severe_recent:
        phys_level=3 if state["alert_days"]>=3 else 2
    elif state["cusum_s_t"]>=2 or (len(state["history"])>=2 and all(x>=1.5 for x in state["history"][-2:])):
        phys_level=1
    elif state["low_z_days"]>=3:
        phys_level=0; state["cusum_s_t"]=min(state["cusum_s_t"],1.99)
    else:
        phys_level=int(_num(old,"phys_level",0)) if _num(old,"phys_level",0)>0 else 0
    state["phys_level"]=phys_level
    if accepted:
        # context-v2.md 5.2: nights enter the 28-night buffer only if they pass the
        # quality gate and are Level 0 (z_raw < 1.5 and S_t < 2.0).
        admit=phys_level==0 and z<1.5 and state["cusum_s_t"]<2.0
        state["baseline_rr"]=(history+[rr])[-28:] if admit else history

    # Weekly mental indices: specified component scores are combined when present; absent components
    # are omitted rather than treated as zero. Clinical scales provide established anchor components.
    def avg_to_index(values): return round(_clip(50+15*(sum(values)/len(values))),2) if values else 50.0
    stress=[]
    if "evening_stress" in behavior: stress.append((_num(behavior,"evening_stress")-5)/5)
    if "evening_workload" in behavior: stress.append((_num(behavior,"evening_workload")-5)/5)
    if "gad2" in behavior: stress.append((_num(behavior,"gad2")-3)/3)
    if "stress_vas" in behavior: stress.append((_num(behavior,"stress_vas")-50)/50)
    if clinical: stress.extend([(_num(clinical,"gad7")-5)/10] if "gad7" in clinical else [])
    mood=[]
    if "mood_vas" in behavior: mood.append((50-_num(behavior,"mood_vas"))/50)
    if "phq2" in behavior: mood.append((_num(behavior,"phq2")-1.5)/1.5)
    if "who5" in clinical: mood.append((50-_num(clinical,"who5"))/50)
    fatigue=[]
    if "fatigue_vas" in behavior: fatigue.append((_num(behavior,"fatigue_vas")-50)/50)
    if "morning_kss" in behavior: fatigue.append((_num(behavior,"morning_kss")-5)/4)
    if "mental_fatigue_pulse_sum" in behavior: fatigue.append((_num(behavior,"mental_fatigue_pulse_sum")-9)/9)
    if "pvt_lapses" in (payload.get("cognitive_results") or {}): fatigue.append((_num(payload["cognitive_results"],"pvt_lapses")-2.5)/2.5)
    connect=[]
    for k,sign in (("ucla3",1),("team_friction_vas",1),("team_support_vas",-1)):
        if k in behavior: connect.append(sign*(_num(behavior,k)-50)/50)
    if "authority_displacement" in (behavior.get("ice_scores") or {}): connect.append((_num(behavior["ice_scores"],"authority_displacement")-3)/2)
    somatic=behavior.get("somatic_symptoms",[])
    if not isinstance(somatic,list): somatic=[]
    somatic_count=sum(str(x).lower()!="none" for x in somatic)
    body=[min(1,somatic_count/5)] if somatic else []
    if "somatic_score" in behavior: body.append((_num(behavior,"somatic_score")-50)/50)
    mental_indices={"stress_load":avg_to_index(stress),"mood_wellbeing":avg_to_index(mood),"fatigue_alertness":avg_to_index(fatigue),"connection_team":avg_to_index(connect),"body_symptom":avg_to_index(body)}
    mental_level=max(2 if (_num(clinical,"phq9")>=10 or _num(clinical,"gad7")>=10 or ("who5" in clinical and _num(clinical,"who5")<50) or _num(clinical,"k6")>=13) else 0,
                    2 if max(mental_indices.values())>=80 else 1 if max(mental_indices.values())>=65 else 0)

    # Context adjustment uses median pairwise slope on stored single-driver/day pairs.
    drivers={"evening_stress":_num(behavior,"evening_stress"),"evening_workload":_num(behavior,"evening_workload"),"late_caffeine":float(bool(behavior.get("late_caffeine",False))),"cabin_ppco2":_num(env,"cabin_ppco2"),"cognitive_fatigue":mental_indices["fatigue_alertness"]}
    ch=state["context_history"]
    prediction=base_med
    if len(ch)>=14:
        for key,x in drivers.items():
            pairs=[]
            for i,a in enumerate(ch):
                for b in ch[i+1:]:
                    dx=_num(b.get("drivers",{}),key)-_num(a.get("drivers",{}),key)
                    if abs(dx)>1e-9: pairs.append((_num(b,"rr")-_num(a,"rr"))/dx)
            beta=_median(pairs,0.0)
            prediction+=beta*(x-_median([_num(a.get("drivers",{}),key) for a in ch],x))
    z_adj=(rr-prediction)/(1.4826*base_mad) if accepted else 0.0
    persistence=state["persistence_days"]
    explained=bool(accepted and z>=2 and z_adj<1.5 and persistence<3)
    if mental_level and phys_level: quadrant="Converging Signals"
    elif phys_level: quadrant="Body Signal First"
    elif mental_level: quadrant="Mind Signal First"
    else: quadrant="Steady"
    priority=_clip(40*phys_level/3+40*mental_level/3+(15 if phys_level and mental_level else 0)+5*min(persistence,7)/7-(10 if explained else 0))

    cognitive=payload.get("cognitive_results") or {}; cogpen=_clip(.4*_clip(_num(cognitive,"pvt_lapses")/5*100)+.3*_clip(_num(cognitive,"dsst_throughput_drop_pct")/30*100)+.3*_clip((_num(cognitive,"stroop_interference_ms")-_num(cognitive,"stroop_baseline_ms"))/150*100))
    pulse=_num(behavior,"mental_fatigue_pulse_sum")
    mental_fatigue=_clip(.25*_num(behavior,"fatigue_vas",mental_indices["fatigue_alertness"])+.25*pulse/18*100+.25*cogpen+.25*_num(behavior,"nasa_tlx_mental_demand",_num(behavior,"evening_workload")*10))
    restlessness=_clip(_num(sensing,"restless_frac")/.25*100)
    somatic_score=_clip(somatic_count/5*100) if somatic else _num(behavior,"somatic_score")
    phys_fatigue=_clip(.35*_clip(z/3*100)+.25*restlessness+.20*_clip(state["cusum_s_t"]/4*100)+.20*somatic_score)
    health=_clip(100-.5*phys_fatigue-.5*mental_fatigue)
    # Intake resilience buffer is applied only when actual item-level intake is available.
    psych=_psychometrics(payload)
    resilience_values=[psych["pt_domains"].get("sprp"),psych["pt_domains"].get("sdfc"),psych["ice_domains"].get("resilience")]
    if all(v is not None for v in resilience_values) and sum(resilience_values)/14*100>75: health=_clip(health+5)

    # Record valid observations for forecasting only; baseline updates remain restricted to non-alert nights.
    if accepted:
        state["context_history"]=(ch+[ {"rr":rr,"drivers":drivers} ])[-28:]
    state["cusum_s_t"]=round(state["cusum_s_t"],6)
    metrics={"phys_z_raw":round(z,4),"phys_z_adj":round(z_adj,4),"cusum_s_t":state["cusum_s_t"],"phys_level":phys_level,"mental_indices":mental_indices,"mental_level":mental_level,"clinical_floor_breached":mental_level>=2 and (_num(clinical,"phq9")>=10 or _num(clinical,"gad7")>=10 or ("who5" in clinical and _num(clinical,"who5")<50) or _num(clinical,"k6")>=13),"night_quality_status":"ACCEPTED" if accepted else "NO_ESTIMATE","psychometric_scores":psych,"cognitive_metrics":_cognitive(cognitive)}

    co2=_num(env,"cabin_ppco2",float("nan")); co2_note=(f"Cabin ppCO2 elevated at {co2:.1f} mmHg; review ventilation." if math.isfinite(co2) and co2>3 else f"Cabin ppCO2 nominal at {co2:.1f} mmHg." if math.isfinite(co2) else "Cabin ppCO2 was not provided.")
    stability=( _num(traits,"C",12)+(24-_num(traits,"N",12)) )/2
    agency=(_num(traits,"E",12)+_num(traits,"O",12))/2
    if traits:
        px=stability>=12; py=agency>=12
        persona_quad="Autonomous Pioneer" if px and py else "Steady Anchor" if px else "Dynamic Explorer" if py else "Internal Deliberator"
    else:
        persona_quad=(persona.get("persona_matrix") or {}).get("quadrant","Unspecified")
        stability=_num((persona.get("persona_matrix") or {}),"stability",stability); agency=_num((persona.get("persona_matrix") or {}),"agency",agency)
    badge="#FB8C00" if _num(traits,"N")>=15 else "#D32F2F" if max(phys_level,mental_level)>=2 else "#43A047"
    advice=[]
    if behavior.get("late_caffeine"): advice.append("Consider moving caffeine earlier relative to the planned sleep period.")
    if phys_level or mental_level: advice.append("Review today's workload and recovery plan with mission support if these signals persist.")
    if not advice: advice.append("Continue the usual recovery routine and review the next check-in.")
    if _num(traits,"C")>=16: advice=[f"{i+1}. {x}" for i,x in enumerate(advice)]
    message="Your overnight measures are close to your personal baseline." if quadrant=="Steady" else f"Your current pattern is classified as {quadrant.lower()}; review the contributing measures and context."
    if _num(traits,"N")>=15: message="Small baseline shifts can occur during schedule changes. "+message
    if _num(traits,"E")<=8 and traits: advice.append("A quiet individual recovery activity may fit your preference.")
    band=[round(base_med-1.4826*base_mad,2),round(base_med+1.4826*base_mad,2)]
    packet_id=str(uuid.uuid5(uuid.NAMESPACE_URL,repr(sorted(payload.keys()))+str(rr)+str(state["cusum_s_t"])))
    headline=f"[{quadrant.upper()}] Recovery Advisory"
    return {
      "safety_status":{"crisis_override_triggered":False,"escalation_type":"NONE","emergency_message":None},
      "scores_and_metrics":metrics,
      "fatigue_and_health_ratings":{"mental_fatigue_score":round(_clip(mental_fatigue),2),"physiological_fatigue_score":round(_clip(phys_fatigue),2),"overall_health_resilience_index":round(_clip(health),2)},
      "classification":{"quadrant":quadrant,"priority_score":round(priority,2),"is_explained_by_context":explained,"persistence_days":persistence,"primary_driver":"Daytime workload and late caffeine" if behavior.get("late_caffeine") and _num(behavior,"evening_workload")>=5 else "Respiration and sleep quality" if z>=1.5 else "No single elevated driver"},
      "dashboard_visualization_data":{"dual_axis_timeline_point":{"respiration_bpm":rr if accepted else None,"respiration_baseline_band":band,"mental_load_score":mental_indices["stress_load"]},"persona_matrix":{"stability_score":round(stability,2),"agency_score":round(agency,2),"quadrant_name":persona_quad},"radar_traits":{k:traits[k] for k in "EACNO" if k in traits},"badge_color":badge,"cusum_meter_percent":round(_clip(state["cusum_s_t"]/4*100),2)},
      "user_facing_advisory":{"headline":headline,"personality_tailored_message":message,"actionable_recommendations":advice,"environmental_note":co2_note},
      "flight_surgeon_briefing_snippet":f"{persona.get('user_id','Crew')}: nocturnal RR {rr:.1f} BPM (z={z:.2f}); Stress/Load Index {mental_indices['stress_load']:.1f}. {co2_note}",
      "operational_extensions":{"exercise_log":payload.get("exercise_log",{}),"environmental_logs":env,"ventilation_anomaly":bool(math.isfinite(co2) and co2>3 and z>=1.5),"pmc_report":"Weekly private conference summary available from the current scores and recent state."},
      "store_and_forward_sync_packet":{"packet_id":packet_id,"timestamp_utc":payload.get("timestamp_utc"),"queue_status":"QUEUED"},
      "state":state
    }

