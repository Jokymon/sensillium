import xml.dom.minidom as xdm

GlobalTokens = {
     0x0 : "SWITCH_PAGE", 
     0x1 : "END", 
     0x2 : "ENTITY", 
     0x3 : "STR_I", 
     0x4 : "LITERAL", 
    0x40 : "EXT_I_0", 
    0x41 : "EXT_I_1", 
    0x42 : "EXT_I_2", 
    0x43 : "PI", 
    0x44 : "LITERAL_C", 
    0x80 : "EXT_T_0", 
    0x81 : "EXT_T_1", 
    0x82 : "EXT_T_2", 
    0x83 : "STR_T", 
    0x84 : "LITERAL_A", 
    0xC0 : "EXT_0", 
    0xC1 : "EXT_1", 
    0xC2 : "EXT_2", 
    0xC3 : "OPAQUE", 
    0xC4 : "LITERAL_AC", 
}

PublicIdentifiers = {
    0 : "Identifier encoded in stringtable", 
    1 : "Unknown or missing public identifier.", 
    2 : "-//WAPFORUM//DTD WML 1.0//EN", 
    3 : "-//WAPFORUM//DTD WTA 1.0//EN", 
    4 : "-//WAPFORUM//DTD WML 1.1//EN", 
    5 : "-//WAPFORUM//DTD SI 1.0//EN", 
    6 : "-//WAPFORUM//DTD SL 1.0//EN", 
    7 : "-//WAPFORUM//DTD CO 1.0//EN", 
    8 : "-//WAPFORUM//DTD CHANNEL 1.1//EN", 
    9 : "-//WAPFORUM//DTD WML 1.2//EN", 
}


def peekByte(data):
    if data=="":
        return 1
    else:
        return ord(data[0])

def extractByte(data):
    """Extract the first byte of the given data and return a tuple consisting
of the extracted byte and the rest of the data"""
    return ( ord(data[0]), data[1:] )

def extractMultiByte(data):
    (byte, data) = extractByte(data)
    counter = 1
    value = (byte & 0x7f)
    while (byte>>7)==1 and len(data)!=0 and counter<4:
        (byte, data) = extractByte(data)
        value = (value<<7) + (byte & 0x7f)
        counter += 1
    return (value, data)

def createMultiByte(value):
    if (value<0 or value>2**32):
        raise ValueError("Cannot convert %u into a multibyte string" % value)
    s = ""
    remainder = value
    while remainder>0:
        ch = remainder & 0x7f
        remainder = remainder >> 7
        if remainder>0:
            ch |= 0x80
        s += "%c" % ch
    if len(s)==0:
        s = "\0"
    return s

class WbXmlParser:
    """WBXML document parser implementation based on
    http://polylab.sfu.ca/spacesystems/teach/wireless/wap/documents/SPEC-WBXML-19991104.pdf"""
    def __init__(self):
        self.document = None
        self.tag_table = None

    def parse(self, document):
        self._parseStart(document)

    def _parseStart(self, document):
        self.document = xdm.Document()

        self._current_node = self.document
        self._current_page = 0

        document = self._parseVersion(document)
        document = self._parsePublicId(document)
        document = self._parseCharset(document)
        document = self._parseStringTable(document)
        document = self._parseBody(document)
        return document

    def _parseVersion(self, document):
        (self.version, document) = extractByte(document)
        return document

    def _parsePublicId(self, document):
        if peekByte(document)==0:
            # we have an index into the string table, only remember the index
            # here
            (zero, document) = extractByte(document)
            (publicid, document) = extractMultiByte(document)
            self.publicid = publicid
        else:
            (publicid, document) = extractMultiByte(document)
            self.publicid = PublicIdentifiers[publicid]
        return document

    def _parseCharset(self, document):
        (charset, document) = extractMultiByte(document)
        import iana_charsets
        if charset in iana_charsets.MIBenum.keys():
            charset = iana_charsets.MIBenum[charset]
        else:
            charset = "%u" % charset
        self.charset = charset
        return document

    def _parseStringTable(self, document):
        (length, document) = extractMultiByte(document)
        self.stringtable = document[:length]

        # TODO: This part only works if the only entry in the stringtable is
        # actually the tag table to use. We should probably adapt this to use
        # the publicId to find the tag table. Also we need to split the string
        # table according to the WBXML specification
        import wbxml_tables
        self.tag_table = wbxml_tables.tag_tables[self.stringtable]
        self.tag_table = convert_to_lookup(self.tag_table)

        return document[length:]

    def _parseBody(self, document):
        code = peekByte(document)
        # processing *pi part of 'body'
        while code in GlobalTokens.keys() and GlobalTokens[code]=="PI":
            document = self._parsePI(self, document)
            code = peekByte(document)
        document = self._parseElement(document)

    def _parseElement(self, document):
        # processing initial switchPage part of 'element'
        (code, document) = extractByte(document)
        if code in GlobalTokens.keys() and GlobalTokens[code]=="SWITCH_PAGE":
            (newpage, document) = extractByte(document)
            self._current_page = newpage
            (code, document) = extractByte(document)
        # processing 'stag' in 'element'
        if code in GlobalTokens.keys() and GlobalTokens[code]=="LITERAL":
            raise "LITERAL token not yet supported"

        has_attributes = (code>>7)==1
        is_empty = ((code>>6) & 1)==0
        code = code & 0x3f

        # start with content processing
        newnode = self.document.createElement(self.tag_table[self._current_page][code])
        self._current_node.appendChild(newnode)
        old_root = self._current_node
        self._current_node = newnode

        if has_attributes:
            # TODO: implement attributes
            print "Element has attributes"
            document = self._parseAttribute(document)

        if not is_empty:
            next_code = peekByte(document)
            while not next_code in GlobalTokens.keys() or GlobalTokens[next_code]!="END":
                document = self._parseContent(document)
                next_code = peekByte(document)
            if next_code in GlobalTokens.keys() and GlobalTokens[next_code]=="END":
                (next_code, document) = extractByte(document)

        self._current_node = old_root
        return document

    def _parseContent(self, document):
        code = peekByte(document)
        # some elements can have switch page instruction, so just capture it here
        if code in GlobalTokens.keys() and GlobalTokens[code]=="SWITCH_PAGE":
            (code, document) = extractByte(document)
            (newpage, document) = extractByte(document)
            self._current_page = newpage
            code = peekByte(document)
        # now check the next token
        if not code in GlobalTokens.keys():
            document = self._parseElement(document)
        elif GlobalTokens[code]=="STR_I":
            document = self._parseString(document)
        elif GlobalTokens[code]=="STR_T":
            raise "Tableref string token currently not supported"
        elif GlobalTokens[code]=="OPAQUE":
            document = self._parseOpaque(document)
        else:
            print "Unhandled token: %s" % GlobalTokens[code]
        return document

    def _parsePI(self, document):
        print "Parse PI"

    def _parseString(self, document):
        (code, document) = extractByte(document)

        eos = document.index("\x00")

        newnode = self.document.createTextNode(document[:eos])
        self._current_node.appendChild(newnode)

        return document[eos+1:]

    def _parseOpaque(self, document):
        (code, document) = extractByte(document)
        assert code == 0xc3
        (length, document) = extractMultiByte(document)

        newnode = self.document.createTextNode(document[:length])
        self._current_node.appendChild(newnode)

        return document[length:]

    def parse_file(self, file_name):
        f = open(file_name, "rb")
        data = f.read()
        f.close()
        self.parse(data)

