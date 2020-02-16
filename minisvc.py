#
# curl http://localhost:7778/func1
#

import WebF

import datetime
import bson
from decimal import Decimal


class Func1:
    def __init__(self, context):
        pass

    def help(self):
        return {"type":"simple",
                "desc":"A function that returns something.",
                "args":[
                  {"name":"maxCount", "type":"int","req":"Y",
                   "desc":"max number of snacks"}
                ]
                }

    def makeDoc(self, num):
        #dd = datetime.datetime.now()
        dd = datetime.datetime(2018,1,1)

        # You MUST use bson.decimal128, not the built in Decimal type!
        # This is exactly the same as the Java imp.  The reason is both
        # python Decimal and Java BigDecimal are *subsets* of the full 
        # decimal128 spec which covers NaN and Infinity.
        #
        # If you want to use regular Decimal, then cart that around in 
        # the logic BUT at the point where construct the outbound doc,
        # make a bson.decimal128 as follows:
        #   val = Decimal("23.7");
        #   ... logic
        #   doc = {"val": bson.decimal128.Decimal128(val)}
        #
        bamt = bson.decimal128.Decimal128("23.7") 

        CRcontent = """hello
and
	goodbye
forever"""

        doc = {
            "name":"buzz", 
            "addr":{"city":"NY","state":"NY","zip":"07078","loc":{"n":"139","s":"W82 St."}},
            "num":num, 

            "CR": CRcontent,
            "quotes": [ '"yow"' , "hawai\'i" ],

            "whatevs": {
                "fpets": [ "dog","cat", 3, dd]
                },

            "someDouble":11.11, 
            "date":dd, 
            "bson128_amt":bamt

            }

        return doc


    def start(self, cmd, hdrs, args, rfile):
        print("hdrs:", hdrs)
        print("args:", args)
        doc = self.makeDoc(1)
        addtl_hdrs = {"X-Header-1":"v1"}
        return (200, addtl_hdrs, doc, True)

    def next(self):
        for x in range(0,2):
            doc = self.makeDoc(2+x)
            yield doc


class Func2:
    def __init__(self, context):
        pass

    def help(self):
        return {"type":"simple",
                "desc":"A function that returns something."
                }

    def start(self, cmd, hdrs, args, rfile):
        print("hdrs:", hdrs)
        print("args:", args)

        doc = {"x":0,"name":"buzz","hdate":datetime.datetime.now()}

        addtl_hdrs = {"Transfer-Encoding":"chunked"}
        return (200, addtl_hdrs, doc, True)

    def next(self):
        for x in range(1,3):
            doc = {"x":x,"name":"buzz","hdate":datetime.datetime.now(), "amt": bson.decimal128.Decimal128("77.2")}
            yield doc



class MyErr:
    def __init__(self, respcode, errs):
        self.respcode = respcode
        self.errs = errs
        
    def log(self, info):
        print("MyErr class override log:", info)

    def start(self, cmd, hdrs, args, rfile):
        # Basically, turn ALL errors into Go Away errors:
        return (501, {"Warning":"299 - Go Away"}, None, False)



def logF(doc, context):
    print("my log function:", context)
    print(doc)

def main():
    webfArgs = {
        "port":7778,
        "addr":"0.0.0.0",
#        "sslKeyCertChainFile":"mycert.pem", # must be PEM format w/private key + cert
        "sslKeyFile":"../WebF/key.pem",
        "sslCertChainFile":"../WebF/cert.pem",
        "cors":'*',

#        "allowHelp":False,
#        "matchHeader": { "User-Agent": [ "^Xcurl" ] } ,

        "errorHandler": MyErr,

        "rateLimit":5
        }

    r = WebF.WebF(webfArgs)

    r.registerFunction("func1", Func1, None);
    r.registerFunction("func2", Func2, None);

#    r.registerLogger(logF, "log context")

    print("ready")
    r.go()

main()




