/**
 * Simple (thanks to jQuery) replacement of xmlHttpCall provided by portal
 * 
 * @param $destination - object { url, portletPath, actionName }
 * @param $data object with query params
 * @param $callback - object { func, args } or function
 */
function smHttpCall(destination, data, callback, dataType)
{
    var url = (typeof destination.url != "undefined")  ?  destination.url  :  window.location.href.replace(/\?.*/,'');
    jQuery.extend(data, {
        'p$site': document.forms[0]['p$st'].value,
        'p$rq':   destination.portletPath + ":" + destination.actionName
    });
    
    jQuery.post(url, data, function(response, status, jqXHR) 
    {
        if (typeof(callback) == 'function') {
            callback(response.response, textStatis, jqXHR);
        }
        else
        {
           callback["func"](callback.args, response.response, status, jqXHR);
        }
    }, dataType);    
}


;
jQuery(function(){
    jQuery('#rss_createfeed').bind('click',createRssFeed);
    function createRssFeed (e){
        e.preventDefault();
        var oThis = jQuery(this);
	   	var args = {
            'QueryKey': oThis.data('qk'),
            'Db': oThis.data('db'),
            'RssFeedName': jQuery('#rss_name').val(),
            'RssFeedLimit': jQuery('#rss_results').val(),
            'HID': oThis.data('hid')
        };
        Portal.$send('CreateRssFeed',args);
    }  
});

;
(function($){

    $(function() {    

        var theSearchInput = $("#term");
        var originalTerm = $.trim(theSearchInput.val());
        var theForm = jQuery("form").has(theSearchInput);
        var dbNode = theForm.find("#database");
        var currDb = dbNode.val();
        var sbConfig = {};
        try{
            sbConfig = eval("({" + theSearchInput.data("sbconfig") + "})");
        }catch(e){}
        var defaultSubmit =  sbConfig.ds == "yes";
        var searched = false;
        var dbChanged = null; //since db.change is triggered as a work around for JSL-2067 
        var searchModified = false; //this is used to allow searching when something esle changed on the page with out the term changing
    
        if(!$.ncbi)
            $.extend($,{ncbi:{}});
        if(!$.ncbi.searchbar)
            $.extend($.ncbi,{searchbar:{}});
            
        $.extend($.ncbi.searchbar,
            (function(){
                //*****************private ******************/
               function doSearchPing() {
                   try{
                    var cVals = ncbi.sg.getInstance()._cachedVals;
                    var searchDetails = {}
                    searchDetails["jsEvent"] = "search";
                    var app = cVals["ncbi_app"];
                    var db = cVals["ncbi_db"];
                    var pd = cVals["ncbi_pdid"];
                    var pc = cVals["ncbi_pcid"];
                    var sel = dbNode[0];
                    var searchDB = sel.options[sel.selectedIndex].value;
                    var searchText = theSearchInput[0].value;
                    if( app ){ searchDetails["ncbi_app"] = app.value; }
                    if( db ){ searchDetails["ncbi_db"] = db.value; }
                    if( pd ){ searchDetails["ncbi_pdid"] = pd.value; }
                    if( pc ){ searchDetails["ncbi_pcid"] = pc.value; }
                    if( searchDB ){ searchDetails["searchdb"] = searchDB;}
                    if( searchText ){ searchDetails["searchtext"] = searchText;}
                    ncbi.sg.ping( searchDetails );
                   }catch(e){
                       console.log(e);
                   }
                }
                function getSearchUrl(term){
                    var url = "";
                    if (typeof(NCBISearchBar_customSearchUrl) == "function") 
                            url = NCBISearchBar_customSearchUrl();
                    if (!url) {
                        var searchURI = dbNode.find("option:selected").data("search_uri");
                        url = searchURI ?  searchURI.replace('$',term) : 
                             "/" + dbNode.val() + "/" + ( term !="" ? "?term=" + term : "");
                        }
                    return url;
                }
            
                return {
                    //*****************exposed attributes and functions ******************/
                    'theSearchInput':theSearchInput,
                    'theForm':theForm,
                    'dbNode':dbNode,
                    'searched':searched,
                    'setSearchModified':function() { searchModified = true; },
                    'setSearchUnmodified':function() { searchModified = false; },
                    'searchModified':function(){return searchModified;},
                    'doSearch':function(e){
                           e.stopPropagation();
                           e.preventDefault();
                           //checking for the searched flag is necessary because the autocompelete control fires on enter key, the form submit also fires on enter key
                           if(searched == false){
                               searched = true;
                               theForm.find('input[type="hidden"][name^="p$"]').attr('disabled', 'disabled');
                               //$("input[name]").not(jQuery(".search_form *")).attr('disabled', 'disabled');
                               if (defaultSubmit)
                                   $.ncbi.searchbar.doSearchPing();
                               else {
                                   var term = $.trim(theSearchInput.val());
                                   if (dbChanged || searchModified || term !== originalTerm){
                                       $.ncbi.searchbar.doSearchPing();
                                       var searchUrl = $.ncbi.searchbar.getSearchUrl(encodeURIComponent(term).replace(/%20/g,'+'));
                                       var doPost = (term.length  > 2000) ? true : false; 
                                       if (doPost){
                                           if (e.data.usepjs){
                                               Portal.$send('PostFrom',{"theForm":theForm,"term":term,"targetUrl":searchUrl.replace(/\?.*/,'')});
                                           }
                                           else{
                                               theForm.attr('action',searchUrl.replace(/\?.*/,''));
                                               theForm.attr('method','post');
                                           }
                                       }
                                       else {
                                           window.location = searchUrl;
                                       }
                                   }
                                   else{ //if (term !== originalTerm){
                                       searched = false;
                                   }
                               }
                           }
                    },
                    'onDbChange':function(e){
                         if (dbChanged === null)
                             dbChanged = false;
                         else
                             dbChanged = true;
                         var optionSel = $(e.target).find("option:selected");
                         var dict = optionSel.data("ac_dict");
                         if (dict){
                             //theSearchInput.ncbiautocomplete("option","isEnabled",true).ncbiautocomplete("option","dictionary",dict);
                             theSearchInput.ncbiautocomplete({
                                    isEnabled: true,
                                    dictionary: dict
                                });
                             theSearchInput.attr("title","Search " + optionSel.text() + ". Use up and down arrows to choose an item from the autocomplete.");
                         }
                         else{
                           theSearchInput.ncbiautocomplete("turnOff",true);
                           theSearchInput.attr("title", "Search " + optionSel.text());
                         }
                         if (defaultSubmit)
                            theForm.attr('action','/' + dbNode.val() + '/');  
                    },
                    'doSearchPing':function(){
                        doSearchPing();
                    },
                    'getSearchUrl':function(term){
                        return getSearchUrl(term);
                    }
                    
                };//end of return 
             })() //end of the self executing anon
        );//end of $.extend($.ncbi.searchbar
    
         function initSearchBar(usepjs){
            //enable the controls for the back button
            theForm.find('input[type="hidden"][name^="p$"]').removeAttr('disabled');
             if (usepjs)
                 portalSearchBar();
         }
         
        
    
        function portalSearchBar(){
            
            Portal.Portlet.NcbiSearchBar = Portal.Portlet.extend ({
                init:function(path,name,notifier){
                    this.base (path, name, notifier);
                },
                send:{
                    "Cmd":null,
                    "Term":null
                },
                "listen":{
                    "PostFrom":function(sMessage,oData,sSrc){
                        this.postForm(oData.theForm,oData.term,oData.targetUrl);
                    }
                },
                "postForm":function(theForm,term,targetUrl){
                       //console.log('targetUrl = ' + targetUrl);
                       theForm.attr('action',targetUrl);
                       theForm.attr('method','post');
                       this.send.Cmd({
                            'cmd' : 'Go'
                        });
                           this.send.Term({
                            'term' : term
                        });
                        Portal.requestSubmit();
                },
                'getPortletPath':function(){
                    return this.realpath + '.Entrez_SearchBar';
                }
            });
    
        }//portalSearchBar
        


         //portal javascript is required to make a POST when the rest of the app uses portal forms 
         var usepjs = sbConfig.pjs == "yes"; 
         //console.log('sbConfig',sbConfig);
         initSearchBar(usepjs);
         
         dbNode.on("change",$.ncbi.searchbar.onDbChange);
        
        theForm.on("submit",{'usepjs':usepjs},$.ncbi.searchbar.doSearch);
        theSearchInput.on("ncbiautocompleteenter ncbiautocompleteoptionclick", function(){theForm.submit();});
        //a work around for JSL-2067
        dbNode.trigger("change");
        //iOS 8.02 changed behavior on autofocus, should probably check other mobile devices too
        if (sbConfig.afs == "yes" && !/(iPad|iPhone|iPod)/g.test(navigator.userAgent) ){ 
            window.setTimeout(function(){
                try{
                    var size= originalTerm.length;
                    if (size == 0 || /\s$/.test(originalTerm))
                        theSearchInput.focus()[0].setSelectionRange(size, size);
                    else
                        theSearchInput.focus().val(originalTerm + " ")[0].setSelectionRange(size+1, size+1);
                }
                catch(e){} //setSelectionRange not defined in IE8
            },1);
        }
        
        //set the query changed flag true after a few seconds, still prevents scripted clicking or stuck enter key
        window.setTimeout(function(){$.ncbi.searchbar.setSearchModified();},2000);
         
     });//End of DOM Ready

})(jQuery);

/*
a call back for the 'Turn off' link at the bottom of the auto complete list
*/
function NcbiSearchBarAutoComplCtrl(){
    jQuery("#term").ncbiautocomplete("turnOff",true);
    if (typeof(NcbiSearchBarSaveAutoCompState) == 'function')
        NcbiSearchBarSaveAutoCompState();
 }

 



;
jQuery(function () {
    Portal.Portlet.Entrez_SearchBar = Portal.Portlet.NcbiSearchBar.extend ({
        init:function(path,name,notifier){
            this.base (path, name, notifier);
            var oThis = this;
            jQuery("#database").on("change", function(){
                oThis.send.DbChanged({'db' : this.value});
            });
        },
        send:{
            "Cmd":null,
            "Term":null,
            "DbChanged":null
        },
        'listen':{
            "PostFrom":function(sMessage,oData,sSrc){
        	    this.postForm(oData.theForm,oData.term,oData.targetUrl);
        	    },
            "ChangeAutoCompleteState": function(sMessage, oData, sSrc) {
        	    this.ChangeAutoCompleteState(sMessage, oData, sSrc);
                },
            'CreateRssFeed':function(sMessage,oData,sSrc){
                this.createRssFeed(sMessage,oData,sSrc);
            },
            'AppendTerm': function(sMessage, oData, sSrc) {
    		    this.ProcessAppendTerm(sMessage, oData, sSrc);
    		},
    		// to allow any other portlet to clear term if needed  
    		'ClearSearchBarTerm': function(sMessage, oData, sSrc) {
    			jQuery("#term").val("");
    		},
    		// request current search bar term to be broadcast  
    		'SendSearchBarTerm': function(sMessage, oData, sSrc) {
    			this.send.Term({'term' : jQuery("#term").val()});
    		}
        },
        'createRssFeed':function(sMessage,oData,sSrc){
            
            var site = document.forms[0]['p$st'].value;
    	   	var portletPath = this.getPortletPath();
    	   	
            try{
                var resp = xmlHttpCall(site, portletPath, 'CreateRssFeed', oData, receiveRss, {}, this);
            }
            catch (err){
                alert ('Could not create RSS feed.');
            }
            function receiveRss(responseObject, userArgs) {
        	    try{
            	    //Handle timeouts 
            	    if(responseObject.status == 408){
            	        //display an error indicating a server timeout
            	        alert('RSS feed creation timed out.');
            	    }
            	    
            	    // deserialize the string with the JSON object 
            	    var response = '(' + responseObject.responseText + ')'; 
            	    var JSONobject = eval(response);
            	    // display link to feed
            	    jQuery('#rss_menu').html(JSONobject.Output,true);
            	    //jQuery('#rss_dropdown a.jig-ncbipopper').trigger('click');
            	    jQuery('#rss_dropdown a.jig-ncbipopper').ncbipopper('open');
            	    //document.getElementById('rss_menu').innerHTML = JSONobject.Output;
                }
                catch(e){
                    alert('RSS unavailable.');
                }
            }
                
        },
        'getPortletPath':function(){
            return this.realpath + '.Entrez_SearchBar';
        },
        "ChangeAutoCompleteState": function(sMessage, oData, sSrc){
            var site = document.forms[0]['p$st'].value;
            var resp = xmlHttpCall(site, this.getPortletPath(), "ChangeAutoCompleteState", {"ShowAutoComplete": 'false'}, function(){}, {}, this);
        },
        "ProcessAppendTerm" : function(sMessage, oData, sSrc){
            var theInput = jQuery("#term");
    	    var newTerm = theInput.val();
    	    if (newTerm != '' && oData.op != ''){
    	        newTerm = '(' + newTerm + ') ' + oData.op + ' ';
    	    }
    	    newTerm += oData.term;
    	    theInput.val(newTerm); 
    	    
    	    theInput.focus();
    	}
    }); //end of Portlet.extend
}); //end of jQuery ready

