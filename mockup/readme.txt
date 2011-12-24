# ----------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# ----------------------------------------------------------------------

Last edit: 21:39, 21th May 2001.

After coming up with an initial database model it's obvious that this
application is so complex that taking an initial stab with Erlang
is unwise.  This mockup is intended as a 100% implementation of
ArtiCheck's requirements and functional specification, but without the
requirement to meet its availability or performance requirements.

This means there will need to be an HTTP/HTTPS interface, PostgreSQL
interaction, PDF generation, and image resizing.  It should just work.
That way, if push comes to shove this is good to go for a prototype.

Try to design the components as loosely coupled with HTTP interfaces.
That way we can slowly replace the core of the application with
Erlang as we go along, if need be.
