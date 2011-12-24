# ----------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# File: bristol_board/src/mockup/test_client.py
#
# Run functional verification tests against the server.
#
# Right now assumes that create_table.py has been executed with
# RANDOM_SEED = 0.
# ----------------------------------------------------------------------

import os
import sys
import json
import httplib2
import pprint
import logging

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
APP_NAME = 'test_client'
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
# ----------------------------------------------------------------------

SERVER = "192.168.0.195"
PORT = "8080"
BASE_URL = "http://%s:%s" % (SERVER, PORT)
USERNAME = "user0"
PASSWORD = "pass0"

def create_condition_report(h, username=USERNAME, password=PASSWORD, compression=True):
    logger = logging.getLogger("%s.create_condition_report" % (APP_NAME, ))
    logger.debug("entry")
    document_blob = {"title": "Title of the art",
                     "type": "Painting"}
    data = {"api_version": "1",
            "username": username,
            "password": password,
            "document_blob": document_blob}
    headers = {"content-type": "application/json"}
    if not compression:
        headers["Accept-Encoding"] = "identity"
    resp, content = h.request("%s/condition_report" % (BASE_URL, ),
                              "POST",
                              body=json.dumps(data),
                              headers=headers)
    logger.debug("\n\nresp:\n%s" % (pprint.pformat(resp), ))
    logger.debug("\n\ncontent:\n%s" % (pprint.pformat(content), ))
    return (resp, content)
    #import pdb; pdb.set_trace()

def get_condition_reports_by_username(h, username=USERNAME, password=PASSWORD, compression=True):
    logger = logging.getLogger("%s.get_condition_reports_by_username" % (APP_NAME, ))
    logger.debug("entry")
    data = {"api_version": "1",
            "username": username,
            "password": password,
            "get_using": "username"}
    headers = {"content-type": "application/json"}
    if not compression:
        headers["Accept-Encoding"] = "identity"    
    resp, content = h.request("%s/condition_report" % (BASE_URL, ),
                              "GET",
                              body=json.dumps(data),
                              headers=headers)
    logger.debug("\n\nresp:\n%s" % (pprint.pformat(resp), ))
    logger.debug("\n\ncontent:\n%s" % (pprint.pformat(content), ))
    return (resp, content)
    
if __name__ == "__main__":    
    logger.setLevel(logging.DEBUG)
    httplib2.debuglevel = 1
    logger.info("starting")
    
    h = httplib2.Http()    
    #(resp, content) = create_condition_report(h)
    #(resp, content) = create_condition_report(h, password="garbage")
    #(resp, content) = import pdb; pdb.set_trace()
    
    #(resp, content) = get_condition_reports_by_username(h, compression=False)
    #import pdb; pdb.set_trace()
    
    (resp, content) = get_condition_reports_by_username(h, compression=True)
    import pdb; pdb.set_trace()
    
    #(resp, content) = get_condition_reports_by_username(h, password="garbage", compression=True)
    
    