function NcbiSearchBarSaveAutoCompState(){
    Portal.$send('ChangeAutoCompleteState');
}


;
jQuery(function() {
Portal.Portlet.SearchBar = Portal.Portlet.Entrez_SearchBar.extend ({
  
	init: function (path, name, notifier) {
		this.base (path, name, notifier);
		console.log('search modified true');
		// BK-10103 tell search bar to submit even if term hasn't been changed
		jQuery.ncbi.searchbar.setSearchModified(true);
	},

	/* ######### this is a hack. See detailed comment on same function in base */
	"getPortletPath" : function(){
	    return (this.realname + ".Entrez_SearchBar");
	}
});

});
;
Portal.Portlet.EmailTab = Portal.Portlet.extend({

	init: function(path, name, notifier) {
		this.base(path, name, notifier);
	},
	
	listen: {
		
		/* browser events */
		
		'SendMail': function(sMessage, oData, sSrc) {
			this.setValue('EmailReport', oData.report);
			this.setValue('EmailFormat', oData.format);
			this.setValue('EmailCount', oData.count);
			this.setValue('EmailStart', oData.start);
			this.setValue('EmailSort', oData.sort);
			this.setValue('Email', oData.email);
			this.setValue('EmailSubject', oData.subject);
			this.setValue('EmailText', oData.text);
            this.setValue('EmailQueryKey', oData.querykey);
			this.setValue('QueryDescription', oData.querydesc);
		}

	}
});
;
(function( $ ){ // pass in $ to self exec anon fn

    // on page ready
    $( function() {
    
        $( 'div.portlet' ).each( function() {

            // get the elements we will need
            var $this = $( this );
            var anchor = $this.find( 'a.portlet_shutter' );
            var portBody = $this.find( 'div.portlet_content' );

            // we need an id on the body, make one if it doesn't exist already
            // then set toggles attr on anchor to point to body
            var id = portBody.attr('id') || $.ui.jig._generateId( 'portlet_content' );
            portBody.attr('id', id );
            anchor.attr('toggles', id );

            // initialize jig toggler with proper configs, then remove some classes that interfere with 
            // presentation
            var togglerOpen = anchor.hasClass('shutter_closed')? false : true; 
            anchor.ncbitoggler({
                isIcon: false,
                initOpen: togglerOpen 
            }).
                removeClass('ui-ncbitoggler-no-icon').
                removeClass('ui-widget');

            // get rid of ncbitoggler css props that interfere with portlet styling, this is hack
            // we should change how this works for next jig release
            anchor.css('position', 'absolute').
                css('padding', 0 );

            $this.find( 'div.ui-helper-reset' ).
                removeClass('ui-helper-reset');

            portBody.removeClass('ui-widget').
                css('margin', 0);

            // trigger an event with the id of the node when closed
            anchor.bind( 'ncbitogglerclose', function() {
                anchor.addClass('shutter_closed');
            });

            anchor.bind('ncbitoggleropen', function() {
                anchor.removeClass('shutter_closed');
            });

        });  // end each loop          
    });// end on page ready
})( jQuery );
/*
jQuery(document).bind('ncbitogglerclose ncbitoggleropen', function( event ) {
           var $ = jQuery;
           var eventType = event.type;
           var t = $(event.target);
           
          alert('event happened ' + t.attr('id'));
   
           if ( t.hasClass('portlet_shutter') || false ) { // if it's a portlet
               // get the toggle state
               var sectionClosed = (eventType === 'ncbitogglerclosed')? 'true' : 'false';
               alert ('now call xml-http');

            }
        });
*/

Portal.Portlet.NCBIPageSection = Portal.Portlet.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);
		
		this.AddListeners();
	},
    
	"AddListeners": function(){
        var oThis = this;
        
		jQuery(document).bind('ncbitogglerclose ncbitoggleropen', function( event ) {
            var $ = jQuery;
            var eventType = event.type;
            var t = $(event.target);
            
            // proceed only if this is a page section portlet {
            if ( t.hasClass('portlet_shutter')){
                var myid = '';
                if (oThis.getInput("Shutter")){
                    myid = oThis.getInput("Shutter").getAttribute('id');
                }
    
                // if the event was triggered on this portlet instance
                if (t.attr('id') && t.attr('id') == myid){
                    // get the toggle state
                    var sectionClosed = (eventType === 'ncbitogglerclose')? 'true' : 'false';
                    // react to the toggle event
                    oThis.ToggleSection(oThis.getInput("Shutter"), sectionClosed);
                }
            } // if portlet            
        });
	},
	
	"ToggleSection": function(target, sectionClosed){
	   // if remember toggle state, save the selection and log it
	   if (target.getAttribute('remembercollapsed') == 'true'){
	       this.UpdateCollapsedState(target, sectionClosed);
	   }else {
	       this.LogCollapsedState(target, sectionClosed);
	   }
	},
	
	"UpdateCollapsedState": function(target, sectionClosed){
	    var site = document.forms[0]['p$st'].value;
	    var args = { "PageSectionCollapsed": sectionClosed, "PageSectionName": target.getAttribute('pgsec_name')};
	    // Issue asynchronous call to XHR service
        var resp = xmlHttpCall(site, this.getPortletPath(), "UpdateCollapsedState", args, this.receiveCollapse, {}, this);  
	},
	
	"LogCollapsedState": function(target, sectionClosed){
	    var site = document.forms[0]['p$st'].value;
	    // Issue asynchronous call to XHR service
        var resp = xmlHttpCall(site, this.getPortletPath(), "LogCollapsedState", {"PageSectionCollapsed": sectionClosed}, this.receiveCollapse, {}, this);  
	},
	
	'getPortletPath': function(){
        return this.realname;
    }, 
    
    receiveCollapse: function(responseObject, userArgs) {
    }
	
});
		 
;
Portal.Portlet.SensorPageSection = Portal.Portlet.NCBIPageSection.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);
	}
});

(function( $ ){ // pass in $ to self exec anon fn

    // on page ready
    $( function() {
    
        $( 'div.sensor' ).each( function() {

            // get the elements we will need
            var $this = $( this );
            var anchor = $this.find( 'a.portlet_shutter' );
            var portBody = $this.find( 'div.sensor_content' );

            // we need an id on the body, make one if it doesn't exist already
            // then set toggles attr on anchor to point to body
            var id = portBody.attr('id') || $.ui.jig._generateId( 'sensor_content' );
            portBody.attr('id', id );
            anchor.attr('toggles', id );

            // initialize jig toggler with proper configs, then remove some classes that interfere with 
            // presentation
            var togglerOpen = anchor.hasClass('shutter_closed')? false : true; 
            anchor.ncbitoggler({
                isIcon: false,
                initOpen: togglerOpen 
            }).
                removeClass('ui-ncbitoggler-no-icon').
                removeClass('ui-widget');

            // get rid of ncbitoggler css props that interfere with portlet styling, this is hack
            // we should change how this works for next jig release
            anchor.css('position', 'absolute').
                css('padding', 0 );

            $this.find( 'div.ui-helper-reset' ).
                removeClass('ui-helper-reset');

            portBody.removeClass('ui-widget').
                css('margin', 0);

            // trigger an event with the id of the node when closed
            anchor.bind( 'ncbitogglerclose', function() {
                anchor.addClass('shutter_closed');
            });

            anchor.bind('ncbitoggleropen', function() {
                anchor.removeClass('shutter_closed');
            });

        });  // end each loop          
    });// end on page ready
})( jQuery );
;
Portal.Portlet.SmartSearch = Portal.Portlet.SensorPageSection.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);
	}
});


