from gunicorn.workers.sync import SyncWorker

class CustomWorker(SyncWorker):
    def handle_request(self, listener, req, client, addr):
        subject = client.getpeercert().get('subject')

        for ((key,value),) in subject:
            if key == "commonName":
                cn = value
                break

        headers = dict(req.headers)
        headers['X-CERT-CN'] = cn
        req.headers = list(headers.items())

        super(CustomWorker, self).handle_request(listener, req, client, addr)

