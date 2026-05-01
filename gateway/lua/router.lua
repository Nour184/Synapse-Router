--external lua script fpr load balancing and accessing redis

--notice lua tables start with index 1
local worker_nodes = {
    { name = "worker-1", url ="worker:8000"}, --change these when using tailscale
    { name = "worker-2", url = "worker-2:8000"}
}

local req_id = "req-"..tostring(ngx.time()).."-"..math.random(1000,9999) --give a unique id to each req

--inject the requst id in the request sent to the nodes
ngx.req.set_header("x-request-id", req_id)
ngx.req.read_body() --buffer the request body so that it can be read by the lua script and also sent to the worker nodes

local request_body = ngx.req.get_body_data() or "{}"  --get the request body as a string


local state = ngx.shared.router_state --access the 1MB shared memory dictionary defined in nginx.conf to store the state of the router
local curr_count = state:incr("request_counter",1,0) --increment a counter by 1 (starrting by 0) to keep track of the current request number recieved

local worker_node_index = (curr_count % #worker_nodes) + 1 --use modulo to select the worker node index in a round-robin way
local target_node_name = worker_nodes[worker_node_index].name --get the name of the target worker node
local target_node_url = worker_nodes[worker_node_index].url




--save the request to redis 
local redis = require "resty.redis"
local red = redis:new()
red:set_timeout(1500,1000,1500) --1 sec timeout for connect, read, and write

local ok, err = red:connect("redis",6379) --connect to redis server unning on port 6379 in the redis container
if ok then 
    local json_data = '{"request_id":"' .. req_id .. '", "node":"' .. target_node_name .. '", "payload":' .. request_body .. '}' --json envelope to store the request data in redis
    red:hset("requests:"..target_node_name, req_id, json_data) --store the request data in a hash with the key "requests:worker-1" or "requests:worker-2" and the field as the request id
    
    red:set_keepalive(10000, 100) --leave the connection to redis opened to 10secs and allow up to 100 simultaneous connections 
else 
    ngx.log(ngx.ERR,"Failed to connect to Redis: ", err) --log the error if failed but wont stop the request from being processed by the worker nodes
end 

ngx.var.assigned_worker = target_node_url --set the global variable to the chosen worker node url so that it can be used by proxy_pass in nginx.conf