;
Portal.Portlet.GeneSensor = Portal.Portlet.SensorPageSection.extend({
    init: function (path, name, notifier) {
        var oThis = this;
		console.info("Created GeneSensor");
		this.base(path, name, notifier);
		
		/*To add linkpos to species links*/
		jQuery(".speciesline .specieslink").each(function(index){
		    var ref = jQuery(this).attr('ref');
		    ref= ref+"&linkpos="+(index+1);
		    jQuery(this).attr('ref', ref);
		});
    },
    
    send: { 
        'Cmd': null, 
        //'DbChanged': null,
        'LinkName': null,
        //'PresentationChange': null,
        'LastQueryKey': null       
    }, 
    
    listen: {       
        'GeneLink<click>':function (e, target, name) {
            //this.send.DbChanged({'db' : 'gene'});
            this.send.Cmd({'cmd' : 'link'});
            this.send.LinkName({'linkname' : 'gene_pubmed_rif'});
            this.send.LastQueryKey({'qk': target.getAttribute('value')});           
            Portal.requestSubmit(); 
        }        
    }
});
;
Portal.Portlet.Entrez_DisplayBar = Portal.Portlet.extend({

	init: function(path, name, notifier) {
		console.info("Created DisplayBar");
		this.base(path, name, notifier);
		
		// for back button compatibility reset values when page loads
		if (this.getInput("Presentation")){
		    this.setValue("Presentation", this.getValue("LastPresentation"));
		    Portal.Portlet.Entrez_DisplayBar.Presentation = this.getValue("LastPresentation");
		}
		if (this.getInput("Format")){
		    this.setValue("Format", this.getValue("LastFormat"));
		    Portal.Portlet.Entrez_DisplayBar.Format = this.getValue("LastFormat");
		}
		if (this.getInput("PageSize")){
		    this.setValue("PageSize", this.getValue("LastPageSize"));
		    Portal.Portlet.Entrez_DisplayBar.PageSize = this.getValue("LastPageSize");
		}
		if (this.getInput("Sort")){
		    this.setValue("Sort", this.getValue("LastSort"));
		    Portal.Portlet.Entrez_DisplayBar.Sort = this.getValue("LastSort");
		}
		this.ResetDisplaySelections();
		this.ResetSendToSelection();
		
    	jQuery( 
            function(){
        
                var animationTime = jQuery("#sendto2").ncbipopper("option","openAnimationTime");
                var currentCnt = 0;
                var expTimer;
        
                function testPosition(){
                    jQuery(window).trigger("ncbipopperdocumentresize");
                    currentCnt+=10;
                    if (currentCnt<animationTime) {
                        expTimer = window.setTimeout(testPosition,10);
                    }
                }
        
                jQuery("#send_to_menu2 input").on("change click", 
                    function(){
                        currentCnt = 0;
                        if(expTimer) window.clearTimeout(expTimer);
                        testPosition();
                    } 
                );
        
            }
        );
		        
	},
	
	
	send: {
		'Cmd': null, 
		'PageSizeChanged': null,
		'ResetSendTo': null,
		'ResetCurrPage': null
	},
	
	
	
	listen: {
		
		/* browser events */
			
		"sPresentation<click>": function(e, target, name){
		    this.PresentationClick(e, target, name); 
		},
		
		"sPresentation2<click>": function(e, target, name){
		    this.PresentationClick(e, target, name); 
		},
		
		"sPageSize<click>": function(e, target, name){	
		    this.PageSizeClick(e, target, name);
		},
		
		"sPageSize2<click>": function(e, target, name){	
		    this.PageSizeClick(e, target, name);
		},
		
		"sSort<click>": function(e, target, name){
		    this.SortClick(e, target, name);
		},
		
		"sSort2<click>": function(e, target, name){
		    this.SortClick(e, target, name);
		},
		
		"SetDisplay<click>": function(e, target, name){
			this.DisplayChange(e, target, name); 
		},
		
		"SendTo<click>": function(e, target, name){
			var sendto = target.value;
            var idx = target.getAttribute('sid') > 10? "2" : "";
			this.SendToClick(sendto, idx, e, target, name); 
		},
		
		"SendToSubmit<click>": function(e, target, name){
		    e.preventDefault();
		    var cmd = target.getAttribute('cmd').toLowerCase();
		    var idx = target.getAttribute('sid') > 10? "2" : "";
			this.SendToSubmitted(cmd, idx, e, target, name); 
		},
		
		/* messages from message bus*/
		
		'ResetSendTo' : function(sMessage, oData, sSrc) {
		    this.ResetSendToSelection();
		}
	
	}, // end listen
	
	
	
	/* functions */
	
	'PresentationClick': function(e, target, name){
		Portal.Portlet.Entrez_DisplayBar.Presentation = target.value;
		Portal.Portlet.Entrez_DisplayBar.Format = target.getAttribute('format');
		this.DisplayChange();
	},
	
	'PageSizeClick': function(e, target, name){ 
		Portal.Portlet.Entrez_DisplayBar.PageSize = target.value;
		this.DisplayChange();
	},
	
	'SortClick': function(e, target, name){
		Portal.Portlet.Entrez_DisplayBar.Sort = target.value;
		this.DisplayChange();
	},
	
	'DisplayChange': function(e, target, name){
	    var submit = false;
	    var extractdb = window.location.pathname.match(/\/([A-Za-z]+)\/?/); 
	    var db = (extractdb[1] && extractdb[1] != '') ? extractdb[1] : "";
	    
	    if (db != '' && getEntrezSelectedItemCount() == 1){
	        //get id, attach db and report, and link	        
	        var URL = '/' + db + '/' + getEntrezSelectedItemList() + '?report=' + Portal.Portlet.Entrez_DisplayBar.Presentation
	        + (Portal.Portlet.Entrez_DisplayBar.Format.toLowerCase() == 'text' ? '&format=text' : '');
	        window.location = URL;
	    }
	    else if (db != '' && getEntrezResultCount() == 1 && window.location.href != ""){   
	        //remove report= from URL and insert new report= into URL
	        if ((window.location.pathname != '' && window.location.pathname.match(/\/[A-Za-z]+\/\w*\d+\w*/))
	            || window.location.href.match(/\/[A-Za-z]+\/??.*term=[^&\s]+/)
	        ){
	            var URL = window.location.href.replace(/&?report=\w+/, "").replace(/\?&/, "?");
	            var hashtagindex = URL.indexOf("#");
	            if (hashtagindex >= 0){
	                URL = URL.substring(0, hashtagindex);
	            }
	            URL += (URL.match(/\?/) ? (URL.match(/\?[^\s]+/) ? "&" : "") : "?") 
	                + "report=" + Portal.Portlet.Entrez_DisplayBar.Presentation
	                + (Portal.Portlet.Entrez_DisplayBar.Format.toLowerCase() == 'text' ? '&format=text' : '');
	            window.location = URL;    
	        }
	        else {
	            submit = true;
	        }
	    }
	    else{
            submit = true;
        }
        
        if (submit){
            this.send.Cmd({'cmd': 'displaychanged'});
            
    	    this.SetPresentationChange(e, target, name);
    	    this.SetPageSizeChange(e, target, name);
    	    this.SetSortChange(e, target, name);
    	    
    	    Portal.requestSubmit();
	    }
	},
	
	'SetPresentationChange': function(e, target, name){
        this.setValue("Presentation", Portal.Portlet.Entrez_DisplayBar.Presentation);
	    this.setValue("Format", Portal.Portlet.Entrez_DisplayBar.Format);
	},
	
	'SetPageSizeChange': function(e, target, name){
	    this.setValue("PageSize", Portal.Portlet.Entrez_DisplayBar.PageSize);
		if (this.getValue("PageSize") != this.getValue("LastPageSize")){
    		//send PageSizeChanged
    		this.send.PageSizeChanged({
    			'size': this.getValue("PageSize"),
                'oldsize': this.getValue("LastPageSize")
    		});	
		}
	},
		
	'SetSortChange': function(e, target, name){
	    if (this.getInput("Sort")){
	        this.setValue("Sort", Portal.Portlet.Entrez_DisplayBar.Sort);
            if (this.getValue("Sort") != this.getValue("LastSort")){
                // ask to reset CurrPage 
    		    this.send.ResetCurrPage();
    		}
    		
    		// set sort in cookie   		
    		var extractdb = window.location.pathname.match(/\/([A-Za-z]+)\/?/); 
    	    var db = (extractdb[1] && extractdb[1] != '') ? extractdb[1] : "";
    	    
    		this.SetSortCookie(Portal.Portlet.Entrez_DisplayBar.Sort, db);
        }    	
	},
		
	'SendToClick': function(sendto, idx, e, target, name) {
		if(sendto.toLowerCase() == 'file'){
			this.SendToFile(sendto, idx);
		}
		else if(sendto.toLowerCase() == 'addtocollections'){
			this.SendToCollections(sendto, idx);
		}
		else if(sendto.toLowerCase() == 'addtoclipboard'){
		    this.SendToClipboard(sendto, idx);
		}
	},
	
	'SendToSubmitted': function(cmd, idx, e, target, name){
	    if (cmd == 'file'){
	         this.SendToFileSubmitted(cmd, idx, target);
	    }
	    else if (cmd == 'addtocollections'){
	    	this.SendToCollectionsSubmitted(cmd, idx, target);
	    }
	    this.send.Cmd({'cmd': cmd});
	    Portal.requestSubmit();
	},
	
	'ResetSendToSelection': function(){
	    var SendToInputs = this.getInputs("SendTo");
	    for (var j = 0; j < SendToInputs.length; j++){
		    if (SendToInputs[j].checked){
		        SendToInputs[j].checked = false;
			}
		}
	},
	
	'SendToFile': function(name, idx){
	    // generate content
	    var count = this.getItemCount();
		var content = 'Download ' + count + ' items.';
		this.addSendToHintContent(name, idx, content);
	},
	
	'SendToCollections': function(name, idx){
	    // generate content
        var count = this.getItemCount();
        var content= 'Add ';
        var optionNode = document.getElementById("coll_start_option" + idx);
        if (count > Portal.Portlet.Entrez_DisplayBar.CollectionsUpperLimit){
            content += Portal.Portlet.Entrez_DisplayBar.CollectionsUpperLimitText;
            if (optionNode){
            	optionNode.className = '';
            }
        }
        else{
            content += count;
            if (optionNode){
            	optionNode.className = 'hidden';
            }
        }
        content += " items.";
        this.addSendToHintContent(name, idx, content);	
	},
	
	'SendToClipboard': function(name, idx){
	    // generate content
	    var count = this.getItemCount();
        var content= 'Add ';
        if (count > Portal.Portlet.Entrez_DisplayBar.ClipboardLimit){
            content += "the first " + Portal.Portlet.Entrez_DisplayBar.ClipboardLimit;
        }
        else{
            content += count;
        }
        content += " items.";
        this.addSendToHintContent(name, idx, content);
	},
	
	'getItemCount': function(){
	    // ask for selected items count from DbConnector
	    var selectedItemCount = getEntrezSelectedItemCount();
	    if (selectedItemCount > 0){
	        return selectedItemCount;
	    }
	    else{
	        // ask for result count from Entrez_ResultsController
	        return getEntrezResultCount();
	    }
	},
	
	'addSendToHintContent': function(name, idx, content){
	    var hintNode = document.getElementById("submenu_" + name + "_hint" + idx);
	    if (hintNode){
	        hintNode.innerHTML = content;
	        hintNode.className = 'hint';
	    }
	},
	
	'AddSendToSubmitEvent': function(){
	    // add event for SendTo submit button click. 
	    // This call is needed if the position of the submit button node has changed in relation to its parent node. 
        this.addEvent("SendToSubmit", "click", function(e, target, name) {
            var cmd = target.getAttribute('cmd');
            this.SendToSubmitted(cmd, e, target, name); 
        }, false);
    },
    
    'SendToFileSubmitted': function(cmd, idx, target){
         if (this.getInput("FFormat" + idx)){
             this.setValue("FileFormat", this.getValue("FFormat" + idx));
         }
         if (this.getInput("FSort" + idx)){
             this.setValue("FileSort", this.getValue("FSort" + idx));
         }
    },
    
    'SendToCollectionsSubmitted': function(cmd, idx, target){
         if (document.getElementById("coll_start" + idx)){
             document.getElementById("coll_startindex").value = document.getElementById("coll_start" + idx).value;
         }
    },
    
    'ResetDisplaySelections': function(){
        if (this.getInput("Presentation")){
            var selection = this.getValue("Presentation").toLowerCase() + this.getValue("Format").toLowerCase();
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
            
        }
        if (this.getInput("PageSize")){
            var selection = 'ps' + this.getValue("PageSize");
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
        }
        if (this.getInput("Sort")){
            var selection = this.getValue("Sort") || 'none'; 
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
        }
    },
    
    'SetSortCookie': function(sort, db){
	    if (db != ''){
           /* var d = new Date();
            d.setTime(d.getTime() + (365*24*60*60*1000));
            var expires = "expires="+d.toUTCString();
            document.cookie = "ncbi_Sort=" + db + ":" + target.value + "; " + expires;
            */
		}
    }	
	
},
{
    Presentation: '',
    Format: '',
    PageSize: '',
    Sort: '',
    CollectionsUpperLimit: 1000,
	CollectionsUpperLimitText: '1,000',
	ClipboardLimit: 500
});


