local balancer = require "ngx.balancer"
local state = ngx.shared.router_state

local worker_nodes = {  
    { name = "worker-1", ip = "100.127.81.29", port = 5000 }, 
    { name = "worker-2", ip = "100.127.81.29", port = 5001 },
    { name = "worker-3", ip = "100.127.81.29", port = 5002 }
}

-- --just for testing on my machine now
-- local worker_nodes = {  
--     { name = "local-worker-1", ip = "172.19.208.1", port = 5000 }, 
--     { name = "local-worker-2", ip = "172.19.208.1", port = 5001 },
--     { name = "local-worker-3", ip = "172.19.208.1", port = 5002 }
-- }

local req_id = ngx.req.get_headers()["x-request-id"]

if not ngx.ctx.tries_set then
    -- change  this number for when i knwo how many nodes we are gonna have 
    balancer.set_more_tries(2) 
    ngx.ctx.tries_set = true
end

-- 1. IF THIS IS A RETRY: Ban the node that just dropped the connection
local state_name = balancer.get_last_failure()
if state_name and state_name ~= "" and ngx.ctx.last_node then
    ngx.log(ngx.ERR, "Upstream failure (" .. state_name .. ") on " .. ngx.ctx.last_node .. ". Banning for 5 mins.")
    state:set("banned_" .. ngx.ctx.last_node, true, 30) --ban for 30secs instead of 5 mins
end

-- 2. FILTER OUT BANNED NODES
local healthy_nodes = {}
for _, node in ipairs(worker_nodes) do
    if not state:get("banned_" .. node.name) then
        table.insert(healthy_nodes, node)
    end
end

-- If all nodes are dead, return a 502 error immediately
if #healthy_nodes == 0 then
    ngx.log(ngx.ERR, "FATAL: All worker nodes are currently banned or dead!")
    return ngx.exit(502)
end

-- 3. LOAD BALANCE ONLY AMONG HEALTHY NODES
local current_count = state:incr("request_counter", 1, 0) 
local worker_index = (current_count % #healthy_nodes) + 1
local chosen_worker = healthy_nodes[worker_index]

-- Save the chosen node to Nginx context so we know who to ban if the connection fails
ngx.ctx.last_node = chosen_worker.name

if req_id then 
    state:set("tracking_" .. req_id, chosen_worker.name, 300) 
end

local ok, error = balancer.set_current_peer(chosen_worker.ip, chosen_worker.port) 
if not ok then
    ngx.log(ngx.ERR, "Failed to set the current peer:", error) 
end