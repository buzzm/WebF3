WebF
=============

A very lightweight python3 web server with pluggable function handling.

UNDER CONSTRUCTION!

Basic Use
---------

```python
$ cat mysvc1.py
import WebF

class Func1:
    def __init__(self, context):
    	pass

    def help(self):
        return {"type":"simple",
	        "desc":"A function that returns something.",
                "args":[
                {"name":"startTime", "type":"datetime","req":"N",
                 "desc":"Starting time for snacking"},
                {"name":"maxCount", "type":"int","req":"Y",
                 "desc":"max number of snacks"}
                ]}
    
    def start(self, cmd, hdrs, args, rfile):
        # maxCount must be in args because it is required:
        self.maxCount = args['maxCount']

	# Return:
	#   200 ("ok")
	#   None (no additional headers to add to response)
	#   None (no doc to emit because we will let next() vend each doc)
	#   True (tell WebF to keep going with next() )
        return (200, None, None, True)
        
    def next(self):
        for n in range(0, self.maxCount):
            doc = {"name":"chips", "type":n}
            yield doc   # yield, NOT return!

    # No need to define end()


def main():
    websvc = WebF.WebF()
    websvc.registerFunction("helloWorld", Func1, None)
    print "Waiting for web calls"
    websvc.go()

main()

$ python mysvc.py &
Waiting for web calls

$ curl -g 'http://localhost:7778/helloWorld?args={"startTime":{"$date":"2017-01-02T19:00:06.000Z"},"maxCount":3}'
{"type":0,"name":"chips"}
{"type":1,"name":"chips"}
{"type":2,"name":"chips"}

$ curl -g 'http://localhost:7778/help
{"funcname":"helloWorld","args":{"args":[{"req":"N","type":"datetime","name":"startTime","desc":"Starting time for snacking"},{"req":"Y","type":"int","name":"maxCount","desc":"max number of snacks"}],"desc":"A function that returns something."}}

```

The WebF framework has these design goals:

1. Lightweight.  WebF relies only on internal python libs and one other lib (included)
2. Standardized handling of web service args.  All functions in WebF take a
single arg called "args" which is a JSON string.  This permits standardization
of representing extended types like Decimal and Dates and facilitates array and
substructure processing.
3. Ability to generate JSON, EJSON, or BSON for output.  EJSON is extended
JSON which originated at MongoDB and implements a convention for identifying
types of data beyond the basic JSON types WITHOUT requiring a non-JSON compliant
parser.  BSON is an ideal "code-to-code" format because of performance and
precise preservation of types like datetimes, decimal128, binary, and 32
vs. 64 bit integers.  Output format is set in an industry-standard way by
specifying the `Accept` header on the inbound call as follows:
* `application/json` for json.
* `application/ejson` for ejson
* `application/bson` for bson

In addition, json and ejson output can be sent in CR-delimited form
with the `boundary=LF` attribute.  More
on this in the section following basic class and function setup.

4. Flexibility to efficiently support a variety of response semantics from
"the one big JSON object" to streamable (constant output) BSON and meta/data
constructs without imposing a standard through appropriate use of `start` 
and `next` methods.

5. Automatic handling of help.  Calling http://machine:port/help will return
the set of functions and descriptions and arguments to the caller.   
6. Easy, flexible integration to RESTful callers.



Overview
--------

WebF starts a web server on the host machine at the designated port, by 
default 7778
```
websvc = WebF.WebF({dict of options})
```
These options are available upon construction:
```
addr (string)           listen addr (default: localhost BUT if you want other machines to connect, specify "0.0.0.0"
port (int)              Port upon which to listen (default 7778)

sslKeyCertChainFile (string)  Path to file in PEM format containing a concatenation of private key and the full cert chain; automatically enables SSL to permit https access to this service

sslKeyFile (string)  Path to file in PEM format containing just the private key; must be used with sslCertChainFile arg
sslCertChainFile (string)  Path to file in PEM format just the full cert chain but no private key; must be used with sslKeyFile arg

cors (string)           URI or *.  If set, server will set Access-Control-Allow-Origin header to this value upon return

rateLimit (int)         Server-scoped (i.e. across all functions) call rate limit per second

allowHelp (boolean)     If False, the built-in help function is defeated (default: True)

matchHeader  (dict of array of regexp)  Incoming header must match one of the specified regexp. To 
                        make a header mandatory but with any value use .*
                            

Example:
websvc = WebF.WebF({"port": 8080,
       	            "sslKeyCertChainFile": theFile,
		    "matchHeader": { "User-Agent": [ "^curl/", "^Mozilla/5.0" ] }
                    "cors":'*'})
```



