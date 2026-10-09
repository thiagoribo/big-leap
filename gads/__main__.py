"""Usage:
  python -m gads check     # tests the connection and lists accessible accounts
  python -m gads report    # writes reports/AAAA-MM-DD.md with KPIs and alerts
  python -m gads alerts    # prints only the alerts
"""

import sys
from datetime import date
from pathlib import Path

import yaml

from . import alerts, fetch, report


def check():
    client = fetch.get_client()
    service = client.get_service("CustomerService")
    names = service.list_accessible_customers().resource_names
    print(f"Conexão OK. Contas acessíveis com este login: {len(names)}")
    for n in names:
        print(" ", n.split("/")[-1])
    info = fetch.account_info(client, fetch.customer_id())
    print(f"Conta configurada: {info['name']} ({info['currency']}, {info['time_zone']})")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "check":
        return check()
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    data = fetch.collect()
    found = alerts.run_all(data, cfg)
    if cmd == "alerts":
        for a in found:
            print(f"[{a['severity'].upper()}] {a['area']}: {a['message']}")
        print(f"{len(found)} alerta(s).")
        return
    path = Path("reports") / f"{date.today():%Y-%m-%d}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(report.render(data, found))
    print(f"Relatório salvo em {path} ({len(found)} alerta(s)).")


main()
