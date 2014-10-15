<img src="https://github.com/erickpeirson/jars/blob/master/docs/jar.jpg" height="50" />     jars
====

Just Another Repository for Scholars

JARS is an extremely minimalistic data repository implemented in Django 1.7. In contrast
to monolithic one-stop-shop repository packages that require an army of developers to
support, JARS focuses on providing bare-minimum data and metadata storage out of the box.

Some notable features:
----------------------
* Supports just about any metadata schema that can be expressed in RDF,
* Can interface with remote authority services, and include references to remote resources
  in metadata,
* Provides a simple REST API for interacting with your resources,
* Can talk to a Handle server to generate unique handles for resources,
* Curate and retrieve collections of resources (e.g. a corpus for text mining), including
  remote resources.
* Friendly and simple content access control for projects working with copyright or
  otherwise restricted data.

The target audience is primarily scholars working with digitized texts that need a more
robust storage facility than whatever mess is on their harddrive, and need stable URIs.