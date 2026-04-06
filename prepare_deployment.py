import os
import secrets
import string
import sys
from ruamel.yaml import YAML
from dotenv import load_dotenv, set_key

# Target Services with weights
# Medium: 2GB
# Light: 512MB
TARGET_SERVICES = {
    'adguardhome': 'light',
    'tailscale-exit-node': 'light',
    'qbittorrent': 'medium',
    'prowlarr': 'light',
    'radarr': 'medium',
    'sonarr': 'medium',
    'metube': 'light',
    'configarr': 'light',
    'actual-budget': 'light',
    'clipcascade': 'light',
    'karakeep': 'light',
    'linkding': 'light',
    'stirlingpdf': 'medium',
    'vaultwarden': 'light',
    'wallos': 'light',
    'glance': 'light',
    'changedetection': 'light',
    'coder': 'light',
    'it-tools': 'light',
    'searxng': 'light',
    'portainer': 'light',
    'uptime-kuma': 'light',
    'ntfy': 'light',
    'homebox': 'light',
    'mealie': 'light'
}

LIMITS = {
    'light': '512M',
    'medium': '2G'
}

RESERVATIONS = {
    'light': '256M',
    'medium': '1G'
}

USED_PORTS = {8080, 6443, 6444, 10010, 9100, 10250, 10257, 10256, 10259, 10258, 10249, 10248}

def generate_password(length=16):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_next_available_port(start_port):
    port = start_port
    while port in USED_PORTS:
        port += 1
    USED_PORTS.add(port)
    return port

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

def process_service(service_name, weight, base_path):
    service_dir = os.path.join(base_path, 'services', service_name)
    if not os.path.isdir(service_dir):
        print(f"Service directory {service_dir} not found. Skipping.")
        return

    print(f"Processing service: {service_name} ({weight})")

    env_path = os.path.join(service_dir, '.env')
    template_path = os.path.join(service_dir, '.env.template')

    if not os.path.exists(env_path) and os.path.exists(template_path):
        import shutil
        shutil.copy(template_path, env_path)

    if os.path.exists(env_path):
        # Read current port if it exists
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        current_port = 0
        for line in lines:
            if line.startswith('SERVICEPORT='):
                try:
                    current_port = int(line.split('=')[1].strip())
                except:
                    pass
        
        if current_port == 0:
             # Default from the list provided if missing
             current_port = 8000
        
        new_port = get_next_available_port(current_port)
        if new_port != current_port:
            print(f"  Updating port from {current_port} to {new_port}")
            set_key(env_path, 'SERVICEPORT', str(new_port))

    # Process compose.yaml
    compose_path = os.path.join(service_dir, 'compose.yaml')
    if os.path.exists(compose_path):
        with open(compose_path, 'r') as f:
            data = yaml.load(f)

        if 'services' in data:
            for s_key, s_val in data['services'].items():
                # Inject resource limits
                if 'deploy' not in s_val:
                    s_val['deploy'] = {}
                if 'resources' not in s_val['deploy']:
                    s_val['deploy']['resources'] = {}
                
                s_val['deploy']['resources']['limits'] = {'memory': LIMITS[weight]}
                s_val['deploy']['resources']['reservations'] = {'memory': RESERVATIONS[weight]}

                # Check for DB isolation
                # If image is postgres or redis, ensure no host port mapping unless strictly necessary
                image = s_val.get('image', '')
                if 'postgres' in image or 'redis' in image:
                    if 'ports' in s_val:
                        print(f"  Warning: Internal DB {s_key} has host ports mapped. Removing to ensure isolation.")
                        del s_val['ports']
                    
                    # Ensure unique container name if it's not using variables
                    alias = f"{service_name}-{s_key}"
                    s_val['container_name'] = alias

                # Fix hardcoded port 53 (common in adguardhome/pihole)
                if 'ports' in s_val:
                    new_ports = []
                    for port_mapping in s_val['ports']:
                        if isinstance(port_mapping, str):
                            if port_mapping.startswith('0.0.0.0:53:') or port_mapping.startswith('53:'):
                                updated = port_mapping.replace(':53:', ':5353:').replace(':53/', ':5353/')
                                print(f"  Updating hardcoded port 53 to 5353 in {s_key}")
                                new_ports.append(updated)
                            else:
                                new_ports.append(port_mapping)
                        else:
                            new_ports.append(port_mapping)
                    s_val['ports'] = new_ports

        with open(compose_path, 'w') as f:
            yaml.dump(data, f)

def main():
    base_path = 'scaletail'
    for service, weight in TARGET_SERVICES.items():
        process_service(service, weight, base_path)

if __name__ == "__main__":
    main()
