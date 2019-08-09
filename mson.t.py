import sys

from mson import mson


def showList(l, lvl):
    for n in range(0, len(l)):
        emit(l[n], str(n), lvl)

def showMap(m, lvl):
    for k in m:
        emit(m[k], k, lvl)

def emit(obj, fld, lvl):
    cn = obj.__class__.__name__
    print(' '*lvl, fld, cn , end="")
    if cn == "dict":
        print()
        showMap(obj, lvl + 1)
    elif cn == "list":
        print()
        showList(obj, lvl + 1)
    else:
        print(obj)


def pt(s, inmode, outmode):
#m = mson.mson.parse(s, mson.mson.PURE)
#    print s
    m = mson.parse(s, inmode)
    #showMap(m,0)
    #mson.write(sys.stdout, m, outmode)
    mson.write(sys.stdout.buffer, m, outmode)  # buffer gives a bytes sink instead of unicode sink



for s in [

# Ah hA!  Single quotes do not -- and CANNOT -- be escaped with \
"""
{"a":"\\"quoted\\" and 'quoted'"}
"""

,
"""
{"a":"foo", "K_int":3, "K_dbl":3.0, "z":{"z1":{"z2":22}}}
"""
,
"""
{
"typeLong1":8888123123123123123, 
"typeStr2":"8888123123123123123",
"typeLong3":{"$numberLong":"8888123123123123123"},

"K_int":3, "K_dbl":3.0, "z":{"z1":{"z2":{"$numberLong":"22"}}}
}
"""

,
"""
{
        "d_iso": {"$date":"2017-01-28T21:47:46.333"},
     "d_iso_wZ": {"$date":"2017-01-28T21:47:46.333Z"},
    "d_str_int": {"$date": "1485640066333"},
  "d_plain_int": {"$date": 1485640066333}
}
"""

,
"""
{"type_list":[  {"$date":"2015-09-27T22:31:58.542Z"}, 34, "A" ] }
"""

,
"""
{"type_binary": {"$binary":"c29tZXRoaW5n","$type":"00"}}
"""


,
"""
{"dbl": 13.0, "int": 13}
"""

,
"""
{
"type_long": 44444444444444444
,"type_2_31": 2147483648
,"type_2_31_min1": 2147483647
,"type_2_31_plus1": 2147483649
,"type_neg_2_31": -2147483648
,"type_neg_2_31_min1": -2147483647
,"type_neg2_31_plus1": -2147483649
,"type_date": "2017-01-28T21:47:46.333"
,"type_date_M": {"$date":"2017-01-28T21:47:46.333"}
,"type_decimal": 99999999999.99
}
"""

]:
    pt(s, mson.PURE, mson.MONGO)
    print()




