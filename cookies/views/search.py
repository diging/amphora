




# class ResourceSearchView(SearchView):
#     """Class based view for thread-safe search."""
#     template = 'templates/search/search.html'
#     queryset = SearchQuerySet()
#     results_per_page = 20
#
#     def get_context_data(self, *args, **kwargs):
#         """Return context data."""
#         context = super(ResourceSearchView, self).get_context_data(*args, **kwargs)
#         sort_base = self.request.get_full_path().split('?')[0] + '?q=' + context['query']
#
#         context.update({
#             'sort_base': sort_base,
#         })
#         return context
#
#     def form_valid(self, form):
#
#         self.queryset = form.search()
#
#         context = self.get_context_data(**{
#             self.form_name: form,
#             'query': form.cleaned_data.get(self.search_field),
#             'object_list': self.queryset,
#             'search_results' : self.queryset,
#         })
#
#         return self.render_to_response(context)
