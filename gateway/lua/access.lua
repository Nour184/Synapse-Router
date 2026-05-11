-- intercept the request before load balancing it to give it a unique ID
local req_id = "req-"..tostring(ngx.time()).."-"..math.random(1000,9999)

-- inject the request id in the request sent to the nodes
ngx.req.set_header("x-request-id", req_id)
ngx.ctx.req_id = req_id

-- We no longer save the request body to Redis here! 
-- Nginx handles retries natively via proxy_next_upstream by buffering the request in memory.
