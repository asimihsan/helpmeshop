# ----------------------------------------------------------------------------
#   NOTES
#
#   !!AI List modification (reading, deleting) must be based on a revision_id
#   as well as the list_id. This prevents situations where you're modifying
#   a list which has already been modified by someone else, in which case
#   you need to refresh your view of the list before continuing. For now,
#   let's ignore this.
#
#   #!!AI All list modification operations must use POSTs. This will force
#   Tornado to check XSRF. Of course, we could hack our own XSRF using GETs,
#   but why? Just start POSTing. Besides, GETs are idempotent.
# ----------------------------------------------------------------------------

import logging
import base64
import pprint
import tornado
import tornado.escape

from model.List import List
from base_request_handlers import BasePageHandler
from utilities import validate_base64_parameter, convert_uuid_string_to_base64, convert_base64_to_uuid_string, normalize_uuid_string
        
class ListsHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):    
        logger = logging.getLogger("ListsHandler.get")
        logger.debug("entry.")
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)    
        data = {}
        data['user'] = tornado.escape.xhtml_escape(self.current_user)
        lists = yield tornado.gen.Task(self.db.get_lists, self.current_user)
        for list_obj in lists:
            contents_decoded = tornado.escape.json_decode(list_obj.contents)
            setattr(list_obj, "title", contents_decoded["title"])
        logger.debug("lists:\n%s" % (pprint.pformat(lists), ))        
        data['lists'] = lists 
        data['title'] = "Help Me Shop"      
        self.render("lists.html", **data)   

class ListCreateHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        logger = logging.getLogger("ListCreateHandler.post")
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
        
        new_url = self.reverse_url("ListsHandler")
        logger.debug("Redirecting to: %s" % (new_url, ))
        self.redirect(new_url)        

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
    def post(self, list_id_base64):
        logger = logging.getLogger("ListCreateItemHandler.post")
        logger.debug("entry. list_id_base64: %s, current_user: %s" % (list_id_base64, self.current_user, ))
        
        # --------------------------------------------------------------------
        #   Gather inputs.
        # --------------------------------------------------------------------
        list_id_base64 = str(list_id_base64)
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Validate inputs.
        # --------------------------------------------------------------------        
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)        
        if not validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        list_id = convert_base64_to_uuid_string(str(list_id_base64))                
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
    def post(self, list_id_base64):
        logger = logging.getLogger("ListDeleteHandler.post")
        logger.debug("entry. current_user: %s" % (self.current_user, ))
        
        # --------------------------------------------------------------------
        #   Gather inputs.
        # --------------------------------------------------------------------
        list_id_base64 = str(list_id_base64)
        # --------------------------------------------------------------------        
        
        # --------------------------------------------------------------------
        #   Validate inputs.
        # --------------------------------------------------------------------
        if not self.current_user:
            logging.debug("User is not authorized.")
            raise tornado.web.HTTPError(403)                
        if not validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        # --------------------------------------------------------------------
        
        list_id = convert_base64_to_uuid_string(str(list_id_base64))        
        logger.debug("list_id: %s" % (list_id, ))
        rc = yield tornado.gen.Task(self.db.delete_list,                                
                                    list_id,
                                    self.current_user)
        logger.debug("rc: %s" % (rc, ))        
        if rc != True:
            raise tornado.web.HTTPError(400, "Failed to delete the list.")
            
        new_url = self.reverse_url("ListsHandler")
        logger.debug("Redirecting to: %s" % (new_url, ))
        self.redirect(new_url)

