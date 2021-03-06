import urllib2, re, time

IANA_URL = "http://www.iana.org/assignments/character-sets"

f = urllib2.urlopen(IANA_URL)
lines = f.readlines()
f.close()

out_file = open("iana_charsets.py", "w")
out_file.write( "# This file was generated by generate_iana_charsets.py on %s\n" % time.strftime("%Y-%m-%d %H:%M") )
out_file.write( "# The data is based on %s\n" % IANA_URL )
out_file.write( "\n" )
out_file.write( "MIBenum = {\n" )

name_pattern = re.compile("Name: ([a-zA-Z0-9_:\.\-]+)")
mibenum_pattern = re.compile("MIBenum: ([0-9]+)")
name = ""
for l in lines:
    m = name_pattern.match(l)
    if m:
        name = m.group(1)
    n = mibenum_pattern.match(l)
    if n:
        mibenum = n.group(1)
        out_file.write( "    %s : \"%s\",\n" % (mibenum, name) )

out_file.write( "}\n" )
out_file.write( "\n" )
out_file.close()
