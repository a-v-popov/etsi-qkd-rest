# Server certificate and key
certfile = "../certs/kme-1.crt"
keyfile = "../certs/kme-1.key"
# CA cert for mutual TLS auth
ca_certs = "../certs/ca.crt"
# require client cert verification against CA cert
cert_reqs = 2
do_handshake_on_connect = True
# CN to header transfer
worker_class = "worker.CustomWorker"

#monitor app for changes
reload = True

#accesslog = "access.log"

bind='127.0.0.1:8001'
#workers: 1
#timeout: 30
