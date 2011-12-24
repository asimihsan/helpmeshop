import tornado
import tornado.gen

from tornado.options import define, options

import os
import sys
import logging

import momoko

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
define("database_cleanup_timeout", default=None, type=int, help="Datasbe cleanup timeout.")
# ----------------------------------------------------------------------------
        
class DatabaseManager(object):
    # ------------------------------------------------------------------------
    #   Database statements.
    # ------------------------------------------------------------------------
    GET_USER_ID_FROM_BROWSERID_EMAIL = """SELECT user_id FROM auth_browserid WHERE email = %s;"""
    CREATE_AUTH_BROWSERID = """INSERT INTO auth_browserid (email, user_id) VALUES (%s, %s);"""    
    
    GET_ROLE_ID = """SELECT role_id FROM role WHERE role_name = %s;"""    
    CREATE_USER = """INSERT INTO helpmeshop_user (user_id, role_id)
                     VALUES (uuid_generate_v4(), %s)
                     RETURNING user_id;"""
    
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

    def extract_one_value_from_one_or_zero_rows(self, cursor):
        """ If you execute a query that SELECTs for one value, and expects only
        one row in the results, then use this function.
        
        If there are zero rows in the output then the function will return None.
        Else, the function will assert if these conditions are not true.
        Else, it will return the single value.
        """
        logger = logging.getLogger("DatabaseManager.extract_one_value_from_one_or_zero_rows")        
        results = cursor.fetchall()
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
        logger = logging.getLogger("DatabaseManager.get_role_id_for_regular")
        logger.debug("entry. type: %s" % (type, ))
        cursor = yield tornado.gen.Task(self.db.execute, self.GET_ROLE_ID, (type, ));
        yield_value = self.extract_one_value_from_one_or_zero_rows(cursor)        
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
                                        self.CREATE_USER,
                                        (role_id, ))
        new_user_id = self.extract_one_value_from_one_or_zero_rows(cursor)
        logger.debug("new_user_id: %s" % (new_user_id, ))  
        assert(new_user_id is not None)
        callback(new_user_id)
        
    @tornado.gen.engine
    def create_auth_browserid(self, email, user_id, callback):
        logger = logging.getLogger("DatabaseManager.create_auth_browserid")
        logger.debug("entry. email: %s, user_id: %s" % (email, user_id))
        
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.CREATE_AUTH_BROWSERID,
                                        (email, user_id))
        rc = cursor.fetchall()        
        logger.debug("rc: %s" % (rc, ))        
        callback(True)        
        
    @tornado.gen.engine
    def get_user_id_from_browserid_email(self, email, callback):
        logger = logging.getLogger("DatabaseManager.get_user_id_from_browserid_email")
        logger.debug("entry. email: %s" % (email, ))
        cursor = yield tornado.gen.Task(self.db.execute,
                                        self.GET_USER_ID_FROM_BROWSERID_EMAIL,
                                        (email, ))
        yield_value = self.extract_one_value_from_one_or_zero_rows(cursor)
        logger.debug("yielding: %s" % (yield_value, ))        
        callback(yield_value)
        