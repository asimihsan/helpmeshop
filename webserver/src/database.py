# ----------------------------------------------------------------------------
#   TODO
#
#!!AI Surely sometimes I want to fetch rows from a cursor as dicts?
# Fix the caching DB caller.
# ----------------------------------------------------------------------------

import tornado
import tornado.gen
from tornado.options import define, options

import os
import sys
import logging
import cPickle as pickle
import hashlib
import base64
import uuid
import bz2

import momoko
import redis

from model.List import List
from utilities import normalize_uuid_string

# ----------------------------------------------------------------------------
#   Configuration constants.
# ----------------------------------------------------------------------------
define("database_name", default=None, help="Name of database.")
define("database_username", default=None, help="Username for database.")
define("database_password", default=None, help="Password for database.")
define("database_host", default=None, help="Hostname for database.")
define("database_port", default=None, type=int, help="Port for database.")
define("database_min_conn", default=None, type=int, help="Minimum number of database connections.")
define("database_max_conn", default=None, type=int, help="Maximum number of database connections.")
define("database_cleanup_timeout", default=None, type=int, help="Database cleanup timeout.")

define("redis_hostname", default=None, help="Redis server hostname")
define("redis_port", default=None, type=int, help="Redis server port")
define("redis_database_id_for_database_results", default=None, type=int, help="Database ID for database statements")
# ----------------------------------------------------------------------------
        
