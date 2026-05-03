--intercept the request before load balancing it and save it to a generic hash in redis 
local req_id = "req-"..tostring(ngx.time()).."-"..math.random(1000,9999) --give a unique id to each req
--inject the requst id in the request sent to the nodes
ngx.req.set_header("x-request-id", req_id)
ngx.ctx.req_id = req_id

ngx.req.read_body() --buffer the request body as a string 
local request_body = ngx.req.get_body_data() or "{}"  --get the request body as a string

--save the request to redis without knowing the worker node its assigned to yet..will be set by the watchdog script 
local redis = require "resty.redis"
local red = redis:new()
red:set_timeout(1500,1000,1500) --1 sec timeout for connect, read, and write
local ok, error = red:connect("redis",6379) --connect to redis server running on port 6379 in the redis container
if ok then 
    red:hset("requests:payloads", req_id, request_body) --store the request body in a generic hash so that the watchdog script can access it and assign it to the correct worker node 
    red:set_keepalive(10000,100) --leave the connection to redis opened to 10secs and allow up to 100 simultaneous connections
else 
    ngx.log(ngx.ERR, "Failed to connect to Redis:", error) --log the error if failed but wont stop the request from being processed by the worker nodes
end
