import tornado
import tornado.web
import tornado.auth
import tornado.httpclient
import urllib
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
#   RequestHandler that deals with Mozilla BrowserID authentication.
# ----------------------------------------------------------------------------
class LoginBrowserIDHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        logger = logging.getLogger("LoginBrowserIDHandler.get")
        logger.debug("entry")     
        
        assertion = self.get_argument('assertion')
        domain = self.request.host
        data = {'assertion': assertion,
                'audience': domain}
        logger.debug('data: %s' % (data, ))
        
        http_client = tornado.httpclient.AsyncHTTPClient()
        url = 'https://browserid.org/verify' 
        response = http_client.fetch(url,
                                     method='POST',
                                     body=urllib.urlencode(data),
                                     callback=self.async_callback(self._on_response))
                                     
    def _on_response(self, response):
        logger = logging.getLogger("LoginBrowserIDHandler._on_response")
        logger.debug("entry. response: %s" % (response, ))     
        struct = tornado.escape.json_decode(response.body)
        logger.debug("response struct: %s" % (struct, ))
        if struct['status'] != 'okay':
            raise tornado.web.HTTPError(400, "BrowserID status not okay")
        email = struct['email']
        self.set_secure_cookie('user', email)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        response = {'next_url': '/'}
        self.write(tornado.escape.json_encode(response))
        self.finish()

# ----------------------------------------------------------------------------
#   RequestHandler that deals with Twitter authentication.
# ----------------------------------------------------------------------------
class LoginTwitterHandler(tornado.web.RequestHandler, tornado.auth.TwitterMixin):
    @tornado.web.asynchronous
    def get(self):
        logger = logging.getLogger("LoginTwitterHandler.get")
        logger.debug("entry")    
        
        # We'll get a "denied" GET paramater back if the user has refused
        # to authorise us.
        denied = self.get_argument("denied", None)
        logger.debug("denied: %s" % (denied, ))
        if denied:
            raise tornado.web.HTTPError(500, "Twitter authentication failed. User refused to authorize.")
    
        oauth_token = self.get_argument("oauth_token", None)
        logger.debug("oauth_token: %s" % (oauth_token, ))
        if oauth_token:
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authorize_redirect()
        
    def _on_auth(self, user):
        logger = logging.getLogger("LoginTwitterHandler._on_auth")
        logger.debug("entry. user: %s" % (user, ))    
        if not user:
            raise tornado.web.HTTPError(500, "Twitter authentication failed")
        assert("username" in user)
        self.set_secure_cookie("user", str(user["username"]))
        self.redirect("/")
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
#   RequestHandler that deals with Facebook authentication.
#
#   redirect_uri must be an absolute path, or else the Facebook authentication
#   API throws an error and references the OAuth RFC. Hence you must know
#   the full URI of where you want Facebook to return your user.   
#
#   For more elaboration on the available "scope" parameters see:
#   https://developers.facebook.com/docs/reference/api/permissions/
#
#   Note that, unlike Twitter or Google, Facebook does not have an explicit
#   "do not accept" choice for the user.
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
        
        # If openid_mode is None we have not authenticated yet.
        # If openid_mode is cancel the user has refused to
        # authorise us.
        openid_mode = self.get_argument("openid.mode", None)
        logger.debug("openid_mode: %s" % (openid_mode, ))
        if openid_mode == "cancel":
            raise tornado.web.HTTPError(500, "Google authentication failed. User refused to authorize.")
        
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