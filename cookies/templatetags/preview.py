from django import template
register = template.Library()

from django.utils.safestring import mark_safe

from cookies.models import Field


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

images = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/tiff",
    "image/x-tiff"
]


@register.filter(name='preview')
def preview(resource, request):
    page_field = Field.objects.get(uri='http://xmlns.com/foaf/0.1/page')

    content_relations = resource.content.all()
    page_relations = resource.relations_from.filter(predicate=page_field)

    if resource.content_resource:   # This resource is the content resource.
        if resource.content_type in images:
            return mark_safe(image_preview_template.format(src=resource.content_location))
    elif content_relations.count() > 0:     # Get content from linked resources.
        tabs = []
        tabpanes = []
        for i, relation in enumerate(content_relations.all()):
            print relation.content_resource.location, relation.content_resource.local
            preview_elem = relation.content_resource.content_location
            if relation.content_resource.content_type in images and not relation.content_resource.local:
                image_location = relation.content_resource.content_location
                if not relation.content_resource.public:
                    social = request.user.social_auth.get(provider='github')
                    image_location += '&accessToken=' + social.extra_data['access_token']
                    image_location += '&dw=400'    # We can let page scripts change this after rendering.
                preview_elem = image_preview_template.format(src=image_location)
            elif (resource.content_type == 'application/xpdf' or (relation.content_resource.content_location and relation.content_resource.content_location.lower().endswith('.pdf'))) and relation.content_resource.local:
                preview_elem = pdf_preview_template.format(**{
                    'src': relation.content_resource.content_location,
                    "page_id": str(relation.content_resource.id),
                }) + pdf_preview_fragment
            elif not relation.content_resource.local:
                preview_elem = external_link_template.format(**{
                    'href': relation.content_resource.location
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
        return mark_safe(tablist_template.format(tabs="\n".join(tabs)) + tabcontent_template.format(panes="\n".join(tabpanes)))


    if page_relations > 0:    # There are several pages in this resource.
        tabs = []
        tabpanes = []
        for i, relation in enumerate(page_relations.all()):
            content_resource = relation.target.content.first().content_resource

            preview_elem = content_resource.content_type
            if content_resource.content_type in images:
                image_location = content_resource.content_location
                if not content_resource.public:
                    social = request.user.social_auth.get(provider='github')
                    image_location += '?accessToken=' + social.extra_data['access_token']
                preview_elem = image_preview_template.format(src=image_location)
            elif content_resource.content_type == 'application/xpdf' or content_resource.content_location.lower().endswith('.pdf'):
                preview_elem = pdf_preview_template.format(src=content_resource.content_location) + pdf_preview_fragment

            tabpanes.append(tabpane_template.format(**{
                "class": "active" if i == 0 else "",
                "page_id": str(relation.target.id),
                "preview": preview_elem,
            }))

            tabs.append(tab_template.format(**{
                "class": "active" if i == 0 else "",
                "page_id": str(relation.target.id),
                "page": u"Page %s" % str(i + 1)
            }))
        return mark_safe(tablist_template.format(tabs="\n".join(tabs)) + tabcontent_template.format(panes="\n".join(tabpanes)))