Each server can have many functions associated with it.  
A function is registered in the `registerFunction` method and establishes
the first `n` components of path in the URL as a map to a handler.  A simple
example:
```
      http://machine:port/foo
```
would be handled by the following function registration:
```
websvc.registerFunction("foo", Func1, context)
```

Registration binds the function name (a string) to a class (*not* an instance
of the class; not the class name as a string; just the class!) plus "context" or variables to pass
to the function class upon construction.  The function name string cannot be
the empty string "" and it should realistically
be something that can be easily encoded on the URL so
avoid spaces, punctuation, quotes, etc.

This approach differs slightly from Java servlets where typically the 
servlet is instantiated only once in the lifetime of the container and
shared across multiple threads.  This requires special attention to not
putting anything in class scope (without special handling) to prevent
concurrency issues.   WebF is simpler: when the function is called, a
new handler instance is created.  Shared material or material that must
persist across calls, if desired, can be accessed/managed via the context.
The complete scope lifecycle is:
* After startup, there is a single object of type `MultiThreadedHTTPServer`
listening on address and port.  It is derived from `http.server.HTTPServer`
and `ThreadingMixIn`. 
* As part of the `MultiThreadedHTTPServer` initialization, it takes the name
of a class (*not* an instance of the class; not the class name as a string;
just the class!) that must implement
 `BaseHTTPRequestHandler`; in this implementation,
the internal derived type is `WebF.HTTPHandler`.
* When a socket connection is made to `MultiThreadedHTTPServer`, it creates
a new `WebF.HTTPHandler` instance, sets it up with connection specific 
information like caller IP and port, creates a new thread, and calls the
`do_GET/do_POST` etc. on the new `WebF.HTTPHandler` instance.
* The WebF framework will map the incoming URL path to a registered function,
create a new instance of that class, and begin the `__init__/authenticate/
start/next/end` cycle
* In summary, by the time `__init__` is called on the registered function,
all material accessible from `self` is threadsafe.

It is the responsibility of the program using WebF to properly apply
locking constructs around shared resources in the parent context, if
necessary and appropriate.

Functions can be deregistered with the `deregisterFunction` method.  Both
`registerFunction` and `deregisterFunction` can be called at any time 
during the lifetime of the WebF service instance.  This means both functions
themselves and other asynchronous events can dynamically create endpoints.


More sophisticated designs might call for versioning:
```
      http://machine:port/v1/foo
```
This might be handled by the following function registration:
```
# Note the "v1/foo" path!
websvc.registerFunction("v1/foo", Func1, context)
```

All other path pieces following the registered pieces are considered RESTful arguments
to the function and are handled as described in `args` below.

The class must support these methods:
* `__init__`:  Is passed context as argument.
* `help`:  More on this later.
* `start`:  Called once at the start of the web service call and is passed:
  * cmd: "GET", "POST", "PUT", "PATCH", or "DELETE"
  * hdrs:  A dictionary of HTTP headers
  * args:  A dictionary of arguments, decoded from the inbound JSON args and observing EJSON conventions, so numbers are actually numbers, dates are `datetime.datetime`, etc.  Any RESTful arguments i.e. those path components appearing
after the function name are placed into an array and assigned to the special
argument name `_` in the `args` dictionary.
  * rfile:  The input stream if this is a PUT, POST, or PATCH

