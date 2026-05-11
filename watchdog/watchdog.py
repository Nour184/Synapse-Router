import os
import requests
import redis
import time

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

NGINX_STATE_URL = "http://gateway:80/watchdog/state"
NGINX_CONTROL_URL = "http://gateway:80/watchdog/control"
NGINX_API_URL = "http://gateway:80/api/"

TIMEOUT_SECONDS = 5 #10 secs longer than nginx timeout 

# Mapping of node names to their specific Tailscale ports
NODE_PORTS = {
    "worker-1": 5000,
    "worker-2": 5001,
    "worker-3": 5002
}

# Manual recover_request is no longer needed! Nginx will natively retry 
# when we force-close the TCP connections using iptables.

def run_watchdog():
    print("Starting Watchdog with Bulk Recovery & Instant Circuit Breaker...")
    
    banned_history = set() 

    while True:
        try:
            response = requests.get(NGINX_STATE_URL)
            if response.status_code != 200:
                continue
                
            state_data = response.json()
            active_requests = state_data.get("tracking", {})
            banned_nodes = state_data.get("banned", [])
            current_time = int(time.time())
            
            # Clean up history for nodes whose ban has expired
            banned_history = {node for node in banned_history if node in banned_nodes}
            
            # 1. BULK RECOVERY VIA TCP KILL
            for node_name in banned_nodes:
                if node_name not in banned_history:
                    print(f"[TCP KILL] {node_name} was banned! Force-closing all active Nginx connections...")
                    
                    port = NODE_PORTS.get(node_name)
                    if port:
                        # Instantly close active connections by dropping packets to the node's specific port
                        os.system(f"docker exec synapse-gateway iptables -A OUTPUT -p tcp --dport {port} -j REJECT --reject-with tcp-reset")
                        # The block is now PERMANENT until the node passes the health check!
                    else:
                        print(f"[ERROR] No port mapping found for {node_name}!")
                    
                    banned_history.add(node_name)

            # 2. TIMEOUT DETECTION: Check remaining active requests on healthy nodes
            for req_id, node_name in active_requests.items():
                if node_name in banned_nodes:
                    continue 
                    
                try:
                    req_timestamp = int(req_id.split('-')[1])
                except (IndexError, ValueError):
                    continue

                if (current_time - req_timestamp) > TIMEOUT_SECONDS:
                    # The request is taking longer than TIMEOUT_SECONDS. Let's actively check if the node is alive!
                    port = NODE_PORTS.get(node_name)
                    if not port:
                        continue
                        
                    health_url = f"http://100.127.81.29:{port}/api/health" # Using the Tailscale IP
                    
                    try:
                        # Ping the health endpoint with a strict 2-second timeout
                        health_resp = requests.get(health_url, timeout=5)
                        
                        if health_resp.status_code == 200:
                            pass 
                        else:
                            raise Exception("Health check returned bad status")
                            
                    except requests.exceptions.RequestException:
                        # Scenario B: Node is DEAD or FROZEN!
                        print(f"[CIRCUIT BREAKER] {node_name} failed health check! Banning instantly!")
                        requests.post(NGINX_CONTROL_URL, data={"ban_node": node_name})

            # 3. PROACTIVE RECOVERY: Ping banned nodes to see if they woke up
            for node_name in banned_nodes:
                port = NODE_PORTS.get(node_name)
                if not port:
                    continue
                
                health_url = f"http://100.127.81.29:{port}/api/health"
                try:
                    resp = requests.get(health_url, timeout=2)
                    if resp.status_code == 200:
                        print(f"[RECOVERY] {node_name} is back online! Unbanning.")
                        
                        # Tell Nginx to unban the node
                        requests.post(NGINX_CONTROL_URL, data={"unban_node": node_name})
                        
                        # Remove the physical iptables block
                        os.system(f"docker exec synapse-gateway iptables -D OUTPUT -p tcp --dport {port} -j REJECT --reject-with tcp-reset")
                        
                        # Remove from history so it can be banned again if it dies
                        if node_name in banned_history:
                            banned_history.remove(node_name)
                            
                except requests.exceptions.RequestException:
                    pass # Node is still dead, keep it banned!

        except Exception as e:
            print(f"[ERROR] Watchdog issue: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    run_watchdog()