# ----------------------------------------------------------------------------
#   NOTES
#
#   !!AI This code frightens me. Refactor the whole thing.
# ----------------------------------------------------------------------------

import tornado.escape
import json
import logging
import base64
import uuid
import re

from ListItem import ListItem
from utilities import validate_base64_parameter, convert_uuid_string_to_base64, convert_base64_to_uuid_string, validate_uuid_string

class List(object):
    REQUIRED_KEYS = ["revision_id", "list_id", "contents", "datetime_edited"]   
    ALL_KEYS = ["revision_id", "list_id", "contents", "datetime_edited", "list_items"]    
    
    def __init__(self, revision_id, list_id, contents, datetime_edited):
        logger = logging.getLogger("List")
        assert validate_uuid_string(revision_id)
        assert validate_uuid_string(list_id)
    
        self.revision_id = revision_id
        self.list_id = list_id
        self.url_safe_list_id = convert_uuid_string_to_base64(self.list_id)
        self.url_safe_revision_id = convert_uuid_string_to_base64(self.revision_id)
        self.contents = contents
        self.datetime_edited = datetime_edited
        
        self.list_items = []
        try:
            contents_decoded = tornado.escape.json_decode(self.contents)
        except:
            logger.exception("JSON decoding exception.")
        else:            
            if "list_items" in contents_decoded:                                
                for list_item_encoded in contents_decoded['list_items']:                    
                    list_item = ListItem.from_json(list_item_encoded)                    
                    if list_item:                        
                        self.list_items.append(list_item)
            
    def get_title(self):
        try:
            contents_decoded = tornado.escape.json_decode(self.contents)
        except:
            logger.exception("JSON decoding exception.")
            return None
        return contents_decoded.get("title", "")            
            
    def create_item(self, title=None, url=None, notes=None):
        if len(self.list_items) == 0:
            new_ident = "1"
        else:
            current_maximum_ident = max(int(elem.ident) for elem in self.list_items)
            new_ident = str(current_maximum_ident + 1)
        if not title:
            title = "List item title"
        list_item = ListItem(new_ident, title, url, notes)
        self.list_items.append(list_item)
        
        contents_decoded = tornado.escape.json_decode(self.contents)
        contents_decoded['list_items'] = [elem.to_json() for elem in self.list_items]
        self.contents = tornado.escape.json_encode(contents_decoded)

    def get_value_from_contents(self, key, default_value=None):
        contents_decoded = tornado.escape.json_decode(self.contents)
        return contents_decoded.get(key, default_value)
        
    def __repr__(self):
        key_value_pairs = ["%s=%s" % (key, getattr(self, key)) for key in self.ALL_KEYS]
        output = "{List. %s}" % (", ".join(key_value_pairs), )
        return output

    @staticmethod
    def is_valid_json_representation(json_string):        
        try:
            decoded = tornado.escape.json_decode(json_string)
        except:
            return False
        if not all(key in decoded for key in List.REQUIRED_KEYS):
            return False
        if not all(elem in decoded['contents'] for elem in ["title", "list_items"]):
            return False
        return True

    @staticmethod
    def from_json(json_string):
        if not List.is_valid_json_representation(json_string):
            return None
        decoded = tornado.escape.json_decode(json_string)
        list_items = []
        if 'list_items' in decoded:            
            for list_item_encoded in decoded['list_items']:
                list_item = ListItem.from_json(list_item_encoded)
                if list_item:
                    list_items.append(list_item)
        if len(list_items) == 0:
            list_items = None
        key_value_pairs = [(key, decoded.get(key)) for key in List.ALL_KEYS]
        key_value_dict = dict(key_value_pairs)
        key_value_dict['list_items'] = list_items
        return List(**key_value_dict)
        
    def to_json(self):
        key_value_pairs = [(key, getattr(self, key)) for key in self.ALL_KEYS]
        decoded = dict(key_value_pairs)
        decoded["list_items"] = [elem.to_json() for elem in self.list_items]
        return tornado.escape.json_encode(decoded)
