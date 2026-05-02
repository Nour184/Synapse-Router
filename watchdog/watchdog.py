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

def recover_request(req_id):
    """Helper function to pull from Redis, requeue, and clean up."""
    payload = redis_client.hget("requests:payloads", req_id)
    if payload:
        try:
            # FIRE AND FORGET: 0.5s timeout. It will send the data to Nginx, 
            # then instantly raise a ReadTimeout so the Watchdog can keep looping.
            requests.post(NGINX_API_URL, data=payload, headers={'Content-Type': 'application/json'}, timeout=0.5)
        except requests.exceptions.ReadTimeout:
            # This is expected behavior. The payload was sent successfully.
            pass
        except Exception as e:
            print(f"Failed to requeue {req_id}: {e}")
        
        # Tell Nginx to stop tracking it, then delete from Redis
        requests.post(NGINX_CONTROL_URL, data={"clear_req": req_id})
        redis_client.hdel("requests:payloads", req_id)
        return True
    return False

def run_watchdog():
    print("Starting Watchdog with Bulk Recovery & 3-Strike Circuit Breaker...")
    
    node_strikes = {}      
    handled_timeouts = set() 

    while True:
        try:
            response = requests.get(NGINX_STATE_URL)
            if response.status_code != 200:
                continue
                
            state_data = response.json()
            active_requests = state_data.get("tracking", {})
            banned_nodes = state_data.get("banned", [])
            current_time = int(time.time())
            
            # MEMORY LEAK FIX: Remove old req_ids that are no longer active in Nginx
            handled_timeouts = {req for req in handled_timeouts if req in active_requests}
            
            # 1. BULK RECOVERY: Instantly evacuate all requests on banned nodes
            for req_id, node_name in list(active_requests.items()):
                if node_name in banned_nodes and req_id not in handled_timeouts:
                    print(f"[BULK RECOVERY] {node_name} is banned! Instantly recovering {req_id}...")
                    if recover_request(req_id):
                        handled_timeouts.add(req_id)
                    del active_requests[req_id]

            # 2. TIMEOUT DETECTION: Check remaining active requests on healthy nodes
            for req_id, node_name in active_requests.items():
                if req_id in handled_timeouts:
                    continue 
                    
                try:
                    req_timestamp = int(req_id.split('-')[1])
                except (IndexError, ValueError):
                    continue

                if (current_time - req_timestamp) > TIMEOUT_SECONDS:
                    print(f"[TIMEOUT] {req_id} stuck on {node_name}!")
                    
                    node_strikes[node_name] = node_strikes.get(node_name, 0) + 1
                    handled_timeouts.add(req_id)
                    
                    # Check for 3 Strikes
                    if node_strikes[node_name] >= 3:
                        print(f"[CIRCUIT BREAKER] {node_name} hit 3 strikes. Banning via API!")
                        requests.post(NGINX_CONTROL_URL, data={"ban_node": node_name})
                        node_strikes[node_name] = 0 
                    
                    print(f"[RECOVERY] Re-queueing {req_id} back to Gateway...")
                    recover_request(req_id)

        except Exception as e:
            print(f"[ERROR] Watchdog issue: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_watchdog()