;
Portal.Portlet.DisplayBar = Portal.Portlet.Entrez_DisplayBar.extend
({
	init: function(path, name, notifier) 
	{
		this.base( path, name, notifier);
		
		if (this.getInput("SortBy")){
		    this.setValue("SortBy", this.getValue("LastSortBy"));
		    Portal.Portlet.Entrez_DisplayBar.GroupBy = this.getValue("LastSortBy");
		}		
	},
	
	send: {
		'Cmd': null, 
		'PageSizeChanged': null,
		'ResetSendTo': null,
		'ResetCurrPage': null,
		'SendMail': null,
		'SortByChanged': null 
	},
	
	listen: {
		
		/* browser events */
			
		"sPresentation<click>": function(e, target, name){
		    this.PresentationClick(e, target, name); 
		},
		
		"sPresentation2<click>": function(e, target, name){
		    this.PresentationClick(e, target, name); 
		},
		
		"sPageSize<click>": function(e, target, name){	
		    this.PageSizeClick(e, target, name);
		},
		
		"sPageSize2<click>": function(e, target, name){	
		    this.PageSizeClick(e, target, name);
		},
		
		"sSort<click>": function(e, target, name){
		    this.SortClick(e, target, name);
		},
		
		"sSort2<click>": function(e, target, name){
		    this.SortClick(e, target, name);
		},
		
		//Books
		"sSortBy<click>": function(e, target, name){
		    this.SortByClick(e, target, name);
		},
		
		"SetDisplay<click>": function(e, target, name){
			this.DisplayChange(e, target, name); 
		},
		
		"SendTo<click>": function(e, target, name){
			var sendto = target.value;
            var idx = target.getAttribute('sid') > 10? "2" : "";
			this.SendToClick(sendto, idx, e, target, name); 
		}, 
		
		"SendToSubmit<click>": function(e, target, name){
		    var cmd = target.getAttribute('cmd').toLowerCase();
		    var idx = target.getAttribute('sid') > 10? "2" : "";
			this.SendToSubmitted(cmd, idx, e, target, name); 
		},
		
		/* messages from message bus*/
		
		'ResetSendTo' : function(sMessage, oData, sSrc) {
		    this.ResetSendToSelection();
		}	
	}, // end listen
	
	/* functions */
	'SortByClick': function(e, target, name){
		Portal.Portlet.Entrez_DisplayBar.SortBy = target.value;
		Portal.Portlet.Entrez_DisplayBar.SortByChanged = true;
	},
	
	'SetSortByChange': function(e, target, name){
	    if (this.getInput("SortBy")){
	        this.setValue("SortBy", Portal.Portlet.Entrez_DisplayBar.SortBy);            
        }    	
	},
	
	'DisplayChange': function(e, target, name){
        if (Portal.Portlet.Entrez_DisplayBar.SortByChanged == true) {
            this.send.SortByChanged({'value': 'yes'});//Search Controller would use this combined w/ cmd
        }
        this.SetSortByChange(e, target, name);
        
        this.base();
/* EZ-7958
        this.send.Cmd({'cmd': 'displaychanged'});
        
	    this.SetPresentationChange(e, target, name);
	    this.SetPageSizeChange(e, target, name);
	    this.SetSortChange(e, target, name);
	    
    
	    Portal.requestSubmit();
*/	
    },
	
	/* reuse PubMed code for Send to Email */
	'SendToClick': function(sendto, idx,  e, target, name) { 
	    if (sendto.toLowerCase() == 'poptext'){
	        this.SendToText(sendto, idx);
	    }
	    else if (sendto.toLowerCase() == 'mail'){
	        this.SendToMail(sendto, idx);
	    }
	    else if (sendto.toLowerCase() == 'addtobibliography'){
	        this.SendToBib(sendto, idx);
	    }
	    else
	        this.base(sendto, idx, e, target, name);
	},
	
	'SendToFile': function(name, idx){
	    // generate content
	    var count = this.getItemCount();
		var content = 'Download ' + count + ' item'+(count > 1? 's' : '')+'.';
		this.addSendToHintContent(name, idx, content);
	},
	
	'SendToCollections': function(name, idx){
	    // generate content
        var count = this.getItemCount();
		var content = 'Add ' + count + ' item'+(count > 1? 's' : '')+'.';
        this.addSendToHintContent(name, idx, content);	
	},
	
	'SendToClipboard': function(name, idx){
	    // generate content
	    var count = this.getItemCount();
        var content= 'Add ';
        if (count > Portal.Portlet.Entrez_DisplayBar.ClipboardLimit){
            content += "the first " + Portal.Portlet.Entrez_DisplayBar.ClipboardLimit;
        }
        else{
            content += count;
        }
        content += ' item'+(count > 1? 's' : '')+'.';
        this.addSendToHintContent(name, idx, content);
	},
	
	
	'SendToMail': function(sendto, idx){
	    // hide any previous alert messages 
	    var alertnode = document.getElementById("email_alert" + idx);
	    alertnode.className = 'hidden';
	    
	    // ask for selected items count from DbConnector
	    var selectedItemCount = getEntrezSelectedItemCount() || 0;
	    var descNode = document.getElementById("email_desc" + idx);
        if (selectedItemCount > 0){
            if (Portal.Portlet.Entrez_DisplayBar.Description == '')
	            Portal.Portlet.Entrez_DisplayBar.Description = descNode.innerHTML;
	        descNode.innerHTML = selectedItemCount + " selected item" + (selectedItemCount > 1? "s" : "");
	    }
	    // if ids are not selected, and an old description or subject are present, restore those
	    else{
	        if ( Portal.Portlet.Entrez_DisplayBar.Description && Portal.Portlet.Entrez_DisplayBar.Description != '')
	            descNode.innerText = Portal.Portlet.Entrez_DisplayBar.Description;
        }
        
        // get total number of items about to be sent
        var count = this.getItemCount();
        
        // don't show email count and start options if less than 5 items are in search result, or user has selected some items
        if (document.getElementById("email_count_option" + idx)){
            if (count <= 5 || selectedItemCount > 1){
                document.getElementById("email_count_option" +  idx).style.display = "none";
            }
            else {
                document.getElementById("email_count_option" + idx).style.display = "list-item";
            }
        }
        if (document.getElementById("email_start_option" + idx)){
            if (count <= 5 || selectedItemCount > 1){
                document.getElementById("email_start_option" +  idx).style.display = "none";
            }
            else {
                document.getElementById("email_start_option" + idx).style.display = "list-item";
            }
        }
        
        // don't show sort option if 1 item is selected
        //if (document.getElementById("email_sort_option" + idx)){
        //    if (count == 1){
        //        document.getElementById("email_sort_option" + idx).style.display = "none";
        //    }
        //    else {
        //        document.getElementById("email_sort_option" + idx).style.display = "list-item";
        //    }
        //}
	},

	'SendToBib': function(name, idx){
	    // generate content
        var count = this.getItemCount();
        var content= 'Add ';
        if (count > Portal.Portlet.DisplayBar.BibUpperLimit){
            content += "the first " + Portal.Portlet.DisplayBar.BibUpperLimit;
        }
        else{
            content += count;
        }
        content += " items.";
        this.addSendToHintContent(name, idx, content);	
	},
		
	'SendToSubmitted': function(cmd, idx, e, target, name){
	    if (cmd.toLowerCase() == 'mail'){
	         this.SendToEmailSubmitted(cmd, idx, target);
	    }	    
	    else{
	        /*if (cmd.toLowerCase() == 'text'){
	            this.SendToTextSubmitted(cmd, idx, target);
	        }*/
	        this.base(cmd, idx, e, target, name);
	    }
	},
	
	'SendToEmailSubmitted': function(cmd, idx, target){
	    
	    var alertnode = document.getElementById("email_alert" + idx);
	    alertnode.className = 'hidden';
	    
	    var email = document.getElementById("email_address" + idx).value.replace(/^\s*|\s*$/g,'');
	    if (email == ''){
	        alertnode.innerHTML = 'Please provide an email address.';
	        alertnode.className = 'email_alert';
	    }
	    else {
    	    var emailRegexp = /^[A-Za-z0-9._\'%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}$/;
    		if (emailRegexp.test(email)){
        	    this.SendMailInfo(cmd, idx, target, email);		
    		}
    		else {
    			alertnode.innerHTML = 'The email address is invalid!';
	            alertnode.className = 'email_alert';
    		}
        }    		
	    
	},
	
	'SendMailInfo': function(cmd, idx, target, email){
	    // collect options, description and extra text
	    var emailFormat = document.getElementById("email_format" + idx);
	    var report = emailFormat.value;
	    var format =  emailFormat.options[emailFormat.selectedIndex].getAttribute('format');
	    var sort = document.getElementById("email_sort" + idx)? document.getElementById("email_sort").value : "";
	    if( sort == "Relevance" )
	    	sort = "";
	    var count = document.getElementById("email_count" + idx)? document.getElementById("email_count").value : "5";
	    var start = document.getElementById("email_start" + idx)? document.getElementById("email_start").value : "1";
	    var text = document.getElementById("email_add_text" + idx).value;
	    var querykey = target.getAttribute('qk');
	    var querydesc = document.getElementById("email_desc" + idx).innerHTML;
	    //var suppData = jQuery('#chkSupplementalData').attr('checked');
	    //if (suppData && report == 'abstract' && format != 'text' ) report = 'AbstractWithSupp';
	    
	    // send message to email portlet with data
	    this.send.SendMail({
	        'report' : report,
	        'format' : format,
	        'count' : count,
	        'start' : start,
	        'sort' : sort,
	        'email' : email,
	        'text' : text,
	        'subject' : 'Books Search Results',
	        'querykey': querykey,
	        'querydesc': querydesc /*,
	        'suppData' : suppData */
	    });
		    
	    this.send.Cmd({'cmd': cmd});
	    
        // Fix for BK-12079
	    // Set searchModified to false
	    jQuery.ncbi.searchbar.setSearchUnmodified();
	    
	    Portal.requestSubmit();
    },
    
    'ResetDisplaySelections': function(){
        //alert('yes');
        if (this.getInput("Presentation")){
            var selection = this.getValue("Presentation").toLowerCase() + this.getValue("Format").toLowerCase();
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
            
        }
        if (this.getInput("PageSize")){
            var selection = 'ps' + this.getValue("PageSize");
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
        }
        if (this.getInput("Sort")){
            var selection = this.getValue("Sort") || 'none'; 
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
        }
        if (this.getInput("SortBy")){
            var selection = this.getValue("SortBy") || 'none';
            if (document.getElementById(selection)){
                document.getElementById(selection).checked = true;
            }
            // bottom display bar
            if (document.getElementById(selection + "2")){
                document.getElementById(selection + "2").checked = true;
            }
        }
    }
},
{
    SortBy: '',
    SortByChanged: '', 
    BibUpperLimit: 500,
    Description: '',
    CollectionsUpperLimit: 10000,
	CollectionsUpperLimitText: '10,000'
});


;
Portal.Portlet.Entrez_ResultsController = Portal.Portlet.extend({

	init: function(path, name, notifier) {
		console.info("Created Entrez_ResultsController");
		this.base(path, name, notifier);
	},	
		
	send: {
	    'Cmd': null
	},
		
	listen: {
	
	    /* page events */
	    
	    "RemoveFromClipboard<click>": function(e, target, name){
            this.RemoveFromClipboardClick(e, target, name);
	    },
	    
		/* messages */
		
		'Cmd': function(sMessage, oData, sSrc){
		    this.ReceivedCmd(sMessage, oData, sSrc);
		},
		
		'SelectedItemCountChanged' : function(sMessage, oData, sSrc){
		    this.ItemSelectionChangedMsg(sMessage, oData, sSrc);
		},
		
		// currently sent by searchbox pubmed in journals 
		'RunLastQuery' : function(sMessage, oData, sSrc){
			if (this.getInput("RunLastQuery")){
				this.setValue ("RunLastQuery", 'true');
			}
		}
		
	},//listen
	
	'RemoveFromClipboardClick': function(e, target, name){
	    if(confirm("Are you sure you want to delete these items from the Clipboard?")){
	        this.send.Cmd({'cmd': 'deletefromclipboard'});
		    Portal.requestSubmit();  
    	}
	},
	
	// fix to not show remove selected items message when Remove from clipboard was clicked directly on one item
	'ReceivedCmd': function(sMessage, oData, sSrc){
	    if (oData.cmd == 'deletefromclipboard'){
	        Portal.Portlet.Entrez_ResultsController.RemoveOneClip = true;
	    }
	},
	
	'ItemSelectionChangedMsg': function(sMessage, oData, sSrc){
	    // do not show any messages if one item from clipbaord was removed with direct click.
	    if (Portal.Portlet.Entrez_ResultsController.RemoveOneClip){
	        Portal.Portlet.Entrez_ResultsController.RemoveOneClip = false;
	    }
	    else{
    		this.SelectedItemsMsg(oData.count);
    	    this.ClipRemoveMsg(oData.count);
    	}
	},
	
	'SelectedItemsMsg': function(count){
	    SelMsgNode = document.getElementById('result_sel');
	    if (SelMsgNode){
	        if (count > 0){
	            SelMsgNode.className = 'result_sel';
 	            SelMsgNode.innerHTML = "Selected: " + count;
 	        }
 	        else {
 	            SelMsgNode.className = 'none';
 	            SelMsgNode.innerHTML = "";
 	        }
	    }
	},
	
	'ClipRemoveMsg': function(count){
	    ClipRemNode = document.getElementById('rem_clips');
 	    if (ClipRemNode){
 	        if (count > 0){
 	            ClipRemNode.innerHTML = "Remove selected items";
 	        }
 	        else {
 	            ClipRemNode.innerHTML = "Remove all items";
 	        }
 	    }
	},
	
	'ResultCount': function(){
	    var totalCount = parseInt(this.getValue("ResultCount"));
	    totalCount = totalCount > 0 ? totalCount : 0;
	    return totalCount;
	}

},
{
    RemoveOneClip: false
});

function getEntrezResultCount() {
    var totalCount = document.getElementById("resultcount") ? parseInt(document.getElementById("resultcount").value) : 0;
	totalCount = totalCount > 0 ? totalCount : 0;
	return totalCount;
}

;
Portal.Portlet.ResultsController = Portal.Portlet.Entrez_ResultsController.extend({

	init: function(path, name, notifier) {
		this.base(path, name, notifier);		
	},
	
	listen: {	
	    /* page events */
	    
	    "RemoveFromClipboard<click>": function(e, target, name){
            this.RemoveFromClipboardClick(e, target, name);
	    },
	    
		/* messages */
		
		'Cmd': function(sMessage, oData, sSrc){
		    this.ReceivedCmd(sMessage, oData, sSrc);	    
		},
		
		'SelectedItemCountChanged' : function(sMessage, oData, sSrc){
		    this.ItemSelectionChangedMsg(sMessage, oData, sSrc);
		},
		
		// currently sent by searchbox pubmed in journals 
		'RunLastQuery' : function(sMessage, oData, sSrc){
			if (this.getInput("RunLastQuery")){
				this.setValue ("RunLastQuery", 'true');
			}
		},
		
		// special case of display change, msg sent from display bar  
		'SortByChanged' : function(sMessage, oData, sSrc){
			if (this.getInput("SortByChanged")){
				this.setValue ("SortByChanged", oData.value);
			}
		}
		
	}//listen
});

function getEntrezResultCount() {
    return $PN('ResultsController').ResultCount();
}



;
Portal.Portlet.Entrez_Pager = Portal.Portlet.extend ({

    init: function (path, name, notifier) {		
		this.base (path, name, notifier);
    },
   
   
    send: {
        'Cmd': null
    },
   
   
    listen: {
		// page events
		"Page<click>" : function(e, target, name){
			this.send.Cmd({'cmd': 'PageChanged'});
			this.setValue("CurrPage", target.getAttribute('page'));
			Portal.requestSubmit();
		},
		
		"cPage<keypress>" : function(e, target, name){
		    // get page event
		    var event = e || utils.fixEvent (window.event);
		    // if page event was trying to submit 
		    if ((event.keyCode || event.which) == 13) {
		        this.NewPage(event, target);
		    } 			
		},
		
		// messages

		// when pagesize is changed, pager adjusts page number to keep displaying the start 
		// the start item of the initial page
		'PageSizeChanged' : function(sMessage, oData, sSrc) {
			if (this.getInput("CurrPage")){
				var start = (oData.oldsize * (this.getValue("CurrPage") - 1)) + 1;
				var newPage = parseInt((start - 1)/oData.size) + 1;
				this.setValue("CurrPage", newPage);
			}
		},
		
		'ResetCurrPage' : function(sMessage, oData, sSrc) {
			if (this.getInput("CurrPage")){
				this.setValue("CurrPage", '1');
			}
		}

    },
    
    'NewPage': function (event, target){
        // stop event propagation
        event.returnValue = false;
        if (event.stopPropagation != undefined)
            event.stopPropagation ();   
        if (event.preventDefault != undefined)
            event.preventDefault ();    
        
        // get new page info
        newPage = target.value.replace(/,/, ''); // remove comma in page number;
        var npage = parseInt(newPage); 
        var lpage = parseInt(target.getAttribute('last'));
        var cpage = this.getValue("CurrPage");
        
        // check validity of new page
        if (!isNaN(lpage) && newPage != cpage){
             // if the page number entered is not a number or it is a negative number
            if (isNaN(npage) || npage <= 0) { 
                alert("This is not a valid page number: " + newPage); 
                target.value = cpage; 
            } 
            // if the entered value was changed during conversion due to forgiving extras
            else if (npage.toString() != newPage) { 
                alert("This is not a valid page number: " + newPage); 
                target.value = cpage; 
            } 
            // if the entered page is larger than the last page
            else if (npage > lpage) {
                alert("This number is outside the page range: " + newPage); 
                target.value = cpage; 
            }
            else {
                // update the page if entered page number was valid
                this.send.Cmd({'cmd': 'PageChanged'});
                this.setValue("CurrPage", newPage);
                Portal.requestSubmit();  
            } 
        }// end if max is not invalid
           
        return false;
    }
    
});

;
Portal.Portlet.Entrez_LimitsTab = Portal.Portlet.extend ({
  
	init: function (path, name, notifier) 
	{ 
		this.base (path, name, notifier);
		
		var limApplyBtn = jQuery("button[name$=ApplyLimits]");
		if(limApplyBtn[0]){
    		jQuery(document.forms[0]).off("submit").on("submit",function(e){
    		    e.preventDefault();
    		    limApplyBtn.trigger("click")
    		});
		}
	},

    /* If you have to OVERRIDE the send and listen sections, please make sure to include the code in 
    those sections here before your code. Same for init if you need to override it. All other functions
    will be carried over by Portal.Portlet.My_LimitsTab = Portal.Portlet.Entrez_LimitsTab.extend .
    */
    
	send: {
		"Cmd": null,
		"SendSearchBarTerm": null
	},
	
	listen: {
	
	    /* actions from the Limits activated message area */
		
		"ChangeLimits<click>": function(e, target, name) {
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessChange (e, target, name);
		},
		
		"RemoveLimits<click>": function(e, target, name) {
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessRemove (e, target, name);
		},
		
		"Term": function(sMessage, oData, sSrc) {
		    this.ProcessTerm (sMessage, oData, sSrc);
		},
		
		/* actions from the LimitsPage */
		
		"ClearAllLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessClearAll(e, target, name);
		},
		
		"ApplyLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessApply(e, target, name);
		},
		
		"CancelLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessCancel(e, target, name);
		}
		
	}, //end listen
	
	/* actions from the Limits activated message area */
	
	"ProcessChange" : function(e, target, name){
		Portal.Portlet.Entrez_LimitsTab.WaitingForSearchTerm = true;	
		Portal.Portlet.Entrez_LimitsTab.Link = target.href;
		this.send.SendSearchBarTerm();
	},
	
	"ProcessRemove" : function(e, target, name){
		this.send.Cmd({'cmd': 'removelimits'});
		Portal.requestSubmit();
	},
	
	"ProcessTerm": function(sMessage, oData, sSrc) {
        if (Portal.Portlet.Entrez_LimitsTab.WaitingForSearchTerm) { // make sure ProcessChange was clicked
            Portal.Portlet.Entrez_LimitsTab.WaitingForSearchTerm = false; 

		    if (oData.term){
		        Portal.Portlet.Entrez_LimitsTab.Link += "?term=" + escape(oData.term);
	        }
		    window.location = Portal.Portlet.Entrez_LimitsTab.Link;        
        }       
    },
   
    /* actions from the LimitsPage */
    
    "ProcessCancel" : function(e, target, name){
		history.back();
    },
    
	"ProcessApply" : function(e, target, name){
	    this.send.SendSearchBarTerm();
	    this.send.Cmd({'cmd': 'search'});
		Portal.requestSubmit();
	},
	
	// Implementation will have to change depending on database. All Limit options will have to be cleared.
	"ProcessClearAll" : function(e, target, name){
		this.ClearTagTerms();
	},
	
	"ClearTagTerms": function(){
	    this.getInput("LimitsField").options[0].selected = true;
	},
	
	// Provide implementation for this function if you need to collect some data before the form is submitted.
	// This is necessary if you cannot directly depend on getting form element values from this
	// page into portlet attributes in your Limits portlet after submit
	"beforesubmit": function(){
	    return false;
	}

},

