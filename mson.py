#
#  Convert dicts of structures of "standard scalars" to JSON and be
#  aware of MongoDB "extended JSON" (i.e. type metadata conventions
#  like {"$numberDecimal": "234.23"}
#
#  Standard scalars are int, float, datetime, string, decimal, etc.
#  Arrays are supported, as are dicts of dicts.
#  Custom class mapping is not supported.
#  
#  Two Modes:  Pure and Mongo
#  PURE:
#    Parse:  
#           Whatever json.loads() returns. 
#
#    Emits:  String versions of whatever it has unless its a number
#            in which case a number.  
#
#  MONGO:
#    Parse:  
#           $numberLong, $numberDecimal, $binary, $date recognized
#           and converted to appropriate python types.
#
#    Emit:   long -> $numberLong
#            int -> if -2^32 -1 < n < 2^32-1, regular JSON number, else $numberLong
#            dates -> $date
#            binary -> $binary
#            ObjectId -> $oid
#            Decimal -> $numberDecimal
#            All MongoDB EJSON values are string quoted to protect the value
#            from misinterpretation as some kind of number
#
import json
import datetime

from dateutil import parser

from decimal import Decimal

import bson
from bson.objectid import ObjectId
from bson.binary import Binary

import base64

class mson:
    PURE = 0
    MONGO = 1

    @staticmethod
    def parse(strval,mode):

        mm = json.loads(strval)
        
        if mode == mson.PURE:  # Yer done!
            return mm  #  just leave

        def cvtLongMillisToDatetime(v):
            millis  = v / 1000.0; # Ha!  micros are float FRACTION!
            dv = datetime.datetime.utcfromtimestamp(millis)
            return dv

        # ... else look for code below these two defs!
        def XprocessMap(zz):
            for k in zz:
                newval = XprocessThing(zz[k])

                if newval is not None:
                    zz[k] = newval

        def XprocessThing(thing):
            newval = None

            if isinstance(thing, dict):
                # python3 thing.keys() is no long an iteratable but
                # rather a dict_keys.  len() still works BUT direct
                # integer subscripting does not.  The std workaround
                # is to call list() which exposes us to the thread-
                # changing-the-dict-miditeration problem but we do
                # not have that here...
                cks = list(thing.keys())

                #  Sigh.... special case for $binary...
                if len(cks) == 2:
                    ck1 = cks[0]
                    ck2 = cks[1]

                    if ck1 == "$binary" and ck2 == "$type":
                        v = thing[ck1]
                        q2 = base64.b64decode(v);
                        q = Binary(q2)
                        newval = q    
                        
                    if ck2 == "$binary" and ck1 == "$type":
                        v = thing[ck2]
                        q2 = base64.b64decode(v);
                        q = Binary(q2)
                        newval = q    

                elif len(cks) == 1:
                    ck = cks[0]
                    v = thing[ck]
                        
                    if ck == "$numberInt":  # future?
                        newval = int(v)
                
                    elif ck == "$date":
                        #  jsonp will turn ANY numberish thing into 
                        #  an int, even 8888123123123123123 .  Yep.
                        #  is __class__ int.
                        if isinstance(v, int):
                            dv = cvtLongMillisToDatetime(v)
                        else:
                            # It's a string.  If T is there go for parse:
                            if "T" in v:
                                dv = parser.parse(v)
                            else:
                                dv = cvtLongMillisToDatetime(int(v))

                        newval = dv

                    elif ck == "$numberLong":
                        newval = long(v)
                
                    elif ck == "$numberFloat":  # future?
                        newval = float(v)

                    elif ck == "$numberDouble":  # future?
                        newval = float(v)

                    elif ck == "$numberDecimal":
                        newval = Decimal(v)
                
                    elif ck == "$binary":
                        q2 = base64.b64decode(v);
                        q = Binary(q2)
                        newval = q    

                    elif ck == "$oid":
                        q = ObjectId(v)
                        newval = q    

                if newval == None:
                    XprocessMap(thing)

            elif isinstance(thing, list):
                for i in range(0, len(thing)):
                    v = thing[i]
                    nv2 = XprocessThing(v)
                    if nv2 is not None:
                        thing[i] = nv2

            return newval

        XprocessMap(mm)
        return mm




    @staticmethod
    def write(ostream, m, fmt):
        #  ostream,m,fmt will remain in scope for all the functions we
        #  define here, sort of like class instance level vars
        
        def emit(spcs, strval):
            #ostream.write(strval)
            ostream.write(strval.encode('utf-8'))

        #  A JSON String that prints like this:
        #
        #    {"server": "julia", "bob \"and\" danA"}
        #
        #  needs to look like this when captured a string
        #
        #    {\"server\": \"julia\", \"bob \\\"and\\\" danA\"}
        #
        #  TBD:  This groom could use completeness and performance...
        def groomJSONStr(instr):
            return instr.replace('\\','\\\\').replace('"', '\\\"').replace("\n","\\n").replace("\t","\\t")


        def emitItem(lvl, ith, v):
            spcs = ""
            spcs2 = " " * ith

            if v == None:
                emit(spcs, "null")

            elif isinstance(v, Binary):
                q = base64.b64encode(v);
                emit(spcs,  "{\"$binary\":\"%s\", \"$type\":\"00\"}" % q )

            elif isinstance(v, Decimal):
                if fmt == mson.MONGO:
                    emit(spcs,  "{\"$numberDecimal\":\"%s\"}" % v )
                else:
                    emit(spcs, "%s" % v)

            elif isinstance(v, bson.decimal128.Decimal128):
                if fmt == mson.MONGO:
                    emit(spcs,  "{\"$numberDecimal\":\"%s\"}" % v )
                else:
                    emit(spcs, "%s" % v)

