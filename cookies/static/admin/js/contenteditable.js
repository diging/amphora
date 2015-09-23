/** 

    Updates the input element based on changes to the contenteditable div element
    in a ContenteditableField widget.

**/

$('body').ready(function() {
    // We bind DOMSubtreeModified rather than change on the div element itself so 
    //  that we don't have to periodically check innerHTML.
    $('[contenteditable="true"]').bind("DOMSubtreeModified", function() {
        var name = $( this ).attr('id');
        var value = $( this ).text();
        $('input[name="'+name+'"]').attr('value', value);
    });
});