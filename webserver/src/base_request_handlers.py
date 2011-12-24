import tornado
from tornado.options import define, options

import database

# ----------------------------------------------------------------------------
#   Base request handler.
# ----------------------------------------------------------------------------
class BaseLoginHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        """ Create a database connection when a request handler is called
        and store the connection in the application object.
        """
        if not hasattr(self.application, 'db'):
            self.application.db = database.DatabaseManager()
        return self.application.db
# ----------------------------------------------------------------------------

