from datetime import date

import yaml

from gads import alerts, report

CFG = yaml.safe_load(open("config.yaml"))


def m(cost=0, clicks=0, conv=0, impr=1000, value=0):
    return {"cost": cost, "clicks": clicks, "conversions": conv, "impressions": impr, "conv_value": value}


def base_data(**over):
    data = {
        "customer_id": "123",
        "period": (date(2026, 10, 2), date(2026, 10, 8)),
        "previous_period": (date(2026, 9, 25), date(2026, 10, 1)),
        "account": {"name": "Big Leap", "currency": "BRL", "time_zone": "America/Sao_Paulo", "auto_tagging": True},
        # 28 days, 2 conversions/day, R$100/day -> CPA R$50
        "daily": [{"date": f"2026-09-{d:02d}" if d <= 30 else f"2026-10-{d - 30:02d}", **m(100, 40, 2)} for d in range(11, 39)],
        "campaigns": [{"id": 1, "name": "Search Brand", "status": "ENABLED", "channel": "SEARCH", **m(700, 280, 14)}],
        "campaigns_prev": [{"id": 1, "name": "Search Brand", "status": "ENABLED", "channel": "SEARCH", **m(700, 280, 14)}],
        "impression_share": [],
        "keywords": [],
        "search_terms": [],
        "disapproved_ads": [],
        "conversion_actions": [{"name": "Lead", "status": "ENABLED", "primary": True, "type": "WEBPAGE", "category": "SUBMIT_LEAD_FORM", "all_conversions": 20}],
    }
    data.update(over)
    return data


def areas(found):
    return [(a["severity"], a["area"]) for a in found]


def test_healthy_account_has_no_alerts():
    assert alerts.run_all(base_data(), CFG) == []


def test_tracking_break_detected():
    data = base_data()
    for d in data["daily"][-2:]:
        d["conversions"] = 0
    assert ("alta", "Tracking") in areas(alerts.run_all(data, CFG))


def test_auto_tagging_off():
    data = base_data()
    data["account"]["auto_tagging"] = False
    assert "Auto-tagging" in alerts.run_all(data, CFG)[0]["message"]


def test_primary_conversion_action_silent():
    data = base_data()
    data["conversion_actions"][0]["all_conversions"] = 0
    assert ("media", "Tracking") in areas(alerts.run_all(data, CFG))


def test_expensive_keyword_without_conversions():
    kw = {"campaign": "Search Brand", "ad_group": "AG", "keyword": "curso gratis", "match_type": "BROAD", "status": "ENABLED", "quality_score": 7, **m(120, 30, 0)}
    found = alerts.run_all(base_data(keywords=[kw]), CFG)
    assert areas(found) == [("alta", "Palavras-chave")]


def test_keyword_high_cpa_and_low_qs():
    kw = {"campaign": "C", "ad_group": "AG", "keyword": "x", "match_type": "PHRASE", "status": "ENABLED", "quality_score": 3, **m(300, 30, 2)}
    found = alerts.run_all(base_data(keywords=[kw]), CFG)
    assert sorted(areas(found)) == [("baixa", "Palavras-chave"), ("media", "Palavras-chave")]


def test_cheap_keyword_ignored():
    kw = {"campaign": "C", "ad_group": "AG", "keyword": "x", "match_type": "EXACT", "status": "ENABLED", "quality_score": None, **m(20, 5, 0)}
    assert alerts.run_all(base_data(keywords=[kw]), CFG) == []


def test_negative_keyword_candidate():
    st = {"campaign": "C", "ad_group": "AG", "term": "vagas emprego", "status": "NONE", **m(60, 20, 0)}
    assert areas(alerts.run_all(base_data(search_terms=[st]), CFG)) == [("media", "Termos de busca")]


def test_week_over_week_drop_and_budget():
    data = base_data()
    data["campaigns"][0].update(conversions=6)
    data["impression_share"] = [{"id": 1, "name": "Search Brand", "impression_share": 0.5, "lost_budget": 0.35, "lost_rank": 0.15}]
    found = areas(alerts.run_all(data, CFG))
    assert ("alta", "Performance") in found and ("media", "Performance") in found and ("media", "Orçamento") in found


def test_disapproved_ad():
    ad = {"campaign": "C", "ad_group": "AG", "ad_id": 9, "approval": "DISAPPROVED"}
    assert areas(alerts.run_all(base_data(disapproved_ads=[ad]), CFG)) == [("alta", "Anúncios")]


def test_report_renders():
    data = base_data()
    md = report.render(data, alerts.run_all(data, CFG))
    assert "Relatório semanal" in md and "Search Brand" in md and "BRL 700.00" in md
