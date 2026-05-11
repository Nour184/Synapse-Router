#download a lightweght openresty 
FROM openresty/openresty:alpine 

#install iptables so the watchdog can force-close connections
RUN apk add --no-cache iptables

#use the custom nginx.conf file to replace the default one by openresty
COPY nginx.conf /usr/local/openresty/nginx/conf/nginx.conf

COPY ./lua /usr/local/openresty/lua