`start` must return a tuple containing 4 items: the HTTP response code, additional http headers, the "initial return set" either a dict (set of 1) OR an array of dict, and a boolean True or False to indicate that `next` and `end` should
be executed.  The additional headers can be `None`.  The initial return set can be
`None`.  It is 
OK to return `None` as the initial return set yet pass `True` as the "keep going"
flag.
This sometimes make the setup of producing and emitting "rows" of data easier by
localizing the logic to the `next` method instead of splitting it across `start` and
`next`.  Conversely, it may be easier to construct a small set of return dicts
as an array in `start` and dispense with `next`.


The framework does not interpret the meaning of response codes; it is the
responsibility of the function writer to pass the combination of code, data (in the dict),
and "keep going" flag.  The "keep going" flag is necessary because the framework will
automatically try to execute `next` and `end` if they exist regardless of the HTTP
response code.   
Note that it is a noop if the keep going flag is set True and there is no
`next` or `end` method.


The class can optionally provide these methods:
* `next`:  Called iteratively as necessary for the function to vend units of
content.   This allows the function to incrementally vend output
to the consumer.  It is therefore not necessary, for example, to build a giant
array of 100,000 items in the start() method and emit a single huge response.
The client, however, sees a single stream of material and does not have to
perform any special actions.  next() leverages python's yield operator.
* `end`:  Called after iteration to next() has concluded.  Can optionally return
a dict that will be sent to the client.
Command-style function that only return a status doc typically only need a
start() method; no next() or end().

The class does not have to deal with encoding or output formats.  `start`,
`next`, and `end` should return native python dicts complete with rich types
like arrays and `Decimal` and `datetime.datetime` -- i.e. you don't have to
bother with converting dates into ISO8601 strings.  The WebF framework will
convert the data to the format specified in the `Accept` header.

The class also does not have to deal with "array wrapping" of the returned 
material.  The class need only construct individuals dicts.  The WebF
framework will appropriately wrap the outbound material based on the
`Accept` header as follows:
* `application/json or ejson`:  A leading `[` will be emitted before the first doc
and a trailing `]` emitted after the last doc.  If no docs are created in the
function, this becomes a valid array of length 0 i.e. `[]`.  If an error occurs
and a precise return cannot be determined (including length zero), the function
may not emit `[]` at all.  The
caller must slurp/parse the entire response as a potentially large array and
only then begin to operate on the individual items within.  It also means 
that simple functions that emit a single doc are still always wrapped in
an array.
* `application/json or ejson; boundary=LF|CR`:  NO leading `[` or trailing
`]` will be emitted.  Each doc is vended as a "standalone" JSON object followed
by a CR.  The caller can now use so-called CR-delimited JSON conventions and
read the response line by line, parsing the objects one at a time.  This is
potentially much more efficient for the caller because it avoids "high 
watermarking" in creating a large JSON array only to turn it into something else.  It also means that simple functions that emit a single doc can be easily
parsed directly into a JSON object without the wrapper array.
* `application/bson`:  BSON has built-in length so there is no concept of an
additional boundary; it already acts as if it has a boundary.  Multiple docs
streamed "back to back" as BSON can be easily consumed by utils provided in
the BSON libraries for doing so; thus it is never necessary to wrap BSON in
an outer BSON array.

The class optionally may provide an `authenticate` method.  See 
Authentication below for more.