{
    'WaitingForSearchTerm': false,
    'Link': ''
});


// Clear all checkboxes inside target node
function setAll(nodeName, value) {
   if (!document.getElementById) return false;
   var node= document.getElementById(nodeName);

   if (node) {
      var cbs = node.getElementsByTagName("INPUT");
      for (var i = 0; i < cbs.length; i++) {
         var cb = cbs[i];
         if (cb.getAttribute("TYPE").toUpperCase() == "CHECKBOX") {
            cb.checked = value;
         } else {
             cb.value = ""; 
		 }
      }
   }
   return false;
}

;
Portal.Portlet.LimitsTab = Portal.Portlet.Entrez_LimitsTab.extend ({

    init: function (path, name, notifier) {		
		this.base (path, name, notifier);
		
		// show date block if range is selected on page load
		if (this.getInput("pmfilter_PDatLimit")){
		    this.PDateRange();
		}
    },
    
	beforesubmit: function ()
	{
		this.CollectArchived ();
		this.CollectResorces ();
		this.CollectSubjects ();
		this.CollectContent ();
		return false;
	},    
    
    listen: {
	
	    /* actions from the Limits activated message area */
		
		"ChangeLimits<click>": function(e, target, name) {
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessChange (e, target, name);
		},
		
		"RemoveLimits<click>": function(e, target, name) {
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessRemove (e, target, name);
		},
		
		"Term": function(sMessage, oData, sSrc) {
		    this.ProcessTerm (sMessage, oData, sSrc);
		},
		
		/* actions from the LimitsPage */
		
		"ClearAllLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessClearAll(e, target, name);
		},
		
		"ApplyLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessApply(e, target, name);
		},
		
		"CancelLimits<click>": function(e, target, name){
		    e.preventDefault();
	        e.stopPropagation();
		    this.ProcessCancel(e, target, name);
		},
		
		"LimitsPYrFrom<change>": function(e, target, name){
		    this.getInputs("LimitsPYr")[1].checked = true;
		},
		
		"LimitsPYrTo<change>": function(e, target, name){
		    this.getInputs("LimitsPYr")[1].checked = true;
		},
		
		"pmfilter_PDatLimit<change>": function(e, target, name){
		    this.PDateRange();
		},
		
		"pmfilter_PDatRange_MinYear<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		},
		"pmfilter_PDatRange_MinMonth<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		},
		"pmfilter_PDatRange_MinDay<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		},
		"pmfilter_PDatRange_MaxYear<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		},
		"pmfilter_PDatRange_MaxMonth<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		},
		"pmfilter_PDatRange_MaxDay<focus>": function(e, target, name){
		    this.DateFieldFocus(target);
		}
		
	}, //end listen
	
	"ProcessCheckBox": function( name){
		var a = $(name);
		if (a != null) 
		{
			var v = $(name+'_msg');
			if( v != null )
			{ 
				if( document.getElementById(name).checked )
					this.setValue(name, document.getElementById(name+'_msg').value);
				else	
					this.setValue(name, "no");
			}		
		}	
	},
	
	"ProcessClearAll" : function(e, target, name){
		/*this.base(e, target, name);*/
		this.BooksClearAll();
	},
	
	"BooksClearAll": function (){
		setAllCB ('archived', false); 
		this.setValue("bsfilter_ShowArchived", "no");
	
		setAllCB ('rtype', false); 
		setAllCB ('stype', false); 
		setAllCB ('ctype', false);
		
	    setAll ('PDatesSelBlock', false);
	    document.getElementById('PDatesSelBlock').style.display = 'none';
	    this.getInput("pmfilter_PDatLimit").options[0].selected = true;
	    
	    this.getInputs("LimitsPYr")[0].checked = true;
	    this.getInput("LimitsPYrFrom").options[0].selected = true;
	    this.getInput("LimitsPYrTo").value = 'present';
	    
		return false; 
	},
	
	"PDateRange": function (){
	    if (this.getValue("pmfilter_PDatLimit") == 'daterange'){
	        document.getElementById('PDatesSelBlock').style.display = 'block';
	    }
	    else {
	        document.getElementById('PDatesSelBlock').style.display = 'none';
	    }
	},
	
	"DateFieldFocus" : function(target){
	    if (target.value in {'YYYY':1, 'MM':1, 'DD':1}){
	        target.className = "";
	        target.value = "";
	    }
	},

	"CollectArchived" : function ()
	{
		this.ProcessCheckBox( "bsfilter_ShowArchived");
	},

	"CollectContent" : function ()
	{
		this.ProcessCheckBox( "bsfilter_FigContentType");
		this.ProcessCheckBox( "bsfilter_TabContentType");
		this.ProcessCheckBox( "bsfilter_GlosContentType");
	},

	"CollectResorces" : function ()
	{
		this.AddToQuery ('bsfilter_ResType', 'ResourceType', 'EntrezSystem2.PEntrez.Books.LimitsTab.resTypeOperand', 'OR', "pmfilter_ResType", "pmfilter_ResTypeMsg", "Resource Type", "pmfilter_ResTypeXML");
	},

	"CollectSubjects" : function ()
	{
		this.AddToQuery ('bsfilter_Subj', 'Subject', 'EntrezSystem2.PEntrez.Books.LimitsTab.subjTypeOperand', 'OR', "pmfilter_SubjType", "pmfilter_SubjTypeMsg", "Subject", "pmfilter_SubjTypeXML");
	},

   "AddToQuery" : function (id, field, selector, defval, targetid, msgid, txt, xmlid)
   {
		if (!document.getElementsByTagName || !document.getElementById) 
			return; 
	
		var page = this.HiddenValue( 'EntrezSystem2.PEntrez.Books.PageController.PreviousPageName');		
		if( page != 'limits' )
			return;
	
		var ln = id.length;
		var query_add = "";
		var msg = "";
		var xml = "";
		var op = "";
		var operation = defval;
		if( selector != '' )
			operation = this.SelectorValue (selector, defval);
		var inps = document.getElementsByTagName ("INPUT")
		for (var i = 0; i < inps.length; i++) 
		{
			var thisNode = inps[i];
			if (thisNode.type.toUpperCase() == "CHECKBOX" ) 
			{
				var thisId = thisNode.id;
				var s1 = thisId.substring (ln, -ln), s2 = thisId.substring (ln);
				if ((id == s1) && (s2.match (/[0-9]+/))) 
				{
					if( thisNode.checked )
					{
						var v = thisNode.value;
						if ((v.length > 0) && (!v.match (/~[\s]*$/))) 
						{
							query_add = query_add + op + '"' + v + '"[' + field + ']';
							if (!(op.length > 0))
								op = " " + operation + " ";
							if( msg == "" )
								msg = txt+": ";
							else
								msg = msg + " " + op.toLowerCase() + " ";	
							msg = msg + v;
							
							xml += "<Limit><Kind>"+field+"</Kind><Id>"+thisId+"</Id><Value>"+v+"</Value></Limit>";	
						}
					}	
				}
			}
		}
		
		this.setValue( targetid, query_add);  
		this.setValue( msgid, msg);  
	
		if( xml.length > 0 ) 
			xml = "<Limits>"+xml+"</Limits>";
		else
			xml = "<set/>";	
	
		this.setValue( xmlid, xml);  
	},
	
	"SelectorValue" : function (sname, defval)
	{
		if (!document.getElementsByName || !document.getElementById) 
			return; 
		var value = defval;
		if (!value.length > 0) 
			value = "AND";

		if ( sname.length > 0 ) 
		{
			var cbs = $N(sname);		  
			for (var i = 0; i < cbs.length; i++) 
			{
				var thisNode = cbs[i];
				if (thisNode.type.toUpperCase() == "RADIO" ) 
				{
					if (thisNode.checked) 
					{
						value = thisNode.value;
						return value;
					}
				}
			}
		}
		return value;
	},

	"HiddenValue" : function (sname)
	{
		if (!document.getElementsByName || !document.getElementById) 
			return; 
		var value = '';

		if ( sname.length > 0 ) 
		{
			var cbs = $N(sname);		  
			for (var i = 0; i < cbs.length; i++) 
			{
				var thisNode = cbs[i];
				if (thisNode.type.toUpperCase() == "HIDDEN" ) 
				{
					value = thisNode.value;
					return value;
				}
			}
		}
		return value;
	}
});

