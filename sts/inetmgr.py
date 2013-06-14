# -*- coding: utf-8 -*-
import os
from xml.etree import ElementTree
from . import inetsocket

def connect(socket, conn_type, program, build):
    s = inetsocket.Socket(socket)

    root = ElementTree.Element('Connect')
    ElementTree.SubElement(root, 'ConnType').text = str(conn_type)
    ElementTree.SubElement(root, 'Program').text = str(program)
    ElementTree.SubElement(root, 'Build').text = str(build)
    ElementTree.SubElement(root, 'Process').text = str(os.getpid())
    ElementTree.SubElement(root, 'ProductType').text = '1000'
    ElementTree.SubElement(root, 'AppIndex').text = '1'
    ElementTree.SubElement(root, 'Address').text = socket.getsockname()[0]

    s.send('Sts', 'Connect', body=ElementTree.tostring(root))
    return s