Functions can have zero more arguments.  Unlike traditional functions,
there are only 2 HTTP arguments in the framework: `args` and `fargs`.  The latter
is framework arguments which we'll cover later.  `args` is simply a JSON
string that itself carries all the "real" arguments.  This provides a 
standard, easily externalizable format to supply arguments of any type
including lists of structures, binary data, etc.  The incoming JSON
is parsed into a real python dictionary so functions never have to deal 
with JSON itself, http decoding, etc.  In addition, EJSON is always honored
upon input to specify non-standard JSON types.  Some `args` examples:
```
Assume http://machine:port/ is the URL prefix; then:

Pass one arg "name" with value buzz:
    foo?args={"name":"buzz"}      

A call with several types of args, some complex:
    foo?args={"name":"buzz","fpets":["bird","dog","cat"],"idx":83}}

Pass value = 1    
    foo?args={"value":1}
    value will be class int in the args

Pass value = 1.0   
    foo?args={"value":1.0}
    value will be class float in the args

Pass value = 1L (long)
    foo?args={"value":{"$numberLong":"1"}}
    value will be class long in the args.  Note we pass 1 as a string
    to prevent any truncation issues along the way

Pass value = 1D (decimal128)
    foo?args={"value":{"$numberDecimal":"1"}}
    value will be class Decimal in the args.  Note we pass 1 as a string
    to prevent any truncation issues along the way

Pass value = date(2017-01-20)
    foo?args={"value":{"$date":"2017-01-28T21:47:46.333"}}
    EJSON requires dates to be passed as ISO8601 strings.
    value will be class datetime.datetime 

The advantage of the standardized JSON arg structure becomes clear with
really complex args:
    foo?args={"reqs":[{"n":"A1","t":7,"data":["foo","bar"]},{"n":"A2","t":9,"data":{"sample":{"$numberDecimal":"4.40"}}}]}

Of course, VERY complex and/or large arguments should probably be sent via POST.

```
Remember it is important to encode spaces and other special characters in the
web service call, and if calling from the shell, protecting the whole thing 
with single quotes and -g if using curl to prevent globbing:
```
This will not work!  The spaces between one, two, and three break the URL:
curl http://machine:port/foo?args={"value":"one two three"}

Nor will this.  The braces trigger globbing in curl
curl 'http://machine:port/foo?args={"value":"one two three"}'

Nor will this.  URLs must be encoded:
curl -g 'http://machine:port/foo?args={"value":"one two three"}'

Finally, this WILL work:
curl -g 'http://machine:port/foo?args={"value":"one%20two%20three"}'
```
Again, WebF will properly decode URLs and convert args to a native
python dictionary containing the proper types.

It is the responsibility of the function implementer to rationalize 
specifically named arguments presented in `args` and those optionally
appearing as RESTful args:
```
Basic example from before; nothing new:
    curl:             foo?args={"id":"E123"}      
    args in start():  {"id":"E123"}

Now adding RESTful args:
    curl:             foo/E999/4?args={"id":"E123"}      
    args in start():  {"_":["E999","4"], "id":"E123"}
```
The _ member of `args` is populated with the RESTful positional arguments.
It is the responsibility of the function to determine which id should be
used and for what purpose, especially in the context of the command
(GET/PUT/POST/PATCH).

The combination of standard args handling plus RESTful features makes it
very easy to implement RESTful GET services that require extra 
arguments to control behavior -- especially complex arguments like 
filtering expressions:
```
# Get all things (no filter, no nothing):
GET thing		

# Get thing E123:
GET thing/E123

# Get all things of color red OR size < 8. Note we are using MongoDB filtering expressions here but that 
# does NOT tie us to MongoDB!  The point is that the standard JSON handling makes it straightforward and
# robust to pass complex structures:
GET thing?args='{"filter":{"$or":[{"color":"red"},{"size":{"$lt":8}}]}}'

# Same as above but restrict fields to just id and maker (i.e. don't return a huge payload):
GET thing?args='{"filter":{"$or":[{"color":"red"},{"size":{"$lt":8}}]}, fields:["id","maker"]}'

# Same as above but with paging:
GET thing?args='{"filter":{"$or":[{"color":"red"},{"size":{"$lt":8}}]}, "fields":["id","maker"], "page":2, "limit":40}'

# Get thing E123 but restrict fields as before:
GET thing/E123?args='{"fields":["id","maker"]}'
```





`fargs` are framework-level args and are common across ALL functions
in ANY service that is deployed.  This is an area to be developed.




Help
----
A key feature of WebF is built-in help for functions.  When the service 
is called with the reserved function name `help`, the help() method of
each registered function will be called and the details of the args and
a description will be returned as structured payload in whatever format
is indicated in the `Accept` header JSON by default).  The data
in help() is also used for required argument and argument type enforcement.

