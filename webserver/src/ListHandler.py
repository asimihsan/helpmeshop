import tornado
import tornado.escape

import logging
import base64

from model.List import List

from base_request_handlers import BasePageHandler

class ListCreateHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):
        logger = logging.getLogger("ListCreateHandler.get")
        logger.debug("entry.")
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)
        new_list_contents = {"title": "New list",
                             "list_items": []}
        new_list_id = yield tornado.gen.Task(self.db.create_list,
                                             self.current_user,
                                             tornado.escape.json_encode(new_list_contents))
        logger.debug("new_list_id: %s" % (new_list_id, ))
        self.redirect("/")

class ListDisplayHandler(BasePageHandler):
    def get(self, list_id_base64): 
        logger = logging.getLogger("ListDisplayHandler.get")
        logger.debug("entry. list_id_base64: %s" % (list_id_base64, ))
        if not List.validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        list_id = List.convert_base64_to_uuid_string(str(list_id_base64))        
        logger.debug("list_id: %s" % (list_id, ))
        data = {}
        data['user'] = None
        if self.current_user:
            data['user'] = tornado.escape.xhtml_escape(self.current_user)
        
        self.render("list.html", **data)     
    