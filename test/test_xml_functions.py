import syncml_server

import xml.dom.minidom

def test_child_by_name():
    doc="""
    <root>
        <child1></child1>
        <child2></child2>
    </root>
    """
    tree = xml.dom.minidom.parseString(doc).childNodes[0]
    
    ch1 = syncml_server.get_child_by_name(tree, "child1")
    ch3 = syncml_server.get_child_by_name(tree, "child3")

    assert(ch1!=None)
    assert(ch1.tagName=="child1")
    assert(ch3==None)