Sometimes help is not desired.  The help function can be defeated with
the `allowHelp: False` option.

The help() method has a specific structure:
```
{
  "type": "simple",
  "desc": "Top level description of the function",
  "allowUnknownArgs":boolean,
  "args": [
    {"name": "argName", "type": "argType", "req": Y|N, "desc":"description"}
    ...
   ]
}
```
`type` indicates the structure of the help data; that is, what other fields
appear in the dict and an definition for their meaning and use.
The only `type` currently supported is `simple`.
In the future, "type":"json-schema" might be used to provide very
comprehensive and detailed help on arguments.

`allowUnknownArgs` defaults False.  Unless set to True, extra/unknown args
are caught and the error code 400 will be returned.  This is very useful
for catching misspellings of optional args and in general providing a more
locked-down interface.


argType is a string, one of the following:
```
any, string, int, long, double, datetime, binary, array, dict
```
Note that the simple help format cannot dive deep into array or dict types;
that is for json-schema or similar.   Also, the simple type does not have
a provision to return an error upon detection of extra / superfluous args.

When a call is made to WebF, the help is accessed and the args checked
for `req` and type.  Any errors will be collected and HTTP error 400 
returned along with the error payload:
```
A successful call (note use of -i so we can see the HTTP headers):

$ curl -i -g 'http://localhost:7778/helloWorld?args={"startTime":{"$date":"2017-01-02T19:00:06.000Z"},"maxCount":3}'
HTTP/1.0 200 OK
Content-type: text/json
{"type":0,"name":"chips"}
{"type":1,"name":"chips"}
{"type":2,"name":"chips"}

Missing required arg maxCount:
$ curl -i -g 'http://localhost:7778/helloWorld?args={"startTime":{"$date":"2017-01-02T19:00:06.000Z"},"maxCount":3}'
HTTP/1.0 400 Bad Request
Content-type: text/json

{"data":"maxCount","errcode":1,"msg":"req arg not found"}

Wrong arg type ($foo is not EJSON so it will remain as a dict)
$ curl -i -g 'http://localhost:7778/helloWorld?args={"startTime":{"$foo":"2017-01-02T19:00:06.000Z"}}'
HTTP/1.0 400 Bad Request
Content-type: text/json

{"msg":"arg has wrong type","data":{"expected":"datetime","found":"dict","arg":"startTime"},"errcode":2}
```


Header Matching
---------------
Some use cases call for specific headers to exist and to have certain values.
It is certainly possible to do this on an individual function basis because
the HTTP headers are passed in the `start` method.  To be more well-factored,
A separate helper function could also be crafted and called at the beginning
of each `start` function.  As a convenience, the `matchHeader` option can be
used which will be automatically applied to all functions.  If a header value
does not match at least one of the supplied regexp, an error is raised similar
to a wrong arg type.  For example, to only allow Mozilla and curl access:
```
websvc = WebF.WebF({"matchHeader": { "User-Agent": [ "^curl/", "^Mozilla/5.0" ] } })
```




Logging
-------
If a logger is registered thusly:
```
    websvc.registerLogger(logF, context)
```
then regular python function `logF` will be called upon completion each time the service is
hit (successful or not) as `logF(info, context)` where `info` is a 
dict with useful data (here filled in with representative examples):
```
{'status': 200,
 'caller': {'name':'1.0.0.127.in-addr.arpa','ip':'127.0.0.1','port':42321},
 'stime': datetime.datetime(2017, 1, 29, 10, 56, 13, 374307)}
 'etime': datetime.datetime(2017, 1, 29, 10, 56, 13, 374909), 
 'millis': 12,
 'params': {'args': '{"startTime":{"$date":"2017-01-02T19:00:06.000Z"}}'},
 'user': 'ANONYMOUS',
 'func': 'helloWorld'
}
```

