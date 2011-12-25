# ----------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# File: helpmeshop/src/mockup/create_tables.py
#
# Assume that the PostgreSQL database is empty and create all
# the tables from scratch.
#
# Refer to helpmeshop/doc/database_model.[vsd/png].
# ----------------------------------------------------------------------

from __future__ import with_statement
import os
import sys
import psycopg2
import logging
from string import Template
import datetime
import pprint
import random
import string
import json
import redis

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
APP_NAME = 'create_tables'
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger = logging.getLogger(APP_NAME)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Constants to leave alone.
# ----------------------------------------------------------------------
DATABASE_NAME = "helpmeshop"
DATABASE_USERNAME = "ubuntu"
DATABASE_PASSWORD = "password"
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432

TEMPL_DB_CONNECT = Template("dbname=${dbname} user=${user} password=${password}")

UUID_LENGTH = 32
HEX_DIGITS = "0123456789abcdef"
RANDOM_SEED = 0

# ----------------------------------------------------------------------
# Tables.
# ----------------------------------------------------------------------
# Role
DROP_ROLE_TABLE = """DROP TABLE IF EXISTS role;"""
CREATE_ROLE_TABLE = """CREATE TABLE role (
    role_id UUID PRIMARY KEY,
    role_name TEXT NOT NULL,
    privileges HSTORE);"""

# User
DROP_USER_TABLE = """DROP TABLE IF EXISTS helpmeshop_user;"""
CREATE_USER_TABLE = """CREATE TABLE helpmeshop_user (
    user_id UUID PRIMARY KEY,
    role_id UUID NOT NULL);"""
                                          
# Google authentication details
DROP_AUTH_GOOGLE_TABLE = """DROP TABLE IF EXISTS auth_google;"""
CREATE_AUTH_GOOGLE_TABLE = """CREATE TABLE auth_google (
    email TEXT PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    name TEXT NOT NULL,
    locale TEXT NOT NULL);"""

# Facebook authentication details
DROP_AUTH_FACEBOOK_TABLE = """DROP TABLE IF EXISTS auth_facebook;"""
CREATE_AUTH_FACEBOOK_TABLE = """CREATE TABLE auth_facebook (
    id TEXT PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL,
    link TEXT NOT NULL,
    access_token TEXT NOT NULL,
    locale TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    name TEXT NOT NULL,
    picture TEXT NOT NULL);"""

# Twitter authentication details
DROP_AUTH_TWITTER_TABLE = """DROP TABLE IF EXISTS auth_twitter;"""
CREATE_AUTH_TWITTER_TABLE = """CREATE TABLE auth_twitter (
    username TEXT PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL,
    profile_image_url TEXT NOT NULL);"""

# BrowserID authentication details
DROP_AUTH_BROWSERID_TABLE = """DROP TABLE IF EXISTS auth_browserid;"""
CREATE_AUTH_BROWSERID_TABLE = """CREATE TABLE auth_browserid (
    email TEXT PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL);"""
    
# list
DROP_LIST_TABLE = """DROP TABLE IF EXISTS list;"""
CREATE_LIST_TABLE = """CREATE TABLE list (revision_id UUID PRIMARY KEY,
                                          list_id UUID NOT NULL,
                                          user_id UUID NOT NULL,
                                          datetime_edited TIMESTAMP NOT NULL,
                                          contents TEXT NOT NULL);"""

INSERT_STATEMENTS = [DROP_ROLE_TABLE,
                     CREATE_ROLE_TABLE,
                     DROP_USER_TABLE,
                     CREATE_USER_TABLE,
                     DROP_AUTH_GOOGLE_TABLE,
                     CREATE_AUTH_GOOGLE_TABLE,
                     DROP_AUTH_FACEBOOK_TABLE,
                     CREATE_AUTH_FACEBOOK_TABLE,
                     DROP_AUTH_TWITTER_TABLE,
                     CREATE_AUTH_TWITTER_TABLE,                     
                     DROP_AUTH_BROWSERID_TABLE,
                     CREATE_AUTH_BROWSERID_TABLE,
                     DROP_LIST_TABLE,
                     CREATE_LIST_TABLE]
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Indexes.
#
# Don't need indexes on unique columns. See:
# http://www.postgresql.org/docs/8.2/static/indexes-unique.html
# ----------------------------------------------------------------------
INDEX_LIST_ID_ON_LIST = """CREATE INDEX list_id_on_list on list(list_id);"""
INDEX_USER_ID_ON_AUTH_GOOGLE = """CREATE INDEX user_id_on_auth_google on auth_google(user_id);"""
INDEX_USER_ID_ON_AUTH_FACEBOOK = """CREATE INDEX user_id_on_auth_facebook on auth_facebook(user_id);"""
INDEX_USER_ID_ON_AUTH_TWITTER = """CREATE INDEX user_id_on_auth_twitter on auth_twitter(user_id);"""
INDEX_USER_ID_ON_AUTH_BROWSERID = """CREATE INDEX user_id_on_auth_browserid on auth_browserid(user_id);"""

INDEX_STATEMENTS = [INDEX_LIST_ID_ON_LIST]
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Foreign key constraints.
# ----------------------------------------------------------------------
FOREIGN_KEY_STATEMENTS = []
# ----------------------------------------------------------------------

