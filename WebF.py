from http.server import BaseHTTPRequestHandler, HTTPServer

from socketserver import ThreadingMixIn

import ratelimit   # PYTHONPATH= pip3 install ratelimit

import urllib.parse
import datetime
from mson import mson
import bson

import re
import traceback
import sys


#  See stackoverflow.com for this.  Excellent.
#class MultiThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
class MultiThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class WebF:

    helpFuncName = "__help"

    class internalHelp:
        def __init__(self, context):
            self.parent = context['parent']

        def help(self):
            return {}

        def start(self, cmd, hdrs, args, rfile):
           return (200, None, None, True)

        def next(self):
            for fname in self.parent.fmap:
                if False == fname.startswith('__'):
                    (href,context) = self.parent.fmap[fname]
                    hh = href(context)
                    hdoc = hh.help()
                    hdoc['funcname'] = fname
                    yield hdoc

        def end(self):
            pass



    class internalErr:
        def __init__(self, respcode, errs):
            self.respcode = respcode
            self.errs = errs

        def start(self, cmd, hdrs, args, rfile):
           return (self.respcode, None, None, True)
        
        def next(self):
            for err in self.errs:
               yield err

        def end(self):
            pass




    class HTTPHandler(BaseHTTPRequestHandler):
        #  Each command action on HTTP gets turned into a callable
        #  method here, e.g. curl -X GET is bound to do_GET.  There is no
        #  restriction; curl -X CORN will map to do_CORN and if do_CORN is not
        #  implemented here, then BaseHTTPRequestHandler will return code 501
        #  unsupported method.

        def do_GET(self):
            self.call(self.path)

        def do_POST(self):
            self.call(self.path)

        def do_PUT(self):
            self.call(self.path)

        def do_PATCH(self):
            self.call(self.path)

        def do_DELETE(self):
            self.call(self.path)


        def log_message(self, format, *args):
           xx = self.server.parent
           if xx.log_handler == None:
              print("%s - - [%s] %s" % (self.address_string(),self.log_date_time_string(),format%args))



        def parse(self, reqinfo):
            params = {}
            if '?' in reqinfo:
                func, params = reqinfo.split('?', 1)
                params = dict([p.split('=', 1) for p in params.split('&') if '=' in p])
                for k in params:
                    params[k] = urllib.parse.unquote(params[k])
            else:
                func = reqinfo

            #  req comes in with leading /, always.  Eat it:
            func = func[1:]
            
            return ((func, params))
        

        def getArgTypeToString(self, argval):
           ss  = argval.__class__.__name__
           if ss == 'unicode':
              ss = "string"
           elif ss == 'str':           
              ss = "string"
           elif ss == 'float':           
              ss = "double"
           elif ss == 'Decimal':
              ss = "decimal"
           elif ss == 'list':
              ss = "array"
              
           return ss


        def chkArgs(self, funcHelp, webArgs):
            argerrs = []
            allowUnknownArgs = False

            if 'allowUnknownArgs' in funcHelp:
               allowUnknownArgs = funcHelp['allowUnknownArgs']

            declaredArgs = {}

            if 'args' in funcHelp:
                for hargs in funcHelp['args']:

                    declaredArgs[hargs['name']] = 1

                    if hargs['req'] == "Y":
                        if hargs['name'] not in webArgs:
                           argerrs.append({
                                    "errcode":1,
                                    "msg":"req arg not found",
                                    "data":hargs['name']})

                    if hargs['name'] in webArgs:
                       # exists: but is it the right type?
                       # any,string, int, long, double, decimal, datetime, binary, array, dict                           
                       argval = webArgs[hargs['name']]
                       argtype = hargs['type'];
                       if argtype != "any":
                          ss = self.getArgTypeToString(argval)
                          if ss != argtype:
                             argerrs.append({
                                    "errcode":2,
                                    "msg":"arg has wrong type",
                                    "data": {
                                      "arg": hargs['name'],
                                      "expected": argtype,
                                      "found": ss
                                      }})
                             
                # Now go the other way:  Check webargs:
                if allowUnknownArgs == False:
                   for warg in webArgs:
                      if warg != '_' and warg not in declaredArgs:
                         argerrs.append({
                             "errcode":2,
                             "msg":"unknown arg",
                             "data": {
                                "arg": warg
                                }})
                       
            return argerrs
                            
            



        def respond(self, args, handler):

            class baseWriter:
                def writeWrap(self, material):
                    if self.encoding == 'CHUNKED':
                        slen = format(len(material), 'x')
                        self.ostream.write(slen.encode('utf-8'))
                        self.ostream.write("\r\n".encode('utf-8'))
                        self.ostream.write(material)
                        self.ostream.write("\r\n".encode('utf-8'))
                    else:
                        self.ostream.write(material)
    
            class bsonWriter(baseWriter):
                def __init__(self, ostream, encoding):
                    self.ostream = ostream
                    self.encoding = encoding

                def prologue(self,things=None):
                    pass

                def emit(self,doc):
                    bytes = bson.BSON.encode(doc)
                    self.writeWrap(bytes)

                def epilogue(self,things=None):
                    if self.encoding == 'CHUNKED':
                        self.writeWrap(b'')  # The zero length chunk!


            class jsonWriter(baseWriter):
                def __init__(self, ostream, fmt, crdelim, encoding):
                    self.ostream = ostream
                    self.fmt = fmt
                    self.crdelim = crdelim
                    self.encoding = encoding
                    self.wroteOne = False

                def prologue(self,things=None):
                    pass

                def emit(self,doc):
                    import io

                    if self.crdelim is False:
                        if self.wroteOne is False:
                            self.writeWrap(b'[')
                        else:
                            self.writeWrap(b',')

                    fstr = io.BytesIO()
                    mson.write(fstr, doc, self.fmt)
                    bytes = fstr.getvalue()
                    fstr.close()
            
                    self.writeWrap(bytes)
                    self.wroteOne = True

                def epilogue(self,things=None):
                    if self.crdelim is False:
                        self.writeWrap(b']')
                    if self.encoding == 'CHUNKED':
                        self.writeWrap(b'')  # The zero length chunk!




            hdrdoc = None

            # Give start() a chance to do something; it is required mostly
            # because it must provide a response code.
            (respCode, addtl_hdrs, hdrdoc, keepGoing) = handler.start(self.command, self.headers, args, self.rfile)

            self.send_response(respCode)


            fmt = 'application/json'  # default
            afmt = fmt
            jfmt = mson.PURE
            crdelim = False
            encoding = None

            if addtl_hdrs is not None:
                for k,v in addtl_hdrs.items():
                    if k.upper() == "TRANSFER-ENCODING" and v == "chunked":
                        encoding = "CHUNKED"


            theWriter = jsonWriter(self.wfile, jfmt, crdelim, encoding)

            #  We expect simple
            #  Accept: application/json,json 
            #  No fancy alternative and q factor stuff.

            gg = []
            if 'Accept' in self.headers:
                gg = [ x.strip() for x in self.headers['Accept'].split(';')]
                afmt = gg[0] # just take first one; very simple

            if afmt == "application/bson":
                fmt = 'application/bson'
                theWriter = bsonWriter(self.wfile, encoding)
               
            elif afmt == "application/json" or afmt == "application/ejson":

                if afmt == "application/json":
                    fmt = afmt
                    jfmt = mson.PURE

                elif afmt == "application/ejson":
                    fmt = afmt
                    jfmt = mson.MONGO
                   
                # json and ejson support boundary=[LF,CR]
                if len(gg) > 1:
                    for item in gg:
                        attr = item.split("=")
                        if attr[0] == "boundary":
                            if attr[1] in ['LF','CR']:
                                crdelim = True
                                fmt += "; boundary=LF"
                            else:
                                print("unsupported json boundary") # TBD

                theWriter = jsonWriter(self.wfile, jfmt, crdelim, encoding)


            # else afmt is an unrecognized fmt; should do something about this
            self.send_header('Content-type', fmt)
            
            if addtl_hdrs is not None:
                for k,v in addtl_hdrs.items():
                    self.send_header(k,v) 

            if self.server.parent.cors is not None:
                self.send_header('Access-Control-Allow-Origin', self.server.parent.cors)

            self.end_headers()



            theWriter.prologue()

            if hdrdoc != None:
                theWriter.emit(hdrdoc)

            if keepGoing is False:
                theWriter.epilogue()
                return

            mmm = getattr(handler, "next", None)
            if callable(mmm):              
                for r in handler.next():
                    theWriter.emit(r)

            mmm = getattr(handler, "end", None)
            if callable(mmm):              
                footerdoc = handler.end()
                if footerdoc != None:
                    theWriter.emit(r)

            theWriter.epilogue()



        def call(self, path):
            xx = self.server.parent

            respCode    = 200
            args        = None
            fargs       = None
            fmt         = None; 

            try: 
                # Fancy way of calling decorator:
                if xx.rateLimiter is not None:
                    xx.rateLimiter.__call__(lambda: None)()

            except ratelimit.exception.RateLimitException as e:
               err = {
                  'errcode': 9,
                  'msg': "call rate limit exceeded"
                  }
               handler = xx.errHandler(429, [err])
               self.respond(None, handler)
               return   # bail out



            if xx.match_header is not None:
                for hdrname in xx.match_header:
                    mm = None
                    for rr in xx.match_header[hdrname]:
                        item = self.headers[hdrname] if hdrname in self.headers else ""

                        mm = re.search(rr, item)
                        if mm is not None:
                            break
                    if mm is None:
                        err = {
                            'errcode': 11,
                            'msg': "header %s value is invalid" % hdrname
                            }
                        #handler = xx.errHandler(400, [err])
                        handler = xx.errHandler(400, [err])
                        self.respond(None, handler)
                        return   # bail out

                
            try:
                user = None

                ss = datetime.datetime.now()

                # Extract params (after the '?') from the rest of it:
                prefunc,params = self.parse(path)

                if prefunc == xx.helpFuncName:  
                    prefunc = "help"

                if prefunc == "help":
                    # "__help" is registered; help is not.  So is help
                    # is defeated, then don't switch names 
                    if xx.allow_help == True:
                        prefunc = xx.helpFuncName

                
                func = None
                restful = None

                #  Basically, do a longest-first match...
                for fname,v in sorted(xx.fmap.items(), key=lambda k: (len(k),k), reverse=True):
                    lname = len(fname)
                    frag = prefunc[:lname]
                    #print "[%s] %d [%s] %d" % (fname,lname,frag,len(frag))
                    if fname == frag:
                        func = fname
                        restful = prefunc[lname+1:]  # hop over the /
                        if restful == "":
                            restful = None
                        break
                
                if restful is not None:
                    qq = restful.split('/')
                    params['_'] = qq


                #
                # START PRELIM
                # Get the function, parse the args
                #
                if func not in xx.fmap:
                   err = {
                      'errcode': 5,  # TBD
                      'msg': "no such function",
                      "data": prefunc
                      }
                   respCode = 404 
                   handler = xx.errHandler(respCode, [err])

                else:
                    (hname,context) = xx.fmap[func]

                    # Construct a NEW handler instance!
                    handler = hname(context)

                    try:
                       args = mson.parse(params['args'], mson.MONGO) if 'args' in params else {}
                       if '_' in params:
                           args['_'] = params['_'] 

                    except:
                       err = {
                          'errcode': 4,
                          'msg': "malformed JSON for args"
                          }
                       respCode = 400
                       handler = xx.errHandler(respCode, [err])


                    try:
                       fargs = mson.parse(params['fargs'], mson.MONGO) if 'fargs' in params else {}
                    except:
                       err = {
                          'errcode': 5,
                          'msg': "malformed JSON for fargs"
                          }
                       respCode = 400
                       handler = xx.errHandler(respCode, [err])



                # END PRELIM
                if respCode != 200:
                   self.respond(args, handler)

                else:
                    #  Basic stuff is OK and handler is set.  Move on.
                    #  Check args and authentication.  If either is bad, then
                    #  SWITCH the handler to the error handler and set an
                    #  appropriate HTTP return code.
                    zz = handler.help()
                    argerrs = self.chkArgs(zz, args)

                    if len(argerrs) > 0:
                       respCode = 400
                       handler = xx.errHandler(respCode, argerrs)

                    else:
                       tt2 = None

                       # Low impact so get it out of the way, even if
                       # unused...
                       clrt = self.client_address  # not a func, a tuple!
                       clrh = {
                           "name": self.address_string(),
                           "ip": clrt[0],
                           "port": clrt[1]
                           }

                       # Go for local override first...
                       authMethod = getattr(handler, "authenticate", None)

                       if callable(authMethod):
                           tt2 = authMethod(clrh, self.headers, args)

                       elif xx.auth_handler is not None:

                          tt2 = xx.auth_handler(handler, xx.auth_context, clrh, self.headers, args)
                           
                       if tt2 is not None:
                           # Expect (T|F, name, data)
                           user = tt2[1]

                           if tt2[0] == False:
                               err = {
                                   'errcode': 3,
                                   'user': user,  # OK to be None
                                   'msg': "authentication failure"
                                   }
                               if len(tt2) == 3:
                                   err['data'] = tt2[2]

                               handler = xx.errHandler(401, [err])

                    self.respond(args, handler)


                ee = datetime.datetime.now()


                loghandler = None
                uselogcontext = True

                if xx.log_handler != None:
                    loghandler = xx.log_handler

                # Function-specific overrides:
                logMethod = getattr(handler, "log", None)
                if callable(logMethod):
                    loghandler = logMethod
                    uselogcontext = False

                if loghandler != None:
                   if user == None:
                      user = "ANONYMOUS"

                   #diffms = int((ee - ss)/1000)
                   tdelta = ee - ss
                   diffms = int(tdelta.microseconds/1000)

                   clrt = self.client_address  # not a func, a tuple!
                   clrh = {
                       "name": self.address_string(),
                       "ip": clrt[0],
                       "port": clrt[1]
                       }
                   
                   info = {
                         "caller": clrh,
                         "user": user,
                         "func": func,
                         "params": params,
                         "stime": ss,
                         "etime": ee,
                         "millis": diffms,
                         "status": respCode
                         }

                   if uselogcontext == True:
                       loghandler(info, xx.log_context)
                   else:
                       loghandler(info)



            except Exception as e:
               err = {
                  'errcode': 6,
                  'msg': "internal error",
                  "data": func
                  }
               handler = xx.errHandler(500, [err])
               self.respond(args, handler)

               import traceback
               traceback.print_exc()

               raise e


    #
    #  wargs:
    #  port           int      listen port (default: 7778)
    #  addr           string   listen addr (default: localhost BUT if you want
    #                          other machines to connect, specify "0.0.0.0"
    #
    #  sslKeyCertChainFile  string   Path to file in PEM format containing concatenation of
    #                          private key plus ALL certs (the full cert chain)
    #                          (required for https access to this service)
    #
    #  sslKeyFile  string   Path to file in PEM format containing private key only (must be used with sslCertChainFile)
    #  sslCertChainFile  string   Path to file in PEM format containing the full cert chain but not the key (must be used with sslKeyFile)
    #
    #  cors           URI | *  Set Access-Control-Allow-Origin to this
    #                          value.  See http CORS docs for details.
    #
    #  rateLimit      int      Server-scoped function call rate limit per second
    #  allowHelp      boolean  Permit or disable /help builtin function (default: true)
    #
    #  matchHeader  (dict of array of regexp)  Incoming header must match one of the specified regexp. To 
    #                 make a header mandatory but with any value use .*
                            

    def __init__(self, wargs=None):

        self.fmap = {}
        self.wargs = wargs if wargs is not None else {}


        self.rateLimiter = None
        if 'rateLimit' in self.wargs:
            self.rateLimiter = ratelimit.RateLimitDecorator(calls=self.wargs['rateLimit'],period=1)


        listen_addr = self.wargs['addr'] if 'addr' in self.wargs else "localhost"
        listen_port = int(self.wargs['port']) if 'port' in self.wargs else 7778

        self.httpd = MultiThreadedHTTPServer((listen_addr, listen_port), WebF.HTTPHandler)

        #  To run this server as https:
        #  Make a key and cert files:
        #    openssl req -x509 -nodes -newkey rsa:2048 -subj "/CN=localhost" -keyout key.pem -out cert.pem -days 3650
        #  Then set the sslKeyFile + sslCertChainFile args
        #  OR, 
        #    cat key.pem cert.pem > mycert.pem
        #  Pass the mycert.pem file as value for sslPEMKeyFile

        if 'sslKeyCertChainFile' in self.wargs:
           import ssl   # condition import!
           cf = self.wargs['sslKeyCertChainFile']

           self.httpd.socket = ssl.wrap_socket (self.httpd.socket, certfile=cf, server_side=True)

        if 'sslKeyFile' in self.wargs and 'sslCertChainFile' in self.wargs:
           import ssl   # condition import!
           kf = self.wargs['sslKeyFile']
           cf = self.wargs['sslCertChainFile']

           context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
           context.load_cert_chain(cf, kf)

           self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
            

        self.cors = self.wargs['cors'] if 'cors' in self.wargs else None

        self.log_handler = None   # optional
        self.log_context = None   # optional
        self.auth_handler = None   # optional
        self.auth_context = None   # optional

        self.allow_help = self.wargs['allowHelp'] if 'allowHelp' in self.wargs else True

        self.match_header = self.wargs['matchHeader'] if 'matchHeader' in self.wargs else None

        self.errHandler = self.wargs['errorHandler'] if 'errorHandler' in self.wargs else self.internalErr

        # Needed for args chking.
        self.registerFunction(self.helpFuncName, self.internalHelp, {"parent":self});

        self.httpd.parent = self


    def registerFunction(self, name, handler, context):
        if name == "":
            raise ValueError("function name cannot be empty string")

        self.fmap[name] = (handler,context)

    def deregisterFunction(self, name):
        if name in self.fmap:
            del self.fmap[name]




    def registerLogger(self, handler, context):
        self.log_handler = handler
        self.log_context = context



    def registerAuthentication(self, handler, context):
        self.auth_handler = handler
        self.auth_context = context


    def go(self):
        self.httpd.serve_forever()

