import json
import os
import sys

# Configuration
DOCS_ROOT = "living-docs/docs"
SERVICES_DIR = f"{DOCS_ROOT}/services"
HOSTS_DIR = f"{DOCS_ROOT}/infrastructure/hosts"
MAPS_DIR = f"{DOCS_ROOT}/infrastructure/network-map"
STATE_DIR = f"{DOCS_ROOT}/operational-state"
ARCHIVE_DIR = f"{DOCS_ROOT}/archive"

def generate_service_page(service):
    name = service['name']
    filename = f"{name}.md"
    human_filename = f"{name}.human.md"
    
    content = f"# {name}\n\n"
    content += f"**Status**: {'🔴 Critical' if service.get('critical') else '🟢 Standard'}\n"
    content += f"**Host**: `{service.get('host')}`\n"
    content += f"**Type**: {service.get('service_type')}\n"
    content += f"**Last Seen**: {service.get('last_seen')}\n\n"
    
    content += "## Dependencies\n"
    deps = service.get('dependencies', [])
    if deps:
        for dep in deps:
            content += f"- [{dep}](./{dep}.md)\n"
    else:
        content += "No dependencies registered.\n"
    
    content += "\n## Baseline Behavior\n"
    baseline = service.get('baseline_behavior', {})
    if baseline:
        content += f"```json\n{json.dumps(baseline, indent=2)}\n```\n"
    else:
        content += "No baseline behavior defined.\n"

    human_path = os.path.join(SERVICES_DIR, human_filename)
    if os.path.exists(human_path):
        with open(human_path, 'r') as f:
            content += "\n---\n## Human Notes\n" + f.read()

    with open(os.path.join(SERVICES_DIR, filename), 'w') as f:
        f.write(content)

def generate_host_inventory(services_data):
    hosts = {}
    for s in services_data:
        h = s['host']
        if h not in hosts:
            hosts[h] = []
        hosts[h].append(s['name'])
    
    content = "# Infrastructure Hosts\n\n"
    content += "Automated inventory of all hosts and their resident services.\n\n"
    
    for host in sorted(hosts.keys()):
        content += f"## {host}\n"
        content += "Services:\n"
        for s_name in sorted(hosts[host]):
            content += f"- {s_name}\n"
        content += "\n"
    
    os.makedirs(HOSTS_DIR, exist_ok=True)
    with open(os.path.join(HOSTS_DIR, "index.md"), 'w') as f:
        f.write(content)

def generate_network_maps(services_data):
    domains = {
        "AI Stack": ["inference"],
        "Core Stack": ["proxy", "database", "utility", "secrets"],
        "HomeAuto": ["home_automation", "iot_gateway"]
    }
    
    os.makedirs(MAPS_DIR, exist_ok=True)
    
    for domain, types in domains.items():
        filename = f"{domain.lower().replace(' ', '_')}.md"
        content = f"# {domain} Network Map\n\n"
        content += "```mermaid\ngraph TD\n"
        
        domain_services = [s for s in services_data if s.get('service_type') in types]
        
        for s in domain_services:
            name = s['name']
            deps = s.get('dependencies', [])
            for dep in deps:
                content += f"    {dep} --> {name}\n"
        
        content += "```\n"
        with open(os.path.join(MAPS_DIR, filename), 'w') as f:
            f.write(content)

def generate_operational_state(incidents, changes):
    os.makedirs(STATE_DIR, exist_ok=True)
    
    content = "# Operational State\n\n"
    content += "This page is a live reflection of current infrastructure health and activity.\n\n"
    
    content += "## 🚨 Active Incidents\n"
    if incidents:
        content += "| ID | Target | Severity | Title |\n"
        content += "|---|---|---|---|\n"
        for inc in incidents:
            content += f"| {inc['id']} | {inc['target']} | {inc['severity']} | {inc['title']} |\n"
    else:
        content += "No active incidents. All systems nominal.\n"
    
    content += "\n## 🛠️ Active Change Windows\n"
    if changes:
        content += "| ID | Targets | Description |\n"
        content += "|---|---|---|\n"
        for chg in changes:
            targets = ", ".join(chg.get('targets', [])) if isinstance(chg.get('targets'), list) else chg.get('targets', 'N/A')
            content += f"| {chg['id']} | {targets} | {chg['description']} |\n"
    else:
        content += "No active change windows.\n"
    
    with open(os.path.join(STATE_DIR, "index.md"), 'w') as f:
        f.write(content)

def sync(services_data, incidents_data=None, changes_data=None):
    print(f"Syncing {len(services_data)} services...")
    
    # 1. Generate service pages
    current_service_names = []
    for service in services_data:
        generate_service_page(service)
        current_service_names.append(service['name'])
    
    # 2. Generate Host Inventory
    generate_host_inventory(services_data)
    
    # 3. Generate Network Maps
    generate_network_maps(services_data)
    
    # 4. Generate Operational State
    generate_operational_state(incidents_data or [], changes_data or [])
    
    # 5. Purge Logic
    if os.path.exists(SERVICES_DIR):
        existing_files = [f for f in os.listdir(SERVICES_DIR) if f.endswith('.md') and not f.endswith('.human.md')]
        existing_names = [f.replace('.md', '') for f in existing_files]
        to_purge = [name for name in existing_names if name not in current_service_names]
        
        if len(to_purge) > 0:
            purge_percent = (len(to_purge) / len(existing_names)) * 100 if existing_names else 0
            if purge_percent > 10:
                print(f"CRITICAL: Safety Valve triggered! {purge_percent:.1f}% of services missing. Aborting purge.")
            else:
                print(f"Purging {len(to_purge)} decommissioned services...")
                os.makedirs(ARCHIVE_DIR, exist_ok=True)
                for name in to_purge:
                    os.rename(os.path.join(SERVICES_DIR, f"{name}.md"), os.path.join(ARCHIVE_DIR, f"{name}.md"))

if __name__ == "__main__":
    # The script now expects 3 JSON arguments: services, incidents, changes
    if len(sys.argv) > 1:
        try:
            services = json.loads(sys.argv[1])
            incidents = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
            changes = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
            sync(services, incidents, changes)
        except Exception as e:
            print(f"Error during sync: {e}")
    else:
        print("No data provided")
