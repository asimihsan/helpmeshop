# ----------------------------------------------------------------------------
#   NOTES
#
#   !!AI List modification (reading, deleting) must be based on a revision_id
#   as well as the list_id. This prevents situations where you're modifying
#   a list which has already been modified by someone else, in which case
#   you need to refresh your view of the list before continuing. For now,
#   let's ignore this.
# ----------------------------------------------------------------------------

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
        logger.debug("entry. current_user: %s" % (self.current_user, ))
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

# ----------------------------------------------------------------------------
#   Simplest way of doing this is to:
#   - Read the current list object from the database.
#   - Write new contents into the object.
#   - Write the object back to the database.
#   - Read the current list object from the database.
#
#   !!AI Creating an item is the same as modifying or deleting an item,
#   because items are encoded in the JSON 'contents' field. Hence refactor
#   this code into a base class later.
#
#   !!AI We also need to pass in the revision_id of the list version we 
#   think we're modifying. If this is no longer the newest revision_id
#   then bail out in a manner useful to the user ("You need to refresh").
#   But I want to stop using variables in the path, and use real URL
#   encoding.
# ----------------------------------------------------------------------------
class ListCreateItemHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, list_id_base64):
        logger = logging.getLogger("ListCreateItemHandler.get")
        logger.debug("entry. list_id_base64: %s, current_user: %s" % (list_id_base64, self.current_user, ))
        
        # --------------------------------------------------------------------
        #   Validate inputs.
        # --------------------------------------------------------------------
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)
        if not List.validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        list_id = List.convert_base64_to_uuid_string(str(list_id_base64))                
        logger.debug("list_id: %s" % (list_id, ))
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   At this point we know the list_id is a validly formed, and that
        #   the user is authorized in general to access the service.
        #
        #   However, we do not know if:
        #   - If the list exists.
        #   - The user is the owner of this particular list. This is currently
        #     defined as the user with the first edit, i.e. the creator.
        #
        #   !!AI For now ignore this. This urgently needs implementation.
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Get the current list object.
        # --------------------------------------------------------------------
        list_obj = yield tornado.gen.Task(self.db.read_list,                                
                                          list_id)
        if not list_obj:
            raise tornado.web.HTTPError(404, "Could not find the list.")        
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Add a new list item to the list and then add it to the database.        
        # --------------------------------------------------------------------
        
        # Everything except this line belongs in a base class.
        list_obj.create_item()        
        rc = yield tornado.gen.Task(self.db.update_list,
                                    list_obj.list_id,
                                    self.current_user,
                                    list_obj.contents)
        logger.debug("update_list rc: %s" % (rc, ))      
        if rc != True:
            raise tornado.web.HTTPError(500, "Failed to create a new item in the list.")
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Read in the new list object, confirm that the revision ID has
        #   changed.
        # --------------------------------------------------------------------
        new_list_obj = yield tornado.gen.Task(self.db.read_list,                                
                                              list_id)
        if not new_list_obj:
            raise tornado.web.HTTPError(404, "Could not find the list after updating it.")
        assert(new_list_obj.revision_id != list_obj.revision_id)
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Re-direct to the read list page.
        # --------------------------------------------------------------------
        new_url = self.reverse_url("ListReadHandler", new_list_obj.url_safe_list_id)
        logger.debug("redirecting to: %s" % (new_url, ))
        self.redirect(new_url)
# ----------------------------------------------------------------------------
        
class ListDeleteHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, list_id_base64):
        logger = logging.getLogger("ListDeleteHandler.get")
        logger.debug("entry. current_user: %s" % (self.current_user, ))
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)        
        if not List.validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        list_id = List.convert_base64_to_uuid_string(str(list_id_base64))        
        logger.debug("list_id: %s" % (list_id, ))
        rc = yield tornado.gen.Task(self.db.delete_list,                                
                                    list_id,
                                    self.current_user)
        logger.debug("rc: %s" % (rc, ))
        if rc != True:
            raise tornado.web.HTTPError(400, "Failed to delete the list.")
        self.redirect("/")    

# ----------------------------------------------------------------------------
#   Keep in mind that lists are public, so we don't need to authenticate
#   users who simply want to view a list.
# ----------------------------------------------------------------------------
class ListReadHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, list_id_base64): 
        logger = logging.getLogger("ListDisplayHandler.get")
        logger.debug("entry. list_id_base64: %s" % (list_id_base64, ))
        if not List.validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
            
        list_id = List.convert_base64_to_uuid_string(str(list_id_base64))        
        logger.debug("list_id: %s" % (list_id, ))
        list_obj = yield tornado.gen.Task(self.db.read_list,                                
                                          list_id)
        if not list_obj:
            raise tornado.web.HTTPError(404)
        data = {}
        data['list_obj'] = list_obj
        data['user'] = self.current_user
        
        self.render("read_list.html", **data)     
    