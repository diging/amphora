var autocomplete_filter = function(e) {
    var target = $(this).attr('target');
    var predicate_id = $(this).val();
    if (predicate_id != "") {
        var name_split = $(this).attr('name').split('-');
        var prefix = name_split.slice(0,name_split.length - 1);
        prefix.push(target);
        var target_element_name = prefix.join('-');
        var target_widget = $('input[name='+target_element_name+']');
        console.log(target_widget);
        target_widget.yourlabsWidget().autocomplete.data = {
            'in_range_of': predicate_id,
        };
        console.log(target_widget.yourlabsWidget().autocomplete.data);
    }
}

$('body').ready(function(e) {


    $('.autocomplete_filter').each(autocomplete_filter);
    $('.autocomplete_filter').on('change', autocomplete_filter);
    
});  