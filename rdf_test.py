import rdflib

# Load RDF for DC terms.
g = rdflib.Graph()
g.parse('http://dublincore.org/2012/06/14/dcterms.rdf')

# Define some elements.
property = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#Property')
type = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
label = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#label')
range = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#range')
subPropertyOf = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#subPropertyOf')
description = rdflib.term.URIRef('http://purl.org/dc/terms/description')
comment = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#comment')


# Get all of the properties.
properties = [ p for p in g.subjects(type, property) ]

for p in properties:
    this_uri = str(p)
    print this_uri

    this_label = [ s for s in g.objects(p, label) ][0]
    print this_label
    
    try:
        this_description = [ s for s in g.objects(p, description)][0]
        print this_description
    except IndexError:
        try:
            this_description = [ s for s in g.objects(p, comment)][0]
            print this_description
        except IndexError:
            print 'no description'
    
    try:
        this_range = [ s for s in g.objects(p, range)][0]
        print this_range
    except IndexError:
        pass
    
    this_parents = [ s for s in g.objects(p, subPropertyOf) ]
    print this_parents
    
    print '-'*40
    