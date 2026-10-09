"""Weekly report rendered as Markdown (PT-BR)."""

from . import alerts as al

ICON = {"alta": "🔴", "media": "🟠", "baixa": "🟡"}


def _pct_change(cur, prev):
    if not prev:
        return "—"
    return f"{(cur / prev - 1):+.0%}"


def _kpis(t):
    return {
        "Investimento": t["cost"],
        "Impressões": t["impressions"],
        "Cliques": t["clicks"],
        "CTR": t["clicks"] / t["impressions"] if t["impressions"] else 0,
        "CPC médio": t["cost"] / t["clicks"] if t["clicks"] else 0,
        "Conversões": t["conversions"],
        "CPA": al.cpa(t) or 0,
        "Valor de conversão": t["conv_value"],
        "ROAS": t["conv_value"] / t["cost"] if t["cost"] else 0,
    }


def _fmt(name, value, cur):
    if name in ("Investimento", "CPC médio", "CPA", "Valor de conversão"):
        return f"{cur} {value:,.2f}"
    if name == "CTR":
        return f"{value:.2%}"
    if name == "ROAS":
        return f"{value:.2f}x"
    if name == "Conversões":
        return f"{value:,.1f}"
    return f"{value:,.0f}"


def render(data, found):
    cur = data["account"]["currency"]
    (start, end), (pstart, pend) = data["period"], data["previous_period"]
    now = _kpis(al.totals(data["campaigns"]))
    before = _kpis(al.totals(data["campaigns_prev"]))

    out = [
        f"# Relatório semanal Google Ads: {data['account']['name']}",
        "",
        f"Período: **{start:%d/%m} a {end:%d/%m/%Y}** · comparado com {pstart:%d/%m} a {pend:%d/%m}",
        "",
        "## Resumo da semana",
        "",
        "| Métrica | Semana | Semana anterior | Variação |",
        "|---|---:|---:|---:|",
    ]
    for k in now:
        out.append(f"| {k} | {_fmt(k, now[k], cur)} | {_fmt(k, before[k], cur)} | {_pct_change(now[k], before[k])} |")

    out += ["", f"## Alertas ({len(found)})", ""]
    if not found:
        out.append("Nenhum problema encontrado com os limites atuais.")
    for a in found:
        out.append(f"- {ICON[a['severity']]} **{a['area']}**: {a['message']}")

    out += ["", "## Campanhas", "",
            "| Campanha | Tipo | Investimento | Cliques | Conv. | CPA | Δ Conv. |",
            "|---|---|---:|---:|---:|---:|---:|"]
    prev = {p["id"]: p for p in data["campaigns_prev"]}
    for c in sorted(data["campaigns"], key=lambda c: -c["cost"]):
        if not c["cost"] and not (prev.get(c["id"]) or {}).get("cost"):
            continue
        p = prev.get(c["id"], {"conversions": 0})
        c_cpa = al.cpa(c)
        out.append(
            f"| {c['name']} | {c['channel']} | {cur} {c['cost']:,.2f} | {c['clicks']:,} | "
            f"{c['conversions']:,.1f} | {f'{cur} {c_cpa:,.2f}' if c_cpa else '—'} | "
            f"{_pct_change(c['conversions'], p['conversions'])} |"
        )

    days = sorted(data["daily"], key=lambda d: d["date"])[-7:]
    out += ["", "## Dia a dia", "", "| Dia | Investimento | Cliques | Conversões |", "|---|---:|---:|---:|"]
    for d in days:
        out.append(f"| {d['date']} | {cur} {d['cost']:,.2f} | {d['clicks']:,} | {d['conversions']:,.1f} |")

    top = sorted((k for k in data["keywords"] if k["conversions"]), key=lambda k: -k["conversions"])[:10]
    if top:
        out += ["", "## Top palavras-chave por conversão", "",
                "| Palavra-chave | Campanha | Investimento | Conv. | CPA |", "|---|---|---:|---:|---:|"]
        for k in top:
            out.append(f"| {k['keyword']} [{k['match_type']}] | {k['campaign']} | "
                       f"{cur} {k['cost']:,.2f} | {k['conversions']:,.1f} | {cur} {al.cpa(k):,.2f} |")

    return "\n".join(out) + "\n"
