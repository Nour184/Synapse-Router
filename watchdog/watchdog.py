import os
import requests
import redis
import time

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

NGINX_STATE_URL = "http://gateway:80/watchdog/state"
NGINX_CONTROL_URL = "http://gateway:80/watchdog/control"
NGINX_API_URL = "http://gateway:80/api/"

TIMEOUT_SECONDS = 310 #10 secs longer than nginx timeout 

# Mapping of node names to their specific Tailscale ports
NODE_PORTS = {
    "worker-1": 5000,
    "worker-2": 5001,
    "worker-3": 5002
}

# Manual recover_request is no longer needed! Nginx will natively retry 
# when we force-close the TCP connections using iptables.

def run_watchdog():
    print("Starting Watchdog with Bulk Recovery & 3-Strike Circuit Breaker...")
    
    node_strikes = {}      
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
                        
                        # KEEP the block active for 35 seconds! (Longer than Nginx's 30s timeout)
                        # This guarantees any delayed response from the node is blocked.
                        os.system(f"(sleep 35 && docker exec synapse-gateway iptables -D OUTPUT -p tcp --dport {port} -j REJECT --reject-with tcp-reset) &")
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
                    print(f"[TIMEOUT] {req_id} stuck on {node_name}!")
                    
                    node_strikes[node_name] = node_strikes.get(node_name, 0) + 1
                    
                    # Check for 3 Strikes
                    if node_strikes[node_name] >= 3:
                        print(f"[CIRCUIT BREAKER] {node_name} hit 3 strikes. Banning via API!")
                        # This tells Nginx to ban the node. On the NEXT loop iteration (1 sec later),
                        # the TCP KILL block above will catch it and execute the iptables rule!
                        requests.post(NGINX_CONTROL_URL, data={"ban_node": node_name})
                        node_strikes[node_name] = 0 

        except Exception as e:
            print(f"[ERROR] Watchdog issue: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    run_watchdog()