class WbXmlDocument:
    def __init__(self, wbxmlversion=2, publicid="-//SYNCML//DTD SyncML 1.2//EN", charset="UTF-8"):
        self.wbxmlversion = wbxmlversion
        self.publicid = publicid
        self.charset = charset
        import wbxml_tables
        self.tag_table = convert_to_reverse_lookup( wbxml_tables.tag_tables[publicid] )
        self.code_page = 0

    def write_xml_to_file(self, xml_root, outfile):
        output = open(outfile, "wb")
        output.write("%c" % self.wbxmlversion)
        # for the moment the public ID is always index 0 in the string table
        output.write("\0")
        output.write( createMultiByte(0) )

        # TODO: error handling for unknown, wrong or missing charset name
        import iana_charsets
        inv_MIBenum = dict((v, k) for k, v in iana_charsets.MIBenum.iteritems())
        output.write( createMultiByte(inv_MIBenum[self.charset]) )
        self._write_strtbl(output)

        self._convert_xml_node(xml_root, output)

        output.close()

    def _write_strtbl(self, out):
        length = len(self.publicid)
        out.write( createMultiByte(length) )
        out.write( self.publicid )

    def _convert_xml_node(self, xml_node, out):
        if xml_node.nodeType==xml_node.ELEMENT_NODE:
            self._convert_xml_element(xml_node, out)
        elif xml_node.nodeType==xml_node.TEXT_NODE:
            self._convert_xml_text_node(xml_node, out)
        else:
            print "Not converting unknown element type %u" % xml_node.nodeType

    def _convert_xml_text_node(self, xml_text_node, out):
        # we always insert text as inline
        text = xml_text_node.data.strip()
        if text!="":
            out.write("\x03")   # STR_I
            out.write(text)
            out.write("\0")

    def _convert_xml_element(self, xml_element, out):
        (page, code) = self.tag_table[ xml_element.tagName ]
        if page!=self.code_page:
            out.write("\0%c" % page) # SWITCH_PAGE
            self.code_page = page
        if xml_element.hasAttributes():
            code |= 0x80
        if len( xml_element.childNodes ) > 0:
            code |= 0x40
        out.write("%c" % code)
        # TODO: encode attributes
        
        if len( xml_element.childNodes ) > 0:
            for child in xml_element.childNodes:
                self._convert_xml_node(child, out)
            out.write("\x01") # END code

def convert_to_lookup(c_table):
    lookup = {}     # each hash element represents a code page containing a lookup dictionary for the codes
    for item in c_table:
        if not lookup.has_key(item[1]):
            lookup[item[1]] = {}
        lookup[item[1]][item[2]] = item[0]
    return lookup

def convert_to_reverse_lookup(c_table):
    lookup = {}     # maps a tag to a code page/code number tuple
    for item in c_table:
        lookup[item[0]] = ( item[1], item[2] )
    return lookup

if __name__=="__main__":
    assert extractMultiByte("\x81\x20")[0]==0xa0

    import sys
    wxd = WbXmlParser()
    wxd.parse_file(sys.argv[1])
    print "Version:  %u" % wxd.version
    print "PublicId: %s" % int(wxd.publicid)
    print "Charset:  %s" % wxd.charset
    print "Stringtable: %s" % wxd.stringtable
    print wxd.document.toprettyxml()

    #xml = xdm.parse(sys.argv[1])
    #wxd = WbXmlDocument()
    #wxd.write_xml_to_file( xml.childNodes[0], "test.bin" )
