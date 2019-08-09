import http.client, urllib
import json

import bson
from bson.codec_options import CodecOptions
import collections  # From Python standard library.
from collections import OrderedDict


fmt = "bson"  # or json or "json; boundary=LF"
urlloc = "localhost:7778"
#urlloc = "moschetti.org:7779"

headers = {"Accept" : "application/" + fmt}

conn = http.client.HTTPConnection(urlloc)

params = None

conn.request("GET", "/func1", params, headers)
response = conn.getresponse()
#print response.status, response.reason

data = response.read()

if fmt == "json":
    doc = json.loads(data)
    print(doc)

elif fmt == "bson":
    options = CodecOptions(document_class=collections.OrderedDict)
    for doc in bson.decode_iter(data, codec_options=options):
        print(doc)

        # Important to get things back to native decimal...
        z2 = doc['bson128_amt'].to_decimal()
        print("mult:", z2 * doc['num'])
        print("escaped:", doc['CR'])
        print("quotes:", doc['quotes'])

conn.close()
