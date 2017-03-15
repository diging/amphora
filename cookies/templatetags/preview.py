from django import template
from django.conf import settings
from django.core.urlresolvers import reverse

register = template.Library()

from django.utils.safestring import mark_safe

from cookies.models import Field, Resource
from cookies import giles


tablist_template = """
<ul class="nav nav-tabs nav-left" role="tablist">{tabs}</ul>
"""

tab_template = """
    <li role="presentation" class="{class}">
        <a href="#page_{page_id}" aria-controls="fields" role="tab" data-toggle="tab">{page}</a>
    </li>
"""

tabcontent_template = """
<div class="tab-content">{panes}</div>
"""

tabpane_template = """
    <div role="tabpanel" class="tab-pane {class} panel-body" id="page_{page_id}">
       {preview}
    </div>
"""

image_preview_template = """
        <img class="img img-responsive" src="{src}" />
"""

external_link_template = """
        <a class="btn" href="{href}" target="_blank">
            <span class="glyphicon glyphicon-new-window"></span> View resource in a new window (leaving JARS).
        </a>

"""
# <div>
# <iframe src="{href}" height="400" width="300" />
# </div>

pdf_preview_template = """
<canvas id="pdf-preview"></canvas>
<script>
var preview_container = $('#page_{page_id}');

PDFJS.getDocument('{src}')
"""
pdf_preview_fragment = """.then(function(pdf) {
    pdf.getPage(1).then(function(page) {
        var scale = 1;
        var viewport = page.getViewport(scale);
        console.log(preview_container.width());
        var canvas = document.getElementById('pdf-preview');
        var context = canvas.getContext('2d');
        canvas.height = preview_container.width()*1.4;
        canvas.width = preview_container.width();

        var renderContext = {
          canvasContext: context,
          viewport: viewport
        };
        page.render(renderContext);
    });
});
</script>
"""

page_link_template = """
<a href="{href}">View page resource</a>
"""

iframe_template = """
<iframe src="{href}" width="100%" height="400"></iframe>
"""

images = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/tiff",
    "image/x-tiff"
]


import urlparse, urllib


@register.filter(name='preview')
def preview(resource, request):
    page_field = Field.objects.get_or_create(uri='http://purl.org/dc/terms/isPartOf')[0]
    user = resource.created_by
    content_relations = resource.content.filter(is_deleted=False)
    page_relations = resource.relations_to.filter(predicate=page_field, is_deleted=False)

    if resource.content_resource:   # This resource is the content resource.
        if resource.content_type in images:
            return mark_safe(image_preview_template.format(src=resource.content_view))
        else:
            return mark_safe(resource.content_view)
    else:
        tabs = []
        tabpanes = []
        if content_relations.count() > 0:     # Get content from linked resources.

            for i, relation in enumerate(content_relations.all()):
                preview_elem = relation.content_resource.content_view
                # Remote image.
                if relation.content_resource.content_type in images and not relation.content_resource.is_local:
                    image_location = relation.content_resource.content_view

                    # Giles images.
                    if resource.external_source == Resource.GILES:
                        image_location = giles.format_giles_url(relation.content_resource.location, request.user, dw=400)
                    preview_elem = image_preview_template.format(src=image_location)

                # Local PDFs.
                elif (resource.content_type == 'application/xpdf' or (relation.content_resource.content_location and relation.content_resource.content_location.lower().endswith('.pdf'))) and relation.content_resource.is_local:
                    preview_elem = pdf_preview_template.format(**{
                        'src': relation.content_resource.content_view,
                        "page_id": str(relation.content_resource.id),
                    }) + pdf_preview_fragment

                # Remote content.
                elif not relation.content_resource.is_local:
                    # Giles plain text; use an IFrame.
                    if relation.content_resource.external_source == Resource.GILES and relation.content_resource.content_type == 'text/plain':
                        preview_elem = iframe_template.format(**{
                            'href': giles.format_giles_url(relation.content_resource.location, user.username),
                        })
                    # Giles image -- TODO: is this redundant?
                    elif relation.content_resource.external_source == Resource.GILES and relation.content_resource.content_type in images:
                        preview_elem = image_preview_template.format(**{
                            'src': giles.format_giles_url(relation.content_resource.location, user.username)
                        })
                    # Giles (other). Provide a link.
                    elif relation.content_resource.external_source == Resource.GILES:
                        preview_elem = external_link_template.format(**{
                            'href': giles.format_giles_url(relation.content_resource.location, user.username)
                        })
                    # Something else -- just provide a link.
                    else:
                        preview_elem = external_link_template.format(**{
                            'href': relation.content_resource.location
                        })
                elif relation.content_resource.content_type in images:
                    preview_elem = image_preview_template.format(**{
                        'src': relation.content_resource.file.url
                    })
                else:
                    preview_elem =external_link_template.format(**{
                        'href': relation.content_resource.file.url
                    })
                tabpanes.append(tabpane_template.format(**{
                    "class": "active" if i == 0 else "",
                    "page_id": str(relation.content_resource.id),
                    "preview": preview_elem,
                }))

                tabs.append(tab_template.format(**{
                    "class": "active" if i == 0 else "",
                    "page_id": str(relation.content_resource.id),
                    "page": relation.content_resource.content_type if relation.content_resource.content_type else "Preview"
                }))

        if page_relations > 0:    # There are several pages in this resource.
            for i, relation in enumerate(page_relations.all()):
                content_resource = relation.source.content.first().content_resource

                preview_elem = page_link_template.format(href=reverse('resource', args=(relation.source.id,)))
                if content_resource.content_type in images:

                    if content_resource.external_source == Resource.GILES:
                        image_location = giles.format_giles_url(content_resource.location, user.username)
                    else:
                        image_location = content_resource.content_view
                    preview_elem += image_preview_template.format(src=image_location)
                elif content_resource.content_type == 'application/xpdf' or content_resource.content_view.lower().endswith('.pdf'):
                    preview_elem += pdf_preview_template.format(src=content_resource.content_view, page_id=str(content_resource.id)) + pdf_preview_fragment

                tabpanes.append(tabpane_template.format(**{
                    "class": "active" if i == 0 and len(tabs) == 0 else "",
                    "page_id": str(content_resource.id),
                    "preview": preview_elem,
                }))

                tabs.append(tab_template.format(**{
                    "class": "active" if i == 0 and len(tabs) == 0 else "",
                    "page_id": str(content_resource.id),
                    "page": u"Page %s" % str(i + 1)
                }))

    return mark_safe(tablist_template.format(tabs="\n".join(tabs)) + tabcontent_template.format(panes="\n".join(tabpanes)))
