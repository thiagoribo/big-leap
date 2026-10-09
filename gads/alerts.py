"""Alert rules. Each rule takes the collected data plus thresholds and returns
a list of alerts: {"severity": "alta|media|baixa", "area": ..., "message": ...}."""

from datetime import date


def totals(rows):
    t = {"cost": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0, "conv_value": 0.0}
    for r in rows:
        for k in t:
            t[k] += r[k]
    return t


def cpa(row):
    return row["cost"] / row["conversions"] if row["conversions"] else None


def target_cpa(data, cfg):
    if cfg.get("target_cpa"):
        return float(cfg["target_cpa"])
    return cpa(totals(data["daily"]))


def _money(value, data):
    return f"{data['account']['currency']} {value:,.2f}"


def _alert(severity, area, message):
    return {"severity": severity, "area": area, "message": message}


def tracking(data, cfg):
    alerts = []
    if not data["account"]["auto_tagging"]:
        alerts.append(_alert("alta", "Tracking",
            "Auto-tagging (GCLID) está DESLIGADO. Isso quebra a atribuição de conversões "
            "do GA4 e de conversões offline."))

    days = sorted(data["daily"], key=lambda d: d["date"])
    n = cfg["tracking_zero_days"]
    baseline = days[-14 - n:-n] if len(days) > n else []
    avg = sum(d["conversions"] for d in baseline) / len(baseline) if baseline else 0
    recent = days[-n:]
    if avg >= 1 and len(recent) == n and all(d["conversions"] == 0 and d["clicks"] > 0 for d in recent):
        alerts.append(_alert("alta", "Tracking",
            f"Zero conversões nos últimos {n} dias ({recent[0]['date']} a {recent[-1]['date']}) "
            f"com cliques acontecendo, mas a média era {avg:.1f}/dia. Verifique a tag/GTM "
            "e o formulário da landing page."))

    for a in data["conversion_actions"]:
        if a["status"] == "ENABLED" and a["primary"] and a["all_conversions"] == 0:
            alerts.append(_alert("media", "Tracking",
                f"Ação de conversão primária \"{a['name']}\" ({a['type']}) não registrou "
                "nenhuma conversão em 14 dias. Ela está otimizando lances; confira se está disparando."))
        if a["status"] not in ("ENABLED", "HIDDEN"):
            alerts.append(_alert("baixa", "Tracking",
                f"Ação de conversão \"{a['name']}\" está com status {a['status']}."))

    for c in data["campaigns"]:
        if c["status"] == "ENABLED" and c["clicks"] >= 30 and c["conversions"] == 0:
            prev = next((p for p in data["campaigns_prev"] if p["id"] == c["id"]), None)
            if prev and prev["conversions"] >= 3:
                alerts.append(_alert("alta", "Tracking",
                    f"Campanha \"{c['name']}\" teve {c['clicks']} cliques e 0 conversões na semana, "
                    f"contra {prev['conversions']:.0f} na semana anterior."))
    return alerts


def campaigns(data, cfg):
    alerts = []
    prev = {p["id"]: p for p in data["campaigns_prev"]}
    for c in data["campaigns"]:
        p = prev.get(c["id"])
        if not p or p["conversions"] < cfg["wow_min_conversions"]:
            continue
        drop = 1 - c["conversions"] / p["conversions"]
        if drop >= cfg["wow_conversions_drop"]:
            alerts.append(_alert("alta", "Performance",
                f"\"{c['name']}\": conversões caíram {drop:.0%} na semana "
                f"({p['conversions']:.0f} → {c['conversions']:.0f})."))
        c_cpa, p_cpa = cpa(c), cpa(p)
        if c_cpa and p_cpa and c_cpa / p_cpa - 1 >= cfg["wow_cpa_increase"]:
            alerts.append(_alert("media", "Performance",
                f"\"{c['name']}\": CPA subiu {c_cpa / p_cpa - 1:.0%} "
                f"({_money(p_cpa, data)} → {_money(c_cpa, data)})."))

    for s in data["impression_share"]:
        if s["lost_budget"] and s["lost_budget"] >= cfg["budget_lost_is"]:
            alerts.append(_alert("media", "Orçamento",
                f"\"{s['name']}\" perdeu {s['lost_budget']:.0%} das impressões por orçamento. "
                "Se o CPA estiver bom, vale aumentar o orçamento."))
    return alerts


def keywords(data, cfg):
    alerts = []
    tcpa = target_cpa(data, cfg)
    floor = cfg["min_spend_for_alert"]
    for k in data["keywords"]:
        label = f"\"{k['keyword']}\" [{k['match_type']}] em {k['campaign']} › {k['ad_group']}"
        if k["conversions"] == 0:
            limit = max(floor, tcpa * cfg["keyword_no_conv_spend_x_cpa"]) if tcpa else floor
            if k["cost"] >= limit:
                alerts.append(_alert("alta", "Palavras-chave",
                    f"{label} gastou {_money(k['cost'], data)} sem nenhuma conversão."))
        elif tcpa and k["cost"] >= floor and cpa(k) >= tcpa * cfg["keyword_high_cpa_x"]:
            alerts.append(_alert("media", "Palavras-chave",
                f"{label} com CPA de {_money(cpa(k), data)} "
                f"({cpa(k) / tcpa:.1f}x o alvo de {_money(tcpa, data)})."))
        qs = k["quality_score"]
        if qs and qs <= cfg["low_quality_score"] and k["cost"] >= floor:
            alerts.append(_alert("baixa", "Palavras-chave",
                f"{label} com Quality Score {qs}/10 e {_money(k['cost'], data)} de gasto. "
                "Revise relevância do anúncio e da landing page."))
    return alerts


def search_terms(data, cfg):
    alerts = []
    tcpa = target_cpa(data, cfg)
    floor = cfg["min_spend_for_alert"]
    limit = max(floor, tcpa * cfg["search_term_no_conv_spend_x_cpa"]) if tcpa else floor
    for t in data["search_terms"]:
        if t["conversions"] == 0 and t["cost"] >= limit and t["status"] != "EXCLUDED":
            alerts.append(_alert("media", "Termos de busca",
                f"\"{t['term']}\" ({t['campaign']}) gastou {_money(t['cost'], data)} sem conversão. "
                "Candidato a palavra-chave negativa."))
    return alerts


def ads(data, cfg):
    return [
        _alert("alta" if a["approval"] == "DISAPPROVED" else "baixa", "Anúncios",
            f"Anúncio {a['ad_id']} em {a['campaign']} › {a['ad_group']} está {a['approval']}.")
        for a in data["disapproved_ads"]
    ]


RULES = [tracking, campaigns, keywords, search_terms, ads]
SEVERITY_ORDER = {"alta": 0, "media": 1, "baixa": 2}


def run_all(data, cfg):
    found = [a for rule in RULES for a in rule(data, cfg)]
    return sorted(found, key=lambda a: SEVERITY_ORDER[a["severity"]])
