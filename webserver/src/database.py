import tornado
import tornado.gen
from tornado.options import define, options

import os
import sys
import logging
import cPickle as pickle
import hashlib
import base64

import momoko
import redis

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
    
    GET_ROLE_ID = """SELECT role_id FROM role WHERE role_name = %s;"""    
    CREATE_USER_AND_RETURN_USER_ID = """INSERT INTO helpmeshop_user (helpmeshop_user_id, role_id)
                                        VALUES (uuid_generate_v4(), %s)
                                        RETURNING helpmeshop_user_id;"""
    
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
        self.r.flushall()            

    @tornado.gen.engine
    def execute_cached_db_statement(self, statement, args, callback):
        """ Execute a database statement. Use a redis-based cache.
        Only call this function for database queries that gather
        data, rather than modify data, i.e. SELECT statements.
        
        This will return the full result of cursor.fetchall(). If
        you need access to the actual cursor don't use this
        function, as cursors can't be pickled."""
        
        logger = logging.getLogger("DatabaseManager.execute_cached_db_statement")
        logger.debug("entry. statement: %s, args: %s" % (statement, args))
        
        key_elems = [statement] + list(args)
        key = ":".join(key_elems)
        #key_elem = pickle.dumps((statement, args), -1)
        #key = hashlib.md5(key_elem).digest()
        value_pickled = self.r.get(key)        
        if not value_pickled:
            logger.debug("cache miss")
            cursor = yield tornado.gen.Task(self.db.execute, statement, args)
            value = cursor.fetchall()
            self.r.setex(key, 60 * 60 * 24, pickle.dumps(value))
        else:
            logger.debug("cache hit")
            value = pickle.loads(value_pickled)
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
            
    @tornado.gen.engine
    def get_role_id(self, type, callback):
        logger = logging.getLogger("DatabaseManager.get_role_id")
        logger.debug("entry. type: %s" % (type, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_ROLE_ID,
                                      (type, ))        
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
        callback(new_user_id)
        
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
        callback(True)        
        
    @tornado.gen.engine
    def get_user_id_from_google_email(self, email, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_google_email")
        logger.debug("entry. email: %s" % (email, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_GOOGLE_EMAIL,
                                      (email, ))
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
        callback(True)        
        
    @tornado.gen.engine
    def get_user_id_from_facebook_id(self, id, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_facebook_id")
        logger.debug("entry. id: %s" % (id, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_FACEBOOK_ID,
                                      (id, ))
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
        callback(True)        
        
    @tornado.gen.engine
    def get_user_id_from_twitter_username(self, username, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_twitter_username")
        logger.debug("entry. username: %s" % (username, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_TWITTER_USERNAME,
                                      (username, ))
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
        callback(True)        
        
    @tornado.gen.engine
    def get_user_id_from_browserid_email(self, email, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_browserid_email")
        logger.debug("entry. email: %s" % (email, ))
        rows = yield tornado.gen.Task(self.execute_cached_db_statement,
                                      self.GET_USER_ID_FROM_BROWSERID_EMAIL,
                                      (email, ))
        yield_value = self.extract_one_value_from_one_or_zero_rows(rows)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
    # ------------------------------------------------------------------------