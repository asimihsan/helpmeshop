import tornado
import tornado.web
import tornado.auth
from tornado.options import define, options

import os
import sys
import logging

# ----------------------------------------------------------------------------
#   Configuration constants.
# ----------------------------------------------------------------------------
define("base_uri", default=None, help="Base URI where the site is hosted.")
define("facebook_app_id", default=None, help="Facebook app ID")
define("facebook_app_secret", default=None, help="Facebook app secret")
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   RequestHandler that deals with Facebook authentication.
#
#   redirect_uri must be an absolute path, or else the Facebook authentication
#   API throws an error and references the OAuth RFC. Hence you must know
#   the full URI of where you want Facebook to return your user.   
# ----------------------------------------------------------------------------
class LoginFacebookHandler(tornado.web.RequestHandler, tornado.auth.FacebookGraphMixin):
    @tornado.web.asynchronous
    def get(self):
        logger = logging.getLogger("LoginFacebookHandler.get")
        logger.debug("entry")
        
        redirect_uri = '%s/login/facebook/' % (options.base_uri, )
        
        code = self.get_argument("code", False)
        logger.debug("code: %s" % (code, ))        
        if code:
            self.get_authenticated_user(
                redirect_uri=redirect_uri,
                client_id=options.facebook_app_id,
                client_secret=options.facebook_app_secret,
                code=code,
                callback=self.async_callback(self._on_login))
            return
        self.authorize_redirect(redirect_uri=redirect_uri,
                                client_id=options.facebook_app_id,
                                extra_params={"scope": "read_stream,offline_access"})
                                
    def _on_login(self, user):
        logger = logging.getLogger("LoginFacebookHandler._on_login")
        logger.debug("entry. user: %s" % (user, ))
        if not user:
            raise tornado.web.HTTPError(500, "Facebook authentication failed")
        assert("id" in user)
        self.set_secure_cookie("user", str(user["id"]))
        self.redirect("/") 

# ----------------------------------------------------------------------------
#   RequestHandler that deals with Facebook authentication. This is the
#   old-style OAuth1 that works but is depreciated in favour of the graph
#   mixin.
# ----------------------------------------------------------------------------
#class LoginFacebookHandler(tornado.web.RequestHandler, tornado.auth.FacebookMixin):
#    @tornado.web.asynchronous
#    def get(self):
#        logger = logging.getLogger("LoginFacebookHandler.get")
#        logger.debug("entry")
#        
#        session = self.get_argument("session", None)
#        logger.debug("session: %s" % (session, ))
#        if session:
#            self.get_authenticated_user(self.async_callback(self._on_auth))
#            return
#        self.authenticate_redirect()
#        
#    def _on_auth(self, user):
#        logger = logging.getLogger("LoginFacebookHandler._on_auth")
#        logger.debug("entry. user: %s" % (user, ))
#        if not user:
#            raise tornado.web.HTTPError(500, "Facebook authentication failed")
#        assert("uid" in user)
#        self.set_secure_cookie("user", str(user["uid"]))
#        self.redirect("/")        
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   RequestHandler that deals with Google authentication.
# ----------------------------------------------------------------------------
class LoginGoogleHandler(tornado.web.RequestHandler, tornado.auth.GoogleMixin):
    @tornado.web.asynchronous
    def get(self):
        logger = logging.getLogger("LoginGoogleHandler.get")
        logger.debug("entry")
        
        openid_mode = self.get_argument("openid.mode", None)
        logger.debug("openid_mode: %s" % (openid_mode, ))
        if openid_mode:            
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect()
        
    def _on_auth(self, user):
        logger = logging.getLogger("LoginGoogleHandler._on_auth")
        logger.debug("entry. user: %s" % (user, ))            
        if not user:
            raise tornado.web.HTTPError(500, "Google authentication failed")
        assert("email" in user)
        self.set_secure_cookie("user", user["email"])
        self.redirect("/")
# ----------------------------------------------------------------------------