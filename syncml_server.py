import socket
import BaseHTTPServer
import time

import wbxml

HOST = ''
PORT = 80

STORE_BINARY_REQUEST = False
STORE_SYNCML_REQUEST = True

def get_child_by_name(node, child_name):
    for child in node.childNodes:
        if child.nodeType==child.ELEMENT_NODE and child.tagName==child_name:
            return child
    return None

def get_child_text_by_name(node, child_name):
    child = get_child_by_name( node, child_name )
    for ch in child.childNodes:
        if ch.nodeType==ch.TEXT_NODE:
            return ch.data
    return ""

class SyncMLCommand:

    def parse(self, xml_node):
        self.command = xml_node.tagName
        self.response_expected = True
        if get_child_by_name(xml_node, "NoResp"):
            self.response_expected = False
        self.cmdid   = int( get_child_text_by_name( xml_node, "CmdID" ) )
        self.meta    = {}
        meta = get_child_by_name(xml_node, "Meta")
        if meta:
            for ch in meta.childNodes:
                if ch.childNodes[0].nodeType==ch.TEXT_NODE:
                    self.meta[ch.tagName] = ch.childNodes[0].data.strip()
        print "Command %s with meta %s" % (self.command, self.meta)
        # TODO: parse the optional <Cred> element

        # Just playing a bit here
        if self.command=="Put":
            item = get_child_by_name( xml_node, "Item" )
            data = get_child_by_name( item, "Data" )
            wxd = wbxml.WbXmlParser()
            wxd.parse( data.childNodes[0].data )

            ts = time.strftime("%Y%m%d-%H%M%S")
            f = "devinf-%s.xml" % ts
            devinf = open(f, "w")
            devinf.write( wxd.document.toprettyxml(indent="    ") )
            devinf.close()

    def __repr__(self):
        return "Generic '%s'" % self.command

class Alert(SyncMLCommand):
    alert_codes = {
        100: "DISPLAY",     # The data element type contains content information that should be processed and displayed through the user agent
        200: "TWO-WAY",     # Specifies a client-initiated two-way sync
        201: "SLOW SYNC",   # Specified a client-initiated, two-way slow sync.
    }

    def parse(self, xml_node):
        SyncMLCommand.parse(self, xml_node)
        self.alert_type = int( get_child_by_name("Data") )

    def __repr__(self):
        if self.alert_type in self.alert_codes.keys():
            alert_type_name = self.alert_codes[self.alert_type]
        else:
            alert_type_name = "%u" % self.alert_type
        return "Alert (%s)" % alert_type_name

class Final(SyncMLCommand):
    # 'Final' doesn't have any additional attributes because it isn't a
    # real command but rather more like a flag
    def parse(self, xml_node):
        self.command = "Final"
        self.response_expected = False

class SyncMLCommandFactory:
    parsing_table = {
        "Final" : Final
    }

    @classmethod
    def get_command_from_xml(cls, xml_node):
        command_name = xml_node.tagName
        if command_name in cls.parsing_table.keys():
            command = cls.parsing_table[command_name]()
        else:
            print "Generic parsing for command %s" % command_name
            command = SyncMLCommand()
        command.parse(xml_node)
        return command

class SyncMLMessage:
    def __init__(self, syncml_document):
        header = get_child_by_name( syncml_document, "SyncHdr")
        self.dtd_version      = get_child_text_by_name( header, "VerDTD" ).strip()
        self.protocol_version = get_child_text_by_name( header, "VerProto" ).strip()
        self.sessionid        = int( get_child_text_by_name( header, "SessionID" ) )
        self.msgid            = int( get_child_text_by_name( header, "MsgID" ) )
        body = get_child_by_name( syncml_document, "SyncBody")

        self.commands = []
        for cmd in body.childNodes:
            self.commands.append( SyncMLCommandFactory.get_command_from_xml(cmd) )

class SyncMLSession:
    def __init__(self, id):
        self.id = id

    def handle_message(self, syncml_message):
        for command in syncml_message.commands:
            self.handle_command(command)

    def handle_command(self, syncml_command):
        print syncml_command

class SessionManager:
    """The session manager handles incoming messages and dispatches them to the
    responsible session handler which is a SyncMLSession instance. When an
    incoming message belongs to a new session then the session manager creates
    a corresponding new session handler. The session manager also takes care of
    cleaning up sessions that are finished and have no outstanding requests."""
    def __init__(self):
        self.sessions = {}

    def handle_message(self, syncml_message):
        if syncml_message.sessionid in self.sessions.keys():
            session = self.sessions[syncml_message.sessionid]
        else:
            session = SyncMLSession( syncml_message.sessionid )
            self.sessions[syncml_message.sessionid] = session
        session.handle_message(syncml_message)

class SyncMLRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        content_size = int(self.headers["Content-Length"])
        recv_data = self.rfile.read(content_size)
        wxd = wbxml.WbXmlParser()
        wxd.parse( recv_data )
        message = SyncMLMessage( wxd.document.childNodes[0] )
        print "Incoming Message with SessionID %u" % message.sessionid
        self.server.sm.handle_message( message )

        self.send_response(200)
        self.send_header("Connection", "close")
        self.end_headers()

        ts = time.strftime("%Y%m%d-%H%M%S")
        if STORE_BINARY_REQUEST:
            f = "incoming-%s-%u.bin" % (ts, self.server.counter)
            datalog = open(f, "wb")
            datalog.write( recv_data )
            datalog.close()

        if STORE_SYNCML_REQUEST:
            f = "incoming-%s-%u.xml" % (ts, self.server.counter)
            syncmllog = open(f, "w")
            syncmllog.write( wxd.document.toprettyxml(indent="    ") )
            syncmllog.close()

        self.server.counter += 1

class SyncMLServer(BaseHTTPServer.HTTPServer):
    def __init__(self, *args, **kwargs):
        BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
        self.counter = 0
        self.sm = SessionManager()

def main():
    server_address = (HOST, PORT)
    httpd = SyncMLServer( server_address, SyncMLRequestHandler )
    httpd.serve_forever()

if __name__=="__main__":
    main()