// Clear all checkboxes inside target node
function setAllCB(nodeName, value) {
   if (!document.getElementById) return false;
   var node= document.getElementById(nodeName);
   if (node) 
   {
      var cbs = node.getElementsByTagName("INPUT");
      for (var i = 0; i < cbs.length; i++) {
         var cb = cbs[i];
         if (cb.getAttribute("TYPE").toUpperCase() == "CHECKBOX") 
         {
         	cb.checked = value;
         	if( !value )
         	{
            	cb.removeAttribute( "checked");
            }	
  	 	 }
      }
   }
   return false;
}


;
Portal.Portlet.Entrez_Messages = Portal.Portlet.extend({

	init: function(path, name, notifier) {
		this.base(path, name, notifier);
		
		this.setMsgAreaClassName();
	},
	
	listen: {
	   /* messages from message bus*/
		
		'AddUserMessage' : function(sMessage, oData, sSrc) {
		    // create new message node
		    var msgnode = document.createElement('li');
		    if (oData.type != ''){
		        msgnode.className = oData.type + ' icon'; 
		    }
		    if (oData.name != ''){
		        msgnode.id = oData.name; 
		    }
		    msgnode.innerHTML = "<span class='icon'>" + oData.msg + "</span>";
		    
		    // add new node as first message in message block (not ads that look like messages)
		    var parent = document.getElementById('msgportlet');
		    if (parent){
    		    var oldnode = document.getElementById(oData.name);
    		    if (oldnode){
    		        parent.removeChild(oldnode);
    		    }
    		    var firstchild = parent.firstChild;
    	        if (firstchild){
                    parent.insertBefore(msgnode, firstchild);
                }
                else{
                    parent.appendChild(msgnode);
                }
                this.setMsgAreaClassName('true');
            }
            //if there was no ul, create one, then insert the li
            else {
                var msgarea = document.getElementById('messagearea');
                if (msgarea){
                    var msgportlet = document.createElement('ul');
                    msgportlet.className = 'messages';
                    msgportlet.id = 'msgportlet';
                    msgportlet.appendChild(msgnode);
                    if (msgarea.firstChild){
                         msgarea.insertBefore(msgportlet, msgarea.firstChild);
                    }
                    else{
                        msgarea.appendChild(msgportlet);
                    }
                    this.setMsgAreaClassName('true');
                }
            }
		},
		
		'RemoveUserMessage' : function(sMessage, oData, sSrc) {
		    var msgnode = document.getElementById(oData.name);
		    if (msgnode){
		        var parent = document.getElementById('msgportlet'); 
		        if (parent){
    		        parent.removeChild(msgnode);
    		        this.setMsgAreaClassName();
    		        // if the parent ul has no children then remove the parent
    		        if (parent.firstChild){}
    		        else {
    		            if (document.getElementById('messagearea')) {
    		                document.getElementById('messagearea').removeChild(parent);
    		            }
    		        }
    		    }
		    }
		}
	}, // end listen
	
	'setMsgAreaClassName' : function(hasMsg){
        var msgarea = document.getElementById('messagearea');
	    if (msgarea){
	        var msgclass = "empty";
	        
    	    // if a message was added, hasMsg is set to true at call time to avoid checks. 
    	    // by default, hasMsg is false.
    	    if (hasMsg == 'true'){
    	        msgclass = "messagearea";
    	    }
    	    else if (msgarea.getElementsByTagName('li').length > 0){
                msgclass = "messagearea"; 
        	}
        	
            msgarea.className = msgclass;
        }
	} // end setMsgAreaClassName
});
		
		
;
Portal.Portlet.Entrez_RVBasicReport = Portal.Portlet.extend({
	
	init: function(path, name, notifier) {
		console.info("Created report portlet");
		this.base(path, name, notifier);
	},
	
	send: {
		'ItemSelectionChanged': null,
		'ClearIdList': null,
		'Cmd': null
	},
	
	listen: {
		"uid<click>" : function(e, target, name){
		    this.UidClick(e, target, name);
		},
		
		"RemoveClip<click>" : function(e, target, name){
		    this.ClipRemoveClick(e, target, name);              
		}
	},
	
	'UidClick': function(e, target, name){	
		this.send.ItemSelectionChanged( { 'id': target.value,
		                                  'selected': target.checked });
	},
	
	'ClipRemoveClick': function(e, target, name){
	    this.send.ClearIdList();
		this.send.Cmd({'cmd': 'deletefromclipboard'});
		this.send.ItemSelectionChanged( { 'id': target.getAttribute('uid'),
		                                  'selected': true });
		Portal.requestSubmit();
	}
});
   

;
{
    var oThis;
Portal.Portlet.Report_ResultsView = Portal.Portlet.Entrez_RVBasicReport.extend({
    
	init: function(path, name, notifier) {
	  oThis = this;
	  
      this.base(path, name, notifier);  
	      
	  jQuery(function(){		
		  jQuery(".rprt .jig-ncbitoggler").bind("ncbitogglerclosed", function(){
		      jQuery(this).find(".h2rep").html(jQuery(this).attr("title-open"));    
		  });			    
			    
		  jQuery(".rprt .jig-ncbitoggler").bind("ncbitoggleropen",function(){
		      var link = jQuery(this);
		      
		      jQuery(this).find(".h2rep").html(link.attr("title-hidden"));    
		
              var bookBlock = oThis.GetBookBlock(link.attr('id'));
              if (bookBlock && bookBlock.innerHTML == '')
              {
                  oThis.DoSearchRequest(link, bookBlock);
              }
		  });		    
		});
	
	},
	
	send: {
		'ItemSelectionChanged': null,
		'ClearIdList': null,
		'Cmd': null		
	},

    'ajaxResponse' : "",

   	'DoSearchRequest': function(link, container) 
   	{
        var args = {
            'Db' : 'books',
            'Term' : link.data("term"),
            'MaxCount' : link.data("maxcnt"),
            'qk': link.data('qk'),
            'groupby': link.data('groupby') 
        };
                          
        try {
           var response = smHttpCall(
               {
                   url: "/books/",
                   portletPath: "EntrezSystem2.PEntrez.Books.AjaxHandler",
                   actionName: "SubItems"
               },
               args,
               {
                   func: this.DoSearchResponse,
                   args: { container: container } 
               }
           );
               
        }
        catch(err)
        {
            this.DisplayResponse(container, this.FormatError(err));
        }
    },
     
     'FormatError': function(err)
     {
     	return '<p>Error: ' + err + '</p>';
     },
     
     'DisplayResponse': function(container, html)
     {
         container.innerHTML = html;
     },
     
	 'GetBookBlock': function(book)
     {
     	if (book != '')
     	{
     	 	var booksToggle = document.getElementById( book+"_slave");
   			return booksToggle;
     	}
    	return false;
     },
     	 
	 'DoSearchResponse': function(args, response, status)
     {
        var html = response;
        
		try {		 
	      	if (status != "success")
	      	{
                html = oThis.FormatError('No response from the server.');
            }
        }
	    catch (e) {
             html = oThis.FormatError(e.message);
        }                 
        
        oThis.DisplayResponse(args.container, html);
     }
});
	
}
;
/**
 * BK-10177 The function does not replace "span" with "form" tag anymore because of
 * issues in IE. It simulates form behavior instead by listening for button click
 * and Enter key in input box  
 */
jQuery(function($) 
{
    var form = $('span#bk_srch');
    
    if (!form.size()) {
        return;
    }
        
   // Replace span with form element, copy all attributes and child elements
   // The hack is needed for "search-within-book" form
   // http://stackoverflow.com/questions/8584098/how-to-change-an-element-type-using-jquery
   // It also updates value of "form" variable 
   form.replaceWith(function() {
       var attrs = {};

       $.each(this.attributes, function(idx, attr) {
           attrs[attr.nodeName] = attr.nodeValue;
       });
       
       form = $("<form/>", attrs).append($(this).contents());
       return form
   });
   
   // Change submission link
   // BK-10177, BK-11186, BK-11185
   document.forms[0].action = $('form#bk_srch').attr('action');
   
   // BK-10177
   // following code fixes submission issues in IE
   var term  = form.find('#bk_srch_term'),
       submit_btn  = form.find('#bk_srch_submit');

   submit_btn.click(function(e) {
       e.preventDefault()
       window.location = form.attr('action')+'?'+term.attr('name')+'='+encodeURIComponent(term.val());
       return false;
   });
    
   term.keydown(function(e) {
       // Submit form on enter
       if (e.keyCode == 13) {
       e.preventDefault()
           return submit_btn.click();
       }
   });
});