# no more unicode in python3; strings ARE unicode         
#            elif isinstance(v, unicode):
#                q = v.encode('ascii', 'replace')
#                s2 = groomJSONStr(q)
#                emit(spcs, "\"%s\"" % s2)

            elif isinstance(v, str):
                s2 = groomJSONStr(v)
                emit(spcs, "\"%s\"" % s2)

            # Test for isinstance bool MUST precede test for int
            # because it will satisfy that condition too!
            elif isinstance(v, bool):
                # toString of bool works just fine...
                emit(spcs, "%s" % v)

            elif isinstance(v, int):
                if fmt == mson.MONGO:
                    # TBD:  Need to affirm these!
                    if v > 2147483647 or v < -2147483647:
                        emit(spcs,  "{\"$numberLong\":\"%s\"}" % v )
                    else:
                        emit(spcs, "%s" % v )
                else:
                    emit(spcs, "%s" % v )


            elif isinstance(v, float):
                # Fortunately, the string formatter for
                # doubles will add .0 upon output so you KNOW
                # it's a double.
                emit(spcs,  "%s" % v )

# no long in python3
#            elif isinstance(v, long):
#                if fmt == mson.MONGO:
#                    emit(spcs,  "{\"$numberLong\":\"%s\"}" % v )
#                else:
#                    emit(spcs, v)


            elif isinstance(v, datetime.datetime) or isinstance(v, datetime.date):
                #  Mongo supports pass epoch as well but
                #  this is probably the safer route.
                #  Just convert to ISO8601 for both...
                # q = v.strftime('%s')  # epoach

                q = v.strftime("%Y-%m-%dT%H:%M:%S")                

                #  Sigh.  Must get millis from micros!
                if isinstance(v, datetime.date):
                    ms = 0
                else:
                    ms = v.microsecond/1000

                iso8601 ="%s.%sZ" % (q,ms)

                #  Dates are simply too often used to force people
                #  not in MongoDB mode to deal with the extra $date.
                #  It's the caller's choice so... if they really want
                #  the fidelity, ask for ejson or better yet:  bson!
                if fmt == mson.MONGO:
                    emit(spcs,  "{\"$date\":\"%s\"}" % iso8601)
                else:
                    emit(spcs, "\"%s\"" % iso8601)


            elif isinstance(v, ObjectId):
                # toString of ObjectId mercifully does the right thing....
                emit(spcs,  "{\"$oid\":\"%s\"}" % v )

            elif isinstance(v, list):
                emit (spcs2,  "[" )
                i = 0
                for item in v:
                    if i > 0:
                        emit( spcs2, "," )
               
                    emitItem(lvl + 1, i, item)
                    i = i + 1

                emit( spcs2, "]" ) 

            elif isinstance(v, dict):
                emitDoc(lvl + 1, v)

            else:
                #  UNKNOWN type?
                t = type(v)
                emit(spcs,  "\"%s::%s\"" % (t,v) )


        def emitDoc(lvl, m):
            i = 0

            spcs = ""

            emit( spcs, "{")

            for k in m:
                item = m[k]
                if i > 0:
                    emit(spcs,  ",\"%s\":" % (k) )
                else:
                    emit(spcs,  "\"%s\":" % (k) )

                emitItem(lvl + 1, i, item)
                i = i + 1

            emit(spcs,  "}")


            if lvl == 0:
                #ostream.write("\n")
                emit("", "\n")

         #print ""   # force the CR

        emitDoc(0, m)