Logging can also be locally overridden in the function by supplying a `log`
method:
```
class Func1:
    def log(self, info):
    	print info
```
In this case, context is not used.



Custom Error Handling
---------------------
A service may wish to perform more than just report the error code, or it
may wish a more or less verbose response, for example.  To do so, declare
an handler class in the `errorHandler` option.  The handler has the same
interaction requirements as regular functions (start/next/end) so only
`start` is mandatory.  The differences are there is no authentication
(because it is internal) and the `__init__` signature is different.  Here
is a simple example that basically copies the default behavior but prints
something in the init:
```
class MyErr:
    def __init__(self, respcode, errs):
        print("You are in MyErr")
        self.respcode = respcode
        self.errs = errs
        
    def start(self, cmd, hdrs, args, rfile):
        return (self.respcode, None, None, True)
        
    def next(self):
        for err in self.errs:
            yield err


websvc = WebF.WebF({"errorHandler": MyErr})
```




Context
-------
Context is a way to make data and resources available to functions from
"outside" the framework.  Context is completely under control of the 
invocation environment; thus, different functions can have different
contexts or share one.   Context is fully read/writable; thus, functions
can communicate back to the invocation environment.  Common resources can
be managed via a common context if appropriate concurrency control is applied.

A very common use is to set up client-side handles to databases.  Here is
an example of a service that sets up MongoDB and makes a collection
available to a function via the context:
```
import pymongo
from pymongo import MongoClient

import WebF

import sys

class Func1:
    def __init__(self, context):
        self.db = context['db']
        self.cursor = None

    def help(self):
        return {"desc":"Fetch product info from DB",
                "args":[
                {"name":"productType", "type":"array","req":"N","desc":"fetch only products of this type(s)"}
                ]}
    
    def start(self, cmd, hdrs, args, rfile):
        pred = {}  # Fetch all
        if 'productType' in args:
            logging.info("subset requested")
            pred = {"prodType": {"$in": args['productType']}}

        # Set up cursor:
        self.cursor = self.parent.db['product'].find(pred)
        
        # Assume all OK; normally we'd catch exceptions and such.  We'll
        # let the next() method iterate over the cursor, so no need
	# to return anything here except a good HTTP code and setting the
	# keep-going flag to True
        return (200, None, True)

    def next(self):
        for doc in self.cursor:
            yield doc


def main(args):
    client = MongoClient()  # various auth options here...
    db = client['testX']

    websvc = WebF.WebF(args)
    websvc.registerFunction("getProducts", Func1, {"db": db})
    websvc.go()

main(sys.argv)
```


Context can carry the instance of the invoking "self."  This makes ALL the 
resources available.   Below is a complete example of this, including
separating the invocation environment (main and command line args),
the real logic body (MyProgram) which contains bespoke methods like
`fancyCalculation()`, and the WebF framework:

```
import pymongo
from pymongo import MongoClient

import WebF

import argparse
import sys

class Func1:
    def __init__(self, context):
        self.parent = context['parent']

    def help(self):
        return {"desc":"Fetch product info from DB",
                "args":[
                {"name":"productType", "type":"array","req":"N","desc":"fetch only products of this type(s)"}
                ]}
    
    def start(self, cmd, hdrs, args, rfile):
        pred = {}  # Fetch all
        if 'productType' in args:
            logging.info("subset requested")
            pred = {"prodType": {"$in": args['productType']}}

        # Set up cursor:
        self.cursor = self.parent.db['product'].find(pred)
        
        # Assume all OK; normally we'd catch exceptions and such.  We'll
        # let the next() method iterate over the cursor:
        return (200, None, True)

    def next(self):
        for doc in self.cursor:
	    # Add to the dict as vended from the database:
            doc['val'] = self.parent.fancyCalculation(5,6)
            yield doc


class MyProgram:
    def __init__(self, rargs):
        self.rargs = rargs

        client = MongoClient(host=self.rargs.host)
        self.db = client['testX']

        self.websvc = WebF.WebF({"port":self.rargs.port})

        # Give the Func1 access to the complete parent!
        self.websvc.registerFunction("getProducts", Func1, {"parent": self})

    def run(self):
        self.websvc.go()  # drop into loop

    # Example of a method that we want to call from within with web service:
    def fancyCalculation(self, a, b):
        return a + b


def main(args):
    parser = argparse.ArgumentParser(description=
   """A service to fetch products
   """,
         formatter_class=argparse.ArgumentDefaultsHelpFormatter
   )

    parser.add_argument('--host',
                        metavar='mongoDBhost',
                        default="mongodb://localhost:27017",
                        help='connection string to product DB7')

    parser.add_argument('--port',
                        type=int,
                        metavar='int',
                        default=9119,
                        help='port upon which to listen')

    rargs = parser.parse_args()

    r = MyProgram(rargs)
    r.run()

main(sys.argv)
```