;
Portal.Portlet.LinkListPageSection = Portal.Portlet.NCBIPageSection.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);
	},
	
	"getPortletPath" : function(){
	    return (this.realname + ".NCBIPageSection");
	}
});
;
Portal.Portlet.ImageListOnlyPageSection = Portal.Portlet.LinkListPageSection.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);
		jQuery(".imagepopup").bind("click",this.showImagePopUp);
	},
	/*This is required for remembering collapse state of Ad*/
	"getPortletPath" : function(){
	    return (this.realname + ".LinkListPageSection.NCBIPageSection");
	},
	"showImagePopUp":function(){
	    window.open(jQuery(this).attr("image-link"),'figure','resizable=no,scrollbars=yes,location=no,status=yes,menubar=no,width=1024,height=800');
	}
});
;
Portal.Portlet.ImageSection = Portal.Portlet.ImageListOnlyPageSection.extend ({
	init: function (path, name, notifier){
	    console.info("Created Books Image Ad");
		this.base (path, name, notifier);
	},
	/*This is required for remembering collapse state of Ad*/
	"getPortletPath" : function(){
	    return (this.realname + ".ImageListOnlyPageSection.LinkListPageSection.NCBIPageSection");
	}
});


;
Portal.Portlet.RelatedDataLinks = Portal.Portlet.NCBIPageSection.extend({
    init: function (path, name, notifier) {
        var link_descr;
        console.info("Created RelatedDataLinks Ad");
        this.base(path, name, notifier);
        this.initializeControls();
    },
      
    send: { 
        'SendSavedUidList': null
    }, 
    
    listen: {       
        'rdDatabase<change>' : function (e, target, name) {
            this.setSelectButton();
            this.makeXmlHttpCall();
        },
        
        'rdFind<click>':function (e, target, name) {
            e.preventDefault();
	        e.stopPropagation();
            this.SendLink(e, target, name); 
        },
        
        'rdLinkOption<change>':function (e, target, name) {
            this.SetDescription(e, target, name);
        },
        
        //message from DbConnector with selectedIds
        'newUidSelectionList': function(sMessage, oData, sSrc){
            Portal.Portlet.RelatedDataLinks.selectedIdList = oData.list;
        }
    },    
    
    'getPortletPath' : function(){
        return (this.realname + ".NCBIPageSection");
    },   
    
    'responder' : function (responseObject, userArgs) {
        var seldb = document.getElementById('rdDatabase').selectedIndex;
        if(seldb!=0){
            //use "try" so we can gracefully handle errors
            try {
                // Handle timeouts
                if (responseObject.status == 408) {
                    
                    //display an appropriate error message
                }
                
                //convert the string response into a JavaScript Object
                var resp = responseObject.responseText;
                
                console.debug('This is what was returned from the portlet');
                console.info(resp);
                //why don't you take a look at this in firebug?
                
                resp = '(' + resp + ')';
                json_obj = eval(resp);
                
                console.debug('This is the object that we created from the portlet response');
                console.info(json_obj);
                //now look at what it is.
                
                var link_name = json_obj.response;
                link_name = link_name.split(',');
                
                var link_disp_name = json_obj.response_disp;
                link_disp_name = link_disp_name.split(';');
                
                link_descr = json_obj.response_descr;
                link_descr = link_descr.split('||');
                if(link_descr[0]!=''){
                    document.getElementById('rdDescr').innerHTML = link_descr[0];
                    document.getElementById('rdDescr').style.display = "block";
                }
                
                var link_count = link_name.length;
                if(link_count>0){
                    for(var countr=0;countr<link_count;countr++){
                        if(countr==0)
                            document.getElementById('rdLinkOption').options[countr] = new Option(link_disp_name[countr], link_name[countr], true, false);
                        else
                            document.getElementById('rdLinkOption').options[countr] = new Option(link_disp_name[countr], link_name[countr], false, false);
                    }
                }
                
                if(link_count>1)
                    document.getElementById('rdOption').style.display = "block";
                
                jQuery("#rdFind").ncbibutton("enable");
                document.getElementById('rdDescr').style.display = "block";
                
                //Now we will update the display, and change the second input.
               /* this .setValue('output', json_obj.response);*/
                
                
                
                //now catch any errors that may have occured
            }
            catch (e) {
                //display an appropriate error.  Remember, user-friendly messages!
                alert("Please refresh the page and try again. (" + e + ")");
            }
        }
    }, 
    
    'SendLink': function(e, target, name){ 
        window.location = "/" + this.getValue("rdDatabase") + "?linkname=" +  this.getValue("rdLinkOption")
         + (Portal.Portlet.RelatedDataLinks.selectedIdList != '' ? 
            ("&from_uid=" + Portal.Portlet.RelatedDataLinks.selectedIdList) : 
            (jQuery('#rdqk') && jQuery('#rdqk').val() != '' ? "&querykey=" + jQuery('#rdqk').val() : ""));
        
    },
    
    'initializeControls':function(){
        document.getElementById('rdDatabase') .selectedIndex = 0;
        // Resetting Database select on page load/reload
        this.setSelectButton();
    },
    
    'setSelectButton':function(){
        document.getElementById('rdOption').style.display = "none";
        document.getElementById('rdDescr').style.display = "none";
        document.getElementById('rdFind').disabled = true;
        
        this.deleteOption("rdLinkOption");
    },
    
    /*
    FUNCTION NAME: deleteOption
    Delete all the current options from the required drop down menu
    */
    'deleteOption':function(selectbox){
        while(document.forms[0].elements[selectbox].childNodes.length>0) {
            document.forms[0].elements[selectbox].removeChild(document.forms[0].elements[selectbox].childNodes[0])
        }
    },
    
    'SetDescription':function(e, target, name){
        var selOpt = document.getElementById('rdLinkOption').selectedIndex;
        document.getElementById('rdDescr').innerHTML = link_descr[selOpt];
    },
    
    'makeXmlHttpCall':function(){
        var dbto = this.getValue("rdDatabase");
    
            var siteName = document.forms[0][ 'p$st' ].value;
            
            var portletPath = this .realname;
            
            var actionName = 'XMLHTTPhandler';
            
            var args = {
                'related_data_db' : dbto,
                'Db' : document.getElementById('DbName').value
            };
            
            var callback = this .responder;
            
            var userArgs = {
            };
            
            var oThis = this;
            
            try {
                var response = xmlHttpCall(siteName, portletPath, actionName, args, callback, userArgs, oThis);
            }
            catch (err) {
                alert('The following error has occured: ' + err);
            }
            
    }
},
{
	selectedIdList: ''
});
;
Portal.Portlet.Books_RelatedDataLinks = Portal.Portlet.RelatedDataLinks.extend({
    init: function (path, name, notifier) {
        var link_descr;
        this.base(path, name, notifier);
        this.initializeControls();
    },
    
    'getPortletPath' : function(){
        return (this.realname + ".RelatedDataLinks.NCBIPageSection");
    }

});

;
Portal.Portlet.Discovery_SearchDetails = Portal.Portlet.NCBIPageSection.extend ({
	init: function (path, name, notifier){
		this.base (path, name, notifier);		
	},
	
	listen: {	    
	    "SearchDetailsTerm<keypress>": function(e, target, name) {
			var event = e || utils.fixEvent (window.event);
			if ((event.keyCode || event.which) == 13) {
			    // Emulate button click
			    this.SearchDetailsTermPress(event, e, target, name);
			}
		},
	    
        "SearchDetailsQuery<click>":  function(e, target, name) {       
		     this.SearchDetailsQueryClick(e, target, name);
		}		
	},
	
	'getPortletPath' : function(){	    
        return (this.realname + ".NCBIPageSection");
    },   
	
	"SearchDetailsTermPress" : function(event,e, target, name){
    	event.returnValue = false;
    	if (event.stopPropagation != undefined)
              event.stopPropagation ();   
    	if (event.preventDefault != undefined)
              event.preventDefault ();
              
    	this.ProcessSearch (target,e);
    	return false;
	},
	
	"SearchDetailsQueryClick": function(e, target, name){
	    this.ProcessSearch (target,e);
	},
	
	"ProcessSearch": function(target,e){
	    e.preventDefault();
	    e.stopPropagation();
	    if (this.getValue('SearchDetailsTerm') != ''){
	        window.location = "/" + this.getInput('SearchDetailsTerm').getAttribute('db') + "?term=" 
    		 + escape(this.getValue('SearchDetailsTerm')) + "&cmd=DetailsSearch";
    	}
    	else{
    	    alert ('There is no term in the Query Translation box to search.');
    	}
	}
	
});
;
(function( $ ){ // pass in $ to self exec anon fn
    // on page ready
    $( function() {
        $('li.ralinkpopper').each( function(){
            var $this = $( this );
            var popper = $this;
            var popnode = $this.find('div.ralinkpop');
            var popid = popnode.attr('id') || $.ui.jig._generateId('ralinkpop');
            popnode.attr('id', popid);
            popper.ncbipopper({
                destSelector: "#" + popid,
                destPosition: 'top right', 
                triggerPosition: 'middle left', 
                hasArrow: true, 
                arrowDirection: 'right',
                isTriggerElementCloseClick: false,
                adjustFit: 'none',
                openAnimation: 'none',
                closeAnimation: 'none',
                delayTimeout : 130
            });
        }); // end each loop  
    });// end on page ready
})( jQuery );

Portal.Portlet.HistoryDisplay = Portal.Portlet.NCBIPageSection.extend({

	init: function(path, name, notifier) {
		console.info("Created History Ad...");
		this.base(path, name, notifier);    
	},
	
	send: {
      'Cmd': null      
    },   
    
    receive: function(responseObject, userArgs) {  
         var cmd = userArgs.cmd;
         var rootNode = document.getElementById('HTDisplay'); 
         var ul = document.getElementById('activity');
         var resp = responseObject.responseText;
             
         if (cmd == 'HTOn') { 
            rootNode.className = '';    // hide all msg and the turnOn link
            try {
            //alert(resp);
                // Handle timeouts
                if (responseObject.status == 408) { 
                    rootNode.className = 'HTOn'; // so that the following msg will show up
                    rootNode.innerHTML = "<p class='HTOn'>Your browsing activity is temporarily unavailable.</p>";
                    return;
                }
                   
                 // Looks like we got something...
                 resp = '(' + resp + ')';
                 var JSONobj = eval(resp);
                 
                 // Build new content (ul)
                 var newHTML = JSONobj.Activity;
                 var newContent = document.createElement('div');
                 newContent.innerHTML = newHTML;
                 var newUL = newContent.getElementsByTagName('ul')[0];
                 //alert(newHTML);
                 //alert(newContent.innerHTML);
                 //alert(newUL.innerHTML);
                 // Update content
                 rootNode.replaceChild(newUL, ul);
                 //XHR returns no activity (empty ul), e.g. activity cleared
                 if (newUL.className == 'hide')                     
                     rootNode.className = 'HTOn';  // show "Your browsing activity is empty." message
                 
            }         
            catch (e) {
                //alert('error');
                rootNode.className = 'HTOn'; // so that the following msg will show up
                rootNode.innerHTML = "<p class='HTOn'>Your browsing activity is temporarily unavailable.</p>";
           }
         }
         else if (cmd == 'HTOff') {                         
             if (ul != null) { 
                 ul.className='hide'; 
                 ul.innerHTML = ''; // clear activity
             }
             rootNode.className = 'HTOff';    // make "Activity recording is turned off." and the turnOn link show up             
         }
         else if (cmd == 'ClearHT') { 
             var goAhead = confirm('Are you sure you want to delete all your saved Recent Activity?');
             if (goAhead == true) { 
                 if ( rootNode.className == '') { //                 
                     rootNode.className = 'HTOn';  // show "Your browsing activity is empty." message                                  
                     if (ul != null) {
                         ul.className='hide'; 
                         ul.innerHTML = '';
                     }
                 }
             }
         } 
         
    },
    
	listen: {
	  'Cmd' : function(sMessage, oData, sSrc){
			console.info("Inside Cmd in HistoryDisplay: " + oData.cmd);
			this.setValue("Cmd", oData.cmd);
	  },	  
		
      "HistoryToggle<click>" : function(e, target, name){
         //alert(target.getAttribute("cmd"));
         this.send.Cmd({'cmd': target.getAttribute("cmd")});         
         console.info("Inside HistoryToggle in HistoryDisplay: " + target.getAttribute("cmd"));
         
         //var site = document.forms[0]['p$st'].value;
         var cmd =  target.getAttribute("cmd");     
               
         // Issue asynchronous call to XHR service, callback is to update the portlet output            
         this.doRemoteAction(target.getAttribute("cmd"));                      
      }, 
      
      "HistoryOn<click>" : function(e, target, name){
         this.send.Cmd({'cmd': target.getAttribute("cmd")});
         //$PN('Pubmed_ResultsSearchController').getInput('RecordingHistory').value = 'yes';		 
         console.info("Inside HistoryOn in HistoryDisplay: " + target.getAttribute("cmd"));
         this.doRemoteAction(target.getAttribute("cmd"));         
      },
      
      "ClearHistory<click>" : function(e, target, name){
         this.send.Cmd({'cmd': target.getAttribute("cmd")});
         this.doRemoteAction(target.getAttribute("cmd"));         
      }
    },
    
    'getPortletPath': function(){
        return this.realname + ".NCBIPageSection";
    }, 
    
    'doRemoteAction': function(command) {
         var site = document.forms[0]['p$st'].value;          
	     var resp = xmlHttpCall(site, this.realname, command, {}, this.receive, {'cmd': command}, this);
    }
});

