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

from auth_request_handlers import LoginGoogleHandler, LoginFacebookHandler

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

# If you want to use the old-style OAuth1 Facebook authentication API then
# uncomment these lines, as Tornado requires forward-declaration of
# configuration variables, and you need to pass in these guys into the
# Application constructor.
#define("facebook_app_id", default=None, help="Facebook app ID")
#define("facebook_app_secret", default=None, help="Facebook app secret")
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
import logging
import logging.handlers
logger = logging.getLogger('')
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

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

class MainHandler(BaseHandler):
    def get(self):
        if not self.current_user:
            self.redirect("/login/facebook/")
            return
        name = tornado.escape.xhtml_escape(self.current_user)
        self.write("Hello, " + name)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/login/google/", LoginGoogleHandler),
            (r"/login/facebook/", LoginFacebookHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), 'templates'),
            static_path=os.path.join(os.path.dirname(__file__), 'static'),
            xsrf_cookies=True,
            
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
        )
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
    http_server.start(0)    
    tornado.ioloop.IOLoop.instance().start()
    