# ----------------------------------------------------------------------------
#   Keep in mind that lists are public, so we don't need to authenticate
#   users who simply want to view a list.
# ----------------------------------------------------------------------------
class ListReadHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, list_id_base64): 
        logger = logging.getLogger("ListReadHandler.get")
        logger.debug("entry. list_id_base64: %s" % (list_id_base64, ))
        
        # --------------------------------------------------------------------
        #   Gather and validate inputs.
        # --------------------------------------------------------------------
        list_id_base64 = str(list_id_base64)
        if not validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")                    
        list_id = convert_base64_to_uuid_string(str(list_id_base64))        
        logger.debug("list_id: %s" % (list_id, ))
        # --------------------------------------------------------------------
        
        list_obj = yield tornado.gen.Task(self.db.read_list,                                
                                          list_id)
        if not list_obj:
            raise tornado.web.HTTPError(404)
        data = {}
        data['list_obj'] = list_obj
        data['user'] = self.current_user                
        self.render("read_list.html", **data)     
        
class ListUpdateItemHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, list_id_base64, item_ident):
        logger = logging.getLogger("ListUpdateItemHandler.post")
        logger.debug("entry. list_id_base64: %s, item_ident: %s" % (list_id_base64, item_ident))
        logger.debug("request: %s" % (self.request, ))
        logger.debug("request arguments\n%s" % (pprint.pformat(self.request.arguments), ))
        logger.debug("request files: %s" % (self.request.files, ))
        
        # --------------------------------------------------------------------
        #   Gather the arguments. GET arguments come for free in the
        #   function call.
        # --------------------------------------------------------------------
        revision_id_base64 = str(self.get_argument("list_revision_id"))
        logger.debug("revision_id_base64: %s" % (revision_id_base64, ))
        list_id_base64 = str(list_id_base64)
        # --------------------------------------------------------------------        
        
        # --------------------------------------------------------------------
        #   Validate inputs.
        # --------------------------------------------------------------------
        if not self.current_user:            
            raise tornado.web.HTTPError(403, "User is not authorized.")        
        if not validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        if not item_ident.isdigit():
            raise tornado.web.HTTPError(400, "Item ident is malformed.")
        if not validate_base64_parameter(revision_id_base64):
            raise tornado.web.HTTPError(400, "Revision identifier is malformed.")
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Parse inputs.
        # --------------------------------------------------------------------
        list_id = convert_base64_to_uuid_string(str(list_id_base64))        
        revision_id = convert_base64_to_uuid_string(str(revision_id_base64))        
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Return to the view that shows the list being read.
        # --------------------------------------------------------------------
        new_url = self.reverse_url("ListReadHandler", list_id_base64)
        logger.debug("redirecting to: %s" % (new_url, ))
        self.redirect(new_url)
        # --------------------------------------------------------------------
    
class ListDeleteItemHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, list_id_base64, item_ident):
        logger = logging.getLogger("ListDeleteItemHandler.post")
        logger.debug("entry. list_id_base64: %s, item_ident: %s" % (list_id_base64, item_ident))
        
        # --------------------------------------------------------------------
        #   Gather the arguments. GET arguments come for free in the
        #   function call.
        # --------------------------------------------------------------------
        revision_id_base64 = str(self.get_argument("list_revision_id"))
        logger.debug("revision_id_base64: %s" % (revision_id_base64, ))
        list_id_base64 = str(list_id_base64)
        # --------------------------------------------------------------------        
        
        # --------------------------------------------------------------------
        #   Validate inputs.
        # --------------------------------------------------------------------
        if not self.current_user:            
            raise tornado.web.HTTPError(403, "User is not authorized.")        
        if not validate_base64_parameter(list_id_base64):
            raise tornado.web.HTTPError(400, "List identifier is malformed.")
        if not item_ident.isdigit():
            raise tornado.web.HTTPError(400, "Item ident is malformed.")
        if not validate_base64_parameter(revision_id_base64):
            raise tornado.web.HTTPError(400, "Revision identifier is malformed.")
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Parse inputs.
        # --------------------------------------------------------------------
        list_id = convert_base64_to_uuid_string(str(list_id_base64))        
        revision_id = convert_base64_to_uuid_string(str(revision_id_base64))        
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   Return to the view that shows the list being read.
        # --------------------------------------------------------------------
        new_url = self.reverse_url("ListReadHandler", list_id_base64)
        logger.debug("redirecting to: %s" % (new_url, ))
        self.redirect(new_url)
        # --------------------------------------------------------------------