;
Portal.Portlet.DbConnector = Portal.Portlet.extend({

	init: function(path, name, notifier) {
		var oThis = this;
		console.info("Created DbConnector");
		this.base(path, name, notifier);
		
		// reset Db value to original value on page load. Since LastDb is the same value as Db on page load and LastDb is not changed on
		// the client, this value can be used to reset Db. This is a fix for back button use.
		if (this.getValue("Db") != this.getValue("LastDb")){
		    this.setValue("Db", this.getValue("LastDb"));
		}
     
		// the SelectedIdList and id count from previous iteration (use a different attribute from IdsFromResult to prevent back button issues)
		Portal.Portlet.DbConnector.originalIdList = this.getValue("LastIdsFromResult");
		console.info("originalIdList " + Portal.Portlet.DbConnector.originalIdList);
		// if there is an IdList from last iteration set the count
		if (Portal.Portlet.DbConnector.originalIdList != ''){
			Portal.Portlet.DbConnector.originalCount = Portal.Portlet.DbConnector.originalIdList.split(/,/).length;
		}

		notifier.setListener(this, 'HistoryCmd', 
        	function(oListener, custom_data, sMessage, oNotifierObj) {
           		var sbTabCmd = $N(oThis.path + '.TabCmd');
           		sbTabCmd[0].value = custom_data.tab;
        	}
    		, null);
    
	},

	send: {
   		'SelectedItemCountChanged': null,
   		'newUidSelectionList': null,
   		'SavedSelectedItemCount': null,
   		'SavedUidList': null
	},

	listen: {
	
		//message from Display bar on Presentation change 
		'PresentationChange' : function(sMessage, oData, sSrc){
			
			// set link information only if it exists
			if (oData.dbfrom){
				console.info("Inside PresentationChange in DbConnector: " + oData.readablename);
				this.setValue("Db", oData.dbto);
				this.setValue("LinkSrcDb", oData.dbfrom);
				this.setValue("LinkName", oData.linkname);
				this.setValue("LinkReadableName", oData.readablename);
			}
			//document.forms[0].submit();
		},
		
		// various commands associated with clicking different form control elements
		'Cmd' : function(sMessage, oData, sSrc){
			console.info("Inside Cmd in DbConnector: " + oData.cmd);
			this.setValue("Cmd", oData.cmd);
			
			// back button fix, clear TabCmd
			if (oData.cmd == 'Go' || oData.cmd == 'PageChanged' || oData.cmd == 'FilterChanged' || 
			oData.cmd == 'DisplayChanged' || oData.cmd == 'HistorySearch' || oData.cmd == 'Text' || 
			oData.cmd == 'File' || oData.cmd == 'Printer' || oData.cmd == 'Order' || 
			oData.cmd == 'Add to Clipboard' || oData.cmd == 'Remove from Clipboard' || 
			oData.cmd.toLowerCase().match('details')){
				this.setValue("TabCmd", '');
				console.info("Inside Cmd in DbConnector, reset TabCmd: " + this.getValue('TabCmd'));
			}

		},
		
		
		// the term to be shown in the search bar, and used from searching
		'Term' : function(sMessage, oData, sSrc){
			console.info("Inside Term in DbConnector: " + oData.term);
			this.setValue("Term", oData.term);
		},
		
		
		// to indicate the Command Tab to be in
		'TabCmd' : function(sMessage, oData, sSrc){
			console.info("Inside TABCMD in DbConnector: " + oData.tab);
			this.setValue("TabCmd", oData.tab);
			console.info("DbConnector TabCmd: " + this.getValue("TabCmd"));
		},
		
		
		// message sent from SearchBar when db is changed while in a Command Tab
		'DbChanged' : function(sMessage, oData, sSrc){
			console.info("Inside DbChanged in DbConnector");
			this.setValue("Db", oData.db);
		},
		
		// Handles item select/deselect events
		// Argument is { 'id': item-id, 'selected': true or false }
		'ItemSelectionChanged' : function(sMessage, oData, oSrc) {
			var sSelection = this.getValue("IdsFromResult");
			var bAlreadySelected = (new RegExp("\\b" + oData.id + "\\b").exec(sSelection) != null);
	       	var count =0;
	       	
			if (oData.selected && !bAlreadySelected) {
				sSelection += ((sSelection > "") ? "," : "") + oData.id;
			   	this.setValue("IdsFromResult", sSelection);
			   	if (sSelection.length > 0){
			   		count = sSelection.split(',').length;
			   	}
			   	this.send.SelectedItemCountChanged({'count': count});
			   	this.send.newUidSelectionList({'list': sSelection});
			   	jQuery(document).trigger("itemsel",{'list': sSelection});
		   	} else if (!oData.selected && bAlreadySelected) {
				sSelection = sSelection.replace(new RegExp("^"+oData.id+"\\b,?|,?\\b"+oData.id+"\\b"), '');
		   	   	this.setValue("IdsFromResult", sSelection);
				console.info("Message ItemSelectionChanged - IdsFromResult after change:  " + this.getValue("IdsFromResult"));
			   	if (sSelection.length > 0){
			   		count = sSelection.split(',').length;
			   	}
				console.info("Message ItemSelectionChanged - IdsFromResult length:  " + count);   
				this.send.SelectedItemCountChanged({'count': count});
			   	this.send.newUidSelectionList({'list': sSelection});
			   	jQuery(document).trigger("itemsel",{'list': sSelection});
		   	}
		},
				
		// FIXME: This is the "old message" that is being phased out.
		// when result citations are selected, the list of selected ids are intercepted here,
		// and notification sent that selected item count has changed.
		'newSelection' : function(sMessage, oData, sSrc){
		
			// Check if we already have such IDs in the list
			var newList = new Array();
			var haveNow = new Array();
			if(Portal.Portlet.DbConnector.originalIdList){
				haveNow = Portal.Portlet.DbConnector.originalIdList.split(',');
				newList = haveNow;
			}
			
			var cameNew = new Array();
			if (oData.selectionList.length > 0) {
				cameNew = oData.selectionList;
			}
			
			if (cameNew.length > 0) {
				for(var ind=0;ind<cameNew.length;ind++) {
					var found = 0;
					for(var i=0;i<haveNow.length;i++) {
						if (cameNew[ind] == haveNow[i]) {
							found = 1;
							break;
						}
					}
						//Add this ID if it is not in the list
					if (found == 0) {
						newList.push(cameNew[ind]);
					}
				}
			}
			else {
				newList = haveNow;
			}

				// if there was an IdList from last iteration add new values to old
			var count = 0;
			if ((newList.length > 0) && (newList[0].length > 0)){
				count = newList.length;
			}
			
			console.info("id count = " + count);
			this.setValue("IdsFromResult", newList.join(","));
			
			this.send.SelectedItemCountChanged({'count': count});
			this.send.newUidSelectionList({'list': newList.join(",")});
			jQuery(document).trigger("itemsel",{'list': newList.join(",")});
		},


		// empty local idlist when list was being collected for other purposes.
		//used by Mesh and Journals (empty UidList should not be distributed, otherwise Journals breaks)
		// now used by all reports for remove from clipboard function.
		'ClearIdList' : function(sMessage, oData, sSrc){
			this.setValue("IdsFromResult", '');
			this.send.SelectedItemCountChanged({'count': '0'});
			this.send.newUidSelectionList({'list': ''});
			jQuery(document).trigger("itemsel",{'list': ""});
		}, 


		// back button fix: when search backend click go or hot enter on term field,
		//it also sends db. this db should be same as dbconnector's db
		'SearchBarSearch' : function(sMessage, oData, sSrc){
			if (this.getValue("Db") != oData.db){
				this.setValue("Db", oData.db);
			}
		},
		
		// back button fix: whrn links is selected from DisplayBar,
		//ResultsSearchController sends the LastQueryKey from the results on the page
		// (should not be needed by Entrez 3 code)
		'LastQueryKey' : function(sMessage, oData, sSrc){
			if (this.getInput("LastQueryKey")){
				this.setValue("LastQueryKey", oData.qk);
			}
		},
		
		'QueryKey' : function(sMessage, oData, sSrc){
			if (this.getInput("QueryKey")){
				this.setValue("QueryKey", oData.qk);
			}
		},
		
		
		//ResultsSearchController asks for the initial item count in case of send to file 
		'needSavedSelectedItemCount' : function(sMessage, oData, sSrc){
			var count = 0;
			if(this.getInput("IdsFromResult")){
				if (this.getValue("IdsFromResult").length > 0){
					count = this.getValue("IdsFromResult").split(',').length;
				}
				console.info("sending SavedSelectedItemCount from IdsFromResult: " + count);
			}
			else{
				count = Portal.Portlet.DbConnector.originalCount;
				console.info("sending SavedSelectedItemCount from OriginalCount: " + count);
			}
			this.send.SavedSelectedItemCount({'count': count});
		},
		
		// Force form submit, optionally passing db, term and cmd parameters
		'ForceSubmit': function (sMessage, oData, sSrc)
		{
		    if (oData.db)
    			this.setValue("Db", oData.db);
		    if (oData.cmd)
    			this.setValue("Cmd", oData.cmd);
		    if (oData.term)
    			this.setValue("Term", oData.term);
    		Portal.requestSubmit ();
		},
		
		'LinkName': function (sMessage, oData, sSrc){
		    this.setValue("LinkName", oData.linkname);
		},
		
		'IdsFromResult': function (sMessage, oData, sSrc){
		    this.setValue("IdsFromResult", oData.IdsFromResult);
		},
		
		'SendSavedUidList': function (sMessage, oData, sSrc){
		    this.send.SavedUidList({'idlist': this.getValue("IdsFromResult")});
		}
		
	}, //listen
	
	/* other portlet functions */
	
	// DisplayBar in new design wants selected item count
	'SelectedItemCount': function(){
	    var count = 0;
		if(this.getInput("IdsFromResult")){
			if (this.getValue("IdsFromResult") != ''){
				count = this.getValue("IdsFromResult").split(',').length;
			}
		}
		else{
			count = Portal.Portlet.DbConnector.originalCount;
		}
		return count;
	},
	
	'SelectedItemList': function(){
		if(this.getInput("IdsFromResult") && this.getValue("IdsFromResult") != ''){
			return this.getValue("IdsFromResult");
		}
		else{
			return Portal.Portlet.DbConnector.originalIdList;
		}
		
	},
	setValue: function(name, value){
	    if(name == 'Term')
	        value = jQuery.trim(value);
	    this.base(name,value);
	}
},
{
	originalIdList: '',
	originalCount: 0
});

function getEntrezSelectedItemCount() {
    return $PN('DbConnector').SelectedItemCount();
}

function getEntrezSelectedItemList() {
    return $PN('DbConnector').SelectedItemList();
}