# ----------------------------------------------------------------------------
#   So how does database caching work?
#   
#`  We use redis. What do we cache? We want to map (statement, args) to
#   (value). This is easy, and is done in execute_cached_db_statement().
#   The much harder problem is what parts of the cache do we delete
#   after executing operations that modify the database (create, update,
#   or delete relevant elements)?
#
#   There are a spectrum of solutions here. The easier, but most useless,
#   solution would be to empty the entire cache on any operation that
#   changes the state of the database. This is the easiest to execute, but
#   is a bit brutal.
#
#   Another easy solution would be to use very low time-to-live (TTL)
#   values on all cache elements, and never delete any elements. But this
#   doesn't feel like a cache, and seems hacky.
#
#   The hardest solution is to find every single statement that could
#   be affected by a given database modification. There will be tradeoffs
#   between time and space here (we use more memory in the cache to make
#   the operation cheaper) but the worse part is that we'd need to
#   hard code a lot of logic here, I think.
#   
#   I've accepted the hard solution, and to hard code a lot of logic.
# ----------------------------------------------------------------------------
class DatabaseManager(object):
    # ------------------------------------------------------------------------
    #   Database statements related to user authentication and CRUD.
    # ------------------------------------------------------------------------   
    GET_USER_ID_FROM_GOOGLE_EMAIL = """SELECT helpmeshop_user_id FROM auth_google WHERE email = %s;"""
    CREATE_AUTH_GOOGLE = """INSERT INTO auth_google (email, helpmeshop_user_id, first_name, last_name, name, locale) VALUES (%s, %s, %s, %s, %s, %s);"""    
    GET_USER_ID_FROM_FACEBOOK_ID = """SELECT helpmeshop_user_id FROM auth_facebook WHERE id = %s;"""
    CREATE_AUTH_FACEBOOK = """INSERT INTO auth_facebook (id, helpmeshop_user_id, link, access_token, locale, first_name, last_name, name, picture)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"""    
                              
    GET_USER_ID_FROM_TWITTER_USERNAME = """SELECT helpmeshop_user_id FROM auth_twitter WHERE username = %s;"""
    CREATE_AUTH_TWITTER = """INSERT INTO auth_twitter (username, helpmeshop_user_id, profile_image_url) VALUES (%s, %s, %s);"""    
    
    GET_USER_ID_FROM_BROWSERID_EMAIL = """SELECT helpmeshop_user_id FROM auth_browserid WHERE email = %s;"""
    CREATE_AUTH_BROWSERID = """INSERT INTO auth_browserid (email, helpmeshop_user_id) VALUES (%s, %s);"""   
    
    GET_USER_ID_FROM_API_SECRET_KEY = """SELECT helpmeshop_user_id FROM auth_api WHERE api_secret_key = %s;"""
    CREATE_AUTH_API = """INSERT INTO auth_api (api_secret_key, helpmeshop_user_id) VALUES (%s, %s);"""   
    
    GET_ROLE_ID = """SELECT role_id FROM role WHERE role_name = %s;"""    
    CREATE_USER_AND_RETURN_USER_ID = """INSERT INTO helpmeshop_user (helpmeshop_user_id, role_id)
                                        VALUES (uuid_generate_v4(), %s)
                                        RETURNING helpmeshop_user_id;"""    
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------
    #   Database statements for list CRUD.
    #
    #   We define the owner of a list as the user that created the list,
    #   i.e. the user who has the oldest datetime_edited for all revisions
    #   of a given list.
    # ------------------------------------------------------------------------
    CREATE_LIST_WITH_USER_ID_AND_CONTENTS_RETURN_LIST_ID = """
        INSERT INTO list (revision_id, list_id, helpmeshop_user_id, datetime_edited, contents)
        VALUES (uuid_generate_v4(), uuid_generate_v4(), %s, now(), %s)
        RETURNING list_id;"""
    UPDATE_LIST_WITH_LIST_ID_AND_USER_ID_AND_CONTENTS = """
        INSERT INTO list (revision_id, list_id, helpmeshop_user_id, datetime_edited, contents)
        VALUES (uuid_generate_v4(), %s, %s, now(), %s);"""        
    GET_LATEST_LISTS_WITH_USER_ID = """
        SELECT L.revision_id, L.list_id, L.contents, L.datetime_edited
        FROM list L
        INNER JOIN (
            SELECT list_id, MAX(datetime_edited) AS datetime_edited
            FROM list
            WHERE helpmeshop_user_id = %s
            GROUP BY list_id
        ) X
        ON X.list_id = L.list_id AND
           X.datetime_edited = L.datetime_edited;"""
    GET_LATEST_LIST_WITH_LIST_ID = """
        SELECT L.revision_id, L.list_id, L.contents, L.datetime_edited
        FROM list L
        INNER JOIN (
            SELECT list_id, MAX(datetime_edited) AS datetime_edited
            FROM list
            GROUP BY list_id
        ) X
        ON X.list_id = L.list_id AND
           X.datetime_edited = L.datetime_edited
        WHERE L.list_id = %s;"""
    DELETE_LIST_WITH_LIST_ID = """DELETE FROM list WHERE list_id = %s;"""
    GET_OWNER_USER_ID_WITH_LIST_ID = """
        SELECT L.helpmeshop_user_id
        FROM LIST L
        INNER JOIN (
            SELECT list_id, MIN(datetime_edited) AS datetime_edited
            FROM list
            WHERE list_id = %s
            GROUP BY list_id
        ) X
        ON X.list_id = L.list_id AND
           X.datetime_edited = L.datetime_edited;"""        
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------
    #   If a 
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------

    def __init__(self):
        self.db = momoko.AsyncClient({
            'host': options.database_host,
            'port': options.database_port,
            'database': options.database_name,
            'user': options.database_username,
            'password': options.database_password,
            'min_conn': options.database_min_conn,
            'max_conn': options.database_max_conn,
            'cleanup_timeout': options.database_cleanup_timeout})

        # Start a connection to the redis to the database ID that stores
        # cached versions of database read queries. Delete all of them.
        self.r = redis.StrictRedis(host=options.redis_hostname,
                                   port=options.redis_port,
                                   db=options.redis_database_id_for_database_results)
        self.r.flushdb()            

    def expire_cache(self, pattern):
        """ Expire all keys in the catch that contain 'pattern',
        which is a string.  For a given database query call this
        function repeatedly for every argument you used.
        
        This function will not normalize UUIDs for you, i.e.
        remove the dashes! Do this yourself!"""
        logger = logging.getLogger("DatabaseManager.expire_cache")
        logger.debug("entry. pattern: %s" % (pattern))
        substring_pattern = "*%s*" % (pattern, )
        for key in self.r.keys(substring_pattern):
            self.r.delete(key)
        
    @tornado.gen.engine
    def execute_cached_db_statement(self,
                                    statement,
                                    args,
                                    statement_name,
                                    callback):
        """ Execute a database statement. Use a redis-based cache.
        Only call this function for database queries that gather
        data, rather than modify data, i.e. SELECT statements.
        
        This will return the full result of cursor.fetchall(). If
        you need access to the actual cursor don't use this
        function, as cursors can't be pickled.
        
        statement is a string of the database query you want to
        execute. args is a tuple of arguments. statement_name
        is a string of the variable that the database statement
        string comes from.
        """
        
        logger = logging.getLogger("DatabaseManager.execute_cached_db_statement")
        logger.debug("entry. statement_name: %s, args: %s" % (statement_name, args))
        
        # --------------------------------------------------------------------
        #   Use, or create, an element in the cache that maps
        #   (args, statement) to (value). If this is a cache miss then
        #   execute the database query to get the value.
        #
        #   For each arg that looks like a UUID remove all the dashes
        #   from it. This helps with future lookups.
        # --------------------------------------------------------------------        
        args_with_normalized_uuids = [normalize_uuid_string(elem) for elem in args]
        logger.debug("args_with_normalized_uuids: %s" % (args_with_normalized_uuids, ))        
        key_elems = args_with_normalized_uuids + [statement_name]        
        key = ":".join(key_elems)
        value_pickled = self.r.get(key)        
        if not value_pickled:
            logger.debug("cache miss")
            cursor = yield tornado.gen.Task(self.db.execute, statement, args)
            value = cursor.fetchall()
            self.r.setex(key, 60 * 60 * 24, pickle.dumps(value, -1))
        else:
            logger.debug("cache hit")
            value = pickle.loads(value_pickled)
        # --------------------------------------------------------------------        
        
        logger.debug("value: %s" % (value, ))
        callback(value)

    def extract_one_value_from_one_or_zero_rows(self, cursor_or_rows):
        """ If you execute a query that SELECTs for one value, and expects only
        one row in the results, then use this function.
        
        If there are zero rows in the output then the function will return None.
        Else, the function will assert if these conditions are not true.
        Else, it will return the single value.
        
        In order to support execute_cached_db_statement() we allow either a cursor
        or a list of tuples (i.e. rows) to be passed in. If the object
        has a "fetchall" method we assume its a cursor and call this method.
        """
        logger = logging.getLogger("DatabaseManager.extract_one_value_from_one_or_zero_rows")                
        logger.debug("entry. cursor_or_rows: %s" % (cursor_or_rows, ))
        if hasattr(cursor_or_rows, "fetchall"):
            logger.debug("cursor_or_rows has fetchall method")
            results = cursor_or_rows.fetchall()
        else:
            logger.debug("cursor_or_rows does not have fetchall method")
            results = cursor_or_rows
        logger.debug("results: %s" % (results, ))
        if len(results) == 0:
            logger.debug("returning: None")
            return None
        assert(len(results) == 1)
        only_row = results[0]
        assert(len(only_row) == 1)        
        logger.debug("returning: %s" % (only_row[0], ))
        return only_row[0]        
        
    # ------------------------------------------------------------------------
    #   List CRUD.
    # ------------------------------------------------------------------------    
    @tornado.gen.engine
    def create_list(self, user_id, contents, callback):
        logger = logging.getLogger("DatabaseManager.create_list")
        logger.debug("entry. user_id: %s, contents: %s" % (user_id, contents))        
        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_LIST_WITH_USER_ID_AND_CONTENTS_RETURN_LIST_ID,
                                        (user_id, contents))        
        normalized_user_id = normalize_uuid_string(user_id)
        self.expire_cache(normalized_user_id)                        

        new_list_id = self.extract_one_value_from_one_or_zero_rows(cursor)
        logger.debug("new_list_id: %s" % (new_list_id, ))  
        assert(new_list_id is not None)
        callback(new_list_id)

    @tornado.gen.engine
    def update_list(self, list_id, user_id, contents, callback):
        logger = logging.getLogger("DatabaseManager.update_list")
        logger.debug("entry. list_id: %s, user_id: %s, contents: %s" % (list_id, user_id, contents))        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.UPDATE_LIST_WITH_LIST_ID_AND_USER_ID_AND_CONTENTS,
                                        (list_id, user_id, contents))   
        normalized_list_id = normalize_uuid_string(list_id)
        self.expire_cache(normalized_list_id)                        
        normalized_user_id = normalize_uuid_string(user_id)
        self.expire_cache(normalized_user_id)                        
        
        if cursor.rowcount != 1:        
            rc = False
        else:
            rc = True
        logger.debug("returning: %s" % (rc, ))
        callback(rc)
        
    @tornado.gen.engine
    def get_lists(self, user_id, callback):
        logger = logging.getLogger("DatabaseManager.get_lists")
        logger.debug("entry. user_id: %s" % (user_id, ))        
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_LATEST_LISTS_WITH_USER_ID,
                                      (user_id, ),
                                      "GET_LATEST_LISTS_WITH_USER_ID")                
        lists = []
        for row in rows:
            revision_id = row[0]
            list_id = row[1]
            contents = row[2]
            datetime_edited = row[3]
            list_obj = List(revision_id, list_id, contents, datetime_edited)
            lists.append(list_obj)
        callback(lists)
        
    @tornado.gen.engine
    def delete_list(self, list_id, user_id, callback):
        logger = logging.getLogger("DatabaseManager.delete_list")
        logger.debug("Entry. list_id: %s, user_id: %s" % (list_id, user_id))
        
        # --------------------------------------------------------------------
        #   Validate assumptions.
        # --------------------------------------------------------------------
        try:
            list_id_obj = uuid.UUID(list_id)
        except:
            logger.error("list_id is not a valid UUID.")
            callback(None)
        try:
            user_id_obj = uuid.UUID(user_id)
        except:
            logger.error("user_id is not a valid UUID.")
            callback(None)
        # --------------------------------------------------------------------
        
        # --------------------------------------------------------------------
        #   If the user_id making this request doesn't own the list then
        #   refuse to do so. Return None to indicate this.
        #
        #   Remember that get_owner_user_id() returns a UUID object.
        # --------------------------------------------------------------------        
        owner_user_id_obj = yield tornado.gen.Task(self.get_owner_user_id,
                                                   list_id)        
        if (owner_user_id_obj != user_id_obj):
            logger.debug("User making request is not the owner, who is: %s" % (owner_user_id_obj, ))
            callback(None)
        # --------------------------------------------------------------------        
        
        # --------------------------------------------------------------------
        #   Delete the list and return whether the deletion is successful.
        # --------------------------------------------------------------------
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.DELETE_LIST_WITH_LIST_ID,
                                        (list_id, ))    
        normalized_list_id = normalize_uuid_string(list_id)
        self.expire_cache(normalized_list_id)                        
        normalized_user_id = normalize_uuid_string(user_id)
        self.expire_cache(normalized_user_id)                        
        
        # cursor.rowcount will indicate how many rows were deleted. If it's 0
        # we didn't delete anything, which is unexpected. It can be any other
        # positive because there could be many revisions of a given list.
        logger.debug("cursor.rowcount: %s" % (cursor.rowcount, ))
        if cursor.rowcount == 0:        
            rc = False
        else:
            rc = True            
        logger.debug("returning: %s" % (rc, ))
        callback(rc)        
        # --------------------------------------------------------------------
        
    @tornado.gen.engine
    def read_list(self, list_id, callback):
        logger = logging.getLogger("DatabaseManager.read_list")
        logger.debug("Entry. list_id: %s" % (list_id, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_LATEST_LIST_WITH_LIST_ID,
                                      (list_id, ),
                                      "GET_LATEST_LIST_WITH_LIST_ID")                
        if len(rows) == 0:
            logger.debug("Could not find the list.")
            callback(None)
        assert(len(rows) == 1)
        row = rows[0]
        revision_id = row[0]
        list_id = row[1]
        contents = row[2]
        datetime_edited = row[3]
        list_obj = List(revision_id, list_id, contents, datetime_edited)
        logger.debug("Returning: %s" % (list_obj, ))
        callback(list_obj)     

    @tornado.gen.engine
    def get_owner_user_id(self, list_id, callback):
        logger = logging.getLogger("DatabaseManager.get_owner_user_id")
        logger.debug("Entry. list_id: %s" % (list_id, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_OWNER_USER_ID_WITH_LIST_ID,
                                      (list_id, ),
                                      "GET_OWNER_USER_ID_WITH_LIST_ID")        
        if len(rows) == 0:
            logger.debug("Could not identify the owner.")
            callback(None)
        assert(len(rows) == 1)
        row = rows[0]
        assert(len(row) == 1)
        user_id_obj = uuid.UUID(row[0])
        logger.debug("Returning: %s" % (user_id_obj, ))
        callback(user_id_obj)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   User and role CRUD.
    # ------------------------------------------------------------------------
    @tornado.gen.engine
    def get_role_id(self, type, callback):
        logger = logging.getLogger("DatabaseManager.get_role_id")
        logger.debug("entry. type: %s" % (type, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_ROLE_ID,
                                      (type, ),
                                      "GET_ROLE_ID")        
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        assert(yield_value is not None)
        callback(yield_value)                

    @tornado.gen.engine
    def create_user(self, type, callback):
        logger = logging.getLogger("DatabaseManager.create_user")
        logger.debug("entry. type: %s" % (type, ))
        
        role_id = yield tornado.gen.Task(self.get_role_id, type)
        logger.debug("role_id: %s" % (role_id, ))
        assert(role_id is not None)
        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_USER_AND_RETURN_USER_ID,
                                        (role_id, ))
        new_user_id = self.extract_one_value_from_one_or_zero_rows(cursor)
        logger.debug("new_user_id: %s" % (new_user_id, ))  
        assert(new_user_id is not None)
        
        api_secret_key = base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
        rc = yield tornado.gen.Task(self.create_auth_api,
                                    api_secret_key,
                                    new_user_id)
        logger.debug("rc from API authentication query: %s" % (rc, ))
        assert(rc == True)
        
        callback(new_user_id)
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------
    #   API authentication specific functions.
    # ------------------------------------------------------------------------    
    @tornado.gen.engine
    def create_auth_api(self, api_secret_key, user_id, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_api")
        logger.debug("entry. api_secret_key: %s, user_id: %s" % (api_secret_key, user_id))
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_API,
                                        (api_secret_key, user_id))
        self.expire_cache(api_secret_key)
        if cursor.rowcount == 0:
            return_value = False
        else:
            return_value = True
        logger.debug("returning: %s" % (return_value, ))
        callback(return_value)        
        
    @tornado.gen.engine
    def get_user_id_from_api_secret_key(self, api_secret_key, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_api_secret_key")
        logger.debug("entry. api_secret_key: %s" % (api_secret_key, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_API_SECRET_KEY,
                                      (email, ),
                                      "GET_USER_ID_FROM_API_SECRET_KEY")
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
        
    # ------------------------------------------------------------------------
    #   Google authentication specific functions.
    # ------------------------------------------------------------------------
    @tornado.gen.engine
    def create_auth_google(self, email, user_id, first_name, last_name, name, locale, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_google")
        logger.debug("entry. email: %s, user_id: %s, first_name: %s, last_name: %s, name: %s, locale: %s" % (email, user_id, first_name, last_name, name, locale))        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_GOOGLE,
                                        (email, user_id, first_name, last_name, name, locale))        
        self.expire_cache(email)                        
        if cursor.rowcount == 0:
            return_value = False
        else:
            return_value = True
        logger.debug("returning: %s" % (return_value, ))
        callback(return_value)        
        
    @tornado.gen.engine
    def get_user_id_from_google_email(self, email, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_google_email")
        logger.debug("entry. email: %s" % (email, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_GOOGLE_EMAIL,
                                      (email, ),
                                      "GET_USER_ID_FROM_GOOGLE_EMAIL")
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------
    #   Facebook authentication specific functions.
    # ------------------------------------------------------------------------    
    @tornado.gen.engine
    def create_auth_facebook(self, id, user_id, link, access_token, locale, first_name, last_name, name, picture, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_facebook")
        logger.debug("entry. id: %s, user_id: %s, link: %s, access_token: %s, locale: %s, first_name: %s, last_name: %s, name: %s, picture: %s" % \
                     (id, user_id, link, access_token, locale, first_name, last_name, name, picture))
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_FACEBOOK,
                                        (id, user_id, link, access_token, locale, first_name, last_name, name, picture))
        self.expire_cache(id)
        if cursor.rowcount == 0:
            return_value = False
        else:
            return_value = True
        logger.debug("returning: %s" % (return_value, ))
        callback(return_value)        
        
    @tornado.gen.engine
    def get_user_id_from_facebook_id(self, id, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_facebook_id")
        logger.debug("entry. id: %s" % (id, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_FACEBOOK_ID,
                                      (id, ),
                                      "GET_USER_ID_FROM_FACEBOOK_ID")
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
    # ------------------------------------------------------------------------
    
    # ------------------------------------------------------------------------
    #   Twitter authentication specific functions.
    # ------------------------------------------------------------------------
    @tornado.gen.engine
    def create_auth_twitter(self, username, user_id, profile_image_url, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_twitter")
        logger.debug("entry. username: %s, user_id: %s, profile_image_url: %s" % (username, user_id, profile_image_url))        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_TWITTER,
                                        (username, user_id, profile_image_url))
        self.expire_cache(username)
        if cursor.rowcount == 0:
            return_value = False
        else:
            return_value = True
        logger.debug("returning: %s" % (return_value, ))
        callback(return_value)        
        
    @tornado.gen.engine
    def get_user_id_from_twitter_username(self, username, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_twitter_username")
        logger.debug("entry. username: %s" % (username, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_TWITTER_USERNAME,
                                      (username, ),
                                      "GET_USER_ID_FROM_TWITTER_USERNAME")
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   BrowserID authentication specific functions.
    # ------------------------------------------------------------------------    
    @tornado.gen.engine
    def create_auth_browserid(self, email, user_id, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_browserid")
        logger.debug("entry. email: %s, user_id: %s" % (email, user_id))
        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_BROWSERID,
                                        (email, user_id))
        self.expire_cache(email)
        if cursor.rowcount == 0:
            return_value = False
        else:
            return_value = True
        logger.debug("returning: %s" % (return_value, ))
        callback(return_value)        
        
    @tornado.gen.engine
    def get_user_id_from_browserid_email(self, email, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_browserid_email")
        logger.debug("entry. email: %s" % (email, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_BROWSERID_EMAIL,
                                      (email, ),
                                      "GET_USER_ID_FROM_BROWSERID_EMAIL")
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
    # ------------------------------------------------------------------------