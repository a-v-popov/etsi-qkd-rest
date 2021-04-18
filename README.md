# Description

This is a Python3 implemenation of a mock server compliant with [ETSI GS QKD 014](https://www.etsi.org/deliver/etsi_gs/QKD/001_099/012/01.01.01_60/gs_QKD012v010101p.pdf).
Other related documents are available on [ETSI QKD ISG web page](https://www.etsi.org/committee/1430-qkd).

The goal is to provide a transparent implmenation of a mock server to facilitate ETSI GS QKD 014 compliant client development.

# Components

## Framework

### Falcon

WSGI Python REST API framework.

[https://falconframework.org/](https://falconframework.org/)


## Server

### Green Unicorn

Gunicorn 'Green Unicorn' is a Python WSGI HTTP Server for UNIX.

[https://gunicorn.org/](https://gunicorn.org/)

TLS cert data can be extrated by a custom worker.

## Data Store

### Redis

Redis is an open source (BSD licensed), in-memory data structure store.

[https://redis.io/](https://redis.io/)

# Installation

## KME module
Install KME for current user as a link to current directory
```bash
pip3 install --user .
```
# Start KME
## Redis
```bash
redis-server
```

to access redis store from shell
```bash
$ redis-cli KEYS '*'
1) "a99ac4d0-d13e-4bdc-b33e-0abb68ef6ec6"
$ redis-cli GET "a99ac4d0-d13e-4bdc-b33e-0abb68ef6ec6"
"{\"key\": \"yUje5o5S0/EfiZIHCceSeg==\", \"acl\": [\"SAE_B\", \"SAE_A\"], \"master\": \"SAE_A\"}"
$ redis-cli FLUSHDB
OK

```

# Green Unicorm
`worker.py` provides custom worker class to extract certificate CN to request header
Change to gunicorn subfolder where you store your `worker.py`.
Create configuration file for gunicorn.

#### `gunicorn_kme-1.conf.py`
```Python
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

bind='127.0.0.1:8001'
```

Create configuration file for KME application

#### `kme-1.conf`
```
[kme]
id = kme-1
redis_host = localhost
```

Run gunicorn for kme-1
```bash
gunicorn -c gunicorn_kme-1.conf.py 'kme.app:load_app("kme-1.conf")'
```

# Mutual Cert Auth

## Assumtion

1. standard TLS authentication, i.e. KME_Hostname must be in subjectAltName and kme_ID is not authenitcated
2. client CN = sae_ID, extracted by CustomWorker and added to request header

## Generate Certs
### CA

```Shell
openssl req -nodes -new -x509 -days 1000 -keyout ca.key -out ca.crt \
	-subj "/CN=QKD Test CA"

openssl x509 -noout -text -in ca.crt
```


### Server/Client

```bash
export DNS=kme-1

# create key and certificate request 
openssl req -nodes -new -keyout $DNS.key -out $DNS.csr \
	-subj "/C=NL/CN=$DNS"

# workaround to add subjectAltName into certificate
echo "subjectAltName = DNS:$DNS" > dns-ext.cnf

# create certificate from request
openssl x509 -req -days 1000 -CAcreateserial \
	-CA ca.crt -CAkey ca.key \
	-extfile dns-ext.cnf \
	-in $DNS.csr -out $DNS.crt

rm dns-ext.cnf

# combine key and cert into a PEM file for clients (or just cat them)
openssl pkcs12 -export -in $DNS.crt -inkey $DNS.key -out $DNS.pfx -passout pass:
openssl pkcs12 -in $DNS.pfx -nodes -out $DNS.pem -passin pass:

# some checks on generated files

# print out certificate request
openssl req -noout -text -in $DNS.csr

# print out certificate
openssl x509 -noout -text -in $DNS.crt

# print out PEM file
openssl x509 -in $DNS.pem -text

# verify certificate
openssl verify -CAfile ca.crt $DNS.pem

```
