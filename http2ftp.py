import html
import http.server
import io
import shutil
import socketserver
import urllib
from ftplib import FTP
from functools import partial
from http import HTTPStatus


class FTPClient:
    def __init__(self, host, user, password):
        self.ftp = FTP(host)
        self.ftp.login(user, password)

    def download(self, remote_file, local_file):
        with open(local_file, 'wb') as f:
            self.ftp.retrbinary('RETR ' + remote_file, f.write)

    def upload(self, local_file, remote_file):
        with open(local_file, 'rb') as f:
            self.ftp.storbinary('STOR ' + remote_file, f)

    def close(self):
        self.ftp.quit()

class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, ftp_host=None, ftp_port=21, **kwargs):
        if ftp_host is None:
            ftp_host = '127.0.0.1'
        self.ftp_host = ftp_host
        self.ftp_port = ftp_port
        self.ftp = FTP()
        super().__init__(*args, **kwargs)

    def connect(self):
        self.ftp.connect(self.ftp_host, self.ftp_port, timeout=5)
        self.ftp.login()

    def do_GET(self):
        try:
            self.ftp.dir()
        except (ConnectionResetError , AttributeError) as ex:
            try:
                self.connect()
            except TimeoutError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                                'FTP connection timeout')
                return None
        if self.path.endswith('/'):
            f = self.list_directory(self.path)
            if f:
                try:
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()
        else:
            self.down_file(self.path)
        
    def down_file(self, path):
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "application/octet-stream")
            self.end_headers()
            self.ftp.retrbinary('RETR ' + path, self.wfile.write)
        except Exception as ex:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, ex.args)
            return None

    def list_directory(self, path):
        try:
            file_list = list(self.ftp.mlsd(self.path))
        except Exception as ex:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, ex.args)
            return None
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path,
                                               errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        title = 'Directory listing for %s' % displaypath
        r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                 '"http://www.w3.org/TR/html4/strict.dtd">')
        r.append('<html>\n<head>')
        r.append('<meta http-equiv="Content-Type" '
                 'content="text/html; charset=%s">' % 'utf-8')
        r.append('<title>%s</title>\n</head>' % title)
        r.append('<body>\n<h1>%s</h1>' % title)
        r.append('<hr>\n<ul>')
        for one in [x for x in file_list if x[1]['type'] != 'cdir']:
            name = one[0]
            property = one[1]
            displayname = linkname = name
            if property['type'] == 'dir':
                displayname = name + "/"
                linkname = name + "/"
            r.append('<li><a href="%s">%s</a></li>'
                    % (urllib.parse.quote(linkname,
                                          errors='surrogatepass'),
                       html.escape(displayname, quote=False)))
        r.append('</ul>\n<hr>\n</body>\n</html>\n')
        encoded = '\n'.join(r).encode('utf-8', 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % 'utf-8')
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        shutil.copyfileobj(source, outputfile)

        
        
if __name__ == '__main__':
    handler = partial(HTTPRequestHandler, ftp_host='192.168.88.220', ftp_port=5000)
    with socketserver.TCPServer(("", 8000),  handler) as httpd:
        httpd.serve_forever()
