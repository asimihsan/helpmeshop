import tornado.escape

class ListItem(object):
    REQUIRED_KEYS = ["ident", "title"]   
    ALL_KEYS = ["ident", "title", "url", "notes"]

    def __init__(self, ident, title, url=None, notes=None):
        self.ident = ident
        self.title = title
        self._url = url
        self._notes = notes        
    
    @property
    def url(self):
        if not self._url:
            return ""
        return self._url
    @url.setter
    def url(self, url):
        self._url = url
        
    @property
    def notes(self):
        if not self._notes:
            return ""
        return self._notes
    @notes.setter
    def notes(self, notes):
        self._notes = notes
    
    def __repr__(self):
        output = "{ListItem. ident=%s, title=%s, url=%s, notes=%s}" % (self.ident, self.title, self.url, self.notes)
        return output
        
    @staticmethod
    def is_valid_json_representation(json_string):        
        try:
            decoded = tornado.escape.json_decode(json_string)
        except:
            return False
        if not all(key in decoded for key in ListItem.REQUIRED_KEYS):
            return False
        return True

    @staticmethod
    def from_json(json_string):
        if not ListItem.is_valid_json_representation(json_string):
            return None
        decoded = tornado.escape.json_decode(json_string)
        return ListItem(ident = decoded['ident'],
                        title = decoded['title'],
                        url = decoded.get('url', None),
                        notes = decoded.get('notes', None))

    def to_json(self):
        encoded = {}
        for key in self.ALL_KEYS:
            value = getattr(self, key)
            if (key in self.REQUIRED_KEYS) or \
               (key not in self.REQUIRED_KEYS and value is not None):
                encoded[key] = value                            
        return tornado.escape.json_encode(encoded)
        