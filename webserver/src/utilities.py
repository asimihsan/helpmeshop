import os
import sys
import uuid
import logging
import re
import base64

def normalize_uuid_string(uuid_string):    
    #logging.debug("entry. uuid_string: %s" % (uuid_string, ))
    try:
        uuid_obj = uuid.UUID(uuid_string)
    except:
        return_value = uuid_string
    else:
        return_value = uuid_obj.hex
    #logging.debug("returning: %s" % (return_value, ))
    return return_value    

REGEXP_BASE64 = re.compile("^[A-Za-z0-9-_=]+$")
def validate_base64_parameter(parameter):
    """ Given a string in variable 'parameter' confirm that it is a
    URL safe base64 encoded string. """
    return REGEXP_BASE64.search(parameter)    

def convert_uuid_string_to_base64(uuid_string):
    return base64.urlsafe_b64encode(uuid.UUID(uuid_string).bytes)    

def convert_base64_to_uuid_string(base64_string):
    logger = logging.getLogger("List.convert_base64_to_uuid_string")        
    decoded = base64.urlsafe_b64decode(base64_string)        
    return uuid.UUID(bytes=decoded).hex