Authentication
--------------
WebF has no authentication spec per-se.   Authentication can omitted entirely
(not really recommended) or implemented either by a server-wide
authentication function or by a method in each function class named `authenticate`.
If the server-wide authentication function is registered, it will be called 
for all functions registered.  If an individual function authentication
method exists, it supercedes the server-wide authentication function if one
so exists.  The server-wide authentication function is registered thusly:
```
    websvc.registerAuthentication(myAuthFunction, context)
```
where `myAuthFunction` is a regular python function (not a class) that is called as follows:
```
    def myAuthFunction(functionClassInstance, context, caller, header, args):
        ...
        return (T_or_F, username [, optional dict of err data])
```
`functionClassInstance` is an instance of the function that will be permitted
to continue with the start/next/end call chain if `myAuthFunction` is successful (more on this in a moment).  `context` is any material that you wish passed to 
`myAuthFunction`.

The individual function authentication method signature is nearly the same as the 
server-wide version except it requires no context, the assumption being context
will be taken care of in the `registerFunction` call:
```
class Func1:
    def authenticate(self, caller, headers, args):
        return (T_or_F, username [, optional dict of err data])
```

Both `myAuthFunction` and `authenticate` are passed a dict of the HTTP headers,
a dict of the args parsed from the URL, and a dict `caller` that 
contains the following members:
* name:  A string as interpreted by `HTTPBaseHTTPRequestHander.address_string()`
* ip:    A string, the IP provided eg. `10.23.45.118`
* port:  An int, the outbound port of the caller

The method is free
to perform what tasks necessary, along with material that might have been
set up during `__init__`, to authenticate and allow the rest of the call
to continue.  A very simple
example is basic authentication. where header `Authorization` would have
the value `Basic <base64 enconding of name:password>`.

The function or method must return a tuple with either 2 or 3 elements:

1. True or False.   Indicates success or failure
2. Username.  Whatever user was trying to authenticate, as best as can be
determined by the method.  Can be None.
3. (Optional) dictionary of data to be used in the err message upon failure.
Is not used in the event of success.

Upon success, the rest of the function handler chain (start/next/end) is
executed.
Upon failure, errcode 401 is returned along with an error diagnostic,
additionally populated (and optionally) by the dict of err data described
above.

Like the other class methods, `authenticate` can interact with both the parent
class and the context.  Therefore, more sophisticated schemes like 
cookies and e-tags can be used to maintain state across calls to the function.
For example, authentication on one function can provide a time-bounded 
session cookie that could be reused by different peer functions within the
same service.

Some services may wish to authenticate most functions but leave a small number
unauthenticated.  The strategy here would be to set up a server-wide authentication
function but then in the unauthenticated functions, supply a pass-thru `authenticate`
function:
```
class OKNotToHaveAuthentication:
    def authenticate(self, caller, headers, args):
        return (True, None)
```

License
-------
Copyright (C) {2017,2020} {Buzz Moschetti}

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.


Disclaimer
----------

This software is not supported by MongoDB, Inc. under any of their commercial support subscriptions or otherwise. Any usage of Firehose is at your own risk. Bug reports, feature requests and questions can be posted in the Issues section here on github.
