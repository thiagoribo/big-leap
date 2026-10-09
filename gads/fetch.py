"""Google Ads API access. Every function returns plain dicts so the analysis
layer can be tested without credentials."""

import os
from datetime import date, timedelta

from google.ads.googleads.client import GoogleAdsClient


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def get_client():
    load_dotenv()
    if not os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
        os.environ.pop("GOOGLE_ADS_LOGIN_CUSTOMER_ID", None)
    os.environ.setdefault("GOOGLE_ADS_USE_PROTO_PLUS", "True")
    return GoogleAdsClient.load_from_env()


def customer_id():
    load_dotenv()
    return os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")


def week_ranges(today=None):
    """Last 7 complete days and the 7 days before them."""
    today = today or date.today()
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return (start, end), (prev_start, prev_end)


def _between(start, end):
    return f"segments.date BETWEEN '{start:%Y-%m-%d}' AND '{end:%Y-%m-%d}'"


def _query(client, cid, gaql):
    service = client.get_service("GoogleAdsService")
    for batch in service.search_stream(customer_id=cid, query=gaql):
        yield from batch.results


def _metrics(m):
    return {
        "cost": m.cost_micros / 1e6,
        "impressions": m.impressions,
        "clicks": m.clicks,
        "conversions": m.conversions,
        "conv_value": m.conversions_value,
    }


METRICS = (
    "metrics.cost_micros, metrics.impressions, metrics.clicks, "
    "metrics.conversions, metrics.conversions_value"
)


def account_info(client, cid):
    q = (
        "SELECT customer.descriptive_name, customer.currency_code, "
        "customer.time_zone, customer.auto_tagging_enabled FROM customer"
    )
    for r in _query(client, cid, q):
        c = r.customer
        return {
            "name": c.descriptive_name,
            "currency": c.currency_code,
            "time_zone": c.time_zone,
            "auto_tagging": c.auto_tagging_enabled,
        }


def daily(client, cid, start, end):
    q = f"SELECT segments.date, {METRICS} FROM customer WHERE {_between(start, end)}"
    return [
        {"date": r.segments.date, **_metrics(r.metrics)}
        for r in _query(client, cid, q)
    ]


def campaigns(client, cid, start, end):
    q = (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type, campaign.bidding_strategy_type, "
        f"campaign_budget.amount_micros, {METRICS} "
        f"FROM campaign WHERE {_between(start, end)} AND campaign.status != 'REMOVED'"
    )
    return [
        {
            "id": r.campaign.id,
            "name": r.campaign.name,
            "status": r.campaign.status.name,
            "channel": r.campaign.advertising_channel_type.name,
            "bidding": r.campaign.bidding_strategy_type.name,
            "daily_budget": r.campaign_budget.amount_micros / 1e6,
            **_metrics(r.metrics),
        }
        for r in _query(client, cid, q)
    ]


def search_impression_share(client, cid, start, end):
    q = (
        "SELECT campaign.id, campaign.name, metrics.search_impression_share, "
        "metrics.search_budget_lost_impression_share, "
        "metrics.search_rank_lost_impression_share "
        f"FROM campaign WHERE {_between(start, end)} "
        "AND campaign.status = 'ENABLED' "
        "AND campaign.advertising_channel_type = 'SEARCH'"
    )
    return [
        {
            "id": r.campaign.id,
            "name": r.campaign.name,
            "impression_share": r.metrics.search_impression_share,
            "lost_budget": r.metrics.search_budget_lost_impression_share,
            "lost_rank": r.metrics.search_rank_lost_impression_share,
        }
        for r in _query(client, cid, q)
    ]


def keywords(client, cid, start, end):
    q = (
        "SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
        f"ad_group_criterion.quality_info.quality_score, {METRICS} "
        f"FROM keyword_view WHERE {_between(start, end)} AND metrics.cost_micros > 0"
    )
    return [
        {
            "campaign": r.campaign.name,
            "ad_group": r.ad_group.name,
            "keyword": r.ad_group_criterion.keyword.text,
            "match_type": r.ad_group_criterion.keyword.match_type.name,
            "status": r.ad_group_criterion.status.name,
            "quality_score": r.ad_group_criterion.quality_info.quality_score or None,
            **_metrics(r.metrics),
        }
        for r in _query(client, cid, q)
    ]


def search_terms(client, cid, start, end):
    q = (
        "SELECT campaign.name, ad_group.name, search_term_view.search_term, "
        f"search_term_view.status, {METRICS} "
        f"FROM search_term_view WHERE {_between(start, end)} AND metrics.cost_micros > 0"
    )
    return [
        {
            "campaign": r.campaign.name,
            "ad_group": r.ad_group.name,
            "term": r.search_term_view.search_term,
            "status": r.search_term_view.status.name,
            **_metrics(r.metrics),
        }
        for r in _query(client, cid, q)
    ]


def disapproved_ads(client, cid):
    q = (
        "SELECT campaign.name, ad_group.name, ad_group_ad.ad.id, "
        "ad_group_ad.policy_summary.approval_status "
        "FROM ad_group_ad WHERE ad_group_ad.status = 'ENABLED' "
        "AND ad_group.status = 'ENABLED' AND campaign.status = 'ENABLED' "
        "AND ad_group_ad.policy_summary.approval_status IN ('DISAPPROVED', 'APPROVED_LIMITED')"
    )
    return [
        {
            "campaign": r.campaign.name,
            "ad_group": r.ad_group.name,
            "ad_id": r.ad_group_ad.ad.id,
            "approval": r.ad_group_ad.policy_summary.approval_status.name,
        }
        for r in _query(client, cid, q)
    ]


def conversion_actions(client, cid, start, end):
    actions = {}
    q = (
        "SELECT conversion_action.resource_name, conversion_action.name, "
        "conversion_action.status, conversion_action.primary_for_goal, "
        "conversion_action.type, conversion_action.category FROM conversion_action "
        "WHERE conversion_action.status != 'REMOVED'"
    )
    for r in _query(client, cid, q):
        a = r.conversion_action
        actions[a.resource_name] = {
            "name": a.name,
            "status": a.status.name,
            "primary": a.primary_for_goal,
            "type": a.type_.name,
            "category": a.category.name,
            "all_conversions": 0.0,
        }
    q = (
        "SELECT segments.conversion_action, metrics.all_conversions "
        f"FROM campaign WHERE {_between(start, end)}"
    )
    for r in _query(client, cid, q):
        a = actions.get(r.segments.conversion_action)
        if a:
            a["all_conversions"] += r.metrics.all_conversions
    return list(actions.values())


def collect(today=None):
    """Pull everything the report and alerts need."""
    client = get_client()
    cid = customer_id()
    (start, end), (pstart, pend) = week_ranges(today)
    baseline_start = end - timedelta(days=27)
    return {
        "customer_id": cid,
        "period": (start, end),
        "previous_period": (pstart, pend),
        "account": account_info(client, cid),
        "daily": daily(client, cid, baseline_start, end),
        "campaigns": campaigns(client, cid, start, end),
        "campaigns_prev": campaigns(client, cid, pstart, pend),
        "impression_share": search_impression_share(client, cid, start, end),
        "keywords": keywords(client, cid, start, end),
        "search_terms": search_terms(client, cid, start, end),
        "disapproved_ads": disapproved_ads(client, cid),
        "conversion_actions": conversion_actions(client, cid, end - timedelta(days=13), end),
    }
