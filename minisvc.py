#
# curl http://localhost:7778/func1
#

import WebF

import datetime
import bson

class Func1:
    def __init__(self, context):
        pass

    def help(self):
        return {"type":"simple",
                "desc":"A function that returns something."}


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
        print(hdrs)
        doc = self.makeDoc(1)
        return (200, doc, True)

    def next(self):
        for x in range(0,2):
            doc = self.makeDoc(2+x)
            yield doc


def main():
    webfArgs = {
        "port":7778,
        "addr":"0.0.0.0",
#        "sslPEMKeyFile":"mycert.pem", # must be PEM format w/private key + cert
        "cors":'*'
        }

    r = WebF.WebF(webfArgs)
    r.registerFunction("func1", Func1, None);
    print("ready")
    r.go()

main()




