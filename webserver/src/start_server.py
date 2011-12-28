#!/usr/bin/env python

import tornado
import tornado.ioloop
import tornado.web
import tornado.auth
import tornado.escape
import tornado.httpserver

import tornado.options
from tornado.options import define, options

import os
import sys
import json
import base64
import uuid
import pprint

from base_request_handlers import BasePageHandler

from auth_request_handlers import LoginGoogleHandler
from auth_request_handlers import LoginFacebookHandler
from auth_request_handlers import LoginTwitterHandler
from auth_request_handlers import LoginBrowserIDHandler
from auth_request_handlers import LoginApiHandler
from auth_request_handlers import LogoutHandler

from ListHandler import ListReadHandler
from ListHandler import ListCreateHandler
from ListHandler import ListDeleteHandler
from ListHandler import ListCreateItemHandler

from model.List import List
from model.ListItem import ListItem

# ----------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------
APP_NAME = 'start_server'
LOG_PATH = '/var/log/helpmeshop/webserver/'
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Configuration variables that we require.
# ----------------------------------------------------------------------
define("http_listen_port", default=None, type=int, help="HTTP listen port")
define("number_of_processes", default=None, type=int, help="Number of processes")
define("debug_mode", default=None, help="Tornado debug mode enabled or not")

# If you want to use the old-style OAuth1 Facebook authentication API then
# uncomment these lines, as Tornado requires forward-declaration of
# configuration variables, and you need to pass in these guys into the
# Application constructor.
#define("facebook_app_id", default=None, help="Facebook app ID")
#define("facebook_app_secret", default=None, help="Facebook app secret")

define("twitter_consumer_key", default=None, help="Twitter app consumer key")
define("twitter_consumer_secret", default=None, help="Twitter app consumer secret")
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
import logging
import logging.handlers
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

if not os.path.isdir(LOG_PATH):
    os.makedirs(LOG_PATH)
log_filename = os.path.join(LOG_PATH, "%s.log" % (APP_NAME, ))
ch2 = logging.handlers.RotatingFileHandler(log_filename,
                                           maxBytes=10*1024*1024,
                                           backupCount=5)
ch2.setFormatter(formatter)
logger.addHandler(ch2)

logger = logging.getLogger(APP_NAME)
# ----------------------------------------------------------------------

class MainHandler(BasePageHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self): 
        data = {}
        data['user'] = None
        lists = []
        if self.current_user:
            data['user'] = tornado.escape.xhtml_escape(self.current_user)
            lists = yield tornado.gen.Task(self.db.get_lists, self.current_user)
            for list_obj in lists:
                contents_decoded = tornado.escape.json_decode(list_obj.contents)
                setattr(list_obj, "title", contents_decoded["title"])
            logger.debug("lists:\n%s" % (pprint.pformat(lists), ))        
        data['lists'] = lists 
        data['title'] = "Help Me Shop"      
        
        self.render("index.html", **data)            

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/login/api/", LoginApiHandler),
            (r"/login/google/", LoginGoogleHandler),
            (r"/login/facebook/", LoginFacebookHandler),
            (r"/login/twitter/", LoginTwitterHandler),
            (r"/login/browserid/", LoginBrowserIDHandler),
            (r"/logout", LogoutHandler),
            tornado.web.URLSpec(pattern=r"/read_list/(.*)",   handler_class=ListReadHandler, name="ListReadHandler"),
            tornado.web.URLSpec(pattern=r"/create_list/",     handler_class=ListCreateHandler, name="ListCreateHandler"),
            tornado.web.URLSpec(pattern=r"/delete_list/(.*)", handler_class=ListDeleteHandler, name="ListDeleteHandler"),
            tornado.web.URLSpec(pattern=r"/create_item/(.*)", handler_class=ListCreateItemHandler, name="ListCreateItemHandler"),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), 'templates'),
            static_path=os.path.join(os.path.dirname(__file__), 'static'),
            xsrf_cookies=True,
            gzip=True,
            
            # If you generate the cookie from scratch then server restarts will
            # render old cookies invalid. This affects fault-tolerance!
            cookie_secret='ANrq+RCiRu2VQQIdXOw2rQVT/BvavUI2nEA9TrfjesQ=',
            #cookie_secret=base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes),
            
            # These two lines are required for the old-style OAuth1 Facebook 
            # authentication API. So just leave them here, might come in handy
            # one day. If you uncomment these then you'll need to 'define' these
            # configuration variables at the top as well.
            #facebook_api_key=options.facebook_app_id,
            #facebook_secret=options.facebook_app_secret,
            
            twitter_consumer_key=options.twitter_consumer_key,
            twitter_consumer_secret=options.twitter_consumer_secret,
        )
        if options.debug_mode:
            settings['debug'] = True
        tornado.web.Application.__init__(self, handlers, **settings)

if __name__ == "__main__":
    logger.info("starting")
    
    # ------------------------------------------------------------------------
    #   Import settings.
    # ------------------------------------------------------------------------    
    config_filepath = os.path.join(os.path.dirname(__file__), "server.conf")
    assert(os.path.isfile(config_filepath))    
    tornado.options.parse_config_file(config_filepath)    
    
    #!!AI causes the execution to freeze, debug later.
    #tornado.options.parse_command_line()
    # ------------------------------------------------------------------------        

    logger.debug("start listening on port %s" % (options.http_listen_port, ))
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.bind(options.http_listen_port)
    
    # Debug mode only supports one process in multi-processing mode.
    if options.debug_mode:
        number_of_processes = 1
    else:
        number_of_processes = options.number_of_processes
        
    http_server.start(number_of_processes)    
    tornado.ioloop.IOLoop.instance().start()
    
