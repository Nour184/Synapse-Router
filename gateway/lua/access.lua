-- intercept the request before load balancing it to give it a unique ID
local req_id = "req-"..tostring(ngx.time()).."-"..math.random(1000,9999)

-- inject the request id in the request sent to the nodes
ngx.req.set_header("x-request-id", req_id)
ngx.ctx.req_id = req_id

local state = ngx.shared.router_state
state:incr("total_requests_sent", 1, 0)

if not state:get("start_time") then
    state:set("start_time", ngx.now())
end