ALL_STATEMENTS = INSERT_STATEMENTS + INDEX_STATEMENTS + FOREIGN_KEY_STATEMENTS                  

# ----------------------------------------------------------------------
# insert_dummy_data() commands.
# ----------------------------------------------------------------------
INSERT_ROLE = "INSERT INTO role (role_id, role_name) VALUES (%s, %s);"

SELECT_ADMIN = "SELECT role_id FROM role WHERE role_name = 'admin';"
SELECT_REGULAR = "SELECT role_id FROM role WHERE role_name = 'regular';"

INSERT_USER = "INSERT INTO user (user_id, role_id) VALUES (%s, %s);"

INSERT_LIST = "INSERT INTO list (revision_id, list_id, user_id, datetime_edited, contents) VALUES (%s, %s, %s, %s, %s);"
# ----------------------------------------------------------------------

def get_random_document():
    title = "title %s" % (random.randint(1, 1024), )
    body = "body %s body %s body %s" % (random.randint(1, 1024), random.randint(1, 1024), random.randint(1, 1024))
    data = {"title": title, "body": body}
    return json.dumps(data)

def get_random_uuid():
    return ''.join([random.choice(HEX_DIGITS) for elem in xrange(UUID_LENGTH)])

def insert_dummy_data(cur):
    """ Stuff to get some functional testing done on. """
    
    logger = logging.getLogger("%s.insert_dummy_data" % (APP_NAME, ))
    logger.info("entry")
    
    NUMBER_INSTITUTIONS = 1
    NUMBER_USERS_PER_INSTITUTION = 3
    NUMBER_DOCUMENTS_PER_INSTITUTION = 10
    MAXIMUM_REVISIONS_PER_DOCUMENT = 10    
    
    logger.info("Inserting roles...")
    cur.execute(INSERT_ROLE, (get_random_uuid(), "admin"))
    cur.execute(INSERT_ROLE, (get_random_uuid(), "regular"))
    
    return
    
    logger.info("Inserting users...")    
    user_ids = []
    for i in xrange(NUMBER_INSTITUTIONS):
        for j in xrange(NUMBER_USERS_PER_INSTITUTION):        
            cur.execute(RANDOM_INSTITUTION)        
            institution_id = cur.fetchone()[0]
            
            cur.execute(SELECT_CONSERVATOR)
            role_id = cur.fetchone()[0]
            
            user_id = get_random_uuid()
            username = "user%s" % (i*NUMBER_USERS_PER_INSTITUTION+j, )
            password = "pass%s" % (i*NUMBER_USERS_PER_INSTITUTION+j, )
            email_address = "user@host.com"
            
            args = (user_id, institution_id, username, password, role_id, email_address)
            logger.debug("user insert args:\n%s" % (pprint.pformat(args), ))
            cur.execute(INSERT_USER, args)      

            user_ids.append(user_id)
            
    logger.info("Inserting administrative users...")        
    for i in xrange(NUMBER_INSTITUTIONS):
        institution_id = institution_ids[i]
        cur.execute(SELECT_ADMIN)
        role_id = cur.fetchone()[0]
        user_id = get_random_uuid()
        username = "admin%s" % (i, )
        password = "pass%s" %  (i, )        
        email_address = "user@host.com"
        args = (user_id, institution_id, username, password, role_id, email_address)
        logger.debug("user insert args:\n%s" % (pprint.pformat(args), ))
        cur.execute(INSERT_USER, args)                
            
    logger.info("Inserting documents...")    
    for i in xrange(NUMBER_INSTITUTIONS):    
        for j in xrange(NUMBER_DOCUMENTS_PER_INSTITUTION):
            document_id = get_random_uuid()
            number_revisions = random.randint(1, MAXIMUM_REVISIONS_PER_DOCUMENT)
            for k in xrange(number_revisions):
                revision_id = get_random_uuid()
                user_id = random.choice(user_ids)
                days_ago = random.randint(0, 365*2)
                datetime_edited = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).replace(microsecond=0)
                contents = get_random_document()
                
                args = (revision_id, document_id, user_id, datetime_edited, contents)
                logger.debug("user insert args:\n%s" % (pprint.pformat(args), ))
                cur.execute(INSERT_CONDITION_REPORT, args)

if __name__ == "__main__":
    logger.info("Starting main.  args: %s" % (sys.argv[1:], ))
    
    logger.info("Seeding random generator with: %s" % (RANDOM_SEED, ))
    random.seed(RANDOM_SEED)
    
    logger.debug("Opening database connection and cursor...")
    conn = psycopg2.connect(TEMPL_DB_CONNECT.substitute(dbname=DATABASE_NAME,
                                                        user=DATABASE_USERNAME,
                                                        password=DATABASE_PASSWORD,
                                                        host=DATABASE_HOST,
                                                        port=DATABASE_PORT))
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()    
    logger.debug("Opened database connection and cursor.")        
    try:
        for statement in ALL_STATEMENTS:
            logger.info("Executing: %s" % (statement, ))
            cur.execute(statement)        
        insert_dummy_data(cur)
    finally:
        logger.debug("Closing database connection and cursor...")
        conn.commit()
        cur.close()
        conn.close()
    