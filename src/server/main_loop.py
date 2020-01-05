import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.httpclient import AsyncHTTPClient
from tornado import gen
from tornado.log import enable_pretty_logging

import urllib
from urllib.parse import urlencode
import subprocess
import shlex
import logging
import numpy as np
import sys
import svgwrite
import json

#from falcon_kit import kup, falcon, DWA, get_alignment
#from falcon_kit.FastaReader import FastaReader

from bokeh.plotting import figure, output_file, show
from bokeh.plotting import figure
from bokeh.embed import components


enable_pretty_logging()

rmap = dict(zip("ACGTN","TGCAN"))

GDURL = "http://localhost:6503/GraphData/"
#http_client = tornado.httpclient.HTTPClient()
http_client = AsyncHTTPClient()

async def get_ctg_data(ctg, URL=GDURL):
    post_data = { 'req': 'ctg_path', 'ctg':ctg }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    return json.loads(r.body)

async def get_utg_data(utg_list, URL=GDURL):
    post_data = { 'req': 'utgs', 'ulist':json.dumps(utg_list) }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    return json.loads(r.body)

async def get_ctg_of_node(n, URL=GDURL):
    post_data = { 'req': 'node_to_ctgs', 'nlist':json.dumps([n]) }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    return json.loads(r.body)

async def get_ctg_of_nodes(n, URL=GDURL):
    post_data = { 'req': 'node_to_ctgs', 'nlist':json.dumps(n) }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    return json.loads(r.body)

async def get_ctg_sg(ctg, URL=GDURL):
    post_data = { 'req': 'contig_sg', 'ctg':ctg }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    return json.loads(r.body)

async def get_local_sg(v, layers=10, max_nodes=1800, URL=GDURL):
    post_data = { 'req': 'local_sg', 'v':v, "layers":layers, "max_nodes":max_nodes }
    body = urlencode(post_data)
    r = await http_client.fetch(URL, method='POST', headers=None, body=body)
    rtn = json.loads(r.body)
    return rtn


class ShowLocalSG(tornado.web.RequestHandler):

    """
    # for cross domain requests, add the header
    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', '*')
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
    """

    def post(self):

        v = self.get_argument("v", "NA")
        layers = self.get_argument("layers", 90)
        max_nodes = self.get_argument("max_nodes", 1800)
        print("ShowLocalSG called for node: "+v)
        return self._get_local_sg(v, layers = layers, max_nodes=max_nodes)

    @gen.coroutine
    def _get_local_sg(self, v, layers=60, max_nodes=1800):
        #v = "010913479:E"
        neighbor_ctgs = set()
        g = yield get_local_sg(v, layers=layers, max_nodes=max_nodes)
        all_nodes = g["nodes"]
        all_edges = g["edges"]

        links = []
        node_ctg = {}
        print(len(list(all_nodes)))
        ctg_of_nodes = yield get_ctg_of_nodes( list(all_nodes) )
        for n, ctgs in ctg_of_nodes:
            node_ctg[n] = ctgs
            neighbor_ctgs.update( ctgs )
        #print len(node_ctg)


        ctg = "X"
        nodes = set()
        for s, t in all_edges:
            ctg = set(node_ctg.get(s, set())) & set(node_ctg.get(t, set()))
            if len(ctg) >= 1:
                ctg = ctg.pop()
            else:
                ctg = "X"

            col = "#F44"
            links.append( (s, "x", t, col, ctg) )
            nodes.add(s.split(":")[0])
            nodes.add(t.split(":")[0])

        for n in list(nodes):
            links.append( (n+":B", "x", n+":E", "white", "r") )

        ctg_of_nodes = yield get_ctg_of_nodes( list(all_nodes) )
        for n, ctgs in ctg_of_nodes:
            node_ctg[n] = " / ".join(tuple(ctgs))

        s1 = json.dumps(links)
        s2 = json.dumps(node_ctg)
        s3 = json.dumps(sorted(list(neighbor_ctgs)))
        self.write( json.dumps({"links":links,
                                "node_to_ctg":node_ctg,
                                "ctg_list":sorted(list(neighbor_ctgs)),
                                "center_node": v}) )

        #with open("graph_data.json","w") as f:
        #    print >>f, "var graph_data = {links:%s, node_to_ctg:%s, ctg_list:%s}" % (s1,s2,s3)
        #import os
        #os.system("open show_asm_graph.html")


class PlotSocket(tornado.websocket.WebSocketHandler):
    clients = []
    def open(self):
        PlotSocket.clients.append(self)
        print("Websocket opened")

    def on_message(self, message):
        pass
    #@self.write_message(u"test:%s" % repr(self))

    def on_close(self):
        print("Websocket close")
        PlotSocket.clients.remove(self)

    #def check_origin(self, origin):
    #    return True


class MainHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', '*')
        self.set_header('Access-Control-Max-Age', 1000)
        self.set_header('Content-type', 'application/json')
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.set_header('Access-Control-Allow-Headers',
                                'Content-Type, Access-Control-Allow-Origin, Access-Control-Allow-Headers, X-Requested-By, Access-Control-Allow-Methods')

    def get(self):
        self.write("Hello, world")

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/plotsocket/", PlotSocket),
    (r"/ShowLocalSG/", ShowLocalSG),
    (r"/view/(.*)",tornado.web.StaticFileHandler,  {"path": "../view/"})],
    autoreload=True, debug=True)

if __name__ == "__main__":
    from tornado.options import options
    options.logging = "DEBUG"
    logging.debug("starting torando web server")
    application.listen(6502)
    tornado.ioloop.IOLoop.current().start()
